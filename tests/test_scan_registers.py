"""Tests for scan_registers module."""

import pytest
from unittest.mock import Mock, patch

from scan_registers import scan_registers, interpret_value


class TestScanRegisters:
    """Tests for scan_registers function."""

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_holding_registers_success(self, mock_client_class):
        """Test successful scan of holding registers."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        def mock_read_holding(addr, count, slave):
            result = Mock()
            if addr in [0, 5, 10]:  # Only these addresses respond
                result.isError.return_value = False
                result.registers = [100 + addr]
            else:
                result.isError.return_value = True
            return result

        mock_client.read_holding_registers.side_effect = mock_read_holding
        mock_client_class.return_value = mock_client

        found = scan_registers(
            host="192.168.1.100",
            start_address=0,
            end_address=15,
            register_type="holding"
        )

        assert len(found) == 3
        assert (0, 100) in found
        assert (5, 105) in found
        assert (10, 110) in found
        mock_client.close.assert_called_once()

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_input_registers(self, mock_client_class):
        """Test scanning input registers."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [250]
        mock_client.read_input_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        found = scan_registers(
            host="192.168.1.100",
            start_address=0,
            end_address=3,
            register_type="input"
        )

        assert len(found) == 3
        mock_client.read_input_registers.assert_called()

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_coil_registers(self, mock_client_class):
        """Test scanning coil registers."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.bits = [True]
        mock_client.read_coils.return_value = mock_result
        mock_client_class.return_value = mock_client

        found = scan_registers(
            host="192.168.1.100",
            start_address=0,
            end_address=2,
            register_type="coil"
        )

        assert len(found) == 2
        assert found[0][1] is True
        mock_client.read_coils.assert_called()

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_discrete_registers(self, mock_client_class):
        """Test scanning discrete input registers."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.bits = [False]
        mock_client.read_discrete_inputs.return_value = mock_result
        mock_client_class.return_value = mock_client

        found = scan_registers(
            host="192.168.1.100",
            start_address=0,
            end_address=2,
            register_type="discrete"
        )

        assert len(found) == 2
        mock_client.read_discrete_inputs.assert_called()

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_connection_failure(self, mock_client_class):
        """Test scan raises ConnectionError on connection failure."""
        mock_client = Mock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(ConnectionError) as exc_info:
            scan_registers(host="192.168.1.100")

        assert "Failed to connect" in str(exc_info.value)

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_no_registers_found(self, mock_client_class):
        """Test scan returns empty list when no registers respond."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        mock_result = Mock()
        mock_result.isError.return_value = True
        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        found = scan_registers(
            host="192.168.1.100",
            start_address=0,
            end_address=10
        )

        assert found == []

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_handles_exceptions(self, mock_client_class):
        """Test scan handles exceptions gracefully."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        def mock_read_with_exception(addr, count, slave):
            if addr == 5:
                raise Exception("Random error")
            result = Mock()
            result.isError.return_value = False
            result.registers = [addr]
            return result

        mock_client.read_holding_registers.side_effect = mock_read_with_exception
        mock_client_class.return_value = mock_client

        found = scan_registers(
            host="192.168.1.100",
            start_address=0,
            end_address=10
        )

        # Should have 9 results (0-4, 6-9), skipping 5 which raised exception
        assert len(found) == 9
        assert 5 not in [addr for addr, _ in found]

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_custom_port_and_unit(self, mock_client_class):
        """Test scan with custom port and unit ID."""
        mock_client = Mock()
        mock_client.connect.return_value = True

        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [100]
        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        scan_registers(
            host="192.168.1.100",
            port=5020,
            unit_id=5,
            start_address=0,
            end_address=1
        )

        mock_client_class.assert_called_once_with(
            host="192.168.1.100",
            port=5020,
            timeout=5.0
        )
        mock_client.read_holding_registers.assert_called_with(0, 1, slave=5)

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_closes_client_on_success(self, mock_client_class):
        """Test that client is closed after successful scan."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [0]
        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        scan_registers(host="192.168.1.100", start_address=0, end_address=1)

        mock_client.close.assert_called_once()

    @patch('scan_registers.ModbusTcpClient')
    def test_scan_closes_client_on_exception(self, mock_client_class):
        """Test that client is closed even when exception occurs."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.read_holding_registers.side_effect = Exception("Error")
        mock_client_class.return_value = mock_client

        # Should not raise - exceptions during scan are caught
        scan_registers(host="192.168.1.100", start_address=0, end_address=1)

        mock_client.close.assert_called_once()


class TestInterpretValue:
    """Tests for interpret_value function."""

    def test_interpret_small_positive(self):
        """Test interpreting a small positive value."""
        result = interpret_value(250, 0)

        assert "uint16: 250" in result
        assert "temp(÷10): 25.0°C" in result
        assert "pct(÷10): 25.0%" in result

    def test_interpret_negative_as_int16(self):
        """Test interpreting a value that's negative in int16."""
        # 65526 = -10 in int16
        result = interpret_value(65526, 0)

        assert "uint16: 65526" in result
        assert "int16: -10" in result

    def test_interpret_zero(self):
        """Test interpreting zero."""
        result = interpret_value(0, 0)

        assert "uint16: 0" in result
        assert "temp(÷10): 0.0°C" in result
        assert "pct(÷10): 0.0%" in result

    def test_interpret_large_value_no_temp(self):
        """Test that large values don't show temperature interpretation."""
        # 2000 / 10 = 200°C which is outside -50 to 150 range
        result = interpret_value(2000, 0)

        assert "uint16: 2000" in result
        assert "temp(÷10)" not in result

    def test_interpret_large_value_no_percentage(self):
        """Test that values > 1000 don't show percentage interpretation."""
        result = interpret_value(1500, 0)

        assert "uint16: 1500" in result
        assert "pct(÷10)" not in result

    def test_interpret_max_uint16(self):
        """Test interpreting maximum uint16 value."""
        result = interpret_value(65535, 0)

        assert "uint16: 65535" in result
        assert "int16: -1" in result

    def test_interpret_boundary_temperature(self):
        """Test temperature interpretation at boundaries."""
        # -500 / 10 = -50°C (just at boundary, should not be included)
        result = interpret_value(65036, 0)  # -500 as uint16
        # -50 is not < -50, so it should not show temp

        # 1499 / 10 = 149.9°C (just inside boundary)
        result2 = interpret_value(1499, 0)
        assert "temp(÷10): 149.9°C" in result2

    def test_interpret_boundary_percentage(self):
        """Test percentage interpretation at boundaries."""
        # 1000 / 10 = 100% (at boundary, should be included)
        result = interpret_value(1000, 0)
        assert "pct(÷10): 100.0%" in result

        # 1001 should not have percentage
        result2 = interpret_value(1001, 0)
        assert "pct(÷10)" not in result2
