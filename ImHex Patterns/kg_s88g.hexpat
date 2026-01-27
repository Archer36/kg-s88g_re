#pragma description Wouxun KG-S88G Radio Configuration File
#pragma endian little
#pragma eval_depth 128

import std.mem;
import std.string;

// Custom nibble-to-digit mapping used by KG-S88G (returns u8 ASCII code)
// This matches the encoding used for both channel names and frequencies
fn decode_nibble(u8 nibble) {
    if (nibble == 0x5) return 0x30; // '0'
    else if (nibble == 0x4) return 0x31; // '1'
    else if (nibble == 0x7) return 0x32; // '2'
    else if (nibble == 0x6) return 0x33; // '3'
    else if (nibble == 0x1) return 0x34; // '4'
    else if (nibble == 0x0) return 0x35; // '5'
    else if (nibble == 0x3) return 0x36; // '6'
    else if (nibble == 0x2) return 0x37; // '7'
    else if (nibble == 0xD) return 0x38; // '8'
    else if (nibble == 0xC) return 0x39; // '9'
    else return 0x3f; // '?'
};

// Decode a single encoded character byte to ASCII (returns u8 ASCII code)
fn decode_char(u8 encoded_byte) {
    // Letters
    if (encoded_byte == 0x5f) return 0x41; // 'A'
    else if (encoded_byte == 0x5e) return 0x42; // 'B'
    else if (encoded_byte == 0x59) return 0x43; // 'C'
    else if (encoded_byte == 0x58) return 0x44; // 'D'
    else if (encoded_byte == 0x5b) return 0x45; // 'E'
    else if (encoded_byte == 0x5a) return 0x46; // 'F'
    else if (encoded_byte == 0x45) return 0x47; // 'G'
    else if (encoded_byte == 0x44) return 0x48; // 'H'
    else if (encoded_byte == 0x47) return 0x49; // 'I'
    else if (encoded_byte == 0x46) return 0x4a; // 'J'
    else if (encoded_byte == 0x41) return 0x4b; // 'K'
    else if (encoded_byte == 0x40) return 0x4c; // 'L'
    else if (encoded_byte == 0x43) return 0x4d; // 'M'
    else if (encoded_byte == 0x42) return 0x4e; // 'N'
    else if (encoded_byte == 0x4d) return 0x4f; // 'O'
    else if (encoded_byte == 0x4c) return 0x50; // 'P'
    else if (encoded_byte == 0x4f) return 0x51; // 'Q'
    else if (encoded_byte == 0x4e) return 0x52; // 'R'
    else if (encoded_byte == 0x49) return 0x53; // 'S'
    else if (encoded_byte == 0x48) return 0x54; // 'T'
    else if (encoded_byte == 0x4b) return 0x55; // 'U'
    else if (encoded_byte == 0x4a) return 0x56; // 'V'
    else if (encoded_byte == 0x75) return 0x57; // 'W'
    else if (encoded_byte == 0x74) return 0x58; // 'X'
    else if (encoded_byte == 0x77) return 0x59; // 'Y'
    else if (encoded_byte == 0x76) return 0x5a; // 'Z'
    // Digits
    else if (encoded_byte == 0x55) return 0x30; // '0'
    else if (encoded_byte == 0x54) return 0x31; // '1'
    else if (encoded_byte == 0x57) return 0x32; // '2'
    else if (encoded_byte == 0x56) return 0x33; // '3'
    else if (encoded_byte == 0x51) return 0x34; // '4'
    else if (encoded_byte == 0x50) return 0x35; // '5'
    else if (encoded_byte == 0x53) return 0x36; // '6'
    else if (encoded_byte == 0x52) return 0x37; // '7'
    else if (encoded_byte == 0x5d) return 0x38; // '8'
    else if (encoded_byte == 0x5c) return 0x39; // '9'
    // Space/padding
    else if (encoded_byte == 0x7c) return 0x20; // ' '
    else return 0x3f; // '?'
};

// Frequency type - 4 bytes encoded as nibble-mapped BCD
// Format: XXX.YYYYY MHz (8 digits total)
// Bytes are stored in little-endian (reversed) order
struct Frequency {
    u8 byte3;  // Stored reversed, so byte 3 is first in file
    u8 byte2;
    u8 byte1;
    u8 byte0;  // Byte 0 is last in file
    
    // Decode the frequency to display format
    char decoded_str[12] [[hidden]];
} [[format("format_frequency"), transform("transform_frequency")]];

