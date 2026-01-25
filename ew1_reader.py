#!/usr/bin/env python3
"""
ERAB EW-1 Modbus TCP Reader

Reads data from an ERAB EW-1 DUC via Modbus TCP.
The EW-1 supports Modbus TCP as both master and slave.

Usage:
    from ew1_reader import EW1Reader

    reader = EW1Reader("192.168.1.100")
    data = reader.read_all_registers()
"""

from dataclasses import dataclass
from typing import Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException


@dataclass
class RegisterDefinition:
    """Definition of a Modbus register to read."""
    address: int
    name: str
    description: str
    register_type: str = "holding"  # "holding", "input", "coil", "discrete"
    count: int = 1  # Number of registers to read
    data_type: str = "uint16"  # "uint16", "int16", "uint32", "int32", "float32"
    scale: float = 1.0  # Multiplier for the raw value
    unit: str = ""  # Unit of measurement (e.g., "°C", "kWh")


# Default register configuration for EW-1
# NOTE: These are EXAMPLE registers - you'll need to update these based on
# your EW-1's actual configuration. Check the EW-1 web interface or contact
# ERAB for the specific register map for your installation.
DEFAULT_REGISTERS = [
    # Common Modbus holding registers to try (adjust based on your setup)
    RegisterDefinition(0, "temp_1", "Temperature Sensor 1", "input", 1, "int16", 0.1, "°C"),
    RegisterDefinition(1, "temp_2", "Temperature Sensor 2", "input", 1, "int16", 0.1, "°C"),
    RegisterDefinition(2, "temp_3", "Temperature Sensor 3", "input", 1, "int16", 0.1, "°C"),
    RegisterDefinition(3, "temp_4", "Temperature Sensor 4", "input", 1, "int16", 0.1, "°C"),
    RegisterDefinition(4, "temp_5", "Temperature Sensor 5", "input", 1, "int16", 0.1, "°C"),
    RegisterDefinition(5, "temp_6", "Temperature Sensor 6", "input", 1, "int16", 0.1, "°C"),
]


class EW1Reader:
    """Reader for ERAB EW-1 DUC via Modbus TCP."""

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        registers: Optional[list[RegisterDefinition]] = None,
        timeout: float = 5.0
    ):
        """
        Initialize the EW-1 reader.

        Args:
            host: IP address of the EW-1
            port: Modbus TCP port (default 502)
            unit_id: Modbus unit/slave ID (default 1)
            registers: List of register definitions to read
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.registers = registers or DEFAULT_REGISTERS
        self.timeout = timeout
        self._client: Optional[ModbusTcpClient] = None

    def connect(self) -> bool:
        """Connect to the EW-1."""
        self._client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout
        )
        return self._client.connect()

    def disconnect(self):
        """Disconnect from the EW-1."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise ConnectionError(f"Failed to connect to EW-1 at {self.host}:{self.port}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False

    def _read_register(self, reg: RegisterDefinition) -> Optional[float]:
        """
        Read a single register definition and return the scaled value.

        Args:
            reg: Register definition to read

        Returns:
            Scaled value or None if read failed
        """
        if not self._client:
            raise RuntimeError("Not connected to EW-1")

        try:
            # Read based on register type
            if reg.register_type == "holding":
                result = self._client.read_holding_registers(
                    reg.address, reg.count, slave=self.unit_id
                )
            elif reg.register_type == "input":
                result = self._client.read_input_registers(
                    reg.address, reg.count, slave=self.unit_id
                )
            elif reg.register_type == "coil":
                result = self._client.read_coils(
                    reg.address, reg.count, slave=self.unit_id
                )
            elif reg.register_type == "discrete":
                result = self._client.read_discrete_inputs(
                    reg.address, reg.count, slave=self.unit_id
                )
            else:
                print(f"Unknown register type: {reg.register_type}")
                return None

            if result.isError():
                return None

            # Convert raw value based on data type
            raw_value = self._convert_raw_value(result.registers, reg.data_type)

            # Apply scale
            return raw_value * reg.scale

        except ModbusException as e:
            print(f"Modbus error reading {reg.name}: {e}")
            return None
        except Exception as e:
            print(f"Error reading {reg.name}: {e}")
            return None

    def _convert_raw_value(self, registers: list[int], data_type: str) -> float:
        """Convert raw register values to the appropriate data type."""
        if data_type == "uint16":
            return float(registers[0])
        elif data_type == "int16":
            # Convert unsigned to signed 16-bit
            val = registers[0]
            if val >= 0x8000:
                val -= 0x10000
            return float(val)
        elif data_type == "uint32":
            # Big-endian: high word first
            return float((registers[0] << 16) | registers[1])
        elif data_type == "int32":
            val = (registers[0] << 16) | registers[1]
            if val >= 0x80000000:
                val -= 0x100000000
            return float(val)
        elif data_type == "float32":
            import struct
            # Big-endian float
            raw_bytes = struct.pack('>HH', registers[0], registers[1])
            return struct.unpack('>f', raw_bytes)[0]
        else:
            return float(registers[0])

    def read_register(self, name: str) -> Optional[float]:
        """
        Read a specific register by name.

        Args:
            name: Name of the register to read

        Returns:
            Scaled value or None if not found/failed
        """
        for reg in self.registers:
            if reg.name == name:
                return self._read_register(reg)
        return None

    def read_all_registers(self) -> dict[str, Optional[float]]:
        """
        Read all configured registers.

        Returns:
            Dictionary mapping register names to values
        """
        results = {}
        for reg in self.registers:
            value = self._read_register(reg)
            results[reg.name] = value
        return results

    def get_register_info(self) -> list[dict]:
        """Get information about all configured registers."""
        return [
            {
                "name": reg.name,
                "description": reg.description,
                "address": reg.address,
                "type": reg.register_type,
                "unit": reg.unit
            }
            for reg in self.registers
        ]


def load_registers_from_config(config_path: str) -> list[RegisterDefinition]:
    """
    Load register definitions from a JSON config file.

    Args:
        config_path: Path to the JSON configuration file

    Returns:
        List of RegisterDefinition objects
    """
    import json

    with open(config_path, 'r') as f:
        config = json.load(f)

    registers = []
    for reg_config in config.get("registers", []):
        registers.append(RegisterDefinition(
            address=reg_config["address"],
            name=reg_config["name"],
            description=reg_config.get("description", ""),
            register_type=reg_config.get("register_type", "holding"),
            count=reg_config.get("count", 1),
            data_type=reg_config.get("data_type", "uint16"),
            scale=reg_config.get("scale", 1.0),
            unit=reg_config.get("unit", "")
        ))

    return registers


if __name__ == "__main__":
    import sys

    # Example usage - update with your EW-1's IP address
    if len(sys.argv) < 2:
        print("Usage: python ew1_reader.py <EW1_IP_ADDRESS>")
        print("Example: python ew1_reader.py 192.168.1.100")
        sys.exit(1)

    host = sys.argv[1]
    print(f"Connecting to EW-1 at {host}...")

    try:
        with EW1Reader(host) as reader:
            print("Connected! Reading registers...")
            data = reader.read_all_registers()

            print("\nRegister Values:")
            print("-" * 50)
            for name, value in data.items():
                reg = next((r for r in reader.registers if r.name == name), None)
                if value is not None:
                    unit = reg.unit if reg else ""
                    print(f"  {name}: {value:.2f} {unit}")
                else:
                    print(f"  {name}: <read failed>")
    except ConnectionError as e:
        print(f"Connection failed: {e}")
        sys.exit(1)
