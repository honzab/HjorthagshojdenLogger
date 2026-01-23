# HjorthagshojdenLogger

Simple Python script that can write values to a spreadsheet.
Will be paired up with ModBus reader to actually provide some values.

## Setup Instructions

### 1. Install Dependencies
```bash
uv sync
```

### 2. Create a Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the Google Sheets API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click "Enable"
4. Create Service Account credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Fill in the details and create
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose JSON format
   - Download the JSON file

### 3. Share Your Spreadsheet

1. Open your Google spreadsheet
2. Click "Share" button
3. Add the service account email (found in the JSON file as `client_email`)
4. Give it "Editor" permissions

### 4. Configure the Script

Edit `write_to_sheets.py` and update:
- `SPREADSHEET_URL`: Your Google Sheets URL
- `SERVICE_ACCOUNT_FILE`: Path to your downloaded JSON key file

### 5. Run the Script

```bash
uv run write_to_sheets.py
```

## How It Works

- Connects to Google Sheets using service account authentication
- Finds the next empty row in column A
- Writes the current timestamp in format: `YYYY-MM-DD HH:MM:SS`
- Each run appends a new timestamp below the previous ones

## Example Output

```
✓ Successfully wrote timestamp to cell A5: 2026-01-23 14:30:45
  Spreadsheet: My Spreadsheet
```
