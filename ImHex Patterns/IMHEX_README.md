# KG-S88G ImHex Patterns

ImHex patterns for analyzing and editing Wouxun KG-S88G radio configuration files (.dat format).

## Files Included

### 1. `kg_s88g.hexpat` - Full Pattern
The complete pattern with detailed structure definitions, including:
- Full frequency decoding with transformation functions
- Complete channel name character mapping
- CTCSS/DCS tone decoding (XOR 0x55 method)
- Channel settings (Power, Bandwidth, Busy Lock, Call ID)
- Support for all 400 channels

**Best for**: Understanding the complete file format, learning the encoding scheme

### 2. `kg_s88g_simple.hexpat` - Simplified Pattern
A cleaner version focusing on the essential structures:
- Channel frequency data (16 bytes per channel)
- Channel names (6 bytes per channel)
- Color-coded fields (RX/TX/Settings)
- Less verbose, easier to navigate

**Best for**: Everyday editing and analysis

### 3. `kg_s88g_channels.hexpat` - Decoded View
Shows channels with decoded values in an easy-to-read format:
- Displays actual MHz values (e.g., "462.56250 MHz")
- Shows decoded channel names (e.g., "GMRS01")
- Each channel is a single collapsible item

**Best for**: Quick viewing of channel configuration

## Usage

1. Open your KG-S88G .dat file in ImHex
2. Go to `View` > `Pattern Editor` (or press `Ctrl+E`)
3. Click `File` > `Load Pattern` and select one of the .hexpat files
4. The pattern will automatically parse and display the decoded information

## File Format Overview

### File Structure (16712 bytes total)
```
Offset      End       Size      Description
----------------------------------------------------------------
0x0000      0x0254    597 B     Header/Radio Settings
0x0255      0x1B54    6400 B    Channel Frequency Data (400 x 16 bytes)
0x1B55      0x1C4A    246 B     Gap (filled with 0xAA)
0x1C4B      0x25AA    2400 B    Channel Names (400 x 6 bytes)
0x25AB      0x27C4    537 B     Additional Settings
0x27C5      0x27F7    51 B      Favorites Bitmap
0x27F8      0x4147    6480 B    Remaining Configuration
```

### Per-Channel Frequency Record (16 bytes)
```
Offset  Size  Description
+0      4     RX Frequency (nibble-encoded BCD, little-endian)
+4      4     TX Frequency (nibble-encoded BCD, little-endian)
+8      1     RX Tone Mode (XOR 0x55: 0=OFF, 1=CTCSS, 2=DCS-N, 3=DCS-I)
+9      1     RX Tone Index (XOR 0x55: 1-based index)
+10     1     TX Tone Mode (XOR 0x55)
+11     1     TX Tone Index (XOR 0x55)
+12     1     Settings A (XOR 0x55): Power(bit0), Descramble(bits2-3), SP Mute(bits6-7)
+13     1     Settings B (XOR 0x55): Busy Lock(bit0), Call ID(bits3-7)
+14     1     Settings C (XOR 0x55): Bandwidth(bit0: 1=Wide, 0=Narrow)
+15     1     Settings D (XOR 0x55): Reserved
```

### Frequency Encoding
- **4 bytes per frequency** (RX or TX)
- **Little-endian** byte order (reversed)
- **Custom nibble mapping**: Each nibble encodes one BCD digit
  - `5->0, 4->1, 7->2, 6->3, 1->4, 0->5, 3->6, 2->7, D->8, C->9`
- **Format**: `XXX.YYYYY` MHz (8 digits total)

**Example**: 462.56250 MHz
```
Digits:  4 6 2 5 6 2 5 0
Nibbles: 1 3 7 0 3 7 0 5
Bytes:   13 70 37 05
Stored:  05 37 70 13  (reversed/little-endian)
```

