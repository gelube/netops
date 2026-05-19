"""
Add _CONFIG_MAP and _match_config_command to chat.py
Also fix the "no tool_calls" fallback path
"""
import re

path = r'Z:\netops-ai\web\blueprints\chat.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add _CONFIG_MAP and _match_config_command after _match_device function
match_device_end = "    return None\n\n\n    is_pure_chat"
if match_device_end not in content:
    # Maybe the function was moved to module level already
    match_device_end = "    return None\n\n    is_pure_chat"
    if match_device_end not in content:
        # Try another pattern
        print("ERROR: Can't find insertion point after _match_device")
        # Let's find it
        for i, line in enumerate(content.split('\n')):
            if 'return None' in line and i > 0:
                prev_lines = content.split('\n')[max(0,i-5):i+3]
                # print surrounding context
        exit(1)

config_map_code = '''    return None


# 配置意图 → 命令映射（当LLM不能正确生成tool_calls时使用）
_CONFIG_MAP = [
    # (关键词列表, 命令模板, 参数提取正则)
    # LLDP
    (["关闭lldp", "禁用lldp", "停用lldp"], "undo lldp global enable", None),
    (["开启lldp", "启用lldp"], "lldp global enable", None),
    # 保存
    (["保存配置", "保存"], "save force", None),
    # 重启
    (["重启设备", "重启"], "reboot", None),
]


def _match_config_command(message):
    """Try to match a config intent from the message when LLM returns text instead of tool_calls.
    Returns a command string if matched, None otherwise.
    """
    msg_lower = message.lower().strip()
    
    for keywords, cmd_template, param_regex in _CONFIG_MAP:
        if not any(kw in msg_lower for kw in keywords):
            continue
        if cmd_template:
            return cmd_template
    
    # Special: "关闭GE1/0/1" → system-view + interface + shutdown
    port_match = re.search(r'(?:关闭|shutdown)\s*(?:接口|端口)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+)', message, re.IGNORECASE)
    if port_match:
        port = port_match.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        return f"system-view\\ninterface {port}\\nshutdown"
    
    # "开启GE1/0/1" → undo shutdown
    port_match = re.search(r'(?:开启|undo\s+shutdown)\s*(?:接口|端口)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+)', message, re.IGNORECASE)
    if port_match:
        port = port_match.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        return f"system-view\\ninterface {port}\\nundo shutdown"
    
    # "创建VLAN X"
    vlan_match = re.search(r'创建\s*(?:VLAN|vlan)\s*(\d+)', message, re.IGNORECASE)
    if vlan_match:
        vid = vlan_match.group(1)
        return f"system-view\\nvlan {vid}"
    
    # "删除VLAN X"
    vlan_match = re.search(r'删除\s*(?:VLAN|vlan)\s*(\d+)', message, re.IGNORECASE)
    if vlan_match:
        vid = vlan_match.group(1)
        return f"system-view\\nundo vlan {vid}"
    
    # "把GE1/0/1划入VLAN 10" / "GE1/0/1加入VLAN 10"
    port_vlan = re.search(r'([GEgi][Ei]?\s*\d+/\d+/\d+).*?(?:划入|加入|分配到|放到)\s*(?:VLAN|vlan)\s*(\d+)', message, re.IGNORECASE)
    if port_vlan:
        port = port_vlan.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        vid = port_vlan.group(2)
        return f"system-view\\ninterface {port}\\nport access vlan {vid}"
    
    # "GE1/0/1改成access口"
    port_type = re.search(r'([GEgi][Ei]?\s*\d+/\d+/\d+).*?改成?\s*(access|trunk)', message, re.IGNORECASE)
    if port_type:
        port = port_type.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        ptype = port_type.group(2).lower()
        return f"system-view\\ninterface {port}\\nport link-type {ptype}"
    
    # "给GE1/0/1加描述xxx"
    port_desc = re.search(r'(?:给|为)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+).*?(?:加描述|设置描述|描述为|description)\s*(.+)', message, re.IGNORECASE)
    if port_desc:
        port = port_desc.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        desc = port_desc.group(2).strip()
        return f"system-view\\ninterface {port}\\ndescription {desc}"
    
    # "设置GE1/0/1的IP为x.x.x.x/y"
    port_ip = re.search(r'(?:设置|配置)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+).*?(?:IP|ip|地址).*?(\d+\.\d+\.\d+\.\d+/\d+)', message, re.IGNORECASE)
    if port_ip:
        port = port_ip.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        ip_mask = port_ip.group(2)
        return f"system-view\\ninterface {port}\\nport link-type route\\nmac-address-hashing enable\\nips binding disable\\nipv4 address {ip_mask}"
    
    return None


    is_pure_chat'''

content = content.replace(match_device_end, config_map_code)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK - _CONFIG_MAP and _match_config_command added")
