"""Tests for ew1_reader module."""

import json
import struct
import pytest
from unittest.mock import Mock, patch, MagicMock

from ew1_reader import (
    EW1Reader,
    RegisterDefinition,
    load_registers_from_config,
    DEFAULT_REGISTERS,
)


class TestRegisterDefinition:
    """Tests for RegisterDefinition dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        reg = RegisterDefinition(address=10, name="test", description="Test register")

        assert reg.address == 10
        assert reg.name == "test"
        assert reg.description == "Test register"
        assert reg.register_type == "holding"
        assert reg.count == 1
        assert reg.data_type == "uint16"
        assert reg.scale == 1.0
        assert reg.unit == ""

    def test_custom_values(self):
        """Test that custom values are set correctly."""
        reg = RegisterDefinition(
            address=5,
            name="temp",
            description="Temperature",
            register_type="input",
            count=2,
            data_type="float32",
            scale=0.1,
            unit="°C"
        )

        assert reg.address == 5
        assert reg.register_type == "input"
        assert reg.count == 2
        assert reg.data_type == "float32"
        assert reg.scale == 0.1
        assert reg.unit == "°C"


class TestEW1ReaderInit:
    """Tests for EW1Reader initialization."""

    def test_default_initialization(self):
        """Test initialization with default values."""
        reader = EW1Reader("192.168.1.100")

        assert reader.host == "192.168.1.100"
        assert reader.port == 502
        assert reader.unit_id == 1
        assert reader.timeout == 5.0
        assert reader.registers == DEFAULT_REGISTERS
        assert reader._client is None

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        custom_registers = [
            RegisterDefinition(0, "reg1", "Register 1"),
            RegisterDefinition(1, "reg2", "Register 2"),
        ]
        reader = EW1Reader(
            host="10.0.0.50",
            port=5020,
            unit_id=5,
            registers=custom_registers,
            timeout=10.0
        )

        assert reader.host == "10.0.0.50"
        assert reader.port == 5020
        assert reader.unit_id == 5
        assert reader.timeout == 10.0
        assert reader.registers == custom_registers


class TestEW1ReaderConnection:
    """Tests for EW1Reader connection handling."""

    @patch('ew1_reader.ModbusTcpClient')
    def test_connect_success(self, mock_client_class):
        """Test successful connection."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        reader = EW1Reader("192.168.1.100")
        result = reader.connect()

        assert result is True
        mock_client_class.assert_called_once_with(
            host="192.168.1.100",
            port=502,
            timeout=5.0
        )
        mock_client.connect.assert_called_once()

    @patch('ew1_reader.ModbusTcpClient')
    def test_connect_failure(self, mock_client_class):
        """Test failed connection."""
        mock_client = Mock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        reader = EW1Reader("192.168.1.100")
        result = reader.connect()

        assert result is False

    @patch('ew1_reader.ModbusTcpClient')
    def test_disconnect(self, mock_client_class):
        """Test disconnection."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        reader = EW1Reader("192.168.1.100")
        reader.connect()
        reader.disconnect()

        mock_client.close.assert_called_once()
        assert reader._client is None

    def test_disconnect_when_not_connected(self):
        """Test disconnect when not connected does not raise."""
        reader = EW1Reader("192.168.1.100")
        reader.disconnect()  # Should not raise

    @patch('ew1_reader.ModbusTcpClient')
    def test_context_manager_success(self, mock_client_class):
        """Test context manager with successful connection."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client_class.return_value = mock_client

        with EW1Reader("192.168.1.100") as reader:
            assert reader._client is not None

        mock_client.close.assert_called_once()

    @patch('ew1_reader.ModbusTcpClient')
    def test_context_manager_connection_failure(self, mock_client_class):
        """Test context manager raises on connection failure."""
        mock_client = Mock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(ConnectionError) as exc_info:
            with EW1Reader("192.168.1.100"):
                pass

        assert "Failed to connect" in str(exc_info.value)