fn format_frequency(Frequency freq) {
    // Extract nibbles and decode to digits
    u8 d0 = decode_nibble((freq.byte0 >> 4) & 0x0F);
    u8 d1 = decode_nibble(freq.byte0 & 0x0F);
    u8 d2 = decode_nibble((freq.byte1 >> 4) & 0x0F);
    u8 d3 = decode_nibble(freq.byte1 & 0x0F);
    u8 d4 = decode_nibble((freq.byte2 >> 4) & 0x0F);
    u8 d5 = decode_nibble(freq.byte2 & 0x0F);
    u8 d6 = decode_nibble((freq.byte3 >> 4) & 0x0F);
    u8 d7 = decode_nibble(freq.byte3 & 0x0F);
    
    // Format as XXX.YYYYY MHz
    str result = "";
    result += char(d0);
    result += char(d1);
    result += char(d2);
    result += '.';
    result += char(d3);
    result += char(d4);
    result += char(d5);
    result += char(d6);
    result += char(d7);
    result += " MHz";
    return result;
};

fn transform_frequency(Frequency freq) {
    // Extract nibbles and convert to numeric value
    u8 digit0 = decode_nibble((freq.byte0 >> 4) & 0x0F) - '0';
    u8 digit1 = decode_nibble(freq.byte0 & 0x0F) - '0';
    u8 digit2 = decode_nibble((freq.byte1 >> 4) & 0x0F) - '0';
    u8 digit3 = decode_nibble(freq.byte1 & 0x0F) - '0';
    u8 digit4 = decode_nibble((freq.byte2 >> 4) & 0x0F) - '0';
    u8 digit5 = decode_nibble(freq.byte2 & 0x0F) - '0';
    u8 digit6 = decode_nibble((freq.byte3 >> 4) & 0x0F) - '0';
    u8 digit7 = decode_nibble(freq.byte3 & 0x0F) - '0';
    
    // Calculate numeric value (in MHz)
    double freq_mhz = digit0 * 100.0 + digit1 * 10.0 + digit2 * 1.0 +
                      digit3 * 0.1 + digit4 * 0.01 + digit5 * 0.001 +
                      digit6 * 0.0001 + digit7 * 0.00001;
    
    return freq_mhz;
};

// Channel name - 6 bytes encoded with custom character mapping
struct ChannelName {
    u8 char0_encoded [[name("C0")]];
    u8 char1_encoded [[name("C1")]];
    u8 char2_encoded [[name("C2")]];
    u8 char3_encoded [[name("C3")]];
    u8 char4_encoded [[name("C4")]];
    u8 char5_encoded [[name("C5")]];
} [[format("format_channel_name"), color("00FFFF")]];

fn format_channel_name(ChannelName name) {
    u8 c0 = decode_char(name.char0_encoded);
    u8 c1 = decode_char(name.char1_encoded);
    u8 c2 = decode_char(name.char2_encoded);
    u8 c3 = decode_char(name.char3_encoded);
    u8 c4 = decode_char(name.char4_encoded);
    u8 c5 = decode_char(name.char5_encoded);
    
    // Build string character by character
    str result = "";
    result += char(c0);
    result += char(c1);
    result += char(c2);
    result += char(c3);
    result += char(c4);
    result += char(c5);
    return result;
};

// Channel record - 16 bytes per channel
struct ChannelFrequencyData {
    Frequency rx_frequency [[comment("Receive frequency")]];
    Frequency tx_frequency [[comment("Transmit frequency")]];
    u8 other_data[8] [[comment("CTCSS/DCS codes, power, bandwidth, etc.")]];
};

// Channel configuration (frequency + name)
struct Channel {
    u32 channel_num;
    ChannelFrequencyData freq_data [[inline]];
};

// File header/configuration area
struct FileHeader {
    u8 unknown_header[0x255] [[comment("Radio configuration and settings")]];
};

// Channel names section - located at a different offset
struct ChannelNamesSection {
    ChannelName names[30] [[comment("Channel display names - 6 bytes each")]];
};

// Main file structure
struct KG_S88G_Config {
    // Channel frequency data at absolute offset 0x0255
    ChannelFrequencyData channel_freq_data[30] @ 0x0255 [[comment("Channel frequency configuration")]];
    
    // Channel names at absolute offset 0x1c4b
    ChannelNamesSection channel_names @ 0x1c4b [[comment("Channel names (6 bytes each)")]];
};

// Entry point
KG_S88G_Config config @ 0x00;

// Add some helpful comments at the top level
std::print("KG-S88G Radio Configuration");
std::print("============================");
std::print("Frequency encoding: Custom nibble-mapped BCD");
std::print("Channel name encoding: Custom character map");
std::print("Structure: 16 bytes per channel (RX + TX + settings)");
