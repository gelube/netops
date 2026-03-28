#!/usr/bin/env python3
"""修复：1) 模型保存 2) 传递设备参数给 LLM"""

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修复 LLM 配置保存 - 确保参数正确传递
old_save = '''    llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
    llm_client = LLMClient(llm_config)
    llm_config.save()
    persist_llm_config({'provider': provider.value, 'endpoint': endpoint, 'model': model})'''

new_save = '''    llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
    llm_client = LLMClient(llm_config)
    llm_config.save()
    persist_llm_config({'provider': provider.value, 'endpoint': endpoint, 'api_key': api_key, 'model': model})'''

if old_save in content:
    content = content.replace(old_save, new_save)
    print("Fixed model saving")

# 2. 修复 chat 函数 - 传递设备厂商信息给 LLM
old_chat_context = '''    # 构建上下文
    context = ""
    if current_topology and current_topology.devices:
        context = f"当前网络拓扑：\\n设备数量：{len(current_topology.devices)}\\n\\n"
        for dev in current_topology.devices[:5]:
            context += f"- {dev.name} ({dev.ip}) - {dev.vendor.value}\\n"'''

new_chat_context = '''    # 构建上下文（包含设备厂商信息）
    context = ""
    device_vendors = []
    if current_topology and current_topology.devices:
        for dev in current_topology.devices:
            device_vendors.append(dev.vendor.value)
        context = f"当前网络设备：\\n"
        context += f"设备数量：{len(current_topology.devices)}\\n"
        context += f"设备厂商：{', '.join(set(device_vendors))}\\n\\n"
        for dev in current_topology.devices[:5]:
            context += f"- {dev.name} ({dev.ip}) - {dev.vendor.value}\\n"'''

if old_chat_context in content:
    content = content.replace(old_chat_context, new_chat_context)
    print("Fixed device context")

# 3. 修改 system prompt - 强调根据设备厂商返回命令
old_prompt = 'llm_instruction = "你是 H3C 网络设备配置助手。用户说创建/做 vlan 就返回 vlan batch 命令，说查看就返回 display 命令。只返回命令，不要任何解释！"'
new_prompt = 'llm_instruction = f"你是网络设备配置助手。当前设备厂商：{\\',\\'.join(set(device_vendors)) if device_vendors else \\'H3C\\'}。用户说创建/做 vlan 就返回 vlan batch 命令，说查看就返回 display 命令。只返回命令行，不要任何解释、步骤或说明！"'

if old_prompt in content:
    content = content.replace(old_prompt, new_prompt)
    print("Fixed system prompt")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("All fixes applied!")
