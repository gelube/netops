import requests

print('=== 测试改进 ===')

# 1. 测试 LLM 识别选中设备
print('\n1. 测试 LLM 识别选中设备:')
r = requests.post('http://localhost:5001/api/chat', json={
    'message': '查看 VLAN',
    'context': {'selected_device': 'SW-Test'}
})
d = r.json()
print('   executed:', d.get('executed'))
print('   tool_calls:', [tc.get('name') for tc in d.get('tool_calls', [])])
if d.get('tool_results'):
    tr = d['tool_results'][0]
    print('   device:', tr.get('device'))
    print('   success:', tr.get('success'))
print('   response:', d.get('response', '')[:150])

# 2. 测试不指定设备
print('\n2. 测试不指定设备（应该用选中的）:')
r = requests.post('http://localhost:5001/api/chat', json={
    'message': '查看接口',
    'context': {'selected_device': 'SW-Test'}
})
d = r.json()
print('   executed:', d.get('executed'))
if d.get('tool_results'):
    print('   device:', d['tool_results'][0].get('device'))