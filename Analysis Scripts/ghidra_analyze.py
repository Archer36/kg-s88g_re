"""
Ghidra headless script for KG-S88G.exe protocol analysis.

Run with Ghidra's pyghidraRun or analyzeHeadless + Jython.

Focuses on finding:
  1. Serial communication functions (MSComm OnComm handler)
  2. XOR cipher implementation
  3. Handshake/key material generation
  4. Data read/write state machine
  5. Constants: 0x57, 0x02, RWITF/WRITF magic bytes
"""
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.model.symbol import SymbolType

decomp = DecompInterface()
decomp.openProgram(currentProgram)
monitor = ConsoleTaskMonitor()
fm = currentProgram.getFunctionManager()
mem = currentProgram.getMemory()

OUTPUT = r"C:\Users\Brett\git-repos\gh\chirp\kg-s88g-dev\tmp\ghidra_output_new.txt"

def decompile(func):
    res = decomp.decompileFunction(func, 60, monitor)
    if res and res.decompileCompleted():
        return res.getDecompiledFunction().getC()
    return "  [decompilation failed]\n"

def find_funcs_with_bytes(target_bytes):
    """Find functions containing specific byte sequences."""
    results = []
    for func in fm.getFunctions(True):
        body = func.getBody()
        for rng in body:
            start = rng.getMinAddress()
            length = rng.getLength()
            try:
                data = bytearray(length)
                mem.getBytes(start, data)
                if target_bytes in bytes(data):
                    results.append(func)
                    break
            except Exception:
                pass
    return results

def find_funcs_by_name_keywords(keywords):
    results = []
    for func in fm.getFunctions(True):
        name = func.getName().lower()
        if any(kw in name for kw in keywords):
            results.append(func)
    return results

def get_xrefs_to(addr):
    refs = currentProgram.getReferenceManager().getReferencesTo(addr)
    return list(refs)

lines = []
def out(s=""):
    lines.append(s)
    print(s)

# ─── 1. All function list ───────────────────────────────────────────────────
out("=" * 80)
out("ALL FUNCTIONS")
out("=" * 80)
for func in fm.getFunctions(True):
    size = func.getBody().getNumAddresses()
    out(f"  {func.getEntryPoint()}  {func.getName():40s}  size={size}")

# ─── 2. Search for magic byte patterns ─────────────────────────────────────
out("\n" + "=" * 80)
out("FUNCTIONS CONTAINING KEY CONSTANTS")
out("=" * 80)

searches = [
    ("0x57 (read cmd)",   bytes([0x57])),
    ("0x06 (ACK)",        bytes([0x06])),
    ("RWITF magic",       b"RWITF"),
    ("WRITF magic",       b"WRITF"),
    ("0x02 marker",       bytes([0x02, 0x52, 0x57])),  # 02 RWITF prefix
    ("XOR pattern",       bytes([0x33])),   # XOR opcode
]

for label, pattern in searches:
    funcs = find_funcs_with_bytes(pattern)
    out(f"\n  Pattern '{label}' ({pattern.hex()}) found in {len(funcs)} function(s):")
    for f in funcs:
        out(f"    {f.getEntryPoint()}  {f.getName()}")

# ─── 3. Decompile large functions (likely contain protocol logic) ───────────
out("\n" + "=" * 80)
out("DECOMPILATION OF LARGE FUNCTIONS (>200 instructions)")
out("=" * 80)

large_funcs = sorted(
    fm.getFunctions(True),
    key=lambda f: f.getBody().getNumAddresses(),
    reverse=True
)[:30]  # top 30 largest

for func in large_funcs:
    size = func.getBody().getNumAddresses()
    out(f"\n{'=' * 60}")
    out(f"FUNCTION: {func.getName()} @ {func.getEntryPoint()}  (size={size})")
    out("=" * 60)
    out(decompile(func))

# ─── 4. Decompile functions with interesting keywords ──────────────────────
out("\n" + "=" * 80)
out("KEYWORD-MATCHED FUNCTIONS")
out("=" * 80)

kw_funcs = find_funcs_by_name_keywords([
    'comm', 'serial', 'send', 'recv', 'read', 'write', 'xor', 'key',
    'encrypt', 'decrypt', 'cipher', 'ident', 'handshake', 'magic',
    'download', 'upload', 'click', 'timer', 'oncomm', 'data'
])

for func in kw_funcs:
    out(f"\n{'=' * 60}")
    out(f"FUNCTION: {func.getName()} @ {func.getEntryPoint()}")
    out("=" * 60)
    out(decompile(func))

# ─── 5. Search for string constants ────────────────────────────────────────
out("\n" + "=" * 80)
out("STRING CONSTANTS (ASCII, len 4-50)")
out("=" * 80)
from ghidra.program.model.data import StringDataType
dt = StringDataType()
listing = currentProgram.getListing()
data_iter = listing.getDefinedData(True)
for d in data_iter:
    if d.getDataType().getName() in ('string', 'unicode', 'TerminatedCString', 'TerminatedUnicode'):
        val = str(d.getValue())
        if 4 <= len(val) <= 80:
            out(f"  {d.getAddress()}  {val!r}")

# Write output
with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"\nOutput written to: {OUTPUT}")
