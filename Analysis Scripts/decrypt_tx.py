#!/usr/bin/env python3
"""Try to crack encryption by focusing on TX commands.

Key insight: TX commands should have a predictable structure.
From the decompilation, upload commands are:
  [0x57][channel_index][data...]
And for reads, probably:
  [0x52][address/index][0x00][0x00][checksum] or similar

But BOTH TX and RX go through the same rolling XOR cipher.
The key carries over across ALL data in both directions.

Let's try decrypting the ENTIRE serial stream (TX and RX interleaved)
with all 256 initial keys and look for patterns.
"""

# Read tshark output
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

# Data transfer starts at transaction index 8
# Transactions 0-7 are handshake
DATA_START = 8

# Extract data-phase transactions
data_txns = transactions[DATA_START:]

# The handshake also feeds the key state!
# Let's look at what feeds into the XOR cipher.
#
# From decompilation: the decrypt function operates on a buffer starting
# at DAT_004e539d. But WHEN is it called?
#
# Theory: The cipher applies to the data portion of each packet (skipping byte 0),
# and the key carries over across ALL packets in sequence.
#
# Let's try: concatenate all bytes from data phase (TX and RX interleaved),
# skip byte 0 of each transaction, decrypt the rest.

print("=" * 80)
print("APPROACH 1: Decrypt data bytes (skip byte 0 per txn), key carries over")
print("=" * 80)

for init_key in range(256):
    key = init_key
    decrypted_txns = []

    for d, data in data_txns:
        dec = bytearray()
        dec.append(data[0])  # byte 0 not encrypted
        for i in range(1, len(data)):
            enc_byte = data[i]
            dec_byte = enc_byte ^ key
            key = (key + enc_byte) & 0xFF
            dec.append(dec_byte)
        decrypted_txns.append((d, bytes(dec)))

    # Check if TX commands make sense
    # For a read operation, TX should be [0x57/0x52][sequential_index][zeros or small values]
    # Check first few TX commands
    tx_cmds = [(d, data) for d, data in decrypted_txns if d == 'TX' and len(data) == 5]

    if len(tx_cmds) >= 10:
        # Check if byte[1] of TX commands follows a pattern
        byte1_values = [data[1] for _, data in tx_cmds[:20]]

        # Check for sequential pattern (0,1,2,3...)
        is_sequential = all(byte1_values[i] == i for i in range(min(10, len(byte1_values))))

        # Check for all zeros in bytes 2-4
        zeros_count = sum(1 for _, data in tx_cmds[:10] if data[2] == 0 and data[3] == 0)

        # Check for all same value in bytes 2-4
        byte2_same = len(set(data[2] for _, data in tx_cmds[:10])) == 1

        if is_sequential or zeros_count >= 5 or byte2_same:
            print(f"\n  key=0x{init_key:02x}: INTERESTING!")
            print(f"    byte[1] values: {byte1_values[:15]}")
            print(f"    sequential: {is_sequential}, zeros_count: {zeros_count}, byte2_same: {byte2_same}")
            for j, (_, data) in enumerate(tx_cmds[:5]):
                print(f"    TX[{j}]: {' '.join(f'{b:02x}' for b in data)}")
            # Show corresponding RX
            rx_cmds = [(d, data) for d, data in decrypted_txns if d == 'RX' and len(data) == 21]
            for j, (_, data) in enumerate(rx_cmds[:3]):
                print(f"    RX[{j}]: {' '.join(f'{b:02x}' for b in data)}")

print()
print("=" * 80)
print("APPROACH 2: Maybe handshake data also feeds the key")
print("=" * 80)
print("Handshake transactions:")
for i, (d, data) in enumerate(transactions[:DATA_START]):
    prefix = "TX" if d == 'TX' else "RX"
    print(f"  [{i}] {prefix}: {' '.join(f'{b:02x}' for b in data)}")

