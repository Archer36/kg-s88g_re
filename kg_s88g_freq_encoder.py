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

# XOR mask for tone encoding - all tone bytes are XORed with this value
TONE_XOR_MASK = 0x55

# Tone mode values (after XOR with 0x55)
TONE_MODE_OFF = 0
TONE_MODE_CTCSS = 1
TONE_MODE_DCS_N = 2  # DCS Normal polarity
TONE_MODE_DCS_I = 3  # DCS Inverted polarity

# Standard CTCSS tones (38 tones)
CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,  # 01-10
    94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,  # 11-20
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,  # 21-30
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8  # 31-38
]

# DCS codes as used by the KG-S88G (octal values)
# Note: The radio appears to use 105 codes instead of the standard 104.
# There seems to be an extra code inserted around position 97 (before D703).
# This causes D703 to be at index 98 and D754 at index 105.
# The exact extra code is TBD - for now using standard 104-code list.
DCS_CODES = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53,       # 1-10
    54, 65, 71, 72, 73, 74, 114, 115, 116, 122,   # 11-20
    125, 131, 132, 134, 143, 145, 152, 155, 156, 162,  # 21-30
    165, 172, 174, 205, 212, 223, 225, 226, 243, 244,  # 31-40
    245, 246, 251, 252, 255, 261, 263, 265, 266, 271,  # 41-50
    274, 306, 311, 315, 325, 331, 332, 343, 346, 351,  # 51-60
    356, 364, 365, 371, 411, 412, 413, 423, 431, 432,  # 61-70
    445, 446, 452, 454, 455, 462, 464, 465, 466, 503,  # 71-80
    506, 516, 523, 526, 532, 546, 565, 606, 612, 624,  # 81-90
    627, 631, 632, 654, 662, 664, 703, 712, 723, 731,  # 91-100
    732, 734, 743, 754                                 # 101-104
]

