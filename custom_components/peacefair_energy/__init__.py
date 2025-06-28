"""
Peacefair Energy Monitor Custom Component.

A Home Assistant custom component for communicating with Peacefair energy monitors.
This file has been modernized according to Home Assistant 2024.x+ development specifications.
"""
import logging
import os
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PROTOCOLS,
    STORAGE_PATH,
    UNSUBSCRIBE_LISTENER,  # Corrected constant name
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    UnitOfEnergy,
)
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)

# Service names and schema definitions
SERVICE_RESET_ENERGY = "reset_energy"
RESET_ENERGY_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})


async def async_setup(hass: HomeAssistant, hass_config: dict) -> bool:
    """Set up the top-level DOMAIN for the component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Asynchronously set up a config entry (e.g., a Peacefair device).

    This is the core function for loading the component.
    """
    config = config_entry.data
    options = config_entry.options

    protocol = PROTOCOLS[config[CONF_PROTOCOL]]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    slave = config[CONF_SLAVE]
    scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Create a coordinator to manage data updates for this device.
    coordinator = PeacefairCoordinator(hass, protocol, host, port, slave, scan_interval)

    # Store all data related to this config entry in a dedicated dictionary
    # keyed by its entry_id.
    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    # First data refresh.
    await coordinator.async_config_entry_first_refresh()

    # Forward the config to the sensor platform to create entities.
    await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor"])

    # Listen for configuration updates (e.g., changing scan interval from "Options").
    unsub = config_entry.add_update_listener(update_listener)
    hass.data[DOMAIN][config_entry.entry_id][UNSUBSCRIBE_LISTENER] = unsub

    # --- Register the reset energy service ---
    def service_handle(service):
        """Handle the 'reset_energy' service call."""
        _LOGGER.debug(f"Handling reset energy service call, target entity: {service.data.get(ATTR_ENTITY_ID)}")
        coordinator.reset_energy()

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_ENERGY,
        service_handle,
        schema=RESET_ENERGY_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Asynchronously unload a config entry."""
    # Call `async_forward_entry_unloads` to correctly unload entities.
    ok = await hass.config_entries.async_forward_entry_unloads(config_entry, ["sensor"])

    # Get the unload listener function from the data structure.
    entry_data = hass.data[DOMAIN].get(config_entry.entry_id, {})
    unsub = entry_data.get(UNSUBSCRIBE_LISTENER)

    if unsub:
        unsub()

    # If the platform is successfully unloaded, clean up data and files.
    if ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        if not hass.data[DOMAIN]:  # If it is the last device, clean up the top-level domain.
            hass.data.pop(DOMAIN)

        # Asynchronously perform file I/O operations.
        def do_blocking_file_operations():
            """Perform synchronous file deletion operations."""
            storage_path = hass.config.path(STORAGE_PATH)
            record_file = hass.config.path(f"{STORAGE_PATH}/{config_entry.entry_id}_state.json")
            reset_file = hass.config.path(f"{STORAGE_PATH}/{DOMAIN}_reset.json")
            
            _LOGGER.debug(f"Attempting to delete file: {record_file}")
            if os.path.exists(record_file):
                os.remove(record_file)

            _LOGGER.debug(f"Attempting to delete file: {reset_file}")
            if os.path.exists(reset_file):
                os.remove(reset_file)

            if os.path.exists(storage_path) and not os.listdir(storage_path):
                _LOGGER.debug(f"Storage directory is empty, deleting: {storage_path}")
                os.rmdir(storage_path)

        await hass.async_add_executor_job(do_blocking_file_operations)

    return ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle configuration option updates at runtime."""
    _LOGGER.debug("Configuration update detected, adjusting coordinator...")
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
    # Get the coordinator from the correct location.
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    coordinator.update_interval = timedelta(seconds=scan_interval)
    _LOGGER.debug(f"Coordinator update interval has been set to {scan_interval} seconds")


class PeacefairCoordinator(DataUpdateCoordinator):
    """A class to manage data fetching and polling for Peacefair devices."""

    def __init__(self, hass, protocol, host, port, slave, scan_interval):
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({host})",
            update_interval=timedelta(seconds=scan_interval),
        )
        self._hass = hass
        self._host = host
        self._hub = ModbusHub(protocol, host, port, slave)

    @property
    def host(self):
        """Return the host address managed by this coordinator."""
        return self._host

    def reset_energy(self):
        """Send the reset energy command to the device."""
        _LOGGER.info(f"Resetting energy for device {self._host}...")
        self._hub.reset_energy()
        # Immediately update local data to provide instant feedback.
        if self.data:
            self.data[UnitOfEnergy.KILO_WATT_HOUR] = 0.0
            self.async_set_updated_data(self.data)

    async def _async_update_data(self):
        """Asynchronously fetch the latest data from the Modbus device."""
        try:
            # Use `hass.async_add_executor_job` to run synchronous Modbus I/O operations.
            data_update = await self._hass.async_add_executor_job(self._hub.info_gather)
            
            if data_update:
                _LOGGER.debug(f"Got data from {self._host}: {data_update}")
                return data_update
            
            _LOGGER.warning(f"Failed to get data from {self._host}, returning empty data.")
            return self.data # Return old data to prevent entity from becoming unavailable.
        except Exception as err:
            _LOGGER.error(f"Error updating data for device {self._host}: {err}")
            return self.data # Or return old data.
