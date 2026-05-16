#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NetOps AI Web - 精简入口，逻辑已拆分到blueprints/"""
from flask import Flask, request, jsonify, render_template
import json, os, sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

app = Flask(__name__)
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEB_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DEVICES_FILE = os.path.join(DATA_DIR, 'devices.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'llm_config.json')

# 注册蓝图（init_* 是模块级函数，不是 Blueprint 实例方法）
from blueprints import topology_bp, device_bp, chat_bp, sys_bp
from blueprints.topology import init_topology_blueprint
from blueprints.device import init_device_blueprint
from blueprints.chat import init_chat_blueprint
from blueprints.system import init_system_blueprint

init_topology_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE)
init_device_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE, project_root=PROJECT_ROOT)
init_chat_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE, project_root=PROJECT_ROOT)
init_system_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE, project_root=PROJECT_ROOT)

app.register_blueprint(topology_bp)
app.register_blueprint(device_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(sys_bp)

# WebSocket
try:
    from ws_push import init_socketio
    socketio = init_socketio(app)
except ImportError:
    socketio = None

# CORS 安全：仅允许本机访问（生产环境应配置具体域名）
try:
    from flask_cors import CORS
    CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*"])
except ImportError:
    pass


# ===== 首页 =====
@app.route('/')
def index():
    return render_template('index.html')


# ===== 快速意图匹配（未走模板的旧逻辑，保留兼容） =====
def _match_quick_intent(message, device_name, vendor):
    """匹配高频操作意图 — 优先走 command_templates，这里只做查看类快捷映射"""
    import re
    msg = message.strip()

    # 优先走模板系统
    from app.network.command_templates import TemplateMatcher
    device_type_map = {'huawei': 'huawei', 'h3c': 'hp_comware', 'cisco': 'cisco_ios', 'juniper': 'juniper_junos'}
    netmiko_type = device_type_map.get(vendor, 'huawei')

    # 解析意图参数
    params = _extract_config_params(message)
    if params.get('intent_type'):
        template_commands = TemplateMatcher.match(
            intent_type=params['intent_type'],
            vendor=netmiko_type,
            parameters=params,
        )
        if template_commands:
            return [{'device': device_name, 'commands': template_commands}]

    # 查看类快捷映射
    is_huawei_family = vendor in ('huawei', 'h3c', 'ruijie')
    is_cisco_family = vendor in ('cisco', 'cisco_nxos', 'arista', 'juniper')

    _QUERY_MAP_HUAWEI = {
        'vlan': 'display vlan brief', '接口': 'display interface brief',
        '路由': 'display ip routing-table', 'arp': 'display arp',
        'ospf': 'display ospf peer brief', 'bgp': 'display bgp peer',
        '版本': 'display version', '配置': 'display current-configuration',
        'lldp': 'display lldp neighbor-information list', 'mac': 'display mac-address',
    }
    _QUERY_MAP_CISCO = {
        'vlan': 'show vlan brief', '接口': 'show interface brief',
        '路由': 'show ip route', 'arp': 'show arp',
        'ospf': 'show ip ospf neighbor', 'bgp': 'show bgp summary',
        '版本': 'show version', '配置': 'show running-config',
        'lldp': 'show lldp neighbors', 'mac': 'show mac address-table',
    }

    qm = re.search(r'(?:查看|查看一下|查|显示|看下|看看)\s*(.+)', msg, re.IGNORECASE)
    if qm:
        q_target = qm.group(1).strip().lower()
        query_map = _QUERY_MAP_HUAWEI if is_huawei_family else _QUERY_MAP_CISCO
        for key, cmd in query_map.items():
            if key in q_target:
                return [{'device': device_name, 'commands': [cmd]}]

    return None


def _extract_config_params(message):
    """从自然语言提取配置参数"""
    import re
    msg = message.strip()
    params = {}

    # VLAN操作
    m = re.search(r'(?:创建|新增|添加)\s*VLAN\s*(\d+)', msg, re.IGNORECASE)
    if m:
        params = {'intent_type': 'config_vlan', 'vlan_id': m.group(1), 'mode': 'access'}
        return params

    m = re.search(r'删除\s*VLAN\s*(\d+)', msg, re.IGNORECASE)
    if m:
        params = {'intent_type': 'config_vlan_delete', 'vlan_id': m.group(1)}
        return params

    # 接口划入VLAN
    m = re.search(r'(?:配置|设置|把|将)\s*(.+?)\s*(?:划入|加入|配到|放到)\s*VLAN\s*(\d+)', msg, re.IGNORECASE)
    if m:
        params = {'intent_type': 'config_vlan', 'interfaces': m.group(1), 'vlan_id': m.group(2), 'mode': 'access'}
        return params

    # Trunk配置
    m = re.search(r'(?:配置|设置)\s*(\S+)\s*(?:为|做)\s*trunk', msg, re.IGNORECASE)
    if m:
        vm = re.search(r'(?:allow|允许|放行)\s*VLAN\s*([\d,\-]+)', msg, re.IGNORECASE)
        allow_vlans = vm.group(1) if vm else 'all'
        params = {'intent_type': 'config_vlan', 'interfaces': m.group(1), 'vlan_id': allow_vlans, 'mode': 'trunk'}
        return params

    # 接口shutdown
    m = re.search(r'(?:关闭|shutdown)\s*(?:接口|端口)?\s*(\S+)', msg, re.IGNORECASE)
    if m and 'undo' not in msg.lower() and '开启' not in msg:
        params = {'intent_type': 'config_interface', 'interface': m.group(1), 'action': 'shutdown'}
        return params

    # 接口undo shutdown
    m = re.search(r'(?:开启|undo shutdown|no shutdown)\s*(?:接口|端口)?\s*(\S+)', msg, re.IGNORECASE)
    if m:
        params = {'intent_type': 'config_interface', 'interface': m.group(1), 'action': 'no_shutdown'}
        return params

    # 静态路由
    m = re.search(r'(?:添加|配置|设置)\s*静态路由\s+(\S+)\s+(\S+)', msg, re.IGNORECASE)
    if m:
        params = {'intent_type': 'config_routing', 'dest': m.group(1), 'next_hop': m.group(2)}
        return params

    # ACL封禁
    m = re.search(r'(?:封禁|屏蔽|block|deny)\s*(?:IP\s*)?(\d+\.\d+\.\d+\.\d+)', msg, re.IGNORECASE)
    if m:
        params = {'intent_type': 'config_acl', 'target_ip': m.group(1)}
        return params

    return params


# 启动
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    if socketio:
        socketio.run(app, host=args.host, port=args.port, debug=args.debug)
    else:
        app.run(host=args.host, port=args.port, debug=args.debug)
