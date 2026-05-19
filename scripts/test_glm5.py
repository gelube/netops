"""Test GLM-5 function calling capabilities"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

# Test 1: Simple greeting
print("=== Test 1: Simple greeting ===")
r = requests.post(f'{BASE}/api/chat', json={
    'message': '你好',
    'context': {},
    'session_id': 'test_glm_1'
}, timeout=30)
d = r.json()
print(f"  success={d.get('success')} executed={d.get('executed')} preview={d.get('preview')}")
print(f"  response={d.get('response','')[:200]}")

# Test 2: 查看版本 with device
print("\n=== Test 2: 查看版本 (with device) ===")
r = requests.post(f'{BASE}/api/chat', json={
    'message': '查看版本',
    'context': {'selected_device': '接入交换机'},
    'session_id': 'test_glm_2'
}, timeout=60)
d = r.json()
print(f"  success={d.get('success')} executed={d.get('executed')} preview={d.get('preview')}")
print(f"  response={d.get('response','')[:300]}")
if d.get('planned_commands'):
    print(f"  planned={json.dumps(d['planned_commands'], ensure_ascii=False)[:200]}")

# Test 3: 显示接口
print("\n=== Test 3: 显示接口 (with device) ===")
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_glm_3'})
r = requests.post(f'{BASE}/api/chat', json={
    'message': '显示接口',
    'context': {'selected_device': '核心交换机'},
    'session_id': 'test_glm_3'
}, timeout=60)
d = r.json()
print(f"  success={d.get('success')} executed={d.get('executed')} preview={d.get('preview')}")
print(f"  response={d.get('response','')[:300]}")

# Test 4: VLAN配置
print("\n=== Test 4: 创建VLAN 100 (config) ===")
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_glm_4'})
r = requests.post(f'{BASE}/api/chat', json={
    'message': '创建VLAN 100',
    'context': {'selected_device': '接入交换机'},
    'session_id': 'test_glm_4'
}, timeout=60)
d = r.json()
print(f"  success={d.get('success')} executed={d.get('executed')} preview={d.get('preview')}")
if d.get('planned_commands'):
    print(f"  planned={json.dumps(d['planned_commands'], ensure_ascii=False)[:200]}")
print(f"  response={d.get('response','')[:300]}")

# Test 5: Ping测试
print("\n=== Test 5: Ping 192.168.1.1 ===")
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_glm_5'})
r = requests.post(f'{BASE}/api/chat', json={
    'message': 'ping 192.168.1.1',
    'context': {'selected_device': '接入交换机'},
    'session_id': 'test_glm_5'
}, timeout=60)
d = r.json()
print(f"  success={d.get('success')} executed={d.get('executed')} preview={d.get('preview')}")
print(f"  response={d.get('response','')[:300]}")

# Test 6: 查看路由表
print("\n=== Test 6: 查看路由表 ===")
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_glm_6'})
r = requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_glm_6'})
r = requests.post(f'{BASE}/api/chat', json={
    'message': '查看路由表',
    'context': {'selected_device': '出口路由'},
    'session_id': 'test_glm_6'
}, timeout=60)
d = r.json()
print(f"  success={d.get('success')} executed={d.get('executed')} preview={d.get('preview')}")
print(f"  response={d.get('response','')[:300]}")

# Test 7: 纯问题（不选设备）
print("\n=== Test 7: 什么是VLAN ===")
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_glm_7'})
r = requests.post(f'{BASE}/api/chat', json={
    'message': '什么是VLAN',
    'context': {},
    'session_id': 'test_glm_7'
}, timeout=60)
d = r.json()
print(f"  success={d.get('success')} executed={d.get('executed')}")
print(f"  response={d.get('response','')[:300]}")
