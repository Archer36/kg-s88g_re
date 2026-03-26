"""
pcap_to_img.py — Convert a KG-S88G USB capture into a CHIRP-compatible .img file.

The output .img file can be opened directly in CHIRP:
    File > Open > select the .img file > choose Wouxun KG-S88G

Requirements:
    Wireshark/tshark must be installed and on PATH (or provide path via --tshark).

Usage:
    python pcap_to_img.py <capture.pcapng> [output.img]
    python pcap_to_img.py <capture.pcapng> [output.img] --tshark "C:/Program Files/Wireshark/tshark.exe"

Examples:
    python pcap_to_img.py PCAPs/stock-read-from-radio.pcapng
    python pcap_to_img.py PCAPs/stock-read-from-radio.pcapng stock.img
"""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

EEPROM_SIZE = 0x27D0   # bytes read/written by CHIRP driver


# ── Rolling XOR cipher ────────────────────────────────────────────────────────

def decrypt_stream(data, key, skip_first=True):
    """Decrypt bytes using the KG-S88G rolling XOR cipher.

    key   : starting cipher key byte
    skip_first: byte 0 of each packet is plaintext and does not advance the key
    Returns (decrypted_bytes, new_key)
    """
    result = bytearray()
    for i, byte in enumerate(data):
        if i == 0 and skip_first:
            result.append(byte)
        else:
            result.append(byte ^ key)
            key = (key + byte) & 0xFF
    return bytes(result), key


# ── PCAP extraction via tshark ─────────────────────────────────────────────────

