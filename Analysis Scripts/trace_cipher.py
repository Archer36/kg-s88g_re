#!/usr/bin/env python3
"""
Trace the rolling XOR cipher through handshake to find key derivation.

We know:
  download capture   -> data phase key = 0x4c
  stock-read capture -> data phase key = 0x00
  stock-write capture -> data phase key = 0xe6

Goal: figure out which handshake bytes go through the cipher, and in what
order, to reproduce those keys.
"""

import subprocess
import sys
import itertools

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"

CAPTURES = {
    'download':     r"C:\Users\Brett\git-repos\gh\chirp\kg-s88g-dev\download.pcapng",
    'stock-read':   r"C:\Users\Brett\git-repos\gh\chirp\kg-s88g-dev\stock-read-from-radio.pcapng",
    'stock-write':  r"C:\Users\Brett\git-repos\gh\chirp\kg-s88g-dev\stock-write-to-radio.pcapng",
    'home-dl2':     r"C:\Users\Brett\git-repos\gh\chirp\kg-s88g-dev\home-download-2.pcapng",
}

# Known data-phase starting keys (brute forced previously)
KNOWN_KEYS = {
    'download':   0x4c,
    'stock-read': 0x00,
    # stock-write: 0xe6  (will verify)
}


def parse_pcap(path):
    """Return list of (direction, bytes) transactions."""
    cmd = [
        TSHARK, '-r', path,
        '-Y', '(usb.endpoint_address == 0x01 || usb.endpoint_address == 0x81) and (usb.capdata)',
        '-T', 'fields',
        '-e', 'frame.number', '-e', 'usb.src', '-e', 'usb.dst', '-e', 'usb.capdata',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"tshark error for {path}: {result.stderr[:200]}")
        return []

    transactions = []
    current_dir = None
    current_bytes = bytearray()

    for line in result.stdout.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 4:
            continue
        src, capdata = parts[1], parts[3]
        raw = bytes.fromhex(capdata.replace(':', ''))
        direction = 'TX' if 'host' in src else 'RX'
        if direction != current_dir and current_bytes:
            transactions.append((current_dir, bytes(current_bytes)))
            current_bytes = bytearray()
        current_dir = direction
        current_bytes.extend(raw)
    if current_bytes:
        transactions.append((current_dir, bytes(current_bytes)))

    return transactions


def rolling_key_after(data, key, skip_first=True):
    """Advance cipher key by processing data bytes. Returns new key."""
    start = 1 if skip_first else 0
    for i in range(start, len(data)):
        enc_byte = data[i]
        key = (key + enc_byte) & 0xFF
    return key


def print_transactions(name, txs):
    print(f"\n=== {name} ({len(txs)} transactions) ===")
    for i, (d, data) in enumerate(txs):
        prefix = "TX" if d == "TX" else "RX"
        hex_str = data.hex()
        print(f"  [{i:2d}] {prefix} ({len(data):3d}b): {hex_str[:80]}{'...' if len(hex_str)>80 else ''}")


def find_data_key_brute(txs, data_start=8):
    """Brute force the data-phase starting key by trying all 256 values."""
    if len(txs) <= data_start:
        return None, None

    # The first data TX is the first 0x57 command
    # Decrypt a few blocks and check if address increments correctly
    for key in range(256):
        k = key
        valid = True
        expected_addr = None
        for d, data in txs[data_start:data_start+10]:
            dec = bytearray([data[0]])
            for i in range(1, len(data)):
                enc = data[i]
                dec.append(enc ^ k)
                k = (k + enc) & 0xFF
            if d == 'TX' and len(dec) == 5 and dec[0] == 0x57:
                addr = (dec[1] << 16) | (dec[2] << 8) | dec[3]
                if expected_addr is None:
                    expected_addr = addr
                elif addr != expected_addr + 0x10:
                    valid = False
                    break
                expected_addr = addr
            elif d == 'RX' and len(dec) == 21 and dec[0] == 0x57:
                pass
            else:
                # unexpected packet size
                pass
        if valid and expected_addr is not None:
            return key, k
    return None, None


