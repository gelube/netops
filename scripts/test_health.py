import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = 'http://127.0.0.1:5000'
for ep in ['/api/health', '/api/devices', '/api/topology/state']:
    try:
        r = requests.get(f'{BASE}{ep}', timeout=5)
        print(f'{ep}: {r.status_code}')
    except Exception as e:
        print(f'{ep}: ERROR {e}')
try:
    r = requests.post(f'{BASE}/api/topology/discover', json={}, timeout=120)
    d = r.json()
    print(f'discover: {r.status_code} links={d.get("links")} nodes={d.get("nodes")}')
except Exception as e:
    print(f'discover: ERROR {e}')
