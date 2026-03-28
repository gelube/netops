#!/usr/bin/env python3
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_prompt = '你是网络命令生成器。用户说"做 vlan"就返回"vlan batch 10 20"，用户说"查看"就返回"display xxx"。只返回一行命令，不要任何其他内容。'
new_prompt = '你必须返回以下格式之一：1) "vlan batch X" 2) "display X" 3) "interface X"。用户说"做 vlan"必须返回"vlan batch 10 20"。不要任何其他文字！'

content = content.replace(old_prompt, new_prompt)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed prompt!")
