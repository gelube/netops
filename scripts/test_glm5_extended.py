"""Extended diverse natural language tests for GLM-5"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

tests = [
    # More varied phrasings
    ("告诉我接入交换机的版本信息", "接入交换机", True),
    ("核心交换机有多少个接口在UP", "核心交换机", True),
    ("出口路由的OSPF建邻居了吗", "出口路由", True),
    ("查一下核心的MAC地址表", "核心交换机", True),
    ("接入交换机的配置导出给我看", "接入交换机", True),
    ("看看核心交换机有没有告警", "核心交换机", True),
    ("display device", "接入交换机", True),
    ("ping 10.1.1.1", "出口路由", True),
    ("路由表看一下", "出口路由", True),
    ("有没有环路风险", "核心交换机", True),
    # Config commands (should preview)
    ("给VLAN 20加个描述test", "接入交换机", False),
    ("把GE1/0/3口改成access口", "核心交换机", False),
]

PASS = 0
FAIL = 0
for msg, dev, expect_readonly in tests:
    sid = f'test_ext_{hash(msg) % 10000}'
    requests.post(f'{BASE}/api/chat/clear', json={'session_id': sid})
    try:
        r = requests.post(f'{BASE}/api/chat', json={
            'message': msg,
            'context': {'selected_device': dev},
            'session_id': sid
        }, timeout=60)
        d = r.json()
        executed = d.get('executed')
        preview = d.get('preview')
        planned = d.get('planned_commands')
        
        if expect_readonly:
            ok = executed == True
            status = "✅" if ok else "❌"
            if ok: PASS += 1
            else: FAIL += 1
            print(f"{status} [{msg}] executed={executed} preview={preview}")
            if not ok:
                resp = d.get('response', '')[:150]
                print(f"   resp={resp}")
                if planned: print(f"   planned={json.dumps(planned, ensure_ascii=False)[:200]}")
        else:
            ok = preview == True and planned is not None
            status = "✅" if ok else "❌"
            if ok: PASS += 1
            else: FAIL += 1
            print(f"{status} [{msg}] preview={preview} planned={bool(planned)} executed={executed}")
            if not ok:
                resp = d.get('response', '')[:150]
                print(f"   resp={resp}")
    except Exception as e:
        FAIL += 1
        print(f"❌ [{msg}] ERROR: {e}")

print(f"\n{'='*50}")
print(f"Results: {PASS} PASS / {FAIL} FAIL")