def trace_key_variations(txs, initial_key=0):
    """
    Try all possible subsets of handshake transactions (0-7) to find which ones
    go through the cipher to produce the known data-phase key.
    """
    handshake = txs[:8]

    # Try: each byte processed has skip_first True or False
    # But let's first just try processing ALL handshake bytes
    print("\nHandshake transactions:")
    for i, (d, data) in enumerate(handshake):
        print(f"  [{i}] {'TX' if d=='TX' else 'RX'} ({len(data)}b): {data.hex()}")

    print("\nKey trace scenarios:")

    # Scenario A: only TX key material (txs[2]) goes through cipher, skip_first=False
    key = initial_key
    key = rolling_key_after(txs[2][1], key, skip_first=False)  # TX key material
    key = rolling_key_after(txs[3][1], key, skip_first=True)   # RX identity (skip_first)
    key = rolling_key_after(txs[5][1], key, skip_first=True)   # RX key response (skip_first)
    print(f"  [A] TX-keymaterial + RX-identity + RX-keyresp (all skip_first=True) -> key={key:#04x}")

    # Scenario B: TX key material skip_first=True
    key = initial_key
    key = rolling_key_after(txs[2][1], key, skip_first=True)   # TX key material skip_first=True
    key = rolling_key_after(txs[3][1], key, skip_first=True)   # RX identity
    key = rolling_key_after(txs[5][1], key, skip_first=True)   # RX key response
    print(f"  [B] TX-keymaterial(skip)+RX-id+RX-keyresp -> key={key:#04x}")

    # Scenario C: just RX responses
    key = initial_key
    key = rolling_key_after(txs[3][1], key, skip_first=True)
    key = rolling_key_after(txs[5][1], key, skip_first=True)
    print(f"  [C] RX-identity+RX-keyresp only -> key={key:#04x}")

    # Scenario D: RX identity (skip=False) + RX key resp (skip=True)
    key = initial_key
    key = rolling_key_after(txs[3][1], key, skip_first=False)
    key = rolling_key_after(txs[5][1], key, skip_first=True)
    print(f"  [D] RX-identity(no-skip)+RX-keyresp -> key={key:#04x}")

    # Scenario E: brute-force which transactions matter
    # Try all 2^6 combinations of txs[2..7] (skip magic and first ACK)
    target_key = KNOWN_KEYS.get('download')
    if target_key is not None:
        print(f"\n  Brute-forcing which txs[2..7] produce key={target_key:#04x}:")
        indices = [2, 3, 5, 6, 7]  # skip magic(0), ACK(1), ACK(4)
        for mask in range(1 << len(indices)):
            key = initial_key
            for bit, idx in enumerate(indices):
                if mask & (1 << bit):
                    key = rolling_key_after(txs[idx][1], key, skip_first=True)
            if key == target_key:
                included = [indices[b] for b in range(len(indices)) if mask & (1 << b)]
                print(f"    MATCH: use transactions {included}")


def main():
    all_txs = {}
    for name, path in CAPTURES.items():
        print(f"\nParsing {name}...")
        txs = parse_pcap(path)
        all_txs[name] = txs
        print_transactions(name, txs)

        # Brute force the data key
        key, _ = find_data_key_brute(txs)
        if key is not None:
            print(f"  Data-phase starting key (brute forced): {key:#04x}")
            if name not in KNOWN_KEYS:
                KNOWN_KEYS[name] = key
        else:
            print(f"  Could not determine data-phase key")

    print("\n\n=== CIPHER TRACE ANALYSIS ===")
    for name, txs in all_txs.items():
        if len(txs) < 8:
            print(f"\n{name}: too few transactions ({len(txs)})")
            continue
        print(f"\n--- {name} ---")
        trace_key_variations(txs)

    # Cross-capture comparison of key material bytes
    print("\n\n=== KEY MATERIAL COMPARISON (transaction [2] TX) ===")
    for name, txs in all_txs.items():
        if len(txs) > 2:
            d, data = txs[2]
            print(f"  {name:15s} ({d}, {len(data)}b): {data.hex()}")


if __name__ == '__main__':
    main()
