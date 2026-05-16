#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聊天蓝图 - AI对话、快速配置、诊断
"""
from flask import Blueprint, request, jsonify
import json, os, re, time

chat_bp = Blueprint('chat', __name__)

_data_dir = ''
_devices_file = ''
_project_root = ''

def init_chat_blueprint(data_dir, devices_file, project_root):
    global _data_dir, _devices_file, _project_root
    _data_dir = data_dir
    _devices_file = devices_file
    _project_root = project_root

def _load_devices():
    if os.path.exists(_devices_file):
        with open(_devices_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# 设备列表缓存（避免每次 chat 都重读+重新格式化）
_device_list_cache = {'mtime': 0, 'devices_str': ''}

def _get_device_list_str():
    """获取格式化的设备列表字符串（带文件修改时间缓存）"""
    global _device_list_cache
    try:
        mtime = os.path.getmtime(_devices_file) if os.path.exists(_devices_file) else 0
    except OSError:
        mtime = 0

    if mtime != _device_list_cache['mtime']:
        devices = _load_devices()
        _device_list_cache['mtime'] = mtime
        _device_list_cache['devices_str'] = '\n'.join([
            f"- {d.get('remark') or d.get('name')} ({d.get('ip')}, {d.get('vendor', 'unknown')})"
            for d in devices
        ])
    return _device_list_cache['devices_str']


@chat_bp.route('/api/chat', methods=['POST'])
def chat():
    """主聊天接口"""
    data = request.json or {}
    message = data.get('message', '').strip()
    device_name = data.get('device', '')
    session_id = data.get('session_id', 'default')

    if not message:
        return jsonify({'success': False, 'message': '消息不能为空'})

    try:
        result = _do_chat(message, device_name, session_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def _do_chat(message, selected_device, session_id='default'):
    """核心聊天逻辑"""
    from app.llm.config import LLMConfig
    from app.session import SessionManager
    from app.session.models import TurnRole
    from netops_tools import NetOpsTools, get_tools_definition

    config = LLMConfig()
    llm = config.get_client()
    if not llm:
        return {'success': False, 'message': 'LLM 未配置，请先在设置中配置'}

    tools = NetOpsTools(_devices_file)
    session_dir = os.path.join(_data_dir, 'sessions')
    session_mgr = SessionManager(storage_dir=session_dir)

    # 加载会话历史
    # 注意：Web端用 session_id 作为 user_id，每个浏览器tab一个会话
    # SessionManager 的 user_id 参数在这里传的是 session_id
    session = session_mgr.get_session(session_id)
    if not session:
        session = session_mgr.create_session(session_id)
    # 使用 SessionManager.add_turn 来添加轮次（会自动保存）
    session_mgr.add_turn(session_id, TurnRole.USER, message)

    # 构建系统提示（使用缓存的设备列表字符串）
    devices = _load_devices()
    device_list_str = _get_device_list_str()

    system_prompt = f"""你是一个网络运维助手，帮助用户管理网络设备。

可用设备：
{device_list_str}

当前选中设备：{selected_device or '未选择'}

你可以使用以下工具：
{json.dumps(get_tools_definition(), ensure_ascii=False, indent=2)}

