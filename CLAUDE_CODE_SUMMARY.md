# KG-S88G Radio Configuration File Format - Reverse Engineering Summary

## Project Overview
Reverse engineering the Wouxun KG-S88G ham radio .dat configuration file format to enable programmatic editing without the vendor software.

## File Format Discovered

### Overall Structure
- **File type**: Binary .dat configuration file
- **Total size**: 16712 bytes (0x4148)
- **Channels**: 400 total
- **Key sections**:
  - 0x0000-0x0144: Header start
  - 0x0145-0x0154: VFO Record (16 bytes)
  - 0x0155-0x0254: Header (Optional Features, DTMF Settings)
  - 0x0255-0x1B54: Channel Frequency Data (400 × 16 bytes)
  - 0x1B55-0x1C4A: Gap (0xAA padding)
  - 0x1C4B-0x25AA: Channel Names (400 × 6 bytes)
  - 0x25AB-0x27C4: Additional Settings
  - 0x27C5-0x27F7: Favorites Bitmap (51 bytes)
  - 0x27F8-0x2844: Gap
  - 0x2845-0x28C2: CALL ID List (20 × 6 bytes)
  - 0x28C3-0x4147: Remaining Configuration

### Channel Frequency Data (0x0255+)
**Structure**: 16 bytes per channel, sequential
```
Offset +0:  RX Frequency (4 bytes, nibble-encoded BCD, little-endian)
Offset +4:  TX Frequency (4 bytes, nibble-encoded BCD, little-endian)
Offset +8:  RX Tone Mode (1 byte, XOR 0x55)
Offset +9:  RX Tone Index (1 byte, XOR 0x55)
Offset +10: TX Tone Mode (1 byte, XOR 0x55)
Offset +11: TX Tone Index (1 byte, XOR 0x55)
Offset +12: Settings A - Power/Descramble/SP Mute (XOR 0x55)
Offset +13: Settings B - Busy Lock/Call ID (XOR 0x55)
Offset +14: Settings C - Bandwidth (XOR 0x55)
Offset +15: Settings D - Reserved (XOR 0x55)
```

### Channel Names (0x1C4B+)
**Structure**: 6 bytes per channel, sequential
- Fixed 6-character limit
- Custom character encoding (see below)
- Padded with 0x7C (space), empty channels marked with 0xAA

## Encoding Schemes Discovered

### 1. Custom Character Encoding (Used for Channel Names)
Each byte encodes one character using a proprietary mapping:

**Letters A-Z**:
```
A=0x5f, B=0x5e, C=0x59, D=0x58, E=0x5b, F=0x5a, G=0x45, H=0x44, I=0x47, J=0x46,
K=0x41, L=0x40, M=0x43, N=0x42, O=0x4d, P=0x4c, Q=0x4f, R=0x4e, S=0x49, T=0x48,
U=0x4b, V=0x4a, W=0x75, X=0x74, Y=0x77, Z=0x76
```

**Digits 0-9**:
```
0=0x55, 1=0x54, 2=0x57, 3=0x56, 4=0x51, 5=0x50, 6=0x53, 7=0x52, 8=0x5d, 9=0x5c
```

**Special**:
```
Space=0x7c, Hyphen=0x71, F(terminator)=0x5a, Empty=0xAA
```

### 2. Nibble-to-Digit Mapping (Used for Frequencies and Tones)
Each nibble (4 bits) encodes one decimal digit:
```
Nibble → Digit
0x5 → 0
0x4 → 1
0x7 → 2
0x6 → 3
0x1 → 4
0x0 → 5
0x3 → 6
0x2 → 7
0xD → 8
0xC → 9
```

### 3. Frequency Encoding (4 bytes)
**Format**: XXX.YYYYY MHz (8 digits total)

**Algorithm**:
1. Store frequency as 8-digit string (e.g., 462.56250 → "46256250")
2. Convert each digit using nibble mapping above
3. Pack nibbles into 4 bytes (2 digits per byte)
4. **Reverse byte order** (little-endian)

**Example**: 462.56250 MHz
```
Digits:  4 6 2 5 6 2 5 0
Nibbles: 1 3 7 0 3 7 0 5
Bytes:   0x13 0x70 0x37 0x05
Stored:  05 37 70 13  (reversed)
```

**Decoding**:
1. Reverse the 4 bytes
2. Extract all 8 nibbles
3. Map each nibble to digit
4. Insert decimal point after 3rd digit

### 4. CTCSS/DCS Encoding (4 bytes) - COMPLETE

