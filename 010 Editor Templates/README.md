# KG-S88G 010 Editor Templates

010 Editor binary templates for analyzing Wouxun KG-S88G radio configuration files (.dat format).

## Files

### `kg_s88g.bt`
Complete template with:
- Frequency decoding (displays as "XXX.YYYYY MHz")
- Channel name decoding
- CTCSS/DCS tone decoding
- Channel settings (Power, Bandwidth, Descramble, Busy Lock, Call ID)
- VFO Record
- CALL ID list (20 entries)
- Color-coded sections

## Usage

1. Open your KG-S88G .dat file in 010 Editor
2. Go to `Templates` > `Open Template...` (or press `Ctrl+F5`)
3. Select `kg_s88g.bt`
4. Click `Run Template` (or press `F5`)

The template will parse the file and display decoded values in the Template Results panel.

## Color Coding

| Color | Section |
|-------|---------|
| Green | Frequencies |
| Cyan | Tones |
| Magenta | Settings |
| Yellow | Channel Names |
| Light Green | CALL IDs |
| Orange | VFO Record |
| Gray | Header/Gaps |

## Notes

- All settings use XOR 0x55 encoding
- Frequencies use nibble-to-digit mapping with little-endian byte order
- Channel names and CALL IDs use custom character encoding (also XOR 0x55 based)
- Empty channels/entries are marked with 0xAA bytes
