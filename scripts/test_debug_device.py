"""Debug: check what GLM-5 returns for device name"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

# Check devices first
r = requests.get(f'{BASE}/api/devices', timeout=5)
devs = r.json().get('devices', [])
for d in devs:
    print(f"  name={d.get('name')} remark={d.get('remark')} ip={d.get('ip')}")

# Test 查看设备运行时间 with debug
print("\n=== 查看设备运行时间 ===")
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'debug_route2'})
r = requests.post(f'{BASE}/api/chat', json={
    'message': '查看设备运行时间',
    'context': {'selected_device': '出口路由'},
    'session_id': 'debug_route2'
}, timeout=60)
d = r.json()
print(f"  executed={d.get('executed')} preview={d.get('preview')}")
print(f"  planned={json.dumps(d.get('planned_commands',[]), ensure_ascii=False)}")
print(f"  response={d.get('response','')[:300]}")

# Also check the flask log for more detail
print("\n=== 查下日志有没有报错 ===")
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'debug_log'})
r = requests.post(f'{BASE}/api/chat', json={
    'message': '查下日志有没有报错',
    'context': {'selected_device': '出口路由'},
    'session_id': 'debug_log'
}, timeout=60)
d = r.json()
print(f"  executed={d.get('executed')} preview={d.get('preview')}")
print(f"  planned={json.dumps(d.get('planned_commands',[]), ensure_ascii=False)}")
