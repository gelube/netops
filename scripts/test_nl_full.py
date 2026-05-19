"""Comprehensive natural language command test — find all failures"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, json

BASE = 'http://127.0.0.1:5000'

# Category 1: View/Read commands (should execute directly)
read_tests = [
    # Basic
    ("查看版本", "接入交换机"),
    ("display version", "接入交换机"),
    ("看看接口状态", "核心交换机"),
    ("display interface brief", "核心交换机"),
    # Network
    ("查看路由表", "出口路由"),
    ("看看ARP", "接入交换机"),
    ("MAC地址表", "核心交换机"),
    ("VLAN信息", "接入交换机"),
    # Protocol
    ("OSPF邻居", "出口路由"),
    ("BGP状态", "出口路由"),
    ("STP信息", "核心交换机"),
    # LLDP
    ("LLDP邻居", "接入交换机"),
    ("查看邻居", "核心交换机"),
    # System
    ("CPU利用率", "接入交换机"),
    ("内存使用", "核心交换机"),
    ("看看日志", "出口路由"),
    ("当前配置", "接入交换机"),
    ("告警信息", "核心交换机"),
    # Diagnostics
    ("ping 10.1.1.1", "出口路由"),
    ("traceroute 8.8.8.8", "出口路由"),
]

# Category 2: Config commands (should preview)
config_tests = [
    # LLDP control
    ("关闭LLDP", "出口路由"),
    ("开启LLDP", "出口路由"),
    # Interface
    ("关闭GE1/0/1", "接入交换机"),
    ("开启GE1/0/1", "接入交换机"),
    ("把GE1/0/1划入VLAN 10", "接入交换机"),
    ("创建VLAN 100", "核心交换机"),
    ("删除VLAN 100", "核心交换机"),
    # Interface config
    ("GE1/0/1改成access口", "接入交换机"),
    ("GE1/0/1改成trunk口", "接入交换机"),
    ("给GE1/0/1加描述uplink", "接入交换机"),
    ("设置GE1/0/1的IP为10.1.1.1/24", "出口路由"),
    # System
    ("保存配置", "接入交换机"),
    ("重启设备", "出口路由"),
]

def run_test(msg, dev, expect_readonly):
    sid = f'test_full_{hash(msg) % 100000}'
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
        response = d.get('response', '')
        tool_calls = d.get('tool_calls')
        
        if expect_readonly:
            ok = executed == True
            detail = f"executed={executed}"
        else:
            ok = preview == True and planned is not None
            detail = f"preview={preview} planned={bool(planned)} executed={executed}"
        
        # If failed, show more info
        extra = ""
        if not ok:
            extra = f"\n   response={response[:200]}"
            if planned: extra += f"\n   planned={json.dumps(planned, ensure_ascii=False)[:200]}"
            if tool_calls: extra += f"\n   tool_calls={json.dumps(tool_calls, ensure_ascii=False)[:200]}"
        
        return ok, detail, extra
    except Exception as e:
        return False, "ERROR", f"\n   {str(e)[:200]}"

print("=" * 60)
print("READ-ONLY COMMANDS (should execute directly)")
print("=" * 60)
read_pass = 0
read_fail = []
for msg, dev in read_tests:
    ok, detail, extra = run_test(msg, dev, True)
    status = "✅" if ok else "❌"
    print(f"{status} [{msg}] @ {dev} → {detail}{extra}")
    if ok:
        read_pass += 1
    else:
        read_fail.append((msg, dev))

print(f"\n{'='*60}")
print("CONFIG COMMANDS (should preview)")
print("=" * 60)
cfg_pass = 0
cfg_fail = []
for msg, dev in config_tests:
    ok, detail, extra = run_test(msg, dev, False)
    status = "✅" if ok else "❌"
    print(f"{status} [{msg}] @ {dev} → {detail}{extra}")
    if ok:
        cfg_pass += 1
    else:
        cfg_fail.append((msg, dev))

total = len(read_tests) + len(config_tests)
passed = read_pass + cfg_pass
print(f"\n{'='*60}")
print(f"RESULTS: {passed}/{total} PASS ({read_pass}/{len(read_tests)} read + {cfg_pass}/{len(config_tests)} config)")
if read_fail:
    print(f"\nFailed reads: {[f'{m}@{d}' for m,d in read_fail]}")
if cfg_fail:
    print(f"Failed configs: {[f'{m}@{d}' for m,d in cfg_fail]}")
