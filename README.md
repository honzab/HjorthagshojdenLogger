# HjorthagshojdenLogger

Logs data from an ERAB EW-1 DUC (digitaliserad undercentral in Swedish) to Google Sheets via Modbus TCP.

## Overview

This project reads sensor data from an ERAB EW-1 controller via Modbus TCP and logs it to a Google Spreadsheet for monitoring and analysis.

**Components:**
- `logger.py` - Main script that reads from EW-1 and writes to Google Sheets
- `ew1_reader.py` - Modbus TCP client for reading EW-1 registers
- `scan_registers.py` - Utility to discover available Modbus registers
- `write_to_sheets.py` - Google Sheets API wrapper
- `registers.json` - Configuration for EW-1 connection and register definitions

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

### 4. Configure the EW-1 Connection

#### Step 1: Discover Available Registers

First, find out what registers your EW-1 exposes:

```bash
# Scan holding registers 0-100
uv run scan_registers.py 192.168.1.100

# Scan input registers
uv run scan_registers.py 192.168.1.100 --type input

# Scan all register types with wider range
uv run scan_registers.py 192.168.1.100 --all-types --start 0 --end 200

# Save results to file
uv run scan_registers.py 192.168.1.100 --all-types --output scan_results.json
```

#### Step 2: Update Configuration

Edit `registers.json` with your EW-1's IP address and the registers you discovered:

```json
{
  "ew1": {
    "host": "192.168.1.100",
    "port": 502,
    "unit_id": 1
  },
  "registers": [
    {
      "address": 0,
      "name": "temp_supply",
      "description": "Supply temperature",
      "register_type": "input",
      "data_type": "int16",
      "scale": 0.1,
      "unit": "°C"
    }
  ]
}
```

**Register configuration options:**
- `address`: Modbus register address
- `name`: Column name in Google Sheets
- `description`: Human-readable description
- `register_type`: `"holding"`, `"input"`, `"coil"`, or `"discrete"`
- `data_type`: `"uint16"`, `"int16"`, `"uint32"`, `"int32"`, or `"float32"`
- `scale`: Multiplier for raw value (e.g., 0.1 if raw 235 means 23.5°C)
- `unit`: Unit of measurement for display

### 5. Test the Connection

```bash
# Test reading from EW-1 without writing to Sheets
uv run logger.py --dry-run
```

### 6. Run the Logger

```bash
# Run once
uv run logger.py

# Set up header row first
uv run logger.py --setup-header

# Run continuously every 5 minutes
uv run logger.py --interval 300

# Use custom config file
uv run logger.py --config my_config.json
```

## Running on Raspberry Pi

### Systemd Service (Recommended)

Create `/etc/systemd/system/ew1-logger.service`:

```ini
[Unit]
Description=EW-1 Logger
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/HjorthagshojdenLogger
ExecStart=/home/pi/.local/bin/uv run logger.py --interval 300
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ew1-logger
sudo systemctl start ew1-logger
sudo systemctl status ew1-logger
```

### Cron Job (Alternative)

```bash
# Edit crontab
crontab -e

# Add line to run every 5 minutes
*/5 * * * * cd /home/pi/HjorthagshojdenLogger && /home/pi/.local/bin/uv run logger.py >> /var/log/ew1-logger.log 2>&1
```

## Troubleshooting

### Cannot connect to EW-1
- Verify the IP address is correct
- Ensure the Raspberry Pi is on the same network
- Check if Modbus TCP is enabled on the EW-1 (port 502)
- Try: `nc -zv 192.168.1.100 502`

### No registers found
- The EW-1 may use different register addresses based on configuration
- Try scanning different address ranges: `--start 0 --end 500`
- Check the EW-1 web interface for Modbus configuration
- Contact ERAB for the register documentation for your setup

### Google Sheets authentication error
- Verify the service account JSON file exists
- Ensure the spreadsheet is shared with the service account email
- Check that the Google Sheets API is enabled

## Example Output

```
$ uv run logger.py --interval 300
Loading configuration from registers.json...
EW-1 address: 192.168.1.100:502
Connecting to Google Sheets...

Starting continuous logging (interval: 300s)
Press Ctrl+C to stop

[2026-01-25 10:30:00] Reading from EW-1... Got 6/6 values
  temp_supply: 45.20 °C
  temp_return: 38.50 °C
  temp_outdoor: -2.30 °C
  temp_indoor: 21.40 °C
  temp_hotwater: 52.10 °C
  temp_extra: 35.00 °C
Writing to Google Sheets... Row 15
```

## Development

### Install Dev Dependencies

```bash
uv sync --group dev
```

### Set Up Pre-commit Hooks

```bash
uv tool install pre-commit
pre-commit install
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_ew1_reader.py

# Run specific test class or function
uv run pytest tests/test_ew1_reader.py::TestEW1ReaderConvertRawValue
uv run pytest -k "test_int16"

# Run with coverage (requires pytest-cov)
uv run pytest --cov=. --cov-report=term-missing
```

### Test Structure

```
tests/
├── __init__.py
├── test_ew1_reader.py      # Modbus reader tests
├── test_write_to_sheets.py # Google Sheets writer tests
├── test_logger.py          # Main logger tests
└── test_scan_registers.py  # Register scanner tests
```

Tests use mocking to avoid requiring actual hardware or API connections.
