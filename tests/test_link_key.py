import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

def _normalize_port(port):
    if not port:
        return port
    for pat, repl in [
        (r"^GE(\d)", r"GigabitEthernet\1"),
        (r"^XGE(\d)", r"10GigabitEthernet\1"),
        (r"^10GE(\d)", r"10GigabitEthernet\1"),
        (r"^XE(\d)", r"10GigabitEthernet\1"),
        (r"^FE(\d)", r"FastEthernet\1"),
        (r"^E(\d)", r"Ethernet\1"),
    ]:
        port = re.sub(pat, repl, port)
    return port

def _link_key(e):
    fn = e.get('from_name', '') or e.get('from', '')
    tn = e.get('to_name', '') or e.get('to', '')
    fp = _normalize_port(e.get('from_port', ''))
    tp = _normalize_port(e.get('to_port', ''))
    side_a = f"{fn}|{fp}"
    side_b = f"{tn}|{tp}"
    if side_a > side_b:
        return f"{side_b}||{side_a}"
    else:
        return f"{side_a}||{side_b}"

with open('Z:/netops-ai/web/data/topology_state.json','r',encoding='utf-8') as f:
    d = json.load(f)

old_links = d.get('links', [])
print(f"Old links: {len(old_links)}")
for ol in old_links:
    k = _link_key(ol)
    fn = ol.get('from_name','')
    fp = ol.get('from_port','')
    tn = ol.get('to_name','')
    tp = ol.get('to_port','')
    st = ol.get('status','')
    nfp = _normalize_port(fp)
    ntp = _normalize_port(tp)
    print(f"  [{st}] {fn}({fp}->{nfp}) -> {tn}({tp}->{ntp})")
    print(f"       key: {k}")

# Simulated new edges (chassis_id resolved)
new_edges = [
    {"from_name": "接入交换机", "from_port": "GE1/0/1", "to_name": "核心交换机", "to_port": "GigabitEthernet1/0/1"},
    {"from_name": "核心交换机", "from_port": "GE1/0/2", "to_name": "出口路", "to_port": "GigabitEthernet0/0/0"},
    {"from_name": "接入交换机", "from_port": "GE1/0/2", "to_name": "核心交换机", "to_port": "GigabitEthernet1/0/3"},
]
print(f"\nNew edges: {len(new_edges)}")
for ne in new_edges:
    k = _link_key(ne)
    fn = ne.get('from_name','')
    fp = ne.get('from_port','')
    tn = ne.get('to_name','')
    tp = ne.get('to_port','')
    nfp = _normalize_port(fp)
    ntp = _normalize_port(tp)
    print(f"  {fn}({fp}->{nfp}) -> {tn}({tp}->{ntp})")
    print(f"       key: {k}")

# Match check
new_keys = {_link_key(ne) for ne in new_edges}
print("\n=== Matching ===")
for ol in old_links:
    k = _link_key(ol)
    match = k in new_keys
    print(f"  {k} -> {'MATCH' if match else 'NO MATCH'}")
