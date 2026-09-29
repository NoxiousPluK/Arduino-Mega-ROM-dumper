# Arduino Mega ROM dumper

A simple Arduino sketch that reads a parallel ROM/PROM chip directly
over GPIO. No shift registers, no dedicated programmer. Streams the
contents out as hex text over serial. Written for the Arduino Mega 2560,
whose pin count is generous enough to wire every address and data line
straight to a digital pin.

Inspired by the [2011 Hackaday 82S129 Arduino dumper](https://hackaday.com/2011/05/18/arduino-arcade-rom-dumper/).

## What it dumps

Three built-in profiles, selected at runtime over serial:

| # | Chip family | Addr lines | Data lines | Size |
|---|---|---|---|---|
| 1 | 82S129-family bipolar PROM | 8 | 4 | 256×4 |
| 2 | 82S137-family bipolar PROM | 10 | 4 | 1024×4 |
| 3 | 2732-family EPROM | 12 | 8 | 4K×8 |

See [`docs/ic-profiles.md`](docs/ic-profiles.md) for pinouts, wiring
diagrams, and part-specific notes for each of these.

## Wiring (general)

- **Address lines:** D22 upward, in order (`A0`→D22, `A1`→D23, ...); only
  as many as the selected profile needs.
- **Data lines:** D34 upward, in order (`O1`→D34, `O2`→D35, ...); only as
  many as the selected profile needs.
- **Chip enable / output enable pins** (`CE`, `OE`, `CE1`, `CE2`; all
  active-low on these parts): tie directly to **GND**, not to a GPIO pin.
  This keeps the chip permanently selected and its outputs permanently driven,
  so the Arduino only ever needs to read data, never toggle enables.
- **VCC / GND:** from the Arduino's own 5V and GND pins.

Data pins are configured `INPUT_PULLUP` as a safety net (a defined idle
state if the CE wiring is wrong, or during power-up). This is easily
overridden by the chip's own TTL output drive once it's correctly enabled.

## Usage

1. Flash the sketch in [`rom_dumper/`](rom_dumper/) to the Mega 2560
   (Arduino IDE, or `arduino-cli`):
   ```
   arduino-cli compile --fqbn arduino:avr:mega rom_dumper
   arduino-cli upload -p <serial port> --fqbn arduino:avr:mega rom_dumper
   ```
2. Wire the chip per the profile you need: see [`docs/ic-profiles.md`](docs/ic-profiles.md).
3. Dump it with `rom_dumper.py` (recommended), or by hand over a serial
   terminal.

### Option A: `rom_dumper.py` (recommended)

Requires [pyserial](https://pyserial.readthedocs.io/):
 `pip install pyserial`.

```
python3 rom_dumper.py [--port /dev/ttyACM0] [--profile 2] [--outfile out.rom]
```

Any argument left out is asked for interactively — it lists the serial
ports actually present and lets you pick one, fetches the profile list
live from the connected Arduino (so it can never go stale relative to the
sketch), and suggests a filename derived from the profile name. It
verifies the address count and the Arduino's own XOR checksum before
writing anything, and refuses to write a file if either check fails.

### Option B: by hand over a serial terminal

1. Open a serial terminal at **115200 baud**.
2. Send the profile number (`1`, `2`, or `3`) to select it.
3. Send `D` to start the dump.

Output is one line per address, `ADDR: DATA` (both zero-padded hex), plus
a running XOR checksum printed at the end:

```
=== Parallel ROM dumper ===
1: N82S129N (256x4 bipolar PROM) - 8 addr / 4 data lines
2: N82S137N (1024x4 bipolar PROM) - 10 addr / 4 data lines
3: 2732-family EPROM (4Kx8) - 12 addr / 8 data lines
Send the profile number to select it, then 'D' to dump. 'L' lists profiles machine-readably.
Selected: N82S137N (1024x4 bipolar PROM)
Dumping N82S137N (1024x4 bipolar PROM), 1024 addresses...
0000: 5
0001: A
...
03FF: 3
Done. 1024 addresses read. XOR checksum: 7C
```

Redirect the terminal's log/capture to a file, then post-process it into a
binary by hand. This is what `rom_dumper.py` automates.

## Verifying a dump

`rom_dumper.py` checks the address count and the Arduino's own XOR
checksum automatically, and won't write a `.rom` file if either is off —
but that only catches a dump that changed *mid-run* (a flaky
connection), not a *consistently* wrong one (e.g. a swapped address
line). **Always dump the same chip twice and diff/checksum-compare the
two `.rom` files before trusting either one.** Double-check wiring if
things aren't as expected, perhaps one line isn't properly connected.

## Caveats

- **Settle delay** (`SETTLE_US`, 500µs by default) is a deliberately
  generous safety margin, not tuned for speed. Real access times for these
  parts are tens to a couple hundred nanoseconds. Fine for chips this
  small (at most a few thousand addresses); worth shortening if you ever
  dump something much larger.
- **Stale serial port config.** If a dump comes back as garbled binary
  instead of clean `ADDR: DATA` text, it's almost always a leftover
  terminal/port configuration from a previous session, not a hardware
  fault. Re-open the port fresh (e.g. on Linux:
  `stty -F /dev/ttyACMx 115200 raw -echo` before reconnecting).
