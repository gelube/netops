#!/usr/bin/env python3
"""NetOps AI Web - LLM Function Calling with SSH/Telnet Tools"""
from flask import Flask, request, jsonify, render_template
import json, os, sys
sys.path.insert(0, r'Z:\netops-ai')
from app.llm.config import LLMConfig
from netops_tools import NetOpsTools, get_tools_definition

app = Flask(__name__)
CONFIG_FILE = r'Z:\netops-ai\web\data\llm_config.json'
DEVICES_FILE = r'Z:\netops-ai\web\data\devices.json'

# 初始化工具执行器
tools = NetOpsTools(DEVICES_FILE)

@app.route('/')
def index():
    return render_template('index.html')

# ===== LLM 配置 =====
@app.route('/api/llm/config', methods=['POST', 'GET'])
def handle_llm_config():
    if request.method == 'GET':
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        return jsonify({})
    
    try:
        data = request.json or {}
        
        def clean(s):
            return str(s or '').replace('<', '').replace('>', '').strip()
        
        provider = clean(data.get('provider', 'openai'))
        endpoint = clean(data.get('endpoint', ''))
        api_key = clean(data.get('api_key', ''))
        model = clean(data.get('model', ''))
        
        if endpoint and not endpoint.startswith(('http://', 'https://')):
            endpoint = 'http://' + endpoint
        endpoint = endpoint.rstrip('/')
        
        if not endpoint:
            return jsonify({'success': False, 'message': 'API Endpoint 不能为空'}), 400
        
        llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
        llm_config.save()
        
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'provider': provider, 'endpoint': endpoint, 'api_key': api_key, 'model': model}, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'provider': provider, 'endpoint': endpoint, 'model': model})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/llm/test', methods=['POST'])
def test_llm():
    try:
        data = request.json or {}
        endpoint = str(data.get('endpoint', '')).strip()
        api_key = str(data.get('api_key', '')).strip()
        
        if not endpoint:
            return jsonify({'success': False, 'message': '请填写 API Endpoint'})
        
        import requests
        
        base = endpoint.rstrip('/')
        if '/v1' not in base:
            base = base + '/v1'
        
        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        try:
            resp = requests.get(f'{base}/models', headers=headers, timeout=10)
        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'message': '无法连接，请检查服务是否运行'})
        
        if resp.status_code == 200:
            models_data = resp.json()
            models = [m.get('id', str(m)) for m in models_data.get('data', []) if isinstance(m, dict)]
            return jsonify({'success': True, 'message': f'发现 {len(models)} 个模型', 'models': models[:20]})
        else:
            return jsonify({'success': False, 'message': f'连接失败，HTTP {resp.status_code}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ===== 设备管理 =====
DEVICES_FILE = r'Z:\netops-ai\web\data\devices.json'

def load_devices():
    if os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_devices(devices):
    os.makedirs(os.path.dirname(DEVICES_FILE), exist_ok=True)
    with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)

TOPOLOGY_FILE = r'Z:\netops-ai\web\data\topology_state.json'
TOPOLOGY_TEMPLATES_FILE = r'Z:\netops-ai\web\data\topology_templates.json'

def load_topology_state():
    if os.path.exists(TOPOLOGY_FILE):
        with open(TOPOLOGY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'nodes': [], 'links': [], 'version': 1}

def save_topology_state(state):
    os.makedirs(os.path.dirname(TOPOLOGY_FILE), exist_ok=True)
    with open(TOPOLOGY_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def load_topology_templates():
    if os.path.exists(TOPOLOGY_TEMPLATES_FILE):
        with open(TOPOLOGY_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_topology_templates(templates):
    os.makedirs(os.path.dirname(TOPOLOGY_TEMPLATES_FILE), exist_ok=True)
    with open(TOPOLOGY_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)

@app.route('/api/devices', methods=['GET'])
def get_devices():
    devices = load_devices()
    return jsonify({'devices': devices, 'success': True})

@app.route('/api/topology/state', methods=['GET', 'PATCH'])
def topology_state():
    if request.method == 'GET':
        return jsonify({'success': True, 'state': load_topology_state()})

    try:
        data = request.json or {}
        state = load_topology_state()
        state['nodes'] = data.get('nodes', state.get('nodes', []))
        state['links'] = data.get('links', state.get('links', []))
        state['version'] = int(state.get('version', 1)) + 1
        save_topology_state(state)
        return jsonify({'success': True, 'state': state})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/topology/template/list', methods=['GET'])
def topology_template_list():
    templates = load_topology_templates()
    return jsonify({'success': True, 'templates': [{'name': k, 'updated_at': v.get('updated_at')} for k, v in templates.items()]})

@app.route('/api/topology/template/save', methods=['POST'])
def topology_template_save():
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        state = data.get('state') or load_topology_state()
        if not name:
            return jsonify({'success': False, 'message': '模板名不能为空'})
        templates = load_topology_templates()
        templates[name] = {'state': state, 'updated_at': __import__('datetime').datetime.now().isoformat()}
        save_topology_templates(templates)
        return jsonify({'success': True, 'name': name})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/topology/template/load', methods=['POST'])
def topology_template_load():
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        templates = load_topology_templates()
        tpl = templates.get(name)
        if not tpl:
            return jsonify({'success': False, 'message': '模板不存在'})
        save_topology_state(tpl.get('state', {'nodes': [], 'links': [], 'version': 1}))
        return jsonify({'success': True, 'state': tpl.get('state')})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def _extract_topology_links(text, local_name):
    """从 LLDP/CDP 输出中提取连线（尽量宽松匹配）"""
    import re

    links = []
    if not text:
        return links

    # 常见 detail 输出模式
    patterns = [
        r"(?is)local\s+interface\s*[:：]\s*([^\r\n]+).*?port\s+id\s*\(outgoing\s+port\)\s*[:：]\s*([^\r\n]+).*?system\s+name\s*[:：]\s*([^\r\n]+)",
        r"(?is)interface\s*[:：]\s*([^\r\n]+).*?(?:port\s+id|port\s+description)\s*[:：]\s*([^\r\n]+).*?(?:system\s+name|device\s+id)\s*[:：]\s*([^\r\n]+)",
    ]

    for pat in patterns:
        for m in re.finditer(pat, text):
            local_intf = (m.group(1) or '').strip()
            remote_intf = (m.group(2) or '').strip()
            remote_name = (m.group(3) or '').strip()
            if local_intf and remote_name:
                links.append({
                    'from_name': local_name,
                    'to_name': remote_name,
                    'from_port': local_intf,
                    'to_port': remote_intf or 'unknown',
                    'link_type': 'unknown',
                    'protocol': 'lldp/cdp'
                })

    # H3C 常见输出：LLDP neighbor-information of port 2[GigabitEthernet1/0/1]:
    for m in re.finditer(r"LLDP\s+neighbor-information\s+of\s+port\s+[^\[]*\[([^\]]+)\]", text, re.IGNORECASE):
        local_intf = (m.group(1) or '').strip()
        if local_intf:
            links.append({
                'from_name': local_name,
                'to_name': '',
                'from_port': local_intf,
                'to_port': 'unknown',
                'link_type': 'unknown',
                'protocol': 'lldp'
            })

    # 常见 brief 输出补充（只拿设备名，端口可能缺失）
    if not links:
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if any(x in s.lower() for x in ['device id', 'system name', 'capability', 'holdtime', 'local', 'port']):
                continue
            parts = re.split(r"\s+", s)
            if len(parts) >= 2:
                maybe_name = parts[0]
                maybe_local = parts[1]
                if re.search(r"[a-zA-Z]", maybe_name) and re.search(r"[0-9/]", maybe_local):
                    links.append({
                        'from_name': local_name,
                        'to_name': maybe_name,
                        'from_port': maybe_local,
                        'to_port': 'unknown',
                        'link_type': 'unknown',
                        'protocol': 'lldp/cdp'
                    })

    return links

@app.route('/api/topology/discover', methods=['POST'])
def topology_discover():
    """基于 LLDP/CDP 自动发现拓扑关系"""
    try:
        devices = load_devices()
        links = []
        unknown_peer_ports = {}

        discover_cmds = [
            'display lldp neighbor-information',
            'display lldp neighbor brief',
            'show lldp neighbors detail',
            'show cdp neighbors detail',
            'show lldp neighbors'
        ]

        for d in devices:
            conn_type = d.get('conn_type', 'ssh')
            tool_name = 'telnet_connect' if conn_type == 'telnet' else 'ssh_connect'

            if conn_type == 'ssh' and (not d.get('username') or not d.get('password')):
                continue

            res = tools.execute_tool(tool_name, {'device': d.get('name'), 'commands': discover_cmds})
            if not res.get('success'):
                continue

            text = ''
            for item in res.get('results', []):
                text += '\n' + (item.get('output') or '')

            local_name = d.get('remark') or d.get('name')
            parsed = _extract_topology_links(text, local_name)
            known = [x for x in parsed if x.get('to_name')]
            unknown = [x for x in parsed if not x.get('to_name')]
            links.extend(known)
            if unknown:
                unknown_peer_ports.setdefault(local_name, [])
                unknown_peer_ports[local_name].extend([x.get('from_port') for x in unknown if x.get('from_port')])

        # 去重
        uniq = []
        seen = set()
        for l in links:
            key = (l['from_name'], l['to_name'], l.get('from_port', ''), l.get('to_port', ''))
            rkey = (l['to_name'], l['from_name'], l.get('to_port', ''), l.get('from_port', ''))
            if key in seen or rkey in seen:
                continue
            seen.add(key)
            uniq.append(l)

        # 兜底：双设备实验环境常出现只识别到本端口、无对端名称。
        if not uniq and len(devices) == 2:
            a = devices[0].get('remark') or devices[0].get('name')
            b = devices[1].get('remark') or devices[1].get('name')
            a_ports = list(dict.fromkeys(unknown_peer_ports.get(a) or []))
            b_ports = list(dict.fromkeys(unknown_peer_ports.get(b) or []))

            if not a_ports:
                a_ports = ['unknown']
            if not b_ports:
                b_ports = ['unknown']

            # 按序配对，尽量保留多条并行物理链路
            pair_count = max(len(a_ports), len(b_ports))
            for i in range(pair_count):
                pa = a_ports[i] if i < len(a_ports) else a_ports[-1]
                pb = b_ports[i] if i < len(b_ports) else b_ports[-1]
                uniq.append({
                    'from_name': a,
                    'to_name': b,
                    'from_port': pa,
                    'to_port': pb,
                    'link_type': 'unknown',
                    'protocol': 'lldp-heuristic'
                })

        # 简单聚合识别：同一设备对出现 2 条及以上并行链路，标记为端口聚合候选。
        pair_counter = {}
        for l in uniq:
            pkey = tuple(sorted([l.get('from_name', ''), l.get('to_name', '')]))
            pair_counter[pkey] = pair_counter.get(pkey, 0) + 1
        for l in uniq:
            pkey = tuple(sorted([l.get('from_name', ''), l.get('to_name', '')]))
            if pair_counter.get(pkey, 0) >= 2 and (l.get('link_type') in [None, '', 'unknown']):
                l['link_type'] = 'port-channel-lacp'

        state = load_topology_state()
        state['nodes'] = [
            {
                'id': d.get('id'),
                'name': d.get('name'),
                'remark': d.get('remark', ''),
                'ip': d.get('ip') or d.get('serial_port') or 'N/A',
                'deviceType': d.get('device_type', 'unknown')
            } for d in devices
        ]
        def find_id_by_name(name):
            for d in devices:
                if d.get('remark') == name or d.get('name') == name:
                    return d.get('id')
            return None

        state['links'] = [
            {
                'id': f"link_{i+1}",
                'from': find_id_by_name(l['from_name']),
                'to': find_id_by_name(l['to_name']),
                'from_name': l['from_name'],
                'to_name': l['to_name'],
                'from_port': l.get('from_port', 'unknown'),
                'to_port': l.get('to_port', 'unknown'),
                'link_type': l.get('link_type', 'unknown'),
                'protocol': l.get('protocol', 'lldp/cdp')
            } for i, l in enumerate(uniq)
        ]
        state['version'] = int(state.get('version', 1)) + 1
        save_topology_state(state)

        return jsonify({'success': True, 'state': state, 'discovered_links': len(state['links'])})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/topology/apply', methods=['POST'])
def topology_apply():
    """将拓扑连线类型转为配置命令并通过 LLM/工具执行（基础版）"""
    try:
        data = request.json or {}
        state = data.get('state') or load_topology_state()
        devices = load_devices()

        results = []
        for l in state.get('links', []):
            link_type = (l.get('link_type') or 'unknown').lower()
            src_name = l.get('from_name', '')
            dst_name = l.get('to_name', '')

            src_dev = next((d for d in devices if d.get('remark') == src_name or d.get('name') == src_name), None)
            dst_dev = next((d for d in devices if d.get('remark') == dst_name or d.get('name') == dst_name), None)
            if not src_dev and not dst_dev:
                continue

            cmds = []
            if link_type == 'trunk':
                cmds = [f"interface {l.get('from_port','')}", 'port link-type trunk']
            elif link_type.startswith('port-channel'):
                cmds = [f"interface {l.get('from_port','')}", 'link-aggregation mode dynamic' if 'lacp' in link_type else 'link-aggregation mode static']
            elif link_type == 'access':
                cmds = [f"interface {l.get('from_port','')}", 'port link-type access']
            elif link_type == 'l3-p2p':
                cmds = [f"interface {l.get('from_port','')}", 'undo portswitch']

            if not cmds:
                continue

            for dev in [src_dev, dst_dev]:
                if not dev:
                    continue
                tool_name = 'telnet_connect' if dev.get('conn_type') == 'telnet' else 'ssh_connect'
                r = tools.execute_tool(tool_name, {'device': dev.get('name'), 'commands': cmds})
                results.append({'device': dev.get('name'), 'link': f"{src_name}->{dst_name}", 'link_type': link_type, 'result': r})

        return jsonify({'success': True, 'executed': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/device/add', methods=['POST'])
def add_device():
    """添加设备并自动识别"""
    try:
        data = request.json or {}
        
        name = data.get('name', '').strip()
        conn_type = data.get('conn_type', 'ssh')
        selected_device_type = (data.get('device_type', '') or '').strip()
        username = data.get('username', '')
        password = data.get('password', '')
        remark = (data.get('remark', '') or '').strip()
        vendor = (data.get('vendor', '') or '').strip().lower() or 'auto'
        
        devices = load_devices()
        device_id = (data.get('device_id') or '').strip()

        # 精确更新：优先按 device_id 更新，避免前端编辑基础信息时因连接参数导致保存失败。
        if device_id:
            target = next((x for x in devices if x.get('id') == device_id), None)
            if not target:
                return jsonify({'success': False, 'message': '设备不存在'})

            if data.get('basic_only'):
                target['remark'] = remark
                if selected_device_type:
                    target['device_type'] = selected_device_type
                save_devices(devices)
                return jsonify({'success': True, 'message': '设备已更新', 'device': target})

            target.update({
                'conn_type': conn_type,
                'remark': remark,
                'device_type': selected_device_type or target.get('device_type', 'unknown'),
                'username': username,
                'password': password,
            })
            if conn_type == 'serial':
                target['serial_port'] = data.get('serial_port', '').strip()
                target['baud'] = data.get('baud', 115200)
                target.pop('ip', None)
                target.pop('port', None)
            else:
                target['ip'] = data.get('ip', '').strip()
                target['port'] = int(data.get('port', 22 if conn_type == 'ssh' else 23))
                target.pop('serial_port', None)

            save_devices(devices)
            return jsonify({'success': True, 'message': '设备已更新', 'device': target})

        if conn_type == 'serial':
            serial_port = data.get('serial_port', '').strip()
            baud = data.get('baud', 115200)
            if not serial_port:
                return jsonify({'success': False, 'message': '串口设备不能为空'})
            
            for d in devices:
                if d.get('serial_port') == serial_port:
                    # 已存在则更新，避免“无法保存”
                    d.update({
                        'name': name or d.get('name') or f'serial-{serial_port}',
                        'conn_type': conn_type,
                        'serial_port': serial_port,
                        'baud': baud,
                        'remark': remark,
                        'device_type': selected_device_type or d.get('device_type', 'unknown'),
                        'username': username,
                        'password': password,
                    })
                    save_devices(devices)
                    return jsonify({'success': True, 'message': '设备已更新', 'device': d})
            
            device = {
                'id': f'dev_{len(devices)+1}',
                'name': name or f'serial-{serial_port}',
                'conn_type': conn_type,
                'serial_port': serial_port,
                'baud': baud,
                'remark': remark,
                'username': username,
                'password': password,
                'vendor': vendor,
                'device_type': 'unknown',
                'model': 'unknown',
                'os_version': 'unknown'
            }
        else:
            ip = data.get('ip', '').strip()
            port = int(data.get('port', 22 if conn_type == 'ssh' else 23))
            
            if not ip:
                return jsonify({'success': False, 'message': '设备 IP 不能为空'})
            
            for d in devices:
                if d.get('ip') == ip and d.get('port') == port:
                    # 已存在则更新，避免“无法保存”
                    d.update({
                        'name': name or d.get('name') or f'{conn_type}-{ip}:{port}',
                        'conn_type': conn_type,
                        'ip': ip,
                        'port': port,
                        'remark': remark,
                        'device_type': selected_device_type or d.get('device_type', 'unknown'),
                        'username': username,
                        'password': password,
                    })
                    # vendor 支持自动识别，也允许保留已有识别结果
                    if vendor and vendor != 'auto':
                        d['vendor'] = vendor
                    if conn_type != 'serial':
                        try:
                            device_info = identify_device(d)
                            if device_info:
                                d.update(device_info)
                                if d.get('conn_type') == 'telnet' and d.get('ip') in ['127.0.0.1', 'localhost'] and d.get('vendor') == 'unknown':
                                    d.update({'vendor': 'h3c', 'device_type': 'switch'})
                            elif d.get('conn_type') == 'telnet' and d.get('ip') in ['127.0.0.1', 'localhost']:
                                # 本地 Telnet 测试环境兜底
                                d.update({'vendor': 'h3c', 'device_type': 'switch'})
                        except Exception as e:
                            print(f"设备识别失败: {e}")
                            if d.get('conn_type') == 'telnet' and d.get('ip') in ['127.0.0.1', 'localhost']:
                                d.update({'vendor': 'h3c', 'device_type': 'switch'})
                    save_devices(devices)
                    return jsonify({'success': True, 'message': '设备已更新', 'device': d})
            
            device = {
                'id': f'dev_{len(devices)+1}',
                'name': name or f'{conn_type}-{ip}:{port}',
                'ip': ip,
                'port': port,
                'conn_type': conn_type,
                'remark': remark,
                'username': username,
                'password': password,
                'vendor': vendor,
                'device_type': selected_device_type or 'unknown',
                'model': 'unknown',
                'os_version': 'unknown'
            }
        
        # 尝试自动识别设备信息（厂商/型号/系统版本/设备名）
        if conn_type != 'serial':
            try:
                device_info = identify_device(device)
                if device_info:
                    device.update(device_info)
                    if device.get('conn_type') == 'telnet' and device.get('ip') in ['127.0.0.1', 'localhost'] and device.get('vendor') == 'unknown':
                        device.update({'vendor': 'h3c', 'device_type': 'switch'})
                elif device.get('conn_type') == 'telnet' and device.get('ip') in ['127.0.0.1', 'localhost']:
                    # 本地 Telnet 测试环境兜底
                    device.update({'vendor': 'h3c', 'device_type': 'switch'})
            except Exception as e:
                print(f"设备识别失败: {e}")
                if device.get('conn_type') == 'telnet' and device.get('ip') in ['127.0.0.1', 'localhost']:
                    device.update({'vendor': 'h3c', 'device_type': 'switch'})
        
        # 用户手选了设备类型时，优先使用用户选择。
        if selected_device_type and selected_device_type != 'unknown':
            device['device_type'] = selected_device_type

        devices.append(device)
        save_devices(devices)
        
        return jsonify({'success': True, 'device': device})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def identify_device(device):
    """通过 SSH/Telnet 自动识别设备信息（厂商/型号/系统版本/名称）"""
    ip = device.get('ip')
    port = device.get('port', 22)
    username = device.get('username', '')
    password = device.get('password', '')
    conn_type = device.get('conn_type', 'ssh')

    if not ip:
        return None

    try:
        from netmiko import ConnectHandler
        import re

        if conn_type == 'telnet':
            # 免凭证 Telnet 测试机也要支持自动识别
            conn_params = {
                'device_type': 'generic_termserver_telnet' if (not username and not password) else 'generic_telnet',
                'host': ip,
                'port': port,
                'username': username or '',
                'password': password or '',
                'timeout': 3,
            }
        else:
            # SSH 场景仍要求凭证
            if not username or not password:
                return None
            conn_params = {
                'device_type': 'huawei',
                'host': ip,
                'port': port,
                'username': username,
                'password': password,
                'timeout': 3,
            }

        with ConnectHandler(**conn_params) as conn:
            output_parts = []

            # 先抓一次提示符/欢迎信息，很多 Telnet 模拟器在这里就能看出厂商（如 <H3C>）。
            try:
                banner = conn.send_command_timing('\n', read_timeout=2) or ''
                if banner.strip():
                    output_parts.append(banner)
            except Exception:
                pass

            # 再走常见命令，成功拿到输出就不再继续，缩短保存等待。
            for cmd in ['display version', 'show version']:
                try:
                    if conn_type == 'telnet':
                        out = conn.send_command_timing(cmd, read_timeout=4) or ''
                    else:
                        out = conn.send_command(cmd, read_timeout=4) or ''
                    output_parts.append(out)
                    if out.strip() and ('H3C' in out.upper() or 'HUAWEI' in out.upper() or 'CISCO' in out.upper() or 'VRP' in out.upper()):
                        break
                except Exception:
                    pass

        output = '\n'.join(output_parts)
        if not output.strip():
            return None

        text = output.upper()
        detected_vendor = 'unknown'
        if 'H3C' in text or '<H3C>' in text or 'PRESS ENTER TO GET STARTED' in text:
            detected_vendor = 'h3c'
        elif 'HUAWEI' in text or 'VRP' in text:
            detected_vendor = 'huawei'
        elif 'CISCO' in text or 'IOS' in text:
            detected_vendor = 'cisco'

        # 本地 Telnet 模拟器兜底：127.0.0.1 常见为 H3C 实验环境
        if detected_vendor == 'unknown' and conn_type == 'telnet' and ip in ['127.0.0.1', 'localhost']:
            detected_vendor = 'h3c'

        info = {
            'vendor': detected_vendor,
            'device_type': 'switch',
            'model': 'unknown',
            'os_version': 'unknown',
        }

        model_match = re.search(r'(H3C|HUAWEI|CISCO)\s+([A-Z0-9\-_/\.]+)', output, re.IGNORECASE)
        if model_match:
            info['model'] = model_match.group(2)

        version_match = re.search(r'(?:Version|Software),?\s*([A-Z0-9\(\)\._\-]+)', output, re.IGNORECASE)
        if version_match:
            info['os_version'] = version_match.group(1)

        # 名称优先取设备提示符，例如 <H3C> / [Huawei] / Router#
        prompt_name = None
        prompt_patterns = [
            r'<\s*([^<>\r\n\s]+)\s*>',
            r'\[\s*([^\[\]\r\n\s]+)\s*\]',
            r'\n\s*([A-Za-z0-9._-]{2,})\s*[#>]'
        ]
        for pat in prompt_patterns:
            m = re.search(pat, output)
            if m:
                prompt_name = m.group(1)
                break

        if prompt_name:
            info['name'] = prompt_name
        elif detected_vendor != 'unknown':
            info['name'] = detected_vendor.upper()
        return info

    except Exception as e:
        print(f"连接设备失败: {e}")
        return None

@app.route('/api/discover', methods=['POST'])
def discover():
    devices = load_devices()
    return jsonify({'success': True, 'devices': devices})

# ===== AI 对话与执行 =====
@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 对话 - 支持多设备操作和上下文记忆"""
    try:
        data = request.json or {}
        message = data.get('message', '')
        context = data.get('context', {})  # 前端传来的上下文
        selected_device = context.get('selected_device')  # 用户选中的设备
        
        if not message:
            return jsonify({'success': False, 'message': '消息不能为空'})
        
        # 加载 LLM 配置
        if not os.path.exists(CONFIG_FILE):
            return jsonify({'success': False, 'message': '请先配置 LLM'})
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        endpoint = config.get('endpoint', '')
        api_key = config.get('api_key', '')
        model = config.get('model', '')
        
        if not endpoint or not model:
            return jsonify({'success': False, 'message': '请先配置 LLM'})
        
        import requests
        
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        base = endpoint.rstrip('/')
        if '/v1' not in base:
            base = base + '/v1'
        
        # 获取设备列表
        devices = load_devices()
        device_info = "\n".join([
            f"- {d['name']} (备注: {d.get('remark', '无')}, IP: {d.get('ip')}, {d.get('conn_type', 'ssh')}, {d.get('vendor', 'unknown')}, 型号: {d.get('model', 'unknown')})"
            for d in devices
        ]) if devices else "暂无设备"
        
        # 如果有选中的设备，高亮显示
        selected_device_info = ""
        if selected_device:
            for d in devices:
                if d.get('name') == selected_device or d.get('remark') == selected_device:
                    selected_device_info = f"""
【当前选中设备】: {d['name']}
  - 备注: {d.get('remark', '无')}
  - IP: {d.get('ip')}
  - 厂商: {d.get('vendor')}
  - 型号: {d.get('model')}
  - 连接方式: {d.get('conn_type')}
  
用户的所有操作都针对这个设备，除非明确指定其他设备。"""
                    break
        
        topology = load_topology_state()
        topo_links = topology.get('links', [])
        topo_summary = "\n".join([
            f"- {l.get('from_name') or l.get('from')} -> {l.get('to_name') or l.get('to')} ({l.get('link_type','unknown')})"
            for l in topo_links
        ]) if topo_links else "暂无拓扑连线"

        # 构建系统提示
        system_prompt = f"""你是 NetOps AI 网络工程师助手。你可以直接操作网络设备。

【设备列表】:
{device_info}
{selected_device_info}

【当前拓扑连线】:
{topo_summary}

【重要规则】：
1. 如果用户选中了设备（上面【当前选中设备】），所有操作都针对这个设备
2. 如果用户说"查看 VLAN"、"查看路由"等，直接操作选中的设备，不要问是哪个设备
3. 如果用户明确指定设备名/备注，操作指定的设备
4. 如果用户说"所有设备"、"批量"，才操作所有设备
5. 你必须调用工具执行操作，不要只是回复文字！
6. 不要问用户"是哪个设备"，直接执行！"""

        # 第一次调用 LLM
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': message}
        ]
        
        resp = requests.post(f'{base}/chat/completions', headers=headers, json={
            'model': model,
            'messages': messages,
            'tools': get_tools_definition(),
            'tool_choice': 'auto',
            'max_tokens': 2000
        }, timeout=60)
        
        if resp.status_code != 200:
            return jsonify({'success': False, 'message': f'LLM 错误: {resp.status_code}'})
        
        result = resp.json()
        choice = result.get('choices', [{}])[0]
        tool_calls = choice.get('message', {}).get('tool_calls', [])
        
        if tool_calls:
            tool_results = []
            all_commands = []
            
            for tool_call in tool_calls:
                tool_name = tool_call.get('function', {}).get('name', '')
                arguments = json.loads(tool_call.get('function', {}).get('arguments', '{}'))
                
                if tool_name in ['ssh_connect', 'telnet_connect']:
                    # 多设备目标解析：支持“所有/全部/批量”以及在句子中直接点名多台设备。
                    all_kw = ['所有', '全部', '批量', 'all devices', 'all']
                    wants_all = any(k in message.lower() for k in [x.lower() for x in all_kw])

                    arg_device = (arguments.get('device') or '').strip()
                    matched = []

                    # 1) 备注优先：用户消息里出现备注时，优先按备注命中。
                    for d in devices:
                        dr = d.get('remark', '')
                        if dr and dr in message:
                            matched.append(d)

                    # 2) 再按参数设备名匹配
                    if not matched and arg_device and arg_device not in ['all', 'ALL', '所有', '全部']:
                        matched = [d for d in devices if d.get('name') == arg_device or d.get('ip') == arg_device or d.get('remark') == arg_device]

                    # 3) 再按用户文本中出现的设备名/IP匹配多台
                    if not matched:
                        for d in devices:
                            dn = d.get('name', '')
                            dip = d.get('ip', '')
                            dr = d.get('remark', '')
                            if (dn and dn in message) or (dip and dip in message) or (dr and dr in message):
                                matched.append(d)

                    # 3) 全量/选中/默认兜底
                    if wants_all:
                        matched = devices[:]
                    elif not matched and selected_device:
                        matched = [d for d in devices if d.get('name') == selected_device]
                    elif not matched and devices:
                        matched = [devices[0]]

                    # 去重
                    uniq = []
                    seen = set()
                    for d in matched:
                        did = d.get('id') or d.get('name')
                        if did not in seen:
                            seen.add(did)
                            uniq.append(d)
                    matched = uniq

                    # 批量执行：按每台设备连接方式自动选 ssh/telnet
                    for d in matched:
                        conn_type = d.get('conn_type', 'ssh')
                        if conn_type == 'ssh' and (not d.get('username') or not d.get('password')):
                            tool_result = {'success': False, 'error': f"设备 {d.get('name')} 缺少 SSH 凭证"}
                            actual_tool = 'ssh_connect'
                        else:
                            actual_tool = 'telnet_connect' if conn_type == 'telnet' else 'ssh_connect'
                            per_args = dict(arguments)
                            per_args['device'] = d.get('name')
                            tool_result = tools.execute_tool(actual_tool, per_args)

                        tool_results.append({
                            'tool_call_id': tool_call.get('id', ''),
                            'role': 'tool',
                            'name': actual_tool,
                            'content': json.dumps(tool_result, ensure_ascii=False)
                        })

                        if tool_result.get('results'):
                            all_commands.extend([r.get('command') for r in tool_result['results']])

                    continue

                # 非设备连接类工具，按原路径执行
                tool_result = tools.execute_tool(tool_name, arguments)
                tool_results.append({
                    'tool_call_id': tool_call.get('id', ''),
                    'role': 'tool',
                    'name': tool_name,
                    'content': json.dumps(tool_result, ensure_ascii=False)
                })

                if tool_result.get('results'):
                    all_commands.extend([r.get('command') for r in tool_result['results']])
            
            # 发回 LLM 生成最终回复
            messages.append(choice['message'])
            for tr in tool_results:
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tr['tool_call_id'],
                    'content': tr['content']
                })
            
            resp2 = requests.post(f'{base}/chat/completions', headers=headers, json={
                'model': model,
                'messages': messages,
                'max_tokens': 2000
            }, timeout=60)
            
            # 构建回复
            response_parts = []
            
            # 1. 如果工具执行成功且有结果
            for tr in tool_results:
                result_data = json.loads(tr['content'])
                if result_data.get('success') and result_data.get('results'):
                    for r in result_data['results']:
                        response_parts.append(f"命令: {r['command']}")
                        response_parts.append(f"输出:\n{r['output'][:2000]}")
                        response_parts.append("---")
                elif not result_data.get('success'):
                    response_parts.append(f"❌ 执行失败: {result_data.get('error', result_data.get('message', '未知错误'))}")
            
            # 2. LLM 的解读
            if resp2.status_code == 200:
                llm_reply = resp2.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                # 清理工具请求格式
                if '[TOOL_REQUEST]' not in llm_reply:
                    response_parts.insert(0, llm_reply)
            
            final_reply = '\n'.join(response_parts) if response_parts else '操作完成'
            
            return jsonify({
                'success': True,
                'response': final_reply,
                'executed': True,
                'tool_calls': [
                    {'name': tc.get('function', {}).get('name'), 'arguments': json.loads(tc.get('function', {}).get('arguments', '{}'))}
                    for tc in tool_calls
                ],
                'tool_results': [json.loads(tr['content']) for tr in tool_results],
                'commands': all_commands
            })
        
        else:
            reply = choice.get('message', {}).get('content', '无响应')
            return jsonify({'success': True, 'response': reply})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

def handle_local_intent(message):
    """处理本地操作意图 - 类似 OpenClaw 的工具调用"""
    import subprocess
    import os
    
    workdir = r'Z:\netops-ai'
    
    # 查看文件
    if '查看文件' in message or '读取文件' in message or 'cat ' in message:
        import re
        match = re.search(r'(?:文件|cat)\s*[:\s]*(\S+)', message)
        if match:
            path = match.group(1).strip('"\'')
            if not os.path.isabs(path):
                path = os.path.join(workdir, path)
            
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(5000)  # 限制大小
                return {
                    'type': 'file_read',
                    'path': path,
                    'content': content,
                    'summary': f'已读取文件: {path}'
                }
    
    # 列出目录
    if '列出' in message and ('目录' in message or '文件' in message or 'ls' in message):
        import re
        match = re.search(r'(?:目录|ls)[:\s]*(\S*)', message)
        path = match.group(1) if match else workdir
        if not os.path.isabs(path):
            path = os.path.join(workdir, path)
        
        if os.path.isdir(path):
            files = os.listdir(path)[:50]
            return {
                'type': 'list_dir',
                'path': path,
                'files': files,
                'summary': f'目录 {path} 包含 {len(files)} 个文件:\n' + '\n'.join(files[:20])
            }
    
    # 执行命令
    if '执行' in message or '运行' in message:
        import re
        match = re.search(r'(?:执行|运行)[:\s]+(.+)', message)
        if match:
            cmd = match.group(1).strip()
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=workdir
                )
                return {
                    'type': 'exec',
                    'command': cmd,
                    'stdout': result.stdout[:3000],
                    'stderr': result.stderr[:500],
                    'success': result.returncode == 0,
                    'summary': f'执行: {cmd}\n{result.stdout[:1000]}'
                }
            except Exception as e:
                return {'type': 'exec', 'success': False, 'error': str(e)}
    
    # 查看配置
    if '查看配置' in message or '当前配置' in message:
        config_file = os.path.join(workdir, 'web', 'data', 'llm_config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return {
                    'type': 'config',
                    'summary': f'当前 LLM 配置:\n{f.read()}'
                }
    
    return None


def execute_commands(device, commands):
    """执行设备命令 - 支持 SSH/Telnet/串口"""
    ip = device.get('ip')
    port = device.get('port', 22)
    username = device.get('username', '')
    password = device.get('password', '')
    vendor = device.get('vendor', 'huawei')
    conn_type = device.get('conn_type', 'ssh')
    
    # Telnet 模拟器场景允许空凭证；SSH/串口仍要求凭证。
    if conn_type != 'telnet' and (not username or not password):
        return {'success': False, 'message': '设备缺少登录凭证'}
    
    results = []
    
    try:
        if conn_type == 'serial':
            # 串口连接
            import serial
            import time
            
            serial_port = device.get('serial_port', 'COM1')
            baud = device.get('baud', 9600)
            
            ser = serial.Serial(
                port=serial_port,
                baudrate=baud,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=5
            )
            
            time.sleep(1)  # 等待连接稳定
            
            # 发送回车唤醒
            ser.write(b'\r\n')
            time.sleep(0.5)
            
            # 读取提示
            output = ser.read(4096).decode('utf-8', errors='ignore')
            
            # 如果需要登录
            if 'Username' in output or 'login' in output.lower():
                ser.write((username + '\r\n').encode())
                time.sleep(0.5)
                output += ser.read(4096).decode('utf-8', errors='ignore')
            
            if 'Password' in output or 'password' in output.lower():
                ser.write((password + '\r\n').encode())
                time.sleep(0.5)
                output += ser.read(4096).decode('utf-8', errors='ignore')
            
            # 执行命令
            for cmd in commands:
                ser.write((cmd + '\r\n').encode())
                time.sleep(1)
                cmd_output = ser.read(8192).decode('utf-8', errors='ignore')
                results.append({'command': cmd, 'output': cmd_output})
            
            ser.close()
            
        else:
            # SSH/Telnet 连接
            from netmiko import ConnectHandler
            
            if conn_type == 'telnet':
                telnet_type_map = {
                    'huawei': 'huawei_telnet',
                    'h3c': 'hp_comware_telnet',
                    'cisco': 'cisco_ios_telnet',
                    'juniper': 'juniper_junos_telnet',
                }
                device_type = telnet_type_map.get(vendor, 'generic_telnet')
                if not username and not password:
                    device_type = 'generic_termserver_telnet'
            else:
                device_type_map = {
                    'huawei': 'huawei',
                    'h3c': 'huawei',
                    'cisco': 'cisco_ios',
                    'juniper': 'juniper_junos'
                }
                device_type = device_type_map.get(vendor, 'huawei')
            
            device_params = {
                'device_type': device_type,
                'host': ip,
                'port': port,
                'username': username,
                'password': password,
                'timeout': 30,
            }
            
            with ConnectHandler(**device_params) as conn:
                for cmd in commands:
                    if conn_type == 'telnet':
                        output = conn.send_command_timing(cmd, read_timeout=30)
                    else:
                        output = conn.send_command(cmd, read_timeout=30)
                    results.append({'command': cmd, 'output': output})
        
        return {'success': True, 'commands': commands, 'results': results}
    
    except ImportError as e:
        missing = 'pyserial' if conn_type == 'serial' else 'netmiko'
        return {'success': False, 'message': f'{missing} 未安装，执行: pip install {missing}'}
    except Exception as e:
        return {'success': False, 'message': str(e)}

@app.route('/api/template/list', methods=['GET'])
def get_templates():
    templates = [
        {'name': 'VLAN创建', 'desc': '批量创建VLAN'},
        {'name': '接口配置', 'desc': '配置接口模式和VLAN'},
        {'name': '静态路由', 'desc': '配置静态路由'},
    ]
    return jsonify({'success': True, 'templates': templates})

# ===== 本地执行能力（类似 OpenClaw）=====
@app.route('/api/exec', methods=['POST'])
def api_exec():
    """执行本地命令 - 类似 OpenClaw 的 exec 工具"""
    try:
        data = request.json or {}
        cmd = data.get('command', '')
        
        if not cmd:
            return jsonify({'success': False, 'message': '命令不能为空'})
        
        # 安全检查：禁止危险命令
        dangerous = ['rm -rf', 'del /', 'format', 'mkfs', 'dd if=']
        if any(d in cmd for d in dangerous):
            return jsonify({'success': False, 'message': '禁止执行危险命令'})
        
        import subprocess
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '命令执行超时'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/file/read', methods=['POST'])
def api_file_read():
    """读取本地文件 - 类似 OpenClaw 的 read 工具"""
    try:
        data = request.json or {}
        path = data.get('path', '')
        
        if not path:
            return jsonify({'success': False, 'message': '路径不能为空'})
        
        # 安全检查：只允许读取工作目录下的文件
        import os
        workdir = r'Z:\netops-ai'
        abs_path = os.path.abspath(path)
        
        if not abs_path.startswith(workdir):
            return jsonify({'success': False, 'message': '只能读取项目目录下的文件'})
        
        if not os.path.exists(abs_path):
            return jsonify({'success': False, 'message': '文件不存在'})
        
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/file/write', methods=['POST'])
def api_file_write():
    """写入本地文件 - 类似 OpenClaw 的 write 工具"""
    try:
        data = request.json or {}
        path = data.get('path', '')
        content = data.get('content', '')
        
        if not path:
            return jsonify({'success': False, 'message': '路径不能为空'})
        
        # 安全检查
        import os
        workdir = r'Z:\netops-ai'
        abs_path = os.path.abspath(path)
        
        if not abs_path.startswith(workdir):
            return jsonify({'success': False, 'message': '只能写入项目目录'})
        
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({'success': True, 'path': abs_path})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/device/delete', methods=['POST'])
def delete_device():
    """删除设备"""
    try:
        data = request.json or {}
        device_id = data.get('device_id') or data.get('id')
        device_name = data.get('name')
        
        if not device_id and not device_name:
            return jsonify({'success': False, 'message': '请指定要删除的设备'})
        
        devices = load_devices()
        original_count = len(devices)
        
        if device_id:
            devices = [d for d in devices if d['id'] != device_id]
        else:
            devices = [d for d in devices if d['name'] != device_name]
        
        if len(devices) == original_count:
            return jsonify({'success': False, 'message': '设备不存在'})
        
        save_devices(devices)
        
        return jsonify({
            'success': True, 
            'message': '设备已删除',
            'remaining': len(devices)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
