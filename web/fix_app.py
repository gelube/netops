#!/usr/bin/env python3
import sys

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 750 (0-indexed: 749) has "        else:\n"
# Line 751 (0-indexed: 750) has "    # 2. VLAN..."
# Need to insert a pass statement after else

fixed_lines = []
for i, line in enumerate(lines):
    fixed_lines.append(line)
    # Check if this is line 750 (1-indexed), which is index 749
    if i == 749 and line.strip() == 'else:':
        # Next line should be indented, but it's a comment at wrong level
        # Insert a simple command
        fixed_lines.append('            exec_cmd = "vlan batch 10"\n')

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print(f"Fixed line 750. Total lines: {len(fixed_lines)}")
