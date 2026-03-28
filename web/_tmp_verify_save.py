import requests, time

time.sleep(1)

ds = requests.get('http://127.0.0.1:5001/api/devices', timeout=5).json().get('devices', [])
d = ds[0]
p = {
    'device_id': d['id'],
    'basic_only': True,
    'conn_type': d.get('conn_type'),
    'device_type': d.get('device_type', 'unknown'),
    'remark': '上海核心',
    'username': d.get('username', ''),
    'password': d.get('password', ''),
}
r = requests.post('http://127.0.0.1:5001/api/device/add', json=p, timeout=10)
print(r.status_code, r.json().get('success'), r.json().get('message'))

html = requests.get('http://127.0.0.1:5001/', timeout=5).text
print('btn-edit:', 'id="btn-conn-edit"' in html)
