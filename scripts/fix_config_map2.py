"""
Add _CONFIG_MAP and _match_config_command to chat.py
Insert between _match_device and _get_session_mgr
"""
import re

path = r'Z:\netops-ai\web\blueprints\chat.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

insert_after = "    return None\n\n\ndef _get_session_mgr():"

insert_code = """    return None


# 配置意图 -> 命令映射（当LLM不能正确生成tool_calls时使用）
_CONFIG_MAP = [
    # (关键词列表, 命令模板)
    (["关闭lldp", "禁用lldp", "停用lldp"], "undo lldp global enable"),
    (["开启lldp", "启用lldp"], "lldp global enable"),
    (["保存配置", "保存"], "save force"),
    (["重启设备", "重启"], "reboot"),
]


def _match_config_command(message):
    \"\"\"Try to match a config intent from the message when LLM returns text instead of tool_calls.
    Returns a command string if matched, None otherwise.
    \"\"\"
    msg_lower = message.lower().strip()
    
    # 1. Simple keyword-based mapping
    for keywords, cmd_template in _CONFIG_MAP:
        if any(kw in msg_lower for kw in keywords):
            return cmd_template
    
    # 2. "关闭GE1/0/1" -> system-view + interface + shutdown
    port_match = re.search(r'(?:关闭|shutdown)\\s*(?:接口|端口)?\\s*([GEgi][Ei]?\\s*\\d+/\\d+/\\d+)', message, re.IGNORECASE)
    if port_match:
        port = port_match.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        return f"system-view\\ninterface {port}\\nshutdown"
    
    # 3. "开启GE1/0/1" -> undo shutdown
    port_match = re.search(r'(?:开启|undo\\s+shutdown)\\s*(?:接口|端口)?\\s*([GEgi][Ei]?\\s*\\d+/\\d+/\\d+)', message, re.IGNORECASE)
    if port_match:
        port = port_match.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        return f"system-view\\ninterface {port}\\nundo shutdown"
    
    # 4. "创建VLAN X"
    vlan_match = re.search(r'创建\\s*(?:VLAN|vlan)\\s*(\\d+)', message, re.IGNORECASE)
    if vlan_match:
        vid = vlan_match.group(1)
        return f"system-view\\nvlan {vid}"
    
    # 5. "删除VLAN X"
    vlan_match = re.search(r'删除\\s*(?:VLAN|vlan)\\s*(\\d+)', message, re.IGNORECASE)
    if vlan_match:
        vid = vlan_match.group(1)
        return f"system-view\\nundo vlan {vid}"
    
    # 6. "把GE1/0/1划入VLAN 10"
    port_vlan = re.search(r'([GEgi][Ei]?\\s*\\d+/\\d+/\\d+).*?(?:划入|加入|分配到|放到)\\s*(?:VLAN|vlan)\\s*(\\d+)', message, re.IGNORECASE)
    if port_vlan:
        port = port_vlan.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        vid = port_vlan.group(2)
        return f"system-view\\ninterface {port}\\nport access vlan {vid}"
    
    # 7. "GE1/0/1改成access口"
    port_type = re.search(r'([GEgi][Ei]?\\s*\\d+/\\d+/\\d+).*?改成?\\s*(access|trunk)', message, re.IGNORECASE)
    if port_type:
        port = port_type.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        ptype = port_type.group(2).lower()
        return f"system-view\\ninterface {port}\\nport link-type {ptype}"
    
    # 8. "给GE1/0/1加描述xxx"
    port_desc = re.search(r'(?:给|为)?\\s*([GEgi][Ei]?\\s*\\d+/\\d+/\\d+).*?(?:加描述|设置描述|描述为|description)\\s*(.+)', message, re.IGNORECASE)
    if port_desc:
        port = port_desc.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        desc = port_desc.group(2).strip()
        return f"system-view\\ninterface {port}\\ndescription {desc}"
    
    # 9. "设置GE1/0/1的IP为x.x.x.x/y"
    port_ip = re.search(r'(?:设置|配置)?\\s*([GEgi][Ei]?\\s*\\d+/\\d+/\\d+).*?(?:IP|ip|地址).*?(\\d+\\.\\d+\\.\\d+\\.\\d+/\\d+)', message, re.IGNORECASE)
    if port_ip:
        port = port_ip.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        ip_mask = port_ip.group(2)
        return f"system-view\\ninterface {port}\\nport link-type route\\nipv4 address {ip_mask}"
    
    return None


def _get_session_mgr():"""

if insert_after not in content:
    print("ERROR: Can't find insertion point")
    # Debug
    idx = content.find("def _get_session_mgr")
    if idx >= 0:
        print(f"Found _get_session_mgr at char {idx}")
        print(repr(content[idx-50:idx+30]))
    exit(1)

content = content.replace(insert_after, insert_code, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK - _CONFIG_MAP and _match_config_command added")
