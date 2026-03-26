#!/usr/bin/env python3
"""Check if EEPROM has room for 400 channels and map layout to .dat file."""

with open('/tmp/kg_s88g_eeprom.bin', 'rb') as f:
    eeprom = f.read()

with open('/Users/brett/git-repos/my-gh/kg-s88g_re/Test Saves/stock.dat', 'rb') as f:
    stock_dat = f.read()

print(f"EEPROM size: {len(eeprom)} bytes (0x{len(eeprom):04x})")
print(f".dat size:   {len(stock_dat)} bytes (0x{len(stock_dat):04x})")

# === EEPROM layout hypothesis ===
CH_FREQ_BASE = 0x0100  # channel 0 at 0x0100 (unused?), ch 1 at 0x0110
CH_FREQ_SIZE = 16
CH_NAME_BASE = 0x1B00
CH_NAME_SIZE = 6
NUM_CHANNELS = 400

ch_freq_end = CH_FREQ_BASE + (NUM_CHANNELS + 1) * CH_FREQ_SIZE  # +1 for slot 0
ch_name_end = CH_NAME_BASE + (NUM_CHANNELS + 1) * CH_NAME_SIZE

print(f"\n{'='*70}")
print("EEPROM LAYOUT (hypothesis)")
print(f"{'='*70}")
print(f"  Settings:      0x0000 - 0x00FF  ({0x100:5d} bytes)")
print(f"  Channel freq:  0x{CH_FREQ_BASE:04x} - 0x{ch_freq_end-1:04x}  ({(NUM_CHANNELS+1)*CH_FREQ_SIZE:5d} bytes, {NUM_CHANNELS+1} slots × {CH_FREQ_SIZE}B)")
print(f"  Gap/padding:   0x{ch_freq_end:04x} - 0x{CH_NAME_BASE-1:04x}  ({CH_NAME_BASE - ch_freq_end:5d} bytes)")
print(f"  Channel names: 0x{CH_NAME_BASE:04x} - 0x{ch_name_end-1:04x}  ({(NUM_CHANNELS+1)*CH_NAME_SIZE:5d} bytes, {NUM_CHANNELS+1} slots × {CH_NAME_SIZE}B)")
print(f"  Remainder:     0x{ch_name_end:04x} - 0x{len(eeprom)-1:04x}  ({len(eeprom) - ch_name_end:5d} bytes)")
print(f"  Total EEPROM:  0x0000 - 0x{len(eeprom)-1:04x}  ({len(eeprom):5d} bytes)")

fits = ch_freq_end <= CH_NAME_BASE and ch_name_end <= len(eeprom)
print(f"\n  400 channels fit? {'YES' if fits else 'NO'}")

# === Compare with .dat layout ===
print(f"\n{'='*70}")
print(".dat LAYOUT (from RE summary)")
print(f"{'='*70}")
DAT_FREQ_BASE = 0x0255
DAT_NAME_BASE = 0x1C4B
dat_freq_end = DAT_FREQ_BASE + NUM_CHANNELS * CH_FREQ_SIZE
dat_name_end = DAT_NAME_BASE + NUM_CHANNELS * CH_NAME_SIZE
print(f"  Header:        0x0000 - 0x0254  ({0x0255:5d} bytes)")
print(f"  Channel freq:  0x{DAT_FREQ_BASE:04x} - 0x{dat_freq_end-1:04x}  ({NUM_CHANNELS*CH_FREQ_SIZE:5d} bytes, {NUM_CHANNELS} × {CH_FREQ_SIZE}B)")
print(f"  Gap (0xAA):    0x{dat_freq_end:04x} - 0x{DAT_NAME_BASE-1:04x}  ({DAT_NAME_BASE - dat_freq_end:5d} bytes)")
print(f"  Channel names: 0x{DAT_NAME_BASE:04x} - 0x{dat_name_end-1:04x}  ({NUM_CHANNELS*CH_NAME_SIZE:5d} bytes, {NUM_CHANNELS} × {CH_NAME_SIZE}B)")
print(f"  Remainder:     0x{dat_name_end:04x} - 0x{len(stock_dat)-1:04x}  ({len(stock_dat) - dat_name_end:5d} bytes)")

# === Verify the XOR 0x55 mapping between EEPROM and .dat ===
print(f"\n{'='*70}")
print("VERIFYING EEPROM-to-.dat MAPPING")
print(f"{'='*70}")

# .dat channel 1 is at 0x0255. If EEPROM channel 1 is at 0x0110,
# then .dat offset = EEPROM offset + (0x0255 - 0x0110) = EEPROM offset + 0x0145
# But the .dat is 1-indexed starting at 0x0255, while EEPROM might be 0-indexed at 0x0100

# Let's check: does EEPROM[0x0110:0x0120] XOR 0x55 == stock.dat[0x0255:0x0265]?
print("\nChecking if EEPROM channel data XOR 0x55 matches .dat channel data:")
print("(NOTE: capture and stock.dat may be from different configurations!)\n")

