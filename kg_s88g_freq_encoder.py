#!/usr/bin/env python3
"""
KG-S88G Frequency Encoder/Decoder

This script encodes and decodes RX/TX frequencies for the Wouxun KG-S88G ham radio.
Frequencies are stored as 4 bytes using a custom nibble-based BCD encoding.
"""

# Nibble to digit mapping (same as used for channel names)
NIB_TO_DIGIT = {
    0x5: 0, 0x4: 1, 0x7: 2, 0x6: 3, 0x1: 4,
    0x0: 5, 0x3: 6, 0x2: 7, 0xd: 8, 0xc: 9
}

# Reverse mapping: digit to nibble
DIGIT_TO_NIB = {v: k for k, v in NIB_TO_DIGIT.items()}

# Character encoding (for CTCSS/DCS decoding)
CHAR_TO_HEX = {
    0x55: '0', 0x54: '1', 0x57: '2', 0x56: '3', 0x51: '4',
    0x50: '5', 0x53: '6', 0x52: '7', 0x5d: '8', 0x5c: '9',
    0x5f: 'A', 0x5e: 'B', 0x59: 'C', 0x58: 'D', 0x5b: 'E',
    0x5a: 'F',
}

HEX_TO_CHAR = {v: k for k, v in CHAR_TO_HEX.items()}

# Standard CTCSS tones (38 tones)
CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,  # 01-10
    94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,  # 11-20
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,  # 21-30
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8  # 31-38
]

# Standard DCS codes (104 codes, octal values)
DCS_CODES = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53,
    54, 65, 71, 72, 73, 74, 114, 115, 116, 122,
    125, 131, 132, 134, 143, 145, 152, 155, 156, 162,
    165, 172, 174, 205, 212, 223, 225, 226, 243, 244,
    245, 246, 251, 252, 255, 261, 263, 265, 266, 271,
    274, 306, 311, 315, 325, 331, 332, 343, 346, 351,
    356, 364, 365, 371, 411, 412, 413, 423, 431, 432,
    445, 446, 452, 454, 455, 462, 464, 465, 466, 503,
    506, 516, 523, 526, 532, 546, 565, 606, 612, 624,
    627, 631, 632, 654, 662, 664, 703, 712, 723, 731,
    732, 734, 743, 754
]

# File structure constants
FREQ_DATA_START = 0x0255  # Start of frequency data section
BYTES_PER_CHANNEL = 16     # Each channel record is 16 bytes
BYTES_PER_FREQ = 4         # Each frequency field is 4 bytes
TONE_OFFSET = 8            # CTCSS/DCS offset within channel record


def decode_frequency(freq_bytes: bytes) -> float:
    """
    Decode a 4-byte frequency field to MHz.
    
    Args:
        freq_bytes: 4 bytes representing the encoded frequency
        
    Returns:
        Frequency in MHz (format: XXX.YYYYY)
        
    Raises:
        ValueError: If bytes contain invalid nibbles
    """
    if len(freq_bytes) != BYTES_PER_FREQ:
        raise ValueError(f"Frequency must be exactly {BYTES_PER_FREQ} bytes")
    
    # Step 1: Reverse bytes (little-endian format)
    reversed_bytes = bytes(reversed(freq_bytes))
    
    # Step 2: Extract all nibbles and map to digits
    digits = []
    for byte_val in reversed_bytes:
        high_nibble = (byte_val >> 4) & 0x0F
        low_nibble = byte_val & 0x0F
        
        if high_nibble not in NIB_TO_DIGIT:
            raise ValueError(f"Invalid high nibble: 0x{high_nibble:x} in byte 0x{byte_val:02x}")
        if low_nibble not in NIB_TO_DIGIT:
            raise ValueError(f"Invalid low nibble: 0x{low_nibble:x} in byte 0x{byte_val:02x}")
        
        digits.append(NIB_TO_DIGIT[high_nibble])
        digits.append(NIB_TO_DIGIT[low_nibble])
    
    # Step 3: Build frequency string with decimal point after 3rd digit
    freq_str = ''.join(str(d) for d in digits)
    if len(freq_str) < 3:
        raise ValueError(f"Decoded frequency string too short: {freq_str}")
    
    formatted = freq_str[:3] + '.' + freq_str[3:]
    
    return float(formatted)


