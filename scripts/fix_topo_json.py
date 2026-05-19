import json, re, sys

with open('Z:/netops-ai/web/data/topology_state.json', 'r', encoding='utf-8') as f:
    txt = f.read()

matches = list(re.finditer(r'\}\s*\}', txt))
for i, m in enumerate(matches):
    pos = m.end()
    try:
        data = json.loads(txt[:pos])
        print("First valid at pos", pos, "nodes:", len(data.get('nodes', [])), "links:", len(data.get('links', [])))
        try:
            data2 = json.loads(txt[pos:])
            print("Second valid, nodes:", len(data2.get('nodes', [])), "links:", len(data2.get('links', [])))
            with open('Z:/netops-ai/web/data/topology_state.json', 'w', encoding='utf-8') as f:
                json.dump(data2, f, ensure_ascii=False, indent=2)
            print("Saved second (newer) object")
        except:
            with open('Z:/netops-ai/web/data/topology_state.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("Saved first object (no valid second)")
        break
    except:
        pass
