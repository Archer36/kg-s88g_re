# KG-S88G CTCSS/DCS Encoding - Status and Next Steps

## What We've Discovered

### Encoding Format
- **4 bytes per channel**: `[RX_MSB][RX_LSB][TX_MSB][TX_LSB]`
- **Character encoding**: Uses the same character map as channel names and frequencies
- **2-byte pairs**: Each pair forms a 2-digit hex index
- **Offset**: Stored value = Actual index + 0x10

### Confirmed CTCSS Decoding
Works perfectly for indices 1-15:
- Index 1 (0x11 stored) = 67.0 Hz ✓
- Index 2 (0x12 stored) = 69.3 Hz ✓
- Index 15 (0x1F stored) = 107.2 Hz ✓
- Index 0 (0x10 stored) = OFF ✓

### DCS Problem
Channels 16-20 in your test file show:
- **Expected**: D023N, D025N, D026N, D031N, D032N (from screenshot)
- **Current decoding**: 114.8, 118.8, 123.0, 127.3, 131.8 Hz (CTCSS indices 17-21)
- **Stored indices**: 0x21, 0x22, 0x23, 0x24, 0x25 (hex) = 17-21 (after subtracting 0x10)

## The Issue

The radio appears to use **context-dependent indexing**:
1. When a CTCSS tone is set, indices 1-38 map to standard CTCSS frequencies
2. When a DCS code is set, indices in a certain range map to DCS codes instead

This means we **cannot determine if a tone is CTCSS or DCS from the index alone**. We need additional information that indicates the tone type.

## Possible Solutions

### Option 1: Find the Mode Byte
There may be another byte in the channel record that indicates:
- 0 = No tone / OFF
- 1 = CTCSS
- 2 = DCS Normal (N)
- 3 = DCS Inverted (I)

Let's check the 8 "other" bytes at offset +8 in each channel record.

### Option 2: DCS Uses Different Index Range
Maybe:
- 0x10 = OFF
- 0x11-0x2D (1-38 after offset) = CTCSS
- 0x2E+ (39+ after offset) = DCS codes

But this doesn't match what we're seeing (indices 17-21 are shown as DCS).

### Option 3: Special Encoding for DCS
DCS codes might use a completely different encoding scheme, perhaps:
- High bit set differently
- Different offset value
- Encoded directly as octal values

## What We Need

To fully decode the DCS system, we need:

### Test File Request
Please create a test file with these specific configurations:

**CTCSS Test (CH 1-5)**:
- CH1: 67.0 Hz (first CTCSS)
- CH2: 127.3 Hz (CTCSS #20)
- CH3: 192.8 Hz (last CTCSS #38)
- CH4: OFF
- CH5: 100.0 Hz (CTCSS #13)

**DCS-N Test (CH 6-10)**:
- CH6: D023N (first DCS)
- CH7: D251N (middle DCS)
- CH8: D754N (last DCS)
- CH9: D047N (random DCS)
- CH10: D125N (random DCS)

**DCS-I Test (CH 11-15)**:
- CH11: D023I (first DCS inverted)
- CH12: D251I (middle DCS inverted)
- CH13: D754I (last DCS inverted)
- CH14: D047I (random DCS inverted)
- CH15: D125I (random DCS inverted)

**Mixed Test (CH 16-20)**:
- CH16: RX=67.0 Hz, TX=D023N (different tone types)
- CH17: RX=D125N, TX=100.0 Hz
- CH18: RX=D023N, TX=D023I (N vs I)
- CH19: RX=OFF, TX=100.0
- CH20: RX=100.0, TX=OFF

This test file will let us:
1. Confirm CTCSS index mapping for high indices (20-38)
2. Find the pattern for DCS code encoding
3. Determine how N vs I polarity is encoded
4. See if there's a mode byte that distinguishes CTCSS from DCS
5. Understand mixed RX/TX tone configurations

## Current Status

### Working
✅ Frequency encoding/decoding (RX and TX)
✅ Channel name encoding/decoding
✅ CTCSS tone indices 1-15
✅ OFF tone detection

### Partially Working
⚠️ CTCSS indices 16-38 (not tested yet)
⚠️ DCS codes (structure understood, but mapping unclear)

### Not Working
❌ DCS code decoding (shows as CTCSS)
❌ DCS N vs I polarity detection
❌ Automatic CTCSS vs DCS type detection

## Files Updated

1. **kg_s88g_freq_encoder.py**: Now shows CTCSS/DCS values (but DCS decoding needs work)
2. **kg_s88g.hexpat**: Fixed to use absolute offsets (works correctly now)
3. **kg_s88g_simple.hexpat**: Updated with fixes
4. **kg_s88g_channels.hexpat**: Updated with fixes

## Next Session Goals

Once we get the test file:
1. Analyze the tone bytes for DCS codes
2. Find any mode/type indicator bytes
3. Complete the DCS code mapping
4. Update the Python script with full DCS support
5. Update ImHex patterns to show decoded tones
