# KG-S88G CTCSS/DCS Encoding - SOLVED

## Solution Summary

The CTCSS/DCS encoding mystery has been solved. The key insight is the **XOR 0x55 encoding**.

### Encoding Format

Each tone uses 2 bytes: `[MODE_BYTE][INDEX_BYTE]`

Both bytes are XORed with 0x55 to get their actual values:
- `mode = MODE_BYTE ^ 0x55`
- `index = INDEX_BYTE ^ 0x55`

### Mode Values (after XOR)

| Mode | Value | Description |
|------|-------|-------------|
| OFF | 0 | No tone |
| CTCSS | 1 | Standard CTCSS tone |
| DCS-N | 2 | DCS Normal polarity |
| DCS-I | 3 | DCS Inverted polarity |

### Index Values (after XOR)

- **1-based index** into the tone/code list
- CTCSS: Index 1-38 maps to standard CTCSS frequencies
- DCS: Index 1-104 maps to standard DCS codes

### Encoding Examples

| Stored Bytes | Decoded | Meaning |
|--------------|---------|---------|
| `55 55` | mode=0, idx=0 | OFF |
| `54 54` | mode=1, idx=1 | CTCSS 67.0 Hz |
| `54 58` | mode=1, idx=13 | CTCSS 100.0 Hz |
| `54 73` | mode=1, idx=38 | CTCSS 192.8 Hz |
| `57 54` | mode=2, idx=1 | DCS D023N |
| `56 54` | mode=3, idx=1 | DCS D023I |
| `57 7E` | mode=2, idx=43 | DCS D251N |

### CTCSS Tone List (38 tones)

```
Index  Hz      Index  Hz      Index  Hz      Index  Hz
1      67.0    11     94.8    21     131.8   31     171.3
2      69.3    12     97.4    22     136.5   32     173.8
3      71.9    13     100.0   23     141.3   33     177.3
4      74.4    14     103.5   24     146.2   34     179.9
5      77.0    15     107.2   25     151.4   35     183.5
6      79.7    16     110.9   26     156.7   36     186.2
7      82.5    17     114.8   27     159.8   37     189.9
8      85.4    18     118.8   28     162.2   38     192.8
9      88.5    19     123.0   29     165.5
10     91.5    20     127.3   30     167.9
```

### DCS Code List (104 codes)

Standard DCS codes in order:
```
D023, D025, D026, D031, D032, D036, D043, D047, D051, D053,
D054, D065, D071, D072, D073, D074, D114, D115, D116, D122,
D125, D131, D132, D134, D143, D145, D152, D155, D156, D162,
D165, D172, D174, D205, D212, D223, D225, D226, D243, D244,
D245, D246, D251, D252, D255, D261, D263, D265, D266, D271,
D274, D306, D311, D315, D325, D331, D332, D343, D346, D351,
D356, D364, D365, D371, D411, D412, D413, D423, D431, D432,
D445, D446, D452, D454, D455, D462, D464, D465, D466, D503,
D506, D516, D523, D526, D532, D546, D565, D606, D612, D624,
D627, D631, D632, D654, D662, D664, D703, D712, D723, D731,
D732, D734, D743, D754
```

## Implementation Status

### Completed
- Frequency encoding/decoding (RX and TX)
- Channel name encoding/decoding
- CTCSS tone encoding/decoding (all 38 tones)
- DCS code encoding/decoding (Normal and Inverted polarity)
- OFF tone detection
- Channel settings (Power, Bandwidth, Busy Lock, Call ID, SP Mute, Descramble)
- CSV import/export
- Python CLI tools (read, write, list, export, import)
- ImHex patterns updated with tone decoding

### Known Limitations
- DCS code list: Radio may use 105 codes vs standard 104 (exact list around index 97-105 may need fine-tuning)

## Why Previous Analysis Was Confused

The old analysis tried to interpret the bytes as 2-digit hex strings using character encoding. This worked for low indices but failed for higher values because:
1. The mode byte was being combined with the index byte
2. The character encoding theory was an overcomplication of simple XOR

The actual solution is much simpler: just XOR each byte with 0x55.
