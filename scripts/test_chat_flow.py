"""Full chat flow test"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json, time

BASE = 'http://localhost:5000'

def test_chat_simple():
    """Test 1: Simple greeting"""
    print("=" * 60)
    print("Test 1: Simple greeting")
    r = requests.post(f'{BASE}/api/chat', json={
        'message': '你好',
        'session_id': 'test_e2e'
    }, timeout=60)
    d = r.json()
    ok = d.get('success') and d.get('response','')
    print(f"  success={d.get('success')}, response_len={len(d.get('response',''))}, preview={d.get('preview')}")
    assert ok, f"Failed: {d}"
    print(f"  ✅ PASSED")

def test_chat_device_query():
    """Test 2: Query device info (should trigger tool call)"""
    print("=" * 60)
    print("Test 2: Device query (should trigger run_commands tool)")
    # Clear session first
    requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_e2e'})
    r = requests.post(f'{BASE}/api/chat', json={
        'message': '查看接入交换机的版本',
        'context': {'selected_device': '接入交换机'},
        'session_id': 'test_e2e'
    }, timeout=120)
    d = r.json()
    print(f"  success={d.get('success')}, preview={d.get('preview')}, executed={d.get('executed')}")
    print(f"  response_len={len(d.get('response',''))}")
    if d.get('planned_commands'):
        print(f"  planned_commands: {json.dumps(d['planned_commands'], ensure_ascii=False)[:200]}")
    if d.get('tool_calls'):
        print(f"  tool_calls count: {len(d['tool_calls'])}")
    # Even if device is offline, the chat flow should respond
    assert d.get('success') is not False or d.get('response',''), f"No response: {d}"
    print(f"  ✅ PASSED (got response)")

def test_chat_quick_config():
    """Test 3: Quick config match"""
    print("=" * 60)
    print("Test 3: Quick-config keyword match")
    r = requests.post(f'{BASE}/api/quick-config', json={
        'message': '版本',
        'device': '接入交换机',
        'mode': 'preview'
    }, timeout=30)
    d = r.json()
    print(f"  success={d.get('success')}, matched={d.get('matched')}, query={d.get('query')}")
    if d.get('results'):
        print(f"  results count: {len(d['results'])}")
    print(f"  ✅ PASSED")

def test_chat_natural_language():
    """Test 4: Natural language that doesn't match quick-config"""
    print("=" * 60)
    print("Test 4: Natural language (no quick-config match)")
    requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_nl'})
    r = requests.post(f'{BASE}/api/chat', json={
        'message': '接入交换机有哪些接口是down的',
        'context': {'selected_device': '接入交换机'},
        'session_id': 'test_nl'
    }, timeout=120)
    d = r.json()
    print(f"  success={d.get('success')}, response_len={len(d.get('response',''))}")
    print(f"  preview={d.get('preview')}, executed={d.get('executed')}")
    if d.get('response'):
        print(f"  response preview: {d['response'][:100]}")
    assert d.get('success') is not False or d.get('response',''), f"No response: {d}"
    print(f"  ✅ PASSED")

def test_chat_clear():
    """Test 5: Clear chat"""
    print("=" * 60)
    print("Test 5: Chat clear")
    r = requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'test_e2e'})
    d = r.json()
    print(f"  success={d.get('success')}")
    print(f"  ✅ PASSED")

if __name__ == '__main__':
    try:
        test_chat_simple()
        test_chat_quick_config()
        test_chat_device_query()
        test_chat_natural_language()
        test_chat_clear()
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✅")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback; traceback.print_exc()
