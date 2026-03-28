import sys
import requests

sys.path.insert(0, r'Z:\netops-ai\web')
from netops_tools import NetOpsTools

devs = requests.get('http://127.0.0.1:5001/api/devices', timeout=10).json().get('devices', [])
print('devices', [(d.get('name'), d.get('ip'), d.get('port'), d.get('conn_type')) for d in devs])

tools = NetOpsTools(r'Z:\netops-ai\web\data\devices.json')
cmds = [
    'display lldp neighbor-information',
    'display lldp neighbor brief',
    'show lldp neighbors detail',
    'show cdp neighbors detail',
    'show lldp neighbors',
]

for d in devs:
    tool = 'telnet_connect' if d.get('conn_type') == 'telnet' else 'ssh_connect'
    print('\n===', d.get('name'), tool, '===')
    r = tools.execute_tool(tool, {'device': d.get('name'), 'commands': cmds})
    print('success', r.get('success'), 'error', r.get('error'))
    for item in (r.get('results') or []):
        out = (item.get('output') or '').replace('\r', '')
        print('---', item.get('command'), '---')
        print(out[:800])