# File structure constants
FREQ_DATA_START = 0x0255   # Start of frequency data section
BYTES_PER_CHANNEL = 16     # Each channel record is 16 bytes
BYTES_PER_FREQ = 4         # Each frequency field is 4 bytes
TONE_OFFSET = 8            # CTCSS/DCS offset within channel record
MAX_CHANNELS = 400         # Total number of channels supported


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
    # Convert frequency to 8-digit string (XXX.YYYYY format, no decimal point)
    # Multiply by 100000 to shift decimal 5 places, round to handle float precision
    freq_int = int(round(freq_mhz * 100000))
    freq_str = f"{freq_int:08d}"

    # Validate length
    if len(freq_str) != 8:
        raise ValueError(f"Frequency {freq_mhz} produces invalid digit count: {freq_str}")
    
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

    Format: 4 bytes = [RX_MODE][RX_IDX][TX_MODE][TX_IDX]
    Each byte is XORed with 0x55 to get the actual value.

    Mode byte (after XOR):
        0 = OFF
        1 = CTCSS
        2 = DCS-N (Normal polarity)
        3 = DCS-I (Inverted polarity)

    Index byte (after XOR):
        1-based index into CTCSS_TONES or DCS_CODES

    Args:
        tone_bytes: 4 bytes representing RX and TX tones

    Returns:
        Tuple of (rx_tone_str, tx_tone_str)
    """
    if len(tone_bytes) != 4:
        raise ValueError("Tone data must be exactly 4 bytes")

    def decode_single_tone(mode_byte: int, idx_byte: int) -> str:
        # XOR with mask to get actual values
        mode = mode_byte ^ TONE_XOR_MASK
        idx = idx_byte ^ TONE_XOR_MASK

        if mode == TONE_MODE_OFF:
            return "OFF"
        elif mode == TONE_MODE_CTCSS:
            if 1 <= idx <= len(CTCSS_TONES):
                return f"{CTCSS_TONES[idx - 1]:.1f}"
            else:
                return f"CTCSS#{idx}"
        elif mode == TONE_MODE_DCS_N:
            if 1 <= idx <= len(DCS_CODES):
                return f"D{DCS_CODES[idx - 1]:03d}N"
            else:
                return f"DCS#{idx}N"
        elif mode == TONE_MODE_DCS_I:
            if 1 <= idx <= len(DCS_CODES):
                return f"D{DCS_CODES[idx - 1]:03d}I"
            else:
                return f"DCS#{idx}I"
        else:
            return f"UNKNOWN(mode={mode},idx={idx})"

    rx_tone = decode_single_tone(tone_bytes[0], tone_bytes[1])
    tx_tone = decode_single_tone(tone_bytes[2], tone_bytes[3])

    return rx_tone, tx_tone


def encode_tone(tone_str: str) -> bytes:
    """
    Encode a CTCSS/DCS tone string to 2 bytes.

    Args:
        tone_str: Tone string like "67.0", "OFF", "D023N", "D023I", etc.

    Returns:
        2 bytes representing the encoded tone [mode_byte, idx_byte]
    """
    tone_str = tone_str.strip().upper()

    if tone_str == "OFF" or tone_str == "0":
        mode = TONE_MODE_OFF
        idx = 0
    elif tone_str.startswith('D') and len(tone_str) >= 4:
        # DCS code like D023N or D023I
        try:
            dcs_num = int(tone_str[1:4])
            polarity = tone_str[4:5] if len(tone_str) > 4 else 'N'

            if dcs_num in DCS_CODES:
                idx = DCS_CODES.index(dcs_num) + 1  # 1-based index
            else:
                raise ValueError(f"Unknown DCS code: {dcs_num}")

            if polarity == 'N':
                mode = TONE_MODE_DCS_N
            elif polarity == 'I':
                mode = TONE_MODE_DCS_I
            else:
                raise ValueError(f"Invalid DCS polarity: {polarity} (use N or I)")
        except ValueError as e:
            if "Unknown DCS" in str(e) or "Invalid DCS" in str(e):
                raise
            raise ValueError(f"Invalid DCS format: {tone_str}")
    else:
        # CTCSS tone
        try:
            freq = float(tone_str)
            if freq in CTCSS_TONES:
                mode = TONE_MODE_CTCSS
                idx = CTCSS_TONES.index(freq) + 1  # 1-based index
            else:
                raise ValueError(f"Unknown CTCSS frequency: {freq}")
        except ValueError as e:
            if "Unknown CTCSS" in str(e):
                raise
            raise ValueError(f"Invalid tone format: {tone_str}")

    # XOR with mask to encode
    mode_byte = mode ^ TONE_XOR_MASK
    idx_byte = idx ^ TONE_XOR_MASK

    return bytes([mode_byte, idx_byte])


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


def read_channel_frequencies(dat_file: str, channel_num: int, include_settings: bool = False):
    """
    Read RX/TX frequencies and tones for a specific channel.

    Args:
        dat_file: Path to the .dat file
        channel_num: Channel number (1-based)
        include_settings: If True, also return decoded settings

    Returns:
        If include_settings=False: Tuple of (rx_freq_mhz, tx_freq_mhz, rx_tone, tx_tone)
        If include_settings=True: Tuple of (rx_freq_mhz, tx_freq_mhz, rx_tone, tx_tone, settings_dict)
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

    if include_settings:
        # Read settings (4 bytes at offset +12 from channel start)
        settings_offset = channel_offset + 12
        settings_bytes = data[settings_offset:settings_offset + 4]
        settings = decode_channel_settings(settings_bytes)
        return rx_freq, tx_freq, rx_tone, tx_tone, settings

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