def encode_frequency(freq_mhz: float) -> bytes:
    """
    Encode a frequency in MHz to 4-byte KG-S88G format.
    
    Args:
        freq_mhz: Frequency in MHz (e.g., 462.5625)
        
    Returns:
        4 bytes representing the encoded frequency
        
    Raises:
        ValueError: If frequency is out of valid range or has too many decimal places
    """
    # Convert frequency to string with proper formatting
    # Format: XXX.YYYYY (8 total digits)
    freq_str = f"{freq_mhz:011.5f}".replace('.', '')
    
    # Take only the 8 significant digits
    if len(freq_str) > 8:
        freq_str = freq_str[:8]
    elif len(freq_str) < 8:
        freq_str = freq_str.ljust(8, '0')
    
    # Convert each digit to its nibble encoding
    nibbles = []
    for digit_char in freq_str:
        digit = int(digit_char)
        if digit not in DIGIT_TO_NIB:
            raise ValueError(f"Invalid digit: {digit}")
        nibbles.append(DIGIT_TO_NIB[digit])
    
    # Combine nibbles into bytes (pairs of nibbles)
    encoded_bytes = bytearray()
    for i in range(0, len(nibbles), 2):
        if i + 1 < len(nibbles):
            byte_val = (nibbles[i] << 4) | nibbles[i + 1]
            encoded_bytes.append(byte_val)
    
    # Reverse to match little-endian format
    encoded_bytes.reverse()
    
    return bytes(encoded_bytes)


def decode_tone(tone_bytes: bytes) -> tuple[str, str]:
    """
    Decode CTCSS/DCS tone bytes.
    
    Format: 4 bytes = [RX_MSB][RX_LSB][TX_MSB][TX_LSB]
    Each 2-byte pair encodes a hex index using character encoding.
    Index = stored_value - 0x10
    0 = OFF, 1-38 = CTCSS, 39+ = DCS
    
    Args:
        tone_bytes: 4 bytes representing RX and TX tones
        
    Returns:
        Tuple of (rx_tone_str, tx_tone_str)
    """
    if len(tone_bytes) != 4:
        raise ValueError("Tone data must be exactly 4 bytes")
    
    def decode_single_tone(byte_msb: int, byte_lsb: int) -> str:
        # Decode to hex characters
        hex_msb = CHAR_TO_HEX.get(byte_msb, '?')
        hex_lsb = CHAR_TO_HEX.get(byte_lsb, '?')
        
        if '?' in (hex_msb, hex_lsb):
            return "UNKNOWN"
        
        # Convert to index
        hex_str = hex_msb + hex_lsb
        stored_index = int(hex_str, 16)
        actual_index = stored_index - 0x10
        
        if actual_index == 0:
            return "OFF"
        elif 1 <= actual_index <= len(CTCSS_TONES):
            return f"{CTCSS_TONES[actual_index - 1]:.1f}"
        elif actual_index > 38:
            # DCS code - need to determine if N or I polarity
            # For now, show as DCS with index
            dcs_offset = actual_index - 39
            if 0 <= dcs_offset < len(DCS_CODES):
                # Note: Can't determine N/I polarity from just the index
                return f"D{DCS_CODES[dcs_offset]:03d}N/I?"
            else:
                return f"DCS#{actual_index - 38}"
        else:
            return f"INVALID({actual_index})"
    
    rx_tone = decode_single_tone(tone_bytes[0], tone_bytes[1])
    tx_tone = decode_single_tone(tone_bytes[2], tone_bytes[3])
    
    return rx_tone, tx_tone


