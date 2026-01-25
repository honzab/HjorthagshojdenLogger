"""Tests for write_to_sheets module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from write_to_sheets import SheetsWriter, write_timestamp_to_sheets


class TestSheetsWriterInit:
    """Tests for SheetsWriter initialization."""

    def test_default_initialization(self):
        """Test initialization with default values."""
        writer = SheetsWriter()

        assert "docs.google.com/spreadsheets" in writer.spreadsheet_url
        assert writer.service_account_file == "hjorthagshojdenlogger-a98834ae5994.json"
        assert writer._client is None
        assert writer._spreadsheet is None

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        writer = SheetsWriter(
            spreadsheet_url="https://docs.google.com/spreadsheets/d/test123/edit",
            service_account_file="custom_credentials.json"
        )

        assert writer.spreadsheet_url == "https://docs.google.com/spreadsheets/d/test123/edit"
        assert writer.service_account_file == "custom_credentials.json"


class TestSheetsWriterConnect:
    """Tests for SheetsWriter connection."""

    @patch('write_to_sheets.gspread')
    @patch('write_to_sheets.ServiceAccountCredentials')
    @patch('write_to_sheets.Path')
    def test_connect_success(self, mock_path, mock_creds_class, mock_gspread):
        """Test successful connection."""
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = Mock(return_value="/path/to/creds.json")
        mock_path.return_value.parent = mock_path_instance

        mock_credentials = Mock()
        mock_creds_class.from_json_keyfile_name.return_value = mock_credentials

        mock_client = Mock()
        mock_spreadsheet = Mock()
        mock_client.open_by_url.return_value = mock_spreadsheet
        mock_gspread.authorize.return_value = mock_client

        writer = SheetsWriter()
        writer.connect()

        mock_creds_class.from_json_keyfile_name.assert_called_once()
        mock_gspread.authorize.assert_called_once_with(mock_credentials)
        mock_client.open_by_url.assert_called_once_with(writer.spreadsheet_url)
        assert writer._client == mock_client
        assert writer._spreadsheet == mock_spreadsheet

    @patch('write_to_sheets.gspread')
    @patch('write_to_sheets.ServiceAccountCredentials')
    @patch('write_to_sheets.Path')
    def test_ensure_connected_calls_connect(self, mock_path, mock_creds_class, mock_gspread):
        """Test that _ensure_connected calls connect when not connected."""
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = Mock(return_value="/path/to/creds.json")
        mock_path.return_value.parent = mock_path_instance

        mock_credentials = Mock()
        mock_creds_class.from_json_keyfile_name.return_value = mock_credentials

        mock_client = Mock()
        mock_spreadsheet = Mock()
        mock_client.open_by_url.return_value = mock_spreadsheet
        mock_gspread.authorize.return_value = mock_client

        writer = SheetsWriter()
        writer._ensure_connected()

        assert writer._client is not None

    @patch('write_to_sheets.gspread')
    @patch('write_to_sheets.ServiceAccountCredentials')
    @patch('write_to_sheets.Path')
    def test_ensure_connected_skips_when_connected(self, mock_path, mock_creds_class, mock_gspread):
        """Test that _ensure_connected doesn't reconnect when already connected."""
        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = Mock()

        writer._ensure_connected()

        mock_gspread.authorize.assert_not_called()


class TestSheetsWriterSetupHeaderRow:
    """Tests for setup_header_row method."""

    def test_setup_header_row_when_different(self):
        """Test setting up header row when it differs from expected."""
        mock_sheet = Mock()
        mock_sheet.row_values.return_value = []

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        writer.setup_header_row(["temp1", "temp2", "temp3"])

        mock_sheet.update.assert_called_once_with(
            'A1',
            [["Timestamp", "temp1", "temp2", "temp3"]]
        )

    def test_setup_header_row_when_same(self):
        """Test that header row is not updated when it matches."""
        mock_sheet = Mock()
        mock_sheet.row_values.return_value = ["Timestamp", "temp1", "temp2"]

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        writer.setup_header_row(["temp1", "temp2"])

        mock_sheet.update.assert_not_called()

    def test_setup_header_row_with_sheet_name(self):
        """Test setting up header row on a named sheet."""
        mock_sheet = Mock()
        mock_sheet.row_values.return_value = []

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        writer.setup_header_row(["col1"], sheet_name="CustomSheet")

        mock_spreadsheet.worksheet.assert_called_once_with("CustomSheet")
        mock_sheet.update.assert_called_once()


