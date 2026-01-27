#!/usr/bin/env python3
"""
KG-S88G Channel Name Encoder/Decoder

This script encodes and decodes channel names for the Wouxun KG-S88G ham radio.
Channel names are 6 bytes long with a custom character encoding.
"""

# Complete character encoding map for KG-S88G
ENCODE_MAP = {
    'A': 0x5f, 'B': 0x5e, 'C': 0x59, 'D': 0x58, 'E': 0x5b, 'F': 0x5a,
    'G': 0x45, 'H': 0x44, 'I': 0x47, 'J': 0x46, 'K': 0x41, 'L': 0x40,
    'M': 0x43, 'N': 0x42, 'O': 0x4d, 'P': 0x4c, 'Q': 0x4f, 'R': 0x4e,
    'S': 0x49, 'T': 0x48, 'U': 0x4b, 'V': 0x4a, 'W': 0x75, 'X': 0x74,
    'Y': 0x77, 'Z': 0x76,
    '0': 0x55, '1': 0x54, '2': 0x57, '3': 0x56, '4': 0x51, '5': 0x50,
    '6': 0x53, '7': 0x52, '8': 0x5d, '9': 0x5c,
    ' ': 0x7c,  # Space/padding character
}

# Create reverse decode map
DECODE_MAP = {v: k for k, v in ENCODE_MAP.items()}

# Channel name constants
CHANNEL_NAME_LENGTH = 6
CHANNEL_NAME_OFFSET = 0x1c4b  # Offset of first channel name in .dat file
CHANNEL_NAME_STRIDE = 6  # Bytes between channel names


def encode_channel_name(name: str) -> bytes:
    """
    Encode a channel name string to KG-S88G format.
    
    Args:
        name: Channel name (max 6 characters, A-Z, 0-9, space)
        
    Returns:
        6 bytes representing the encoded channel name
        
    Raises:
        ValueError: If name contains invalid characters or is too long
    """
    # Convert to uppercase and validate length
    name = name.upper()
    if len(name) > CHANNEL_NAME_LENGTH:
        raise ValueError(f"Channel name too long (max {CHANNEL_NAME_LENGTH} chars): {name}")
    
    # Pad with spaces to 6 characters
    name = name.ljust(CHANNEL_NAME_LENGTH)
    
    # Encode each character
    encoded = bytearray()
    for i, char in enumerate(name):
        if char not in ENCODE_MAP:
            raise ValueError(f"Invalid character at position {i}: '{char}' (allowed: A-Z, 0-9, space)")
        encoded.append(ENCODE_MAP[char])
    
    return bytes(encoded)


def decode_channel_name(data: bytes) -> str:
    """
    Decode a KG-S88G encoded channel name.
    
    Args:
        data: 6 bytes of encoded channel name data
        
    Returns:
        Decoded channel name string (trailing spaces removed)
        
    Raises:
        ValueError: If data is wrong length or contains unknown bytes
    """
    if len(data) != CHANNEL_NAME_LENGTH:
        raise ValueError(f"Channel name data must be {CHANNEL_NAME_LENGTH} bytes, got {len(data)}")
    
    # Decode each byte
    decoded = []
    for i, byte in enumerate(data):
        if byte not in DECODE_MAP:
            raise ValueError(f"Unknown encoding byte at position {i}: 0x{byte:02x}")
        decoded.append(DECODE_MAP[byte])
    
    # Join and strip trailing spaces
    return ''.join(decoded).rstrip()


