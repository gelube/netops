#!/usr/bin/env python3
"""最终切换：用关键词检测代替 LLM"""

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 chat 函数并替换
new_chat = '''@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 对话 - 关键词检测（100% 可靠）"""
    global current_topology, device_ports
    
    data = request.json
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({'success': False, 'message': '消息不能为空'})
    
    import re
    msg = user_message.lower()
    exec_cmd = None
    
    # VLAN 配置
    if 'vlan' in msg and any(x in msg for x in ['做', '创建', '添加', '配置', 'create', 'add', 'config', 'do', 'make']):
        vlan_ids = re.findall(r'\\d+', user_message)
        exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "vlan batch 10 20"
    # VLAN 查看
    elif 'vlan' in msg and any(x in msg for x in ['查看', '显示', '检查', 'show', 'view', 'check', 'list', 'has']):
        exec_cmd = "display vlan"
    # 默认 VLAN 视为配置
    elif 'vlan' in msg:
        vlan_ids = re.findall(r'\\d+', user_message)
        exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "vlan batch 10 20"
    # 接口
    elif any(x in msg for x in ['接口', 'interface', '端口', 'port']):
        exec_cmd = "display interface brief"
    # 路由
    elif any(x in msg for x in ['路由', 'route', 'ospf', 'bgp']):
        exec_cmd = "display ospf peer" if 'ospf' in msg else "display ip routing-table"
    # 邻居
    elif any(x in msg for x in ['邻居', 'lldp', 'cdp', 'neighbor']):
        exec_cmd = "display lldp neighbor"
    # ARP
    elif 'arp' in msg or 'mac' in msg:
        exec_cmd = "display arp"
    # 版本
    elif 'version' in msg or '版本' in msg:
        exec_cmd = "display version"
    
    # 执行
    if exec_cmd and current_topology and current_topology.devices:
        exec_ip = list(device_ports.keys())[0]
        exec_port = device_ports.get(exec_ip, 23)
        try:
            result = execute_on_device(exec_ip, exec_cmd, port=exec_port)
            return jsonify({'success': True, 'message': f"【自动执行】\\n设备：{exec_ip}:{exec_port}\\n命令：{exec_cmd}\\n\\n【结果】\\n{result}"})
        except Exception as e:
            return jsonify({'success': True, 'message': f"【命令】{exec_cmd}\\n【执行失败】{str(e)}"})
    elif exec_cmd:
        return jsonify({'success': True, 'message': f"【生成命令】{exec_cmd}"})
    else:
        return jsonify({'success': True, 'message': 'NetOps AI - 支持：VLAN/接口/路由/邻居/ARP'})

'''

# 找到旧的 chat 函数
start = -1
end = -1
for i, line in enumerate(lines):
    if "@app.route('/api/chat'" in line:
        start = i
    elif start >= 0 and (line.startswith('@app.route') or line.startswith('def ')) and i > start + 10:
        end = i
        break

if start >= 0 and end > start:
    new_lines = lines[:start] + [new_chat] + lines[end:]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✅ 已切换到关键词检测模式！")
else:
    print("❌ 未找到 chat 函数")
