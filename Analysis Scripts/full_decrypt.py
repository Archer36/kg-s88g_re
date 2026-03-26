#!/usr/bin/env python3
"""Decrypt the full KG-S88G capture and reconstruct the EEPROM image.

Key findings:
- Rolling XOR cipher: dec = enc ^ key; key = (key + enc) & 0xFF
- Key starts at 0x4c when starting from data phase (transaction 8)
- Byte 0 of each packet is NOT encrypted
- TX format: [0x57][addr_hi][addr_mid][addr_lo][length]
- RX format: [0x57][addr_hi][addr_mid][addr_lo][length][data...]
"""

with open('/tmp/capture_raw.txt') as f:
    lines = f.readlines()

# Reconstruct transactions
transactions = []
current_dir = None
current_bytes = bytearray()

for line in lines:
    parts = line.strip().split('\t')
    if len(parts) < 4:
        continue
    frame, src, dst, capdata = parts[0], parts[1], parts[2], parts[3]
    raw_bytes = bytes.fromhex(capdata.replace(':', ''))
    direction = 'TX' if 'host' in src else 'RX'
    if direction != current_dir and current_bytes:
        transactions.append((current_dir, bytes(current_bytes)))
        current_bytes = bytearray()
    current_dir = direction
    current_bytes.extend(raw_bytes)
if current_bytes:
    transactions.append((current_dir, bytes(current_bytes)))

DATA_START = 8

# Decrypt all data-phase transactions with key=0x4c
key = 0x4c
decrypted = []

for d, data in transactions[DATA_START:]:
    dec = bytearray()
    dec.append(data[0])  # byte 0 not encrypted
    for i in range(1, len(data)):
        enc_byte = data[i]
        dec_byte = enc_byte ^ key
        key = (key + enc_byte) & 0xFF
        dec.append(dec_byte)
    decrypted.append((d, bytes(dec)))

# Extract read pairs
eeprom = bytearray(b'\xff' * 0x10000)  # 64K EEPROM space
addresses_read = []

i = 0
pair_count = 0
while i < len(decrypted) - 1:
    d1, data1 = decrypted[i]
    d2, data2 = decrypted[i + 1]

    if d1 == 'TX' and d2 == 'RX' and len(data1) == 5 and len(data2) == 21:
        # Parse TX command
        cmd = data1[0]
        addr = (data1[1] << 16) | (data1[2] << 8) | data1[3]
        length = data1[4]

        # Parse RX response
        rx_cmd = data2[0]
        rx_addr = (data2[1] << 16) | (data2[2] << 8) | data2[3]
        rx_len = data2[4]
        payload = data2[5:]

        if pair_count < 30 or pair_count % 100 == 0:
            hex_payload = ' '.join(f'{b:02x}' for b in payload)
            print(f"[{pair_count:3d}] addr=0x{addr:06x} len=0x{length:02x} "
                  f"rx_addr=0x{rx_addr:06x} data: {hex_payload}")

        # Verify TX and RX addresses match
        if addr != rx_addr and pair_count < 5:
            print(f"  WARNING: TX addr 0x{addr:06x} != RX addr 0x{rx_addr:06x}")

        # Store in EEPROM image
        if addr < len(eeprom):
            for j, b in enumerate(payload):
                if addr + j < len(eeprom):
                    eeprom[addr + j] = b

        addresses_read.append(addr)
        pair_count += 2
        i += 2
    else:
        # Check for the exit command
        if d1 == 'TX' and len(data1) == 1:
            print(f"  Single TX byte: 0x{data1[0]:02x} ({'T=exit' if data1[0]==0x54 else '?'})")
        i += 1

pair_count = len(addresses_read)
print(f"\nTotal read operations: {pair_count}")
print(f"Address range: 0x{min(addresses_read):06x} - 0x{max(addresses_read):06x}")
print(f"Total bytes read: {pair_count * 16}")

# Check if addresses are sequential
sorted_addrs = sorted(addresses_read)
print(f"\nFirst 20 addresses: {[f'0x{a:04x}' for a in sorted_addrs[:20]]}")
print(f"Last 20 addresses: {[f'0x{a:04x}' for a in sorted_addrs[-20:]]}")

