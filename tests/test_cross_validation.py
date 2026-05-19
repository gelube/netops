"""测试LLDP交叉验证逻辑"""
import re

links = [
    {"from_name":"接入交换机","from_port":"GE1/0/1","to_name":"H3C","to_port":"GigabitEthernet1/0/1","chassis_id":"6874-2a6b-0200"},
    {"from_name":"接入交换机","from_port":"GE1/0/2","to_name":"H3C","to_port":"GigabitEthernet1/0/3","chassis_id":"6874-2a6b-0200"},
    {"from_name":"核心交换机","from_port":"GE1/0/1","to_name":"H3C","to_port":"GigabitEthernet1/0/1","chassis_id":"6873-af13-0100"},
    {"from_name":"核心交换机","from_port":"GE1/0/2","to_name":"H3C","to_port":"GigabitEthernet0/0/0","chassis_id":"6874-dafe-0300"},
    {"from_name":"核心交换机","from_port":"GE1/0/3","to_name":"H3C","to_port":"GigabitEthernet1/0/2","chassis_id":"6873-af13-0100"},
    {"from_name":"出口路","from_port":"GE0/0/0","to_name":"H3C","to_port":"GigabitEthernet1/0/2","chassis_id":"6874-2a6b-0200"},
]

def normalize(p):
    if not p:
        return p
    for pat, rep in [
        (r"^GE(\d)", r"GigabitEthernet\1"),
        (r"^XGE(\d)", r"10GigabitEthernet\1"),
        (r"^10GE(\d)", r"10GigabitEthernet\1"),
    ]:
        p = re.sub(pat, rep, p)
    return p

print("=== 双向交叉验证 ===")
for i, la in enumerate(links):
    for lb in links[i + 1:]:
        la_fp = normalize(la["from_port"])
        la_tp = normalize(la["to_port"])
        lb_fp = normalize(lb["from_port"])
        lb_tp = normalize(lb["to_port"])
        if la_fp == lb_tp and la_tp == lb_fp and la["to_name"] == lb["to_name"]:
            print(f"  MATCH: {la['from_name']} {la['from_port']} <-> {lb['from_name']} {lb['from_port']}")
        elif la_fp == lb_tp or la_tp == lb_fp:
            print(f"  PARTIAL: {la['from_name']} {la['from_port']}:{la_tp} <-> {lb['from_name']} {lb['from_port']}:{lb_tp}")

print("\n=== chassis_id匹配 ===")
# 构建chassis_id → [(device_name, from_port, to_port)]
cid_seen = {}
for link in links:
    cid = link.get("chassis_id", "")
    if not cid:
        continue
    cid_seen.setdefault(cid, []).append((link["from_name"], link["from_port"], link["to_port"]))

for cid, sightings in cid_seen.items():
    print(f"  chassis_id={cid}:")
    for s in sightings:
        print(f"    seen by {s[0]} from_port={s[1]} to_port={s[2]}")

# 尝试chassis_id交叉匹配
print("\n=== chassis_id交叉匹配结果 ===")
# chassis_id就是邻居的MAC地址，每台设备的chassis_id是它自己的
# 如果A看到邻居chassis_id=X，而B也看到邻居chassis_id=Y
# 关键：A看到to_port=GigabitEthernet1/0/1，说明邻居在那个端口连着A
# 如果B的from_port归一化后等于A看到的to_port，那B就是A的邻居

devices = [
    {"name": "接入交换机", "chassis_id": "6873-af13-0100"},
    {"name": "核心交换机", "chassis_id": "6874-2a6b-0200"},
    {"name": "出口路", "chassis_id": "6874-dafe-0300"},
]

# 构建设备名→chassis_id映射
dev_chassis = {d["name"]: d["chassis_id"] for d in devices}
# 构建chassis_id→设备名映射
chassis_dev = {d["chassis_id"]: d["name"] for d in devices}

print("chassis_id → device mapping:")
for cid, name in chassis_dev.items():
    print(f"  {cid} → {name}")

# 对每条链路，用chassis_id找邻居设备名
print("\nchassis_id-based link resolution:")
for link in links:
    cid = link.get("chassis_id", "")
    neighbor_name = chassis_dev.get(cid, "UNKNOWN")
    print(f"  {link['from_name']} {link['from_port']} → {neighbor_name} (chassis={cid}) {link['to_port']}")
