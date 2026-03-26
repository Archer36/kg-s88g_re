#!/usr/bin/env python3
"""Analyze the decrypted KG-S88G EEPROM image."""

with open('/tmp/kg_s88g_eeprom.bin', 'rb') as f:
    eeprom = f.read()

print(f"EEPROM size: {len(eeprom)} bytes (0x{len(eeprom):04x})")

def decode_freq_bcd_le(b):
    """Decode a 4-byte LE BCD frequency.
    e.g. 00 25 26 46 => reversed: 46 26 25 00 => 462.62500 MHz
    """
    bcd_str = f'{b[3]:02x}{b[2]:02x}{b[1]:02x}{b[0]:02x}'
    try:
        freq = int(bcd_str)
        return freq / 100000.0  # MHz with 5 decimal places
    except:
        return 0

# Dump EEPROM from 0x0100 to 0x0300 as potential channel data
print("\n" + "=" * 80)
print("CHANNEL DATA ANALYSIS (16-byte records)")
print("=" * 80)

# GMRS standard channels for reference
gmrs = {
    1: (462.5625, 462.5625), 2: (462.5875, 462.5875),
    3: (462.6125, 462.6125), 4: (462.6375, 462.6375),
    5: (462.6625, 462.6625), 6: (462.6875, 462.6875),
    7: (462.7125, 462.7125), 8: (467.5625, 467.5625),
    9: (467.5875, 467.5875), 10: (467.6125, 467.6125),
    11: (467.6375, 467.6375), 12: (467.6625, 467.6625),
    13: (467.6875, 467.6875), 14: (467.7125, 467.7125),
    15: (462.5500, 462.5500), 16: (462.5750, 462.5750),
    17: (462.6000, 462.6000), 18: (462.6250, 462.6250),
    19: (462.6500, 462.6500), 20: (462.6750, 462.6750),
    21: (462.7000, 462.7000), 22: (462.7250, 462.7250),
}

# Try to find channel data
# Look for 16-byte aligned records with valid frequency patterns
print("\nScanning for channel records with valid frequencies:")
for offset in range(0, min(0x2800, len(eeprom)), 16):
    chunk = eeprom[offset:offset+16]
    if len(chunk) < 16:
        break
    if chunk == b'\xff' * 16:
        continue

    rx_freq = decode_freq_bcd_le(chunk[0:4])
    tx_freq = decode_freq_bcd_le(chunk[4:8])

    # Valid UHF frequency range: 400-520 MHz
    if 400 <= rx_freq <= 520:
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        # Try to identify which GMRS channel this is
        gmrs_match = ""
        for ch, (rx, tx) in gmrs.items():
            if abs(rx_freq - rx) < 0.001:
                gmrs_match = f" = GMRS Ch {ch}"
                break
        print(f"  0x{offset:04x}: {hex_str}  RX={rx_freq:.5f} TX={tx_freq:.5f}{gmrs_match}")

# Now let's look at channel name area
# In the .dat file, names are at 0x1C4B with 6 bytes each
# In EEPROM, name data is at 0x1B00 (we see non-FF there)
print("\n" + "=" * 80)
print("NAME DATA AREA (0x1B00)")
print("=" * 80)
for offset in range(0x1B00, min(0x1C00, len(eeprom)), 16):
    if offset + 16 <= len(eeprom):
        chunk = eeprom[offset:offset+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"  {offset:04x}: {hex_part}  {ascii_part}")

# Settings area at 0x0000-0x00FF
print("\n" + "=" * 80)
print("SETTINGS AREA (0x0000-0x00FF)")
print("=" * 80)
for offset in range(0, 0x100, 16):
    chunk = eeprom[offset:offset+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    non_ff = sum(1 for b in chunk if b != 0xff)
    if non_ff > 0:
        print(f"  {offset:04x}: {hex_part}  {ascii_part}")

# Area 0x2500-0x27D0 (other non-FF data)
print("\n" + "=" * 80)
print("DATA AREA 0x2500-0x27D0")
print("=" * 80)
for offset in range(0x2500, min(0x27D0, len(eeprom)), 16):
    if offset + 16 <= len(eeprom):
        chunk = eeprom[offset:offset+16]
        if chunk != b'\xff' * 16:
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f"  {offset:04x}: {hex_part}  {ascii_part}")

# Full hex dump of 0x0100-0x02FF (likely channel records)
print("\n" + "=" * 80)
print("FULL CHANNEL AREA 0x0100-0x02FF")
print("=" * 80)
for offset in range(0x0100, 0x0300, 16):
    if offset + 16 <= len(eeprom):
        chunk = eeprom[offset:offset+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        rx = decode_freq_bcd_le(chunk[0:4])
        tx = decode_freq_bcd_le(chunk[4:8])
        flags = ' '.join(f'{b:02x}' for b in chunk[8:16])
        if chunk == b'\xff' * 16:
            status = "EMPTY"
        else:
            status = f"RX={rx:.4f} TX={tx:.4f}"
        print(f"  {offset:04x}: {hex_part}  {status}")
