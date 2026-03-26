# KG-S88G Radio Settings Quick Reference

Side-by-side lookup table for every known setting, with both CPS `.dat` and EEPROM
offsets, value ranges, and stock defaults.

**CPS ↔ EEPROM offset formula**: `EEPROM_offset = CPS_offset − 0x0145`

CPS values use **XOR 0x55** encoding. EEPROM values are **raw** (no XOR).

---

## Optional Features / General Settings

| Setting | CPS Offset | EEPROM Offset | Values | Stock Default |
|---------|-----------|---------------|--------|---------------|
| Squelch | 0x0165 | 0x0020 | 0–9 | 5 |
| VFO Step | 0x0166 | 0x0021 | 0=2.5K 1=5K 2=6.25K 3=8.33K 4=10K 5=12.5K 6=25K 7=50K 8=100K | — |
| TOP Long (PF button) | 0x0167 | 0x0022 | 1–13 (function index) | 10 (WorkMode) |
| Beep | 0x0168 | 0x0023 | 0=Off 1=On | 1 |
| Battery Save | 0x0169 | 0x0024 | 0=Off 1=On | 1 |
| Voice | 0x016B | 0x0026 | 0=Off **2**=On (not 1) | 2 |
| TOT (Time Out Timer) | 0x016D | 0x0028 | 0=Off 1–60 (×15s: 1=15s…60=900s) | varies |
| TOP Short (PF button) | 0x016E | 0x0029 | 1–13 | 13 (Favorite) |
| PF2 Long (PF button) | 0x016F | 0x002A | 1–13 | 8 (Monitor) |
| Auto Lock | 0x0171 | 0x002C | 0=Off 1–6 (×10s: 1=10s…6=60s) | varies |
| Work Mode | 0x0172 | 0x002D | 0=Freq 1=Ch/Freq 2=Ch/Num 3=Ch/Name | 3 |
| Scan Mode | 0x0173 | 0x002E | 0=CO 1=TO 2=SE | varies |
| Startup Display | 0x0175 | 0x0030 | 0=Message 1=Voltage | varies |
| Roger | 0x0177 | 0x0032 | 0=Off 1=BOT 2=EOT 3=Both | 0 |
| Backlight | 0x0179 | 0x0034 | 0=Off 1–30 31=Always | varies |
| Repeater (VFO) | 0x017A | 0x0035 | 0=Off 1=On | 0 |
| Active Channel | 0x017B–0x017C | 0x0036–0x0037 | 1–400 (**ul16**, little-endian) | varies |
| VOX | 0x0181 | 0x003C | 0=Off 1–9 | 0 |
| Overtime Alarm (TOA) | 0x0182 | 0x003D | 0=Off 1–10 | 0 |
| Priority Channel | 0x018A–0x018B | 0x0045–0x0046 | 1–400 (**ul16**, little-endian) | varies |
| Lock Mode | 0x018F | 0x004A | 0=Key 1=Key+PTT 2=Key+Enc 3=Key+All | varies |
| Alert Tone | 0x0190 | 0x004B | 0=1000Hz 1=1450Hz 2=1750Hz 3=2100Hz | varies |
| VOX Delay | 0x0191 | 0x004C | 1–5 (seconds) | varies |
| Tone Save | 0x0192 | 0x004D | 0=RX 1=TX 2=TX+RX | varies |
| Priority Scan | 0x0193 | 0x004E | 0=Off 1=On | varies |
| SCAN-QT | 0x019B | 0x0056 | 0=Off 1=On | varies |
| Startup Message | 0x019C–0x01A2 | 0x0057–0x005D | 7 chars (name encoding) | "KG-S88G" |
| Timer | 0x01B5 | 0x0070 | 0=Off 1=On | ⚠ unverified |
| RPT RCT | 0x01B6 | 0x0071 | 0=Off 1=On | ⚠ unverified |

### Notes
- **Active Channel** and **Priority Channel** are 2-byte little-endian values in both CPS and EEPROM.
  The CPS documentation previously listed these as single-byte, which was incorrect.
- **Voice** uses the value 2 for On (not 1). Value 1 is not a valid setting.
- **Timer / RPT RCT** at 0x01B5/0x01B6 (CPS) have been mapped to EEPROM 0x0070/0x0071,
  but their exact behavior has not been verified on hardware.

---

## DTMF Settings

| Setting | CPS Offset | EEPROM Offset | Values | Stock Default |
|---------|-----------|---------------|--------|---------------|
| Sidetone | 0x0184 | 0x003F | 0=Off 1=DT-ST 2=ANI-ST 3=DT+ANI | 3 |
| PTT-ID | 0x0185 | 0x0040 | 0=Off 1=BOT 2=EOT 3=Both | 0 |
| ID DLY | 0x018C | 0x0047 | 1–30 (×100ms: 1=100ms…30=3000ms) | 10 (1000ms) |
| Ring | 0x018D | 0x0048 | 0=Off 1–10 (seconds) | 5 |
| Call Reset | 0x0194 | 0x004F | 0–60 (seconds) | 10 |
| DTMF TX Time | 0x01AB | 0x0066 | 0–45 (50+n×10ms: 0=50ms…45=500ms) | 5 (100ms) |
| DTMF Interval | 0x01AC | 0x0067 | 0–45 (50+n×10ms) | 5 (100ms) |
| Be Control | 0x01AE | 0x0069 | 0=Off 1=On | 1 |
| ID Control | 0x01A5–0x01A8 | 0x0060–0x0063 | 4 bytes: up to 3 digits + terminator | "101" |
| ID-EDIT | 0x01AF–0x01B2 | 0x006A–0x006D | 4 bytes: up to 3 digits + terminator | "101" |