class TestEW1ReaderConvertRawValue:
    """Tests for _convert_raw_value method."""

    def test_uint16(self):
        """Test uint16 conversion."""
        reader = EW1Reader("192.168.1.100")
        result = reader._convert_raw_value([1234], "uint16")
        assert result == 1234.0

    def test_uint16_max(self):
        """Test uint16 max value."""
        reader = EW1Reader("192.168.1.100")
        result = reader._convert_raw_value([65535], "uint16")
        assert result == 65535.0

    def test_int16_positive(self):
        """Test int16 positive value."""
        reader = EW1Reader("192.168.1.100")
        result = reader._convert_raw_value([1234], "int16")
        assert result == 1234.0

    def test_int16_negative(self):
        """Test int16 negative value (two's complement)."""
        reader = EW1Reader("192.168.1.100")
        # -10 in two's complement 16-bit = 0xFFF6 = 65526
        result = reader._convert_raw_value([65526], "int16")
        assert result == -10.0

    def test_int16_min(self):
        """Test int16 minimum value."""
        reader = EW1Reader("192.168.1.100")
        # -32768 in two's complement = 0x8000
        result = reader._convert_raw_value([0x8000], "int16")
        assert result == -32768.0

    def test_uint32(self):
        """Test uint32 conversion (big-endian)."""
        reader = EW1Reader("192.168.1.100")
        # 0x00010002 = 65538
        result = reader._convert_raw_value([0x0001, 0x0002], "uint32")
        assert result == 65538.0

    def test_int32_positive(self):
        """Test int32 positive value."""
        reader = EW1Reader("192.168.1.100")
        result = reader._convert_raw_value([0x0000, 0x1234], "int32")
        assert result == 0x1234

    def test_int32_negative(self):
        """Test int32 negative value."""
        reader = EW1Reader("192.168.1.100")
        # -1 in two's complement 32-bit = 0xFFFFFFFF
        result = reader._convert_raw_value([0xFFFF, 0xFFFF], "int32")
        assert result == -1.0

    def test_float32(self):
        """Test float32 conversion."""
        reader = EW1Reader("192.168.1.100")
        # Pack 3.14 as big-endian float and split into two 16-bit registers
        packed = struct.pack('>f', 3.14)
        reg0, reg1 = struct.unpack('>HH', packed)

        result = reader._convert_raw_value([reg0, reg1], "float32")
        assert abs(result - 3.14) < 0.001

    def test_unknown_type_defaults_to_first_register(self):
        """Test unknown data type returns first register as float."""
        reader = EW1Reader("192.168.1.100")
        result = reader._convert_raw_value([42], "unknown_type")
        assert result == 42.0