**Format**: `[RX_MODE][RX_IDX][TX_MODE][TX_IDX]`

**Algorithm (XOR 0x55 Encoding)**:
Each byte is XORed with 0x55 to get the actual value.

**Mode Byte** (byte XOR 0x55):
- `0` = OFF
- `1` = CTCSS
- `2` = DCS-N (Normal polarity)
- `3` = DCS-I (Inverted polarity)

**Index Byte** (byte XOR 0x55):
- 1-based index into CTCSS_TONES or DCS_CODES list

**CTCSS Tones** (38 standard tones, index 1-38):
```python
CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,  # 01-10
    94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,  # 11-20
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,  # 21-30
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8  # 31-38
]
```

**DCS Codes** (104-105 codes, index 1-105):
The radio appears to use 105 DCS codes (one more than the standard 104).
Standard list order: D023, D025, D026, D031... through D754

**Encoding Examples**:
```
OFF:     55 55 → mode=0x55^0x55=0, idx=0x55^0x55=0 → OFF
67.0 Hz: 54 54 → mode=0x54^0x55=1, idx=0x54^0x55=1 → CTCSS[0]=67.0
100.0:   54 58 → mode=0x54^0x55=1, idx=0x58^0x55=13 → CTCSS[12]=100.0
192.8:   54 73 → mode=0x54^0x55=1, idx=0x73^0x55=38 → CTCSS[37]=192.8
D023N:   57 54 → mode=0x57^0x55=2, idx=0x54^0x55=1 → DCS-N[0]=D023
D023I:   56 54 → mode=0x56^0x55=3, idx=0x54^0x55=1 → DCS-I[0]=D023
D251N:   57 7E → mode=0x57^0x55=2, idx=0x7E^0x55=43 → DCS-N[42]=D251
```

**Note**: The radio's DCS code list order differs slightly from standard lists around index 97-105. D703 appears at index 98 instead of 97, and D754 at index 105 instead of 104, suggesting an extra code is included.

## Tools Created

### 1. Python Scripts

**kg_s88g_channel_encoder.py**:
- Encode/decode channel names
- Read/write channel names from/to .dat files
- CLI: `encode`, `decode`, `read`, `write`

**kg_s88g_freq_encoder.py**:
- Encode/decode frequencies
- Encode/decode CTCSS tones (partial DCS support)
- Read/write frequencies and tones
- CLI: `encode`, `decode`, `read`, `write`, `list`
- **Current limitation**: DCS codes show as CTCSS frequencies

### 2. ImHex Patterns (in `ImHex Patterns/`)

**kg_s88g.hexpat** (main pattern):
- Full structure with decode functions
- Shows frequencies as "XXX.YYYYY MHz"
- Shows channel names as decoded text
- VFO Record with decoded values
- Optional Features settings (27+ settings)
- DTMF Settings (Sidetone, PTT-ID, ID DLY, etc.)
- CALL ID list (20 entries)
- Channel settings with Descramble display
- **Status**: Complete

**kg_s88g_simple.hexpat**:
- Simplified view with color coding
- VFO Record section
- CALL ID list section
- **Status**: Complete

**kg_s88g_channels.hexpat**:
- Decoded channel-by-channel view
- VFO Record with decoded values
- CALL IDs with decoded digits
- Settings show Power/Bandwidth/Descramble
- **Status**: Complete

### 3. 010 Editor Templates (in `010 Editor Templates/`)

**kg_s88g.bt**:
- Complete template with all features
- Frequency decoding (displays as "XXX.YYYYY MHz")
- Channel name and CALL ID decoding
- CTCSS/DCS tone decoding
- Channel settings with Descramble display
- VFO Record
- Color-coded sections
- **Status**: Complete

## Files Provided by User

1. **stock.dat** - Original radio configuration (GMRS channels 1-22)
2. **1-912345.dat** - Test file with frequencies 100-900 MHz + 123.45625
3. **ct-codes.dat** - Test file with CTCSS CH1-15, DCS CH16-20, OFF CH21
4. **Various test files** - For validating encoding schemes

## Current Status

### ✅ COMPLETE
- Frequency encoding/decoding (RX and TX)
- Channel name encoding/decoding
- CTCSS tone encoding/decoding (all 38 tones)
- DCS code encoding/decoding (Normal and Inverted polarity)
- OFF tone detection
- Python CLI tools functional (encode, decode, read, write, list)
- Channel settings (Power, Bandwidth, Descramble, SP Mute, Busy Lock, Call ID)
- Optional Features settings (Squelch, VOX, TOT, Beep, etc.)
- Frequency Mode / VFO settings
- DTMF Settings (Sidetone, PTT-ID, ID DLY, Ring, Call Reset, TX/Interval Time)
- ID-EDIT and ID Control text fields
- CALL ID list (20 entries at 0x2845+)

