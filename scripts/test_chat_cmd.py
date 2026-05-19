import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

# Clear first
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'e2e_test'})

tests = [
    ("查看接入交换机的版本", {"selected_device": "接入交换机"}),
    ("显示核心交换机的接口状态", {"selected_device": "核心交换机"}),
    ("接入交换机ping 192.168.1.1", {"selected_device": "接入交换机"}),
    ("查看路由表", {"selected_device": "出口路由"}),
]

for msg, ctx in tests:
    print(f"\n{'='*60}")
    print(f"User: {msg}")
    print(f"Device: {ctx.get('selected_device','none')}")
    r = requests.post(f'{BASE}/api/chat', json={
        'message': msg,
        'context': ctx,
        'session_id': 'e2e_test'
    }, timeout=120)
    d = r.json()
    print(f"  success={d.get('success')} preview={d.get('preview')} executed={d.get('executed')}")
    print(f"  response[:300]: {d.get('response','')[:300]}")
    if d.get('planned_commands'):
        print(f"  planned: {json.dumps(d['planned_commands'], ensure_ascii=False)[:200]}")
    if d.get('tool_calls'):
        for tc in d['tool_calls']:
            print(f"  tool: {tc.get('tool')} result_keys={list(tc.get('result',{}).keys()) if isinstance(tc.get('result'),dict) else 'N/A'}")
