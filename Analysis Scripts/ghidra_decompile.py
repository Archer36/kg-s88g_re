# Ghidra headless script to find and decompile serial communication functions
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

decomp = DecompInterface()
decomp.openProgram(currentProgram)
monitor = ConsoleTaskMonitor()

fm = currentProgram.getFunctionManager()

# Keywords that suggest serial/protocol functions
keywords = ['read', 'write', 'send', 'recv', 'comm', 'serial', 'data', 
            'click', 'download', 'upload', 'xor', 'encrypt', 'decrypt',
            'block', 'program', 'ident', 'magic']

results = []
for func in fm.getFunctions(True):
    name = func.getName().lower()
    if any(kw in name for kw in keywords):
        results.append(func)

print("=" * 80)
print("FOUND %d INTERESTING FUNCTIONS" % len(results))
print("=" * 80)

for func in results:
    print("\n" + "=" * 60)
    print("FUNCTION: %s @ %s" % (func.getName(), func.getEntryPoint()))
    print("=" * 60)
    res = decomp.decompileFunction(func, 30, monitor)
    if res and res.decompileCompleted():
        print(res.getDecompiledFunction().getC())
    else:
        print("  [decompilation failed]")

print("\n" + "=" * 80)
print("ALL FUNCTION NAMES")
print("=" * 80)
for func in fm.getFunctions(True):
    print("  %s @ %s" % (func.getName(), func.getEntryPoint()))
