#!/usr/bin/env python3
"""创建最小化的 chat 函数"""

minimal_chat = '''@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 对话 - 简单关键词检测"""
    global current_topology, device_ports
    
    data = request.json
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({'success': False, 'message': '消息不能为空'})
    
    import re
    msg = user_message.lower()
    exec_cmd = None
    
    # VLAN
    if 'vlan' in msg:
        if any(x in msg for x in ['创建', '添加', '配置', '做', 'create', 'add', 'config', 'do']):
            vlan_ids = re.findall(r'\\d+', user_message)
            exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "vlan batch 10 20"
        else:
            vlan_ids = re.findall(r'\\d+', user_message)
            exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "display vlan"
    # 接口
    elif any(x in msg for x in ['接口', 'interface', '端口', 'port']):
        exec_cmd = "display interface brief"
    # 路由
    elif any(x in msg for x in ['路由', 'route', 'ospf']):
        exec_cmd = "display ospf peer" if 'ospf' in msg else "display ip routing-table"
    # 邻居
    elif any(x in msg for x in ['邻居', 'lldp', 'cdp']):
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
            response = f"【自动执行】\\n设备：{exec_ip}:{exec_port}\\n命令：{exec_cmd}\\n\\n【结果】\\n{result}"
        except Exception as e:
            response = f"【命令】{exec_cmd}\\n【失败】{str(e)}"
    elif exec_cmd:
        response = f"【生成命令】{exec_cmd}"
    else:
        response = "NetOps AI - 支持：VLAN/接口/路由/邻居/ARP"
    
    return jsonify({'success': True, 'message': response})

'''

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
# 找到并替换整个 chat 函数
pattern = r"@app\.route\('/api/chat'.*?(?=@app\.route|def \w+\(|$)"
new_content = re.sub(pattern, minimal_chat, content, flags=re.DOTALL, count=1)

if new_content != content:
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✅ Replaced chat function with minimal version!")
else:
    print("❌ Could not find chat function")
