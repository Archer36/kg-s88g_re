"""
merge_la.py — Merge PC-TX and RDO-TX logic analyser dumps into a single
time-ordered byte stream, then compare against a PCAP capture.

Usage:
    python merge_la.py                          # merge + print annotated stream
    python merge_la.py --pcap <capture.pcapng>  # also compare against PCAP

Requirements:
    pip install pyshark   (only needed for --pcap comparison)
"""

import csv
import argparse
import sys
from pathlib import Path

LA_DIR = Path(__file__).parent
PC_TX  = LA_DIR / "PC-TX.csv"
RDO_TX = LA_DIR / "RDO-TX.csv"

# ── Rolling XOR cipher (same algorithm as the CHIRP driver) ──────────────────

class RollingXOR:
    def __init__(self, key=0x00):
        self.key = key

    def process(self, data, skip_first=True):
        """Decrypt/encrypt bytes. Byte 0 is passed through unmodified."""
        result = bytearray()
        for i, byte in enumerate(data):
            if i == 0 and skip_first:
                result.append(byte)
            else:
                result.append(byte ^ self.key)
                self.key = (self.key + byte) & 0xFF
        return bytes(result)


# ── CSV loading ───────────────────────────────────────────────────────────────

def load_csv(path, direction):
    """Return list of (timestamp_float, byte_int, direction_str)."""
    rows = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Framing Error') or row.get('Parity Error'):
                print(f"  WARNING: error flag at t={row['Time [s]']} in {path.name}",
                      file=sys.stderr)
            ts  = float(row['Time [s]'])
            val = int(row['Value'], 16)
            rows.append((ts, val, direction))
    return rows


# ── Merge and sort ────────────────────────────────────────────────────────────

def merge(pc_path=PC_TX, rdo_path=RDO_TX):
    pc  = load_csv(pc_path,  'PC->RDO')
    rdo = load_csv(rdo_path, 'RDO->PC ')
    merged = sorted(pc + rdo, key=lambda r: r[0])
    return merged


# ── Pretty-print with optional decryption ────────────────────────────────────

HANDSHAKE_LABELS = {
    # PC -> radio
    'PC->RDO': [
        (8,  'Magic packet (plaintext)'),
        (16, 'Key material (plaintext)'),
        (1,  'ACK'),
        (1,  'ACK'),
    ],
    # Radio -> PC
    'RDO->PC ': [
        (1,  'ACK'),
        (12, 'Radio identity (plaintext)'),
        (18, 'Key response (plaintext)'),
        (1,  'Final ACK'),
    ],
}

def print_stream(merged, decrypt=True, max_data_blocks=5):
    """
    Print the merged stream grouped into logical messages.
    Handshake is shown plaintext. Data phase is decrypted and annotated.
    max_data_blocks: how many data-phase blocks to print before summarising.
    """
    pc_count  = {label: 0 for label in HANDSHAKE_LABELS['PC->RDO']}
    rdo_count = {label: 0 for label in HANDSHAKE_LABELS['RDO->PC ']}

    # Split into PC and RDO streams to track handshake state independently
    pc_bytes  = [(ts, v) for ts, v, d in merged if d == 'PC->RDO']
    rdo_bytes = [(ts, v) for ts, v, d in merged if d == 'RDO->PC ']

    cipher = RollingXOR(0x00)
    data_phase_block = 0

    # We'll walk the merged stream, reconstructing packets as we go
    # ── Handshake ─────────────────────────────────────────────────────────────
    print("\n=== HANDSHAKE (plaintext) ===\n")

    def take(stream, n, label, direction):
        chunk = stream[:n]
        del stream[:n]
        ts_start = chunk[0][0]
        ts_end   = chunk[-1][0]
        hex_str  = ' '.join(f'{v:02X}' for _, v in chunk)
        ascii_str = ''.join(chr(v) if 32 <= v < 127 else '.' for _, v in chunk)
        print(f"  t={ts_start:.6f}  {direction}  [{label}]")
        print(f"    hex:   {hex_str}")
        print(f"    ascii: {ascii_str}")
        print()
        return [v for _, v in chunk]

    pc_stream  = list(pc_bytes)
    rdo_stream = list(rdo_bytes)

    # Step 1: PC sends magic (8 bytes)
    take(pc_stream,  8,  'Magic packet',        'PC->RDO')
    # Step 2: Radio ACKs (1 byte)
    take(rdo_stream, 1,  'ACK',                 'RDO->PC ')
    # Step 3: PC sends key material (16 bytes)
    km = take(pc_stream, 16, 'Key material',    'PC->RDO')
    derived_key = km[1] ^ km[3]
    print(f"  [Key material] km[1]=0x{km[1]:02X}  km[3]=0x{km[3]:02X}  "
          f"derived key = km[1] XOR km[3] = 0x{derived_key:02X}\n")
    # Step 4: Radio sends identity (12 bytes)
    take(rdo_stream, 12, 'Radio identity',      'RDO->PC ')
    # Step 5: PC ACKs (1 byte)
    take(pc_stream,  1,  'ACK',                 'PC->RDO')
    # Step 6: Radio sends key response (18 bytes)
    take(rdo_stream, 18, 'Key response',        'RDO->PC ')
    # Step 7: PC ACKs (1 byte)
    take(pc_stream,  1,  'ACK',                 'PC->RDO')
    # Step 8: Radio final ACK (1 byte)
    take(rdo_stream, 1,  'Final ACK',           'RDO->PC ')

    # Re-init cipher with derived key
    cipher = RollingXOR(derived_key)

    # ── Data phase ────────────────────────────────────────────────────────────
    print(f"=== DATA PHASE (key=0x{derived_key:02X}, rolling XOR) ===\n")

    block = 0
    while len(pc_stream) >= 5:
        # PC sends 5-byte read command
        cmd_raw  = [v for _, v in pc_stream[:5]]
        del pc_stream[:5]
        cmd_dec  = cipher.process(bytes(cmd_raw))
        addr     = (cmd_dec[1] << 16) | (cmd_dec[2] << 8) | cmd_dec[3]
        cmd_hex  = ' '.join(f'{b:02X}' for b in cmd_raw)
        cmd_dhex = ' '.join(f'{b:02X}' for b in cmd_dec)

        # Radio sends 21-byte response
        if len(rdo_stream) < 21:
            break
        rsp_raw = [v for _, v in rdo_stream[:21]]
        del rdo_stream[:21]
        rsp_dec = cipher.process(bytes(rsp_raw))
        data    = rsp_dec[5:]
        rsp_hex  = ' '.join(f'{b:02X}' for b in rsp_raw)
        rsp_dhex = ' '.join(f'{b:02X}' for b in rsp_dec)
        data_hex = ' '.join(f'{b:02X}' for b in data)

        if block < max_data_blocks:
            print(f"  Block {block:03d}  addr=0x{addr:06X}")
            print(f"    TX enc:  {cmd_hex}")
            print(f"    TX dec:  {cmd_dhex}")
            print(f"    RX enc:  {rsp_hex}")
            print(f"    RX dec:  {rsp_dhex}")
            print(f"    data:    {data_hex}")
            print()
        elif block == max_data_blocks:
            remaining = len(pc_stream) // 5
            print(f"  ... ({remaining + 1} more blocks, use --all to show all) ...\n")

        block += 1

    # Terminate byte
    if pc_stream:
        term_raw = [v for _, v in pc_stream[:1]]
        term_dec = cipher.process(bytes(term_raw))
        print(f"  Terminate: enc=0x{term_raw[0]:02X}  dec=0x{term_dec[0]:02X}")

    print(f"\n  Total blocks: {block}")
    print(f"  EEPROM bytes covered: {block * 16} (0x0000–0x{block*16-1:04X})")