class TestSheetsWriterWriteRow:
    """Tests for write_row method."""

    @patch('write_to_sheets.datetime')
    def test_write_row_basic(self, mock_datetime):
        """Test writing a basic row."""
        mock_datetime.now.return_value.strftime.return_value = "2026-01-25 10:30:00"

        mock_sheet = Mock()
        mock_sheet.col_values.return_value = ["Timestamp"]  # Header only

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        data = {"temp1": 25.5, "temp2": 30.0}
        row_num = writer.write_row(data, columns=["temp1", "temp2"])

        assert row_num == 2
        mock_sheet.update.assert_called_once_with(
            'A2',
            [["2026-01-25 10:30:00", "25.50", "30.00"]]
        )

    @patch('write_to_sheets.datetime')
    def test_write_row_with_none_values(self, mock_datetime):
        """Test writing a row with None values."""
        mock_datetime.now.return_value.strftime.return_value = "2026-01-25 10:30:00"

        mock_sheet = Mock()
        mock_sheet.col_values.return_value = ["Timestamp"]

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        data = {"temp1": 25.5, "temp2": None, "temp3": 30.0}
        writer.write_row(data, columns=["temp1", "temp2", "temp3"])

        mock_sheet.update.assert_called_once_with(
            'A2',
            [["2026-01-25 10:30:00", "25.50", "", "30.00"]]
        )

    @patch('write_to_sheets.datetime')
    def test_write_row_appends_to_existing(self, mock_datetime):
        """Test that rows are appended after existing data."""
        mock_datetime.now.return_value.strftime.return_value = "2026-01-25 10:30:00"

        mock_sheet = Mock()
        mock_sheet.col_values.return_value = ["Timestamp", "row2", "row3", "row4", "row5"]

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        row_num = writer.write_row({"temp": 20.0}, columns=["temp"])

        assert row_num == 6
        mock_sheet.update.assert_called_once_with('A6', [["2026-01-25 10:30:00", "20.00"]])

    @patch('write_to_sheets.datetime')
    def test_write_row_default_column_order(self, mock_datetime):
        """Test that columns are sorted by default."""
        mock_datetime.now.return_value.strftime.return_value = "2026-01-25 10:30:00"

        mock_sheet = Mock()
        mock_sheet.col_values.return_value = []

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        data = {"zebra": 1.0, "alpha": 2.0, "beta": 3.0}
        writer.write_row(data)

        # Columns should be sorted: alpha, beta, zebra
        call_args = mock_sheet.update.call_args[0]
        row = call_args[1][0]
        assert row == ["2026-01-25 10:30:00", "2.00", "3.00", "1.00"]

    @patch('write_to_sheets.datetime')
    def test_write_row_with_integer_value(self, mock_datetime):
        """Test writing a row with integer values."""
        mock_datetime.now.return_value.strftime.return_value = "2026-01-25 10:30:00"

        mock_sheet = Mock()
        mock_sheet.col_values.return_value = []

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        data = {"count": 42}  # Integer, not float
        writer.write_row(data, columns=["count"])

        call_args = mock_sheet.update.call_args[0]
        row = call_args[1][0]
        assert row == ["2026-01-25 10:30:00", "42"]

    def test_write_row_with_sheet_name(self):
        """Test writing to a named sheet."""
        mock_sheet = Mock()
        mock_sheet.col_values.return_value = []

        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_sheet

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        with patch('write_to_sheets.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2026-01-25 10:30:00"
            writer.write_row({"val": 1.0}, sheet_name="DataSheet", columns=["val"])

        mock_spreadsheet.worksheet.assert_called_once_with("DataSheet")


class TestSheetsWriterWriteTimestampOnly:
    """Tests for write_timestamp_only method."""

    @patch('write_to_sheets.datetime')
    def test_write_timestamp_only(self, mock_datetime):
        """Test writing only a timestamp."""
        mock_datetime.now.return_value.strftime.return_value = "2026-01-25 10:30:00"

        mock_sheet = Mock()
        mock_sheet.col_values.return_value = ["Timestamp", "row2"]

        mock_spreadsheet = Mock()
        mock_spreadsheet.sheet1 = mock_sheet
        mock_spreadsheet.title = "Test Spreadsheet"

        writer = SheetsWriter()
        writer._client = Mock()
        writer._spreadsheet = mock_spreadsheet

        row_num = writer.write_timestamp_only()

        assert row_num == 3
        mock_sheet.update_cell.assert_called_once_with(3, 1, "2026-01-25 10:30:00")


class TestWriteTimestampToSheets:
    """Tests for legacy write_timestamp_to_sheets function."""

    @patch('write_to_sheets.SheetsWriter')
    def test_write_timestamp_to_sheets(self, mock_writer_class):
        """Test the legacy function creates a writer and calls write_timestamp_only."""
        mock_writer = Mock()
        mock_writer_class.return_value = mock_writer

        write_timestamp_to_sheets()

        mock_writer_class.assert_called_once()
        mock_writer.write_timestamp_only.assert_called_once()
