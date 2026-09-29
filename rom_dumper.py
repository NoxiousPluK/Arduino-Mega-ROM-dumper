#!/usr/bin/env python3
"""Serial helper for rom_dumper.ino: drives the dump and saves a .rom file.

Talks to the Arduino sketch over its machine-readable protocol (see the
comment block at the top of rom_dumper.ino):

    READY,ROM_DUMPER,1
    PROFILE,<n>,<name>,<addrBits>,<dataBits>
    LIST_END
    DUMP_BEGIN,<name>,<count>,<dataBits>
    <ADDR>: <DATA>              (one line per address, hex)
    DUMP_END,<count>,<checksumHex>

Usage:
    python3 rom_dumper.py [--port /dev/ttyACM0] [--profile 2] [--outfile out.rom]

Any omitted argument is asked for interactively: --port offers a picker
built from the serial ports actually present on the system, --profile is
fetched live from the connected Arduino (never hardcoded here, so it can
never drift out of sync with the sketch), and --outfile defaults to a
name derived from the profile but can be overridden.

Requires pyserial (`paru -S python-pyserial`, or `pip install pyserial`).
"""

import argparse
import re
import sys
import time
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit(
        "error: pyserial is not installed.\n"
        "Install it with: paru -S python-pyserial   (or: pip install pyserial)"
    )

BAUD = 115200
# Arduino Mega resets on port open; this is how long to wait for the
# bootloader + sketch setup() to finish before we start talking to it.
RESET_WAIT_S = 2.5
READ_TIMEOUT_S = 5

DATA_LINE_RE = re.compile(r"^([0-9A-Fa-f]{4}):\s*([0-9A-Fa-f]{1,2})$")


class Profile:
    def __init__(self, number, name, addr_bits, data_bits):
        self.number = number
        self.name = name
        self.addr_bits = addr_bits
        self.data_bits = data_bits

    @property
    def count(self):
        return 1 << self.addr_bits

    def __str__(self):
        return f"{self.number}: {self.name} ({self.addr_bits} addr / {self.data_bits} data lines, {self.count} bytes)"