class TestEW1ReaderReadRegister:
    """Tests for reading registers."""

    @patch('ew1_reader.ModbusTcpClient')
    def test_read_holding_register(self, mock_client_class):
        """Test reading a holding register."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [250]
        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        registers = [
            RegisterDefinition(10, "temp", "Temperature", "holding", 1, "int16", 0.1, "°C")
        ]
        reader = EW1Reader("192.168.1.100", registers=registers)
        reader.connect()

        value = reader.read_register("temp")

        assert value == 25.0  # 250 * 0.1
        mock_client.read_holding_registers.assert_called_once_with(10, 1, slave=1)

    @patch('ew1_reader.ModbusTcpClient')
    def test_read_input_register(self, mock_client_class):
        """Test reading an input register."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [500]
        mock_client.read_input_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        registers = [
            RegisterDefinition(5, "sensor", "Sensor", "input", 1, "uint16", 1.0)
        ]
        reader = EW1Reader("192.168.1.100", registers=registers)
        reader.connect()

        value = reader.read_register("sensor")

        assert value == 500.0
        mock_client.read_input_registers.assert_called_once_with(5, 1, slave=1)

    @patch('ew1_reader.ModbusTcpClient')
    def test_read_coil_register(self, mock_client_class):
        """Test reading a coil register."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [1]
        mock_client.read_coils.return_value = mock_result
        mock_client_class.return_value = mock_client

        registers = [
            RegisterDefinition(0, "relay", "Relay", "coil", 1, "uint16", 1.0)
        ]
        reader = EW1Reader("192.168.1.100", registers=registers)
        reader.connect()

        value = reader.read_register("relay")

        mock_client.read_coils.assert_called_once_with(0, 1, slave=1)

    @patch('ew1_reader.ModbusTcpClient')
    def test_read_register_error(self, mock_client_class):
        """Test reading a register that returns an error."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_result = Mock()
        mock_result.isError.return_value = True
        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        registers = [
            RegisterDefinition(10, "temp", "Temperature", "holding")
        ]
        reader = EW1Reader("192.168.1.100", registers=registers)
        reader.connect()

        value = reader.read_register("temp")

        assert value is None

    def test_read_register_not_found(self):
        """Test reading a register that doesn't exist in config."""
        reader = EW1Reader("192.168.1.100", registers=[])
        value = reader.read_register("nonexistent")
        assert value is None

    def test_read_register_not_connected(self):
        """Test reading without being connected raises error."""
        reader = EW1Reader("192.168.1.100")

        with pytest.raises(RuntimeError) as exc_info:
            reader.read_register("temp_1")

        assert "Not connected" in str(exc_info.value)

    @patch('ew1_reader.ModbusTcpClient')
    def test_read_all_registers(self, mock_client_class):
        """Test reading all registers."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        def mock_read_input(addr, count, slave):
            result = Mock()
            result.isError.return_value = False
            result.registers = [200 + addr * 10]  # Different value per register
            return result

        mock_client.read_input_registers.side_effect = mock_read_input
        mock_client_class.return_value = mock_client

        registers = [
            RegisterDefinition(0, "temp1", "Temp 1", "input", 1, "int16", 0.1),
            RegisterDefinition(1, "temp2", "Temp 2", "input", 1, "int16", 0.1),
        ]
        reader = EW1Reader("192.168.1.100", registers=registers)
        reader.connect()

        data = reader.read_all_registers()

        assert data["temp1"] == 20.0  # 200 * 0.1
        assert data["temp2"] == 21.0  # 210 * 0.1


class TestEW1ReaderGetRegisterInfo:
    """Tests for get_register_info method."""

    def test_get_register_info(self):
        """Test getting register information."""
        registers = [
            RegisterDefinition(0, "temp", "Temperature", "input", 1, "int16", 0.1, "°C"),
            RegisterDefinition(10, "power", "Power", "holding", 2, "uint32", 1.0, "W"),
        ]
        reader = EW1Reader("192.168.1.100", registers=registers)

        info = reader.get_register_info()

        assert len(info) == 2
        assert info[0] == {
            "name": "temp",
            "description": "Temperature",
            "address": 0,
            "type": "input",
            "unit": "°C"
        }
        assert info[1] == {
            "name": "power",
            "description": "Power",
            "address": 10,
            "type": "holding",
            "unit": "W"
        }


class TestLoadRegistersFromConfig:
    """Tests for load_registers_from_config function."""

    def test_load_basic_config(self, tmp_path):
        """Test loading a basic configuration file."""
        config = {
            "registers": [
                {
                    "address": 0,
                    "name": "temp",
                    "description": "Temperature",
                    "register_type": "input",
                    "data_type": "int16",
                    "scale": 0.1,
                    "unit": "°C"
                }
            ]
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        registers = load_registers_from_config(str(config_file))

        assert len(registers) == 1
        assert registers[0].address == 0
        assert registers[0].name == "temp"
        assert registers[0].description == "Temperature"
        assert registers[0].register_type == "input"
        assert registers[0].data_type == "int16"
        assert registers[0].scale == 0.1
        assert registers[0].unit == "°C"

    def test_load_config_with_defaults(self, tmp_path):
        """Test loading config that uses default values."""
        config = {
            "registers": [
                {
                    "address": 5,
                    "name": "sensor"
                }
            ]
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        registers = load_registers_from_config(str(config_file))

        assert len(registers) == 1
        assert registers[0].address == 5
        assert registers[0].name == "sensor"
        assert registers[0].description == ""
        assert registers[0].register_type == "holding"
        assert registers[0].count == 1
        assert registers[0].data_type == "uint16"
        assert registers[0].scale == 1.0
        assert registers[0].unit == ""

    def test_load_empty_config(self, tmp_path):
        """Test loading config with no registers."""
        config = {"registers": []}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        registers = load_registers_from_config(str(config_file))

        assert registers == []

    def test_load_multiple_registers(self, tmp_path):
        """Test loading multiple registers."""
        config = {
            "registers": [
                {"address": 0, "name": "reg1"},
                {"address": 1, "name": "reg2"},
                {"address": 2, "name": "reg3"},
            ]
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        registers = load_registers_from_config(str(config_file))

        assert len(registers) == 3
        assert [r.name for r in registers] == ["reg1", "reg2", "reg3"]
