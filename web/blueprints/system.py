#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统蓝图 - 审计日志、知识库、文件操作、LLM配置
"""
from flask import Blueprint, request, jsonify
import json, os, re, time, subprocess, sys

sys_bp = Blueprint('system', __name__)

_data_dir = ''
_devices_file = ''
_project_root = ''

def init_system_blueprint(data_dir, devices_file, project_root):
    global _data_dir, _devices_file, _project_root
    _data_dir = data_dir
    _devices_file = devices_file
    _project_root = project_root


@sys_bp.route('/api/llm/config', methods=['POST', 'GET'])
def handle_llm_config():
    if request.method == 'GET':
        config_file = os.path.join(_data_dir, 'llm_config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        return jsonify({'provider': '', 'model': '', 'api_key': '', 'base_url': ''})
    else:
        data = request.json or {}
        config_file = os.path.join(_data_dir, 'llm_config.json')
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True})


@sys_bp.route('/api/llm/test', methods=['POST'])
def test_llm():
    data = request.json or {}
    provider = data.get('provider', '')
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    base_url = data.get('base_url', '')

    if not api_key:
        return jsonify({'success': False, 'message': 'API Key 不能为空'})

    try:
        if provider == 'openai':
            import openai
            client = openai.OpenAI(api_key=api_key, base_url=base_url or None)
            resp = client.chat.completions.create(
                model=model or 'gpt-3.5-turbo',
                messages=[{'role': 'user', 'content': 'Hi, just testing. Reply with OK.'}],
                max_tokens=10,
            )
            return jsonify({'success': True, 'message': resp.choices[0].message.content})
        else:
            return jsonify({'success': False, 'message': f'不支持的 provider: {provider}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@sys_bp.route('/api/audit/logs', methods=['GET'])
def get_audit_logs():
    from app.audit import AuditLogger
    logger = AuditLogger()
    limit = int(request.args.get('limit', 50))
    logs = logger.get_recent(limit=limit)
    return jsonify({'success': True, 'logs': logs})


@sys_bp.route('/api/audit/summary', methods=['GET'])
def get_audit_summary():
    from app.audit import AuditLogger
    logger = AuditLogger()
    summary = logger.get_summary()
    return jsonify({'success': True, 'summary': summary})


@sys_bp.route('/api/knowledge/stats', methods=['GET'])
def get_knowledge_stats():
    try:
        from app.diagnosis.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        stats = kb.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': True, 'stats': {'total': 0, 'categories': 0}, 'error': str(e)})


@sys_bp.route('/api/knowledge/search', methods=['POST'])
def search_knowledge():
    data = request.json or {}
    query = data.get('query', '')
    if not query:
        return jsonify({'success': False, 'message': '查询不能为空'})

    try:
        from app.diagnosis.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        results = kb.search(query)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@sys_bp.route('/api/template/list', methods=['GET'])
def get_templates():
    """获取可用命令模板列表"""
    from app.network.command_templates import TemplateMatcher
    vendor = request.args.get('vendor', '')
    templates = TemplateMatcher.list_templates(vendor or None)
    return jsonify({'success': True, 'templates': templates})


@sys_bp.route('/api/exec', methods=['POST'])
def api_exec():
    """执行本地命令（仅允许白名单内的安全命令）"""
    data = request.json or {}
    command = data.get('command', '').strip()
    if not command:
        return jsonify({'success': False, 'message': '命令不能为空'})

    # 命令白名单：只允许只读诊断命令
    ALLOWED_PREFIXES = (
        'ping ', 'traceroute ', 'tracert ', 'nslookup ',
        'netstat ', 'ipconfig ', 'ifconfig ',
        'arp -', 'route ',
    )
    if not any(command.lower().startswith(p) for p in ALLOWED_PREFIXES):
        return jsonify({
            'success': False,
            'message': f'安全限制：仅允许网络诊断命令（ping/traceroute/netstat 等），不允许执行: {command.split()[0]}',
        })

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=_project_root,
        )
        return jsonify({
            'success': True,
            'stdout': result.stdout[:5000],
            'stderr': result.stderr[:2000],
            'returncode': result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '命令执行超时'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@sys_bp.route('/api/file/read', methods=['POST'])
def api_file_read():
    data = request.json or {}
    path = data.get('path', '')
    if not path:
        return jsonify({'success': False, 'message': '路径不能为空'})

    # 路径遍历防护：解析真实路径并检查是否在项目目录内
    try:
        abs_path = os.path.realpath(path)
    except Exception:
        return jsonify({'success': False, 'message': '路径无效'})

    project_real = os.path.realpath(_project_root)
    if not abs_path.startswith(project_real + os.sep) and abs_path != project_real:
        return jsonify({'success': False, 'message': '只能读取项目目录下的文件'})

    # 不允许读取敏感文件
    _SENSITIVE_EXTENSIONS = ('.env', '.pem', '.key', '.pkcs12', '.p12', '.jks', '.keystore')
    _SENSITIVE_NAMES = ('.git', 'credentials', 'secret', 'password', 'private_key', 'id_rsa', 'id_ed25519')
    _base_name = os.path.basename(abs_path).lower()
    if any(abs_path.lower().endswith(e) for e in _SENSITIVE_EXTENSIONS):
        return jsonify({'success': False, 'message': '不允许读取敏感文件（证书/密钥/环境配置）'})
    if any(p in _base_name for p in _SENSITIVE_NAMES):
        return jsonify({'success': False, 'message': '不允许读取敏感文件'})

    try:
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(100000)
        return jsonify({'success': True, 'content': content, 'path': abs_path})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@sys_bp.route('/api/file/write', methods=['POST'])
def api_file_write():
    data = request.json or {}
    path = data.get('path', '')
    content = data.get('content', '')
    if not path:
        return jsonify({'success': False, 'message': '路径不能为空'})

    # 写入大小限制 1MB
    if len(content) > 1_000_000:
        return jsonify({'success': False, 'message': '文件内容过大，限制 1MB'})

    # 路径遍历防护
    try:
        abs_path = os.path.realpath(path)
    except Exception:
        return jsonify({'success': False, 'message': '路径无效'})

    project_real = os.path.realpath(_project_root)
    if not abs_path.startswith(project_real + os.sep) and abs_path != project_real:
        return jsonify({'success': False, 'message': '只能写入项目目录下的文件'})

    # 不允许写入可执行文件和敏感配置文件
    _BLOCKED_WRITE_EXTS = ('.py', '.sh', '.bat', '.exe', '.cmd', '.ps1', '.env', '.pem', '.key', '.cfg', '.p12')
    if any(abs_path.lower().endswith(e) for e in _BLOCKED_WRITE_EXTS):
        return jsonify({'success': False, 'message': '不允许写入可执行文件或敏感配置文件'})

    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'path': abs_path})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def handle_local_intent(message):
    """处理本地操作意图"""
    workdir = _project_root

    # 查看文件
    if '查看文件' in message or '读取文件' in message or 'cat ' in message:
        m = re.search(r'(?:查看文件|读取文件|cat\s+)(.+)', message)
        if m:
            path = m.group(1).strip()
            abs_path = os.path.abspath(os.path.join(workdir, path))
            if os.path.isfile(abs_path):
                try:
                    with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read(50000)
                    return f"文件内容 ({abs_path}):\n{content[:50000]}"
                except Exception as e:
                    return f"读取失败: {e}"
            return f"文件不存在: {path}"

    # 列出文件
    if '列出文件' in message or 'ls ' in message:
        m = re.search(r'(?:列出文件|ls\s+)(.+)', message)
        path = m.group(1).strip() if m else '.'
        abs_path = os.path.abspath(os.path.join(workdir, path))
        if os.path.isdir(abs_path):
            items = os.listdir(abs_path)
            return f"目录内容 ({abs_path}):\n" + '\n'.join(items[:100])
        return f"目录不存在: {path}"

    return None


def execute_commands(device, commands):
    """执行设备命令（供handle_local_intent调用）"""
    from netops_tools import NetOpsTools
    tools = NetOpsTools(_devices_file)
    return tools.execute_tool('run_commands', {'device': device, 'commands': commands})
