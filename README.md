# KG-S88G Reverse Engineering

Reverse engineering of the Wouxun KG-S88G GMRS handheld radio — covering the
vendor CPS file format, raw EEPROM layout, USB programming protocol, and a
working CHIRP driver.

---

## What's Here

The radio stores its configuration in an internal EEPROM. This can be accessed
two ways: through the vendor CPS software (which works with `.dat` save files)
or directly over USB (which the CHIRP driver does). Both represent the same
underlying data but with different encodings and address spaces.

---

## Documentation

### Formats

| Document | Description |
|----------|-------------|
| [CPS_FORMAT.md](CPS_FORMAT.md) | Vendor CPS `.dat` file format — offsets, encodings, channel structure, all settings |
| [EEPROM_FORMAT.md](EEPROM_FORMAT.md) | Raw radio EEPROM layout as accessed over USB — differs from CPS in offsets and encoding |
| [TONE_ENCODING.md](TONE_ENCODING.md) | CTCSS/DCS encoding for both formats; the radio's 105-code DCS list and how it differs from the standard 104 |
| [RADIO_SETTINGS_REFERENCE.md](RADIO_SETTINGS_REFERENCE.md) | Side-by-side lookup table of every setting with CPS offset, EEPROM offset, value range, and stock default |

### Protocol

| Document | Description |
|----------|-------------|
| [PROTOCOL.md](PROTOCOL.md) | USB programming protocol — physical connector pinout, handshake sequence, rolling XOR cipher, read/write packet format |
| [PCAP_ANALYSIS.md](PCAP_ANALYSIS.md) | How the protocol was reverse-engineered — capture methodology, tshark extraction, Ghidra disassembly, cipher cracking |

### CHIRP Driver

| Document | Description |
|----------|-------------|
| [CHIRP_DRIVER.md](CHIRP_DRIVER.md) | Developer notes for the CHIRP driver — architecture, memory map, settings groups, per-channel extras, known limitations |

---

## Key Findings

- **CPS ↔ EEPROM offset**: `EEPROM = CPS − 0x0145`
- **CPS encoding**: all settings bytes use XOR 0x55; custom nibble map for names and frequencies
- **EEPROM encoding**: raw values (no XOR); compact name encoding (A=0x0A…); CHIRP `lbcd` for frequencies
- **USB protocol**: rolling XOR stream cipher; key = `km[1] XOR km[3]` from 16-byte handshake key material; byte 0 of each packet is plaintext
- **DCS**: radio uses 105 codes (D463N instead of D464N, plus extra D645N); CHIRP driver uses standard 104
- **Logic level**: 3.3V CMOS (HIGH measured at 3.278V); 2.5mm TRS ring = Radio TX, 3.5mm TRS sleeve = Radio RX

---

## Tools

### Python Scripts

| Script | Description |
|--------|-------------|
| `pcap_to_img.py` | Convert a KG-S88G USB capture (`.pcapng`) to a CHIRP-compatible `.img` file |
| `kg_s88g_freq_encoder.py` | Encode/decode frequencies and tones; read/write channels in CPS `.dat` files |
| `kg_s88g_channel_encoder.py` | Encode/decode channel names in CPS `.dat` files |
| `LA Dumps/merge_la.py` | Merge PC-TX and RDO-TX logic analyser dumps; decrypt and annotate the byte stream |

### ImHex Patterns (`ImHex Patterns/`)
Three patterns for parsing CPS `.dat` files in ImHex. See `ImHex Patterns/IMHEX_README.md`.

### 010 Editor Templates (`010 Editor Templates/`)
Template for parsing CPS `.dat` files in 010 Editor. See `010 Editor Templates/README.md`.

### CHIRP Driver
[`chirp/drivers/kg_s88g.py`](https://github.com/Archer36/chirp/blob/wouxun-kg-s88g/chirp/drivers/kg_s88g.py) in a fork of the CHIRP repository. Supports full read/write,
all settings, and per-channel extras (Busy Lock, Favorite, Call ID, SP Mute, Descramble).

---

## Repository Layout

```
CPS_FORMAT.md                  CPS .dat file format reference
EEPROM_FORMAT.md               Raw EEPROM layout reference
PROTOCOL.md                    USB programming protocol
PCAP_ANALYSIS.md               Protocol reverse-engineering methodology
TONE_ENCODING.md               CTCSS/DCS encoding and code lists
RADIO_SETTINGS_REFERENCE.md    All settings, both address spaces, side-by-side
CHIRP_DRIVER.md                CHIRP driver developer notes
kg_s88g_freq_encoder.py        CPS frequency/tone/channel tool
kg_s88g_channel_encoder.py     CPS channel name tool
ImHex Patterns/                ImHex .hexpat files for CPS .dat
010 Editor Templates/          010 Editor .bt template for CPS .dat
LA Dumps/                      Logic analyser captures and merge script
Test Saves/                    CPS .dat test files used during RE
Screenshots/                   Reference screenshots
OEM/                           OEM documentation and software
```
