#!/usr/bin/env python3
"""
Google Sheets Writer - Writes current timestamp to column A
Requires: pip install gspread oauth2client
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Configuration
SPREADSHEET_URL = ""
SERVICE_ACCOUNT_FILE = ""

def write_timestamp_to_sheets():
    """Write current timestamp to column A of Google Sheet"""
    
    # Define the scope
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Authenticate using service account
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_FILE, 
        scope
    )
    client = gspread.authorize(credentials)
    
    # Open the spreadsheet
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    
    # Get the first sheet (or specify sheet name: spreadsheet.worksheet('Sheet1'))
    sheet = spreadsheet.sheet1
    
    # Get current time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Find the next empty row in column A
    values = sheet.col_values(1)  # Get all values in column A
    next_row = len(values) + 1
    
    # Write to column A
    sheet.update_cell(next_row, 1, current_time)
    
    print(f"✓ Successfully wrote timestamp to cell A{next_row}: {current_time}")
    print(f"  Spreadsheet: {spreadsheet.title}")

if __name__ == "__main__":
    write_timestamp_to_sheets()
    # print(f"✗ Error: {e}")
