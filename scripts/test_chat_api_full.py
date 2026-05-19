"""Full API test - exactly what frontend does"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

# Clear
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'api_test'})

# Test 1: with selected_device
print("=== Test 1: with selected_device=接入交换机 ===")
r = requests.post(f'{BASE}/api/chat', json={
    'message': '查看版本',
    'context': {'selected_device': '接入交换机'},
    'session_id': 'api_test'
}, timeout=120)
d = r.json()
print(f"  success={d.get('success')} preview={d.get('preview')} executed={d.get('executed')}")
print(f"  response[:200]: {d.get('response','')[:200]}")
print(f"  planned_commands: {d.get('planned_commands')}")
print(f"  tool_calls count: {len(d.get('tool_calls',[]))}")
if d.get('tool_calls'):
    for tc in d['tool_calls']:
        print(f"    tool={tc.get('tool')} error={tc.get('error')}")
        if tc.get('result'):
            res = tc['result']
            if isinstance(res, dict):
                print(f"    result_keys={list(res.keys())}")
                if res.get('results'):
                    for output in res['results'][:2]:
                        print(f"      output[:100]={str(output)[:100]}")

# Clear and test 2
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'api_test2'})
print("\n=== Test 2: show interface brief ===")
r2 = requests.post(f'{BASE}/api/chat', json={
    'message': '显示接口状态',
    'context': {'selected_device': '核心交换机'},
    'session_id': 'api_test2'
}, timeout=120)
d2 = r2.json()
print(f"  success={d2.get('success')} preview={d2.get('preview')} executed={d2.get('executed')}")
print(f"  response[:200]: {d2.get('response','')[:200]}")
print(f"  planned_commands: {d2.get('planned_commands')}")
if d2.get('tool_calls'):
    for tc in d2['tool_calls']:
        print(f"    tool={tc.get('tool')}")
        if tc.get('result'):
            res = tc['result']
            if isinstance(res, dict) and res.get('results'):
                for output in res['results'][:2]:
                    print(f"      output[:100]={str(output)[:100]}")

# Test 3: config command (should preview)
requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'api_test3'})
print("\n=== Test 3: config command (should preview) ===")
r3 = requests.post(f'{BASE}/api/chat', json={
    'message': '创建VLAN 100',
    'context': {'selected_device': '接入交换机'},
    'session_id': 'api_test3'
}, timeout=120)
d3 = r3.json()
print(f"  success={d3.get('success')} preview={d3.get('preview')} executed={d3.get('executed')}")
print(f"  planned_commands: {d3.get('planned_commands')}")
print(f"  response[:200]: {d3.get('response','')[:200]}")
