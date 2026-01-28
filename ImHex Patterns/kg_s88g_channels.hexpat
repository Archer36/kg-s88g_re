#pragma description Wouxun KG-S88G Radio Configuration (Decoded Channels)
#pragma endian little
#pragma eval_depth 128

import std.mem;
import std.string;

// ============================================================================
// KG-S88G Decoded Channel View
// ============================================================================
// Shows human-readable frequency and name values
// 400 channels supported
// Settings A: Power (bit 0), Descramble (bits 2-5), SP Mute (bits 6-7)

// Nibble to digit mapping
fn decode_nibble(u8 nibble) {
    if (nibble == 0x5) return 0x30;
    else if (nibble == 0x4) return 0x31;
    else if (nibble == 0x7) return 0x32;
    else if (nibble == 0x6) return 0x33;
    else if (nibble == 0x1) return 0x34;
    else if (nibble == 0x0) return 0x35;
    else if (nibble == 0x3) return 0x36;
    else if (nibble == 0x2) return 0x37;
    else if (nibble == 0xD) return 0x38;
    else if (nibble == 0xC) return 0x39;
    else return 0x3f;
};

// Character decoding
fn decode_char(u8 b) {
    if (b == 0x5f) return 0x41;
    else if (b == 0x5e) return 0x42;
    else if (b == 0x59) return 0x43;
    else if (b == 0x58) return 0x44;
    else if (b == 0x5b) return 0x45;
    else if (b == 0x5a) return 0x46;
    else if (b == 0x45) return 0x47;
    else if (b == 0x44) return 0x48;
    else if (b == 0x47) return 0x49;
    else if (b == 0x46) return 0x4a;
    else if (b == 0x41) return 0x4b;
    else if (b == 0x40) return 0x4c;
    else if (b == 0x43) return 0x4d;
    else if (b == 0x42) return 0x4e;
    else if (b == 0x4d) return 0x4f;
    else if (b == 0x4c) return 0x50;
    else if (b == 0x4f) return 0x51;
    else if (b == 0x4e) return 0x52;
    else if (b == 0x49) return 0x53;
    else if (b == 0x48) return 0x54;
    else if (b == 0x4b) return 0x55;
    else if (b == 0x4a) return 0x56;
    else if (b == 0x75) return 0x57;
    else if (b == 0x74) return 0x58;
    else if (b == 0x77) return 0x59;
    else if (b == 0x76) return 0x5a;
    else if (b == 0x71) return 0x2d;
    else if (b == 0x55) return 0x30;
    else if (b == 0x54) return 0x31;
    else if (b == 0x57) return 0x32;
    else if (b == 0x56) return 0x33;
    else if (b == 0x51) return 0x34;
    else if (b == 0x50) return 0x35;
    else if (b == 0x53) return 0x36;
    else if (b == 0x52) return 0x37;
    else if (b == 0x5d) return 0x38;
    else if (b == 0x5c) return 0x39;
    else if (b == 0x7c) return 0x20;
    else if (b == 0xAA) return 0x20;
    else return 0x3f;
};

// Frequency structure with formatting
struct Frequency {
    u8 b3;
    u8 b2;
    u8 b1;
    u8 b0;
} [[format("fmt_freq")]];

fn fmt_freq(Frequency f) {
    if (f.b0 == 0xAA) return "(Empty)";
    str r = "";
    r += char(decode_nibble((f.b0 >> 4) & 0x0F));
    r += char(decode_nibble(f.b0 & 0x0F));
    r += char(decode_nibble((f.b1 >> 4) & 0x0F));
    r += '.';
    r += char(decode_nibble(f.b1 & 0x0F));
    r += char(decode_nibble((f.b2 >> 4) & 0x0F));
    r += char(decode_nibble(f.b2 & 0x0F));
    r += char(decode_nibble((f.b3 >> 4) & 0x0F));
    r += char(decode_nibble(f.b3 & 0x0F));
    r += " MHz";
    return r;
};

// Tone structure with formatting
struct Tone {
    u8 mode_byte;
    u8 index_byte;
} [[format("fmt_tone")]];

fn fmt_tone(Tone t) {
    u8 mode = t.mode_byte ^ 0x55;
    u8 idx = t.index_byte ^ 0x55;
    if (mode == 0) return "OFF";
    else if (mode == 1) return "CTCSS #" + std::string::to_string(idx);
    else if (mode == 2) return "DCS-N #" + std::string::to_string(idx);
    else if (mode == 3) return "DCS-I #" + std::string::to_string(idx);
    return "?";
};

// Settings structure with formatting
struct Settings {
    u8 a;
    u8 b;
    u8 c;
    u8 d;
} [[format("fmt_settings")]];

fn fmt_settings(Settings s) {
    u8 a = s.a ^ 0x55;
    u8 b = s.b ^ 0x55;
    u8 c = s.c ^ 0x55;
    str pwr = (a & 0x01) ? "High" : "Low";
    str bw = (c & 0x01) ? "Wide" : "Narrow";
    u8 desc = (a >> 2) & 0x0F;
    str desc_str = "";
    if (desc > 0) {
        desc_str = " Desc=" + std::string::to_string(desc);
    }
    str busy = (b & 0x01) ? " BusyLock" : "";
    return pwr + "/" + bw + desc_str + busy;
};

// Channel name structure
struct Name {
    u8 c[6];
} [[format("fmt_name")]];

fn fmt_name(Name n) {
    if (n.c[0] == 0xAA) return "(Empty)";
    str r = "";
    r += char(decode_char(n.c[0]));
    r += char(decode_char(n.c[1]));
    r += char(decode_char(n.c[2]));
    r += char(decode_char(n.c[3]));
    r += char(decode_char(n.c[4]));
    r += char(decode_char(n.c[5]));
    return r;
};

// Complete channel record
struct Channel {
    Frequency rx [[name("RX")]];
    Frequency tx [[name("TX")]];
    Tone rx_tone [[name("RX Tone")]];
    Tone tx_tone [[name("TX Tone")]];
    Settings settings [[name("Settings")]];
};

// VFO Record
struct VFORecord {
    Frequency rx [[name("VFO RX")]];
    Frequency tx [[name("VFO TX")]];
    Tone rx_tone [[name("VFO RX Tone")]];
    Tone tx_tone [[name("VFO TX Tone")]];
    Settings settings [[name("VFO Settings")]];
};

// CALL ID entry
struct CallIDEntry {
    u8 digits[6];
} [[format("fmt_name")]];

// Main file structure
struct KG_S88G_Channels {
    u8 header[0x0145] @ 0x0000 [[name("Header")]];
    VFORecord vfo @ 0x0145 [[name("VFO Record")]];
    u8 header2[0x0100] @ 0x0155 [[name("Header (cont)")]];
    Channel channels[400] @ 0x0255 [[name("Channels")]];
    u8 gap[0xF6] @ 0x1B55 [[name("Gap")]];
    Name names[400] @ 0x1C4B [[name("Names")]];
    u8 additional[0x021A] @ 0x25AB [[name("Additional")]];
    u8 favorites[51] @ 0x27C5 [[name("Favorites")]];
    u8 gap2[0x007F] @ 0x27F8 [[name("Gap 2")]];
    CallIDEntry call_ids[20] @ 0x2845 [[name("CALL IDs")]];
};

KG_S88G_Channels file @ 0x00;