def encode_channel_settings(power: str = 'High', bandwidth: str = 'Wide',
                            busy_lock: str = 'OFF', call_id: int = 1,
                            sp_mute: str = 'QT', descramble: str = 'OFF') -> bytes:
    """
    Encode channel settings to 4 bytes.

    Args:
        power: 'High' or 'Low'
        bandwidth: 'Wide' or 'Narrow'
        busy_lock: 'ON' or 'OFF'
        call_id: Call ID number (1-15)
        sp_mute: 'QT', 'QT*DT', or 'QT+DT'
        descramble: 'OFF', '1', '2', or '3'

    Returns:
        4 bytes of encoded settings
    """
    # Build byte 12 (Settings A)
    b12 = 0
    b12 |= 0x01 if power.upper() == 'HIGH' else 0x00  # Bit 0: Power

    # Descramble (bits 2-3)
    if descramble.upper() == 'OFF' or descramble == '0':
        pass  # bits 2-3 stay 0
    else:
        desc_val = int(descramble) & 0x03
        b12 |= (desc_val << 2)

    # SP Mute (bits 6-7)
    sp_map = {'QT': 0, 'QT*DT': 1, 'QT+DT': 2}
    sp_val = sp_map.get(sp_mute.upper(), 0)
    b12 |= (sp_val << 6)

    # Build byte 13 (Settings B)
    b13 = 0
    b13 |= 0x01 if busy_lock.upper() == 'ON' else 0x00  # Bit 0: Busy Lock
    b13 |= ((call_id & 0x1F) << 3)  # Bits 3-7: Call ID

    # Build byte 14 (Settings C)
    b14 = 0
    b14 |= 0x01 if bandwidth.upper() == 'WIDE' else 0x00  # Bit 0: Bandwidth

    # Byte 15 is reserved
    b15 = 0

    # XOR encode all bytes
    return bytes([
        b12 ^ TONE_XOR_MASK,
        b13 ^ TONE_XOR_MASK,
        b14 ^ TONE_XOR_MASK,
        b15 ^ TONE_XOR_MASK
    ])


def write_channel(dat_file: str, channel_num: int,
                  rx_freq: float = None, tx_freq: float = None,
                  rx_tone: str = None, tx_tone: str = None,
                  power: str = None, bandwidth: str = None,
                  busy_lock: str = None, call_id: int = None,
                  sp_mute: str = None, descramble: str = None,
                  name: str = None) -> None:
    """
    Write complete channel data including frequencies, tones, and settings.

    Args:
        dat_file: Path to the .dat file
        channel_num: Channel number (1-400)
        rx_freq: RX frequency in MHz
        tx_freq: TX frequency in MHz
        rx_tone: RX tone ('OFF', '67.0', 'D023N', 'D023I', etc.)
        tx_tone: TX tone
        power: 'High' or 'Low'
        bandwidth: 'Wide' or 'Narrow'
        busy_lock: 'ON' or 'OFF'
        call_id: Call ID (1-15)
        sp_mute: 'QT', 'QT*DT', or 'QT+DT'
        descramble: 'OFF', '1', '2', or '3'
        name: Channel name (max 6 characters)

    Only specified (non-None) values are updated; others are left unchanged.
    """
    with open(dat_file, 'rb') as f:
        data = bytearray(f.read())

    channel_offset = FREQ_DATA_START + ((channel_num - 1) * BYTES_PER_CHANNEL)

    # Update frequencies
    if rx_freq is not None:
        rx_bytes = encode_frequency(rx_freq)
        data[channel_offset:channel_offset + 4] = rx_bytes

    if tx_freq is not None:
        tx_bytes = encode_frequency(tx_freq)
        data[channel_offset + 4:channel_offset + 8] = tx_bytes

    # Update tones
    if rx_tone is not None:
        tone_bytes = encode_tone(rx_tone)
        data[channel_offset + 8:channel_offset + 10] = tone_bytes

    if tx_tone is not None:
        tone_bytes = encode_tone(tx_tone)
        data[channel_offset + 10:channel_offset + 12] = tone_bytes

    # Update settings (read current, modify, write back)
    if any(x is not None for x in [power, bandwidth, busy_lock, call_id, sp_mute, descramble]):
        current_settings = decode_channel_settings(data[channel_offset + 12:channel_offset + 16])

        new_settings = encode_channel_settings(
            power=power if power is not None else current_settings['power'],
            bandwidth=bandwidth if bandwidth is not None else current_settings['bandwidth'],
            busy_lock=busy_lock if busy_lock is not None else current_settings['busy_lock'],
            call_id=call_id if call_id is not None else current_settings['call_id'],
            sp_mute=sp_mute if sp_mute is not None else current_settings['sp_mute'],
            descramble=descramble if descramble is not None else current_settings['descramble']
        )
        data[channel_offset + 12:channel_offset + 16] = new_settings

    # Update channel name
    if name is not None:
        # Import channel encoder for name handling
        from kg_s88g_channel_encoder import encode_channel_name, CHANNEL_NAME_OFFSET, CHANNEL_NAME_STRIDE
        name_offset = CHANNEL_NAME_OFFSET + ((channel_num - 1) * CHANNEL_NAME_STRIDE)
        name_bytes = encode_channel_name(name)
        data[name_offset:name_offset + 6] = name_bytes

    with open(dat_file, 'wb') as f:
        f.write(data)