# ── PCAP comparison ───────────────────────────────────────────────────────────

def compare_pcap(pcap_path, la_merged):
    """Extract bytes from a PCAP and compare against LA byte stream."""
    try:
        import pyshark
    except ImportError:
        print("pyshark not installed. Run: pip install pyshark", file=sys.stderr)
        return

    print(f"\n=== PCAP COMPARISON: {pcap_path} ===\n")

    cap = pyshark.FileCapture(
        pcap_path,
        display_filter='(usb.endpoint_address == 0x01 || usb.endpoint_address == 0x81) and usb.capdata'
    )

    pcap_bytes = []
    for pkt in cap:
        try:
            direction = 'PC->RDO' if 'host' in str(pkt.usb.src).lower() else 'RDO->PC '
            raw = bytes.fromhex(pkt.usb.capdata.replace(':', ''))
            for b in raw:
                pcap_bytes.append((direction, b))
        except AttributeError:
            pass
    cap.close()

    la_flat = [(d, v) for _, v, d in la_merged]

    print(f"  LA bytes:   {len(la_flat)}")
    print(f"  PCAP bytes: {len(pcap_bytes)}")

    mismatches = 0
    for i, ((la_dir, la_val), (pcap_dir, pcap_val)) in enumerate(
            zip(la_flat, pcap_bytes)):
        if la_val != pcap_val or la_dir != pcap_dir:
            print(f"  MISMATCH at byte {i}: "
                  f"LA={la_dir} 0x{la_val:02X}  PCAP={pcap_dir} 0x{pcap_val:02X}")
            mismatches += 1
            if mismatches > 20:
                print("  (too many mismatches, stopping)")
                break

    if mismatches == 0 and len(la_flat) == len(pcap_bytes):
        print("  MATCH — LA dump and PCAP are identical byte-for-byte.")
    elif mismatches == 0:
        print(f"  No byte mismatches but lengths differ "
              f"(LA={len(la_flat)}, PCAP={len(pcap_bytes)}).")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Merge and analyse LA dumps')
    parser.add_argument('--pcap',  metavar='FILE', help='PCAP file to compare against')
    parser.add_argument('--all',   action='store_true', help='Print all data-phase blocks')
    parser.add_argument('--csv',   metavar='FILE', help='Write merged stream to CSV')
    args = parser.parse_args()

    print("Loading LA dumps...")
    merged = merge()
    pc_count  = sum(1 for _, _, d in merged if d == 'PC->RDO')
    rdo_count = sum(1 for _, _, d in merged if d == 'RDO->PC ')
    print(f"  PC->RDO: {pc_count} bytes   RDO->PC: {rdo_count} bytes   total: {len(merged)}")

    max_blocks = 999999 if args.all else 5
    print_stream(merged, decrypt=True, max_data_blocks=max_blocks)

    if args.csv:
        out = Path(args.csv)
        with open(out, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['time_s', 'direction', 'value_hex', 'value_dec'])
            for ts, val, direction in merged:
                writer.writerow([f'{ts:.9f}', direction, f'0x{val:02X}', val])
        print(f"\nMerged stream written to {out}")

    if args.pcap:
        compare_pcap(args.pcap, merged)


if __name__ == '__main__':
    main()
