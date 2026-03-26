#!/usr/bin/env python3
"""KG-S88G EEPROM channel decoder.

Decodes channel data from a raw EEPROM binary image.
Can also accept a pcapng file and decrypt it automatically.

Usage:
    python3 eeprom_decode.py <eeprom.bin>
    python3 eeprom_decode.py <capture.pcapng>
"""

import sys
import os
import subprocess
import struct

# === Constants ===

CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,
    94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8
]

DCS_CODES = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53, 54, 65, 71, 72, 73, 74,
    114, 115, 116, 122, 125, 131, 132, 134, 143, 145, 152, 155, 156, 162,
    165, 172, 174, 205, 212, 223, 225, 226, 243, 244, 245, 246, 251, 252,
    255, 261, 263, 265, 266, 271, 274, 306, 311, 315, 325, 331, 332, 343,
    346, 351, 356, 364, 365, 371, 411, 412, 413, 423, 431, 432, 445, 446,
    452, 454, 455, 462, 464, 465, 466, 503, 506, 516, 523, 526, 532, 546,
    565, 606, 612, 624, 627, 631, 632, 654, 662, 664, 703, 712, 723, 731,
    732, 734, 743, 754
]

# EEPROM character encoding: 0-9 = 0x00-0x09, A-Z = 0x0A-0x23
# Special: '-' = 0x24, ' ' = 0x29, empty = 0xFF
def decode_char(b):
    if b == 0xFF:
        return ''
    elif b == 0x29:
        return ' '
    elif b == 0x24:
        return '-'
    elif 0x00 <= b <= 0x09:
        return str(b)
    elif 0x0A <= b <= 0x23:
        return chr(ord('A') + b - 0x0A)
    else:
        return f'?{b:02x}'


def decode_name(data):
    """Decode 6-byte channel name from EEPROM."""
    return ''.join(decode_char(b) for b in data).rstrip()


def decode_freq_bcd_le(data):
    """Decode 4-byte BCD LE frequency to MHz float."""
    bcd_str = f'{data[3]:02x}{data[2]:02x}{data[1]:02x}{data[0]:02x}'
    try:
        return int(bcd_str) / 100000.0
    except ValueError:
        return 0.0


def decode_tone(mode_byte, index_byte):
    """Decode tone mode and index to human-readable string."""
    if mode_byte == 0:
        return "OFF"
    elif mode_byte == 1:
        # CTCSS
        if 1 <= index_byte <= len(CTCSS_TONES):
            return f"CTCSS {CTCSS_TONES[index_byte - 1]:.1f} Hz"
        else:
            return f"CTCSS ?idx={index_byte}"
    elif mode_byte == 2:
        # DCS Normal
        if 1 <= index_byte <= len(DCS_CODES):
            return f"DCS D{DCS_CODES[index_byte - 1]:03d}N"
        else:
            return f"DCS-N ?idx={index_byte}"
    elif mode_byte == 3:
        # DCS Inverted
        if 1 <= index_byte <= len(DCS_CODES):
            return f"DCS D{DCS_CODES[index_byte - 1]:03d}I"
        else:
            return f"DCS-I ?idx={index_byte}"
    else:
        return f"?mode={mode_byte}"


def decode_channel(freq_data, name_data=None):
    """Decode a channel from 16 bytes of frequency data + optional 6 bytes name."""
    if freq_data == b'\xff' * 16:
        return None

    rx_freq = decode_freq_bcd_le(freq_data[0:4])
    tx_freq = decode_freq_bcd_le(freq_data[4:8])

    rx_tone = decode_tone(freq_data[8], freq_data[9])
    tx_tone = decode_tone(freq_data[10], freq_data[11])

    # Settings byte 12 (Settings A)
    settings_a = freq_data[12]
    power = "High" if (settings_a & 0x01) else "Low"
    descramble = (settings_a >> 2) & 0x0F
    descramble_str = "OFF" if descramble == 0 else str(descramble)
    sp_mute = (settings_a >> 6) & 0x03
    sp_mute_str = ["QT", "QT*DT", "QT+DT"][sp_mute] if sp_mute < 3 else f"?{sp_mute}"

    # Settings byte 13 (Settings B)
    settings_b = freq_data[13]
    busy_lock = "ON" if (settings_b & 0x01) else "OFF"
    call_id = settings_b >> 3

    # Settings byte 14 (Settings C)
    settings_c = freq_data[14]
    bandwidth = "Wide" if (settings_c & 0x01) else "Narrow"

    # Settings byte 15 (Settings D)
    settings_d = freq_data[15]

    name = decode_name(name_data) if name_data and name_data != b'\xff' * 6 else ""

    offset = tx_freq - rx_freq
    if abs(offset) < 0.001:
        duplex = "Simplex"
    elif offset > 0:
        duplex = f"+{offset:.4f}"
    else:
        duplex = f"{offset:.4f}"

    return {
        'rx_freq': rx_freq,
        'tx_freq': tx_freq,
        'rx_tone': rx_tone,
        'tx_tone': tx_tone,
        'power': power,
        'bandwidth': bandwidth,
        'descramble': descramble_str,
        'sp_mute': sp_mute_str,
        'busy_lock': busy_lock,
        'call_id': call_id,
        'duplex': duplex,
        'name': name,
        'raw_freq': freq_data.hex(),
        'settings_d': settings_d,
    }


