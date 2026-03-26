# KG-S88G CHIRP Driver

Developer notes for the Wouxun KG-S88G CHIRP driver.

---

## File Location

https://github.com/Archer36/chirp/blob/wouxun-kg-s88g/chirp/drivers/kgs88g.py

---

## Installation / Development

For development, place the driver file in CHIRP's `chirp/drivers/` directory.
The driver is auto-discovered by CHIRP's `@directory.register` decorator — no
other registration is needed.

To load in CHIRP:
1. Start CHIRP
2. Connect the KG-S88G via USB programming cable
3. Radio → Download From Radio → select port → Wouxun KG-S88G

The radio is marked `ExperimentalRadio`. Users will see a warning when first
using it; this is expected for in-development drivers.

---

## Driver Architecture

The driver follows CHIRP's standard `CloneModeRadio` pattern:
- `do_download()`: Runs the handshake then reads EEPROM in 16-byte blocks
- `do_upload()`: Runs the handshake then writes EEPROM in 16-byte blocks
- `get_memory()` / `set_memory()`: Convert between CHIRP's `Memory` objects and
  the EEPROM bitwise struct
- `get_settings()` / `set_settings()`: Expose radio global settings as a
  `RadioSettings` tree with groups

### Key Classes and Functions

| Name | Purpose |
|------|---------|
| `RollingXOR` | Rolling XOR stream cipher (encrypt/decrypt with shared key state) |
| `_do_handshake()` | 8-step handshake; returns initialized `RollingXOR` and echo flag |
| `_send()` | Byte-at-a-time serial write with 2 ms inter-byte delay |
| `_decode_name()` | EEPROM name bytes → ASCII string |
| `_encode_name()` | ASCII string → EEPROM name bytes |
| `_tone_to_setting_idx()` | Convert (tmode, 1-based index) to VFO tone list position |
| `_setting_idx_to_tone()` | Convert VFO tone list position to (tmode, 1-based index) |
| `KGS88GRadio` | Main radio class |

---

## Memory Map (MEM_FORMAT)

The driver uses CHIRP's `bitwise` parser with the following layout:

| Struct | Address | Description |
|--------|---------|-------------|
| `vfo` | 0x0000 | VFO / Frequency Mode record (16 bytes) |
| `memory[401]` | 0x0100 | Channel records; `memory[0]` unused, channels 1–400 at `[1]–[400]` |
| `names[401]` | 0x1B00 | Channel names; `names[0]` unused, channels 1–400 at `[1]–[400]` |
| `settings` | 0x0020 | Radio global settings struct (see below) |
| `favorites` | 0x2680 | 51-byte favorites bitmap |
| `callids[20]` | 0x2700 | CALL ID list (20 × 6 bytes) |

**Memory image size**: 0x27D0 bytes (10,192 bytes), defined by `_memsize`.

---

## Channel Encoding

### Frequency

CHIRP's `lbcd` type (little-endian packed BCD) in 10 Hz units. Handled
transparently by the `bitwise` parser — no manual conversion needed.

### Tone Mode and Index

The EEPROM uses raw values (no XOR):
- `tmode`: 0=Off, 1=CTCSS, 2=DCS-N, 3=DCS-I

The driver maps these to CHIRP's `tmode` strings using:
```python
TMODES = ["", "Tone", "DTCS", "DTCS"]
```

For DCS, polarity is stored in the `tmode` field (2=N, 3=I) rather than a
separate field. This is handled in `get_memory()` / `set_memory()`.

### Name Encoding

EEPROM uses a compact encoding (A=0x0A, digits=0x00–0x09, space=0x29, etc.)
that is distinct from the CPS `.dat` encoding. See `EEPROM_FORMAT.md`.

The `_decode_name()` and `_encode_name()` functions handle this encoding.

---

## Channel Presence Bitmaps

The radio maintains bitmaps at EEPROM 0x2500 and 0x2600 indicating which channel
slots contain valid data. Channels not marked in these bitmaps are silently ignored
by the radio firmware, even if frequency data is present.

On every upload, `do_upload()` recomputes both bitmaps from the actual channel data
before writing. A channel is considered active if its RX frequency bytes are neither
all-0xFF (empty) nor all-0x00.

---

## Settings Groups

`get_settings()` returns a `RadioSettings` with these groups:

