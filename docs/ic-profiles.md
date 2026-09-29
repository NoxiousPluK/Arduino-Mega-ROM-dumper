# Per-IC wiring guide

Pinouts and Arduino Mega 2560 pin mappings actually used for each profile.
All three chips are read the same way: address lines driven from
`ADDR_PIN_BASE` (D22) upward, data lines read from `DATA_PIN_BASE` (D34)
upward, both assigned **in ascending pin order** (`A0`/`O1` first).

Every enable pin on these parts is active-low, so grounding it holds the
chip permanently selected so the Arduino never has to drive an enable line.

---

## Profile 1: N82S129N (256×4 bipolar PROM), 16-pin DIP

8 address lines, 4 data lines.

```
              N82S129N
            ┌────┬──┬────┐
      A5 ─1─┤●   ╰──╯  16├─ VCC  ─ 5V
      A4 ─2─┤          15├─ A7   ─ D29
      A3 ─3─┤          14├─ !CE1 ─ GND
      A0 ─4─┤          13├─ !CE2 ─ GND
      A1 ─5─┤          12├─ O1   ─ D34
      A2 ─6─┤          11├─ O2   ─ D35
     GND ─7─┤ GND      10├─ O3   ─ D36
      A6 ─8─┤           9├─ O4   ─ D37
            └────────────┘
```

| Pin | Signal | Connects to |
|---|---|---|
| 1 | A5 | D27 |
| 2 | A4 | D26 |
| 3 | A3 | D25 |
| 4 | A0 | D22 |
| 5 | A1 | D23 |
| 6 | A2 | D24 |
| 7 | GND | GND |
| 8 | A6 | D28 |
| 9 | O4 | D37 |
| 10 | O3 | D36 |
| 11 | O2 | D35 |
| 12 | O1 | D34 |
| 13 | !CE2 | GND |
| 14 | !CE1 | GND |
| 15 | A7 | D29 |
| 16 | VCC | 5V |

Data nibble bit order: **bit0 = O1 (LSB) … bit3 = O4 (MSB)**.

---

## Profile 2: N82S137N (1024×4 bipolar PROM), 18-pin DIP

10 address lines, 4 data lines.

```
              N82S137N
            ┌────┬──┬────┐
      A6 ─1─┤●   ╰──╯  18├─ VCC  ─ 5V
      A5 ─2─┤          17├─ A7   ─ D29
      A4 ─3─┤          16├─ A8   ─ D30
      A3 ─4─┤          15├─ A9   ─ D31
      A0 ─5─┤          14├─ O1   ─ D34
      A1 ─6─┤          13├─ O2   ─ D35
      A2 ─7─┤          12├─ O3   ─ D36
    !CE2 ─8─┤ GND      11├─ O4   ─ D37
     GND ─9─┤          10├─ !CE1 ─ GND
            └────────────┘
```

| Pin | Signal | Connects to |
|---|---|---|
| 1 | A6 | D28 |
| 2 | A5 | D27 |
| 3 | A4 | D26 |
| 4 | A3 | D25 |
| 5 | A0 | D22 |
| 6 | A1 | D23 |
| 7 | A2 | D24 |
| 8 | !CE2 | GND |
| 9 | GND | GND |
| 10 | !CE1 | GND |
| 11 | O4 | D37 |
| 12 | O3 | D36 |
| 13 | O2 | D35 |
| 14 | O1 | D34 |
| 15 | A9 | D31 |
| 16 | A8 | D30 |
| 17 | A7 | D29 |
| 18 | VCC | 5V |

Data nibble bit order: **bit0 = O1 (LSB) … bit3 = O4 (MSB)**.

---

## Profile 3: 2732-family EPROM (4K×8), 24-pin DIP

12 address lines, 8 data lines.

Standard JEDEC 24-pin EPROM pinout (`A0`-`A11`, `O0`-`O7`, `!CE`, `!OE`,
`VPP`/`A12` tied per the 2732 datasheet). Ground `!CE` and `!OE` on the
breadboard exactly as with the bipolar PROMs above; map `A0`-`A11` to
`D22`-`D33` in order and `O0`-`O7` (or `O1`-`O8`, depending on the
datasheet's own numbering) to `D34`-`D41` in order.

| Signal | Connects to | Signal | Connects to |
|---|---|---|---|
| A0 | D22 | D0 | D34 |
| A1 | D23 | D1 | D35 |
| A2 | D24 | D2 | D36 |
| A3 | D25 | D3 | D37 |
| A4 | D26 | D4 | D38 |
| A5 | D27 | D5 | D39 |
| A6 | D28 | D6 | D40 |
| A7 | D29 | D7 | D41 |
| A8 | D30 | !CE | GND |
| A9 | D31 | !OE | GND |
| A10 | D32 | VCC | 5V |
| A11 | D33 | GND | GND |

Data byte bit order: **bit0 = D0 (LSB) … bit7 = D7 (MSB)**, matching the
sketch's `readData()` loop.

> **Note:** unlike the two PROM profiles above (whose exact pinouts were
> verified pin-by-pin against the physical chips, this profile's mapping is
> the general 2732 JEDEC pinout applied straight through. Cross-check
> against your specific part's datasheet before wiring.

---

## Adding a new profile

To dump a different chip, add an entry to the `PROFILES[]` array in
`../rom_dumper/rom_dumper.ino` with its address/data bit counts, then wire address
lines to D22 upward and data lines to D34 upward per its own datasheet
pinout (following the pattern above). Keep `MAX_ADDR_BITS` /
`MAX_DATA_BITS` in the sketch equal to or greater than the new profile's
requirements. They're currently sized for the 2732 EPROM profile (12/8)
and don't need raising for anything smaller.