def encode_tone(tone_str: str) -> bytes:
    """
    Encode a CTCSS/DCS tone string to 2 bytes.
    
    Args:
        tone_str: Tone string like "67.0", "OFF", "D023N", etc.
        
    Returns:
        2 bytes representing the encoded tone
    """
    tone_str = tone_str.strip().upper()
    
    if tone_str == "OFF" or tone_str == "0":
        actual_index = 0
    elif tone_str.startswith('D') and len(tone_str) >= 4:
        # DCS code like D023N or D023I
        try:
            dcs_num = int(tone_str[1:4])
            if dcs_num in DCS_CODES:
                dcs_offset = DCS_CODES.index(dcs_num)
                actual_index = 39 + dcs_offset
            else:
                raise ValueError(f"Unknown DCS code: {dcs_num}")
        except ValueError:
            raise ValueError(f"Invalid DCS format: {tone_str}")
    else:
        # CTCSS tone
        try:
            freq = float(tone_str)
            if freq in CTCSS_TONES:
                actual_index = CTCSS_TONES.index(freq) + 1
            else:
                raise ValueError(f"Unknown CTCSS frequency: {freq}")
        except ValueError:
            raise ValueError(f"Invalid tone format: {tone_str}")
    
    # Add offset and convert to hex
    stored_index = actual_index + 0x10
    hex_str = f"{stored_index:02X}"
    
    # Encode as 2 bytes using character encoding
    msb_char = hex_str[0]
    lsb_char = hex_str[1]
    
    if msb_char not in HEX_TO_CHAR or lsb_char not in HEX_TO_CHAR:
        raise ValueError(f"Cannot encode index {stored_index:02X}")
    
    return bytes([HEX_TO_CHAR[msb_char], HEX_TO_CHAR[lsb_char]])


def get_channel_freq_offsets(channel_num: int) -> tuple[int, int]:
    """
    Calculate the file offsets for RX and TX frequencies of a channel.
    
    The file uses a simple sequential structure where each channel occupies
    16 bytes: 4 bytes RX, 4 bytes TX, 8 bytes other data.
    
    Args:
        channel_num: Channel number (1-based)
        
    Returns:
        Tuple of (rx_offset, tx_offset) in bytes
    """
    channel_start = FREQ_DATA_START + ((channel_num - 1) * BYTES_PER_CHANNEL)
    
    rx_offset = channel_start
    tx_offset = channel_start + BYTES_PER_FREQ
    
    return rx_offset, tx_offset


def read_channel_frequencies(dat_file: str, channel_num: int) -> tuple[float, float, str, str]:
    """
    Read RX/TX frequencies and tones for a specific channel.
    
    Args:
        dat_file: Path to the .dat file
        channel_num: Channel number (1-based)
        
    Returns:
        Tuple of (rx_freq_mhz, tx_freq_mhz, rx_tone, tx_tone)
    """
    with open(dat_file, 'rb') as f:
        data = f.read()
    
    rx_offset, tx_offset = get_channel_freq_offsets(channel_num)
    
    rx_bytes = data[rx_offset:rx_offset + BYTES_PER_FREQ]
    tx_bytes = data[tx_offset:tx_offset + BYTES_PER_FREQ]
    
    rx_freq = decode_frequency(rx_bytes)
    tx_freq = decode_frequency(tx_bytes)
    
    # Read tone data (4 bytes at offset +8 from channel start)
    channel_offset = FREQ_DATA_START + ((channel_num - 1) * BYTES_PER_CHANNEL)
    tone_offset = channel_offset + TONE_OFFSET
    tone_bytes = data[tone_offset:tone_offset + 4]
    rx_tone, tx_tone = decode_tone(tone_bytes)
    
    return rx_freq, tx_freq, rx_tone, tx_tone


def write_channel_frequencies(dat_file: str, channel_num: int, 
                              rx_freq_mhz: float = None, 
                              tx_freq_mhz: float = None) -> None:
    """
    Write RX and/or TX frequencies for a specific channel.
    
    Args:
        dat_file: Path to the .dat file
        channel_num: Channel number (1-based)
        rx_freq_mhz: RX frequency in MHz (None to leave unchanged)
        tx_freq_mhz: TX frequency in MHz (None to leave unchanged)
    """
    with open(dat_file, 'rb') as f:
        data = bytearray(f.read())
    
    rx_offset, tx_offset = get_channel_freq_offsets(channel_num)
    
    if rx_freq_mhz is not None:
        rx_bytes = encode_frequency(rx_freq_mhz)
        data[rx_offset:rx_offset + BYTES_PER_FREQ] = rx_bytes
    
    if tx_freq_mhz is not None:
        tx_bytes = encode_frequency(tx_freq_mhz)
        data[tx_offset:tx_offset + BYTES_PER_FREQ] = tx_bytes
    
    with open(dat_file, 'wb') as f:
        f.write(data)


