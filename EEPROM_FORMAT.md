# KG-S88G Raw EEPROM Format

This document describes the raw EEPROM image as read from and written to the radio
over the USB programming cable. This is **distinct from the CPS `.dat` file format**
documented in `CPS_FORMAT.md`.

See `PROTOCOL.md` for how the EEPROM image is transferred. See `PCAP_ANALYSIS.md`
for how it was extracted from USB captures.

---

## Key Differences from CPS `.dat`

| Property | CPS `.dat` | EEPROM |
|----------|-----------|--------|
| Offset base | 0x0000 | 0x0000 |
| Offset relation | `EEPROM = CPS − 0x0145` | `CPS = EEPROM + 0x0145` |
| Settings encoding | XOR 0x55 on all settings bytes | Raw values, no XOR |
| Name encoding | Custom nibble/XOR map (A=0x5F…) | Compact encoding (A=0x0A…) |
| Frequency encoding | Custom nibble mapping, reversed | CHIRP `lbcd` (little-endian BCD) |
| File size | 16,712 bytes (0x4148) | 10,192 bytes (0x27D0) read by CHIRP |

---

## Overall EEPROM Structure

```
Offset      End       Size      Description
----------------------------------------------------------------
0x0000      0x000F    16 B      VFO Record (Frequency Mode)
0x0010      0x001F    16 B      (reserved / unknown)
0x0020      0x0071    82 B      Radio Settings
0x0072      0x00FF    ?         Unknown / padding
0x0100      0x1AFF    6656 B    Channel Records (memory[0..400], 16 B each)
                                  memory[0] unused, channels 1-400 at [1]..[400]
0x1B00      0x1CFF    512 B     Channel Names (names[0..400], 6 B each)
                                  names[0] unused, channels 1-400 at [1]..[400]
0x2500      0x2531    50 B      Channel Presence Bitmap (primary)
0x2600      0x2631    50 B      Channel Presence Bitmap (copy/mirror)
0x2680      0x26B2    51 B      Favorites Bitmap
0x2700      0x275F    96 B      CALL ID List (20 × 6 bytes)
0x2760      0x27CF    ?         Unknown / unanalyzed
----------------------------------------------------------------
Total read by CHIRP: 0x27D0 (10,192 bytes)
```

---

## VFO Record (0x0000–0x000F)

16 bytes, identical structure to a channel record. Used when the radio is in
Frequency (VFO) mode.

```
Offset  Size  Description
0x0000  4     RX Frequency (lbcd, little-endian BCD, 10 Hz units)
0x0004  4     TX Frequency (lbcd, little-endian BCD, 10 Hz units)
0x0008  1     RX Tone Mode (0=Off, 1=CTCSS, 2=DCS-N, 3=DCS-I)
0x0009  1     RX Tone Index (1-based)
0x000A  1     TX Tone Mode
0x000B  1     TX Tone Index (1-based)
0x000C  1     Settings A — bits: [7:6]=SP Mute, [5:2]=Descramble, [1]=unknown, [0]=Power
0x000D  1     Settings B — bits: [7:3]=Call ID, [2:1]=unknown, [0]=Busy Lock
0x000E  1     Settings C — bits: [7:1]=unknown, [0]=Wide (1=Wide, 0=Narrow)
0x000F  1     Settings D — reserved (unused)
```

Settings A bit fields:
- `highpower` bit 0: 0=Low (2W), 1=High (5W)
- `descramble` bits 2–5: 0=Off, 1–8
- `sp_mute` bits 6–7: 0=QT, 1=QT\*DT, 2=QT+DT

Settings B bit fields:
- `busy_lock` bit 0: 0=Off, 1=On
- `call_id` bits 3–7: 0–19 (1-based display: 1–20)

---

## Channel Records (0x0100–0x1AFF)

401 entries × 16 bytes. Entry 0 is unused; channels 1–400 are at entries 1–400.

**Channel N address**: `0x0100 + N × 16`  (N = 1–400)

Example: Channel 1 = `0x0110`, Channel 2 = `0x0120`, Channel 400 = `0x1A00`

Structure per channel (same as VFO above):
```
+0   4   lbcd rxfreq    — RX frequency, 10 Hz units
+4   4   lbcd txfreq    — TX frequency, 10 Hz units
+8   1   rx_tmode       — 0=Off 1=CTCSS 2=DCS-N 3=DCS-I
+9   1   rx_tone        — 1-based tone index
+10  1   tx_tmode
+11  1   tx_tone
+12  1   Settings A     — see VFO section
+13  1   Settings B     — see VFO section
+14  1   Settings C     — Bandwidth (bit 0: 1=Wide, 0=Narrow)
+15  1   Settings D     — reserved
```

**Empty channel**: all bytes `0xFF`

### Frequency Encoding (`lbcd`)

