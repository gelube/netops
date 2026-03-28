APP_PATH = 'Z:/netops-ai/web/app.py'
with open(APP_PATH, 'r', encoding='utf-8') as f:
    lines = f.readlines()
fixed = []
i = 0
while i < len(lines):
    line = lines[i]
    fixed.append(line)
    if line.strip() == 'else:' and i + 1 < len(lines):
        next_line = lines[i + 1]
        if not next_line.startswith('            ') and not next_line.strip().startswith('#'):
            fixed.append('            pass\n')
            print(f"Fixed at line {i+1}")
    i += 1
with open(APP_PATH, 'w', encoding='utf-8') as f:
    f.writelines(fixed)
print(f"Done. {len(fixed)} lines")
