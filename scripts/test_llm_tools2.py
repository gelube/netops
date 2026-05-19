import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'Z:\netops-ai\web')
from netops_tools import get_tools_definition
import json, requests

t = get_tools_definition()
print(f"Tools count: {len(t)}")
for tool in t:
    fn = tool['function']
    print(f"  {fn['name']}: {fn['description'][:80]}")
    params = fn.get('parameters', {}).get('properties', {})
    print(f"    params: {list(params.keys())}")

# Now test LLM with these tools
with open(r'Z:\netops-ai\web\data\llm_config.json','r',encoding='utf-8') as f:
    cfg = json.load(f)

endpoint = cfg.get('endpoint','')
model = cfg.get('model','')

messages = [
    {"role": "system", "content": "你是网络运维助手。设备：接入交换机。当前选中设备：接入交换机。"},
    {"role": "user", "content": "查看版本"}
]

print(f"\n=== Testing LLM with tools ===")
r = requests.post(f'{endpoint}/chat/completions', json={
    'model': model,
    'messages': messages,
    'tools': t,
    'tool_choice': 'auto',
    'max_tokens': 500
}, timeout=60)
import requests
d = r.json()
msg = d['choices'][0]['message']
print(f"Content: {msg.get('content','')[:200]}")
tc = msg.get('tool_calls')
print(f"Tool calls: {json.dumps(tc, ensure_ascii=False)[:300] if tc else 'None'}")
print(f"Finish reason: {d['choices'][0].get('finish_reason')}")