### ⚠️ MINOR ISSUES
- DCS code list: Radio uses 105 codes vs standard 104; exact list order around index 97-105 may need fine-tuning
- DTMF read-only fields (Kill, Stun, Monitor, Inspection, Free) location not determined - these are grayed out in the software

### ❌ NOT YET ANALYZED
- **Footer section** - Remaining configuration after 0x28C3

## SOLVED: CTCSS/DCS Encoding

The DCS encoding mystery has been solved! The key insight is the **XOR 0x55 encoding**:

### The Solution
Each tone uses 2 bytes: `[MODE_BYTE][INDEX_BYTE]`

Both bytes are XORed with 0x55 to get their actual values:
- `mode = MODE_BYTE ^ 0x55` → 0=OFF, 1=CTCSS, 2=DCS-N, 3=DCS-I
- `index = INDEX_BYTE ^ 0x55` → 1-based index into tone/code list

### Why Previous Analysis Was Confused
The old analysis tried to interpret the bytes as 2-digit hex strings using character encoding. This worked for low indices but failed for higher values because:
1. The mode byte was being combined with the index byte
2. The character encoding theory was an overcomplication of simple XOR

### Verification
All CTCSS tones (1-38), DCS-N codes, and DCS-I codes now decode correctly.
Mixed RX/TX configurations work properly.

## Potential Future Work

### 1. Fine-tune DCS Code List
The radio uses 105 DCS codes instead of standard 104. Need to determine the exact extra code and its position (likely around index 97).

### 2. Analyze Remaining Footer Section
The area from 0x28C3 to 0x4147 (6277 bytes) has not been fully analyzed. May contain:
- Scan list configuration
- Additional radio settings
- Reserved/unused space

### 3. DTMF Read-Only Fields
Determine where Kill, Stun, Monitor, Inspection, and Free DTMF codes are stored (if at all - they may be hardcoded in firmware).

### ✅ COMPLETED
- ~~Analyze Other Channel Settings~~ - Power, Bandwidth, Descramble, SP Mute, Busy Lock, Call ID all mapped
- ~~Analyze Header Section~~ - Optional Features, VFO, DTMF Settings all mapped
- ~~Update ImHex Patterns~~ - All three patterns updated with complete settings

## Code Locations

All code files are in the project root:
- `kg_s88g_channel_encoder.py` - Channel name encoding/decoding
- `kg_s88g_freq_encoder.py` - Full channel read/write with CSV import/export

ImHex Patterns (in `ImHex Patterns/`):
- `kg_s88g.hexpat` - Main ImHex pattern
- `kg_s88g_simple.hexpat` - Simplified pattern
- `kg_s88g_channels.hexpat` - Channel-focused pattern
- `IMHEX_README.md` - ImHex usage documentation

010 Editor Templates (in `010 Editor Templates/`):
- `kg_s88g.bt` - Main 010 Editor template
- `README.md` - 010 Editor usage documentation

Test files are in `Test Saves/` folder.

## Key Insights

1. **XOR 0x55 encoding**: All settings bytes use XOR with 0x55, not complex character mappings
2. **Nibble encoding for frequencies/names**: Frequencies and channel names use nibble-to-digit mapping
3. **Little-endian byte order**: Frequencies are stored reversed
4. **Mode + Index**: Tones use 2 bytes - first for mode (OFF/CTCSS/DCS-N/DCS-I), second for index
5. **1-based indexing**: Tone indices start at 1, not 0
6. **VFO mirrors channel structure**: VFO record at 0x0145 uses identical encoding to channel records
7. **Character encoding reuse**: CALL IDs, ID-EDIT, ID Control all use same encoding as channel names
8. **Bit-packed settings**: Settings A byte packs Power (bit 0), Descramble (bits 2-5), SP Mute (bits 6-7)

## File Structure Summary (400 Channels)