def extract_transactions(pcap_path, tshark='tshark'):
    """Use tshark to extract USB frames and return list of (direction, bytes)."""
    cmd = [
        tshark,
        '-r', str(pcap_path),
        '-Y', '(usb.endpoint_address == 0x01 || usb.endpoint_address == 0x81)'
              ' and usb.capdata',
        '-T', 'fields',
        '-e', 'frame.number',
        '-e', 'usb.src',
        '-e', 'usb.dst',
        '-e', 'usb.capdata',
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        print(f"ERROR: tshark not found at '{tshark}'.")
        print("Install Wireshark or provide the path with --tshark.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: tshark failed: {e.stderr.strip()}")
        sys.exit(1)

    transactions = []
    current_dir = None
    current_bytes = bytearray()

    for line in result.stdout.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 4 or not parts[3]:
            continue
        _, src, _, capdata = parts
        raw = bytes.fromhex(capdata.replace(':', ''))
        direction = 'TX' if 'host' in src.lower() else 'RX'

        if direction != current_dir and current_bytes:
            transactions.append((current_dir, bytes(current_bytes)))
            current_bytes = bytearray()

        current_dir = direction
        current_bytes.extend(raw)

    if current_bytes:
        transactions.append((current_dir, bytes(current_bytes)))

    return transactions


# ── Handshake parsing ─────────────────────────────────────────────────────────

def parse_handshake(transactions):
    """Parse the 8-step handshake and return (data_phase_key, data_start_idx).

    Raises ValueError if handshake structure is not recognised.
    """
    # Expected handshake layout (transaction indices 0-7):
    #   0  TX  8B   magic packet  (02 RWITF/WRITF FF FF)
    #   1  RX  1B   ACK (06)
    #   2  TX  16B  key material  (A5 ...)
    #   3  RX  12B  radio identity
    #   4  TX  1B   ACK
    #   5  RX  18B  key response
    #   6  TX  1B   ACK
    #   7  RX  1B   final ACK (06)

    if len(transactions) < 9:
        raise ValueError(f"Too few transactions ({len(transactions)}) — not a complete session")

    dir0, data0 = transactions[0]
    if dir0 != 'TX' or len(data0) != 8 or data0[0] != 0x02:
        raise ValueError("Transaction 0 does not look like a magic packet")

    magic = data0[1:6]
    if magic not in (b'RWITF', b'WRITF'):
        raise ValueError(f"Unrecognised magic: {magic}")

    operation = 'READ' if magic == b'RWITF' else 'WRITE'

    dir2, km = transactions[2]
    if dir2 != 'TX' or len(km) != 16 or km[0] != 0xA5:
        raise ValueError("Transaction 2 does not look like key material")

    data_phase_key = km[1] ^ km[3]

    print(f"  Operation  : {operation}")
    print(f"  Magic      : {magic.decode()}")
    print(f"  km[1]=0x{km[1]:02X}  km[3]=0x{km[3]:02X}  "
          f"data_phase_key = 0x{data_phase_key:02X}")

    return data_phase_key, operation, 8   # data phase starts at index 8


# ── EEPROM reconstruction ─────────────────────────────────────────────────────

def reconstruct_eeprom(transactions, data_start, key, operation):
    """Decrypt data-phase transactions and reconstruct the EEPROM image.

    For READ sessions: extract 16-byte payloads from decrypted RX packets.
    For WRITE sessions: extract 16-byte payloads from decrypted TX packets.
    Returns bytearray of EEPROM_SIZE bytes (0xFF for any unread regions).
    """
    eeprom = bytearray(b'\xff' * EEPROM_SIZE)
    blocks_found = 0
    addresses = []

    for direction, data in transactions[data_start:]:
        dec, key = decrypt_stream(data, key)

        if operation == 'READ' and direction == 'RX' and len(dec) == 21 and dec[0] == 0x57:
            addr = (dec[1] << 16) | (dec[2] << 8) | dec[3]
            payload = dec[5:]
        elif operation == 'WRITE' and direction == 'TX' and len(dec) == 21 and dec[0] == 0x57:
            addr = (dec[1] << 16) | (dec[2] << 8) | dec[3]
            payload = dec[5:]
        else:
            continue

        if addr + 16 <= EEPROM_SIZE:
            eeprom[addr:addr + 16] = payload
            addresses.append(addr)
            blocks_found += 1

    if not addresses:
        raise ValueError("No valid EEPROM blocks found — wrong operation type or corrupted capture?")

    print(f"  Blocks     : {blocks_found}")
    print(f"  Addr range : 0x{min(addresses):04X} – 0x{max(addresses):04X}")

    gaps = []
    for i in range(1, len(sorted(addresses))):
        s = sorted(addresses)
        if s[i] != s[i-1] + 0x10:
            gaps.append((s[i-1], s[i]))
    if gaps:
        print(f"  WARNING: {len(gaps)} address gap(s) found — capture may be incomplete")

    return eeprom


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Convert a KG-S88G USB capture (.pcapng) to a CHIRP .img file')
    parser.add_argument('pcap', help='Input capture file (.pcapng)')
    parser.add_argument('img',  nargs='?', help='Output .img file (default: <pcap>.img)')
    parser.add_argument('--tshark', default='tshark',
                        help='Path to tshark executable (default: tshark)')
    args = parser.parse_args()

    pcap_path = Path(args.pcap)
    if not pcap_path.exists():
        print(f"ERROR: {pcap_path} not found")
        sys.exit(1)

    img_path = Path(args.img) if args.img else pcap_path.with_suffix('.img')

    print(f"Input  : {pcap_path}")
    print(f"Output : {img_path}")
    print()

    print("Extracting USB frames with tshark...")
    transactions = extract_transactions(pcap_path, args.tshark)
    print(f"  Transactions: {len(transactions)}")
    print()

    print("Parsing handshake...")
    try:
        key, operation, data_start = parse_handshake(transactions)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print()

    print("Reconstructing EEPROM...")
    try:
        eeprom = reconstruct_eeprom(transactions, data_start, key, operation)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print()

    # Append CHIRP metadata header so CHIRP can auto-identify the radio.
    # Format: raw EEPROM bytes + magic + base64(JSON metadata)
    CHIRP_MAGIC = b'\x00\xffchirp\xeeimg\x00\x01'
    metadata = json.dumps({
        'rclass': 'KGS88GRadio',
        'vendor': 'Wouxun',
        'model': 'KG-S88G',
        'variant': '',
        'chirp_version': 'daily-20230101',
    }).encode()

    with img_path.open('wb') as f:
        f.write(eeprom)
        f.write(CHIRP_MAGIC)
        f.write(base64.b64encode(metadata))

    print(f"Saved {len(eeprom)} bytes + CHIRP metadata to {img_path}")
    print()
    print("To open in CHIRP:")
    print("  File > Open > select the .img file")


if __name__ == '__main__':
    main()