CHIRP's `lbcd` type stores frequency as little-endian packed BCD in units of 10 Hz.

Example: 462.5625 MHz = 46,256,250 Hz → in 10 Hz units = 4,625,625
- BCD digits: `0 4 6 2 5 6 2 5`
- Packed (2 digits/byte): `04 62 56 25`  → but lbcd reverses byte order
- Stored bytes: `25 56 62 04`

Decoding: reverse the 4 bytes, read each byte as two BCD digits, shift decimal after digit 3.

### Tone Encoding

Raw values (no XOR):
- tmode: 0=Off, 1=CTCSS, 2=DCS-N, 3=DCS-I
- tone: 1-based index into CTCSS list (38 tones) or DCS list

See `TONE_ENCODING.md` for full tone tables and the radio's DCS list (105 codes).

---

## Channel Names (0x1B00–0x1CFF)

401 entries × 6 bytes. Entry 0 unused; channels 1–400 at entries 1–400.

**Channel N name address**: `0x1B00 + N × 6`  (N = 1–400)

Example: Channel 1 = `0x1B06`, Channel 2 = `0x1B0C`

### EEPROM Name Character Encoding

Each byte encodes one character:

| Value | Character |
|-------|-----------|
| 0x00–0x09 | Digits '0'–'9' |
| 0x0A–0x23 | Letters 'A'–'Z' (A=0x0A, B=0x0B, …, Z=0x23) |
| 0x24 | Hyphen '-' |
| 0x29 | Space ' ' |
| 0xFF | Padding / end of name |

Names are padded to 6 bytes with `0xFF`. An empty/deleted name is all `0xFF`.

**Note**: This encoding is completely different from the CPS `.dat` name encoding.
The CPS uses a custom nibble/XOR map (A=0x5F, etc.). Do not confuse the two.

**Example**: "GMRS01"
```
G=0x10  M=0x16  R=0x1B  S=0x1C  0=0x00  1=0x01
→ bytes: 10 16 1B 1C 00 01
```

---

## Radio Settings (0x0020–0x0071)

All values are raw — **no XOR 0x55** (unlike CPS `.dat`).

```
Offset  Size  Setting           Values
------  ----  -------           ------
0x0020  1     squelch           0–9
0x0021  1     vfo_step          0=2.5K 1=5K 2=6.25K 3=8.33K 4=10K 5=12.5K 6=25K 7=50K 8=100K
0x0022  1     pf_top_long       1–13 (PF function index, see table below)
0x0023  1     beep              0=Off 1=On
0x0024  1     battery_save      0=Off 1=On
0x0025  1     (unknown)
0x0026  1     voice             0=Off 2=On  (note: 2, not 1)
0x0027  1     (unknown)
0x0028  1     tot               0=Off 1–60 (×15 s: 1=15s … 60=900s)
0x0029  1     pf_top_short      1–13
0x002A  1     pf2_long          1–13
0x002B  1     (unknown)
0x002C  1     auto_lock         0=Off 1–6 (×10 s: 1=10s … 6=60s)
0x002D  1     work_mode         0=Freq 1=Ch/Freq 2=Ch/Num 3=Ch/Name
0x002E  1     scan_mode         0=CO 1=TO 2=SE
0x002F  1     (unknown)
0x0030  1     startup_display   0=Message 1=Voltage
0x0031  1     (unknown)
0x0032  1     roger             0=Off 1=BOT 2=EOT 3=Both
0x0033  1     (unknown)
0x0034  1     backlight         0=Off 1–30 31=Always
0x0035  1     repeater          0=Off 1=On  (VFO repeater offset enable)
0x0036  2     active_channel    1–400 (ul16, little-endian)
0x0038  4     (unknown)
0x003C  1     vox               0=Off 1–9
0x003D  1     toa               0=Off 1–10  (overtime alarm)
0x003E  1     (unknown)
0x003F  1     sidetone          0=Off 1=DT-ST 2=ANI-ST 3=DT+ANI
0x0040  1     ptt_id            0=Off 1=BOT 2=EOT 3=Both
0x0041  4     (unknown)
0x0045  2     priority_channel  1–400 (ul16, little-endian)
0x0047  1     id_dly            1–30 (×100 ms: 1=100ms … 30=3000ms)
0x0048  1     ring              0=Off 1–10 (seconds)
0x0049  1     (unknown)
0x004A  1     lock_mode         0=Key 1=Key+PTT 2=Key+Enc 3=Key+All
0x004B  1     alert_tone        0=1000Hz 1=1450Hz 2=1750Hz 3=2100Hz
0x004C  1     vox_delay         1–5 (seconds)
0x004D  1     tone_save         0=RX 1=TX 2=TX+RX
0x004E  1     priority_scan     0=Off 1=On
0x004F  1     call_reset        0–60 (seconds)
0x0050  3     (unknown)
0x0053  1     pf1_short         1–13
0x0054  1     pf1_long          1–13
0x0055  1     pf2_short         1–13
0x0056  1     scan_qt           0=Off 1=On
0x0057  7     startup_msg       7-char name (EEPROM encoding, padded with 0xFF)
0x005E  2     (unknown)
0x0060  4     id_control        Up to 3 digits + 0x0F terminator (EEPROM encoding)
0x0064  2     (unknown)
0x0066  1     dtmf_tx_time      0–45 (50 + n×10 ms: 0=50ms … 45=500ms)
0x0067  1     dtmf_interval     0–45 (50 + n×10 ms)
0x0068  1     (unknown)
0x0069  1     be_control        0=Off 1=On
0x006A  4     id_edit           Up to 3 digits + 0x0F terminator (EEPROM encoding)
0x006E  2     (unknown)
0x0070  1     timer             0=Off 1=On  (⚠ needs hardware verification)
0x0071  1     rpt_rct           0=Off 1=On  (⚠ needs hardware verification)
```

