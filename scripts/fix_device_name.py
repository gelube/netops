"""Fix device name: 出口路 -> 出口路由"""
import json

filepath = r'Z:\netops-ai\web\data\devices.json'
with open(filepath, 'r', encoding='utf-8') as f:
    devs = json.load(f)

changed = 0
for d in devs:
    name = d.get('name', '')
    remark = d.get('remark', '')
    if name == '出口路':
        d['name'] = '出口路由'
        changed += 1
        print(f"Fixed name: 出口路 -> 出口路由")
    if remark == '出口路':
        d['remark'] = '出口路由'
        changed += 1
        print(f"Fixed remark: 出口路 -> 出口路由")

# Also fix topology_state.json
topo_path = r'Z:\netops-ai\web\data\topology_state.json'
with open(topo_path, 'r', encoding='utf-8') as f:
    state = json.load(f)

topo_changed = 0
for n in state.get('nodes', []):
    if n.get('name') == '出口路':
        n['name'] = '出口路由'
        topo_changed += 1
    if n.get('remark') == '出口路':
        n['remark'] = '出口路由'
        topo_changed += 1
    if n.get('label') == '出口路':
        n['label'] = '出口路由'
        topo_changed += 1
for l in state.get('links', []):
    if l.get('from_name') == '出口路':
        l['from_name'] = '出口路由'
        topo_changed += 1
    if l.get('to_name') == '出口路':
        l['to_name'] = '出口路由'
        topo_changed += 1

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(devs, f, ensure_ascii=False, indent=2)
with open(topo_path, 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"devices.json: {changed} fixes")
print(f"topology_state.json: {topo_changed} fixes")