规则：
1. 执行命令前先确认设备名
2. 配置命令需要用户确认
3. 危险操作（重启、删除配置等）必须警告
4. 优先使用只读命令了解状态
"""

    # 构建消息列表
    messages = [{'role': 'system', 'content': system_prompt}]
    for turn in session.turns[-20:]:  # 最近20轮
        messages.append({'role': turn.role.value, 'content': turn.content})

    # 调用LLM
    response = llm.chat(messages=messages, tools=get_tools_definition())

    # 处理工具调用
    if response.get('tool_calls'):
        from app.network.command_service import CommandService
        cmd_svc = CommandService()
        results = []
        for tc in response['tool_calls']:
            tool_name = tc.get('function', {}).get('name', '')
            arguments = json.loads(tc.get('function', {}).get('arguments', '{}'))

            # 命令类工具 → 统一走 CommandService
            if tool_name in ('run_commands', 'ssh_connect'):
                commands = arguments.get('commands', [])
                if commands:
                    # 查找设备
                    dev = None
                    for d in devices:
                        if d.get('name') == arguments.get('device') or d.get('remark') == arguments.get('device'):
                            dev = d
                            break
                    if dev:
                        dev_info = CommandService.device_from_dict(dev)
                        cmd_result = cmd_svc.execute(dev_info, commands, user_id=session_id, source='llm')
                        if not cmd_result.success:
                            results.append({
                                'tool': tool_name,
                                'error': cmd_result.error,
                                'blocked': bool(cmd_result.blocked_commands),
                            })
                            continue
                        # 转换 CommandService 结果为原格式
                        tool_result = {
                            'success': True,
                            'results': cmd_result.outputs,
                            'backup_id': cmd_result.backup_id,
                        }
                        results.append({'tool': tool_name, 'result': tool_result})
                        continue

            # 非命令类工具（如 get_devices）仍走 NetOpsTools
            tool_result = tools.execute_tool(tool_name, arguments)
            results.append({'tool': tool_name, 'result': tool_result})

        # 把工具结果反馈给LLM
        tool_summary = '\n'.join([
            f"工具 {r['tool']}: {json.dumps(r.get('result', r.get('error', '')), ensure_ascii=False)[:500]}"
            for r in results
        ])
        session_mgr.add_turn(session_id, TurnRole.ASSISTANT, f"已执行工具，结果如下：\n{tool_summary}")

        return {
            'success': True,
            'message': tool_summary,
            'tool_calls': results,
        }

    # 普通回复
    content = response.get('content', '')
    session_mgr.add_turn(session_id, TurnRole.ASSISTANT, content)

    return {
        'success': True,
        'message': content,
    }


@chat_bp.route('/api/quick-config', methods=['POST'])
def quick_config():
    """快速配置接口 — 模板优先"""
    data = request.json or {}
    device_name = data.get('device', '')
    config_type = data.get('type', '')
    parameters = data.get('parameters', {})

    if not device_name:
        return jsonify({'success': False, 'message': '请指定设备'})

    # 查找设备
    devices = _load_devices()
    device = None
    for d in devices:
        if d.get('name') == device_name or d.get('remark') == device_name or d.get('ip') == device_name:
            device = d
            break

    if not device:
        return jsonify({'success': False, 'message': f'设备 {device_name} 不存在'})

    vendor = device.get('vendor', 'huawei')
    netmiko_type = {'huawei': 'huawei', 'h3c': 'huawei', 'cisco': 'cisco_ios', 'juniper': 'juniper_junos'}.get(vendor, 'huawei')

    # 1. 模板优先
    from app.network.command_templates import TemplateMatcher
    template_commands = TemplateMatcher.match(
        intent_type=config_type,
        vendor=netmiko_type,
        parameters=parameters,
    )

    if template_commands:
        # 统一安全检查
        from app.network.command_service import CommandService
        dev_info = CommandService.device_from_dict(device)
        check = CommandService().check_only(dev_info, template_commands)
        if not check.success:
            return jsonify({
                'success': False,
                'message': '命令安全检查未通过',
                'blocked': check.blocked_commands,
            })

        return jsonify({
            'success': True,
            'commands': template_commands,
            'source': 'template',
            'device': device_name,
            'vendor': vendor,
            'requires_confirmation': True,
        })

    # 2. LLM兜底
    from app.llm.config import LLMConfig
    llm = LLMConfig().get_client()
    if not llm:
        return jsonify({'success': False, 'message': 'LLM未配置'})

    prompt = f"""为 {vendor} 设备 {device_name} 生成配置命令。
配置类型: {config_type}
参数: {json.dumps(parameters, ensure_ascii=False)}

