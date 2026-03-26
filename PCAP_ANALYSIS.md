# KG-S88G PCAP Analysis Methodology

This document describes how USB packet captures were taken, how serial byte streams
were extracted from them, and how they were used to reverse-engineer the radio's
programming protocol.

See `PROTOCOL.md` for the protocol findings. See `EEPROM_FORMAT.md` for the EEPROM
image findings.

---

## Hardware Setup

The KG-S88G connects to a PC via a proprietary USB programming cable. The cable
contains a USB-to-serial bridge chip (CH340 or compatible) that presents as a
virtual COM port. The radio's serial interface runs at **9,600 bps, 8N1**.

At the USB layer, data appears as HID bulk transfer packets on two endpoints:
- `0x01`: Host → Radio (TX / OUT)
- `0x81`: Radio → Host (RX / IN)

The actual serial bytes are the payload of these USB frames. No USB-serial dissector
is applied by Wireshark at this layer — the bytes appear as raw `usb.capdata`.

---

## Capture Setup

### Windows (USBPcap)

1. Install [USBPcap](https://desowin.org/usbpcap/) (also bundled with Wireshark).
2. Open Wireshark → select the USBPcap interface that shows the programming cable.
3. Begin capture, connect the cable and open the CPS software or CHIRP.
4. Perform the desired operation (download/upload).
5. Stop capture and save as `.pcapng`.

The programming cable must be connected **before** starting the CPS software.
The radio must be powered on and connected before initiating any programming.

---

## Extracting Serial Bytes with tshark

The following `tshark` command extracts relevant USB frames as tab-separated fields:

```bash
tshark -r capture.pcapng \
  -Y "(usb.endpoint_address == 0x01 || usb.endpoint_address == 0x81) and usb.capdata" \
  -T fields \
  -e frame.number \
  -e usb.src \
  -e usb.dst \
  -e usb.capdata
```

### Filter Explanation

- `usb.endpoint_address == 0x01`: TX frames (host to radio)
- `usb.endpoint_address == 0x81`: RX frames (radio to host)
- `usb.capdata`: Exclude frames with no payload (setup/status packets)

### Output Format

Each line contains four tab-separated fields:
```
<frame_number> \t <src> \t <dst> \t <capdata>
```

- `src`: Source address string — contains `"host"` if the PC sent the frame
- `capdata`: Hex bytes separated by colons, e.g. `02:52:57:49:54:46:ff:ff`

### Direction Determination

```python
if 'host' in src:
    direction = 'TX'   # PC → Radio
else:
    direction = 'RX'   # Radio → PC
```

---

## Packet Reassembly

A single logical serial transaction may span multiple USB frames (if the payload
exceeds one USB packet, or if timing splits frames). Consecutive frames in the
same direction are merged:

```python
transactions = []
current_dir = None
current_bytes = bytearray()

for line in tshark_output:
    frame, src, dst, capdata = line.split('\t')
    raw = bytes.fromhex(capdata.replace(':', ''))
    direction = 'TX' if 'host' in src else 'RX'

    if direction != current_dir and current_bytes:
        transactions.append((current_dir, bytes(current_bytes)))
        current_bytes = bytearray()

    current_dir = direction
    current_bytes.extend(raw)

if current_bytes:
    transactions.append((current_dir, bytes(current_bytes)))
```

This produces a list of `(direction, bytes)` tuples representing complete
logical messages.

---

## Identifying the Handshake

The first several transactions are the handshake (plaintext). They are identifiable
by their fixed structure:

| # | Dir | Length | Content |
|---|-----|--------|---------|
| 0 | TX | 8 | `02 52 57 49 54 46 FF FF` ("RWITF" magic) |
| 1 | RX | 1 | `06` (ACK) |
| 2 | TX | 16 | Key material starting with `A5 ...` |
| 3 | RX | 12 | Radio identity (mostly constant) |
| 4 | TX | 1 | `06` (ACK) |
| 5 | RX | 18 | Key response |
| 6 | TX | 1 | `06` (ACK) |
| 7 | RX | 1 | `06` (final ACK) |

Transaction index 8 onward is the data phase (encrypted).

---

## Deciphering the Data Phase

### Key Discovery

The data-phase cipher key (`data_phase_key`) was determined by brute force:

```python
for key in range(256):                               # (1) try every possible starting key
    k = key
    valid = True
    expected_addr = None
    for direction, data in transactions[8:8+10]:     # (2) process the first 10 data-phase packets
        dec = bytearray([data[0]])                   # (3) byte 0 passes through unencrypted
        for byte in data[1:]:
            dec.append(byte ^ k)                     # (4) XOR each byte with running key
            k = (k + byte) & 0xFF                   # (5) advance key using the ciphertext byte
        if direction == 'TX' and len(dec) == 5 and dec[0] == 0x57:
            addr = (dec[1] << 16) | (dec[2] << 8) | dec[3]  # (6) reconstruct 24-bit address
            if expected_addr is None:
                expected_addr = addr                 # (7) record first address seen
            elif addr != expected_addr + 0x10:
                valid = False; break                 # (8) wrong key: addresses not sequential
            expected_addr = addr
    if valid and expected_addr is not None:
        print(f"Key: {key:#04x}")                   # (9) correct key found
        break
```

What this does, step by step:

1. **Try all 256 candidate keys** — the cipher key is a single byte, so exhaustive search
   is practical.
2. **Simulate decryption over the first 10 data-phase packets** — both TX and RX,
   with the key state carried continuously from one packet to the next, exactly as the
   radio and CPS do it.
3. **Byte 0 is not decrypted** — it is always the command byte `0x57` in plaintext.
4. **XOR each subsequent byte with the current key** — the Ghidra-derived algorithm.
5. **Advance the key using the ciphertext byte** (the raw captured byte, not the
   decrypted result) — this is the self-synchronizing property: both sides update
   their key state from the same byte stream.
6. **Reconstruct the 24-bit EEPROM address** from bytes 1–3 of each decrypted TX packet.
7. **Record the first address** as the baseline.
8. **Reject the key if any address fails to increment by exactly `0x10`** — a valid
   EEPROM read sequence always steps by 16 bytes per block, so any deviation means
   the candidate key is wrong.
9. **The first key that produces all-sequential addresses is the correct one.**

The sequential-address check is a strong validity signal: the probability of a wrong
key accidentally producing 5+ correctly-spaced addresses is negligible, so false
positives do not occur in practice.

This was applied to multiple captures:

| Capture | Magic | Data-Phase Key |
|---------|-------|---------------|
| `stock-read-from-radio.pcapng` | RWITF | 0x00 |
| `stock-write-to-radio.pcapng` | WRITF | 0xE6 |

The differing keys across captures showed the CPS uses random key material each session.

### Key Derivation Formula

Once the per-capture keys were known from brute force, the next question was: how
does the CPS produce that key? It had to be derived from something in the handshake,
since the radio and CPS agree on the same key without an explicit key exchange message.

**Looking at the handshake key material packet** (transaction 2, 16 bytes, plaintext):

A download triggered from the CPS with custom frequencies set shows the CPS sent:
```
A5 b4 09 f8 8d cf 35 61 35 4c 65 fb ec 63 a7 82
```
The brute-forced data-phase key for that capture was `0x4C`.

Immediately visible: `0x4C` appears at byte index 9 of the key material — but that
felt too coincidental, so every possible relationship between the 16 key material
bytes and the known key was examined systematically. The formula that held across
all four captures was:

```
data_phase_key = km[1] XOR km[3]
```

Verified against each capture:

| Capture | km[1] | km[3] | km[1] XOR km[3] | Brute-forced key |
|---------|-------|-------|-----------------|-----------------|
| CPS download (custom config) | 0xB4 | 0xF8 | 0x4C | 0x4C ✓ |
| `stock-read-from-radio.pcapng` | 0x00 | 0x00 | 0x00 | 0x00 ✓ |
| `stock-write-to-radio.pcapng` | 0x?? | 0x?? | 0xE6 | 0xE6 ✓ |

The `stock-read` capture had key=0x00, consistent with the CPS sending zeroes at
positions 1 and 3 in that session (or those bytes not being randomised every time).

**How km[1] and km[3] were identified:**

The exact path is not fully certain, but there are two plausible routes — likely
both played a role:

*Route A — Ghidra disassembly (most probable primary source):*
The Ghidra scripts that searched for protocol-related functions would have found
the key initialisation routine alongside the cipher itself. That function reads the
key material buffer at specific byte offsets and computes the starting key; the
XOR of positions 1 and 3 would appear directly in the decompiler output as something
like `key = km[1] ^ km[3]`. If this is what happened, the formula was read from the
disassembly and the captures were used to *confirm* it rather than to derive it.

*Route B — Systematic cross-capture search (possible corroboration):*
With the brute-forced keys and the raw key material bytes from each capture in hand,
every candidate formula of the form `f(km) = key` can be checked exhaustively:
- 16 single-byte candidates: `km[i] == key` for i in 0..15
- 120 XOR-pair candidates: `km[i] XOR km[j] == key` for all pairs i,j
- Plus sum, difference, and other simple combinations

The CPS download with non-trivial km bytes (key=`0x4C`) provides the most
discriminating test — many formulas will produce `0x4C` by coincidence from one
capture, but most are eliminated when cross-checked against `stock-write`
(key=`0xE6`) and the stock-read capture (key=`0x00`). The formula
`km[1] XOR km[3]` is the one consistent across all of them.

In practice the Ghidra route is more likely to have been the initial finding,
with the cross-capture check serving as independent confirmation. No analysis
script specifically implementing Route B survives in the `Analysis Scripts/` directory, whereas
the Ghidra scripts do. If you recall it being from the disassembly, trust that.

**Why km[1] and km[3] specifically?**

Presumably a deliberate design choice in the CPS firmware. The two bytes are XOR'd
together so neither alone determines the key — a weak form of two-factor key
contribution. No documentation of the design intent exists beyond what the
disassembly shows. The radio validates `km[0] == 0xA5` (confirmed by testing:
sessions with a different first byte are rejected) but does not appear to validate
any other specific byte values in the key material.

**CHIRP driver implication:**

The driver deliberately sends `A5 00 00 00 ...` (all zeros after the magic byte),
giving `km[1] XOR km[3] = 0x00 XOR 0x00 = 0x00`. A zero starting key means the
first encrypted byte is XOR'd with zero — i.e. sent unmodified — which makes it
trivial to inspect a captured CHIRP session without any decryption tooling.

### Validating the Cipher

After decrypting with the correct key, every TX packet in the data phase has the form:
```
57 [addr_hi] [addr_mid] [addr_lo] 10
```
with addresses incrementing by `0x10` each block. This sequential structure
provides a reliable validity check.

Every RX packet has the form:
```
57 [addr_hi] [addr_mid] [addr_lo] 10 [16 data bytes]
```
with the address echoing the TX command.

---

## Reconstructing the EEPROM Image

```python
eeprom = bytearray(b'\xff' * 0x10000)
cipher_key = 0x00   # or brute-forced value

key = cipher_key
for direction, data in transactions[8:]:
    dec = bytearray([data[0]])    # byte 0 unencrypted
    for byte in data[1:]:
        dec.append(byte ^ key)
        key = (key + byte) & 0xFF

    if direction == 'RX' and len(dec) == 21 and dec[0] == 0x57:
        addr = (dec[1] << 16) | (dec[2] << 8) | dec[3]
        payload = dec[5:]         # 16 data bytes
        eeprom[addr:addr+16] = payload
```

The resulting byte array is a faithful image of the radio's EEPROM content.

---

## Echo Detection

Some USB-to-serial adapters loop TX bytes back on the RX line. This appears in
captures as RX frames immediately after TX frames containing the same bytes.

To detect: after sending the 8-byte magic, check the first byte received:
- `0x02` → echo (matches our own magic prefix) — skip ahead by reading remainder of echo
- `0x06` → no echo (direct ACK from radio)

In echo mode, each TX operation requires reading back the same number of bytes
before proceeding.

---

## Captures Taken

| File | Direction | Magic | Notes |
|------|-----------|-------|-------|
| `PCAPs/stock-read-from-radio.pcapng` | Read | RWITF | Stock radio read, key=0x00 |
| `PCAPs/stock-write-to-radio.pcapng` | Write | WRITF | Stock radio write-back, key=0xE6 |

---

## Analysis Scripts

All scripts are in `Analysis Scripts/`.

### Ghidra Scripts (run via Ghidra headless analyser against `KG-S88G.exe`)

| Script | Purpose |
|--------|---------|
| `ghidra_decompile.py` | First-pass keyword search — scans all function names for serial/protocol terms (`read`, `write`, `comm`, `xor`, `encrypt`, etc.) and decompiles matches; also prints the full function list as an index |
| `ghidra_protocol.py` | Targeted search — decompiles all functions in the application address range (`0x0047xxxx–0x004Dxxxx`) that reference known protocol constants (`0x57`, `0x52`, `0x54`, `0x06`, `RWITF`, `WriteFile`, `ReadFile`) |
| `ghidra_analyze.py` | Broadest sweep — byte-pattern search for key constants in function bodies (XOR opcode `0x33`, `0x57`, `0x06`, `RWITF`, `WRITF`, magic prefix); decompiles the top 30 largest functions unconditionally; keyword-matches function names; outputs string constants |

### PCAP and Cipher Scripts

| Script | Purpose |
|--------|---------|
| `parse_pcap.py` | Extract and print raw transactions from a capture; first script run to understand raw packet structure |
| `decrypt_capture.py` | Systematic cipher hypothesis testing — works through Approaches A–H trying different combinations of key scope, packet coverage, and direction to find the correct decryption model |
| `decrypt_tx.py` | Focused on decrypting TX commands — tries all 256 starting keys against the interleaved TX+RX stream, looking for sequential EEPROM addresses in decrypted TX packets as the validity signal |
| `full_decrypt.py` | Full EEPROM reconstruction — decrypts the entire data phase and assembles the 16-byte blocks into a binary EEPROM image; also compares against `stock.dat` to establish the CPS↔EEPROM offset mapping |
| `trace_cipher.py` | Key derivation analysis — brute-forces the data-phase key across multiple captures; traces which handshake bytes feed the key state; tests candidate formulas against known keys |

### EEPROM Analysis Scripts

| Script | Purpose |
|--------|---------|
| `analyze_eeprom.py` | Inspect decoded EEPROM content — dumps regions, identifies channel structure, searches for known frequency encodings |
| `compare_formats.py` | Compare EEPROM image against CPS `.dat` file to confirm the `EEPROM = CPS − 0x0145` offset formula |
| `eeprom_decode.py` | Decode EEPROM fields — names, frequencies, tone bytes, settings values |
| `check_layout.py` | Verify struct field alignment — confirms byte offsets for each settings field match between the CHIRP `MEM_FORMAT` struct and the raw EEPROM dump |
| `analyze_chirp_write.py` | Verify CHIRP-generated uploads — decrypts a CHIRP write capture and confirms the written EEPROM content matches what CHIRP intended |

---

## Cipher Algorithm Discovery

This section documents the step-by-step process by which the cipher was identified
and cracked, combining PCAP observation with Ghidra disassembly of the CPS executable.

### Step 1 — Initial Observations (PCAP)

After extracting the raw byte stream with tshark and grouping frames into transactions,
the first thing examined was the raw data-phase packets without any decryption applied.

Two immediate observations:

**Byte 0 is always `0x57`** across every TX and RX data-phase packet, regardless of
session or capture. `0x57` is the ASCII character `W`. This was consistent across
the stock-read and stock-write captures — two different sessions with different key material. A statically keyed or otherwise encrypted byte 0 could not
produce the same value in every session. Conclusion: **byte 0 is not encrypted**.

**Packet sizes are fixed**: every data-phase TX is 5 bytes, every RX is 21 bytes.
This suggested a simple command/response protocol with a fixed-length read command
and fixed-length 16-byte data response (5 header + 16 data = 21).

**Handshake is readable ASCII**: the very first TX packet decoded plainly as
`02 52 57 49 54 46 FF FF` → `\x02 RWITF \xFF\xFF`. No cipher was applied.
The upload capture used `WRITF`. This confirmed the handshake is entirely plaintext
and that the magic strings encode the operation type.

### Step 2 — Disassembly of the CPS Executable (Ghidra)

With the structural observations from the PCAP in hand, Ghidra was run in headless
mode against `KG-S88G.exe` to locate the cipher implementation. The binary is a
32-bit Windows Delphi application. Application code lives in the `0x0047xxxx–0x004Dxxxx`
address range; library/RTL code outside that range was ignored.

Three parallel search strategies were used simultaneously via headless scripts:

**Strategy 1 — Byte pattern search** (`ghidra_analyze.py`):
Scanned every function body for known byte sequences. The most targeted search was
for the x86 XOR opcode `0x33` (`XOR r32, r/m32`), which a compiler would emit for
the cipher's core operation. Additional patterns searched included:
- `0x57` — the read command byte
- `0x06` — the ACK byte
- `b"RWITF"` / `b"WRITF"` — the magic strings
- `bytes([0x02, 0x52, 0x57])` — the magic packet prefix

**Strategy 2 — Large function decompilation** (`ghidra_analyze.py`):
The top 30 functions by instruction count were decompiled unconditionally. Protocol
state machines tend to be large functions; this cast a wide net to catch any that
the byte pattern search might miss.

**Strategy 3 — Function name keyword search** (`ghidra_analyze.py`, `ghidra_protocol.py`):
Scanned all function names (including Delphi symbol names where available) for terms
including: `comm`, `serial`, `send`, `recv`, `read`, `write`, `xor`, `key`,
`encrypt`, `decrypt`, `oncomm`, `download`, `upload`, `handshake`. The `OnComm`
event handler (the VCL MSComm control's receive callback) was the primary target —
this is where Delphi serial applications process incoming bytes.

**Finding the function**:
The XOR opcode search (`0x33`) returned many candidates — XOR is common in general
code — but cross-referencing with functions that *also* referenced the known buffer
address `DAT_004e539d` (which appeared in the handshake-phase decompilations)
narrowed the field significantly. `FUN_004d1e2c` appeared in both the XOR opcode
results and the large-function list, and its decompilation immediately showed the
characteristic rolling-key pattern rather than a data comparison or bitfield
manipulation (the other common uses of XOR in this codebase).

The Ghidra decompiler produced the following pseudo-C for `FUN_004d1e2c`:

```c
bVar1 = *pbVar3;           // save the original (encrypted) byte
*pbVar3 = *pbVar3 ^ key;   // decrypt: XOR with current key
key = (key + bVar1) & 0xFF; // advance key: add the encrypted byte (not plaintext)
```

The function was called starting at `pbVar3 = &DAT_004e539d`, which was one byte
past the buffer start — confirming the **byte 0 skip** observed in the captures.
The loop processed `(param_2 - 1)` bytes, i.e. all bytes except the first.

This gave the complete algorithm in one step:
- XOR each byte with the current key
- Advance the key by adding the **ciphertext byte** (not the decrypted plaintext)
- Byte 0 of each packet is passed through untouched

The reason the key is advanced using the ciphertext — not the plaintext — is what
makes this cipher self-synchronizing: both the sender and receiver advance their
key state by processing the same byte stream (the ciphertext), so they stay in sync
without any separate key exchange per packet.

### Step 3 — Testing Cipher Hypotheses (PCAP)

With the algorithm known from Ghidra, `decrypt_capture.py` tested several hypotheses
about how the cipher was applied, working through them as labelled "Approaches":

**Approach A** — Cumulative key, skip byte 0 per packet, key=0:
Applied the Ghidra algorithm starting at key=0, carrying key state across
all packets (TX and RX interleaved). Result: TX byte 0 correctly passed through
as `0x57`; decrypted address bytes showed a pattern but addresses were not sequential.
This meant key=0 was not the right starting value for that capture.

**Approach B** — All bytes encrypted (no skip):
Byte 0 would decrypt to something other than `0x57`. Ruled out.

**Approach C** — TX and RX through the same shared key state:
Tested explicitly — key carries through both TX and RX packets in sequence, not
reset between them. This was the correct model: decryption only became consistent
when the TX packet's encrypted bytes advanced the key *before* decrypting the
following RX packet.

**Approach D** — Key derived from handshake data:
Tested whether individual bytes from the handshake RX responses could be the
initial key. Did not yield sequential addresses.

**Approaches E–H** — Various other models:
Tried decrypting RX as a single continuous stream, treating TX and RX as having
separate cipher states, and assuming no encryption on one direction. All failed.

**The breakthrough**: Approach C (shared cumulative state, skip byte 0, key from
brute-force) combined with the exact Ghidra algorithm was the correct model. With
the right initial key, the decrypted TX bytes decoded to:
```
57 00 00 00 10   → read command: addr=0x000000, len=16
57 00 00 10 10   → read command: addr=0x000010, len=16
57 00 00 20 10   → read command: addr=0x000020, len=16
...
```
Sequential addresses incrementing by `0x10` — exactly what an EEPROM reader
would produce. This confirmed the cipher and structure simultaneously.

### Step 4 — Brute-Forcing the Initial Key

Since the initial key varied per session (the CPS uses random key material),
`trace_cipher.py` brute-forced the 256 possible starting key values for each
capture. The validity check was simple: decrypt with a candidate key, then verify
that decrypted TX address bytes increment by `0x10` per block. Only one key value
per capture produced valid sequential addresses.

Results across captures:

| Capture | Data-Phase Key |
|---------|---------------|
| `stock-read-from-radio.pcapng` | 0x00 |
| `stock-write-to-radio.pcapng` | 0xE6 |

### Step 5 — Key Derivation Formula

With multiple known keys and the raw handshake key material from each capture, the
relationship was found by inspecting `km[1]` and `km[3]` (bytes at index 1 and 3
of the 16-byte key material packet):

```
data_phase_key = km[1] XOR km[3]
```

This was verified across all captures. The CPS generates random key material
each session, so the per-session key varies. The CHIRP driver sends all-zero key
material (`A5 00 00 00 ...`) so that `km[1] XOR km[3] = 0x00 XOR 0x00 = 0x00`,
giving a predictable and debuggable session key.

### Step 6 — Write ACK Behavior

During write capture analysis, the ACK byte (`0x06`) the radio sends after each
written block was observed not to follow the cipher. Applying the running key at
that point in the stream would have produced a non-`0x06` value if the ACK were
encrypted. The raw `0x06` appeared directly — confirming write ACKs are sent
**unencrypted** and do not advance the cipher key.

---

## Converting a Capture to a CHIRP Image

Any complete read or write capture can be converted directly to a CHIRP-compatible
`.img` file using `pcap_to_img.py`. This is the fastest way to inspect a captured
EEPROM image without going through the full radio download workflow.

### Tool: `pcap_to_img.py`

Located at the root of the repository. Requires Python 3 and tshark (bundled with Wireshark).

```
python pcap_to_img.py <capture.pcapng> [output.img] [--tshark PATH]
```

**Arguments:**
- `capture.pcapng` — input capture file (read or write session)
- `output.img` — output filename (default: `<capture>.img`)
- `--tshark PATH` — path to tshark if not on PATH (e.g. `"C:/Program Files/Wireshark/tshark.exe"`)

**Examples:**
```bash
# Minimal — output written to stock-read-from-radio.img
python pcap_to_img.py PCAPs/stock-read-from-radio.pcapng

# Explicit output name
python pcap_to_img.py PCAPs/stock-read-from-radio.pcapng stock.img

# Windows with Wireshark not on PATH
python pcap_to_img.py PCAPs/stock-read-from-radio.pcapng stock.img --tshark "C:/Program Files/Wireshark/tshark.exe"
```

**What it does:**
1. Uses tshark to extract USB bulk frames from endpoints `0x01` and `0x81`
2. Reassembles consecutive same-direction frames into transactions
3. Parses the 8-step handshake and derives the data-phase cipher key (`km[1] XOR km[3]`)
4. Decrypts the data phase using the rolling XOR cipher
5. Extracts 16-byte payloads from `0x57`-prefixed packets and assembles the EEPROM image
6. Writes a 10,192-byte (0x27D0) raw EEPROM image to the output file

**Opening in CHIRP:**
```
File > Open > select the .img file
```

The `.img` file contains the raw EEPROM bytes followed by a CHIRP metadata header
(`\x00\xff chirp\xee img\x00\x01` + base64 JSON with `rclass`, `vendor`, `model`).
CHIRP uses this metadata to auto-identify the file as a Wouxun KG-S88G image without
requiring manual radio selection.

### Example Output

Running against `PCAPs/stock-read-from-radio.pcapng`:

```
Input  : PCAPs/stock-read-from-radio.pcapng
Output : stock-read-from-radio.img

Extracting USB frames with tshark...
  Transactions: 1283

Parsing handshake...
  Operation  : READ
  Magic      : RWITF
  km[1]=0x00  km[3]=0x00  data_phase_key = 0x00

Reconstructing EEPROM...
  Blocks     : 637
  Addr range : 0x0000 - 0x27C0

Saved 10192 bytes + CHIRP metadata to stock-read-from-radio.img
```

The key `0x00` here means the CPS sent zero key material bytes at positions 1 and 3
in this session. CHIRP sessions also always produce `data_phase_key = 0x00` since
the driver deliberately sends all-zero key material.

The 1283 transactions break down as: 8 handshake + 637 TX read commands + 637 RX responses + 1 terminate = 1283.

---

## Key Findings Summary

1. **Protocol is entirely serial** — USB is only a transport layer; the HID frames
   carry raw serial bytes with no additional framing.
2. **Cipher is rolling XOR** — self-synchronizing, shared state across TX and RX.
3. **Key material determines the per-session cipher key** — `km[1] XOR km[3]`.
4. **Byte 0 of every encrypted packet is plaintext** — always `0x57` (read/write)
   or `0x54` (terminate) and does not advance the cipher key.
5. **Write ACKs are unencrypted** — the radio's single-byte `0x06` ACK per write
   block does not pass through the cipher.
6. **EEPROM offset = CPS offset − 0x0145** — determined by cross-referencing
   known field values (channel frequencies, settings) between the EEPROM image
   and a known CPS `.dat` file.