def decode_channel_settings(settings_bytes: bytes) -> dict:
    """
    Decode the 4 settings bytes (offset +12 to +15) of a channel record.

    Args:
        settings_bytes: 4 bytes of settings data

    Returns:
        Dictionary with decoded settings
    """
    if len(settings_bytes) != 4:
        raise ValueError("Settings must be exactly 4 bytes")

    # Decode with XOR 0x55
    b12 = settings_bytes[0] ^ TONE_XOR_MASK
    b13 = settings_bytes[1] ^ TONE_XOR_MASK
    b14 = settings_bytes[2] ^ TONE_XOR_MASK
    b15 = settings_bytes[3] ^ TONE_XOR_MASK

    # Extract individual settings
    power = 'High' if (b12 & 0x01) else 'Low'
    bandwidth = 'Wide' if (b14 & 0x01) else 'Narrow'
    busy_lock = 'ON' if (b13 & 0x01) else 'OFF'
    call_id = (b13 >> 3) & 0x1F

    # SP Mute mode (bits 6-7 of b12)
    sp_bits = (b12 >> 6) & 0x03
    sp_mute = {0: 'QT', 1: 'QT*DT', 2: 'QT+DT', 3: 'QT?DT'}.get(sp_bits, 'QT')

    # Descramble (bits 2-3 of b12)
    descramble = (b12 >> 2) & 0x03
    descramble_str = 'OFF' if descramble == 0 else str(descramble)

    return {
        'power': power,
        'bandwidth': bandwidth,
        'busy_lock': busy_lock,
        'call_id': call_id,
        'sp_mute': sp_mute,
        'descramble': descramble_str,
        'raw': settings_bytes,
    }


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


