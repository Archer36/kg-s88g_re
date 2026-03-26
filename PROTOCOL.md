# KG-S88G USB Programming Protocol

This document describes the serial protocol used by the Wouxun KG-S88G to transfer
the radio's EEPROM image over the USB programming cable.

See `PCAP_ANALYSIS.md` for how this protocol was reverse-engineered from USB captures.
See `EEPROM_FORMAT.md` for the structure of the data transferred.

---

## Physical Layer

- **Interface**: USB-to-Serial adapter (CH340 or similar chipset)
- **Baud rate**: 9,600 bps
- **Data format**: 8 data bits, no parity, 1 stop bit (8N1)
- **Logic levels**: 3.3V CMOS (HIGH measured at 3.278V, LOW = 0V). Output drives
  rail-to-rail as expected for CMOS; the small drop from nominal 3.3V is normal
  MOSFET on-resistance. Do **not** connect a 5V TTL serial adapter directly — it
  will likely damage the radio's RX input.
- **USB endpoints**: 0x01 (host → radio / TX), 0x81 (radio → host / RX)
- **Byte timing**: The CPS sends each byte individually with ~2 ms inter-byte delay.
  The CHIRP driver replicates this behavior to ensure radio compatibility.

### Radio-Side Connector Pinout

The programming cable uses two TRS audio connectors on the radio end. Pinout
determined via logic analyser:

**2.5mm TRS** (smaller connector):

| Contact | Signal | Description |
|---------|--------|-------------|
| Sleeve | GND | Data ground |
| Ring | Radio TX | Serial data output from radio to PC |
| Tip | — | Not used for data |

**3.5mm TRS** (larger connector):

| Contact | Signal | Description |
|---------|--------|-------------|
| Sleeve | Radio RX | Serial data input to radio from PC |
| Ring | — | Not used for data |
| Tip | — | Not used for data |

The USB programming cable's internal adapter converts these signals to USB via a
CH340 (or compatible) USB-to-serial bridge chip, which handles the 3.3V CMOS ↔
USB level conversion.

### Echo Behavior

Some USB-to-serial adapters echo TX bytes back on the RX line. The radio itself does
not echo. The driver detects echo mode automatically during the handshake:

- After sending the 8-byte magic packet, read the first byte back.
- If the first byte is `0x02` (our own byte), the adapter is echoing → skip echoed bytes.
- If the first byte is `0x06` (radio ACK), no echo.

---

## Session Overview

A programming session consists of three phases:

```
┌─────────────────────────────────────────────────┐
│  1. HANDSHAKE (plaintext)                       │
│     Establish session and derive cipher key     │
├─────────────────────────────────────────────────┤
│  2. DATA TRANSFER (encrypted)                   │
│     Read or write EEPROM in 16-byte blocks      │
├─────────────────────────────────────────────────┤
│  3. TERMINATE (encrypted)                       │
│     Single-byte close signal                    │
└─────────────────────────────────────────────────┘
```

Download uses magic `"RWITF"`. Upload uses magic `"WRITF"`.

---

## Phase 1: Handshake (Plaintext)

All handshake messages are **unencrypted**. The cipher is initialized at the
end of the handshake and takes effect only in the data phase.

### Step 1 — TX: Magic Packet (8 bytes)

```
02 [M1 M2 M3 M4 M5] FF FF
```

- `0x02`: Session start marker
- `[M1..M5]`: 5-byte magic string — `"RWITF"` (download) or `"WRITF"` (upload)
- `0xFF 0xFF`: Terminator

Download example: `02 52 57 49 54 46 FF FF`
Upload example:   `02 57 52 49 54 46 FF FF`

**Radio response**: `0x06` (ACK)

If no ACK is received, the driver retries up to 5 times before failing.

### Step 2 — TX: Key Material (16 bytes, plaintext)

```
A5 [km1] [km2] [km3] [km4..km15]
```

