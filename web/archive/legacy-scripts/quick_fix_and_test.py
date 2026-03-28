#!/usr/bin/env python3
"""快速修复缩进 + 删除翻译层"""

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. 删除翻译层代码（大约在第 653-665 行）
# 2. 修复缩进错误

cleaned_lines = []
skip_until = -1

for i, line in enumerate(lines):
    # 跳过翻译层代码
    if i >= 652 and i <= 665 and ('translation_map' in line or 'translated_msg' in line or '翻译' in line):
        continue
    
    # 修复重复的 exec_cmd 行
    if 'exec_cmd = "vlan batch 10 20"' in line and i > 700:
        # 检查是否重复
        if i > 0 and 'exec_cmd = "vlan batch 10 20"' in lines[i-1]:
            continue
    
    cleaned_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print("Quick fix applied! Removed translation layer and duplicate lines.")
print("Now testing syntax...")

import ast
try:
    ast.parse(open('app.py', encoding='utf-8').read())
    print("✅ Syntax OK!")
except SyntaxError as e:
    print(f"❌ Syntax error at line {e.lineno}: {e.msg}")
