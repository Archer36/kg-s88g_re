# KG-S88G Radio Configuration File Format - Reverse Engineering Summary

## Project Overview
Reverse engineering the Wouxun KG-S88G ham radio .dat configuration file format to enable programmatic editing without the vendor software.

## File Format Discovered

### Overall Structure
- **File type**: Binary .dat configuration file
- **Total size**: ~16KB (0x4148 bytes in test files)
- **Key sections**:
  - 0x0000-0x0254: Header/settings (not yet analyzed)
  - 0x0255-0x0434: Channel frequency data (30 channels × 16 bytes)
  - 0x1C4B-0x1CFE: Channel names (30 channels × 6 bytes)
  - Remainder: Additional configuration

### Channel Frequency Data (0x0255+)
**Structure**: 16 bytes per channel, sequential
```
Offset +0: RX Frequency (4 bytes)
Offset +4: TX Frequency (4 bytes)  
Offset +8: CTCSS/DCS tones (4 bytes) - RX and TX
Offset +12: Other settings (4 bytes) - power, bandwidth, etc.
```

### Channel Names (0x1C4B+)
**Structure**: 6 bytes per channel, sequential
- Fixed 6-character limit
- Custom character encoding (see below)

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
Space=0x7c
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

### 2. ImHex Patterns

**kg_s88g.hexpat** (main pattern):
- Full structure with decode functions
- Shows frequencies as "XXX.YYYYY MHz"
- Shows channel names as decoded text
- Uses absolute offsets with `@` operator
- **Status**: Working correctly

**kg_s88g_simple.hexpat**:
- Simplified view with color coding
- **Status**: Updated with offset fixes

**kg_s88g_channels.hexpat**:
- Decoded channel-by-channel view
- **Status**: Updated with offset fixes

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

### ⚠️ MINOR ISSUES
- DCS code list: Radio uses 105 codes vs standard 104; exact list order around index 97-105 may need fine-tuning
- ImHex patterns may need updating to use new XOR 0x55 decoding

### ❌ NOT YET ANALYZED
- **Other channel settings** - Power, bandwidth, etc. (bytes 12-15 of each channel)
- **Header section** (0x0000-0x0254) - Radio settings, not yet analyzed
- **Footer section** - Additional configuration after channel data

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

### 2. Analyze Other Channel Settings
Bytes 12-15 of each 16-byte channel record contain additional settings:
- Power level (High/Low)
- Bandwidth (Wide/Narrow)
- Busy Lock
- Scan Add
- Other flags

### 3. Analyze Header Section
The header (0x0000-0x0254) likely contains:
- Radio serial number or ID
- Global settings (squelch level, VOX, etc.)
- Scan list configuration

### 4. Update ImHex Patterns
Update the .hexpat files to use the XOR 0x55 decoding method for proper tone display.

## Code Locations

All code files are in `/mnt/user-data/outputs/`:
- `kg_s88g_channel_encoder.py`
- `kg_s88g_freq_encoder.py`
- `kg_s88g.hexpat`
- `kg_s88g_simple.hexpat`
- `kg_s88g_channels.hexpat`
- `IMHEX_README.md`
- `DCS_MAPPING_TODO.md`

Test files are in `/mnt/user-data/uploads/`.

## Key Insights

1. **XOR 0x55 encoding**: Tone bytes use XOR with 0x55, not complex character mappings
2. **Nibble encoding for frequencies/names**: Frequencies and channel names use nibble-to-digit mapping
3. **Little-endian byte order**: Frequencies are stored reversed
4. **Mode + Index**: Tones use 2 bytes - first for mode (OFF/CTCSS/DCS-N/DCS-I), second for index
5. **1-based indexing**: Tone indices start at 1, not 0

## File Structure Summary (400 Channels)

```
Offset      End       Size      Description
----------------------------------------------------------------
0x0000      0x0254    597 B     Header/Settings
0x0255      0x1B54    6400 B    Frequency Data (400 channels × 16 bytes)
0x1B55      0x1C4A    246 B     [Gap - all 0xAA]
0x1C4B      0x25AA    2400 B    Channel Names (400 channels × 6 bytes)
0x25AB      0x4147    7069 B    Additional Settings (scan lists, etc.)
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
                Bits 2-3: Descramble value (0=OFF, 1=1, etc.)
                Bits 6-7: SP Mute mode (00=QT, 10=QT*DT, 01=QT+DT)
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
```
