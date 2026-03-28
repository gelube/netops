#!/usr/bin/env python3
import re

user_message = '做两个 vlan'
msg = user_message.lower()
exec_cmd = None

print(f"Testing: {user_message}")
print(f"msg: {msg}")
print(f"'vlan' in msg: {'vlan' in msg}")
print(f"Config keywords: {any(x in msg for x in ['做', '创建', '添加', '配置', 'create', 'add', 'config', 'do', 'make'])}")

# VLAN 配置
if 'vlan' in msg and any(x in msg for x in ['做', '创建', '添加', '配置', 'create', 'add', 'config', 'do', 'make']):
    vlan_ids = re.findall(r'\d+', user_message)
    exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "vlan batch 10 20"
    print(f"Match config: {exec_cmd}")
elif 'vlan' in msg:
    vlan_ids = re.findall(r'\d+', user_message)
    exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "vlan batch 10 20"
    print(f"Match default: {exec_cmd}")
else:
    print("No match")

print(f"Final: {exec_cmd}")
