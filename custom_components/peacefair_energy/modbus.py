"""
Modbus communication hub for Peacefair Energy Monitor.

This module handles the low-level communication with the Peacefair device
using the pymodbus library.
"""
import logging

from homeassistant.const import (
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
)
from .const import POWER_FACTOR
from pymodbus.client import ModbusTcpClient, ModbusUdpClient
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ModbusRequest
from pymodbus.transaction import ModbusRtuFramer

_LOGGER = logging.getLogger(__name__)


class ModbusResetEnergyRequest(ModbusRequest):
    """
    A custom Modbus request to reset the energy register on the device.
    Function code 0x42 is a non-standard, device-specific command.
    """

    _rtu_frame_size = 4
    function_code = 0x42

    def __init__(self, **kwargs):
        """Initialize the request."""
        super().__init__(**kwargs)

    def encode(self):
        """Return an empty payload for this command."""
        return b""

    def get_response_pdu_size(self):
        """Return the expected response size."""
        return 4

    def __str__(self):
        """Return a string representation of the request."""
        return "ModbusResetEnergyRequest"


class ModbusHub:
    """Manages the connection and data exchange with a Modbus device."""

    def __init__(self, protocol: str, host: str, port: int, slave: int):
        """Initialize the Modbus client."""
        self._slave = slave
        self._client = None
        common_args = {
            "host": host,
            "port": port,
            "framer": ModbusRtuFramer,
            "timeout": 2,
        }

        # NOTE: Using threading.Lock() here is dangerous within Home Assistant's
        # async environment as it can lead to deadlocks. Pymodbus synchronous
        # clients are not inherently thread-safe, but since Home Assistant's
        # `async_add_executor_job` runs each call in a separate thread,
        # we remove the lock to prevent deadlocks. The caller is responsible
        # for ensuring thread safety if needed, which HA's architecture does.

        if protocol == "rtuovertcp":
            self._client = ModbusTcpClient(**common_args, retry_on_empty=True)
        elif protocol == "rtuoverudp":
            self._client = ModbusUdpClient(**common_args, retry_on_empty=False)

    def _read_input_registers(self, address: int, count: int):
        """Read from the device's input registers."""
        # The pymodbus client handles connect/close on each call automatically.
        kwargs = {"slave": self._slave}
        return self._client.read_input_registers(address, count, **kwargs)

    def reset_energy(self) -> None:
        """Execute the custom reset energy command."""
        kwargs = {"slave": self._slave}
        request = ModbusResetEnergyRequest(**kwargs)
        self._client.execute(request)

    def info_gather(self) -> dict:
        """Read all sensor data from the device and parse it."""
        data = {}
        try:
            # Read 9 input registers starting from address 0.
            result = self._read_input_registers(0, 9)

            # Check for a valid response.
            if result and not result.isError() and hasattr(result, "registers") and len(result.registers) == 9:
                # Parse the register data according to the device's protocol.
                data[UnitOfElectricPotential.VOLT] = result.registers[0] / 10
                data[UnitOfElectricCurrent.AMPERE] = ((result.registers[2] << 16) + result.registers[1]) / 1000
                data[UnitOfPower.WATT] = ((result.registers[4] << 16) + result.registers[3]) / 10
                data[UnitOfEnergy.KILO_WATT_HOUR] = ((result.registers[6] << 16) + result.registers[5]) / 1000
                data[UnitOfFrequency.HERTZ] = result.registers[7] / 10
                data[POWER_FACTOR] = result.registers[8] / 100
            elif isinstance(result, ModbusIOException):
                _LOGGER.debug("Modbus I/O exception while gathering data: %s", result)
            else:
                _LOGGER.debug("Received an invalid or error response: %s", result)

        except Exception as e:
            _LOGGER.error("An unexpected error occurred during data gathering: %s", e)
        return data