# Check for gaps
gaps = []
for i in range(1, len(sorted_addrs)):
    expected = sorted_addrs[i-1] + 16
    if sorted_addrs[i] != expected:
        gaps.append((sorted_addrs[i-1], sorted_addrs[i], sorted_addrs[i] - expected))

if gaps:
    print(f"\nAddress gaps found: {len(gaps)}")
    for prev, next_addr, gap_size in gaps[:10]:
        print(f"  Gap after 0x{prev:04x}, next=0x{next_addr:04x}, size={gap_size}")
else:
    print("\nNo gaps - addresses are fully sequential!")

# Save the EEPROM image
eeprom_end = max(addresses_read) + 16
eeprom_trimmed = bytes(eeprom[:eeprom_end])
with open('/tmp/kg_s88g_eeprom.bin', 'wb') as f:
    f.write(eeprom_trimmed)
print(f"\nSaved EEPROM image: /tmp/kg_s88g_eeprom.bin ({len(eeprom_trimmed)} bytes)")

# Now compare against the .dat file to understand the mapping
with open('/Users/brett/git-repos/my-gh/kg-s88g_re/Test Saves/stock.dat', 'rb') as f:
    stock_dat = f.read()

print(f"\n{'=' * 80}")
print("EEPROM vs .dat FILE COMPARISON")
print(f"{'=' * 80}")
print(f"EEPROM size: {len(eeprom_trimmed)} bytes")
print(f".dat size: {len(stock_dat)} bytes")

# Show first 256 bytes of EEPROM
print("\nFirst 256 bytes of EEPROM:")
for offset in range(0, 256, 16):
    chunk = eeprom_trimmed[offset:offset+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f"  {offset:04x}: {hex_part}  {ascii_part}")

# Show first 256 bytes of .dat
print("\nFirst 256 bytes of .dat:")
for offset in range(0, 256, 16):
    chunk = stock_dat[offset:offset+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f"  {offset:04x}: {hex_part}  {ascii_part}")

# Look for GMRS channel 1 frequency in EEPROM
# Channel 1 = 462.5625 MHz
# In the .dat file it's encoded as 05 37 70 13 (custom nibble encoding)
# In EEPROM it might be stored differently - maybe BCD or binary
print("\nSearching EEPROM for potential frequency representations of 462.5625 MHz:")

# BCD: 4625625 = 0x04 0x62 0x56 0x25
bcd_freq = bytes([0x04, 0x62, 0x56, 0x25])
for i in range(len(eeprom_trimmed) - 3):
    if eeprom_trimmed[i:i+4] == bcd_freq:
        print(f"  Found BCD 04625625 at offset 0x{i:04x}")

# Reversed BCD: 25 56 62 04
bcd_rev = bytes([0x25, 0x56, 0x62, 0x04])
for i in range(len(eeprom_trimmed) - 3):
    if eeprom_trimmed[i:i+4] == bcd_rev:
        print(f"  Found reversed BCD at offset 0x{i:04x}")

# Binary Hz: 462562500 = 0x1B929AA4
freq_hz = 462562500
freq_bytes = freq_hz.to_bytes(4, 'little')
for i in range(len(eeprom_trimmed) - 3):
    if eeprom_trimmed[i:i+4] == freq_bytes:
        print(f"  Found binary Hz (LE) at offset 0x{i:04x}")
freq_bytes_be = freq_hz.to_bytes(4, 'big')
for i in range(len(eeprom_trimmed) - 3):
    if eeprom_trimmed[i:i+4] == freq_bytes_be:
        print(f"  Found binary Hz (BE) at offset 0x{i:04x}")

# 10 Hz units: 46256250 = 0x02C1F28A
freq_10hz = 46256250
for endian, name in [('little', 'LE'), ('big', 'BE')]:
    fb = freq_10hz.to_bytes(4, endian)
    for i in range(len(eeprom_trimmed) - 3):
        if eeprom_trimmed[i:i+4] == fb:
            print(f"  Found 10Hz units ({name}) at offset 0x{i:04x}")

# 100 Hz units: 4625625 = 0x469E69
freq_100hz = 4625625
for endian, name in [('little', 'LE'), ('big', 'BE')]:
    fb = freq_100hz.to_bytes(4, endian)
    for i in range(len(eeprom_trimmed) - 3):
        if eeprom_trimmed[i:i+4] == fb:
            print(f"  Found 100Hz units ({name}) at offset 0x{i:04x}")

