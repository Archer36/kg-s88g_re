#!/usr/bin/env python3
"""Parse KG-S88G USB capture and try to decrypt with rolling XOR."""

import sys

# Read tshark output
with open('/tmp/capture_raw.txt') as f:
    lines = f.readlines()

# Reconstruct transactions (group consecutive same-direction frames)
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

print(f"Total transactions: {len(transactions)}")
print()

# Show first 20 transactions
print("=" * 80)
print("FIRST 20 TRANSACTIONS (RAW)")
print("=" * 80)
for i, (direction, data) in enumerate(transactions[:20]):
    prefix = "PC->Radio" if direction == 'TX' else "Radio->PC"
    hex_str = ' '.join(f'{b:02x}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print(f"[{i:3d}] {prefix} ({len(data):3d} bytes): {hex_str}")
    print(f"       ASCII: {ascii_str}")

# Identify protocol phases
# Phase 1: Handshake - magic string exchange
# Phase 2: Key exchange - 16 random bytes
# Phase 3: Data transfer - read commands/responses
print()
print("=" * 80)
print("PROTOCOL ANALYSIS")
print("=" * 80)

# Count TX/RX sizes
tx_sizes = {}
rx_sizes = {}
for d, data in transactions:
    sizes = tx_sizes if d == 'TX' else rx_sizes
    sz = len(data)
    sizes[sz] = sizes.get(sz, 0) + 1

print(f"TX packet sizes: {dict(sorted(tx_sizes.items()))}")
print(f"RX packet sizes: {dict(sorted(rx_sizes.items()))}")

# Find where data transfer starts (after handshake)
# Look for the pattern: after the initial handshake exchanges, we should see
# repetitive TX(5)/RX(21) patterns for data reads
data_start_idx = None
for i in range(len(transactions) - 1):
    d1, data1 = transactions[i]
    d2, data2 = transactions[i+1]
    # First 5-byte TX command followed by 21-byte RX response
    if d1 == 'TX' and len(data1) == 5 and d2 == 'RX' and len(data2) == 21:
        if data_start_idx is None:
            data_start_idx = i
            print(f"\nData transfer starts at transaction [{i}]")
        break

# Now let's look at the handshake more carefully
print("\n--- HANDSHAKE PHASE ---")
for i in range(min(data_start_idx or 10, 12)):
    d, data = transactions[i]
    prefix = "TX" if d == 'TX' else "RX"
    hex_str = ' '.join(f'{b:02x}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print(f"  [{i}] {prefix} ({len(data):3d}B): {hex_str}")
    print(f"        ASCII: {ascii_str}")

# Extract data transfer pairs
data_pairs = []  # (tx_command, rx_response)
i = data_start_idx if data_start_idx else 0
while i < len(transactions) - 1:
    d1, data1 = transactions[i]
    d2, data2 = transactions[i+1]
    if d1 == 'TX' and d2 == 'RX':
        data_pairs.append((data1, data2))
        i += 2
    else:
        i += 1

print(f"\nTotal data pairs: {len(data_pairs)}")
print(f"First 5 data TX commands:")
for j, (tx, rx) in enumerate(data_pairs[:5]):
    print(f"  TX: {' '.join(f'{b:02x}' for b in tx)}")
    print(f"  RX: {' '.join(f'{b:02x}' for b in rx)}")
    print()

# Now try decryption approaches

def rolling_xor_decrypt(data, initial_key, skip_first=True):
    """Decrypt data using rolling XOR.

    Algorithm from Ghidra decompilation of FUN_004d1e2c:
      bVar1 = *pbVar3;              // save original encrypted byte
      *pbVar3 = *pbVar3 ^ key;      // decrypt: XOR with key
      key = (key + bVar1) & 0xFF;   // update key: add original encrypted byte

    The function starts at byte index 1 (pbVar3 = &DAT_004e539d, which is
    one byte past the buffer start), processing (param_2 - 1) bytes.
    """
    result = bytearray()
    key = initial_key
    start = 1 if skip_first else 0

    if skip_first:
        result.append(data[0])  # first byte not decrypted

    for i in range(start, len(data)):
        encrypted_byte = data[i]
        decrypted_byte = encrypted_byte ^ key
        key = (key + encrypted_byte) & 0xFF
        result.append(decrypted_byte)

    return bytes(result), key


def rolling_xor_decrypt_cumulative(pairs, initial_key, skip_first=True):
    """Decrypt all pairs with key carrying over between packets."""
    key = initial_key
    decrypted_pairs = []

    for tx, rx in pairs:
        dec_rx, key = rolling_xor_decrypt(rx, key, skip_first=skip_first)
        decrypted_pairs.append((tx, dec_rx))

    return decrypted_pairs


print()
print("=" * 80)
print("DECRYPTION ATTEMPTS")
print("=" * 80)

# Read stock.dat for comparison
with open('/Users/brett/git-repos/my-gh/kg-s88g_re/Test Saves/stock.dat', 'rb') as f:
    stock_dat = f.read()

print(f"\nstock.dat size: {len(stock_dat)} bytes")
print(f"Channel data starts at 0x0255, first 32 bytes:")
ch_data = stock_dat[0x0255:0x0255+32]
print(f"  {' '.join(f'{b:02x}' for b in ch_data)}")

# Try approach A: key=0, cumulative, skip first byte of each RX
print("\n--- Approach A: key=0, cumulative, skip byte 0 ---")
dec_pairs_a = rolling_xor_decrypt_cumulative(data_pairs, 0, skip_first=True)
for j, (tx, dec_rx) in enumerate(dec_pairs_a[:10]):
    hex_str = ' '.join(f'{b:02x}' for b in dec_rx)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in dec_rx)
    print(f"  [{j}] TX: {' '.join(f'{b:02x}' for b in tx)}")
    print(f"       RX: {hex_str}")
    print(f"       ASCII: {ascii_str}")

# Try approach B: key=0, cumulative, decrypt ALL bytes including byte 0
print("\n--- Approach B: key=0, cumulative, all bytes ---")
dec_pairs_b = rolling_xor_decrypt_cumulative(data_pairs, 0, skip_first=False)
for j, (tx, dec_rx) in enumerate(dec_pairs_b[:10]):
    hex_str = ' '.join(f'{b:02x}' for b in dec_rx)
    print(f"  [{j}] RX: {hex_str}")

# Try approach C: Also decrypt TX commands (maybe TX is encrypted too!)
print("\n--- Approach C: Decrypt both TX and RX, key=0, cumulative ---")
# In this model, ALL serial data in both directions goes through the same rolling XOR
key = 0
all_decrypted = []
for d, data in transactions[data_start_idx:data_start_idx+20]:
    dec_data, key = rolling_xor_decrypt(data, key, skip_first=True)
    prefix = "TX" if d == 'TX' else "RX"
    hex_str = ' '.join(f'{b:02x}' for b in dec_data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in dec_data)
    all_decrypted.append((d, dec_data))
    print(f"  {prefix}: {hex_str}  | {ascii_str}")

# Try approach D: Maybe key is initialized from handshake data
# Look at the handshake responses for possible key values
print("\n--- Approach D: Key from handshake ---")
# Transaction layout: TX0=magic, RX1=response, TX2=random bytes, RX3=validation...
# The checksum bytes from the handshake could be the key
if data_start_idx and data_start_idx >= 2:
    for hs_idx in range(data_start_idx):
        d, data = transactions[hs_idx]
        if d == 'RX':
            print(f"  Handshake RX [{hs_idx}] ({len(data)}B): {' '.join(f'{b:02x}' for b in data)}")
            # Try each byte of this response as the initial key
            for byte_pos in range(len(data)):
                test_key = data[byte_pos]
                dec_test, _ = rolling_xor_decrypt(data_pairs[0][1], test_key, skip_first=True)
                # Check if decrypted data has reasonable values
                # Frequency bytes should be 0x00-0x09 or specific nibble values
                payload = dec_test[1:]  # skip command byte
                # Check if it looks like channel data (lots of small values, or 0x55 pattern)
                has_55 = payload.count(0x55) >= 2
                small_values = sum(1 for b in payload[:8] if b < 0x10)
                if has_55 or small_values >= 4:
                    hex_str = ' '.join(f'{b:02x}' for b in dec_test)
                    print(f"    key=0x{test_key:02x} (from byte {byte_pos}): {hex_str}")

# Try approach E: The encryption may apply to the WHOLE serial stream, not per-packet
# Concatenate all RX bytes from data phase and decrypt as one stream
print("\n--- Approach E: Decrypt RX as one continuous stream, key=0 ---")
all_rx_bytes = bytearray()
for tx, rx in data_pairs:
    all_rx_bytes.extend(rx)

key = 0
dec_stream = bytearray()
for i, b in enumerate(all_rx_bytes):
    dec_stream.append(b ^ key)
    key = (key + b) & 0xFF

# Show first 200 bytes of decrypted stream
print(f"  Total RX bytes: {len(all_rx_bytes)}")
for offset in range(0, min(200, len(dec_stream)), 16):
    chunk = dec_stream[offset:offset+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f"  {offset:04x}: {hex_part:<48s}  {ascii_part}")

# Compare against stock.dat
print("\n--- Compare decrypted stream vs stock.dat ---")
# Try matching windows of decrypted stream against known .dat offsets
# Channel 1 data at 0x0255 in .dat: 16 bytes
ch1_dat = stock_dat[0x0255:0x0255+16]
print(f"  stock.dat ch1 (0x0255): {' '.join(f'{b:02x}' for b in ch1_dat)}")

# Try approach F: Maybe the initial key is derived from the handshake
# In the state machine, after receiving the magic response,
# the radio sends back validation data. The checksum bytes from the
# random key exchange might set DAT_004e94fd.
print("\n--- Approach F: Try all 256 keys on CUMULATIVE stream ---")
best_matches = []
for init_key in range(256):
    key = init_key
    dec = bytearray()
    for b in all_rx_bytes:
        dec.append(b ^ key)
        key = (key + b) & 0xFF

    # Score: count how many bytes match stock.dat at various offsets
    # Try different alignment offsets
    score = 0
    for dat_offset in [0x0255, 0x0000, 0x0010, 0x0100]:
        dat_chunk = stock_dat[dat_offset:dat_offset+20]
        for stream_offset in range(0, min(2000, len(dec)-20)):
            match = sum(1 for a, b in zip(dec[stream_offset:stream_offset+20], dat_chunk) if a == b)
            if match > score:
                score = match
                best_info = (init_key, stream_offset, dat_offset, match)

    if score >= 8:
        best_matches.append(best_info)

best_matches.sort(key=lambda x: -x[3])
print(f"  Best matches (score >= 8 out of 20):")
for key_val, s_off, d_off, score in best_matches[:20]:
    print(f"    key=0x{key_val:02x}, stream_off={s_off}, dat_off=0x{d_off:04x}, match={score}/20")

# Approach G: Maybe the protocol doesn't use encryption for read mode!
# Let me just look at the raw data for patterns
print("\n--- Approach G: Raw data analysis (no decryption) ---")
print("  First 10 RX responses raw payload (bytes 1-20):")
for j, (tx, rx) in enumerate(data_pairs[:10]):
    payload = rx[1:]  # skip first byte
    hex_str = ' '.join(f'{b:02x}' for b in payload)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in payload)
    tx_hex = ' '.join(f'{b:02x}' for b in tx)
    print(f"  [{j}] TX: {tx_hex}")
    print(f"       payload: {hex_str}")
    print(f"       ascii:   {ascii_str}")