### CTCSS/DCS Tone Encoding
- **2 bytes per tone**: `[MODE_BYTE][INDEX_BYTE]`
- **XOR 0x55**: Both bytes are XORed with 0x55 to get actual values
- **Mode values** (after XOR):
  - 0 = OFF
  - 1 = CTCSS
  - 2 = DCS Normal (N)
  - 3 = DCS Inverted (I)
- **Index**: 1-based into CTCSS (1-38) or DCS (1-104) list

**Examples**:
```
55 55 -> mode=0, idx=0 -> OFF
54 54 -> mode=1, idx=1 -> CTCSS 67.0 Hz
54 58 -> mode=1, idx=13 -> CTCSS 100.0 Hz
57 54 -> mode=2, idx=1 -> DCS D023N
56 54 -> mode=3, idx=1 -> DCS D023I
```

### Channel Name Encoding
- **6 bytes per name**
- **Custom character map** for A-Z, 0-9, space, and hyphen
- Each byte encodes exactly one character
- Unused positions padded with `0x7c` (space)
- Empty channels marked with `0xAA`

**Example**: "GMRS01" encodes as: `45 43 4e 49 55 54`

## Editing Tips

1. **To change a frequency**:
   - Locate the channel's frequency bytes
   - Convert your desired frequency to the encoded format
   - Or use the Python script: `kg_s88g_freq_encoder.py`

2. **To change a channel name**:
   - Locate the channel name bytes (starts at 0x1C4B)
   - Use the character map to encode your desired name
   - Or use the Python script: `kg_s88g_channel_encoder.py`

3. **After editing**:
   - Save the file
   - Upload to radio using official programming software
   - Verify changes on the radio

## Related Tools

- `kg_s88g_freq_encoder.py` - Full channel read/write with CSV import/export
- `kg_s88g_channel_encoder.py` - Channel name encoding/decoding

### CLI Examples
```bash
# List all channels
python kg_s88g_freq_encoder.py list radio.dat -n 30

# Read single channel with all settings
python kg_s88g_freq_encoder.py read radio.dat 1

# Write channel with all options
python kg_s88g_freq_encoder.py write radio.dat 1 --rx 462.5625 --tx 462.5625 \
    --rx-tone 67.0 --tx-tone D023N --power High --bandwidth Wide --name "GMRS01"

# Export to CSV
python kg_s88g_freq_encoder.py export radio.dat channels.csv -n 30

# Import from CSV
python kg_s88g_freq_encoder.py import channels.csv radio.dat

# Clear a single channel
python kg_s88g_freq_encoder.py clear radio.dat 5

# Clear a range of channels
python kg_s88g_freq_encoder.py clear radio.dat 10-20
```

## Character Encoding Reference

### Letters
```
A=5f B=5e C=59 D=58 E=5b F=5a G=45 H=44 I=47 J=46
K=41 L=40 M=43 N=42 O=4d P=4c Q=4f R=4e S=49 T=48
U=4b V=4a W=75 X=74 Y=77 Z=76
```

### Digits
```
0=55 1=54 2=57 3=56 4=51 5=50 6=53 7=52 8=5d 9=5c
```

### Special
```
Space=7c  Hyphen=71  Empty=AA
```

## Frequency Nibble Mapping
```
Nibble -> Digit
  5    ->   0
  4    ->   1
  7    ->   2
  6    ->   3
  1    ->   4
  0    ->   5
  3    ->   6
  2    ->   7
  D    ->   8
  C    ->   9
```

## Notes

- The KG-S88G uses the **same nibble encoding** for both channel names (byte-level) and frequencies (nibble-level)
- All multi-byte values use **little-endian** (LSB first) byte order
- Channel numbering is **1-based** (Channel 1 starts at offset 0x0255)
- The radio supports **400 channels** total
- Empty channels are marked with **0xAA** bytes
- Tone and settings bytes use **XOR 0x55** encoding

## Credits

Reverse engineered through comparative analysis of multiple .dat files with known configurations.
