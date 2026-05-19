"""Test GLM-5 diverse natural language commands via API"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

tests = [
    ("查看ARP表", "接入交换机", True),
    ("看看有哪些VLAN", "核心交换机", True),
    ("接口GE1/0/1的流量怎么样", "接入交换机", True),
    ("帮我查一下MAC地址表", "核心交换机", True),
    ("查看设备运行时间", "出口路由", True),
    ("ospf邻居状态", "核心交换机", True),
    ("看看CPU利用率", "接入交换机", True),
    ("设备内存够不够", "核心交换机", True),
    ("查下日志有没有报错", "出口路由", True),
    ("当前配置是什么", "接入交换机", True),
    ("把GE1/0/1划入VLAN 10", "接入交换机", False),  # config
    ("关闭GE1/0/2接口", "核心交换机", False),  # config
]

PASS = 0
FAIL = 0
for msg, dev, expect_readonly in tests:
    sid = f'test_div_{msg[:6]}'
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
        resp = d.get('response', '')[:150]
        planned = d.get('planned_commands')
        
        if expect_readonly:
            ok = executed == True
            status = "✅" if ok else "❌"
            if ok: PASS += 1
            else: FAIL += 1
            print(f"{status} [{msg}] executed={executed} preview={preview}")
            if not ok:
                print(f"   resp={resp}")
                if planned: print(f"   planned={json.dumps(planned, ensure_ascii=False)[:200]}")
        else:
            ok = preview == True and planned is not None
            status = "✅" if ok else "❌"
            if ok: PASS += 1
            else: FAIL += 1
            print(f"{status} [{msg}] preview={preview} planned={bool(planned)}")
            if not ok:
                print(f"   executed={executed} resp={resp}")
    except Exception as e:
        FAIL += 1
        print(f"❌ [{msg}] ERROR: {e}")

print(f"\n{'='*50}")
print(f"Results: {PASS} PASS / {FAIL} FAIL")
