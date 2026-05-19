import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

# Test 1: No device selected
print("=== Test: No device selected ===")
r = requests.post('http://localhost:5000/api/chat', json={
    'message': '帮我看看接入交换机的接口状态',
    'context': {},
    'session_id': 'test_no_dev'
}, timeout=120)
d = r.json()
print(f"success={d.get('success')} preview={d.get('preview')} executed={d.get('executed')}")
print(f"response[:200]={d.get('response','')[:200]}")

# Test 2: With device context
print("\n=== Test: With device context ===")
requests.post('http://localhost:5000/api/chat/clear', json={'session_id': 'test_with_dev'})
r = requests.post('http://localhost:5000/api/chat', json={
    'message': '查看版本',
    'context': {'selected_device': '接入交换机'},
    'session_id': 'test_with_dev'
}, timeout=120)
d = r.json()
print(f"success={d.get('success')} preview={d.get('preview')} executed={d.get('executed')}")
print(f"response[:200]={d.get('response','')[:200]}")

# Test 3: Quick-config path
print("\n=== Test: Quick-config ===")
r = requests.post('http://localhost:5000/api/quick-config', json={
    'message': '版本',
    'device': '接入交换机',
    'mode': 'preview'
}, timeout=30)
d = r.json()
print(f"success={d.get('success')} matched={d.get('matched')} query={d.get('query')}")
