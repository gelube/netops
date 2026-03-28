#!/usr/bin/env python3
"""添加 /api/devices 接口"""

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 在 LLM 配置 API 后面添加 devices 接口
api_code = '''
# 设备列表 API
@app.route('/api/devices', methods=['GET'])
def get_devices():
    """获取已保存的设备列表"""
    global current_topology, device_ports
    
    if not current_topology or not current_topology.devices:
        return jsonify({'success': True, 'devices': [], 'count': 0})
    
    devices = []
    for dev in current_topology.devices:
        devices.append({
            'id': dev.id,
            'name': dev.name,
            'ip': dev.ip,
            'vendor': dev.vendor.value,
            'model': dev.model,
            'port': device_ports.get(dev.ip, 23)
        })
    
    return jsonify({'success': True, 'devices': devices, 'count': len(devices)})

'''

# 找到 LLM 配置 API 的结尾
import re
pattern = r"(@app\.route\('/api/llm/test'.*?return jsonify\(\{'success': True, 'provider':)"
match = re.search(pattern, content, re.DOTALL)

if match:
    # 在 LLM test API 后面插入
    end_pos = match.end()
    # 找到这一行的结尾
    newline_pos = content.find('\n', end_pos)
    if newline_pos > 0:
        content = content[:newline_pos+1] + api_code + content[newline_pos+1:]
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Added /api/devices endpoint!")
    else:
        print("❌ Could not find insertion point")
else:
    print("❌ Could not find LLM test API")
