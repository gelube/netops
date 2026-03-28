with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = []
for i, line in enumerate(lines):
    fixed.append(line)
    if line.rstrip() == 'else:' and i + 1 < len(lines):
        next_line = lines[i + 1]
        # Check if next line should be part of else block but isn't indented properly
        if next_line and not next_line[0].isspace() and not next_line.strip().startswith('#'):
            # This shouldn't happen, skip
            pass
        elif next_line.strip() and not next_line.startswith('        ') and not next_line.strip().startswith('#') and not next_line.strip().startswith('elif') and not next_line.strip().startswith('else'):
            # Need to add pass
            indent = len(line) - len(line.lstrip())
            fixed.append(' ' * (indent + 4) + 'pass\n')
            print(f"Added pass at line {i+2}")

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed)

print("Done")