def decrypt_pcapng(pcap_path):
    """Decrypt a pcapng capture and return EEPROM binary data."""
    tshark = '/Applications/Wireshark.app/Contents/MacOS/tshark'
    if not os.path.exists(tshark):
        # Try system tshark
        tshark = 'tshark'

    cmd = [
        tshark, '-r', pcap_path,
        '-Y', '(usb.endpoint_address == 0x01 || usb.endpoint_address == 0x81) and (usb.capdata)',
        '-T', 'fields', '-e', 'frame.number', '-e', 'usb.src',
        '-e', 'usb.dst', '-e', 'usb.capdata',
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"tshark error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Reconstruct transactions
    transactions = []
    current_dir = None
    current_bytes = bytearray()

    for line in result.stdout.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 4:
            continue
        src, capdata = parts[1], parts[3]
        raw_bytes = bytes.fromhex(capdata.replace(':', ''))
        direction = 'TX' if 'host' in src else 'RX'
        if direction != current_dir and current_bytes:
            transactions.append((current_dir, bytes(current_bytes)))
            current_bytes = bytearray()
        current_dir = direction
        current_bytes.extend(raw_bytes)
    if current_bytes:
        transactions.append((current_dir, bytes(current_bytes)))

    # Data transfer starts at transaction 8
    DATA_START = 8
    key = 0x4c

    # Decrypt
    eeprom = bytearray(b'\xff' * 0x10000)
    for d, data in transactions[DATA_START:]:
        dec = bytearray([data[0]])
        for i in range(1, len(data)):
            enc_byte = data[i]
            dec.append(enc_byte ^ key)
            key = (key + enc_byte) & 0xFF

        if d == 'TX' and len(dec) == 5 and dec[0] == 0x57:
            pass  # TX command, skip
        elif d == 'RX' and len(dec) == 21 and dec[0] == 0x57:
            addr = (dec[1] << 16) | (dec[2] << 8) | dec[3]
            payload = dec[5:]
            for j, b in enumerate(payload):
                if addr + j < len(eeprom):
                    eeprom[addr + j] = b

    # Find actual end
    last_nonff = 0
    for i in range(len(eeprom) - 1, -1, -1):
        if eeprom[i] != 0xff:
            last_nonff = i
            break

    return bytes(eeprom[:last_nonff + 1])


def load_eeprom(path):
    """Load EEPROM data from .bin or .pcapng file."""
    if path.endswith('.pcapng') or path.endswith('.pcap'):
        print(f"Decrypting capture: {path}")
        return decrypt_pcapng(path)
    else:
        with open(path, 'rb') as f:
            return f.read()


# === EEPROM Layout ===
# Channel frequency data: 0x0100 + (ch * 16), 400 channels (ch 0-399)
#   But channel 0 (0x0100) appears to be unused/special
#   Channels are numbered 1-400 in the radio, stored at 0x0110 onwards
# Channel names: 0x1B00 + (ch * 6), 400 names
# Settings: 0x0000-0x00FF

CHANNEL_FREQ_BASE = 0x0100  # channel 0 at 0x0100, channel 1 at 0x0110, etc.
CHANNEL_NAME_BASE = 0x1B00  # channel 0 name at 0x1B00, channel 1 name at 0x1B06, etc.
MAX_CHANNELS = 400


def get_channel(eeprom, ch_num):
    """Get channel data. ch_num is 1-based (1-400)."""
    if ch_num < 1 or ch_num > MAX_CHANNELS:
        return None

    freq_offset = CHANNEL_FREQ_BASE + ch_num * 16
    name_offset = CHANNEL_NAME_BASE + ch_num * 6

    if freq_offset + 16 > len(eeprom):
        return None

    freq_data = eeprom[freq_offset:freq_offset + 16]
    name_data = eeprom[name_offset:name_offset + 6] if name_offset + 6 <= len(eeprom) else None

    return decode_channel(freq_data, name_data)


def print_channel(ch_num, ch):
    """Pretty-print channel data."""
    if ch is None:
        print(f"  Channel {ch_num}: EMPTY")
        return

    name_str = f' "{ch["name"]}"' if ch['name'] else ''
    print(f"  Channel {ch_num}{name_str}:")
    print(f"    RX Freq:    {ch['rx_freq']:.5f} MHz")
    print(f"    TX Freq:    {ch['tx_freq']:.5f} MHz  ({ch['duplex']})")
    print(f"    RX Tone:    {ch['rx_tone']}")
    print(f"    TX Tone:    {ch['tx_tone']}")
    print(f"    Power:      {ch['power']}")
    print(f"    Bandwidth:  {ch['bandwidth']}")
    print(f"    Descramble: {ch['descramble']}")
    print(f"    SP Mute:    {ch['sp_mute']}")
    print(f"    Busy Lock:  {ch['busy_lock']}")
    if ch['call_id']:
        print(f"    Call ID:    {ch['call_id']}")
    print(f"    Raw bytes:  {ch['raw_freq']}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 eeprom_decode.py <eeprom.bin|capture.pcapng>")
        print("\nDecodes KG-S88G EEPROM channel data.")
        print("Accepts raw EEPROM binary or Wireshark pcapng capture.")
        sys.exit(1)

    eeprom = load_eeprom(sys.argv[1])
    print(f"EEPROM size: {len(eeprom)} bytes")

    # Show VFO (offset 0x0000)
    if len(eeprom) >= 16:
        vfo = decode_channel(eeprom[0:16])
        if vfo:
            print(f"\nVFO/Current:")
            print_channel(0, vfo)

    # Show summary of programmed channels
    print(f"\nProgrammed channels:")
    programmed = []
    for ch in range(1, MAX_CHANNELS + 1):
        ch_data = get_channel(eeprom, ch)
        if ch_data:
            programmed.append(ch)

    if programmed:
        print(f"  Found {len(programmed)} programmed channel(s): {programmed}")
    else:
        print("  No programmed channels found.")

    # Interactive loop
    print(f"\nEnter channel number (1-{MAX_CHANNELS}) to decode, 'all' for all, or 'q' to quit:")
    while True:
        try:
            inp = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if inp.lower() in ('q', 'quit', 'exit'):
            break
        elif inp.lower() == 'all':
            for ch in programmed:
                ch_data = get_channel(eeprom, ch)
                print_channel(ch, ch_data)
                print()
        elif inp.lower() == 'settings':
            print("\nSettings area (0x0000-0x007F):")
            for offset in range(0, min(0x80, len(eeprom)), 16):
                chunk = eeprom[offset:offset + 16]
                hex_part = ' '.join(f'{b:02x}' for b in chunk)
                print(f"  {offset:04x}: {hex_part}")
        elif inp.lower().startswith('raw '):
            # Show raw hex at an offset
            try:
                addr = int(inp.split()[1], 0)
                size = int(inp.split()[2], 0) if len(inp.split()) > 2 else 64
                print(f"\nRaw data at 0x{addr:04x} ({size} bytes):")
                for offset in range(addr, min(addr + size, len(eeprom)), 16):
                    chunk = eeprom[offset:offset + 16]
                    hex_part = ' '.join(f'{b:02x}' for b in chunk)
                    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                    print(f"  {offset:04x}: {hex_part}  {ascii_part}")
            except (ValueError, IndexError):
                print("Usage: raw <hex_offset> [size]")
        elif inp.lower() == 'help':
            print("Commands:")
            print("  <number>   - Show channel details (1-400)")
            print("  all        - Show all programmed channels")
            print("  settings   - Show settings area")
            print("  raw <addr> [size] - Show raw hex at offset")
            print("  q          - Quit")
        else:
            try:
                ch_num = int(inp)
                ch_data = get_channel(eeprom, ch_num)
                print_channel(ch_num, ch_data)
            except ValueError:
                print("Invalid input. Type 'help' for commands.")


if __name__ == '__main__':
    main()
