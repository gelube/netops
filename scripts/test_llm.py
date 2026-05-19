import json, requests

with open(r'Z:\netops-ai\web\data\llm_config.json','r',encoding='utf-8') as f:
    cfg = json.load(f)
endpoint = cfg.get('endpoint','')
model = cfg.get('model','')

tools_def = [{
    'type': 'function',
    'function': {
        'name': 'run_commands',
        'description': 'Execute commands on a network device',
        'parameters': {
            'type': 'object',
            'properties': {
                'device': {'type':'string','description':'device name'},
                'commands': {'type':'array','items':{'type':'string'},'description':'commands to run'}
            },
            'required': ['device','commands']
        }
    }
}]

# Test with tools
r = requests.post(f'{endpoint}/chat/completions', json={
    'model': model,
    'messages': [
        {'role':'system','content':'You are a network assistant.'},
        {'role':'user','content':'查看接入交换机的版本信息'}
    ],
    'tools': tools_def,
    'max_tokens': 200
}, timeout=60)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    d = r.json()
    msg = d['choices'][0]['message']
    content = msg.get('content','')
    tool_calls = msg.get('tool_calls','none')
    print(f'Content: {content[:300]}')
    print(f'Tool calls: {json.dumps(tool_calls, ensure_ascii=False)[:500] if tool_calls != "none" else "none"}')
else:
    print(f'Error: {r.text[:300]}')