# Theory: ALL serial bytes (from transaction 0 onward) feed the key
# including the handshake bytes
for init_key in range(256):
    key = init_key
    all_decrypted = []

    for d, data in transactions:
        dec = bytearray()
        dec.append(data[0])  # byte 0 not encrypted
        for i in range(1, len(data)):
            enc_byte = data[i]
            dec_byte = enc_byte ^ key
            key = (key + enc_byte) & 0xFF
            dec.append(dec_byte)
        all_decrypted.append((d, bytes(dec)))

    # Check data-phase TX commands
    data_dec = all_decrypted[DATA_START:]
    tx_cmds = [(d, data) for d, data in data_dec if d == 'TX' and len(data) == 5]

    if len(tx_cmds) >= 10:
        byte1_values = [data[1] for _, data in tx_cmds[:20]]
        is_sequential = all(byte1_values[i] == i for i in range(min(10, len(byte1_values))))
        zeros_count = sum(1 for _, data in tx_cmds[:10] if data[2] == 0 and data[3] == 0)
        byte2_same = len(set(data[2] for _, data in tx_cmds[:10])) == 1

        if is_sequential or zeros_count >= 5 or byte2_same:
            print(f"\n  key=0x{init_key:02x}: INTERESTING!")
            print(f"    byte[1] values: {byte1_values[:15]}")
            for j, (_, data) in enumerate(tx_cmds[:5]):
                print(f"    TX[{j}]: {' '.join(f'{b:02x}' for b in data)}")
            rx_cmds = [(d, data) for d, data in data_dec if d == 'RX' and len(data) == 21]
            for j, (_, data) in enumerate(rx_cmds[:3]):
                print(f"    RX[{j}]: {' '.join(f'{b:02x}' for b in data)}")

print()
print("=" * 80)
print("APPROACH 3: Maybe ALL bytes (including byte 0) are encrypted")
print("=" * 80)

for init_key in range(256):
    key = init_key
    all_decrypted = []

    for d, data in transactions:
        dec = bytearray()
        for i in range(len(data)):
            enc_byte = data[i]
            dec_byte = enc_byte ^ key
            key = (key + enc_byte) & 0xFF
            dec.append(dec_byte)
        all_decrypted.append((d, bytes(dec)))

    data_dec = all_decrypted[DATA_START:]
    tx_cmds = [(d, data) for d, data in data_dec if d == 'TX' and len(data) == 5]

    if len(tx_cmds) >= 10:
        # For this approach, byte[0] should decrypt to 0x57 or 0x52
        cmd_bytes = [data[0] for _, data in tx_cmds[:10]]
        all_same_cmd = len(set(cmd_bytes)) == 1 and cmd_bytes[0] in (0x52, 0x57)

        byte1_values = [data[1] for _, data in tx_cmds[:20]]
        is_sequential = all(byte1_values[i] == i for i in range(min(10, len(byte1_values))))
        zeros_count = sum(1 for _, data in tx_cmds[:10] if data[2] == 0 and data[3] == 0)

        if all_same_cmd or is_sequential or zeros_count >= 5:
            print(f"\n  key=0x{init_key:02x}: cmd_bytes={[f'0x{b:02x}' for b in cmd_bytes[:5]]}")
            print(f"    byte[1]: {byte1_values[:15]}")
            for j, (_, data) in enumerate(tx_cmds[:5]):
                print(f"    TX[{j}]: {' '.join(f'{b:02x}' for b in data)}")

print()
print("=" * 80)
print("APPROACH 4: Cipher only on data-phase, only RX, try matching RX patterns")
print("=" * 80)
print("Looking at raw RX responses for patterns...")

# Many RX responses have lots of 0x00 bytes (empty channels)
# Response [1] has 15 trailing zeros, [8] has 16 trailing zeros, etc.
# If these are encrypted zeros, what key would produce them?
# 0x00 ^ key = encrypted_byte => key = encrypted_byte
# Then key = (key + encrypted_byte) & 0xFF = (encrypted_byte + encrypted_byte) & 0xFF

# Look at response [1] (pair index 1): 57 d0 a0 50 80 ef 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# Bytes 5-20 are all 0x00. If the plaintext is also 0x00:
# 0x00 ^ key = 0x00 => key = 0x00, then key = (0+0)=0, then 0x00^0=0x00... consistent!
# So either these ARE unencrypted zeros, or the key happened to be 0 at that point.

# But if byte 5 (0xef) decrypts to something with key K:
# 0xef ^ K = plaintext
# then K_next = (K + 0xef) & 0xFF
# then 0x00 ^ K_next = plaintext_next
# For trailing zeros to decrypt to zeros, K_next must be 0, so K + 0xef = 0 mod 256 => K = 0x11
# Then 0xef ^ 0x11 = 0xfe

