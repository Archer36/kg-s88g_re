# Ghidra script to find protocol-related functions by searching for
# constants and cross-references related to the serial protocol
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.model.symbol import RefType

decomp = DecompInterface()
decomp.openProgram(currentProgram)
monitor = ConsoleTaskMonitor()

fm = currentProgram.getFunctionManager()
listing = currentProgram.getListing()
refMgr = currentProgram.getReferenceManager()

# Strategy: Find functions that call WriteFile/ReadFile from the comm port area
# and also reference interesting constants

# Find all functions and decompile them, searching for protocol patterns
print("=" * 80)
print("SEARCHING FOR PROTOCOL FUNCTIONS")
print("=" * 80)

interesting_funcs = set()

# Get all functions
all_funcs = list(fm.getFunctions(True))
print("Total functions: %d" % len(all_funcs))

# Decompile ALL functions in the 0x0048xxxx-0x004Dxxxx range (likely application code)
# and look for ones that reference serial port operations or our protocol constants
for func in all_funcs:
    addr = func.getEntryPoint().getOffset()
    # Application code is typically in the higher address range for Delphi
    if addr < 0x00470000 or addr > 0x004e0000:
        continue
    
    res = decomp.decompileFunction(func, 15, monitor)
    if res and res.decompileCompleted():
        code = res.getDecompiledFunction().getC()
        # Look for protocol-related patterns
        if any(pattern in code for pattern in [
            '0x57',    # 'W' command byte
            '0x52',    # 'R' command byte  
            '0x54',    # 'T' exit byte
            '0x6',     # ACK
            'WriteFile', 'ReadFile',
            'Comm', 'comm',
            '0x2520', '9600', '19200',
            'RWITF',
            '0xff',
        ]):
            interesting_funcs.add(func)

print("\nFound %d potentially protocol-related functions" % len(interesting_funcs))

# Now decompile and print the interesting ones, sorted by address
for func in sorted(interesting_funcs, key=lambda f: f.getEntryPoint().getOffset()):
    print("\n" + "=" * 60)
    print("FUNCTION @ %s (size: %d)" % (func.getEntryPoint(), func.getBody().getNumAddresses()))
    print("=" * 60)
    res = decomp.decompileFunction(func, 30, monitor)
    if res and res.decompileCompleted():
        print(res.getDecompiledFunction().getC())
