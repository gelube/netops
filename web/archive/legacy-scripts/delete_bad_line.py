#!/usr/bin/env python3
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 删除第 791 行（索引 790）的孤立代码
if 790 < len(lines) and 'exec_cmd = "vlan batch 10 20"' in lines[790] and not lines[790].strip().startswith('#'):
    # 检查是否是孤立行（前面不是 if/elif/else）
    prev_line = lines[789] if 789 >= 0 else ''
    if 'elif' not in prev_line and 'else:' not in prev_line and 'if ' not in prev_line:
        del lines[790]
        print("Deleted isolated line 791")

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Fix applied")