def pick_port():
    ports = list(list_ports.comports())
    if not ports:
        sys.exit("error: no serial ports found. Is the Arduino plugged in?")
    if len(ports) == 1:
        print(f"Using the only serial port found: {ports[0].device} ({ports[0].description})")
        return ports[0].device

    print("Available serial ports:")
    for i, p in enumerate(ports, 1):
        print(f"  {i}: {p.device} - {p.description}")
    while True:
        choice = input(f"Select a port [1-{len(ports)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        print("Invalid choice, try again.")


def open_connection(port):
    print(f"Connecting to {port} at {BAUD} baud...")
    try:
        ser = serial.Serial(port, BAUD, timeout=READ_TIMEOUT_S)
    except serial.SerialException as e:
        sys.exit(f"error: couldn't open {port}: {e}")
    # Opening the port resets the Mega; give the sketch time to boot before
    # sending anything, otherwise early bytes get lost.
    time.sleep(RESET_WAIT_S)
    ser.reset_input_buffer()
    return ser


def fetch_profiles(ser):
    ser.write(b"L")
    profiles = []
    deadline = time.time() + READ_TIMEOUT_S
    while time.time() < deadline:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if not line:
            continue
        if line == "LIST_END":
            break
        if line.startswith("PROFILE,"):
            parts = line.split(",")
            if len(parts) == 5:
                _, num, name, addr_bits, data_bits = parts
                profiles.append(Profile(int(num), name, int(addr_bits), int(data_bits)))
    if not profiles:
        sys.exit(
            "error: got no profile list back from the Arduino.\n"
            "Check it's running rom_dumper.ino and not still resetting."
        )
    return profiles


def pick_profile(profiles):
    print("Profiles reported by the Arduino:")
    for p in profiles:
        print(f"  {p}")
    valid = {p.number for p in profiles}
    while True:
        choice = input(f"Select a profile [{'/'.join(str(n) for n in sorted(valid))}]: ").strip()
        if choice.isdigit() and int(choice) in valid:
            return next(p for p in profiles if p.number == int(choice))
        print("Invalid choice, try again.")


def default_outfile(profile):
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", profile.name).strip("_")
    return f"{safe_name}.rom"


def run_dump(ser, profile):
    ser.reset_input_buffer()
    ser.write(str(profile.number).encode("ascii"))

    # Confirm the Arduino actually selected the profile we asked for before
    # triggering the dump, rather than silently dumping whatever it had
    # selected previously.
    deadline = time.time() + READ_TIMEOUT_S
    selected = False
    while time.time() < deadline:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if line.startswith("Selected:"):
            selected = True
            break
    if not selected:
        sys.exit("error: Arduino didn't confirm profile selection.")

    ser.write(b"D")

    data = {}
    expected_count = None
    reported_checksum = None
    dump_started = False
    deadline = time.time() + READ_TIMEOUT_S

    print(f"Dumping {profile.name} ({profile.count} addresses)...")
    while True:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if not line:
            if time.time() > deadline:
                sys.exit("error: timed out waiting for dump data from the Arduino.")
            continue
        deadline = time.time() + READ_TIMEOUT_S

        if line.startswith("DUMP_BEGIN,"):
            dump_started = True
            expected_count = int(line.split(",")[2])
            continue
        if line.startswith("DUMP_END,"):
            parts = line.split(",")
            reported_checksum = int(parts[2], 16)
            break

        m = DATA_LINE_RE.match(line)
        if m and dump_started:
            addr = int(m.group(1), 16)
            data[addr] = int(m.group(2), 16)
            if len(data) % 256 == 0:
                print(f"  {len(data)}/{expected_count}", end="\r")

    print(f"  {len(data)}/{expected_count}")

    if expected_count is None or len(data) != expected_count:
        sys.exit(f"error: expected {expected_count} addresses, got {len(data)}. Aborting, not writing a file.")
    if sorted(data.keys()) != list(range(expected_count)):
        sys.exit("error: gaps or duplicate addresses in the dump. Aborting, not writing a file.")

    computed_checksum = 0
    for addr in range(expected_count):
        computed_checksum ^= data[addr]
    if computed_checksum != reported_checksum:
        sys.exit(
            f"error: checksum mismatch (Arduino said {reported_checksum:02X}, "
            f"recomputed {computed_checksum:02X}). Aborting, not writing a file."
        )

    print(f"Checksum OK: {computed_checksum:02X}")
    return bytes(data[addr] for addr in range(expected_count))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port, e.g. /dev/ttyACM0 (asked interactively if omitted)")
    parser.add_argument("--profile", type=int, help="profile number, e.g. 2 (asked interactively if omitted)")
    parser.add_argument("--outfile", help="output .rom filename (default derived from profile name)")
    args = parser.parse_args()

    port = args.port or pick_port()
    ser = open_connection(port)

    try:
        profiles = fetch_profiles(ser)

        if args.profile is not None:
            profile = next((p for p in profiles if p.number == args.profile), None)
            if profile is None:
                valid = ", ".join(str(p.number) for p in profiles)
                sys.exit(f"error: profile {args.profile} not offered by this Arduino. Valid: {valid}")
        else:
            profile = pick_profile(profiles)

        outfile = args.outfile or default_outfile(profile)
        if Path(outfile).exists():
            resp = input(f"{outfile} already exists, overwrite? [y/N]: ").strip().lower()
            if resp != "y":
                sys.exit("Aborted.")

        raw = run_dump(ser, profile)
    finally:
        ser.close()

    Path(outfile).write_bytes(raw)
    print(f"Wrote {len(raw)} bytes to {outfile}")


if __name__ == "__main__":
    main()