def export_to_csv(dat_file: str, csv_file: str, num_channels: int = 30) -> int:
    """
    Export channel data from a .dat file to CSV format.

    Args:
        dat_file: Path to the .dat file
        csv_file: Path to output CSV file
        num_channels: Number of channels to export

    Returns:
        Number of channels exported
    """
    import csv
    from kg_s88g_channel_encoder import decode_channel_name, CHANNEL_NAME_OFFSET, CHANNEL_NAME_STRIDE

    with open(dat_file, 'rb') as f:
        data = f.read()

    channels = []
    for ch in range(1, num_channels + 1):
        try:
            rx_freq, tx_freq, rx_tone, tx_tone, settings = read_channel_frequencies(
                dat_file, ch, include_settings=True)

            # Read channel name
            name_offset = CHANNEL_NAME_OFFSET + ((ch - 1) * CHANNEL_NAME_STRIDE)
            name_bytes = data[name_offset:name_offset + 6]

            # Check if channel is empty (all 0xAA)
            channel_offset = FREQ_DATA_START + ((ch - 1) * BYTES_PER_CHANNEL)
            if data[channel_offset] == 0xAA:
                continue  # Skip empty channels

            name = decode_channel_name(name_bytes)

            channels.append({
                'Channel': ch,
                'Name': name,
                'RX_Freq': f"{rx_freq:.5f}",
                'TX_Freq': f"{tx_freq:.5f}",
                'RX_Tone': rx_tone,
                'TX_Tone': tx_tone,
                'Power': settings['power'],
                'Bandwidth': settings['bandwidth'],
                'Busy_Lock': settings['busy_lock'],
                'Call_ID': settings['call_id'],
                'SP_Mute': settings['sp_mute'],
                'Descramble': settings['descramble'],
            })
        except Exception as e:
            continue  # Skip channels that can't be read

    # Write CSV
    if channels:
        fieldnames = ['Channel', 'Name', 'RX_Freq', 'TX_Freq', 'RX_Tone', 'TX_Tone',
                      'Power', 'Bandwidth', 'Busy_Lock', 'Call_ID', 'SP_Mute', 'Descramble']
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(channels)

    return len(channels)


def clear_channels(dat_file: str, start_channel: int, end_channel: int = None,
                   create_backup: bool = True) -> int:
    """
    Clear (delete) one or more channels by writing 0xAA to their data.

    Args:
        dat_file: Path to the .dat file
        start_channel: First channel to clear (1-based)
        end_channel: Last channel to clear (inclusive), or None for single channel
        create_backup: If True, create a .bak backup before modifying

    Returns:
        Number of channels cleared
    """
    import shutil
    from kg_s88g_channel_encoder import CHANNEL_NAME_OFFSET, CHANNEL_NAME_STRIDE

    if end_channel is None:
        end_channel = start_channel

    # Validate range
    if start_channel < 1 or end_channel > MAX_CHANNELS:
        raise ValueError(f"Channel numbers must be between 1 and {MAX_CHANNELS}")
    if start_channel > end_channel:
        raise ValueError("Start channel must be <= end channel")

    # Create backup
    if create_backup:
        backup_file = dat_file + '.bak'
        shutil.copy2(dat_file, backup_file)

    with open(dat_file, 'rb') as f:
        data = bytearray(f.read())

    # Clear each channel
    count = 0
    for channel_num in range(start_channel, end_channel + 1):
        # Clear frequency/tone/settings data (16 bytes) - all 0xAA per stock firmware
        freq_offset = FREQ_DATA_START + ((channel_num - 1) * BYTES_PER_CHANNEL)
        for i in range(BYTES_PER_CHANNEL):
            data[freq_offset + i] = 0xAA

        # Clear channel name (6 bytes) - 0xAA per stock firmware
        name_offset = CHANNEL_NAME_OFFSET + ((channel_num - 1) * CHANNEL_NAME_STRIDE)
        for i in range(CHANNEL_NAME_STRIDE):
            data[name_offset + i] = 0xAA

        count += 1

    with open(dat_file, 'wb') as f:
        f.write(data)

    return count