### PF Button Function Index

| Index | Function  | Index | Function  |
|-------|-----------|-------|-----------|
| 1     | Scan      | 8     | Monitor   |
| 2     | Backlight | 9     | Reverse   |
| 3     | VOX       | 10    | WorkMode  |
| 4     | TX Power  | 11    | Alarm     |
| 5     | Call      | 12    | SOS       |
| 6     | Talk-Around | 13  | Favorite  |
| 7     | Flashlight |      |           |

Stock PF button assignments:

| Button   | EEPROM | Stock Value |
|----------|--------|-------------|
| TOP Long | 0x0022 | 10 (WorkMode) |
| TOP Short | 0x0029 | 13 (Favorite) |
| PF2 Long | 0x002A | 8 (Monitor) |
| PF1 Short | 0x0053 | 1 (Scan) |
| PF1 Long | 0x0054 | 4 (TX Power) |
| PF2 Short | 0x0055 | 7 (Flashlight) |

### ID-EDIT and ID Control Text Encoding

These 4-byte fields store up to 3 decimal digits followed by a terminator byte (`0x0F`).
Digits use the same EEPROM encoding (0='0x00', 1=0x01, …, 9=0x09). The terminator
byte in EEPROM encoding is `0x0F` (which would be the letter 'F' if treated as a
character, since 'F' = 0x0A + 5 = 0x0F). Unused trailing positions are `0x0F`.

Example: "101" stored as `01 00 01 0F`

---

## Channel Presence Bitmaps (0x2500 and 0x2600)

Two identical 50-byte bitmaps. The radio uses these to track which channel slots
are occupied. If a channel's bit is not set here, the radio ignores it even if
frequency data exists in the channel record.

**Bit assignment**: Channel N (1-based) uses bit `N % 8` of byte `N // 8`.

Example: Channel 1 → byte 0, bit 1. Channel 8 → byte 1, bit 0.

The CHIRP driver recomputes these bitmaps from actual channel data on every upload.
Both 0x2500 and 0x2600 receive the same value (mirror copy).

---

## Favorites Bitmap (0x2680–0x26B2)

51 bytes. Each bit marks a channel as a Favorite (accessible via the FAVORITE
PF button function).

**Bit assignment**: Channel N (1-based) uses bit `(N-1) % 8` of byte `(N-1) // 8`.

Example: Channel 1 → byte 0, bit 0. Channel 9 → byte 1, bit 0.

The bitmap supports all 400 channels (50 bytes needed; 51 bytes allocated).

Stock image observation: byte 2, bit 3 is set → channel 19 is a favorite
(GMRS repeater channel 19 = 462.6125 MHz).

---

## CALL ID List (0x2700–0x275F)

20 entries × 6 bytes each.

| Entry | Offset | Channel |
|-------|--------|---------|
| 1 | 0x2700 | CALL ID 1 |
| 2 | 0x2706 | CALL ID 2 |
| … | … | … |
| 20 | 0x274E | CALL ID 20 |

Each entry is 6 bytes using EEPROM name encoding (digits 0x00–0x09, padded with 0xFF).
Empty entries are all `0xFF`.

---

## Known Unknowns

- **0x0072–0x00FF**: Purpose unknown. Likely padding or additional settings.
- **0x0025, 0x0027, 0x002B, 0x002F, 0x0031, 0x0033, 0x003E, 0x0041–0x0044, 0x0049**: Individual unknown bytes within settings struct.
- **0x2760–0x27CF**: Unanalyzed tail of the read region.
- **Timer (0x0070) / RPT RCT (0x0071)**: Mapped from PCAP comparison but behavior
  unconfirmed on hardware. The CPS documentation suggests these may interact.
- **Multiple favorites**: When multiple channels are marked as favorites, pressing
  the FAVORITE PF button cycles through them in order. Confirmed on hardware.
