#!/usr/bin/env python3
"""
Google Sheets Writer - Writes data with timestamps to Google Sheets
Requires: gspread oauth2client
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import Optional
from pathlib import Path

# Configuration
SPREADSHEET_URL = ""
SERVICE_ACCOUNT_FILE = ""


class SheetsWriter:
    """Writes data to Google Sheets."""

    def __init__(
        self,
        spreadsheet_url: str = SPREADSHEET_URL,
        service_account_file: str = SERVICE_ACCOUNT_FILE
    ):
        """
        Initialize the Sheets writer.

        Args:
            spreadsheet_url: URL of the Google Spreadsheet
            service_account_file: Path to the service account JSON file
        """
        self.spreadsheet_url = spreadsheet_url
        self.service_account_file = service_account_file
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None

    def connect(self):
        """Connect to Google Sheets API."""
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]

        # Resolve path relative to this script's directory
        script_dir = Path(__file__).parent
        service_file = script_dir / self.service_account_file

        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            str(service_file),
            scope
        )
        self._client = gspread.authorize(credentials)
        self._spreadsheet = self._client.open_by_url(self.spreadsheet_url)

    def _ensure_connected(self):
        """Ensure we're connected to the API."""
        if self._client is None or self._spreadsheet is None:
            self.connect()

    def setup_header_row(self, columns: list[str], sheet_name: Optional[str] = None):
        """
        Set up the header row with column names.

        Args:
            columns: List of column names (first column is always "Timestamp")
            sheet_name: Name of the worksheet (default: first sheet)
        """
        self._ensure_connected()

        sheet = (
            self._spreadsheet.worksheet(sheet_name)
            if sheet_name
            else self._spreadsheet.sheet1
        )

        # Check if header already exists
        existing_header = sheet.row_values(1)
        expected_header = ["Timestamp"] + columns

        if existing_header != expected_header:
            # Update header row
            sheet.update('A1', [expected_header])
            print(f"Header row updated: {expected_header}")

    def write_row(
        self,
        data: dict[str, Optional[float]],
        sheet_name: Optional[str] = None,
        columns: Optional[list[str]] = None
    ) -> int:
        """
        Write a row of data with timestamp to the spreadsheet.

        Args:
            data: Dictionary of column_name -> value
            sheet_name: Name of the worksheet (default: first sheet)
            columns: Column order (default: sorted keys from data)

        Returns:
            Row number that was written
        """
        self._ensure_connected()

        sheet = (
            self._spreadsheet.worksheet(sheet_name)
            if sheet_name
            else self._spreadsheet.sheet1
        )

        # Get current time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine column order
        if columns is None:
            columns = sorted(data.keys())

        # Build row: timestamp + values in column order
        row = [current_time]
        for col in columns:
            value = data.get(col)
            if value is not None:
                # Format numbers nicely
                row.append(f"{value:.2f}" if isinstance(value, float) else str(value))
            else:
                row.append("")

        # Find next empty row (check column A)
        values = sheet.col_values(1)
        next_row = len(values) + 1

        # Write the row
        sheet.update(f'A{next_row}', [row])

        return next_row

    def write_timestamp_only(self, sheet_name: Optional[str] = None) -> int:
        """
        Write only a timestamp (backwards compatible with original behavior).

        Args:
            sheet_name: Name of the worksheet (default: first sheet)

        Returns:
            Row number that was written
        """
        self._ensure_connected()

        sheet = (
            self._spreadsheet.worksheet(sheet_name)
            if sheet_name
            else self._spreadsheet.sheet1
        )

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        values = sheet.col_values(1)
        next_row = len(values) + 1

        sheet.update_cell(next_row, 1, current_time)

        print(f"Wrote timestamp to cell A{next_row}: {current_time}")
        print(f"  Spreadsheet: {self._spreadsheet.title}")

        return next_row


def write_timestamp_to_sheets():
    """Write current timestamp to column A of Google Sheet (legacy function)."""
    writer = SheetsWriter()
    writer.write_timestamp_only()


if __name__ == "__main__":
    write_timestamp_to_sheets()
