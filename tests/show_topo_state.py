import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('Z:/netops-ai/web/data/topology_state.json','r',encoding='utf-8') as f:
    d = json.load(f)
links = d.get('links',[])
print(f'links: {len(links)}')
for lk in links:
    fn = lk.get('from_name','?')
    fp = lk.get('from_port','?')
    tn = lk.get('to_name','?')
    tp = lk.get('to_port','?')
    st = lk.get('status','?')
    print(f'  [{st}] {fn} {fp} -> {tn} {tp}')
