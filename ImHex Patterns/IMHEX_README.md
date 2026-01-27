# KG-S88G ImHex Patterns

ImHex patterns for analyzing and editing Wouxun KG-S88G radio configuration files (.dat format).

## Files Included

### 1. `kg_s88g.hexpat` - Full Pattern
The complete pattern with detailed structure definitions, including:
- Full frequency decoding with transformation functions
- Complete channel name character mapping
- All file sections labeled
- Helper functions for encoding/decoding

**Best for**: Understanding the complete file format, learning the encoding scheme

### 2. `kg_s88g_simple.hexpat` - Simplified Pattern
A cleaner version focusing on the essential structures:
- Channel frequency data (16 bytes per channel)
- Channel names (6 bytes per channel)
- Color-coded fields (RX/TX/Settings)
- Less verbose, easier to navigate

**Best for**: Everyday editing and analysis

### 3. `kg_s88g_channels.hexpat` - Decoded View
Shows all 30 channels with decoded values in an easy-to-read format:
- Displays actual MHz values (e.g., "462.56250 MHz")
- Shows decoded channel names (e.g., "GMRS01")
- Each channel is a single collapsible item
- No raw hex, just human-readable values

**Best for**: Quick viewing of channel configuration

## Usage

1. Open your KG-S88G .dat file in ImHex
2. Go to `View` → `Pattern Editor` (or press `Ctrl+E`)
3. Click `File` → `Load Pattern` and select one of the .hexpat files
4. The pattern will automatically parse and display the decoded information

## File Format Overview

### Frequency Encoding
- **4 bytes per frequency** (RX or TX)
- **Little-endian** byte order (reversed)
- **Custom nibble mapping**: Each nibble encodes one BCD digit
  - `5→0, 4→1, 7→2, 6→3, 1→4, 0→5, 3→6, 2→7, D→8, C→9`
- **Format**: `XXX.YYYYY` MHz (8 digits total)

**Example**: 462.56250 MHz
```
Digits:  4 6 2 5 6 2 5 0
Nibbles: 1 3 7 0 3 7 0 5
Bytes:   13 70 37 05
Stored:  05 37 70 13  (reversed/little-endian)
```

### Channel Name Encoding
- **6 bytes per name**
- **Custom character map** for A-Z, 0-9, and space
- Each byte encodes exactly one character
- Unused positions padded with `0x7c` (space)

**Example**: "GMRS01" encodes as: `45 43 4e 49 55 54`

### File Structure
```
0x0000 - 0x0254: Header and radio settings
0x0255 - 0x03D4: Channel frequency data (30 channels × 16 bytes)
                 Each channel: [RX(4)] [TX(4)] [Tones(4)] [Settings(4)]
0x03D5 - 0x1C4A: Additional configuration data
0x1C4B - 0x1CFF: Channel names (30 channels × 6 bytes)
0x1D00 - EOF:    Remaining configuration
```

### Per-Channel Layout (16 bytes)
```
+0x00: RX Frequency (4 bytes)
+0x04: TX Frequency (4 bytes)
+0x08: CTCSS/DCS Tones (4 bytes)
+0x0C: Settings (Power, Bandwidth, etc.) (4 bytes)
```

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

- `kg_s88g_freq_encoder.py` - Python CLI for encoding/decoding frequencies
- `kg_s88g_channel_encoder.py` - Python CLI for encoding/decoding channel names

Both scripts can read/write .dat files directly and provide easier command-line access for batch operations.

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
Space=7c
```

## Frequency Nibble Mapping
```
Nibble → Digit
  5    →   0
  4    →   1
  7    →   2
  6    →   3
  1    →   4
  0    →   5
  3    →   6
  2    →   7
  D    →   8
  C    →   9
```

## Notes

- The KG-S88G uses the **same nibble encoding** for both channel names (byte-level) and frequencies (nibble-level)
- All multi-byte values use **little-endian** (LSB first) byte order
- Channel numbering is **1-based** (Channel 1 starts at offset 0x0255)
- The radio supports **30 channels** total

## Credits

Reverse engineered through comparative analysis of multiple .dat files with known configurations.