### ID-EDIT / ID Control Encoding

Stored as up to 3 decimal digit bytes followed by a terminator byte (`0x0F`).
In EEPROM encoding: digits 0–9 = values 0x00–0x09; terminator = 0x0F.
In CPS encoding: same character map as channel names, with 'F' (0x5A) as terminator.

---

## PF Button Functions

| Index | Function | Index | Function |
|-------|----------|-------|----------|
| 1 | Scan | 8 | Monitor |
| 2 | Backlight | 9 | Reverse |
| 3 | VOX | 10 | WorkMode |
| 4 | TX Power | 11 | Alarm |
| 5 | Call | 12 | SOS |
| 6 | Talk-Around | 13 | Favorite |
| 7 | Flashlight | | |

| Button | CPS Offset | EEPROM Offset | Stock Value |
|--------|-----------|---------------|-------------|
| TOP Long | 0x0167 | 0x0022 | 10 (WorkMode) |
| TOP Short | 0x016E | 0x0029 | 13 (Favorite) |
| PF2 Long | 0x016F | 0x002A | 8 (Monitor) |
| PF1 Short | 0x0198 | 0x0053 | 1 (Scan) |
| PF1 Long | 0x0199 | 0x0054 | 4 (TX Power) |
| PF2 Short | 0x019A | 0x0055 | 7 (Flashlight) |

---

## VFO / Frequency Mode Record

The VFO record is at CPS `0x0145` / EEPROM `0x0000`. It uses the same 16-byte
structure as a channel record. See `EEPROM_FORMAT.md` for field layout.

Additional VFO-specific settings in the general settings area:

| Setting | CPS Offset | EEPROM Offset | Values |
|---------|-----------|---------------|--------|
| VFO Step | 0x0166 | 0x0021 | 0=2.5K…8=100K |
| Repeater | 0x017A | 0x0035 | 0=Off 1=On |

---

## Per-Channel Settings

Each channel record (16 bytes) contains these settings:

| Field | Offset | Bits | Values |
|-------|--------|------|--------|
| RX Frequency | +0 | 32 | lbcd, 10 Hz units |
| TX Frequency | +4 | 32 | lbcd, 10 Hz units |
| RX Tone Mode | +8 | 8 | 0=Off 1=CTCSS 2=DCS-N 3=DCS-I |
| RX Tone Index | +9 | 8 | 1-based |
| TX Tone Mode | +10 | 8 | 0=Off 1=CTCSS 2=DCS-N 3=DCS-I |
| TX Tone Index | +11 | 8 | 1-based |
| Power | +12 | bit 0 | 0=Low(2W) 1=High(5W) |
| Descramble | +12 | bits 2–5 | 0=Off 1–8 |
| SP Mute | +12 | bits 6–7 | 0=QT 1=QT\*DT 2=QT+DT |
| Busy Lock | +13 | bit 0 | 0=Off 1=On |
| Call ID | +13 | bits 3–7 | 0–19 (display as 1–20) |
| Bandwidth | +14 | bit 0 | 0=Narrow 1=Wide |

---

## Special EEPROM Regions

| Region | Offset | Size | Description |
|--------|--------|------|-------------|
| Channel presence bitmap | 0x2500 | 50 B | Bit per channel; radio ignores channels not marked here |
| Channel presence bitmap (copy) | 0x2600 | 50 B | Mirror of 0x2500 |
| Favorites bitmap | 0x2680 | 51 B | Bit per channel; marks favorites for FAVORITE PF button |
| CALL ID list | 0x2700 | 120 B | 20 × 6 bytes, EEPROM name encoding |

### Favorites Bitmap Bit Assignment

Channel N (1-based): bit `(N-1) % 8` of byte `(N-1) // 8`

Example: CH1 → byte 0 bit 0; CH8 → byte 0 bit 7; CH9 → byte 1 bit 0

### Channel Presence Bitmap Bit Assignment

Channel N (1-based): bit `N % 8` of byte `N // 8`

Example: CH1 → byte 0 bit 1; CH8 → byte 1 bit 0

---

## CALL ID List

20 entries at EEPROM `0x2700`, CPS `0x2845`. Each entry is 6 bytes using EEPROM
name encoding (digits 0x00–0x09, padded with 0xFF). All 0xFF = empty entry.

| Entry | EEPROM Offset | CPS Offset |
|-------|--------------|------------|
| CALL ID 1 | 0x2700 | 0x2845 |
| CALL ID 2 | 0x2706 | 0x284B |
| … | … | … |
| CALL ID 20 | 0x274E | 0x28C4 |

---

## Unknown / Unverified Settings

| EEPROM Offset | Observation |
|--------------|-------------|
| 0x0025 | Unknown; changes with some settings |
| 0x0027 | Unknown |
| 0x002B | Unknown |
| 0x002F | Unknown |
| 0x0031 | Unknown |
| 0x0033 | Unknown |
| 0x003E | Unknown |
| 0x0041–0x0044 | Unknown (4 bytes) |
| 0x0049 | Unknown |
| 0x0050–0x0052 | Unknown (3 bytes) |
| 0x005E–0x005F | Unknown (2 bytes) |
| 0x0064–0x0065 | Unknown (2 bytes) |
| 0x0068 | Unknown |
| 0x006E–0x006F | Unknown (2 bytes) |
| 0x0070 | Timer — mapped but not hardware-verified |
| 0x0071 | RPT RCT — mapped but not hardware-verified |
| 0x2760–0x27CF | Unanalyzed tail region |