请返回JSON格式的命令列表，例如: ["system-view", "vlan 10", ...]
只返回JSON，不要其他内容。"""

    try:
        response = llm.chat(
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,
        )
        content = response.get('content', '').strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]
        commands = json.loads(content.strip())

        return jsonify({
            'success': True,
            'commands': commands,
            'source': 'llm',
            'device': device_name,
            'vendor': vendor,
            'requires_confirmation': True,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'生成配置失败: {e}'})


@chat_bp.route('/api/diagnose', methods=['POST'])
def api_diagnose():
    """诊断接口 — 统一走 CommandService"""
    data = request.json or {}
    device_name = data.get('device', '')
    diagnose_type = data.get('type', 'connectivity')

    if not device_name:
        return jsonify({'success': False, 'message': '请指定设备'})

    devices = _load_devices()
    device = None
    for d in devices:
        if d.get('name') == device_name or d.get('remark') == device_name or d.get('ip') == device_name:
            device = d
            break

    if not device:
        return jsonify({'success': False, 'message': f'设备 {device_name} 不存在'})

    vendor = device.get('vendor', 'huawei')

    # 获取诊断命令
    if vendor in ('huawei', 'h3c'):
        cmd_map = {
            'connectivity': ['ping ', 'display arp', 'display mac-address'],
            'routing': ['display ip routing-table', 'display ospf peer brief'],
            'vlan': ['display vlan', 'display interface brief'],
            'interface': ['display interface', 'display link-aggregation summary'],
        }
    else:
        cmd_map = {
            'connectivity': ['ping ', 'show arp', 'show mac address-table'],
            'routing': ['show ip route', 'show ip ospf neighbor'],
            'vlan': ['show vlan', 'show interfaces status'],
            'interface': ['show interfaces', 'show etherchannel summary'],
        }

    commands = cmd_map.get(diagnose_type, cmd_map['connectivity'])

    # ping需要目标
    if diagnose_type == 'connectivity' and data.get('target'):
        commands[0] = f"{commands[0].strip()} {data['target']}"

    # 统一走 CommandService（含安全检查）
    from app.network.command_service import CommandService
    dev_info = CommandService.device_from_dict(device)
    cmd_result = CommandService().execute(
        dev_info, commands,
        source='diagnosis',
        skip_guard=True,   # 诊断命令都是只读查询，跳过 CommandGuard
    )

    result = {'success': cmd_result.success}
    if cmd_result.success:
        result['results'] = cmd_result.outputs
        analysis = _analyze_diagnosis(cmd_result.outputs, diagnose_type)
        result['analysis'] = analysis
    else:
        result['message'] = cmd_result.error

    return jsonify(result)


def _analyze_diagnosis(results, diagnose_type):
    """简单分析诊断结果"""
    analysis = {'type': diagnose_type, 'findings': [], 'status': 'unknown'}

    for r in results:
        output = r.get('output', '').lower()
        cmd = r.get('command', '')

        if 'ping' in cmd:
            if '100% packet loss' in output or '0 packets received' in output:
                analysis['findings'].append('❌ Ping 100%丢包')
                analysis['status'] = 'fail'
            elif 'packet loss' in output:
                analysis['findings'].append('⚠️ Ping 有丢包')
                analysis['status'] = 'partial'
            else:
                analysis['findings'].append('✅ Ping 正常')
                analysis['status'] = 'ok'

        elif 'arp' in cmd:
            if not output.strip() or len(output.strip()) < 20:
                analysis['findings'].append('⚠️ ARP表为空')
            else:
                lines = [l for l in output.split('\n') if l.strip() and not l.strip().startswith(('Age', 'IP', '-'))]
                analysis['findings'].append(f'ARP表有 {len(lines)} 条记录')

        elif 'route' in cmd:
            if '0 routes' in output or not output.strip():
                analysis['findings'].append('⚠️ 路由表为空')
            else:
                analysis['findings'].append('✅ 路由表有条目')

    return analysis


@chat_bp.route('/api/rollback', methods=['POST'])
def api_rollback():
    """回滚配置"""
    data = request.json or {}
    device_name = data.get('device', '')
    snapshot_id = data.get('snapshot_id', '')

    if not device_name or not snapshot_id:
        return jsonify({'success': False, 'message': '请指定设备和快照ID'})

    from netops_tools import NetOpsTools
    tools = NetOpsTools(_devices_file)
    result = tools.rollback_config(device_name, snapshot_id)
    return jsonify(result)


@chat_bp.route('/api/snapshots', methods=['GET'])
def api_snapshots():
    """获取配置快照列表"""
    snapshot_dir = os.path.join(_data_dir, 'snapshots')
    if not os.path.exists(snapshot_dir):
        return jsonify({'success': True, 'snapshots': []})

    snapshots = []
    for f in sorted(os.listdir(snapshot_dir), reverse=True):
        if f.endswith('.cfg'):
            snapshots.append({
                'id': f[:-4],
                'file': f,
                'size': os.path.getsize(os.path.join(snapshot_dir, f)),
                'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(os.path.join(snapshot_dir, f)))),
            })

    return jsonify({'success': True, 'snapshots': snapshots})


@chat_bp.route('/api/config/diff', methods=['POST'])
def config_diff():
    """配置对比"""
    from app.diagnosis.config_diff import ConfigDiff

    data = request.json or {}
    device_ip = data.get('device_ip', '')
    old_config = data.get('old_config', '')
    new_config = data.get('new_config', '')
    old_file = data.get('old_file', '')
    new_file = data.get('new_file', '')

    differ = ConfigDiff(storage_dir=os.path.join(_data_dir, 'config_snapshots'))

    # 从文件加载
    if old_file and not old_config:
        old_config = differ.load_config_file(old_file)
    if new_file and not new_config:
        new_config = differ.load_config_file(new_file)

    if not old_config or not new_config:
        return jsonify({'success': False, 'message': '请提供两个配置内容或文件路径'})

    result = differ.diff_configs(old_config, new_config)
    sections = differ.diff_sections(old_config, new_config)

    return jsonify({
        'success': True,
        'has_changes': result['has_changes'],
        'summary': result['summary'],
        'added': result['added'][:50],
        'removed': result['removed'][:50],
        'unified_diff': result['unified_diff'][:10000],
        'sections': sections[:20],
    })


@chat_bp.route('/api/config/snapshot', methods=['POST'])
def config_snapshot():
    """保存配置快照"""
    from app.diagnosis.config_diff import ConfigDiff

    data = request.json or {}
    device_ip = data.get('device_ip', '')
    config = data.get('config', '')
    label = data.get('label', 'manual')

    if not device_ip or not config:
        return jsonify({'success': False, 'message': '缺少 device_ip 或 config'})

    differ = ConfigDiff(storage_dir=os.path.join(_data_dir, 'config_snapshots'))
    filepath = differ.save_config(device_ip, config, label)

    return jsonify({'success': True, 'filepath': filepath})
