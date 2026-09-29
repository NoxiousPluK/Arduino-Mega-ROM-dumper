// Parallel ROM/PROM dumper for Arduino Mega 2560.
// Inspired by https://hackaday.com/2011/05/18/arduino-arcade-rom-dumper/
// Direct GPIO only.
//
// Wiring:
//   Address lines: D22, D23, D24, ... (as many as the chip needs, in order)
//   Data lines:    D34, D35, D36, ... (as many as the chip needs, in order)
//   CE / OE / CE1 / CE2: tie directly to GND on the Arduino NOT selected
//                         by the Arduino. These are all active-low chip
//                         enables; grounding them keeps the chip permanently
//                         selected/enabled for reading, same approach the
//                         original Hackaday 82S129 dumper used.
//   VCC / GND: chip's own 5V and ground, from the Arduino's 5V/GND pins.
//
// Usage: open a serial terminal at 115200 baud. Send a digit to pick the
// chip profile, then 'D' to dump. Output is one "ADDR: DATA" line per
// address, plus a running XOR checksum at the end (dump the same chip
// twice and compare the checksum + full output as a quick reliability
// check before trusting a dump).
//
// Machine-readable lines (for rom_dumper.py, or any other script driving
// this sketch) are interspersed with the human-readable ones above:
//   READY,ROM_DUMPER,1                     - printed once at boot
//   PROFILE,<n>,<name>,<addrBits>,<dataBits>  - printed for each profile
//   LIST_END                               - sent by 'L', terminates the list
//   DUMP_BEGIN,<name>,<count>,<dataBits>   - start of a 'D' dump
//   DUMP_END,<count>,<checksumHex>         - end of a 'D' dump

const int ADDR_PIN_BASE = 22;
const int DATA_PIN_BASE = 34;
const int MAX_ADDR_BITS = 12;
const int MAX_DATA_BITS = 8;

struct Profile {
  const char *name;
  uint8_t addrBits;
  uint8_t dataBits;
};

// Index matches the serial command digit ('1', '2', '3').
const Profile PROFILES[] = {
  {"N82S129N (256x4 bipolar PROM)",  8, 4},
  {"N82S137N (1024x4 bipolar PROM)", 10, 4},
  {"2732-family EPROM (4Kx8)",       12, 8},
};
const int NUM_PROFILES = sizeof(PROFILES) / sizeof(PROFILES[0]);

int currentProfile = -1;

// Microseconds to wait after setting a new address before sampling data.
// Real access times for these parts are tens to a couple hundred ns; this
// is a very generous safety margin, not a speed-tuned value.
const unsigned long SETTLE_US = 500;

void printProfileList() {
  for (int i = 0; i < NUM_PROFILES; i++) {
    Serial.print(F("PROFILE,"));
    Serial.print(i + 1);
    Serial.print(F(","));
    Serial.print(PROFILES[i].name);
    Serial.print(F(","));
    Serial.print(PROFILES[i].addrBits);
    Serial.print(F(","));
    Serial.println(PROFILES[i].dataBits);
  }
  Serial.println(F("LIST_END"));
}

void printMenu() {
  Serial.println();
  Serial.println(F("=== Parallel ROM dumper ==="));
  for (int i = 0; i < NUM_PROFILES; i++) {
    Serial.print(i + 1);
    Serial.print(F(": "));
    Serial.print(PROFILES[i].name);
    Serial.print(F(" - "));
    Serial.print(PROFILES[i].addrBits);
    Serial.print(F(" addr / "));
    Serial.print(PROFILES[i].dataBits);
    Serial.println(F(" data lines"));
  }
  Serial.println(F("Send the profile number to select it, then 'D' to dump. 'L' lists profiles machine-readably."));
  if (currentProfile >= 0) {
    Serial.print(F("Current profile: "));
    Serial.println(PROFILES[currentProfile].name);
  }
}

void configurePins(const Profile &p) {
  for (int i = 0; i < p.addrBits; i++) {
    pinMode(ADDR_PIN_BASE + i, OUTPUT);
    digitalWrite(ADDR_PIN_BASE + i, LOW);
  }
  for (int i = 0; i < p.dataBits; i++) {
    // Pullup as a safety net (defined idle state if CE wiring is wrong or
    // during power-up), easily overridden by the chip's own TTL output
    // drive once CE is correctly grounded and the chip is selected.
    pinMode(DATA_PIN_BASE + i, INPUT_PULLUP);
  }
}

void setAddress(uint16_t addr, uint8_t addrBits) {
  for (uint8_t i = 0; i < addrBits; i++) {
    digitalWrite(ADDR_PIN_BASE + i, (addr >> i) & 1);
  }
}

uint8_t readData(uint8_t dataBits) {
  uint8_t v = 0;
  for (uint8_t i = 0; i < dataBits; i++) {
    if (digitalRead(DATA_PIN_BASE + i)) v |= (1 << i);
  }
  return v;
}

void doDump() {
  if (currentProfile < 0) {
    Serial.println(F("No profile selected."));
    return;
  }
  const Profile &p = PROFILES[currentProfile];
  uint32_t count = 1UL << p.addrBits;
  uint8_t checksum = 0;
  int hexDigits = (p.dataBits + 3) / 4;

  Serial.print(F("Dumping "));
  Serial.print(PROFILES[currentProfile].name);
  Serial.print(F(", "));
  Serial.print(count);
  Serial.println(F(" addresses..."));

  Serial.print(F("DUMP_BEGIN,"));
  Serial.print(p.name);
  Serial.print(F(","));
  Serial.print(count);
  Serial.print(F(","));
  Serial.println(p.dataBits);

  for (uint32_t addr = 0; addr < count; addr++) {
    setAddress((uint16_t)addr, p.addrBits);
    delayMicroseconds(SETTLE_US);
    uint8_t data = readData(p.dataBits);
    checksum ^= data;

    // "ADDR: DATA": both zero-padded hex, fixed width per profile.
    char line[32];
    if (hexDigits == 1) {
      snprintf(line, sizeof(line), "%04lX: %01X", (unsigned long)addr, data);
    } else {
      snprintf(line, sizeof(line), "%04lX: %02X", (unsigned long)addr, data);
    }
    Serial.println(line);
  }

  Serial.print(F("Done. "));
  Serial.print(count);
  Serial.print(F(" addresses read. XOR checksum: "));
  Serial.println(checksum, HEX);

  Serial.print(F("DUMP_END,"));
  Serial.print(count);
  Serial.print(F(","));
  Serial.println(checksum, HEX);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { /* wait for USB serial */ }
  Serial.println(F("READY,ROM_DUMPER,1"));
  printMenu();
}

void loop() {
  if (!Serial.available()) return;
  char c = Serial.read();

  if (c >= '1' && c <= ('0' + NUM_PROFILES)) {
    currentProfile = c - '1';
    configurePins(PROFILES[currentProfile]);
    Serial.print(F("Selected: "));
    Serial.println(PROFILES[currentProfile].name);
  } else if (c == 'D' || c == 'd') {
    doDump();
  } else if (c == 'L' || c == 'l') {
    printProfileList();
  } else if (c == '\n' || c == '\r') {
    // ignore line endings
  } else {
    printMenu();
  }
}
