#!/usr/bin/env python3
"""
Hjorthagshojden Logger - Main Script

Reads data from ERAB EW-1 via Modbus TCP and logs it to Google Sheets.

Usage:
    python logger.py                    # Run once
    python logger.py --interval 300     # Run every 5 minutes
    python logger.py --config custom.json
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from ew1_reader import EW1Reader, RegisterDefinition
from write_to_sheets import SheetsWriter


# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    print("\nShutdown requested...")
    running = False


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def create_reader_from_config(config: dict) -> EW1Reader:
    """Create an EW1Reader from configuration dictionary."""
    ew1_config = config.get("ew1", {})

    # Build register definitions
    registers = []
    for reg_config in config.get("registers", []):
        registers.append(
            RegisterDefinition(
                address=reg_config["address"],
                name=reg_config["name"],
                description=reg_config.get("description", ""),
                register_type=reg_config.get("register_type", "holding"),
                count=reg_config.get("count", 1),
                data_type=reg_config.get("data_type", "uint16"),
                scale=reg_config.get("scale", 1.0),
                unit=reg_config.get("unit", ""),
            )
        )

    return EW1Reader(
        host=ew1_config.get("host", "192.168.1.100"),
        port=ew1_config.get("port", 502),
        unit_id=ew1_config.get("unit_id", 1),
        registers=registers,
    )


def log_once(reader: EW1Reader, writer: SheetsWriter, columns: list[str]) -> bool:
    """
    Perform one logging cycle: read from EW-1, write to Sheets.

    Returns:
        True if successful, False otherwise
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Read data from EW-1
        print(f"[{timestamp}] Reading from EW-1...", end=" ")
        with reader:
            data = reader.read_all_registers()

        # Count successful reads
        successful = sum(1 for v in data.values() if v is not None)
        total = len(data)
        print(f"Got {successful}/{total} values")

        # Log values
        for name, value in data.items():
            reg = next((r for r in reader.registers if r.name == name), None)
            unit = reg.unit if reg else ""
            if value is not None:
                print(f"  {name}: {value:.2f} {unit}")
            else:
                print(f"  {name}: <read failed>")

        # Write to Google Sheets
        print("Writing to Google Sheets...", end=" ")
        row = writer.write_row(data, columns=columns)
        print(f"Row {row}")

        return True

    except ConnectionError as e:
        print(f"EW-1 connection error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Log ERAB EW-1 data to Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run once with default config
  %(prog)s --interval 300            # Log every 5 minutes
  %(prog)s --config my_config.json   # Use custom configuration
  %(prog)s --dry-run                 # Test EW-1 connection only
        """,
    )
    parser.add_argument(
        "--config",
        default="registers.json",
        help="Path to configuration file (default: registers.json)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Logging interval in seconds (0 = run once, default: 0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only read from EW-1, don't write to Sheets",
    )
    parser.add_argument(
        "--setup-header",
        action="store_true",
        help="Set up the header row in Google Sheets before logging",
    )

    args = parser.parse_args()

    # Load configuration
    script_dir = Path(__file__).parent
    config_path = script_dir / args.config

    if not config_path.exists():
        print(f"Configuration file not found: {config_path}")
        print("\nPlease create a configuration file. Example:")
        print("  1. Run: python scan_registers.py <EW1_IP>")
        print("  2. Update registers.json with discovered registers")
        sys.exit(1)

    print(f"Loading configuration from {config_path}...")
    config = load_config(config_path)

    # Create reader
    reader = create_reader_from_config(config)
    ew1_host = config.get("ew1", {}).get("host", "unknown")
    print(f"EW-1 address: {ew1_host}:{reader.port}")

    # Get column names in order
    columns = [reg.name for reg in reader.registers]

    if args.dry_run:
        # Test mode - only read from EW-1
        print("\nDry run mode - reading from EW-1 only")
        try:
            with reader:
                data = reader.read_all_registers()
                print("\nRegister values:")
                print("-" * 50)
                for name, value in data.items():
                    reg = next((r for r in reader.registers if r.name == name), None)
                    unit = reg.unit if reg else ""
                    if value is not None:
                        print(f"  {name}: {value:.2f} {unit}")
                    else:
                        print(f"  {name}: <read failed>")
        except ConnectionError as e:
            print(f"Connection failed: {e}")
            sys.exit(1)
        return

    # Create Sheets writer
    writer = SheetsWriter()
    print("Connecting to Google Sheets...")
    writer.connect()

    # Set up header row if requested
    if args.setup_header:
        print("Setting up header row...")
        writer.setup_header_row(columns)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Main logging loop
    if args.interval > 0:
        print(f"\nStarting continuous logging (interval: {args.interval}s)")
        print("Press Ctrl+C to stop\n")

        while running:
            log_once(reader, writer, columns)

            # Wait for next interval (check frequently for shutdown)
            wait_until = time.time() + args.interval
            while running and time.time() < wait_until:
                time.sleep(1)

        print("Logger stopped.")
    else:
        # Single run
        success = log_once(reader, writer, columns)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
