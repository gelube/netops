#!/usr/bin/env python3
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 context 构建部分并修改
for i in range(len(lines)):
    if i > 150 and i < 160 and 'context = f"' in lines[i] and '当前网络' in lines[i]:
        # 修改为包含厂商信息
        lines[i] = '    # 构建设备上下文（包含厂商信息）\n'
        lines.insert(i+1, '    device_vendors = []\n')
        lines.insert(i+2, '    if current_topology and current_topology.devices:\n')
        lines.insert(i+3, '        for dev in current_topology.devices:\n')
        lines.insert(i+4, '            device_vendors.append(dev.vendor.value)\n')
        lines.insert(i+5, '        context = f"当前网络设备：\\n"\n')
        lines.insert(i+6, '        context += f"设备数量：{len(current_topology.devices)}\\n"\n')
        lines.insert(i+7, '        context += f"设备厂商：{\\', \\'.join(set(device_vendors))}\\n\\n"\n')
        lines.insert(i+8, '        for dev in current_topology.devices[:5]:\n')
        lines.insert(i+9, '            context += f"- {dev.name} ({dev.ip}) - {dev.vendor.value}\\n"\n')
        # 删除原来的 for 循环行
        for j in range(i+10, i+15):
            if j < len(lines) and 'for dev in current_topology.devices[:5]:' in lines[j]:
                lines[j] = '    # Context built\n'
                break
        break

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Added vendor info to context!")