def read_channel_names(dat_file: str, num_channels: int = None) -> list[tuple[int, str]]:
    """
    Read all channel names from a KG-S88G .dat file.
    
    Args:
        dat_file: Path to the .dat file
        num_channels: Number of channels to read (None = read until error)
        
    Returns:
        List of (channel_number, channel_name) tuples
    """
    with open(dat_file, 'rb') as f:
        data = f.read()
    
    channels = []
    channel_num = 1
    
    while True:
        if num_channels is not None and channel_num > num_channels:
            break
            
        offset = CHANNEL_NAME_OFFSET + ((channel_num - 1) * CHANNEL_NAME_STRIDE)
        
        if offset + CHANNEL_NAME_LENGTH > len(data):
            break
            
        try:
            name_bytes = data[offset:offset + CHANNEL_NAME_LENGTH]
            name = decode_channel_name(name_bytes)
            channels.append((channel_num, name))
            channel_num += 1
        except ValueError:
            break
    
    return channels


def write_channel_name(dat_file: str, channel_num: int, name: str) -> None:
    """
    Write a channel name to a KG-S88G .dat file.
    
    Args:
        dat_file: Path to the .dat file
        channel_num: Channel number (1-based)
        name: New channel name
    """
    # Read the file
    with open(dat_file, 'rb') as f:
        data = bytearray(f.read())
    
    # Calculate offset
    offset = CHANNEL_NAME_OFFSET + ((channel_num - 1) * CHANNEL_NAME_STRIDE)
    
    if offset + CHANNEL_NAME_LENGTH > len(data):
        raise ValueError(f"Channel {channel_num} offset exceeds file size")
    
    # Encode and write
    encoded = encode_channel_name(name)
    data[offset:offset + CHANNEL_NAME_LENGTH] = encoded
    
    # Write back
    with open(dat_file, 'wb') as f:
        f.write(data)


def main():
    """Interactive command-line interface."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='KG-S88G Channel Name Encoder/Decoder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encode a channel name
  %(prog)s encode "GMRS01"
  
  # Decode hex bytes
  %(prog)s decode 454349555457
  
  # Read all channel names from a file
  %(prog)s read radio.dat
  
  # Write a channel name to a file
  %(prog)s write radio.dat 1 "TEST01"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Encode command
    encode_parser = subparsers.add_parser('encode', help='Encode a channel name')
    encode_parser.add_argument('name', help='Channel name to encode (max 6 chars)')
    
    # Decode command
    decode_parser = subparsers.add_parser('decode', help='Decode channel name bytes')
    decode_parser.add_argument('hex', help='Hex string (12 hex digits, no spaces)')
    
    # Read command
    read_parser = subparsers.add_parser('read', help='Read channel names from file')
    read_parser.add_argument('file', help='Path to .dat file')
    read_parser.add_argument('-n', '--num', type=int, help='Number of channels to read')
    
    # Write command
    write_parser = subparsers.add_parser('write', help='Write channel name to file')
    write_parser.add_argument('file', help='Path to .dat file')
    write_parser.add_argument('channel', type=int, help='Channel number (1-based)')
    write_parser.add_argument('name', help='New channel name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'encode':
            encoded = encode_channel_name(args.name)
            print(f"Channel name: '{args.name}'")
            print(f"Encoded hex:  {encoded.hex().upper()}")
            print(f"Encoded bytes: {' '.join(f'0x{b:02x}' for b in encoded)}")
            
        elif args.command == 'decode':
            # Remove any spaces and convert to bytes
            hex_str = args.hex.replace(' ', '').replace('0x', '')
            if len(hex_str) != 12:
                print(f"Error: Expected 12 hex digits, got {len(hex_str)}")
                return
            data = bytes.fromhex(hex_str)
            decoded = decode_channel_name(data)
            print(f"Encoded hex:  {hex_str.upper()}")
            print(f"Decoded name: '{decoded}'")
            
        elif args.command == 'read':
            channels = read_channel_names(args.file, args.num)
            print(f"\nChannel names from {args.file}:")
            print("-" * 40)
            for ch_num, ch_name in channels:
                print(f"  CH{ch_num:03d}: {ch_name}")
            print(f"\nTotal channels: {len(channels)}")
            
        elif args.command == 'write':
            write_channel_name(args.file, args.channel, args.name)
            print(f"Updated channel {args.channel} to '{args.name}' in {args.file}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