# Actually let me reconsider: maybe the data ISN'T encrypted at all!
# The response bytes for empty channels would naturally be 0x00
# And 0x57 as byte[0] of every response = echo of the command byte

# Let's check: do the raw RX responses already contain valid data?
print("\nRX responses with many zero bytes (potential empty channels):")
data_pairs = []
i = DATA_START
while i < len(transactions) - 1:
    d1, data1 = transactions[i]
    d2, data2 = transactions[i+1]
    if d1 == 'TX' and d2 == 'RX':
        data_pairs.append((data1, data2))
        i += 2
    else:
        i += 1

zero_count_list = []
for j, (tx, rx) in enumerate(data_pairs):
    zeros = sum(1 for b in rx[5:] if b == 0)
    zero_count_list.append(zeros)
    if zeros >= 10 and j < 50:
        print(f"  [{j:3d}] TX: {' '.join(f'{b:02x}' for b in tx)}  RX: {' '.join(f'{b:02x}' for b in rx)}")

total_high_zero = sum(1 for z in zero_count_list if z >= 10)
print(f"\n  Responses with >= 10 zero bytes (of 16): {total_high_zero} out of {len(data_pairs)}")

# Approach 5: What if the TX commands are encrypted but RX data is NOT?
# The 0x57 byte in TX is the unencrypted command.
# The rest of the TX (bytes 1-4) would be encrypted address + checksum
# And the RX is raw data from the radio
print()
print("=" * 80)
print("APPROACH 5: Only TX is encrypted, RX is raw radio data")
print("=" * 80)

# If TX format is [0x57][encrypted: addr_hi, addr_lo, 0x00, checksum]
# and the cipher carries from one TX to the next through both TX and RX bytes:
# This doesn't work because the cipher state depends on what was sent AND received

# Actually, maybe TX and RX have SEPARATE cipher states?
# Or maybe only the "send" direction is encrypted?

# Let's look at this from the radio's perspective:
# The radio receives encrypted commands and sends back encrypted responses
# OR: commands are encrypted, responses are raw

# Key observation: ALL RX responses start with 0x57
# If this is unencrypted, it's the command echo
# If encrypted, 0x57 would need to decrypt to something...

# Let me check: do TX command addresses make sense if we decrypt only bytes 1-4?
print("Trying: TX bytes 1-4 encrypted independently per packet")
for init_key in range(256):
    results = []
    for j, (tx, rx) in enumerate(data_pairs[:20]):
        key = init_key
        dec_addr = bytearray()
        for i in range(1, len(tx)):
            enc = tx[i]
            dec = enc ^ key
            key = (key + enc) & 0xFF
            dec_addr.append(dec)
        results.append(dec_addr)

    # Check if first bytes are sequential
    byte0_vals = [r[0] for r in results]
    is_seq = all(byte0_vals[i] == i for i in range(min(18, len(byte0_vals))))

    if is_seq:
        print(f"\n  key=0x{init_key:02x}: TX addresses are sequential!")
        for j, r in enumerate(results[:10]):
            print(f"    TX[{j}] decrypted addr: {' '.join(f'{b:02x}' for b in r)}")

print()
print("Trying: TX bytes 1-4 encrypted with key carrying through RX too")
for init_key in range(256):
    key = init_key
    tx_results = []

    for d, data in data_txns:
        dec = bytearray()
        dec.append(data[0])
        for i in range(1, len(data)):
            enc = data[i]
            dec_byte = enc ^ key
            key = (key + enc) & 0xFF
            dec.append(dec_byte)

        if d == 'TX' and len(data) == 5:
            tx_results.append(dec)

    if len(tx_results) >= 10:
        byte1_vals = [r[1] for r in tx_results[:20]]
        is_seq = all(byte1_vals[i] == i for i in range(min(10, len(byte1_vals))))
        if is_seq:
            print(f"\n  key=0x{init_key:02x}: Sequential after both TX+RX feed key!")
            for j, r in enumerate(tx_results[:10]):
                print(f"    TX[{j}]: {' '.join(f'{b:02x}' for b in r)}")
            rx_results = [(d, data) for d, data in zip([d for d,_ in data_txns],
                          [bytearray([data[0]] + [0]*19) for _,data in data_txns])
                         if d == 'RX']
