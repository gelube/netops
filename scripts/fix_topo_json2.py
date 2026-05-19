import json

with open('Z:/netops-ai/web/data/topology_state.json', 'rb') as f:
    raw = f.read()

# Find all occurrences of "}\r\n}" or "}\n}"  
ends = []
i = 0
while i < len(raw) - 1:
    if raw[i:i+1] == b'}':
        if raw[i+1:i+2] == b'\n' or raw[i+1:i+2] == b'\r':
            j = i + 1
            if raw[j:j+1] == b'\r': j += 1
            if raw[j:j+1] == b'\n': j += 1
            if raw[j:j+1] == b'}':
                ends.append(j + 1)
    i += 1

print(f"Found {len(ends)} potential JSON boundaries")
for pos in ends:
    try:
        d = json.loads(raw[:pos].decode('utf-8'))
        print(f"  pos {pos}: valid, nodes={len(d.get('nodes',[]))}, links={len(d.get('links',[]))}")
        remainder = raw[pos:].strip()
        if remainder:
            d2 = json.loads(remainder.decode('utf-8'))
            print(f"  remainder: valid, nodes={len(d2.get('nodes',[]))}, links={len(d2.get('links',[]))}")
            with open('Z:/netops-ai/web/data/topology_state.json', 'w', encoding='utf-8') as f:
                json.dump(d2, f, ensure_ascii=False, indent=2)
            print("FIXED - saved second object")
        else:
            with open('Z:/netops-ai/web/data/topology_state.json', 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            print("FIXED - saved only object")
        break
    except Exception as e:
        print(f"  pos {pos}: invalid - {e}")
else:
    print("Could not auto-fix, resetting to empty")
    with open('Z:/netops-ai/web/data/topology_state.json', 'w', encoding='utf-8') as f:
        json.dump({"nodes": [], "links": [], "version": 1}, f, ensure_ascii=False, indent=2)
