#!/usr/bin/env python3
"""删除关键词检测，直接用 LLM"""

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到关键词检测的 chat 函数并替换为纯 LLM 调用
old_chat = '''@app.route('/api/chat', methods=['POST'])
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
        return jsonify({'success': True, 'message': 'NetOps AI - 支持：VLAN/接口/路由/邻居/ARP'})'''

new_chat = '''@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 对话 - 直接调用 LLM"""
    global llm_client, current_topology, device_ports
    
    data = request.json
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({'success': False, 'message': '消息不能为空'})
    
    # 构建上下文
    context = ""
    if current_topology and current_topology.devices:
        context = f"当前网络拓扑：\\n设备数量：{len(current_topology.devices)}\\n\\n"
        for dev in current_topology.devices[:5]:
            context += f"- {dev.name} ({dev.ip}) - {dev.vendor.value}\\n"
    
    # 调用 LLM
    if llm_client and llm_config:
        try:
            system_prompt = """你是一个网络设备配置执行器。用户会让你配置 H3C 设备。

【规则】
1. 只输出命令，不要任何解释
2. 不要步骤，不要说明
3. 直接返回要执行的命令

【H3C 命令示例】
- 创建 VLAN: vlan batch 10 20
- 查看 VLAN: display vlan
- 配置端口：interface GigabitEthernet 0/0/1

用户说什么，你就返回对应的命令。只返回命令本身，不要任何其他内容！"""
            
            response = llm_client.chat_simple(user_message, context, timeout=30)
            
            # 提取命令（清理多余内容）
            if response:
                # 取第一行非空内容
                lines = [l.strip() for l in response.split('\\n') if l.strip() and not l.strip().startswith('#')]
                exec_cmd = lines[0] if lines else response.strip()
                
                # 执行命令
                if current_topology and current_topology.devices:
                    exec_ip = list(device_ports.keys())[0]
                    exec_port = device_ports.get(exec_ip, 23)
                    try:
                        result = execute_on_device(exec_ip, exec_cmd, port=exec_port)
                        return jsonify({'success': True, 'message': f"【自动执行】\\n设备：{exec_ip}:{exec_port}\\n命令：{exec_cmd}\\n\\n【结果】\\n{result}"})
                    except Exception as e:
                        return jsonify({'success': True, 'message': f"【命令】{exec_cmd}\\n【执行失败】{str(e)}"})
            
            return jsonify({'success': True, 'message': response or 'LLM 无响应'})
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'LLM 调用失败：{str(e)}'})
    
    return jsonify({'success': True, 'message': 'LLM 未配置'})'''

if old_chat in content:
    content = content.replace(old_chat, new_chat)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ 已删除关键词检测，切换到纯 LLM 模式！")
else:
    print("❌ 未找到关键词检测代码")
