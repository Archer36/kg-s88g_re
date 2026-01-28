#pragma description Wouxun KG-S88G Radio Configuration File
#pragma endian little
#pragma eval_depth 128

import std.mem;
import std.string;

// ============================================================================
// KG-S88G File Format Constants
// ============================================================================
// File size: 16712 bytes (0x4148)
// Channels: 400 total
// Frequency data: 0x0255 - 0x1B54 (6400 bytes, 16 bytes per channel)
// Channel names: 0x1C4B - 0x25AA (2400 bytes, 6 bytes per channel)
// ============================================================================

// XOR mask for tone and settings encoding
#define XOR_MASK 0x55

// Custom nibble-to-digit mapping used by KG-S88G
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

// Decode a single encoded character byte to ASCII
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
    else if (encoded_byte == 0x71) return 0x2d; // '-'
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
    else if (encoded_byte == 0xAA) return 0x20; // Empty marker
    else return 0x3f; // '?'
};

// ============================================================================
// Frequency Structure
// ============================================================================
// 4 bytes, nibble-mapped BCD, little-endian (reversed)
// Format: XXX.YYYYY MHz (8 digits total)

struct Frequency {
    u8 byte3;
    u8 byte2;
    u8 byte1;
    u8 byte0;
} [[format("format_frequency")]];

fn format_frequency(Frequency freq) {
    // Check for empty channel marker
    if (freq.byte0 == 0xAA && freq.byte1 == 0xAA) {
        return "----.---- MHz (Empty)";
    }

    u8 d0 = decode_nibble((freq.byte0 >> 4) & 0x0F);
    u8 d1 = decode_nibble(freq.byte0 & 0x0F);
    u8 d2 = decode_nibble((freq.byte1 >> 4) & 0x0F);
    u8 d3 = decode_nibble(freq.byte1 & 0x0F);
    u8 d4 = decode_nibble((freq.byte2 >> 4) & 0x0F);
    u8 d5 = decode_nibble(freq.byte2 & 0x0F);
    u8 d6 = decode_nibble((freq.byte3 >> 4) & 0x0F);
    u8 d7 = decode_nibble(freq.byte3 & 0x0F);

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

// ============================================================================
// Tone Structure (CTCSS/DCS)
// ============================================================================
// 2 bytes per tone: [MODE_BYTE][INDEX_BYTE]
// Both bytes XORed with 0x55
// Mode: 0=OFF, 1=CTCSS, 2=DCS-N, 3=DCS-I
// Index: 1-based into CTCSS (1-38) or DCS (1-104) list

struct Tone {
    u8 mode_byte;   // XOR 0x55: 0=OFF, 1=CTCSS, 2=DCS-N, 3=DCS-I
    u8 index_byte;  // XOR 0x55: 1-based index
} [[format("format_tone")]];

fn format_tone(Tone t) {
    u8 mode = t.mode_byte ^ 0x55;
    u8 idx = t.index_byte ^ 0x55;

    if (mode == 0) return "OFF";
    else if (mode == 1) {
        // CTCSS - show index (would need lookup table for actual Hz)
        return "CTCSS #" + std::string::to_string(idx);
    }
    else if (mode == 2) {
        return "DCS-N #" + std::string::to_string(idx);
    }
    else if (mode == 3) {
        return "DCS-I #" + std::string::to_string(idx);
    }
    return "Unknown";
};

// ============================================================================
// Channel Settings Structure
// ============================================================================
// 4 bytes at offset +12, all XORed with 0x55
// Byte 12: Power (bit 0), Descramble (bits 2-3), SP Mute (bits 6-7)
// Byte 13: Busy Lock (bit 0), Call ID (bits 3-7)
// Byte 14: Bandwidth (bit 0)
// Byte 15: Reserved

struct ChannelSettings {
    u8 settings_a;  // Power, Descramble, SP Mute
    u8 settings_b;  // Busy Lock, Call ID
    u8 settings_c;  // Bandwidth
    u8 settings_d;  // Reserved
} [[format("format_settings")]];

fn format_settings(ChannelSettings s) {
    u8 a = s.settings_a ^ 0x55;
    u8 b = s.settings_b ^ 0x55;
    u8 c = s.settings_c ^ 0x55;

    str power = (a & 0x01) ? "High" : "Low";
    str bw = (c & 0x01) ? "Wide" : "Narrow";
    str busy = (b & 0x01) ? "BusyLock" : "";
    u8 call_id = (b >> 3) & 0x1F;

    return power + "/" + bw + " CallID=" + std::string::to_string(call_id);
};

// ============================================================================
// Channel Name Structure
// ============================================================================
// 6 bytes, custom character encoding

struct ChannelName {
    u8 chars[6];
} [[format("format_channel_name"), color("00FFFF")]];

fn format_channel_name(ChannelName name) {
    // Check for empty
    if (name.chars[0] == 0xAA) return "(Empty)";

    str result = "";
    result += char(decode_char(name.chars[0]));
    result += char(decode_char(name.chars[1]));
    result += char(decode_char(name.chars[2]));
    result += char(decode_char(name.chars[3]));
    result += char(decode_char(name.chars[4]));
    result += char(decode_char(name.chars[5]));
    return result;
};

// ============================================================================
// Complete Channel Record (16 bytes)
// ============================================================================

struct ChannelRecord {
    Frequency rx_frequency [[comment("Receive frequency")]];
    Frequency tx_frequency [[comment("Transmit frequency")]];
    Tone rx_tone [[comment("RX CTCSS/DCS")]];
    Tone tx_tone [[comment("TX CTCSS/DCS")]];
    ChannelSettings settings [[comment("Power, BW, etc.")]];
};

// ============================================================================
// Main File Structure
// ============================================================================

struct KG_S88G_Config {
    // Header section (radio settings)
    u8 header[0x0255] @ 0x0000 [[comment("Radio settings and configuration")]];

    // Channel frequency data: 400 channels x 16 bytes = 6400 bytes
    // Located at 0x0255 - 0x1B54
    ChannelRecord channels[400] @ 0x0255 [[comment("Channel frequency/tone/settings data")]];

    // Gap between freq data and names (filled with 0xAA)
    u8 gap[0xF6] @ 0x1B55 [[comment("Padding (0xAA)")]];

    // Channel names: 400 channels x 6 bytes = 2400 bytes
    // Located at 0x1C4B - 0x25AA
    ChannelName names[400] @ 0x1C4B [[comment("Channel names (6 chars each)")]];

    // Favorites bitmap at 0x27C5 (51 bytes for 400 channels)
    u8 favorites[51] @ 0x27C5 [[comment("Favorites bitmask")]];
};

// Entry point
KG_S88G_Config config @ 0x00;

std::print("===========================================");
std::print("KG-S88G Radio Configuration File");
std::print("===========================================");
std::print("Channels: 400");
std::print("Freq data: 0x0255-0x1B54 (16 bytes/ch)");
std::print("Names: 0x1C4B-0x25AA (6 bytes/ch)");
std::print("Tone encoding: XOR 0x55");
std::print("===========================================");
