"""Test _do_chat directly to see what LLM returns"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'Z:\netops-ai\web')

import json, os
from app.llm.config import LLMConfig, LLMClient, _decrypt_api_key
from netops_tools import get_tools_definition

# Load config
llm_config_file = os.path.join(r'Z:\netops-ai\web\data', 'llm_config.json')
with open(llm_config_file, 'r', encoding='utf-8') as f:
    cfg_data = json.load(f)

config = LLMConfig(
    provider=cfg_data.get("provider", "openai"),
    endpoint=cfg_data.get("endpoint", "") or cfg_data.get("base_url", ""),
    api_key=_decrypt_api_key(cfg_data.get("api_key", "")),
    model=cfg_data.get("model", ""),
)
llm = LLMClient(config)

tools_def = get_tools_definition()

# Simulate _do_chat
messages = [
    {"role": "system", "content": "你是一个网络运维助手，帮助用户管理网络设备。\n\n可用设备：\n- 接入交换机 (127.0.0.1, auto)\n- 核心交换机 (127.0.0.1, auto)\n- 出口路由 (127.0.0.1, auto)\n\n当前选中设备：接入交换机"},
    {"role": "user", "content": "查看版本"}
]

print("Calling llm.chat()...")
response = llm.chat(messages=messages, tools=tools_def)

print(f"Response keys: {list(response.keys())}")
print(f"Content: {response.get('content','')[:300]}")
print(f"Tool calls: {json.dumps(response.get('tool_calls'), ensure_ascii=False)[:500] if response.get('tool_calls') else 'None'}")
print(f"Error: {response.get('error','')}")

if response.get('tool_calls'):
    print("\nTool calls detail:")
    for tc in response['tool_calls']:
        print(f"  id={tc.get('id')}, name={tc.get('function',{}).get('name')}, args={tc.get('function',{}).get('arguments','')[:200]}")
