"""
Sensor platform for the Peacefair Energy Monitor integration.

This platform creates sensors for various measurements from the device.
"""
import logging
from datetime import datetime
from typing import final

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from .const import COORDINATOR, DOMAIN, POWER_FACTOR, VERSION # <--- 将 POWER_FACTOR 添加到这里
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import save_json
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, VERSION
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)

# Describes the primary sensors that will be created.
# The keys correspond to the keys in the data dictionary from ModbusHub.
PEACEFAIR_SENSORS = {
    UnitOfElectricPotential.VOLT: {
        "device_class": SensorDeviceClass.VOLTAGE,
        "name": "Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "state_class": "measurement",
    },
    UnitOfElectricCurrent.AMPERE: {
        "device_class": SensorDeviceClass.CURRENT,
        "name": "Current",
        "unit": UnitOfElectricCurrent.AMPERE,
        "state_class": "measurement",
    },
    UnitOfPower.WATT: {
        "device_class": SensorDeviceClass.POWER,
        "name": "Power",
        "unit": UnitOfPower.WATT,
        "state_class": "measurement",
    },
    UnitOfEnergy.KILO_WATT_HOUR: {
        "device_class": SensorDeviceClass.ENERGY,
        "name": "Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "state_class": "total_increasing",
    },
    POWER_FACTOR: {
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "name": "Power Factor",
        "unit": None,  # Power factor is a dimensionless ratio.
        "state_class": "measurement",
    },
    UnitOfFrequency.HERTZ: {
        "device_class": SensorDeviceClass.FREQUENCY,
        "name": "Frequency",
        "unit": UnitOfFrequency.HERTZ,
        "icon": "mdi:current-ac",
        "state_class": "measurement",
    },
}

ATTR_LAST_RESET: final = "last_reset"


async def async_setup_entry(
    hass: HomeAssistant, config_entry, async_add_entities: AddEntitiesCallback
):
    """Set up the sensor entities."""
    coordinator: ModbusHub = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    
    # Create all the defined sensors.
    sensors = [
        PeacefairSensor(coordinator, sensor_type)
        for sensor_type in coordinator.data
    ]
    async_add_entities(sensors)


class PeacefairSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Peacefair sensor."""

    def __init__(self, coordinator: ModbusHub, sensor_type: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._config = PEACEFAIR_SENSORS[self._sensor_type]
        self._host_id = coordinator.host.replace(".", "_")

        # Set entity attributes based on the sensor's config.
        self._attr_name = f"{self._config['name']}"
        self._attr_native_unit_of_measurement = self._config.get("unit")
        self._attr_device_class = self._config["device_class"]
        self._attr_state_class = self._config["state_class"]
        self._attr_icon = self._config.get("icon")
        
        self._attr_unique_id = f"{DOMAIN}_{self._host_id}_{self._sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._host_id)},
            "name": f"Peacefair Energy Monitor ({coordinator.host})",
            "manufacturer": "Peacefair",
            "model": "PZEM-004T",
            "sw_version": VERSION,
        }
        
        # Specific handling for the energy sensor's last_reset attribute.
        if self._attr_device_class == SensorDeviceClass.ENERGY:
            self._attr_last_reset = None # Will be updated on first reset.

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and self._sensor_type in self.coordinator.data:
            value = self.coordinator.data[self._sensor_type]
            # Round the value for display purposes.
            return round(value, 2)
        return STATE_UNKNOWN

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the energy sensor."""
        if self._attr_device_class == SensorDeviceClass.ENERGY and self._attr_last_reset:
            return {ATTR_LAST_RESET: self._attr_last_reset.isoformat()}
        return None
