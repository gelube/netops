"""Extended natural language test — colloquial, fuzzy, edge cases"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

tests = [
    # Very casual / colloquial
    ("帮我看下接入交换机的版本", "接入交换机", True),
    ("核心交换机接口啥情况", "核心交换机", True),
    ("出口路由有多少个arp", "出口路由", True),
    ("接入的mac表看看", "接入交换机", True),
    ("核心现在什么配置", "核心交换机", True),
    ("出口路由的ospf邻居起来没", "出口路由", True),
    ("看看接入交换机跑多久了", "接入交换机", True),
    # Config with casual wording
    ("帮我在接入交换机创个vlan 200", "接入交换机", False),
    ("把核心的GE1/0/2关了", "核心交换机", False),
    ("接入交换机GE1/0/2开一下", "接入交换机", False),
    ("给出口路由配个loopback地址1.1.1.1/32", "出口路由", False),
    # Edge: no device selected
    ("查看版本", None, None),  # should return text, not crash
    # Pure chat
    ("你好", None, "chat"),
    ("谢谢", None, "chat"),
]

def run_test(msg, dev, expect):
    sid = f'ext2_{hash(msg) % 100000}'
    try:
        requests.post(f'{BASE}/api/chat/clear', json={'session_id': sid}, timeout=5)
    except:
        pass
    try:
        payload = {'message': msg, 'session_id': sid}
        if dev:
            payload['context'] = {'selected_device': dev}
        r = requests.post(f'{BASE}/api/chat', json=payload, timeout=90)
        d = r.json()
        executed = d.get('executed')
        preview = d.get('preview')
        planned = d.get('planned_commands')
        response = d.get('response', '')[:120]
        
        if expect is True:  # readonly
            ok = executed == True
            detail = f"executed={executed}"
        elif expect is False:  # config
            ok = preview == True and planned is not None
            detail = f"preview={preview} planned={bool(planned)}"
        elif expect == "chat":
            ok = preview is None and executed is None and not planned
            detail = "chat"
        else:  # None = no device
            ok = True  # just shouldn't crash
            detail = f"no crash (preview={preview}, executed={executed})"
        
        status = "✅" if ok else "❌"
        extra = ""
        if not ok:
            extra = f"\n   response={response}"
            if planned: extra += f"\n   planned={json.dumps(planned, ensure_ascii=False)[:200]}"
        print(f"{status} [{msg}] @ {dev or 'None'} → {detail}{extra}")
        return ok
    except Exception as e:
        print(f"❌ [{msg}] @ {dev or 'None'} → ERROR: {str(e)[:100]}")
        return False

passed = sum(run_test(msg, dev, expect) for msg, dev, expect in tests)
total = len(tests)
print(f"\n{'='*50}")
print(f"Results: {passed}/{total} PASS")