def import_from_csv(csv_file: str, dat_file: str, create_backup: bool = True) -> int:
    """
    Import channel data from CSV into a .dat file.

    Args:
        csv_file: Path to input CSV file
        dat_file: Path to the .dat file to modify
        create_backup: If True, create a .bak backup before modifying

    Returns:
        Number of channels imported

    CSV columns (all optional except Channel):
        Channel, Name, RX_Freq, TX_Freq, RX_Tone, TX_Tone,
        Power, Bandwidth, Busy_Lock, Call_ID, SP_Mute, Descramble
    """
    import csv
    import shutil

    # Create backup
    if create_backup:
        backup_file = dat_file + '.bak'
        shutil.copy2(dat_file, backup_file)

    # Read CSV
    with open(csv_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    count = 0
    for row in rows:
        try:
            channel_num = int(row.get('Channel', 0))
            if channel_num < 1 or channel_num > MAX_CHANNELS:
                continue

            # Parse values, treating empty strings as None
            def get_val(key, converter=str):
                val = row.get(key, '').strip()
                if val == '' or val.upper() == 'NONE':
                    return None
                return converter(val)

            write_channel(
                dat_file=dat_file,
                channel_num=channel_num,
                name=get_val('Name'),
                rx_freq=get_val('RX_Freq', float),
                tx_freq=get_val('TX_Freq', float),
                rx_tone=get_val('RX_Tone'),
                tx_tone=get_val('TX_Tone'),
                power=get_val('Power'),
                bandwidth=get_val('Bandwidth'),
                busy_lock=get_val('Busy_Lock'),
                call_id=get_val('Call_ID', int),
                sp_mute=get_val('SP_Mute'),
                descramble=get_val('Descramble'),
            )
            count += 1
        except Exception as e:
            print(f"Warning: Failed to import channel {row.get('Channel', '?')}: {e}")

    return count


def main():
    """Interactive command-line interface."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='KG-S88G Radio Configuration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read a channel with all settings
  %(prog)s read radio.dat 1

  # Write channel with all options
  %(prog)s write radio.dat 1 --rx 462.5625 --tx 462.5625 --rx-tone 67.0 \\
      --tx-tone D023N --power High --bandwidth Wide --name "GMRS01"

  # Export channels to CSV
  %(prog)s export radio.dat channels.csv -n 30

  # Import channels from CSV
  %(prog)s import channels.csv radio.dat

  # List all frequencies
  %(prog)s list radio.dat -n 22

  # Clear a single channel
  %(prog)s clear radio.dat 5

  # Clear a range of channels
  %(prog)s clear radio.dat 10-20
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
    write_parser = subparsers.add_parser('write', help='Write channel data')
    write_parser.add_argument('file', help='Path to .dat file')
    write_parser.add_argument('channel', type=int, help='Channel number (1-400)')
    write_parser.add_argument('--rx', type=float, help='RX frequency in MHz')
    write_parser.add_argument('--tx', type=float, help='TX frequency in MHz')
    write_parser.add_argument('--rx-tone', help='RX tone (OFF, 67.0, D023N, D023I, etc.)')
    write_parser.add_argument('--tx-tone', help='TX tone')
    write_parser.add_argument('--power', choices=['High', 'Low'], help='Power level')
    write_parser.add_argument('--bandwidth', choices=['Wide', 'Narrow'], help='Bandwidth')
    write_parser.add_argument('--busy-lock', choices=['ON', 'OFF'], help='Busy lock')
    write_parser.add_argument('--call-id', type=int, help='Call ID (1-15)')
    write_parser.add_argument('--sp-mute', choices=['QT', 'QT*DT', 'QT+DT'], help='SP Mute mode')
    write_parser.add_argument('--descramble', choices=['OFF', '1', '2', '3'], help='Descramble')
    write_parser.add_argument('--name', help='Channel name (max 6 chars)')

    # List command
    list_parser = subparsers.add_parser('list', help='List all channel frequencies')
    list_parser.add_argument('file', help='Path to .dat file')
    list_parser.add_argument('-n', '--num', type=int, default=30,
                             help='Number of channels to display (default: 30, max: 400)')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export channels to CSV')
    export_parser.add_argument('dat_file', help='Path to .dat file')
    export_parser.add_argument('csv_file', help='Path to output CSV file')
    export_parser.add_argument('-n', '--num', type=int, default=30,
                               help='Number of channels to export (default: 30, max: 400)')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import channels from CSV')
    import_parser.add_argument('csv_file', help='Path to input CSV file')
    import_parser.add_argument('dat_file', help='Path to .dat file to modify')
    import_parser.add_argument('--no-backup', action='store_true',
                               help='Do not create backup before modifying')

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear (delete) channels')
    clear_parser.add_argument('file', help='Path to .dat file')
    clear_parser.add_argument('range', help='Channel(s) to clear: single (5) or range (1-10)')
    clear_parser.add_argument('--no-backup', action='store_true',
                              help='Do not create backup before modifying')

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
            rx_freq, tx_freq, rx_tone, tx_tone, settings = read_channel_frequencies(
                args.file, args.channel, include_settings=True)
            print(f"Channel {args.channel}:")
            print(f"  RX: {rx_freq:.5f} MHz  Tone: {rx_tone}")
            print(f"  TX: {tx_freq:.5f} MHz  Tone: {tx_tone}")
            print(f"  Power: {settings['power']}  Bandwidth: {settings['bandwidth']}")
            print(f"  Busy Lock: {settings['busy_lock']}  Call ID: {settings['call_id']}")
            print(f"  SP Mute: {settings['sp_mute']}  Descramble: {settings['descramble']}")
            
        elif args.command == 'write':
            # Check if at least one option was specified
            write_opts = [args.rx, args.tx, args.rx_tone, args.tx_tone, args.power,
                          args.bandwidth, args.busy_lock, args.call_id, args.sp_mute,
                          args.descramble, args.name]
            if all(opt is None for opt in write_opts):
                print("Error: Must specify at least one option to write")
                return

            write_channel(
                dat_file=args.file,
                channel_num=args.channel,
                rx_freq=args.rx,
                tx_freq=args.tx,
                rx_tone=args.rx_tone,
                tx_tone=args.tx_tone,
                power=args.power,
                bandwidth=args.bandwidth,
                busy_lock=args.busy_lock,
                call_id=args.call_id,
                sp_mute=args.sp_mute,
                descramble=args.descramble,
                name=args.name
            )

            # Show what was updated
            changes = []
            if args.rx: changes.append(f"RX={args.rx} MHz")
            if args.tx: changes.append(f"TX={args.tx} MHz")
            if args.rx_tone: changes.append(f"RX Tone={args.rx_tone}")
            if args.tx_tone: changes.append(f"TX Tone={args.tx_tone}")
            if args.power: changes.append(f"Power={args.power}")
            if args.bandwidth: changes.append(f"Bandwidth={args.bandwidth}")
            if args.busy_lock: changes.append(f"Busy Lock={args.busy_lock}")
            if args.call_id: changes.append(f"Call ID={args.call_id}")
            if args.sp_mute: changes.append(f"SP Mute={args.sp_mute}")
            if args.descramble: changes.append(f"Descramble={args.descramble}")
            if args.name: changes.append(f"Name={args.name}")
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

        elif args.command == 'export':
            count = export_to_csv(args.dat_file, args.csv_file, args.num)
            print(f"Exported {count} channels to {args.csv_file}")

        elif args.command == 'import':
            count = import_from_csv(args.csv_file, args.dat_file,
                                    create_backup=not args.no_backup)
            if not args.no_backup:
                print(f"Backup created: {args.dat_file}.bak")
            print(f"Imported {count} channels from {args.csv_file}")

        elif args.command == 'clear':
            # Parse range argument: "5" or "1-10"
            range_arg = args.range
            if '-' in range_arg:
                parts = range_arg.split('-')
                start_ch = int(parts[0])
                end_ch = int(parts[1])
            else:
                start_ch = int(range_arg)
                end_ch = start_ch

            count = clear_channels(args.file, start_ch, end_ch,
                                   create_backup=not args.no_backup)
            if not args.no_backup:
                print(f"Backup created: {args.file}.bak")
            if start_ch == end_ch:
                print(f"Cleared channel {start_ch}")
            else:
                print(f"Cleared {count} channels ({start_ch}-{end_ch})")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
