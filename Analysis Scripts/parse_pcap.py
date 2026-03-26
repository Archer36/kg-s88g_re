import subprocess
import sys

# Use tshark to extract frames with data
cmd = [
    '/Applications/Wireshark.app/Contents/MacOS/tshark',
    '-r', '/Users/brett/git-repos/gh/chirp/kg-s88g/download.pcapng',
    '-Y', '(usb.endpoint_address == 0x01 || usb.endpoint_address == 0x81) and (usb.capdata)',
    '-T', 'fields',
    '-e', 'frame.number',
    '-e', 'usb.src',
    '-e', 'usb.dst',
    '-e', 'usb.capdata',
]

result = subprocess.run(cmd, capture_output=True, text=True)

# Reconstruct the byte stream
pc_to_radio = []  # accumulate bytes sent by PC
radio_to_pc = []  # accumulate bytes sent by radio

transactions = []  # list of (direction, hex_bytes)

current_dir = None
current_bytes = bytearray()

for line in result.stdout.strip().split('\n'):
    parts = line.split('\t')
    if len(parts) < 4:
        continue
    frame, src, dst, capdata = parts[0], parts[1], parts[2], parts[3]
    
    raw_bytes = bytes.fromhex(capdata.replace(':', ''))
    
    if 'host' in src:  # PC -> Radio
        direction = 'TX'
    else:  # Radio -> PC
        direction = 'RX'
    
    if direction != current_dir and current_bytes:
        transactions.append((current_dir, bytes(current_bytes)))
        current_bytes = bytearray()
    
    current_dir = direction
    current_bytes.extend(raw_bytes)

if current_bytes:
    transactions.append((current_dir, bytes(current_bytes)))

# Print the transactions
for i, (direction, data) in enumerate(transactions):
    hex_str = data.hex()
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    
    # Format hex in groups of 2 with spaces
    hex_formatted = ' '.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
    
    prefix = "PC->Radio" if direction == 'TX' else "Radio->PC"
    print(f"\n[{i:3d}] {prefix} ({len(data)} bytes):")
    
    # Print in rows of 16
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"      {offset:04x}: {hex_part:<48s}  {ascii_part}")

