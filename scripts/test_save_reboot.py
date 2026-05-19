"""Quick test: save + reboot + lldp"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

tests = [
    # Should preview (not execute directly)
    ("保存配置", "接入交换机", False),
    ("重启设备", "出口路由", False),
    ("关闭lldp", "出口路由", False),
    ("开启lldp", "出口路由", False),
    # Should execute directly
    ("查看版本", "接入交换机", True),
]

for msg, dev, expect_readonly in tests:
    sid = f'qt_{hash(msg) % 10000}'
    try:
        requests.post(f'{BASE}/api/chat/clear', json={'session_id': sid}, timeout=5)
    except:
        pass
    try:
        r = requests.post(f'{BASE}/api/chat', json={
            'message': msg,
            'context': {'selected_device': dev},
            'session_id': sid
        }, timeout=90)
        d = r.json()
        executed = d.get('executed')
        preview = d.get('preview')
        planned = d.get('planned_commands')
        response = d.get('response', '')[:150]
        
        if expect_readonly:
            ok = executed == True
            print(f"{'✅' if ok else '❌'} [{msg}] executed={executed} → {response}")
        else:
            ok = preview == True and planned is not None
            print(f"{'✅' if ok else '❌'} [{msg}] preview={preview} planned={json.dumps(planned, ensure_ascii=False)[:100] if planned else None} executed={executed}")
            if not ok:
                print(f"   response={response}")
    except Exception as e:
        print(f"❌ [{msg}] ERROR: {e}")
