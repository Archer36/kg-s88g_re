#!/usr/bin/env python3
"""
Decrypt and analyze a CHIRP KG-S88G write capture.
Extracts channel data and compares frequencies/tones vs CPS write.
"""
import subprocess
import sys

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"

def parse_pcap(path):
    cmd = [
        TSHARK, '-r', path,
        '-Y', '(usb.endpoint_address == 0x01 || usb.endpoint_address == 0x81) and (usb.capdata)',
        '-T', 'fields',
        '-e', 'frame.number', '-e', 'usb.src', '-e', 'usb.dst', '-e', 'usb.capdata',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
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
    start = 1 if skip_first else 0
    for i in range(start, len(data)):
        key = (key + data[i]) & 0xFF
    return key

def decrypt(data, key):
    out = bytearray([data[0]])
    for i in range(1, len(data)):
        enc = data[i]
        out.append(enc ^ key)
        key = (key + enc) & 0xFF
    return bytes(out), key

def lbcd_to_hz(bcd_bytes):
    """Convert 4-byte little-endian BCD to frequency in Hz."""
    val = 0
    for i in range(len(bcd_bytes)-1, -1, -1):
        b = bcd_bytes[i]
        val = val * 100 + ((b >> 4) & 0xF) * 10 + (b & 0xF)
    return val * 10  # result is in 10Hz units -> Hz

def decode_tone(tmode, tone_byte):
    CTCSS = [
        67.0, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8,
        97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8,
        136.5, 141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8, 179.9, 186.2,
        192.8, 203.5, 210.7, 218.1, 225.7, 233.6, 241.8, 250.3,
    ]
    DCS = list(range(1, 105))  # placeholder

    if tmode == 0:
        return "none"
    elif tmode == 1:
        idx = tone_byte
        if idx < len(CTCSS):
            return f"CTCSS {CTCSS[idx]}"
        return f"CTCSS idx={idx}"
    elif tmode == 2:
        return f"DCS {tone_byte:03o}"
    return f"tmode={tmode} tone={tone_byte:#04x}"

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Brett\git-repos\gh\chirp\kg-s88g-dev\home-write-to-radio-from-chirp.pcapng"
    txs = parse_pcap(path)

    print(f"Total transactions: {len(txs)}")
    print("\nHandshake:")
    for i, (d, data) in enumerate(txs[:8]):
        print(f"  [{i}] {'TX' if d=='TX' else 'RX'} ({len(data)}b): {data.hex()}")

    # Determine key from handshake
    # TX[2] = key material, skip first byte
    # RX[3] = identity response, skip first
    # RX[5] = key response, skip first
    key = 0
    key = rolling_key_after(txs[2][1], key, skip_first=True)
    key = rolling_key_after(txs[3][1], key, skip_first=True)
    key = rolling_key_after(txs[5][1], key, skip_first=True)
    print(f"\nDerived data-phase key: {key:#04x}")

    # Decrypt all data transactions (skip handshake = first 8)
    # Build full EEPROM image from write commands
    eeprom = bytearray(0x2800)

    k = key
    channels_written = {}

    for i, (d, data) in enumerate(txs[8:], start=8):
        if d == 'TX':
            dec, k = decrypt(data, k)
            if len(dec) == 21 and dec[0] == 0x57:
                addr = (dec[1] << 16) | (dec[2] << 8) | dec[3]
                length = dec[4]
                payload = dec[5:5+length]
                if addr + length <= len(eeprom):
                    eeprom[addr:addr+length] = payload
        elif d == 'RX':
            # ACKs are unencrypted single bytes
            pass

    print("\n=== CHANNELS (from CHIRP write) ===")
    print(f"{'CH':>3}  {'RX MHz':>12}  {'TX MHz':>12}  {'RX Tone':>15}  {'TX Tone':>15}  {'Power':>5}  {'Wide':>4}")
    for ch in range(1, 401):
        off = 0x0100 + ch * 16
        rec = eeprom[off:off+16]
        rx_hz = lbcd_to_hz(rec[0:4])
        if rx_hz == 0 or all(b == 0xFF for b in rec[0:4]):
            continue
        tx_hz = lbcd_to_hz(rec[4:8])
        rx_tmode = rec[8]
        rx_tone  = rec[9]
        tx_tmode = rec[10]
        tx_tone  = rec[11]
        flags1   = rec[12]
        flags2   = rec[13]
        flags3   = rec[14]
        highpower = (flags1 >> 7) & 1
        wide      = flags3 & 1
        call_id   = (flags2 >> 3) & 0x1F
        rx_mhz = rx_hz / 1e6
        tx_mhz = tx_hz / 1e6
        rx_tone_s = decode_tone(rx_tmode, rx_tone)
        tx_tone_s = decode_tone(tx_tmode, tx_tone)
        print(f"{ch:>3}  {rx_mhz:>12.5f}  {tx_mhz:>12.5f}  {rx_tone_s:>15}  {tx_tone_s:>15}  {'H' if highpower else 'L':>5}  {'W' if wide else 'N':>4}  call_id={call_id}")

    print("\n=== CHANNEL BITMAP (0x2500) ===")
    bitmap = eeprom[0x2500:0x2550]
    active = []
    for byte_idx, b in enumerate(bitmap):
        for bit in range(8):
            if b & (1 << bit):
                ch = byte_idx * 8 + bit
                active.append(ch)
    print(f"  Active channels: {active}")
    print(f"  Raw: {bitmap[:10].hex()} ...")

    print("\n=== CHANNEL BITMAP (0x2600) ===")
    bitmap2 = eeprom[0x2600:0x2650]
    active2 = []
    for byte_idx, b in enumerate(bitmap2):
        for bit in range(8):
            if b & (1 << bit):
                ch = byte_idx * 8 + bit
                active2.append(ch)
    print(f"  Active channels: {active2}")
    print(f"  Raw: {bitmap2[:10].hex()} ...")

if __name__ == '__main__':
    main()
