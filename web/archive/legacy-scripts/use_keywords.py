#!/usr/bin/env python3
"""回退到关键词检测"""

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到 LLM 调用部分并替换为关键词检测
old_llm = '''    # 调用 LLM
    if llm_client and llm_config:
        try:
            system_prompt = """你是网络命令生成器。用户说"做 vlan"就返回"vlan batch 10 20"，用户说"查看"就返回"display xxx"。只返回一行命令，不要任何其他内容。"""
            
            response = llm_client.chat_simple(user_message, context, timeout=30)
            
            # 如果 LLM 返回了命令，直接执行
            if response and any(x in response.lower() for x in ['vlan', 'display', 'interface', 'ospf', 'bgp', 'arp']):
                # 提取命令
                cmd_match = re.search(r'(vlan\s+batch\s+\d+|display\s+\w+|interface\s+\S+|ospf\s+\d+|bgp\s+\S+|arp)', response, re.IGNORECASE)
                if cmd_match:
                    exec_cmd = cmd_match.group(1).strip()
                else:
                    exec_cmd = response.strip()
                
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
    
    # 没有 LLM 时使用关键词检测
    return jsonify({'success': True, 'message': 'LLM 未配置'})'''

new_keywords = '''    # 关键词检测（更可靠）
    msg = user_message.lower()
    exec_cmd = None
    
    # VLAN
    if 'vlan' in msg:
        if any(x in msg for x in ['做', '创建', '添加', '配置', 'create', 'add', 'config', 'do']):
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
            return jsonify({'success': True, 'message': f"【自动执行】\\n设备：{exec_ip}:{exec_port}\\n命令：{exec_cmd}\\n\\n【结果】\\n{result}"})
        except Exception as e:
            return jsonify({'success': True, 'message': f"【命令】{exec_cmd}\\n【执行失败】{str(e)}"})
    elif exec_cmd:
        return jsonify({'success': True, 'message': f"【生成命令】{exec_cmd}"})
    else:
        return jsonify({'success': True, 'message': 'NetOps AI - 支持：VLAN/接口/路由/邻居/ARP'})'''

if old_llm in content:
    content = content.replace(old_llm, new_keywords)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Replaced LLM with keyword detection!")
else:
    print("❌ Could not find LLM code")
