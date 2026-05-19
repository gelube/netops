import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json, requests

with open(r'Z:\netops-ai\web\data\llm_config.json','r',encoding='utf-8') as f:
    cfg = json.load(f)

endpoint = cfg.get('endpoint','')
model = cfg.get('model','')

# Simulate exactly what _do_chat does
from netops_tools import get_tools_definition
tools_def = get_tools_definition()

# Print tools count and first tool name
print(f"Tools count: {len(tools_def)}")
if tools_def:
    print(f"First tool: {tools_def[0].get('function',{}).get('name','')}")

# Test with same messages as _do_chat
messages = [
    {"role": "system", "content": "你是一个网络运维助手。可用设备：接入交换机(127.0.0.1), 核心交换机(127.0.0.1), 出口路由(127.0.0.1)。当前选中设备：接入交换机"},
    {"role": "user", "content": "查看接入交换机的版本"}
]

r = requests.post(f'{endpoint}/chat/completions', json={
    'model': model,
    'messages': messages,
    'tools': tools_def,
    'tool_choice': 'auto',
    'max_tokens': 500
}, timeout=60)

print(f"\nStatus: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    msg = d['choices'][0]['message']
    content = msg.get('content','')
    tool_calls = msg.get('tool_calls')
    print(f"Content: {content[:300]}")
    print(f"Tool calls: {json.dumps(tool_calls, ensure_ascii=False)[:500] if tool_calls else 'None'}")
    print(f"Finish reason: {d['choices'][0].get('finish_reason')}")
else:
    print(f"Error: {r.text[:300]}")

# Test without tools (just to see model responds)
print("\n\n=== Without tools ===")
r2 = requests.post(f'{endpoint}/chat/completions', json={
    'model': model,
    'messages': messages,
    'max_tokens': 500
}, timeout=60)
if r2.status_code == 200:
    d2 = r2.json()
    print(f"Content: {d2['choices'][0]['message'].get('content','')[:300]}")
    print(f"Finish reason: {d2['choices'][0].get('finish_reason')}")
