from pymodbus.client import ModbusTcpClient, ModbusUdpClient
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ModbusPDU
from homeassistant.components.sensor import SensorDeviceClass


class ModbusResetEnergyRequest(ModbusPDU):
    """A custom Modbus request for function code 0x42 (Reset Energy)."""

    _rtu_frame_size = 4
    function_code = 0x42

    def __init__(self, **kwargs):
        """Initialize the request."""
        super().__init__(**kwargs)

    def encode(self):
        """Encode the request payload."""
        return b""

    def get_response_pdu_size(self):
        """Return the expected response size."""
        return 4

    def __str__(self):
        """Return a string representation of the request."""
        return "ModbusResetEnergyRequest"


class ModbusHub:
    """Modbus Hub for Peacefair meters."""

    def __init__(self, protocol: str, host: str, port: int, slave: int):
        """Initialize the Modbus hub."""
        self._device_id = slave
        self._client = None
        if protocol == "rtuovertcp":
            self._client = ModbusTcpClient(
                host=host,
                port=port,
                framer="rtu",
                timeout=5,
                retry_on_empty=True,
                retry_on_invalid=False,
            )
        elif protocol == "rtuoverudp":
            self._client = ModbusUdpClient(
                host=host,
                port=port,
                framer="rtu",
                timeout=5,
            )

    def read_input_registers(self, address: int, count: int):
        """Read input registers from the device."""
        kwargs = {"device_id": self._device_id} if self._device_id is not None else {}
        return self._client.read_input_registers(address, count=count, **kwargs)

    def reset_energy(self):
        """Send the reset energy command."""
        kwargs = {"device_id": self._device_id} if self._device_id is not None else {}
        request = ModbusResetEnergyRequest(**kwargs)
        self._client.execute(request)

    def info_gather(self) -> dict:
        data = {}
        try:
            result = self.read_input_registers(0, 9)

            if (
                not isinstance(result, ModbusIOException)
                and not result.isError()
                and result.registers
                and len(result.registers) == 9
            ):
                # Only populate data if the read was successful and valid
                data[SensorDeviceClass.VOLTAGE] = result.registers[0] / 10
                data[SensorDeviceClass.CURRENT] = (
                    (result.registers[2] << 16) + result.registers[1]
                ) / 1000
                data[SensorDeviceClass.POWER] = (
                    (result.registers[4] << 16) + result.registers[3]
                ) / 10
                data[SensorDeviceClass.ENERGY] = (
                    (result.registers[6] << 16) + result.registers[5]
                ) / 1000
                data[SensorDeviceClass.FREQUENCY] = result.registers[7] / 10
                data[SensorDeviceClass.POWER_FACTOR] = result.registers[8] / 100

        except Exception:
            # Errors are intentionally ignored after removing logging.
            pass

        return data