```
Offset      End       Size      Description
----------------------------------------------------------------
0x0000      0x0144    325 B     Header Start
0x0145      0x0154    16 B      VFO Record (Frequency Mode settings)
0x0155      0x0164    16 B      Header (continued)
0x0165      0x01B5    81 B      Optional Features & DTMF Settings
0x01B6      0x0254    159 B     Header (continued)
0x0255      0x1B54    6400 B    Channel Frequency Data (400 × 16 bytes)
0x1B55      0x1C4A    246 B     Gap (filled with 0xAA)
0x1C4B      0x25AA    2400 B    Channel Names (400 × 6 bytes)
0x25AB      0x27C4    538 B     Additional Settings
0x27C5      0x27F7    51 B      Favorites Bitmap
0x27F8      0x2844    77 B      Gap
0x2845      0x28C2    120 B     CALL ID List (20 × 6 bytes)
0x28C3      0x4147    6277 B    Remaining Configuration (not fully analyzed)
----------------------------------------------------------------
Total                 16712 B   (0x4148)
```

### Per-Channel Frequency Record (16 bytes)
```
Offset  Size  Description
+0      4     RX Frequency (nibble-encoded, little-endian)
+4      4     TX Frequency (nibble-encoded, little-endian)
+8      1     RX Tone Mode (XOR 0x55: 0=OFF, 1=CTCSS, 2=DCS-N, 3=DCS-I)
+9      1     RX Tone Index (XOR 0x55: 1-based index)
+10     1     TX Tone Mode (XOR 0x55)
+11     1     TX Tone Index (XOR 0x55)
+12     1     Settings A (XOR 0x55):
                Bit 0: Power (1=High, 0=Low)
                Bits 2-5: Descramble (0=OFF, 1-8)
                Bits 6-7: SP Mute mode (0=QT, 1=QT*DT, 2=QT+DT)
+13     1     Settings B (XOR 0x55):
                Bit 0: Busy Lock (0=OFF, 1=ON)
                Bits 3-7: Call ID (value = byte >> 3)
+14     1     Settings C (XOR 0x55):
                Bit 0: Bandwidth (1=Wide, 0=Narrow)
+15     1     Settings D (XOR 0x55): Reserved/unused (always 0x00)
```

### Favorites Bitmap (at 0x27C5, 51 bytes)
Bitmask for 400 channels. Each bit indicates if that channel is a favorite.
- Bit 1 of byte 0 = Channel 1
- Bit N of byte B = Channel (B*8 + N), adjusted for 1-indexing

### Per-Channel Name Record (6 bytes)
Fixed 6-character name using custom character encoding.
Padded with space (0x7C) if shorter than 6 characters.

### Empty Channel Marker
Unused channels are filled with 0xAA bytes.

## Optional Features (Header Section 0x0165-0x01B5)

All optional feature settings use **XOR 0x55 encoding**: `actual_value = stored_byte ^ 0x55`

### Confirmed Settings

| Offset | Setting | Values | Verified By |
|--------|---------|--------|-------------|
| 0x0165 | Squelch | 0-9 | sett-sql9 |
| 0x0167 | TOP Long (PF button) | 1-13 function index | everythingchanged |
| 0x0168 | BEEP | 0=OFF, 1=ON | sett-beep-off |
| 0x0169 | Battery Save | 0=OFF, 1=ON | sett-batterysave-off |
| 0x016B | Voice | 0=OFF, 2=ON | sett-voice-off |
| 0x016D | TOT (Time Out Timer) | 0=OFF, 1-60 (15s steps: 1=15s... 60=900s) | sett-tot15s |
| 0x016E | TOP Short (PF button) | 1-13 function index | everythingchanged |
| 0x016F | PF2 Long (PF button) | 1-13 function index | everythingchanged |
| 0x0171 | Auto Lock | 0=OFF, 1-6 (10s steps: 1=10s... 6=60s) | sett-autolock-20s |
| 0x0172 | Work Mode | 0=Freq, 1=Ch/Freq, 2=Ch/Num, 3=Ch/Name | sett-workmode-* |
| 0x0173 | Scan Mode | 0=CO, 1=TO, 2=SE | sett-scanmode-co |
| 0x0175 | Startup Display | 0=Message, 1=Voltage | sett-startupdisplay-voltage |
| 0x0177 | Roger | 0=OFF, 1=BOT, 2=EOT, 3=BOTH | sett-roger-* |
| 0x0179 | Backlight Control | 0=OFF, 1-30=level, 31=ALWAYS | sett-backlight-always |
| 0x017B | Active Channel | 1-400 (channel number) | sett-activechannel-5 |
| 0x0181 | VOX | 0=OFF, 1-9 | sett-vox-5 |
| 0x0182 | Overtime Alarm (TOA) | 0=OFF, 1-10 | sett-overtimealarm-1 |
| 0x018A | Priority Channel | 1-400 (channel number) | sett-prioritychannel-5 |
| 0x018F | Lock Mode | 0=KEY, 1=KEY+PTT, 2=KEY+ENC, 3=KEY+ALL | sett-lockmode-* |
| 0x0190 | Alert Tone | 0=1000Hz, 1=1450Hz, 2=1750Hz, 3=2100Hz | sett-alerttone-* |
| 0x0191 | VOX Delay | 1=1S, 2=2S, 3=3S, 4=4S, 5=5S (0=OFF?) | sett-voxdelay-5s |
| 0x0192 | Tone Save | 0=RX, 1=TX, 2=Both TX&RX | sett-tonesave-both |
| 0x0193 | Priority Scan | 0=OFF, 1=ON | sett-priorityscan-on |
| 0x0198 | PF1 Short (PF button) | 1-13 function index | everythingchanged |
| 0x0199 | PF1 Long (PF button) | 1-13 function index | everythingchanged |
| 0x019A | PF2 Short (PF button) | 1-13 function index | everythingchanged |
| 0x019B | SCAN-QT | 0=OFF, 1=ON | sett-scanqt-on |
| 0x019C-0x01A2 | Startup Message | 7 characters (same encoding as channel names) | everythingchanged |
| 0x01B5 | Timer / RPT RCT | See note below | sett-timer-on, sett-rptrct-off |

