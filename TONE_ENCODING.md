# KG-S88G Tone Encoding Reference

This document covers CTCSS and DCS encoding for both the CPS `.dat` file format
and the raw EEPROM format. It also documents the radio's DCS code list, which
differs slightly from the standard 104-code list.

---

## CPS `.dat` Tone Encoding

Used in the CPS `.dat` file (see `CPS_FORMAT.md`). All tone bytes are XOR'd with
`0x55` before being stored.

### Format

Each tone occupies 2 bytes: `[MODE_BYTE][INDEX_BYTE]`

```
mode  = MODE_BYTE  XOR 0x55
index = INDEX_BYTE XOR 0x55
```

| Mode (after XOR) | Meaning |
|-----------------|---------|
| 0 | Off |
| 1 | CTCSS |
| 2 | DCS-N (normal polarity) |
| 3 | DCS-I (inverted polarity) |

Index is **1-based** into the CTCSS or DCS list.

### CPS Examples

| Stored Bytes | Decoded | Meaning |
|-------------|---------|---------|
| `55 55` | mode=0, idx=0 | Off |
| `54 54` | mode=1, idx=1 | CTCSS 67.0 Hz |
| `54 58` | mode=1, idx=13 | CTCSS 100.0 Hz |
| `54 73` | mode=1, idx=38 | CTCSS 192.8 Hz |
| `57 54` | mode=2, idx=1 | DCS D023N |
| `56 54` | mode=3, idx=1 | DCS D023I |
| `57 7E` | mode=2, idx=43 | DCS D251N |

---

## EEPROM Tone Encoding

Used in the raw EEPROM (see `EEPROM_FORMAT.md`). Values are stored **raw — no XOR**.

| Field | Meaning |
|-------|---------|
| `rx_tmode` / `tx_tmode` | 0=Off, 1=CTCSS, 2=DCS-N, 3=DCS-I |
| `rx_tone` / `tx_tone` | 1-based index into CTCSS or DCS list |

---

## CTCSS Tone List (38 tones)

Standard tones, identical in both CPS and EEPROM indexing:

| Index | Hz    | Index | Hz    | Index | Hz    | Index | Hz    |
|-------|-------|-------|-------|-------|-------|-------|-------|
| 1  | 67.0  | 11 | 94.8  | 21 | 131.8 | 31 | 171.3 |
| 2  | 69.3  | 12 | 97.4  | 22 | 136.5 | 32 | 173.8 |
| 3  | 71.9  | 13 | 100.0 | 23 | 141.3 | 33 | 177.3 |
| 4  | 74.4  | 14 | 103.5 | 24 | 146.2 | 34 | 179.9 |
| 5  | 77.0  | 15 | 107.2 | 25 | 151.4 | 35 | 183.5 |
| 6  | 79.7  | 16 | 110.9 | 26 | 156.7 | 36 | 186.2 |
| 7  | 82.5  | 17 | 114.8 | 27 | 159.8 | 37 | 189.9 |
| 8  | 85.4  | 18 | 118.8 | 28 | 162.2 | 38 | 192.8 |
| 9  | 88.5  | 19 | 123.0 | 29 | 165.5 |    |       |
| 10 | 91.5  | 20 | 127.3 | 30 | 167.9 |    |       |

---

## DCS Code List — Radio vs Standard

### The Discrepancy

The radio's manual lists **105 DCS codes**. The standard list used by most
software (including CHIRP's `chirp_common.DTCS_CODES`) has **104 codes**.

The radio's list differs at two points:

**Position 77**: Radio has `D463N`, standard has `D464N`
```
Radio (positions 76–79):    D462  D463  D465  D466
Standard (positions 76–79): D462  D464  D465  D466
```

**Position 94**: Radio inserts `D645N` (not in standard list at all)
```
Radio (positions 92–96):    D631  D632  D645  D654  D662
Standard (positions 92–95): D631  D632        D654  D662
```

Net result: radio has D463 (not D464) + extra D645 = 105 codes total.

### CHIRP Driver Implementation Note

The CHIRP driver uses the standard `chirp_common.DTCS_CODES` (104 codes).
Practical impact:
- **D463N**: Not accessible via CHIRP. CHIRP index 77 maps to D464N instead.
- **D645N**: Not accessible via CHIRP.
- All other 103 codes map correctly.

For GMRS operation, these two codes are unlikely to matter in practice.
A future improvement could override the DCS list with the radio's exact 105 codes.

### Radio's Full 105-Code DCS List

As documented in the radio's user manual:

```
Index  Code   Index  Code   Index  Code   Index  Code   Index  Code
  1    D023N   22    D131N   43    D251N   64    D371N   85    D532N
  2    D025N   23    D132N   44    D252N   65    D411N   86    D546N
  3    D026N   24    D134N   45    D255N   66    D412N   87    D565N
  4    D031N   25    D143N   46    D261N   67    D413N   88    D606N
  5    D032N   26    D145N   47    D263N   68    D423N   89    D612N
  6    D036N   27    D152N   48    D265N   69    D431N   90    D624N
  7    D043N   28    D155N   49    D266N   70    D432N   91    D627N
  8    D047N   29    D156N   50    D271N   71    D445N   92    D631N
  9    D051N   30    D162N   51    D274N   72    D446N   93    D632N
 10    D053N   31    D165N   52    D306N   73    D452N   94    D645N ◄ extra
 11    D054N   32    D172N   53    D311N   74    D454N   95    D654N
 12    D065N   33    D174N   54    D315N   75    D455N   96    D662N
 13    D071N   34    D205N   55    D325N   76    D462N   97    D664N
 14    D072N   35    D212N   56    D331N   77    D463N ◄ D464 in std  98    D703N
 15    D073N   36    D223N   57    D332N   78    D465N   99    D712N
 16    D074N   37    D225N   58    D343N   79    D466N  100    D723N
 17    D114N   38    D226N   59    D346N   80    D503N  101    D731N
 18    D115N   39    D243N   60    D351N   81    D506N  102    D732N
 19    D116N   40    D244N   61    D356N   82    D516N  103    D734N
 20    D122N   41    D245N   62    D364N   83    D523N  104    D743N
 21    D125N   42    D246N   63    D365N   84    D526N  105    D754N
```

DCS-I (inverted polarity) uses the same code numbers, indexed separately.

---

## Standard 104-Code DCS List (for reference)

`chirp_common.DTCS_CODES`:

```
023 025 026 031 032 036 043 047 051 053 054 065 071 072 073
074 114 115 116 122 125 131 132 134 143 145 152 155 156 162
165 172 174 205 212 223 225 226 243 244 245 246 251 252 255
261 263 265 266 271 274 306 311 315 325 331 332 343 346 351
356 364 365 371 411 412 413 423 431 432 445 446 452 454 455
462 464 465 466 503 506 516 523 526 532 546 565 606 612 624
627 631 632 654 662 664 703 712 723 731 732 734 743 754
```
