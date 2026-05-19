"""Test confirm flow: preview -> confirm -> verify execution"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

# Step 1: Get preview
sid = 'test_confirm_flow'
requests.post(f'{BASE}/api/chat/clear', json={'session_id': sid}, timeout=5)

r = requests.post(f'{BASE}/api/chat', json={
    'message': '创建VLAN 200',
    'context': {'selected_device': '接入交换机'},
    'session_id': sid
}, timeout=60)
d = r.json()
print(f"Step 1 (preview): preview={d.get('preview')}, planned={json.dumps(d.get('planned_commands'), ensure_ascii=False)}")

if d.get('planned_commands'):
    # Step 2: Confirm execution
    r2 = requests.post(f'{BASE}/api/chat', json={
        'message': '确认执行',
        'confirmed_commands': d['planned_commands'],
        'context': {'selected_device': '接入交换机'},
        'session_id': sid
    }, timeout=60)
    d2 = r2.json()
    print(f"Step 2 (execute): executed={d2.get('executed')}, success={d2.get('success')}")
    if d2.get('results'):
        for r in d2['results']:
            print(f"  device={r.get('device')}, success={r.get('success')}")
            for o in r.get('results', []):
                print(f"  {o[:80]}...")
    
    # Step 3: Verify VLAN 200 exists
    r3 = requests.post(f'{BASE}/api/chat', json={
        'message': '查看VLAN',
        'context': {'selected_device': '接入交换机'},
        'session_id': sid
    }, timeout=60)
    d3 = r3.json()
    print(f"\nStep 3 (verify): executed={d3.get('executed')}")
    resp = d3.get('response', '')
    if '200' in resp:
        print("✅ VLAN 200 found in output!")
    else:
        print(f"❌ VLAN 200 not found. Response: {resp[:200]}")
else:
    print("❌ No planned_commands returned!")

# Test: 关闭LLDP confirm
print("\n--- LLDP关闭测试 ---")
sid2 = 'test_lldp_off'
requests.post(f'{BASE}/api/chat/clear', json={'session_id': sid2}, timeout=5)

r = requests.post(f'{BASE}/api/chat', json={
    'message': '关闭lldp',
    'context': {'selected_device': '出口路由'},
    'session_id': sid2
}, timeout=60)
d = r.json()
print(f"Preview: preview={d.get('preview')}, planned={json.dumps(d.get('planned_commands'), ensure_ascii=False)}")

if d.get('planned_commands'):
    r2 = requests.post(f'{BASE}/api/chat', json={
        'message': '确认',
        'confirmed_commands': d['planned_commands'],
        'context': {'selected_device': '出口路由'},
        'session_id': sid2
    }, timeout=60)
    d2 = r2.json()
    print(f"Execute: executed={d2.get('executed')}, success={d2.get('success')}")
    if d2.get('results'):
        for r in d2['results']:
            print(f"  device={r.get('device')}, success={r.get('success')}")
            for o in r.get('results', []):
                print(f"  {o[:100]}")
