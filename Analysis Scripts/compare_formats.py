#!/usr/bin/env python3
"""Compare EEPROM and .dat encodings to find the relationship."""

# .dat character encoding (from CLAUDE_CODE_SUMMARY.md)
DAT_CHARS = {
    'A': 0x5f, 'B': 0x5e, 'C': 0x59, 'D': 0x58, 'E': 0x5b, 'F': 0x5a,
    'G': 0x45, 'H': 0x44, 'I': 0x47, 'J': 0x46, 'K': 0x41, 'L': 0x40,
    'M': 0x43, 'N': 0x42, 'O': 0x4d, 'P': 0x4c, 'Q': 0x4f, 'R': 0x4e,
    'S': 0x49, 'T': 0x48, 'U': 0x4b, 'V': 0x4a, 'W': 0x75, 'X': 0x74,
    'Y': 0x77, 'Z': 0x76,
    '0': 0x55, '1': 0x54, '2': 0x57, '3': 0x56, '4': 0x51, '5': 0x50,
    '6': 0x53, '7': 0x52, '8': 0x5d, '9': 0x5c,
    ' ': 0x7c, '-': 0x71,
}

print("=" * 70)
print("HYPOTHESIS: .dat encoding = EEPROM encoding XOR 0x55")
print("=" * 70)

print("\nCharacter encoding check:")
print(f"{'Char':<6} {'dat':>6} {'dat^0x55':>8} {'sequential?':>12}")
for ch, dat_val in sorted(DAT_CHARS.items(), key=lambda x: x[1]):
    eeprom_val = dat_val ^ 0x55
    print(f"  {ch!r:<4}  0x{dat_val:02x}    0x{eeprom_val:02x}       ", end="")
    if ch.isdigit():
        expected = int(ch)
        print(f"digit {ch} → 0x{eeprom_val:02x} = {eeprom_val} ({'✓' if eeprom_val == expected else '✗'})")
    elif ch.isalpha():
        expected = ord(ch.upper()) - ord('A') + 10
        print(f"letter {ch} → 0x{eeprom_val:02x} = {eeprom_val} ({'✓' if eeprom_val == expected else '✗'})")
    else:
        print(f"special → 0x{eeprom_val:02x} = {eeprom_val}")

# .dat nibble-to-digit mapping
print("\nFrequency nibble encoding check:")
dat_nibble = {5: 0, 4: 1, 7: 2, 6: 3, 1: 4, 0: 5, 3: 6, 2: 7, 0xD: 8, 0xC: 9}
print(f"{'Digit':<6} {'dat_nibble':>10} {'nibble^0x5':>10} {'= digit?':>10}")
for nibble, digit in sorted(dat_nibble.items(), key=lambda x: x[1]):
    eeprom_nibble = nibble ^ 0x5
    print(f"  {digit}      0x{nibble:X}         0x{eeprom_nibble:X}         {'✓' if eeprom_nibble == digit else '✗'}")

# Verify: XOR 0x55 at byte level encompasses nibble XOR 0x5
print("\nByte-level frequency check:")
print("BCD byte 0x46 (digits 4,6):")
print(f"  0x46 ^ 0x55 = 0x{0x46^0x55:02x} = 0x13")
print(f"  .dat for '46' in freq: nibbles 1,3 → byte 0x13 ✓")

# Now decode EEPROM names
print("\n" + "=" * 70)
print("EEPROM NAME DECODING")
print("=" * 70)

# Build EEPROM char map (= dat values XOR 0x55)
EEPROM_CHARS = {}
for ch, dat_val in DAT_CHARS.items():
    EEPROM_CHARS[dat_val ^ 0x55] = ch

eeprom_names_raw = [
    bytes([0x15, 0x1d, 0x24, 0x01, 0x29, 0x29]),  # slot 1
    bytes([0x15, 0x1d, 0x24, 0x02, 0x29, 0x29]),  # slot 2
    bytes([0x15, 0x1d, 0x24, 0x03, 0x29, 0x29]),  # slot 3
    bytes([0x15, 0x1d, 0x24, 0x04, 0x1c, 0x29]),  # slot 4
    bytes([0x15, 0x1d, 0x24, 0x05, 0x29, 0x29]),  # slot 5
    bytes([0x15, 0x1d, 0x24, 0x06, 0x29, 0x29]),  # slot 6
    bytes([0x15, 0x1d, 0x24, 0x07, 0x19, 0x29]),  # slot 7
    bytes([0x15, 0x1d, 0x24, 0x08, 0x29, 0x29]),  # slot 8
]

for i, raw in enumerate(eeprom_names_raw):
    decoded = ''.join(EEPROM_CHARS.get(b, f'?{b:02x}') for b in raw)
    hex_str = ' '.join(f'{b:02x}' for b in raw)
    print(f"  Slot {i+1}: {hex_str} → \"{decoded}\"")

# Verify tone encoding
print("\n" + "=" * 70)
print("TONE ENCODING CHECK")
print("=" * 70)
print("EEPROM tone bytes at 0x0110: 01 25 01 25")
print(f"  Mode = 0x01 → CTCSS (raw value, no XOR)")
print(f"  Index = 0x25 = {0x25} decimal")
print(f"  In .dat: mode would be 0x01^0x55 = 0x{0x01^0x55:02x}, idx = 0x25^0x55 = 0x{0x25^0x55:02x}")
print(f"  .dat decode: mode = 0x{0x01^0x55:02x}^0x55 = {(0x01^0x55)^0x55} = CTCSS ✓")
print(f"  .dat decode: idx = 0x{0x25^0x55:02x}^0x55 = {(0x25^0x55)^0x55} = 37")

CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5,
    94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8
]
print(f"  CTCSS tone 37 (1-based) = {CTCSS_TONES[36]} Hz")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("""
The .dat file is the EEPROM data with ALL bytes XOR'd with 0x55.

This single transformation explains ALL the "custom encodings" found in
the .dat file reverse engineering:
  - "Custom nibble mapping" = standard BCD nibbles XOR 0x5 (= byte XOR 0x55)
  - "Custom character encoding" = sequential encoding (0-9, A-Z) XOR 0x55
  - "XOR 0x55 settings" = raw EEPROM values XOR 0x55
  - "XOR 0x55 tones" = raw EEPROM tone mode/index XOR 0x55

The .dat file also has a different memory layout/offset than the EEPROM,
adding headers, padding, and rearranging sections.
""")