- `0xA5`: Required magic byte. The radio validates this; sessions with a different
  first byte are rejected.
- `km[1]` and `km[3]`: Determine the data-phase cipher starting key:
  `data_phase_key = km[1] XOR km[3]`
- `km[8..15]`: Arbitrary bytes that the radio echoes back in its key response.

The CHIRP driver sends `A5 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00`,
yielding `data_phase_key = 0x00 XOR 0x00 = 0x00`. This is intentionally
predictable and simplifies debugging.

**No ACK from radio** — proceed to next step.

### Step 3 — RX: Radio Identity (12 bytes, plaintext)

The radio sends a 12-byte identity packet. Content is mostly constant across
sessions (firmware/model identifier). No specific fields have been decoded beyond
confirming it is consistent per radio.

**Driver sends**: `0x06` (ACK)

### Step 4 — RX: Key Response (18 bytes, plaintext)

The radio sends an 18-byte response. Bytes [9..16] echo back `km[8..15]` from
the key material sent in Step 2. This confirms the radio received the key material.

**Driver sends**: `0x06` (ACK)

### Step 5 — RX: Final ACK (1 byte)

Radio sends `0x06`. Handshake is complete.

**Cipher is now initialized** with `key = data_phase_key`.

---

## Rolling XOR Cipher

The data phase uses a rolling (self-synchronizing) XOR stream cipher.

### Key State

The cipher maintains a single 8-bit key byte that evolves with every encrypted
byte processed. Key state is **shared across all packets** in sequence — both TX
and RX packets interleave through the same key state.

### Decryption

```
plain_byte = enc_byte XOR key
key        = (key + enc_byte) & 0xFF
```

### Encryption

```
enc_byte = plain_byte XOR key
key      = (key + enc_byte) & 0xFF
```

Note: because `key` is updated with the *encrypted* byte (not the plaintext byte),
decryption and encryption use the same key advancement formula when applied
to the ciphertext stream.

### Byte 0 Exception

**Byte 0 of each packet is NOT encrypted and does NOT advance the key.**

It is sent and received as plaintext. Bytes 1 onwards are encrypted normally.
This means the key state after packet N depends only on bytes 1+ of that packet,
not byte 0.

### Example

Key = `0x00`. Plaintext TX: `57 00 00 00 00 10`

```
Byte 0: 0x57 → sent as-is (no encrypt, key stays 0x00)
Byte 1: 0x00 → enc = 0x00 XOR 0x00 = 0x00; key = (0x00 + 0x00) & 0xFF = 0x00
Byte 2: 0x00 → enc = 0x00 XOR 0x00 = 0x00; key = 0x00
Byte 3: 0x00 → enc = 0x00; key = 0x00
Byte 4: 0x00 → enc = 0x00; key = 0x00
Byte 5: 0x10 → enc = 0x10 XOR 0x00 = 0x10; key = (0x00 + 0x10) & 0xFF = 0x10
```

With key = `0x00` (as the CHIRP driver uses), the first read command is sent unmodified.

---

## Phase 2a: Data Transfer — Download (Read)

The host reads the radio's EEPROM in 16-byte blocks, sequentially from address
`0x0000` to `0x27CF`.

### Read Command (TX, 5 bytes encrypted)

```
[0x57] [addr_hi] [addr_mid] [addr_lo] [0x10]
```

- `0x57`: Read command byte (byte 0, not encrypted)
- `addr_hi/mid/lo`: 24-bit EEPROM address (big-endian)
- `0x10`: Block length = 16 bytes

### Read Response (RX, 21 bytes encrypted)

```
[0x57] [addr_hi] [addr_mid] [addr_lo] [0x10] [16 data bytes]
```

- Byte 0 (`0x57`): Not encrypted
- Bytes 1–4: Echo of address and length (encrypted) — driver verifies address match
- Bytes 5–20: 16 bytes of EEPROM data (encrypted)

