import json
with open(r'Z:\netops-ai\web\data\devices.json', 'r', encoding='utf-8') as f:
    devs = json.load(f)
for d in devs:
    n = d.get('name', '')
    r = d.get('remark', '')
    print(f'name=[{n}] remark=[{r}] id=[{d.get("id","")}]')
