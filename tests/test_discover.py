import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8')
r = requests.post('http://localhost:5000/api/topology/discover', json={}, timeout=120)
d = r.json()
print('success:', d.get('success'))
print('links:', d.get('links'))
edges = d.get('topology', {}).get('edges', [])
for lk in edges:
    fn = lk.get('from_name', '?')
    fp = lk.get('from_port', '?')
    tn = lk.get('to_name', '?')
    tp = lk.get('to_port', '?')
    st = lk.get('status', '?')
    print(f'  {fn} {fp} -> {tn} {tp} [{st}]')
