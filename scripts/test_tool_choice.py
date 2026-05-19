"""Test: force tool_choice=required if model supports it"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'Z:\netops-ai')
sys.path.insert(0, r'Z:\netops-ai\web')

import json, os, requests
from app.llm.config import LLMConfig, LLMClient, _decrypt_api_key
from netops_tools import get_tools_definition

llm_config_file = os.path.join(r'Z:\netops-ai\web\data', 'llm_config.json')
with open(llm_config_file, 'r', encoding='utf-8') as f:
    cfg_data = json.load(f)

endpoint = cfg_data.get("endpoint", "") or cfg_data.get("base_url", "")
model = cfg_data.get("model", "")

tools_def = get_tools_definition()

messages = [
    {"role": "system", "content": "你是网络运维助手。当前设备：核心交换机。"},
    {"role": "user", "content": "[当前设备：核心交换机] 显示接口状态"}
]

# Test 1: tool_choice=auto (default)
print("=== tool_choice=auto ===")
r = requests.post(f'{endpoint}/chat/completions', json={
    'model': model,
    'messages': messages,
    'tools': tools_def,
    'tool_choice': 'auto',
    'max_tokens': 500
}, timeout=60)
d = r.json()
msg = d['choices'][0]['message']
print(f"  content: {msg.get('content','')[:200]}")
print(f"  tool_calls: {json.dumps(msg.get('tool_calls'), ensure_ascii=False)[:300] if msg.get('tool_calls') else 'None'}")
print(f"  finish_reason: {d['choices'][0].get('finish_reason')}")

# Test 2: tool_choice=required
print("\n=== tool_choice=required ===")
r2 = requests.post(f'{endpoint}/chat/completions', json={
    'model': model,
    'messages': messages,
    'tools': tools_def,
    'tool_choice': 'required',
    'max_tokens': 500
}, timeout=60)
d2 = r2.json()
msg2 = d2['choices'][0]['message']
print(f"  content: {msg2.get('content','')[:200]}")
print(f"  tool_calls: {json.dumps(msg2.get('tool_calls'), ensure_ascii=False)[:300] if msg2.get('tool_calls') else 'None'}")
print(f"  finish_reason: {d2['choices'][0].get('finish_reason')}")

# Test 3: tool_choice pointing to specific function
print("\n=== tool_choice={'type':'function','function':{'name':'run_commands'}} ===")
r3 = requests.post(f'{endpoint}/chat/completions', json={
    'model': model,
    'messages': messages,
    'tools': tools_def,
    'tool_choice': {'type': 'function', 'function': {'name': 'run_commands'}},
    'max_tokens': 500
}, timeout=60)
d3 = r3.json()
msg3 = d3['choices'][0]['message']
print(f"  content: {msg3.get('content','')[:200]}")
print(f"  tool_calls: {json.dumps(msg3.get('tool_calls'), ensure_ascii=False)[:300] if msg3.get('tool_calls') else 'None'}")
print(f"  finish_reason: {d3['choices'][0].get('finish_reason')}")
