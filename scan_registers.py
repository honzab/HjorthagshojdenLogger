#!/usr/bin/env python3
"""
Modbus Register Scanner for ERAB EW-1

Scans the Modbus registers on an EW-1 to discover what data is available.
This is useful since the EW-1 register map may vary based on configuration.

Usage:
    python scan_registers.py <EW1_IP_ADDRESS> [options]

Examples:
    python scan_registers.py 192.168.1.100
    python scan_registers.py 192.168.1.100 --start 0 --end 100 --type holding
    python scan_registers.py 192.168.1.100 --all-types
"""

import argparse
import sys
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException


def scan_registers(
    host: str,
    port: int = 502,
    unit_id: int = 1,
    start_address: int = 0,
    end_address: int = 100,
    register_type: str = "holding",
    timeout: float = 5.0,
) -> list[tuple[int, int]]:
    """
    Scan a range of Modbus registers and return those that respond.

    Args:
        host: IP address of the Modbus device
        port: Modbus TCP port
        unit_id: Modbus unit/slave ID
        start_address: Starting register address
        end_address: Ending register address (exclusive)
        register_type: Type of register ("holding", "input", "coil", "discrete")
        timeout: Connection timeout

    Returns:
        List of (address, value) tuples for registers that responded
    """
    client = ModbusTcpClient(host=host, port=port, timeout=timeout)

    if not client.connect():
        raise ConnectionError(f"Failed to connect to {host}:{port}")

    found_registers = []

    try:
        for address in range(start_address, end_address):
            try:
                if register_type == "holding":
                    result = client.read_holding_registers(address, 1, slave=unit_id)
                elif register_type == "input":
                    result = client.read_input_registers(address, 1, slave=unit_id)
                elif register_type == "coil":
                    result = client.read_coils(address, 1, slave=unit_id)
                elif register_type == "discrete":
                    result = client.read_discrete_inputs(address, 1, slave=unit_id)
                else:
                    print(f"Unknown register type: {register_type}")
                    continue

                if not result.isError():
                    if register_type in ("coil", "discrete"):
                        value = result.bits[0]
                    else:
                        value = result.registers[0]
                    found_registers.append((address, value))

            except ModbusException:
                pass  # Register doesn't exist or isn't accessible
            except Exception:
                pass

    finally:
        client.close()

    return found_registers


def interpret_value(value: int, address: int) -> str:
    """Try to interpret a register value in different formats."""
    interpretations = []

    # Unsigned 16-bit
    interpretations.append(f"uint16: {value}")

    # Signed 16-bit
    signed = value if value < 0x8000 else value - 0x10000
    if signed != value:
        interpretations.append(f"int16: {signed}")

    # As temperature (common scale: value / 10)
    temp = value / 10.0
    if -50 < temp < 150:
        interpretations.append(f"temp(÷10): {temp:.1f}°C")

    # As percentage
    if 0 <= value <= 1000:
        interpretations.append(f"pct(÷10): {value / 10:.1f}%")

    return " | ".join(interpretations)


def main():
    parser = argparse.ArgumentParser(
        description="Scan Modbus registers on ERAB EW-1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 192.168.1.100
  %(prog)s 192.168.1.100 --start 0 --end 200
  %(prog)s 192.168.1.100 --type input
  %(prog)s 192.168.1.100 --all-types
        """,
    )
    parser.add_argument("host", help="IP address of the EW-1")
    parser.add_argument(
        "--port", type=int, default=502, help="Modbus TCP port (default: 502)"
    )
    parser.add_argument(
        "--unit", type=int, default=1, help="Modbus unit/slave ID (default: 1)"
    )
    parser.add_argument(
        "--start", type=int, default=0, help="Start address (default: 0)"
    )
    parser.add_argument(
        "--end", type=int, default=100, help="End address (default: 100)"
    )
    parser.add_argument(
        "--type",
        choices=["holding", "input", "coil", "discrete"],
        default="holding",
        help="Register type to scan (default: holding)",
    )
    parser.add_argument(
        "--all-types", action="store_true", help="Scan all register types"
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="Connection timeout (default: 5.0)"
    )
    parser.add_argument("--output", help="Save results to JSON file")

    args = parser.parse_args()

    print(f"Connecting to {args.host}:{args.port}...")

    register_types = (
        ["holding", "input", "coil", "discrete"] if args.all_types else [args.type]
    )
    all_results = {}

    for reg_type in register_types:
        print(f"\nScanning {reg_type} registers {args.start}-{args.end}...")

        try:
            found = scan_registers(
                host=args.host,
                port=args.port,
                unit_id=args.unit,
                start_address=args.start,
                end_address=args.end,
                register_type=reg_type,
                timeout=args.timeout,
            )

            all_results[reg_type] = found

            if found:
                print(f"\nFound {len(found)} {reg_type} registers:")
                print("-" * 80)
                for address, value in found:
                    interp = interpret_value(value, address)
                    print(
                        f"  [{address:5d}] Raw: {value:5d} (0x{value:04X}) | {interp}"
                    )
            else:
                print(
                    f"  No {reg_type} registers found in range {args.start}-{args.end}"
                )

        except ConnectionError as e:
            print(f"Connection error: {e}")
            sys.exit(1)

    # Save to JSON if requested
    if args.output:
        import json

        output_data = {
            "host": args.host,
            "port": args.port,
            "unit_id": args.unit,
            "scan_range": {"start": args.start, "end": args.end},
            "results": {
                reg_type: [{"address": addr, "value": val} for addr, val in regs]
                for reg_type, regs in all_results.items()
            },
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to {args.output}")

    # Generate suggested configuration
    total_found = sum(len(regs) for regs in all_results.values())
    if total_found > 0:
        print("\n" + "=" * 80)
        print("SUGGESTED CONFIGURATION")
        print("=" * 80)
        print("\nAdd these to your registers.json configuration file:")
        print('{\n  "registers": [')

        entries = []
        for reg_type, regs in all_results.items():
            for address, value in regs:
                entries.append(
                    f'    {{"address": {address}, "name": "reg_{address}", '
                    f'"description": "Register {address}", "register_type": "{reg_type}", '
                    f'"data_type": "int16", "scale": 0.1, "unit": ""}}'
                )
        print(",\n".join(entries))
        print("  ]\n}")


if __name__ == "__main__":
    main()