The driver extracts bytes [5..20] from each response to build the EEPROM image.

### Terminate (TX, 1 byte encrypted)

After all blocks are read, the host sends a single encrypted byte `0x54` (terminate).

---

## Phase 2b: Data Transfer — Upload (Write)

The host writes the EEPROM in 16-byte blocks, same address range `0x0000–0x27CF`.

### Write Command (TX, 21 bytes encrypted)

```
[0x57] [addr_hi] [addr_mid] [addr_lo] [0x10] [16 data bytes]
```

- Same structure as the read response, but sent by the host
- Byte 0 (`0x57`): Not encrypted

### Write ACK (RX, 1 byte, **unencrypted**)

The radio responds with a plain `0x06` ACK after each block.

**Important**: The write ACK is NOT encrypted — it does not pass through the cipher
and does NOT advance the cipher key.

---

## Pre-Upload: Channel Presence Bitmaps

Before uploading, the CHIRP driver recomputes two 50-byte bitmaps stored at
EEPROM offsets `0x2500` and `0x2600`. These bitmaps indicate which channel slots
contain valid data. The radio silently ignores channels not marked in this bitmap,
even if frequency data is present at the channel's offset.

Bit assignment: channel N (1-based) → bit `N % 8` of byte `N // 8`.

The driver sets bits based on whether the channel's RX frequency bytes are non-zero
and non-0xFF. Both 0x2500 and 0x2600 receive identical values.

---

## Full Session Diagram

```
PC                                    RADIO
│                                         │
│── 02 RWITF FF FF ────────────────────►│  Step 1: Magic (plaintext)
│◄──────────────────────────────── 06 ───│  ACK
│                                         │
│── A5 00*15 ─────────────────────────►│  Step 2: Key material (plaintext)
│                                         │
│◄─── 12-byte identity ──────────────────│  Step 3: Radio identity (plaintext)
│── 06 ───────────────────────────────►│  ACK
│                                         │
│◄─── 18-byte key response ──────────────│  Step 4: Key response (plaintext)
│── 06 ───────────────────────────────►│  ACK
│                                         │
│◄────────────────────────────── 06 ───│  Step 5: Final ACK
│                         [cipher active, key=0x00]
│                                         │
│ ── enc(57 00 00 00 10) ─────────────►│  Read addr 0x0000
│◄─── enc(57 00 00 00 10 + 16 bytes) ───│  Response + data
│                                         │
│ ── enc(57 00 00 10 10) ─────────────►│  Read addr 0x0010
│◄─── enc(57 00 00 10 10 + 16 bytes) ───│  Response + data
│  ...                                    │
│ ── enc(57 00 27 C0 10) ─────────────►│  Read addr 0x27C0 (last block)
│◄─── enc(57 00 27 C0 10 + 16 bytes) ───│  Response + data
│                                         │
│ ── enc(54) ─────────────────────────►│  Terminate
│                                         │
```

---

## Address Space

- **Range read/written**: `0x0000` to `0x27CF` (step `0x10`)
- **Total blocks**: 637 blocks × 16 bytes = **10,192 bytes**
- The addresses are sequential with no gaps; no skipped regions within `0x0000–0x27CF`

---

## Notes and Observations

- The protocol was fully derived from USB captures (see `PCAP_ANALYSIS.md`).
  No firmware disassembly was required to implement a working driver.
- The CPS software uses non-zero key material (different `km[1]` and `km[3]` each
  session), yielding a randomized `data_phase_key`. The CHIRP driver deliberately
  uses all-zero key material for simplicity and debuggability.
- The cipher key state is cumulative — after 637 read cycles (each 5-byte TX and
  21-byte RX), the key has advanced through 637 × (4 + 20) = 15,288 encrypted bytes.
- Write ACKs (`0x06`) being unencrypted was confirmed by comparing captures where
  the expected `0x06` appeared without matching the current cipher keystream.