def read_all_frequencies(dat_file: str, num_channels: int = 30) -> list[tuple[int, float, float, str, str]]:
    """
    Read all channel frequencies and tones from a file.
    
    Args:
        dat_file: Path to the .dat file
        num_channels: Number of channels to read
        
    Returns:
        List of (channel_num, rx_freq, tx_freq, rx_tone, tx_tone) tuples
    """
    results = []
    
    for ch in range(1, num_channels + 1):
        try:
            rx_freq, tx_freq, rx_tone, tx_tone = read_channel_frequencies(dat_file, ch)
            results.append((ch, rx_freq, tx_freq, rx_tone, tx_tone))
        except Exception as e:
            print(f"Warning: Could not read channel {ch}: {e}")
            break
    
    return results


def main():
    """Interactive command-line interface."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='KG-S88G Frequency Encoder/Decoder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encode a frequency
  %(prog)s encode 462.5625
  
  # Decode hex bytes
  %(prog)s decode 05377013
  
  # Read channel frequencies from a file
  %(prog)s read radio.dat 1
  
  # Write channel frequencies to a file
  %(prog)s write radio.dat 1 --rx 146.52 --tx 146.52
  
  # List all frequencies
  %(prog)s list radio.dat
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Encode command
    encode_parser = subparsers.add_parser('encode', help='Encode a frequency')
    encode_parser.add_argument('freq', type=float, help='Frequency in MHz')
    
    # Decode command
    decode_parser = subparsers.add_parser('decode', help='Decode frequency bytes')
    decode_parser.add_argument('hex', help='Hex string (8 hex digits, no spaces)')
    
    # Read command
    read_parser = subparsers.add_parser('read', help='Read channel frequencies')
    read_parser.add_argument('file', help='Path to .dat file')
    read_parser.add_argument('channel', type=int, help='Channel number')
    
    # Write command
    write_parser = subparsers.add_parser('write', help='Write channel frequencies')
    write_parser.add_argument('file', help='Path to .dat file')
    write_parser.add_argument('channel', type=int, help='Channel number')
    write_parser.add_argument('--rx', type=float, help='RX frequency in MHz')
    write_parser.add_argument('--tx', type=float, help='TX frequency in MHz')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all channel frequencies')
    list_parser.add_argument('file', help='Path to .dat file')
    list_parser.add_argument('-n', '--num', type=int, default=30, help='Number of channels')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'encode':
            encoded = encode_frequency(args.freq)
            print(f"Frequency: {args.freq} MHz")
            print(f"Encoded hex: {encoded.hex().upper()}")
            print(f"Encoded bytes: {' '.join(f'0x{b:02x}' for b in encoded)}")
            
        elif args.command == 'decode':
            hex_str = args.hex.replace(' ', '').replace('0x', '')
            if len(hex_str) != 8:
                print(f"Error: Expected 8 hex digits, got {len(hex_str)}")
                return
            data = bytes.fromhex(hex_str)
            decoded = decode_frequency(data)
            print(f"Encoded hex: {hex_str.upper()}")
            print(f"Decoded frequency: {decoded:.5f} MHz")
            
        elif args.command == 'read':
            rx_freq, tx_freq, rx_tone, tx_tone = read_channel_frequencies(args.file, args.channel)
            print(f"Channel {args.channel}:")
            print(f"  RX: {rx_freq:.5f} MHz  Tone: {rx_tone}")
            print(f"  TX: {tx_freq:.5f} MHz  Tone: {tx_tone}")
            
        elif args.command == 'write':
            if args.rx is None and args.tx is None:
                print("Error: Must specify at least one of --rx or --tx")
                return
            
            write_channel_frequencies(args.file, args.channel, args.rx, args.tx)
            
            changes = []
            if args.rx: changes.append(f"RX={args.rx} MHz")
            if args.tx: changes.append(f"TX={args.tx} MHz")
            print(f"Updated channel {args.channel}: {', '.join(changes)}")
            
        elif args.command == 'list':
            channels = read_all_frequencies(args.file, args.num)
            print(f"\nChannel Configuration from {args.file}:")
            print("-" * 85)
            print(f"{'CH':<4} {'RX (MHz)':<15} {'TX (MHz)':<15} {'RX Tone':<15} {'TX Tone':<15}")
            print("-" * 85)
            for ch_num, rx_freq, tx_freq, rx_tone, tx_tone in channels:
                print(f"{ch_num:<4} {rx_freq:<15.5f} {tx_freq:<15.5f} {rx_tone:<15} {tx_tone:<15}")
            print(f"\nTotal channels: {len(channels)}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
