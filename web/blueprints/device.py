#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备蓝图 - 设备CRUD、发现、信息采集
"""
from flask import Blueprint, request, jsonify
import json, os, re, time, subprocess

device_bp = Blueprint('device', __name__)

_data_dir = ''
_devices_file = ''
_project_root = ''

def init_device_blueprint(data_dir, devices_file, project_root):
    global _data_dir, _devices_file, _project_root
    _data_dir = data_dir
    _devices_file = devices_file
    _project_root = project_root

def _load_devices():
    if os.path.exists(_devices_file):
        with open(_devices_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_devices(devices):
    os.makedirs(os.path.dirname(_devices_file), exist_ok=True)
    with open(_devices_file, 'w', encoding='utf-8') as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)


@device_bp.route('/api/devices', methods=['GET'])
def get_devices():
    return jsonify(_load_devices())


@device_bp.route('/api/device/add', methods=['POST'])
def add_device():
    """添加设备（支持单个和批量）"""
    data = request.json or {}

    # 批量添加
    if 'devices' in data:
        results = []
        for d in data['devices']:
            r = _add_single_device(d)
            results.append(r)
        ok = sum(1 for r in results if r.get('success'))
        return jsonify({'success': True, 'added': ok, 'total': len(results), 'results': results})

    # 单个添加
    result = _add_single_device(data)
    return jsonify(result)


def _add_single_device(data):
    """添加单个设备"""
    ip = data.get('ip', '').strip()
    name = data.get('name', '').strip()
    remark = data.get('remark', '').strip()
    username = data.get('username', '')
    password = data.get('password', '')
    vendor = data.get('vendor', 'auto')
    port = data.get('port', 22)
    conn_type = data.get('conn_type', 'ssh')
    auto_detect = data.get('auto_detect', False)

    if not ip and not name:
        return {'success': False, 'message': 'IP 或设备名不能为空'}

    devices = _load_devices()

    # 去重
    for d in devices:
        if d.get('ip') == ip or (name and d.get('name') == name):
            return {'success': False, 'message': f'设备 {ip or name} 已存在'}

    # 自动发现
    if auto_detect and ip:
        detected = _auto_detect_device(ip, username, password, port)
        if detected:
            vendor = detected.get('vendor', vendor)
            name = name or detected.get('hostname', '')
            remark = remark or detected.get('hostname', '')

    device_id = f"dev_{int(time.time()*1000)}"
    device = {
        'id': device_id,
        'name': name or ip,
        'ip': ip,
        'port': int(port),
        'username': username,
        'password': password,
        'vendor': vendor,
        'conn_type': conn_type,
        'remark': remark,
        'device_type': 'unknown',
        'facts': {},
    }

    devices.append(device)
    _save_devices(devices)
    return {'success': True, 'device': device}


def _auto_detect_device(ip, username, password, port=22):
    """自动探测设备厂商和型号"""
    try:
        from netmiko import ConnectHandler
        # 先试华为
        for device_type in ['huawei', 'cisco_ios', 'hp_comware', 'juniper_junos']:
            try:
                conn = ConnectHandler(
                    device_type=device_type,
                    host=ip, port=port,
                    username=username, password=password,
                    timeout=10, conn_timeout=8,
                )
                prompt = conn.find_prompt() or ''
                if device_type == 'huawei':
                    output = conn.send_command_timing('display version', delay_factor=1, timeout=10)
                else:
                    output = conn.send_command_timing('show version', delay_factor=1, timeout=10)
                conn.disconnect()

                hostname = prompt.strip('<>[]#>').strip()
                vendor_map = {'huawei': 'huawei', 'cisco_ios': 'cisco', 'hp_comware': 'h3c', 'juniper_junos': 'juniper'}

                return {
                    'vendor': vendor_map.get(device_type, device_type),
                    'hostname': hostname,
                    'version_output': output[:500],
                }
            except Exception:
                continue
    except ImportError:
        pass
    return None


def identify_device(device):
    """识别设备厂商和型号"""
    from app.core.device import Vendor, DeviceType
    from app.core.vendor import VendorIdentifier

    facts = device.get('facts', {})
    sys_descr = facts.get('sys_descr', '')
    sys_object_id = facts.get('sys_object_id', '')

    vendor, model, dtype = VendorIdentifier.identify_from_snmp(sys_descr, sys_object_id)

    return {
        'vendor': vendor.value if vendor else 'unknown',
        'model': model,
        'device_type': dtype.value if dtype else 'unknown',
        'display_vendor': VendorIdentifier.get_vendor_display_name(vendor),
        'display_type': VendorIdentifier.get_device_type_display_name(dtype),
    }


@device_bp.route('/api/discover', methods=['POST'])
def discover():
    """网络发现"""
    data = request.json or {}
    ip_range = data.get('ip_range', '')
    username = data.get('username', '')
    password = data.get('password', '')

    if not ip_range:
        return jsonify({'success': False, 'message': '请指定IP范围'})

    # 解析IP范围
    ips = _parse_ip_range(ip_range)
    if not ips:
        return jsonify({'success': False, 'message': '无效的IP范围'})

    results = []
    for ip in ips:
        detected = _auto_detect_device(ip, username, password)
        if detected:
            results.append({
                'ip': ip,
                'vendor': detected.get('vendor', 'unknown'),
                'hostname': detected.get('hostname', ''),
            })

    return jsonify({'success': True, 'discovered': results, 'total': len(results)})


def _parse_ip_range(ip_range_str):
    """解析IP范围字符串"""
    ips = []
    parts = [p.strip() for p in ip_range_str.replace('，', ',').split(',')]

    for part in parts:
        if '-' in part:
            base, suffix = part.rsplit('-', 1)
            try:
                start = int(base.split('.')[-1])
                end = int(suffix)
                prefix = '.'.join(base.split('.')[:-1])
                for i in range(min(start, end), max(start, end) + 1):
                    ips.append(f"{prefix}.{i}")
            except (ValueError, IndexError):
                continue
        else:
            if re.match(r'\d+\.\d+\.\d+\.\d+', part):
                ips.append(part)

    return ips


@device_bp.route('/api/device/delete', methods=['POST'])
def delete_device():
    """删除设备"""
    data = request.json or {}
    device_id = data.get('id', '')
    device_name = data.get('name', '')

    if not device_id and not device_name:
        return jsonify({'success': False, 'message': '请指定设备ID或名称'})

    devices = _load_devices()
    original_len = len(devices)

    devices = [
        d for d in devices
        if d.get('id') != device_id and (d.get('name') != device_name and d.get('remark') != device_name)
    ]

    if len(devices) == original_len:
        return jsonify({'success': False, 'message': '设备不存在'})

    _save_devices(devices)
    return jsonify({'success': True})


@device_bp.route('/api/device/collect', methods=['POST'])
def device_collect():
    """采集设备信息"""
    data = request.json or {}
    device_name = data.get('device', '')
    collect_type = data.get('type', 'all')

    from netops_tools import NetOpsTools
    tools = NetOpsTools(_devices_file)
    device = None
    for d in tools.load_devices():
        if d.get('name') == device_name or d.get('remark') == device_name or d.get('ip') == device_name:
            device = d
            break

    if not device:
        return jsonify({'success': False, 'message': f'设备 {device_name} 不存在'})

    vendor = device.get('vendor', 'huawei')
    commands = _get_collect_commands(vendor, collect_type)
    result = tools.execute_tool('run_commands', {'device': device_name, 'commands': commands})

    if result.get('success'):
        # 解析采集结果更新设备信息
        _update_device_facts(device, result.get('results', []), vendor)
        devices = _load_devices()
        for i, d in enumerate(devices):
            if d.get('id') == device.get('id'):
                devices[i] = device
                break
        _save_devices(devices)

    return jsonify(result)


def _get_collect_commands(vendor, collect_type):
    """获取采集命令列表"""
    if vendor in ('huawei', 'h3c'):
        cmd_map = {
            'all': ['display version', 'display device', 'display current-configuration'],
            'version': ['display version'],
            'interface': ['display interface brief'],
            'arp': ['display arp'],
            'route': ['display ip routing-table'],
        }
    else:
        cmd_map = {
            'all': ['show version', 'show inventory', 'show running-config'],
            'version': ['show version'],
            'interface': ['show ip interface brief'],
            'arp': ['show arp'],
            'route': ['show ip route'],
        }
    return cmd_map.get(collect_type, cmd_map['all'])


def _update_device_facts(device, results, vendor):
    """更新设备facts"""
    from app.core.vendor import VendorIdentifier
    from app.core.device import Vendor as VendorEnum

    facts = device.get('facts', {})

    for r in results:
        cmd = r.get('command', '')
        output = r.get('output', '')

        if 'version' in cmd:
            vendor_result, model, dtype = VendorIdentifier.identify_from_command_output(output)
            if vendor_result != VendorEnum.UNKNOWN:
                device['vendor'] = vendor_result.value
            if model:
                facts['model'] = model
            if dtype:
                device['device_type'] = dtype.value
            facts['version_output'] = output[:2000]

    device['facts'] = facts


@device_bp.route('/api/device/facts', methods=['GET'])
def device_facts():
    """获取设备facts"""
    device_name = request.args.get('device', '')
    if not device_name:
        return jsonify({'success': False, 'message': '请指定设备名'})

    devices = _load_devices()
    for d in devices:
        if d.get('name') == device_name or d.get('remark') == device_name or d.get('ip') == device_name:
            return jsonify({'success': True, 'facts': d.get('facts', {})})

    return jsonify({'success': False, 'message': '设备不存在'})
