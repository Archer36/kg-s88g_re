#pragma description Wouxun KG-S88G Radio Configuration (Simple View)
#pragma endian little

// ============================================================================
// KG-S88G Simple Pattern - Color-coded channel view
// ============================================================================
// 400 channels, 16 bytes per channel record, 6 bytes per name
// Tone and settings use XOR 0x55 encoding
// Settings A: Power (bit 0), Descramble (bits 2-5), SP Mute (bits 6-7)

// Frequency field - 4 bytes
struct Freq {
    u8 data[4];
} [[color("00FF00")]];

// Tone field - 2 bytes (mode + index, XOR 0x55)
struct Tone {
    u8 mode;   // XOR 0x55: 0=OFF, 1=CTCSS, 2=DCS-N, 3=DCS-I
    u8 index;  // XOR 0x55: 1-based index
} [[color("FFFF00")]];

// Settings field - 4 bytes (all XOR 0x55)
struct Settings {
    u8 power_etc;    // Power(bit0), Descramble(bits2-5), SP Mute(bits6-7)
    u8 busylock_etc; // Busy Lock(bit0), Call ID(bits3-7)
    u8 bandwidth;    // Bandwidth(bit0: 1=Wide, 0=Narrow)
    u8 reserved;
} [[color("FF00FF")]];

// Complete channel record - 16 bytes
struct Channel {
    Freq rx [[name("RX Freq"), comment("Receive frequency")]];
    Freq tx [[name("TX Freq"), comment("Transmit frequency")]];
    Tone rx_tone [[name("RX Tone"), comment("RX CTCSS/DCS")]];
    Tone tx_tone [[name("TX Tone"), comment("TX CTCSS/DCS")]];
    Settings settings [[name("Settings"), comment("Power, BW, etc.")]];
};

// Channel name - 6 bytes
struct Name {
    char data[6];
} [[color("00FFFF")]];

// VFO Record - same structure as channel
struct VFORecord {
    Freq rx [[name("VFO RX"), comment("VFO Receive frequency")]];
    Freq tx [[name("VFO TX"), comment("VFO Transmit frequency")]];
    Tone rx_tone [[name("VFO RX Tone")]];
    Tone tx_tone [[name("VFO TX Tone")]];
    Settings settings [[name("VFO Settings")]];
} [[color("FF8800")]];

// CALL ID entry - 6 bytes
struct CallID {
    u8 digits[6];
} [[color("88FF88")]];

// Main structure
struct KG_S88G {
    // Header (first part)
    u8 header_start[0x0145] @ 0x0000 [[name("Header Start"), color("808080")]];

    // VFO Record
    VFORecord vfo @ 0x0145 [[name("VFO Record")]];

    // Gap to channel data
    u8 header_mid[0x0100] @ 0x0155 [[name("Header Mid"), color("808080")]];

    // Channel frequency/tone data (400 channels x 16 bytes)
    Channel channels[400] @ 0x0255 [[name("Channel Data")]];

    // Gap (0xAA padding)
    u8 gap[0xF6] @ 0x1B55 [[name("Gap"), color("404040")]];

    // Channel names (400 channels x 6 bytes)
    Name names[400] @ 0x1C4B [[name("Channel Names")]];

    // Additional settings
    u8 additional[0x021A] @ 0x25AB [[name("Additional Settings"), color("606060")]];

    // Favorites bitmap
    u8 favorites[51] @ 0x27C5 [[name("Favorites"), color("FF8800")]];

    // Gap to CALL IDs
    u8 gap2[0x007F] @ 0x27F8 [[name("Gap 2"), color("404040")]];

    // CALL ID list (20 entries x 6 bytes)
    CallID call_ids[20] @ 0x2845 [[name("CALL ID List")]];
};

KG_S88G file @ 0x00;
