"""Tests for logger module."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from logger import (
    load_config,
    create_reader_from_config,
    log_once,
    signal_handler,
)
from ew1_reader import RegisterDefinition


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file."""
        config = {
            "ew1": {"host": "192.168.1.100", "port": 502},
            "registers": [
                {"address": 0, "name": "temp", "description": "Temperature"}
            ]
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        result = load_config(str(config_file))

        assert result == config

    def test_load_config_file_not_found(self, tmp_path):
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            load_config(str(tmp_path / "nonexistent.json"))

    def test_load_invalid_json(self, tmp_path):
        """Test that JSONDecodeError is raised for invalid JSON."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text("not valid json {")

        with pytest.raises(json.JSONDecodeError):
            load_config(str(config_file))


class TestCreateReaderFromConfig:
    """Tests for create_reader_from_config function."""

    def test_create_reader_with_full_config(self):
        """Test creating reader with full configuration."""
        config = {
            "ew1": {
                "host": "10.0.0.50",
                "port": 5020,
                "unit_id": 5
            },
            "registers": [
                {
                    "address": 10,
                    "name": "sensor1",
                    "description": "Sensor 1",
                    "register_type": "input",
                    "count": 2,
                    "data_type": "float32",
                    "scale": 0.01,
                    "unit": "kW"
                }
            ]
        }

        reader = create_reader_from_config(config)

        assert reader.host == "10.0.0.50"
        assert reader.port == 5020
        assert reader.unit_id == 5
        assert len(reader.registers) == 1
        assert reader.registers[0].address == 10
        assert reader.registers[0].name == "sensor1"
        assert reader.registers[0].register_type == "input"
        assert reader.registers[0].data_type == "float32"
        assert reader.registers[0].scale == 0.01
        assert reader.registers[0].unit == "kW"

    def test_create_reader_with_defaults(self):
        """Test creating reader uses defaults for missing config."""
        config = {
            "registers": [
                {"address": 0, "name": "reg1"}
            ]
        }

        reader = create_reader_from_config(config)

        assert reader.host == "192.168.1.100"
        assert reader.port == 502
        assert reader.unit_id == 1
        assert reader.registers[0].register_type == "holding"
        assert reader.registers[0].data_type == "uint16"
        assert reader.registers[0].scale == 1.0

    def test_create_reader_empty_config(self):
        """Test creating reader with empty configuration uses defaults."""
        config = {}

        reader = create_reader_from_config(config)

        assert reader.host == "192.168.1.100"
        assert reader.port == 502
        # When no registers in config, EW1Reader falls back to DEFAULT_REGISTERS
        # because empty list is falsy (registers or DEFAULT_REGISTERS)
        from ew1_reader import DEFAULT_REGISTERS
        assert reader.registers == DEFAULT_REGISTERS

    def test_create_reader_multiple_registers(self):
        """Test creating reader with multiple registers."""
        config = {
            "registers": [
                {"address": 0, "name": "reg1"},
                {"address": 1, "name": "reg2"},
                {"address": 2, "name": "reg3"},
            ]
        }

        reader = create_reader_from_config(config)

        assert len(reader.registers) == 3
        assert [r.name for r in reader.registers] == ["reg1", "reg2", "reg3"]


class TestLogOnce:
    """Tests for log_once function."""

    def test_log_once_success(self):
        """Test successful logging cycle."""
        mock_reader = Mock()
        mock_reader.registers = [
            RegisterDefinition(0, "temp1", "Temp 1", "input", 1, "int16", 0.1, "°C"),
            RegisterDefinition(1, "temp2", "Temp 2", "input", 1, "int16", 0.1, "°C"),
        ]
        mock_reader.__enter__ = Mock(return_value=mock_reader)
        mock_reader.__exit__ = Mock(return_value=False)
        mock_reader.read_all_registers.return_value = {"temp1": 25.0, "temp2": 30.0}

        mock_writer = Mock()
        mock_writer.write_row.return_value = 5

        result = log_once(mock_reader, mock_writer, ["temp1", "temp2"])

        assert result is True
        mock_reader.read_all_registers.assert_called_once()
        mock_writer.write_row.assert_called_once_with(
            {"temp1": 25.0, "temp2": 30.0},
            columns=["temp1", "temp2"]
        )

    def test_log_once_with_failed_reads(self):
        """Test logging cycle with some failed register reads."""
        mock_reader = Mock()
        mock_reader.registers = [
            RegisterDefinition(0, "temp1", "Temp 1", "input", 1, "int16", 0.1, "°C"),
            RegisterDefinition(1, "temp2", "Temp 2", "input", 1, "int16", 0.1, "°C"),
        ]
        mock_reader.__enter__ = Mock(return_value=mock_reader)
        mock_reader.__exit__ = Mock(return_value=False)
        mock_reader.read_all_registers.return_value = {"temp1": 25.0, "temp2": None}

        mock_writer = Mock()
        mock_writer.write_row.return_value = 5

        result = log_once(mock_reader, mock_writer, ["temp1", "temp2"])

        assert result is True
        mock_writer.write_row.assert_called_once()

    def test_log_once_connection_error(self):
        """Test logging cycle with connection error."""
        mock_reader = Mock()
        mock_reader.registers = []
        mock_reader.__enter__ = Mock(side_effect=ConnectionError("Connection failed"))
        mock_reader.__exit__ = Mock(return_value=False)

        mock_writer = Mock()

        result = log_once(mock_reader, mock_writer, [])

        assert result is False
        mock_writer.write_row.assert_not_called()

    def test_log_once_general_exception(self):
        """Test logging cycle with general exception."""
        mock_reader = Mock()
        mock_reader.registers = []
        mock_reader.__enter__ = Mock(return_value=mock_reader)
        mock_reader.__exit__ = Mock(return_value=False)
        mock_reader.read_all_registers.side_effect = Exception("Something went wrong")

        mock_writer = Mock()

        result = log_once(mock_reader, mock_writer, [])

        assert result is False


class TestSignalHandler:
    """Tests for signal_handler function."""

    def test_signal_handler_sets_running_false(self):
        """Test that signal handler sets running flag to False."""
        import logger

        # Ensure running is True before test
        logger.running = True

        signal_handler(None, None)

        assert logger.running is False

        # Reset for other tests
        logger.running = True
