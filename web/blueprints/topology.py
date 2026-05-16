#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拓扑蓝图 - 拓扑发现、渲染、模板管理
"""
from flask import Blueprint, request, jsonify
import json, os, re, time

topology_bp = Blueprint('topology', __name__)

# 这些在 register 时由 init_app 注入
_data_dir = ''
_devices_file = ''

def init_topology_blueprint(data_dir, devices_file):
    global _data_dir, _devices_file
    _data_dir = data_dir
    _devices_file = devices_file

def _topology_file():
    return os.path.join(_data_dir, 'topology_state.json')

def _templates_file():
    return os.path.join(_data_dir, 'topology_templates.json')

def _load_topology_state():
    tf = _topology_file()
    if os.path.exists(tf):
        with open(tf, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'nodes': [], 'links': [], 'version': 1}

def _save_topology_state(state):
    tf = _topology_file()
    os.makedirs(os.path.dirname(tf), exist_ok=True)
    with open(tf, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def _load_topology_templates():
    ttf = _templates_file()
    if os.path.exists(ttf):
        with open(ttf, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_topology_templates(templates):
    ttf = _templates_file()
    os.makedirs(os.path.dirname(ttf), exist_ok=True)
    with open(ttf, 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)

def _load_devices():
    if os.path.exists(_devices_file):
        with open(_devices_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


# ===== 路由 =====

@topology_bp.route('/api/topology/state', methods=['GET', 'PATCH'])
def topology_state():
    if request.method == 'GET':
        return jsonify(_load_topology_state())
    else:
        data = request.json or {}
        state = _load_topology_state()
        if 'nodes' in data:
            state['nodes'] = data['nodes']
        if 'links' in data:
            state['links'] = data['links']
        state['version'] = int(state.get('version', 1)) + 1
        _save_topology_state(state)
        return jsonify({'success': True})


@topology_bp.route('/api/topology/template/list', methods=['GET'])
def topology_template_list():
    return jsonify(_load_topology_templates())


@topology_bp.route('/api/topology/template/save', methods=['POST'])
def topology_template_save():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '模板名称不能为空'})

    templates = _load_topology_templates()
    state = _load_topology_state()

    template = {
        'name': name,
        'nodes': state.get('nodes', []),
        'links': state.get('links', []),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    # 更新或追加
    for i, t in enumerate(templates):
        if t.get('name') == name:
            templates[i] = template
            break
    else:
        templates.append(template)

    _save_topology_templates(templates)
    return jsonify({'success': True})


@topology_bp.route('/api/topology/template/load', methods=['POST'])
def topology_template_load():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '模板名称不能为空'})

    templates = _load_topology_templates()
    for t in templates:
        if t.get('name') == name:
            state = _load_topology_state()
            state['nodes'] = t.get('nodes', [])
            state['links'] = t.get('links', [])
            state['version'] = int(state.get('version', 1)) + 1
            _save_topology_state(state)
            return jsonify({'success': True})

    return jsonify({'success': False, 'message': f'模板 "{name}" 不存在'})


def _extract_topology_links(text, local_name):
    """从LLDP/CDP输出提取拓扑链接"""
    links = []
    if not text or not local_name:
        return links

    lines = text.strip().split('\n')
    current_entry = {}

    for line in lines:
        line = line.strip()

        # 华为 LLDP 格式
        if 'Port identifier' in line or 'local interface' in line.lower():
            m = re.search(r'(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?', line, re.IGNORECASE)
            if m:
                current_entry['local_port'] = m.group(0)

        elif 'Neighbor interface' in line or 'neighbor interface' in line.lower():
            m = re.search(r'(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?', line, re.IGNORECASE)
            if m:
                current_entry['neighbor_port'] = m.group(0)

        elif 'Neighbor port id' in line or 'port id' in line.lower():
            m = re.search(r'(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?', line, re.IGNORECASE)
            if not m:
                m = re.search(r'(Gi|Te|Fa)\d+/\d+', line, re.IGNORECASE)
            if m:
                if 'neighbor_port' not in current_entry:
                    current_entry['neighbor_port'] = m.group(0)

        elif 'System name' in line or 'system name' in line.lower():
            m = re.search(r'System name\s*:\s*(.+)', line)
            if not m:
                m = re.search(r'System Name\s*:\s*(.+)', line)
            if m:
                current_entry['neighbor_name'] = m.group(1).strip()

        # 思科 CDP 格式
        elif 'Platform' in line and 'cisco' in line.lower():
            m = re.search(r'Platform:\s*(\S+)', line)
            if m:
                current_entry['neighbor_platform'] = m.group(1)

        elif 'Interface' in line and re.search(r'GigabitEthernet|FastEthernet|TenGig', line):
            m = re.search(r'(GigabitEthernet|FastEthernet|TenGig|Gi|Te|Fa)\d+(?:/\d+)*(?:\.\d+)?', line, re.IGNORECASE)
            if m:
                if 'local_port' not in current_entry:
                    current_entry['local_port'] = m.group(0)
                else:
                    current_entry['neighbor_port'] = m.group(0)

        # 空行表示一条记录结束
        if not line and current_entry.get('neighbor_name') and current_entry.get('local_port'):
            links.append({
                'from_name': local_name,
                'from_port': current_entry['local_port'],
                'to_name': current_entry['neighbor_name'],
                'to_port': current_entry.get('neighbor_port', ''),
            })
            current_entry = {}

    # 最后一条
    if current_entry.get('neighbor_name') and current_entry.get('local_port'):
        links.append({
            'from_name': local_name,
            'from_port': current_entry['local_port'],
            'to_name': current_entry['neighbor_name'],
            'to_port': current_entry.get('neighbor_port', ''),
        })

    return links


def ensure_lldp_on_all_devices(devices):
    """确保所有设备的LLDP信息已采集"""
    from netops_tools import NetOpsTools
    tools = NetOpsTools(_devices_file)
    updated = []

    for d in devices:
        name = d.get('remark') or d.get('name')
        if not name:
            continue

        # 已有LLDP数据则跳过
        if d.get('lldp_neighbors'):
            updated.append(d)
            continue

        # 读取LLDP信息
        try:
            result = tools.execute_tool('run_commands', {
                'device': name,
                'commands': ['display lldp neighbor brief'] if d.get('vendor') in ('huawei', 'h3c')
                            else ['show lldp neighbors detail']
            })
            if result.get('success') and result.get('results'):
                lldp_text = result['results'][0].get('output', '')
                d['lldp_neighbors'] = _extract_topology_links(lldp_text, name)
                updated.append(d)
            else:
                updated.append(d)
        except Exception:
            updated.append(d)

    return updated


@topology_bp.route('/api/topology/discover', methods=['POST'])
def topology_discover():
    """拓扑发现"""
    from netops_tools import NetOpsTools
    tools = NetOpsTools(_devices_file)
    data = request.json or {}
    device_filter = data.get('devices', [])

    devices = _load_devices()
    if device_filter:
        devices = [d for d in devices if (d.get('remark') or d.get('name')) in device_filter]

    if not devices:
        return jsonify({'success': False, 'message': '没有可发现的设备'})

    # 1. 先确保所有设备有LLDP数据
    devices = ensure_lldp_on_all_devices(devices)

    # 2. 收集所有链路
    all_links = []
    for d in devices:
        name = d.get('remark') or d.get('name')
        for link in d.get('lldp_neighbors', []):
            link['from_name'] = name
            all_links.append(link)

    # 3. 去重（A→B 和 B→A 可能重复）
    seen = set()
    uniq_links = []
    for l in all_links:
        from_name = l.get('from_name', '')
        to_name = l.get('to_name', '')
        from_port = l.get('from_port', '')
        to_port = l.get('to_port', '')
        # 排序时端口也要跟着名字一起换
        if from_name > to_name:
            key = (to_name, to_port, from_name, from_port)
        else:
            key = (from_name, from_port, to_name, to_port)
        if key not in seen:
            seen.add(key)
            uniq_links.append(l)

    # 4. 构建节点
    old_state = _load_topology_state()
    old_nodes = old_state.get('nodes', [])

    nodes = []
    for d in devices:
        old = next((n for n in old_nodes if n.get('id') == d.get('id')), {})
        nodes.append({
            'id': d.get('id'),
            'name': d.get('name'),
            'remark': d.get('remark', ''),
            'ip': d.get('ip') or d.get('serial_port') or 'N/A',
            'deviceType': d.get('device_type', 'unknown'),
            'x': old.get('x'),
            'y': old.get('y'),
            'facts': d.get('facts')
        })

    # 5. 构建边（从链路映射到节点ID）
    device_map = {d.get('name'): d.get('id') for d in devices}
    device_map.update({d.get('remark'): d.get('id') for d in devices if d.get('remark')})

    edges = []
    for l in uniq_links:
        fid = device_map.get(l.get('from_name'))
        tid = device_map.get(l.get('to_name'))
        if fid and tid:
            fp = l.get('from_port', '')
            tp = l.get('to_port', '')
            key = f"{fid}-{fp}-{tid}-{tp}"
            edges.append({
                'from': fid, 'to': tid, 'id': f'link_{len(edges)+1}',
                'from_name': l.get('from_name'), 'to_name': l.get('to_name'),
                'from_port': fp, 'to_port': tp,
                'link_type': 'unknown', 'protocol': 'lldp'
            })

    # 6. 保存
    state = _load_topology_state()
    state['nodes'] = nodes
    state['links'] = edges
    state['version'] = int(state.get('version', 1)) + 1
    _save_topology_state(state)

    # debug日志
    debug_path = os.path.join(_data_dir, '_discover_debug.txt')
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(f'Links: {len(edges)}\n')
        for l in edges:
            f.write(f"  {l['from_name']} {l['from_port']} -> {l['to_name']} {l['to_port']}\n")

    return jsonify({
        'success': True,
        'nodes': len(nodes),
        'links': len(edges),
        'state': state
    })


@topology_bp.route('/api/topology/apply', methods=['POST'])
def topology_apply():
    """应用拓扑变更到设备"""
    data = request.json or {}
    changes = data.get('changes', [])
    if not changes:
        return jsonify({'success': False, 'message': '没有变更'})

    results = []
    for change in changes:
        results.append({'change': change, 'status': 'skipped', 'message': '暂不支持自动应用拓扑变更'})

    return jsonify({'success': True, 'results': results})