# The capture has different channels than stock.dat, so direct comparison won't match.
# Instead, verify the encoding relationship using channels that DO exist in both.
# Let's check: EEPROM ch1 = 462.55000 MHz. In stock.dat, is there a 462.55000 somewhere?

# Stock.dat channels start at 0x0255, 16 bytes each
print("Stock .dat channels (first 30):")
for ch in range(30):
    dat_offset = DAT_FREQ_BASE + ch * CH_FREQ_SIZE
    dat_bytes = stock_dat[dat_offset:dat_offset + CH_FREQ_SIZE]
    # XOR with 0x55 to get EEPROM equivalent
    eeprom_equiv = bytes(b ^ 0x55 for b in dat_bytes)

    # Decode frequency from EEPROM-equivalent bytes
    bcd_str = f'{eeprom_equiv[3]:02x}{eeprom_equiv[2]:02x}{eeprom_equiv[1]:02x}{eeprom_equiv[0]:02x}'
    try:
        rx_freq = int(bcd_str) / 100000.0
    except:
        rx_freq = 0

    bcd_str2 = f'{eeprom_equiv[7]:02x}{eeprom_equiv[6]:02x}{eeprom_equiv[5]:02x}{eeprom_equiv[4]:02x}'
    try:
        tx_freq = int(bcd_str2) / 100000.0
    except:
        tx_freq = 0

    if dat_bytes == b'\xaa' * 16:
        print(f"  .dat ch {ch+1:3d}: EMPTY (0xAA fill)")
    elif dat_bytes == b'\xff' * 16:
        print(f"  .dat ch {ch+1:3d}: EMPTY (0xFF fill)")
    else:
        dat_hex = ' '.join(f'{b:02x}' for b in dat_bytes)
        eep_hex = ' '.join(f'{b:02x}' for b in eeprom_equiv)
        print(f"  .dat ch {ch+1:3d}: RX={rx_freq:.5f} TX={tx_freq:.5f}")
        print(f"           .dat bytes: {dat_hex}")
        print(f"           ^0x55 =   : {eep_hex}")

# Check the gap between freq and name areas
print(f"\n{'='*70}")
print("EEPROM GAP AREA (between freq and name)")
print(f"{'='*70}")
gap_start = ch_freq_end
gap_end = CH_NAME_BASE
print(f"Gap: 0x{gap_start:04x} - 0x{gap_end-1:04x} ({gap_end - gap_start} bytes)")
if gap_start < len(eeprom):
    gap_data = eeprom[gap_start:min(gap_end, len(eeprom))]
    non_ff = sum(1 for b in gap_data if b != 0xff)
    print(f"  Non-FF bytes in gap: {non_ff}/{len(gap_data)}")
    if non_ff > 0:
        for offset in range(0, len(gap_data), 16):
            chunk = gap_data[offset:offset+16]
            if any(b != 0xff for b in chunk):
                hex_part = ' '.join(f'{b:02x}' for b in chunk)
                print(f"  {gap_start+offset:04x}: {hex_part}")

# Verify: last channel slot (400) fits?
last_freq = CH_FREQ_BASE + 400 * CH_FREQ_SIZE  # ch 400 at 0x0100 + 400*16 = 0x1A00
last_name = CH_NAME_BASE + 400 * CH_NAME_SIZE   # name 400 at 0x1B00 + 400*6 = 0x2460
print(f"\nChannel 400 freq offset: 0x{last_freq:04x} (EEPROM ends at 0x{len(eeprom)-1:04x}): {'FITS' if last_freq + 16 <= len(eeprom) else 'OUT OF RANGE'}")
print(f"Channel 400 name offset: 0x{last_name:04x} (EEPROM ends at 0x{len(eeprom)-1:04x}): {'FITS' if last_name + 6 <= len(eeprom) else 'OUT OF RANGE'}")

# Check what's in the area after channel 30 (the last programmed one)
print(f"\nChannel 31-35 area (should be empty/0xFF):")
for ch in range(31, 36):
    offset = CH_FREQ_BASE + ch * CH_FREQ_SIZE
    if offset + 16 <= len(eeprom):
        chunk = eeprom[offset:offset+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        status = "EMPTY" if chunk == b'\xff' * 16 else "HAS DATA"
        print(f"  Ch {ch:3d} @ 0x{offset:04x}: {hex_part}  [{status}]")

# Check what's near the end of the channel freq area
print(f"\nChannel 398-400 area:")
for ch in range(398, 401):
    offset = CH_FREQ_BASE + ch * CH_FREQ_SIZE
    if offset + 16 <= len(eeprom):
        chunk = eeprom[offset:offset+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        status = "EMPTY" if chunk == b'\xff' * 16 else "HAS DATA"
        print(f"  Ch {ch:3d} @ 0x{offset:04x}: {hex_part}  [{status}]")
    else:
        print(f"  Ch {ch:3d} @ 0x{offset:04x}: BEYOND EEPROM END")