# Check for sequential patterns in TX commands
print("\n  TX command byte analysis (first 30):")
for j, (tx, rx) in enumerate(data_pairs[:30]):
    print(f"  [{j:3d}] TX: {' '.join(f'{b:02x}' for b in tx)}  RX[0]: 0x{rx[0]:02x}")

# Check if TX commands have sequential addresses
print("\n  TX byte[1] (potential address) first 30:")
addrs = [tx[1] if len(tx) > 1 else -1 for tx, rx in data_pairs[:30]]
print(f"  {addrs}")

# Approach H: Maybe encryption only applies to data content, not the command/address bytes
# And the structure is: TX: [cmd][addr_hi][addr_lo][len][checksum], RX: [cmd][data...]
print("\n--- Approach H: Interpret TX as [cmd][addr_hi][addr_lo][?][?] ---")
print("  First 20 commands interpreted:")
for j, (tx, rx) in enumerate(data_pairs[:20]):
    if len(tx) >= 5:
        cmd = tx[0]
        addr = (tx[1] << 8) | tx[2]
        b3 = tx[3]
        b4 = tx[4]
        print(f"  [{j:3d}] cmd=0x{cmd:02x} addr=0x{addr:04x} b3=0x{b3:02x} b4=0x{b4:02x}  RXlen={len(rx)}")

# Try interpreting [cmd][index][0][0][0]
print("\n  First 20 commands as [cmd][index][...] :")
for j, (tx, rx) in enumerate(data_pairs[:20]):
    if len(tx) >= 5:
        print(f"  [{j:3d}] bytes: {' '.join(f'{b:02x}' for b in tx)}")
