with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 793 (0-indexed: 792)
for i in range(len(lines)):
    if lines[i].rstrip() == 'else:' and i + 1 < len(lines):
        next_line = lines[i + 1]
        # If next line is a comment or elif/else at lower indent, add pass
        if next_line.startswith('    ') and not next_line.startswith('        '):
            # Insert pass with correct indent (12 spaces)
            lines.insert(i + 1, '            pass\n')
            print(f"Fixed at line {i+1}")

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Done")