| Group | Label | Key Settings |
|-------|-------|--------------|
| `basic` | Basic | Squelch, Beep, Voice, Backlight, Work Mode, Startup Display/Message, Roger, Scan Mode |
| `timers` | Timers | TOT, TOA, Auto Lock |
| `scan` | Scan | Scan Mode, Scan QT, Priority Scan, Priority Channel |
| `audio` | Audio | Alert Tone, Sidetone, Roger |
| `lock` | Lock | Lock Mode, Active Channel |
| `vox` | VOX | VOX level, VOX Delay |
| `pfkeys` | PF Keys | All 6 PF button assignments |
| `dtmf` | DTMF | PTT-ID, ID DLY, Ring, Call Reset, TX Time, Interval, Be Control, ID-EDIT, CALL ID 1–20 |
| `vfo` | Frequency Mode | VFO frequency, Tones (RX/TX), Power, Bandwidth, Busy Lock, SP Mute, Descramble, Call ID, Repeater, Step |
| `options` | Options | Timer, RPT RCT |

### RadioSettingValueList Usage

All list settings use the `current_index=` keyword argument to avoid
`FutureWarning` from CHIRP's settings API:

```python
RadioSettingValueList(LIST_X, current_index=idx)
```

### Tooltips

All settings have tooltips set via `set_doc()`, displayed as hover help in
CHIRP's settings UI.

---

## Per-Channel Extra Settings

In addition to standard channel fields, the driver exposes per-channel settings
via `mem.extra` (shown as the "Extra" tab in CHIRP's channel editor):

| Setting | Type | Description |
|---------|------|-------------|
| `busy_lock` | Boolean | Busy channel lockout |
| `call_id` | List (1–20) | DTMF Call ID assignment |
| `sp_mute` | List | SP Mute mode (QT / QT\*DT / QT+DT) |
| `descramble` | List | Descrambler (Off, 1–8) |
| `favorite` | Boolean | Mark channel as a Favorite |

These are read in `get_memory()` and written back in `set_memory()`.

The `favorite` field reads/writes the bit at position `(ch-1) % 8` of
byte `(ch-1) // 8` in the 51-byte favorites bitmap at EEPROM 0x2680.

---

## Special Cases in set_settings()

- **Voice**: Stored as 0 (Off) or 2 (On) — not 0/1.
- **PF keys**: 1-indexed in lists, stored 1-indexed in EEPROM.
- **VOX Delay**: 1-indexed (list[0] = "1S" = EEPROM value 1).
- **ID DLY**: 1-indexed (list[0] = "100MS" = EEPROM value 1).
- **VFO Frequency**: Setting TX = RX (simplex) since only one frequency field is exposed.
- **VFO Tones**: Uses `_setting_idx_to_tone()` to split the combined list index
  back to (tmode, 1-based tone index).
- **ID-EDIT / ID Control**: Apply callbacks strip trailing 'F' for display and
  re-add the `0x0F` terminator byte when saving.
- **CALL IDs**: Apply callbacks use closure `idx=i` to correctly capture loop variable.

---

## Known Limitations and TODO

### DCS Code List Mismatch

The radio uses 105 DCS codes; the driver uses the standard 104-code list
(`chirp_common.DTCS_CODES`). Two codes are unavailable via CHIRP:

- **D463N** (radio index 77): CHIRP maps index 77 to D464N instead.
- **D645N** (radio index 94): Not in CHIRP's list at all.

For GMRS operation this has no practical impact. A future improvement could
define a custom 105-code list for this radio.

### Timer and RPT RCT

Mapped to EEPROM 0x0070 and 0x0071 based on CPS offset comparison. Behavior
confirmed by PCAP but exact radio interaction not hardware-verified. The CPS
documentation suggests these may interact (they may be mutually exclusive).

### Multiple Favorites

The favorites bitmap supports marking multiple channels as favorites. When multiple
channels are marked, pressing the FAVORITE PF button cycles through them in order.
Confirmed on hardware.

### Channels Above 255 (Active/Priority Channel)

`active_channel` and `priority_channel` are stored as `ul16` (little-endian 16-bit)
at EEPROM 0x0036 and 0x0045. The CHIRP driver exposes these as an `Integer` widget
with range 1–400. Values above 255 have not been hardware-tested.

### Test Image

No test image has been added to `tests/images/` yet. A stock EEPROM image should
be committed as `tests/images/Wouxun_KG-S88G.img` for the CHIRP test suite.

---

## Debugging Tips

- Set `logging.DEBUG` level for `chirp.drivers.kgs88g` to see handshake bytes,
  cipher key, and per-block address progress.
- The CHIRP driver deliberately uses `data_phase_key = 0x00` (all-zero key material)
  so captured sessions are trivially decryptable — XOR with 0x00 is a no-op for
  the first encrypted byte.
- If the handshake fails after 5 attempts, check: cable connected, radio powered on,
  correct COM port, radio in programming mode (auto on cable connect).
- Echo mode is detected automatically; no user configuration needed.