**Note on 0x01B5 (Timer/RPT RCT):** This byte appears to control both Timer and RPT RCT settings. When Timer is enabled OR RPT RCT is disabled, this byte changes from 0 to 1. They may be mutually exclusive or use combined logic.

### PF Button Function Index (1-indexed)

| Index | Function |
|-------|----------|
| 1 | SCAN |
| 2 | BACK-LT |
| 3 | VOX |
| 4 | TX Power |
| 5 | CALL |
| 6 | TALK-A |
| 7 | FLASHLT |
| 8 | MONITOR |
| 9 | REVERSE |
| 10 | WORKMODE |
| 11 | ALARM |
| 12 | SOS |
| 13 | FAVORITE |

### PF Button Locations Summary

| Offset | Button | Stock Value |
|--------|--------|-------------|
| 0x0167 | TOP Long | 10 (WORKMODE) |
| 0x016E | TOP Short | 13 (FAVORITE) |
| 0x016F | PF2 Long | 8 (MONITOR) |
| 0x0198 | PF1 Short | 1 (SCAN) |
| 0x0199 | PF1 Long | 4 (TX Power) |
| 0x019A | PF2 Short | 7 (FLASHLT) |

### Unknown
| Offset | Stock→Changed | Notes |
|--------|---------------|-------|
| 0x0178 | 0→1 | Purpose unclear |
| 0x0174 | 1→0 | Changes with Work Mode=Frequency |

## Frequency Mode Settings (VFO)

Settings for when the radio is in VFO/Frequency mode (not channel mode).

### VFO Record (0x0145-0x0154)

| Offset | Size | Description |
|--------|------|-------------|
| 0x0145 | 4 | RX Frequency (same encoding as channels) |
| 0x0149 | 4 | TX Frequency (same encoding as channels) |
| 0x014D | 4 | Tones: RX Mode, RX Index, TX Mode, TX Index (XOR 0x55) |
| 0x0151 | 1 | Settings A: Power (bit 0), Descramble (bits 2-5: 0=OFF, 1-8), SP Mute (bits 6-7) |
| 0x0152 | 1 | Settings B: Busy Lock (bit 0), Call ID (bits 3-7) |
| 0x0153 | 1 | Settings C: Bandwidth (bit 0: 1=Wide, 0=Narrow) |
| 0x0154 | 1 | Settings D: Reserved |

### VFO-Specific Settings

| Offset | Setting | Values | Verified By |
|--------|---------|--------|-------------|
| 0x0166 | Step | 0=2.5K, 1=5K, 2=6.25K, 3=8.33K, 4=10K, 5=12.5K, 6=25K, 7=50K, 8=100K | sett-vfo-step-25k |
| 0x017A | Repeater | 0=OFF, 1=ON | sett-vfo-repeater-on |

**Note:** The VFO uses the same encoding for frequencies, tones, and settings as channel records:
- Power: bit 0 (0=Low, 1=High)
- Descramble: bits 2-5 (0=OFF, 1-8)
- SP Mute: bits 6-7 (0=QT, 1=QT*DT, 2=QT+DT)
- Busy Lock: bit 0 of next byte (0=OFF, 1=ON)
- Call ID: bits 3-7 of next byte (1-20)
- Bandwidth: bit 0 of next byte (0=Narrow, 1=Wide)