# kHz * 10: 4625625 as 3 bytes = 0x469E69
# Also try 2-byte representations
# 462.5625 * 100 = 46256.25, or stored as 46256 = 0xB4C0
freq_khz10 = 46256
for endian, name in [('little', 'LE'), ('big', 'BE')]:
    fb = freq_khz10.to_bytes(2, endian)
    for i in range(len(eeprom_trimmed) - 1):
        if eeprom_trimmed[i:i+2] == fb:
            print(f"  Found kHz*10 ({name}) at offset 0x{i:04x}")

# Try BCD of 4625625 packed differently
# 46 25 62 50 or 46 25 62 5
print("\nSearching for various BCD encodings:")
for pattern, label in [
    (bytes([0x46, 0x25, 0x62, 0x50]), "4625 6250"),
    (bytes([0x46, 0x25, 0x62, 0x5f]), "4625 625f"),
    (bytes([0x62, 0x56, 0x25]), "62 56 25"),
    (bytes([0x25, 0x62, 0x50]), "25 62 50"),
]:
    for i in range(len(eeprom_trimmed) - len(pattern) + 1):
        if eeprom_trimmed[i:i+len(pattern)] == pattern:
            print(f"  Found '{label}' at 0x{i:04x}")

# Look at what's in EEPROM at position 0x0000 (first data)
print(f"\nEEPROM[0x0000:0x0040] (first 64 bytes - likely radio settings):")
for offset in range(0, 64, 16):
    chunk = eeprom_trimmed[offset:offset+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    print(f"  {offset:04x}: {hex_part}")

# .dat file channel 1 starts at 0x0255
# Let's see what's at corresponding EEPROM location
print(f"\nEEPROM around offset 0x0255:")
for offset in range(0x0240, 0x0280, 16):
    if offset < len(eeprom_trimmed):
        chunk = eeprom_trimmed[offset:offset+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        print(f"  {offset:04x}: {hex_part}")

# Let's look for repeated 16-byte structures that could be channels
print("\nSearching for repeating 16-byte channel structures in EEPROM...")
# A GMRS radio with 22 channels should have 22 programmed channel entries
# followed by empty ones (0xFF)
for start in range(0, min(0x2000, len(eeprom_trimmed)), 16):
    chunk = eeprom_trimmed[start:start+16]
    # Check if this looks like a non-empty, non-zero channel entry
    if chunk != b'\xff' * 16 and chunk != b'\x00' * 16:
        # Look ahead to see if next entry is also valid, suggesting channel array
        next_chunk = eeprom_trimmed[start+16:start+32] if start+32 <= len(eeprom_trimmed) else b''
        if next_chunk and next_chunk != b'\xff' * 16 and next_chunk != b'\x00' * 16:
            # Found two consecutive non-empty entries
            if start < 0x100 or (start >= 0x100 and start <= 0x200):
                continue  # skip early bytes (likely settings, not channels)
            hex1 = ' '.join(f'{b:02x}' for b in chunk)
            hex2 = ' '.join(f'{b:02x}' for b in next_chunk)
            print(f"  0x{start:04x}: {hex1}")
            print(f"  0x{start+16:04x}: {hex2}")
            # Check 10 more
            for k in range(2, 12):
                off = start + k * 16
                if off + 16 <= len(eeprom_trimmed):
                    c = eeprom_trimmed[off:off+16]
                    hex_c = ' '.join(f'{b:02x}' for b in c)
                    status = "EMPTY" if c == b'\xff' * 16 else ""
                    print(f"  0x{off:04x}: {hex_c}  {status}")
            break

# Also dump a broader view of the EEPROM to find structure
print(f"\nEEPROM content summary (non-FF blocks):")
for block_start in range(0, len(eeprom_trimmed), 256):
    block = eeprom_trimmed[block_start:block_start+256]
    non_ff = sum(1 for b in block if b != 0xff)
    if non_ff > 0:
        print(f"  0x{block_start:04x}-0x{block_start+255:04x}: {non_ff}/256 non-FF bytes")
