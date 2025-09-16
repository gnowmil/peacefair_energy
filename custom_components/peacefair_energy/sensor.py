"""Sensor platform for Peacefair Energy Monitor."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, POWER_FACTOR, VERSION

# Defines all sensors that will be created for each device.
# This makes the setup independent of the first data poll.
SENSOR_TYPES = {
    SensorDeviceClass.VOLTAGE: {
        "name": "Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:flash",
    },
    SensorDeviceClass.CURRENT: {
        "name": "Current",
        "unit": UnitOfElectricCurrent.AMPERE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:current-ac",
    },
    SensorDeviceClass.POWER: {
        "name": "Power",
        "unit": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:power-plug",
    },
    SensorDeviceClass.ENERGY: {
        "name": "Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:meter-electric",
    },
    SensorDeviceClass.FREQUENCY: {
        "name": "Frequency",
        "unit": UnitOfFrequency.HERTZ,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sine-wave",
    },
    # Use the POWER_FACTOR constant defined in const.py
    POWER_FACTOR: {
        "name": "Power Factor",
        "unit": None,  # Power factor is dimensionless
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:angle-acute",
        "device_class": SensorDeviceClass.POWER_FACTOR,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    ident = coordinator.host.replace(".", "_")
    sensors = []

    # Create sensors based on the predefined SENSOR_TYPES dictionary.
    # This ensures that sensors are created even if the first data poll fails.
    for sensor_type in SENSOR_TYPES:
        sensors.append(PeacefairSensor(coordinator, sensor_type, ident))

    async_add_entities(sensors)


class PeacefairSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Peacefair sensor."""

    def __init__(self, coordinator, sensor_type, ident):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._ident = ident
        sensor_info = SENSOR_TYPES[sensor_type]

        self._attr_name = f"{ident} {sensor_info['name']}"
        self._attr_unique_id = f"{DOMAIN}_{self._ident}_{self._sensor_type}"
        self._attr_native_unit_of_measurement = sensor_info.get("unit")
        self._attr_state_class = sensor_info.get("state_class")
        self._attr_icon = sensor_info.get("icon")
        # Handle device class separately for power factor, which doesn't have a unit
        self._attr_device_class = sensor_info.get("device_class", self._sensor_type)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._ident)},
            "name": f"Peacefair Energy Monitor {self._ident}",
            "manufacturer": "Peacefair",
            "model": "PZEM-004T",
            "sw_version": VERSION,
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # The state is taken from the coordinator's data.
        # If data is not available for this sensor, it will be None,
        # which Home Assistant correctly interprets as 'unavailable'.
        if self.coordinator.data:
            return self.coordinator.data.get(self._sensor_type)
        return None

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and has data."""
        # The sensor is available only if the coordinator has successfully fetched data.
        return super().available and self.coordinator.data is not None