## DTMF Settings (0x0184-0x01B4 and 0x2845+)

Settings for DTMF signaling, ID codes, and Call ID lists.

### Dropdown Settings (XOR 0x55 encoded)

| Offset | Setting | Values | Stock | Verified By |
|--------|---------|--------|-------|-------------|
| 0x0184 | Sidetone | 0=OFF, 1=DT-ST, 2=ANI-ST, 3=DT+ANI | 3 (DT+ANI) | dtmf-sidetone-off |
| 0x0185 | PTT-ID | 0=OFF, 1=BOT, 2=EOT, 3=BOTH | 0 (OFF) | dtmf-pttid-bot |
| 0x018C | ID DLY | 1-30 (value × 100 = MS, range 100MS-3000MS) | 10 (1000MS) | dtmf-iddly-100ms |
| 0x018D | Ring | 0=Off, 1-10 (value = seconds, range 1S-10S) | 5 (5S) | dtmf-ring-off |
| 0x0194 | Call Reset Time | 0-60 (value = seconds, range 0S-60S) | 10 (10S) | dtmf-callreset-0s |
| 0x01AB | DTMF TX Time | 0-45 (50 + value × 10 = MS, range 50MS-500MS) | 5 (100MS) | dtmf-txtime-50ms |
| 0x01AC | DTMF Interval Time | 0-45 (50 + value × 10 = MS, range 50MS-500MS) | 5 (100MS) | dtmf-interval-50ms |

### Checkbox Settings (XOR 0x55 encoded)

| Offset | Setting | Values | Stock | Verified By |
|--------|---------|--------|-------|-------------|
| 0x01AE | Be Control | 0=unchecked, 1=checked | 1 (checked) | dtmf-becontrol-off |

### Text Fields (channel name encoding)

| Offset | Size | Setting | Format | Stock |
|--------|------|---------|--------|-------|
| 0x01A5-0x01A8 | 4 | ID Control | Up to 3 digits + 'F' terminator | "101F" |
| 0x01AF-0x01B2 | 4 | ID-EDIT | Up to 3 digits + 'F' terminator | "101F" |

**Encoding**: Uses same character encoding as channel names. 'F' (0x5A) is used as terminator.

### CALL ID List (0x2845+, 20 entries × 6 bytes)

| Offset | Setting |
|--------|---------|
| 0x2845-0x284A | CALL ID1 |
| 0x284B-0x2850 | CALL ID2 |
| 0x2851-0x2856 | CALL ID3 |
| ... | ... |
| 0x28B7-0x28BC | CALL ID19 |
| 0x28BD-0x28C2 | CALL ID20 |

**Encoding**: Uses same character encoding as channel names. Each ID is 6 bytes.
- Empty IDs are filled with 0xAA
- Unused positions padded with 0x7C (space)
- Example: "12345" encodes as: 54 57 56 51 50 7C

### Read-Only Fields (grayed out in software)

These fields are displayed but not editable in the programming software:
- Kill: AB
- Stun: CB
- Monitor: DA
- Inspection: DB
- Free: AD

Location in file: TBD (hardcoded or protected area)

## Quick Reference

**Decode frequency bytes**:
```python
bytes([0x05, 0x37, 0x70, 0x13]) → reverse → extract nibbles → map → "462.56250"
```

**Decode channel name**:
```python
bytes([0x45, 0x43, 0x4e, 0x49, 0x55, 0x54]) → map each byte → "GMRS01"
```

**Decode tone (XOR 0x55)**:
```python
# OFF:     55 55 → mode=0, idx=0 → OFF
# CTCSS:   54 54 → mode=1, idx=1 → 67.0 Hz
# DCS-N:   57 54 → mode=2, idx=1 → D023N
# DCS-I:   56 54 → mode=3, idx=1 → D023I
```

**CLI Usage**:
```bash
# List all channels
python kg_s88g_freq_encoder.py list radio.dat

# Read single channel
python kg_s88g_freq_encoder.py read radio.dat 1

# Encode a frequency
python kg_s88g_freq_encoder.py encode 462.5625

# Clear a single channel
python kg_s88g_freq_encoder.py clear radio.dat 5

# Clear a range of channels
python kg_s88g_freq_encoder.py clear radio.dat 10-20
```
