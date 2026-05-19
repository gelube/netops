"""Fix system prompt - shorter, no tool def duplication, few-shot examples"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'Z:\netops-ai\web\blueprints\chat.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_prompt = '''    system_prompt = f"""你是一个网络运维助手，帮助用户管理网络设备。

可用设备：
{device_list_str}

当前选中设备：{selected_device or "未选择"}

你可以使用以下工具：
{json.dumps(get_tools_definition(), ensure_ascii=False, indent=2)}

规则：
1. 执行命令前先确认设备名
2. 配置命令需要用户确认
3. 危险操作（重启、删除配置等）必须警告
4. 优先使用只读命令了解状态
"""'''

new_prompt = '''    system_prompt = f"""你是网络运维助手。当前选中设备：{selected_device or "未选择"}。
可用设备：{device_list_str}

重要：当前已选中设备时，直接对该设备执行命令，不要再询问用户选择设备。
直接调用 run_commands 工具，参数示例：
- 用户说"查看版本"→ run_commands(device="{selected_device or '设备名'}", commands=["display version"])
- 用户说"显示接口"→ run_commands(device="{selected_device or '设备名'}", commands=["display interface brief"])
- 用户说"创建VLAN 100"→ run_commands(device="{selected_device or '设备名'}", commands=["system-view","vlan 100","quit"])

规则：
1. 已选中设备时直接执行，不要确认
2. 配置命令（非display/show/save/ping/traceroute）需要预览确认
3. 危险操作（重启、删除配置）必须警告
4. 华为/华三用display，思科用show
"""'''

if old_prompt in content:
    content = content.replace(old_prompt, new_prompt)
    print("System prompt replaced successfully")
else:
    print("ERROR: old prompt not found, trying line-by-line approach")
    # Find and replace
    import re
    # Find the system_prompt assignment
    lines = content.split('\n')
    start = None
    end = None
    for i, line in enumerate(lines):
        if 'system_prompt = f"""' in line and '网络运维助手' in line:
            start = i
        if start is not None and line.strip() == '"""':
            end = i
            break
    if start and end:
        print(f"Found prompt at lines {start+1}-{end+1}")
        # Replace those lines
        indent = '    '
        new_lines = [
            f'{indent}system_prompt = f"""你是网络运维助手。当前选中设备：{{selected_device or "未选择"}}。',
            f'{indent}可用设备：{{device_list_str}}',
            f'{indent}',
            f'{indent}重要：当前已选中设备时，直接对该设备执行命令，不要再询问用户选择设备。',
            f'{indent}直接调用 run_commands 工具，参数示例：',
            f'{indent}- 用户说"查看版本"→ run_commands(device="{{selected_device or \'设备名\'}}", commands=["display version"])',
            f'{indent}- 用户说"显示接口"→ run_commands(device="{{selected_device or \'设备名\'}}", commands=["display interface brief"])',
            f'{indent}- 用户说"创建VLAN 100"→ run_commands(device="{{selected_device or \'设备名\'}}", commands=["system-view","vlan 100","quit"])',
            f'{indent}',
            f'{indent}规则：',
            f'{indent}1. 已选中设备时直接执行，不要确认',
            f'{indent}2. 配置命令（非display/show/save/ping/traceroute）需要预览确认',
            f'{indent}3. 危险操作（重启、删除配置）必须警告',
            f'{indent}4. 华为/华三用display，思科用show',
            f'{indent}"""',
        ]
        lines[start:end+1] = new_lines
        content = '\n'.join(lines)
        print("Replaced via line approach")
    else:
        print("FATAL: Could not find prompt to replace")
        sys.exit(1)

# Also remove the tools from system prompt since they're passed via tools= param
# The old prompt had: {json.dumps(get_tools_definition(), ensure_ascii=False, indent=2)}
# Our new prompt doesn't include this, which is correct

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("File saved")
