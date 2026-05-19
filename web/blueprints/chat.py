#!/usr/bin/env python3
"""
聊天蓝图 - AI对话、快速配置、诊断
"""

from flask import Blueprint, request, jsonify
import json
import os
import re
import time
import logging

from .shared import load_devices as _shared_load_devices

log = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

_data_dir = ""
_devices_file = ""
_project_root = ""
_session_mgr = None  # 模块级SessionManager单例


def _match_device(devices, dev_name):
    """Match device by exact name, then by substring containment"""
    if not dev_name:
        return None
    # Exact match first
    for d in devices:
        if d.get("name") == dev_name or d.get("remark") == dev_name or d.get("ip") == dev_name:
            return d
    # Substring match: LLM name contains device name or vice versa
    for d in devices:
        dn = d.get("name", "")
        dr = d.get("remark", "")
        if (dn and (dn in dev_name or dev_name in dn)) or (dr and (dr in dev_name or dev_name in dr)):
            return d
    return None


# 配置意图 -> 命令映射（当LLM不能正确生成tool_calls时使用）
_CONFIG_MAP = [
    # (关键词列表, 命令模板)
    (['关闭lldp', '禁用lldp', '停用lldp'], 'system-view\nundo lldp global enable'),
    (['开启lldp', '启用lldp'], 'system-view\nlldp global enable'),
    (['保存配置', '保存'], 'save force'),
    (['重启设备', '重启'], 'reboot'),
]


def _match_config_command(message):
    """Try to match a config intent from the message when LLM returns text instead of tool_calls.
    Returns a command string if matched, None otherwise.
    """
    msg_lower = message.lower().strip()
    
    # 1. Simple keyword-based mapping
    for keywords, cmd_template in _CONFIG_MAP:
        if any(kw in msg_lower for kw in keywords):
            return cmd_template
    
    # 2. "关闭GE1/0/1" -> system-view + interface + shutdown
    port_match = re.search(r'(?:关闭|shutdown)\s*(?:接口|端口)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+)', message, re.IGNORECASE)
    if port_match:
        port = port_match.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        return f"system-view\ninterface {port}\nshutdown"
    
    # 3. "开启GE1/0/1" -> undo shutdown
    port_match = re.search(r'(?:开启|undo\s+shutdown)\s*(?:接口|端口)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+)', message, re.IGNORECASE)
    if port_match:
        port = port_match.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        return f"system-view\ninterface {port}\nundo shutdown"
    
    # 4. "创建VLAN X"
    vlan_match = re.search(r'创建\s*(?:VLAN|vlan)\s*(\d+)', message, re.IGNORECASE)
    if vlan_match:
        vid = vlan_match.group(1)
        return f"system-view\nvlan {vid}"
    
    # 5. "删除VLAN X"
    vlan_match = re.search(r'删除\s*(?:VLAN|vlan)\s*(\d+)', message, re.IGNORECASE)
    if vlan_match:
        vid = vlan_match.group(1)
        return f"system-view\nundo vlan {vid}"
    
    # 6. "把GE1/0/1划入VLAN 10"
    port_vlan = re.search(r'([GEgi][Ei]?\s*\d+/\d+/\d+).*?(?:划入|加入|分配到|放到)\s*(?:VLAN|vlan)\s*(\d+)', message, re.IGNORECASE)
    if port_vlan:
        port = port_vlan.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        vid = port_vlan.group(2)
        return f"system-view\ninterface {port}\nport access vlan {vid}"
    
    # 7. "GE1/0/1改成access口"
    port_type = re.search(r'([GEgi][Ei]?\s*\d+/\d+/\d+).*?改成?\s*(access|trunk)', message, re.IGNORECASE)
    if port_type:
        port = port_type.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        ptype = port_type.group(2).lower()
        return f"system-view\ninterface {port}\nport link-type {ptype}"
    
    # 8. "给GE1/0/1加描述xxx"
    port_desc = re.search(r'(?:给|为)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+).*?(?:加描述|设置描述|描述为|description)\s*(.+)', message, re.IGNORECASE)
    if port_desc:
        port = port_desc.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        desc = port_desc.group(2).strip()
        return f"system-view\ninterface {port}\ndescription {desc}"
    
    # 9. "设置GE1/0/1的IP为x.x.x.x/y"
    port_ip = re.search(r'(?:设置|配置)?\s*([GEgi][Ei]?\s*\d+/\d+/\d+).*?(?:IP|ip|地址).*?(\d+\.\d+\.\d+\.\d+/\d+)', message, re.IGNORECASE)
    if port_ip:
        port = port_ip.group(1).replace(' ', '').replace('GE', 'GigabitEthernet').replace('ge', 'GigabitEthernet').replace('Gi', 'GigabitEthernet')
        ip_mask = port_ip.group(2)
        return f"system-view\ninterface {port}\nport link-type route\nipv4 address {ip_mask}"
    
    return None


def _get_session_mgr():
    """获取SessionManager单例，避免每次请求new"""
    global _session_mgr
    if _session_mgr is None:
        from app.session import SessionManager

        session_dir = os.path.join(_data_dir, "sessions")
        _session_mgr = SessionManager(storage_dir=session_dir)
    return _session_mgr


def init_chat_blueprint(data_dir, devices_file, project_root):
    global _data_dir, _devices_file, _project_root
    _data_dir = data_dir
    _devices_file = devices_file
    _project_root = project_root


def _load_devices():
    return _shared_load_devices(_devices_file)


# 设备列表缓存（避免每次 chat 都重读+重新格式化）
_device_list_cache = {"mtime": 0, "devices_str": ""}


def _get_device_list_str():
    """获取格式化的设备列表字符串（带文件修改时间缓存）"""
    global _device_list_cache
    try:
        mtime = os.path.getmtime(_devices_file) if os.path.exists(_devices_file) else 0
    except OSError:
        mtime = 0

    if mtime != _device_list_cache["mtime"]:
        devices = _load_devices()
        _device_list_cache["mtime"] = mtime
        _device_list_cache["devices_str"] = "\n".join(
            [
                f"- {d.get('remark') or d.get('name')} ({d.get('ip')}, {d.get('vendor', 'unknown')})"
                for d in devices
            ]
        )
    return _device_list_cache["devices_str"]


@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """主聊天接口"""
    data = request.json or {}
    message = data.get("message", "").strip()
    device_name = data.get("device", "")
    session_id = data.get("session_id", "default")
    preview_only = data.get("preview_only", False)
    confirmed_commands = data.get("confirmed_commands")
    context = data.get("context", {})
    selected_device = context.get("selected_device", "") or device_name

    if not message and not confirmed_commands:
        return jsonify({"success": False, "message": "消息不能为空"})

    try:
        # 确认执行模式：直接执行已确认的命令
        if confirmed_commands:
            result = _do_exec_confirmed(confirmed_commands, session_id)
            return jsonify(result)

        result = _do_chat(
            message, selected_device, session_id, preview_only=preview_only
        )
        # 兼容前端：response = message
        if "message" in result and "response" not in result:
            result["response"] = result["message"]
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e), "response": str(e)})


@chat_bp.route("/api/chat/clear", methods=["POST"])
def chat_clear():
    """清除聊天会话"""
    data = request.json or {}
    session_id = data.get("session_id", "default")
    try:
        session_mgr = _get_session_mgr()
        session_mgr.delete_session(session_id)
        return jsonify({"success": True, "message": "会话已清除"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def _do_exec_confirmed(confirmed_commands, session_id="default"):
    """执行已确认的命令（用户确认后调用）"""
    from app.network.command_service import CommandService
    from app.session.models import TurnRole

    cmd_svc = CommandService()
    session_mgr = _get_session_mgr()
    devices = _load_devices()
    all_results = []

    for item in confirmed_commands:
        dev_name = item.get("device", "")
        commands = item.get("commands", [])
        if not commands:
            continue

        # 查找设备
        dev = None
        for d in devices:
            if (
                d.get("name") == dev_name
                or d.get("remark") == dev_name
                or d.get("ip") == dev_name
            ):
                dev = d
                break

        if not dev:
            all_results.append(
                {
                    "device": dev_name,
                    "error": f"设备 {dev_name} 不存在",
                    "success": False,
                }
            )
            continue

        dev_info = CommandService.device_from_dict(dev)
        cmd_result = cmd_svc.execute(
            dev_info, commands, user_id=session_id, source="confirmed"
        )

        if cmd_result.success:
            outputs = []
            for o in cmd_result.outputs:
                outputs.append(
                    f"命令: {o.get('command', '')}\n{o.get('output', '')[:500]}"
                )
            all_results.append(
                {
                    "device": dev_name,
                    "success": True,
                    "results": outputs,
                    "backup_id": cmd_result.backup_id,
                }
            )
        else:
            all_results.append(
                {
                    "device": dev_name,
                    "success": False,
                    "error": cmd_result.error,
                    "blocked": [c.command for c in (cmd_result.blocked_commands or [])],
                }
            )

    # 记录会话
    summary_parts = []
    for r in all_results:
        if r.get("success"):
            summary_parts.append(
                f"✅ {r['device']}: {len(r.get('results', []))} 条命令执行成功"
            )
        else:
            summary_parts.append(f"❌ {r['device']}: {r.get('error', '执行失败')}")
    summary = "\n".join(summary_parts)
    session_mgr.add_turn(session_id, TurnRole.ASSISTANT, f"已确认执行:\n{summary}")

    return {
        "success": all(r.get("success") for r in all_results) if all_results else False,
        "message": summary,
        "response": summary,
        "executed": True,
        "results": all_results,
    }


def _extract_commands_from_text(text, selected_device="", user_message=""):
    """从LLM文本回复中提取命令（fallback for models without function calling）"""
    # 只有用户明确请求执行操作时才提取
    EXEC_KEYWORDS = [
        "配置",
        "创建",
        "设置",
        "添加",
        "删除",
        "修改",
        "关闭",
        "开启",
        "执行",
        "下发",
        "应用",
        "部署",
        "开通",
        "关闭",
        "shutdown",
        "undo",
        "撤销",
        "取消",
        "no ",
    ]
    is_exec_intent = any(k in user_message for k in EXEC_KEYWORDS)
    if not is_exec_intent:
        return []

    planned = []
    # 提取 ```bash 或 ``` 代码块中的命令
    blocks = re.findall(r"```(?:bash|shell|sh)?\s*\n(.*?)```", text, re.DOTALL)
    if not blocks:
        return planned

    # 网络设备命令关键词（华为/H3C/Cisco/Juniper）
    CMD_PREFIXES = (
        "display ",
        "show ",
        "system-view",
        "configure",
        "interface ",
        "vlan ",
        "ip ",
        "port ",
        "undo ",
        "no ",
        "delete ",
        "ping ",
        "traceroute",
        "telnet ",
        "ssh ",
        "ospf ",
        "bgp ",
        "isis ",
        "mpls ",
        "acl ",
        "firewall ",
        "nat ",
        "snmp ",
        "ntp ",
        "syslog ",
        "stp ",
        "lacp ",
        "ethernet ",
        "router ",
        "switchport ",
        "commit",
        "rollback",
        "save",
        "quit",
        "return",
        "set ",
        "edit ",
        "top ",
    )

    commands = []
    for block in blocks:
        for line in block.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # 跳过中文行
            if re.search(r"[\u4e00-\u9fff]", line):
                continue
            # 只保留以网络命令前缀开头的行
            if any(line.lower().startswith(p) for p in CMD_PREFIXES):
                commands.append(line)

    if commands:
        planned.append(
            {
                "device": selected_device or "",
                "commands": commands,
            }
        )

    return planned


def _do_chat(message, selected_device, session_id="default", preview_only=False):
    """核心聊天逻辑"""
    from app.llm.config import LLMConfig, LLMClient, LLMConfigManager, _decrypt_api_key
    from app.session.models import TurnRole
    from netops_tools import NetOpsTools, get_tools_definition

    # 从 web/data/llm_config.json 加载配置（前端保存到此路径）
    llm_config_file = os.path.join(_data_dir, "llm_config.json")
    if os.path.exists(llm_config_file):
        try:
            with open(llm_config_file, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            config = LLMConfig(
                provider=cfg_data.get("provider", "openai"),
                endpoint=cfg_data.get("endpoint", "") or cfg_data.get("base_url", ""),
                api_key=_decrypt_api_key(cfg_data.get("api_key", "")),
                model=cfg_data.get("model", ""),
            )
            llm = LLMClient(config)
        except Exception as e:
            log_msg = f"加载LLM配置失败: {e}"
            return {"success": False, "message": log_msg}
    else:
        # 回退到 LLMConfigManager（读 config/llm_config.json）
        config = LLMConfigManager()
        llm = config.get_client()

    if not llm:
        return {"success": False, "message": "LLM 未配置，请先在设置中配置"}

    tools = NetOpsTools(_devices_file)
    session_mgr = _get_session_mgr()

    # 加载会话历史
    session = session_mgr.get_session(session_id)
    if not session:
        session = session_mgr.create_session(session_id)
    session_mgr.add_turn(session_id, TurnRole.USER, message)

    # 构建系统提示（使用缓存的设备列表字符串）
    devices = _load_devices()
    device_list_str = _get_device_list_str()

    system_prompt = f"""你是网络运维助手。当前选中设备：{selected_device or "未选择"}。
可用设备：{device_list_str}

重要：当前已选中设备时，直接对该设备执行命令，不要再询问用户选择设备。
直接调用 run_commands 工具，参数示例：
- 用户说"查看版本"→ run_commands(device="{selected_device or '设备名'}", commands=["display version"])
- 用户说"显示接口"→ run_commands(device="{selected_device or '设备名'}", commands=["display interface brief"])
- 用户说"创建VLAN 100"→ run_commands(device="{selected_device or '设备名'}", commands=["system-view","vlan 100","quit"])
- 用户说"关闭LLDP"→ run_commands(device="{selected_device or '设备名'}", commands=["system-view","undo lldp global enable"])
- 用户说"开启LLDP"→ run_commands(device="{selected_device or '设备名'}", commands=["system-view","lldp global enable"])
- 用户说"重启设备"→ run_commands(device="{selected_device or '设备名'}", commands=["reboot"])
- 用户说"保存配置"→ run_commands(device="{selected_device or '设备名'}", commands=["save force"])

规则：
1. 已选中设备时直接执行，不要确认
2. 配置命令（system-view/undo/接口配置等）需要走run_commands工具
3. 危险操作（重启、删除配置）必须警告
4. 华为/华三用display，思科用show
5. 配置操作必须包含system-view，不要只发display查看
"""

    # 如果已选中设备，在用户消息中附加设备信息，确保LLM能识别
    if selected_device:
        message = f"[当前设备：{selected_device}] {message}"

    # 构建消息列表
    messages = [{"role": "system", "content": system_prompt}]
    for turn in session.turns[-20:]:  # 最近20轮
        messages.append({"role": turn.role.value, "content": turn.content})

    # 调用LLM — 检测是否需要强制工具调用
    _ACTION_KEYWORDS = (
        '查看', '显示', '执行', '运行', '配置', '创建', '删除', '修改', '改成',
        'display', 'show', 'ping', 'traceroute', '版本', '接口', '路由',
        'vlan', 'arp', 'mac', 'lldp', 'ospf', 'bgp', 'cpu', '内存',
        '重启', '关闭', '开启', '备份', '恢复', '诊断', '改', '加', '设',
    )
    # 纯聊天关键词（不用工具）
    _CHAT_KEYWORDS = ('你好', '谢谢', '你是谁', '什么', '为什么', '怎么', '如何', '帮我', '解释', '区别')


    is_pure_chat = any(message.strip().startswith(kw) for kw in _CHAT_KEYWORDS) and not any(kw in message for kw in _ACTION_KEYWORDS)
    
    if selected_device and not is_pure_chat and any(kw in message for kw in _ACTION_KEYWORDS):
        tool_choice = "required"
    else:
        tool_choice = "auto"
    log.info(f"LLM chat: tool_choice={tool_choice}, device={selected_device}")

    response = llm.chat(messages=messages, tools=get_tools_definition(), tool_choice=tool_choice)

    # 处理工具调用
    if isinstance(response.get("tool_calls"), list) and response.get("tool_calls"):
        from app.network.command_service import CommandService

        cmd_svc = CommandService()
        planned_commands = []
        results = []

        for tc in response["tool_calls"]:
            tool_name = tc.get("function", {}).get("name", "")
            arguments = json.loads(tc.get("function", {}).get("arguments", "{}"))

            # 命令类工具 — 始终走预览+确认流程，不直接执行
            if tool_name in ("run_commands", "ssh_connect"):
                commands = arguments.get("commands", [])
                dev_name = arguments.get("device", "")
                if commands:
                    # 判断是否为只读命令（display/show/ping/traceroute）
                    # 注意：save需要Y/N确认，不属于只读
                    # 意图校验：如果用户意图是配置操作但LLM生成了查看命令，用意图映射覆盖
                    _config_intent = _match_config_command(message)
                    if _config_intent and _config_intent != commands:
                        # LLM没理解配置意图，用映射命令覆盖
                        log.info(f"Intent override: LLM={commands}, mapped={_config_intent}")
                        commands = _config_intent.split("\n")
                    
                    _READ_ONLY_PREFIXES = ("display ", "show ", "ping ", "traceroute", "tracert ")
                    all_readonly = all(
                        any(cmd.lower().strip().startswith(p) for p in _READ_ONLY_PREFIXES)
                        for cmd in commands
                    )
                    if all_readonly and not preview_only:
                        # 只读命令：直接执行，秒回
                        dev = _match_device(devices, dev_name)
                        if dev:
                            dev_info = CommandService.device_from_dict(dev)
                            cmd_result = cmd_svc.execute(
                                dev_info, commands, user_id=session_id, source="llm"
                            )
                            if not cmd_result.success:
                                results.append(
                                    {
                                        "tool": tool_name,
                                        "error": cmd_result.error,
                                        "blocked": bool(cmd_result.blocked_commands),
                                    }
                                )
                                continue
                            tool_result = {
                                "success": True,
                                "results": cmd_result.outputs,
                                "backup_id": cmd_result.backup_id,
                            }
                            results.append({"tool": tool_name, "result": tool_result})
                            continue
                    # 非只读命令：走预览流程
                    planned_commands.append(
                        {"device": dev_name, "commands": commands}
                    )
                    continue

            # 非命令类工具（如 list_devices）— 如果消息有命令意图，自动补 run_commands
            if tool_name == "list_devices" and selected_device and any(kw in message for kw in _ACTION_KEYWORDS):
                # LLM误选了list_devices，用命令模板匹配
                _QUERY_MAP = {
                    "版本": "display version",
                    "运行时间": "display version",
                    "启动时间": "display version",
                    "vlan": "display vlan",
                    "路由": "display ip routing-table",
                    "路由表": "display ip routing-table",
                    "arp": "display arp",
                    "接口": "display interface brief",
                    "mac": "display mac-address",
                    "配置": "display current-configuration",
                    "cpu": "display cpu-usage",
                    "内存": "display memory",
                    "日志": "display logbuffer",
                    "邻居": "display lldp neighbor-information list",
                    "告警": "display alarm",
                    "ospf": "display ospf peer",
                    "bgp": "display bgp peer",
                    "stp": "display stp",
                    "nat": "display nat session",
                    "acl": "display acl",
                    "环境": "display environment",
                    "风扇": "display fan",
                    "电源": "display power",
                    "流量": "display interface",
                }
                matched_cmd = None
                _CMD_PREFIXES = ("display ", "show ", "save", "ping ", "traceroute")
                if any(message.lower().startswith(p) for p in _CMD_PREFIXES):
                    matched_cmd = message.split("\n")[0].strip()
                else:
                    for kw, cmd in _QUERY_MAP.items():
                        if kw in message:
                            matched_cmd = cmd
                            break
                if matched_cmd:
                    # 覆盖为 run_commands
                    tool_name = "run_commands"
                    arguments = {"device": selected_device, "commands": [matched_cmd]}
                    # 走下面的 run_commands 逻辑
                    commands = [matched_cmd]
                    dev_name = selected_device
                    _READ_ONLY_PREFIXES = ("display ", "show ", "ping ", "traceroute", "tracert ")
                    all_readonly = any(cmd.lower().strip().startswith(p) for p in _READ_ONLY_PREFIXES for cmd in commands)
                    if all_readonly and not preview_only:
                        dev = _match_device(devices, dev_name)
                        if dev:
                            dev_info = CommandService.device_from_dict(dev)
                            cmd_result = cmd_svc.execute(dev_info, commands, user_id=session_id, source="llm")
                            if cmd_result.success:
                                results.append({"tool": "run_commands", "result": {"success": True, "results": cmd_result.outputs, "backup_id": cmd_result.backup_id}})
                                continue
                            else:
                                results.append({"tool": "run_commands", "error": cmd_result.error})
                                continue
                    planned_commands.append({"device": dev_name, "commands": commands})
                    continue
                else:
                    # 没匹配到命令，正常执行 list_devices
                    tool_result = tools.execute_tool(tool_name, arguments)
                    results.append({"tool": tool_name, "result": tool_result})
                    continue

            # 其他非命令类工具
            tool_result = tools.execute_tool(tool_name, arguments)
            results.append({"tool": tool_name, "result": tool_result})

        # 有计划命令（配置操作需确认）
        if planned_commands:
            session_mgr.add_turn(
                session_id,
                TurnRole.ASSISTANT,
                f"预览命令: {json.dumps(planned_commands, ensure_ascii=False)}",
            )
            return {
                "success": True,
                "preview": True,
                "planned_commands": planned_commands,
                "message": "配置命令预览已生成，请确认后执行",
                "response": "配置命令预览已生成，请确认后执行",
            }

        # LLM没生成命令工具调用，尝试配置命令映射
        if not results:
            content = response.get("content", "")
            # 尝试用_CONFIG_MAP匹配配置意图
            if selected_device and any(kw in message for kw in _ACTION_KEYWORDS):
                config_cmd = _match_config_command(message)
                if config_cmd:
                    planned_commands.append({"device": selected_device, "commands": [config_cmd]})
                    session_mgr.add_turn(session_id, TurnRole.ASSISTANT, f"预览命令: {json.dumps(planned_commands, ensure_ascii=False)}")
                    return {
                        "success": True,
                        "preview": True,
                        "planned_commands": planned_commands,
                        "message": f"将执行: {config_cmd}",
                        "response": f"将执行: {config_cmd}",
                    }
            session_mgr.add_turn(session_id, TurnRole.ASSISTANT, content)
            return {
                "success": True,
                "message": content,
                "response": content,
            }

        # 把工具结果反馈给LLM
        tool_summary = "\n".join(
            [
                f"工具 {r['tool']}: {json.dumps(r.get('result', r.get('error', '')), ensure_ascii=False)[:500]}"
                for r in results
            ]
        )
        session_mgr.add_turn(
            session_id, TurnRole.ASSISTANT, f"已执行工具，结果如下：\n{tool_summary}"
        )

        return {
            "success": True,
            "message": tool_summary,
            "response": tool_summary,
            "executed": True,
            "tool_calls": results,
        }

    # 普通回复 — 尝试从文本中提取命令（fallback for models without function calling）
    content = response.get("content", "")
    extracted = _extract_commands_from_text(content, selected_device, message)

    if extracted:
        session_mgr.add_turn(session_id, TurnRole.ASSISTANT, content)
        if preview_only:
            return {
                "success": True,
                "preview": True,
                "planned_commands": extracted,
                "message": content,
                "response": content,
            }
        else:
            # 非preview模式也只预览，等用户确认
            return {
                "success": True,
                "preview": True,
                "planned_commands": extracted,
                "message": content,
                "response": content,
            }

    session_mgr.add_turn(session_id, TurnRole.ASSISTANT, content)

    return {
        "success": True,
        "message": content,
        "response": content,
    }


@chat_bp.route("/api/quick-config", methods=["POST"])
def quick_config():
    """快速配置接口 — 模板优先"""
    data = request.json or {}
    device_name = data.get("device", "")
    config_type = data.get("type", "")
    parameters = data.get("parameters", {})
    mode = data.get("mode", "preview")  # preview=只返回命令, execute=执行

    if not device_name:
        return jsonify({"success": False, "message": "请指定设备"})

    # 查找设备
    devices = _load_devices()
    device = None
    for d in devices:
        if (
            d.get("name") == device_name
            or d.get("remark") == device_name
            or d.get("ip") == device_name
        ):
            device = d
            break

    if not device:
        return jsonify({"success": False, "message": f"设备 {device_name} 不存在"})

    vendor = device.get("vendor", "huawei")

    # mode=execute: 直接执行前端传来的命令
    if mode == "execute":
        exec_commands = []
        for item in data.get("commands") or []:
            if isinstance(item, dict):
                exec_commands.extend(item.get("commands", []))
            elif isinstance(item, str):
                exec_commands.append(item)
        if not exec_commands:
            return jsonify({"success": False, "message": "无命令可执行"})
        from app.network.command_service import CommandService

        dev_info = CommandService.device_from_dict(device)
        cmd_result = CommandService().execute(
            dev_info,
            exec_commands,
            source="quick-config",
        )
        result = {"success": cmd_result.success}
        if cmd_result.success:
            result["results"] = [
                {
                    "success": True,
                    "results": [
                        {"command": r.get("command", ""), "output": r.get("output", "")}
                        for r in (cmd_result.outputs or [])
                    ],
                }
            ]
        else:
            result["error"] = cmd_result.error or "执行失败"
        return jsonify(result)

    # mode=query: 快速查询（只读命令，直接执行）
    if mode == "query":
        query_commands = data.get("commands", [])
        if isinstance(query_commands, str):
            query_commands = [query_commands]
        if not query_commands:
            return jsonify({"success": False, "message": "无查询命令"})
        from app.network.command_service import CommandService

        dev_info = CommandService.device_from_dict(device)
        cmd_result = CommandService().execute(
            dev_info,
            query_commands,
            source="quick-config",
            skip_guard=True,  # 只读查询
        )
        result = {"success": cmd_result.success, "query": True}
        if cmd_result.success:
            result["results"] = [
                {
                    "success": True,
                    "results": [
                        {"command": r.get("command", ""), "output": r.get("output", "")}
                        for r in (cmd_result.outputs or [])
                    ],
                }
            ]
        else:
            result["error"] = cmd_result.error or "查询失败"
        return jsonify(result)

    # mode=preview: 快速模板匹配（秒回）
    message = data.get("message", "")
    if mode == "preview" and message and not config_type:
        # 简单自然语言匹配
        _QUERY_MAP = {
            "版本": "display version",
            "运行时间": "display version",
            "启动时间": "display version",
            "vlan": "display vlan",
            "路由": "display ip routing-table",
            "路由表": "display ip routing-table",
            "arp": "display arp",
            "接口": "display interface brief",
            "mac": "display mac-address",
            "配置": "display current-configuration",
            "cpu": "display cpu-usage",
            "内存": "display memory",
            "日志": "display logbuffer",
            "邻居": "display lldp neighbor-information list",
            "告警": "display alarm",
            "ospf": "display ospf peer",
            "bgp": "display bgp peer",
            "stp": "display stp",
            "nat": "display nat session",
            "acl": "display acl",
            "环境": "display environment",
            "风扇": "display fan",
            "电源": "display power",
            "流量": "display interface",
        }
        matched_cmd = None
        # 如果message本身是命令（display/show/save等），直接执行
        _CMD_PREFIXES = ("display ", "show ", "save", "ping ", "traceroute")
        if any(message.lower().startswith(p) for p in _CMD_PREFIXES):
            matched_cmd = message.split("\n")[0].strip()  # 取第一行
        else:
            for kw, cmd in _QUERY_MAP.items():
                if kw in message:
                    matched_cmd = cmd
                    break
        if matched_cmd:
            from app.network.command_service import CommandService

            dev_info = CommandService.device_from_dict(device)
            cmd_result = CommandService().execute(
                dev_info,
                [matched_cmd],
                source="quick-config",
                skip_guard=True,
            )
            result = {"success": cmd_result.success, "matched": True, "query": True}
            if cmd_result.success:
                result["results"] = [
                    {
                        "success": True,
                        "results": [
                            {
                                "command": r.get("command", ""),
                                "output": r.get("output", ""),
                            }
                            for r in (cmd_result.outputs or [])
                        ],
                    }
                ]
            else:
                result["error"] = cmd_result.error or "查询失败"
            return jsonify(result)
        # 没匹配到，返回空让前端走LLM
        return jsonify({"success": True, "matched": False})

    # 1. 模板优先
    netmiko_type = {
        "huawei": "huawei",
        "h3c": "huawei",
        "cisco": "cisco_ios",
        "juniper": "juniper_junos",
    }.get(vendor, "huawei")
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
            return jsonify(
                {
                    "success": False,
                    "message": "命令安全检查未通过",
                    "blocked": check.blocked_commands,
                }
            )

        return jsonify(
            {
                "success": True,
                "preview": True,
                "commands": template_commands,
                "source": "template",
                "device": device_name,
                "vendor": vendor,
                "requires_confirmation": True,
            }
        )

    # 2. LLM兜底
    from app.llm.config import LLMConfigManager

    llm = LLMConfigManager().get_client()
    if not llm:
        return jsonify({"success": False, "message": "LLM未配置"})

    prompt = f"""为 {vendor} 设备 {device_name} 生成配置命令。
配置类型: {config_type}
参数: {json.dumps(parameters, ensure_ascii=False)}

请返回JSON格式的命令列表，例如: ["system-view", "vlan 10", ...]
只返回JSON，不要其他内容。"""

    try:
        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.get("content", "").strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        commands = json.loads(content.strip())

        return jsonify(
            {
                "success": True,
                "commands": commands,
                "source": "llm",
                "device": device_name,
                "vendor": vendor,
                "requires_confirmation": True,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"生成配置失败: {e}"})


@chat_bp.route("/api/diagnose", methods=["POST"])
def api_diagnose():
    """诊断接口 — 统一走 CommandService"""
    data = request.json or {}
    device_name = data.get("device", "")
    diagnose_type = data.get("type", "connectivity")

    if not device_name:
        return jsonify({"success": False, "message": "请指定设备"})

    devices = _load_devices()
    device = None
    for d in devices:
        if (
            d.get("name") == device_name
            or d.get("remark") == device_name
            or d.get("ip") == device_name
        ):
            device = d
            break

    if not device:
        return jsonify({"success": False, "message": f"设备 {device_name} 不存在"})

    vendor = device.get("vendor", "huawei")

    # 获取诊断命令
    if vendor in ("huawei", "h3c"):
        cmd_map = {
            "connectivity": [
                "display arp",
                "display mac-address",
                "display interface brief",
            ],
            "routing": ["display ip routing-table", "display ospf peer"],
            "vlan": ["display vlan", "display interface brief"],
            "interface": ["display interface", "display link-aggregation summary"],
        }
    else:
        cmd_map = {
            "connectivity": ["ping ", "show arp", "show mac address-table"],
            "routing": ["show ip route", "show ip ospf neighbor"],
            "vlan": ["show vlan", "show interfaces status"],
            "interface": ["show interfaces", "show etherchannel summary"],
        }

    commands = cmd_map.get(diagnose_type, cmd_map["connectivity"])

    # ping需要目标，无目标则跳过ping命令
    if diagnose_type == "connectivity":
        if data.get("target"):
            commands[0] = f"{commands[0].strip()} {data['target']}"
        else:
            commands = [c for c in commands if not c.strip().startswith("ping")]

    # 统一走 CommandService（含安全检查）
    from app.network.command_service import CommandService

    dev_info = CommandService.device_from_dict(device)
    cmd_result = CommandService().execute(
        dev_info,
        commands,
        source="diagnosis",
        skip_guard=True,  # 诊断命令都是只读查询，跳过 CommandGuard
    )

    result = {"success": cmd_result.success}
    if cmd_result.success:
        result["results"] = cmd_result.outputs
        analysis = _analyze_diagnosis(cmd_result.outputs, diagnose_type)
        result["analysis"] = analysis
        # 构建前端期望的 steps/root_cause/suggestions 格式
        steps = []
        fail_count = 0
        findings = analysis.get("findings", [])
        finding_idx = 0
        error_patterns = [
            "wrong parameter",
            "unrecognized command",
            "incomplete command",
            "error:",
            "syntax error",
            "invalid input",
            "% ",
        ]
        for r in cmd_result.outputs:
            cmd = r.get("command", "")
            output = r.get("output", "")
            status = "PASS"
            message = output[:200].replace("\n", " ").strip() if output else "无输出"
            suggestion = ""
            # 检测命令执行错误
            output_lower = output.lower()
            is_error = any(p in output_lower for p in error_patterns)
            if is_error:
                status = "WARNING"
                message = f"命令不支持或执行失败: {cmd}"
            # 按顺序匹配findings（仅对非错误命令）
            elif finding_idx < len(findings):
                f = findings[finding_idx]
                if "❌" in f:
                    status = "FAIL"
                    fail_count += 1
                elif "⚠️" in f:
                    status = "WARNING"
                message = f.replace("❌", "").replace("⚠️", "").replace("✅", "").strip()
                finding_idx += 1
            steps.append(
                {
                    "step": cmd,
                    "status": status,
                    "message": message,
                    "suggestion": suggestion,
                }
            )
        result["steps"] = steps
        if fail_count > 0:
            result["root_cause"] = f"{diagnose_type}诊断发现 {fail_count} 个失败项"
            result["suggestions"] = ["请检查对应配置并修复"]
        else:
            result["root_cause"] = ""
            result["suggestions"] = []
    else:
        result["message"] = cmd_result.error
        result["steps"] = []
        result["root_cause"] = cmd_result.error
        result["suggestions"] = []

    return jsonify(result)


def _analyze_diagnosis(results, diagnose_type):
    """简单分析诊断结果"""
    analysis = {"type": diagnose_type, "findings": [], "status": "unknown"}

    for r in results:
        output = r.get("output", "").lower()
        cmd = r.get("command", "")

        # 检测命令执行错误
        error_sigs = [
            "wrong parameter",
            "unrecognized command",
            "incomplete command",
            "syntax error",
            "invalid input",
        ]
        if any(sig in output for sig in error_sigs):
            analysis["findings"].append("⚠️ 命令不支持或执行失败")
            continue

        if "ping" in cmd:
            if "100% packet loss" in output or "0 packets received" in output:
                analysis["findings"].append("❌ Ping 100%丢包")
                analysis["status"] = "fail"
            elif "packet loss" in output:
                analysis["findings"].append("⚠️ Ping 有丢包")
                analysis["status"] = "partial"
            else:
                analysis["findings"].append("✅ Ping 正常")
                analysis["status"] = "ok"

        elif "arp" in cmd:
            if not output.strip() or len(output.strip()) < 20:
                analysis["findings"].append("⚠️ ARP表为空")
            else:
                lines = [
                    link
                    for link in output.split("\n")
                    if link.strip() and not link.strip().startswith(("Age", "IP", "-"))
                ]
                analysis["findings"].append(f"ARP表有 {len(lines)} 条记录")

        elif "route" in cmd:
            if "0 routes" in output or not output.strip():
                analysis["findings"].append("⚠️ 路由表为空")
            else:
                analysis["findings"].append("✅ 路由表有条目")

        elif "ospf" in cmd:
            if "not configured" in output or "not enabled" in output:
                analysis["findings"].append("⚠️ OSPF未配置")
            elif "full" in output or "neighbor" in output:
                analysis["findings"].append("✅ OSPF邻居正常")
            else:
                analysis["findings"].append("ℹ️ OSPF无邻居")

        elif "vlan" in cmd:
            if not output.strip() or "no vlans" in output:
                analysis["findings"].append("⚠️ 无VLAN")
            else:
                analysis["findings"].append("✅ VLAN配置正常")

        elif "interface" in cmd and "brief" not in cmd:
            if "down" in output and "up" not in output:
                analysis["findings"].append("⚠️ 接口全部down")
            else:
                analysis["findings"].append("✅ 接口状态正常")

        elif "mac-address" in cmd or "mac address" in cmd:
            if not output.strip() or len(output.strip()) < 20:
                analysis["findings"].append("⚠️ MAC表为空")
            else:
                analysis["findings"].append("✅ MAC表有条目")

    return analysis


@chat_bp.route("/api/rollback", methods=["POST"])
def api_rollback():
    """回滚配置"""
    data = request.json or {}
    device_name = data.get("device", "")
    snapshot_id = data.get("snapshot_id", "")

    if not device_name or not snapshot_id:
        return jsonify({"success": False, "message": "请指定设备和快照ID"})

    from netops_tools import NetOpsTools

    tools = NetOpsTools(_devices_file)
    result = tools.rollback_config(device_name, snapshot_id)
    return jsonify(result)


@chat_bp.route("/api/snapshots", methods=["GET"])
def api_snapshots():
    """获取配置快照列表"""
    snapshot_dir = os.path.join(_data_dir, "snapshots")
    if not os.path.exists(snapshot_dir):
        return jsonify({"success": True, "snapshots": []})

    snapshots = []
    for f in sorted(os.listdir(snapshot_dir), reverse=True):
        if f.endswith(".cfg"):
            snapshots.append(
                {
                    "id": f[:-4],
                    "file": f,
                    "size": os.path.getsize(os.path.join(snapshot_dir, f)),
                    "time": time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(os.path.getmtime(os.path.join(snapshot_dir, f))),
                    ),
                }
            )

    return jsonify({"success": True, "snapshots": snapshots})


@chat_bp.route("/api/config/diff", methods=["POST"])
def config_diff():
    """配置对比"""
    from app.diagnosis.config_diff import ConfigDiff

    data = request.json or {}
    data.get("device_ip", "")
    old_config = data.get("old_config", "")
    new_config = data.get("new_config", "")
    old_file = data.get("old_file", "")
    new_file = data.get("new_file", "")

    differ = ConfigDiff(storage_dir=os.path.join(_data_dir, "config_snapshots"))

    # 从文件加载
    if old_file and not old_config:
        old_config = differ.load_config_file(old_file)
    if new_file and not new_config:
        new_config = differ.load_config_file(new_file)

    if not old_config or not new_config:
        return jsonify({"success": False, "message": "请提供两个配置内容或文件路径"})

    result = differ.diff_configs(old_config, new_config)
    sections = differ.diff_sections(old_config, new_config)

    return jsonify(
        {
            "success": True,
            "has_changes": result["has_changes"],
            "summary": result["summary"],
            "added": result["added"][:50],
            "removed": result["removed"][:50],
            "unified_diff": result["unified_diff"][:10000],
            "sections": sections[:20],
        }
    )


@chat_bp.route("/api/config/snapshot", methods=["POST"])
def config_snapshot():
    """保存配置快照"""
    from app.diagnosis.config_diff import ConfigDiff

    data = request.json or {}
    device_name = data.get("device", "")
    device_ip = data.get("device_ip", "")
    config = data.get("config", "")
    label = data.get("label", "manual")

    # 如果没传config，自动采集
    if not config and (device_name or device_ip):
        from netops_tools import NetOpsTools

        tools = NetOpsTools(_devices_file)
        devices = tools.load_devices()
        device = None
        for d in devices:
            if (
                d.get("id") == device_name
                or d.get("remark") == device_name
                or d.get("ip") == device_ip
                or d.get("ip") == device_name
            ):
                device = d
                break
        if not device:
            return jsonify(
                {"success": False, "message": f"设备 {device_name or device_ip} 不存在"}
            )
        dev_id = device.get("remark") or device.get("name") or device.get("ip")
        vendor = device.get("vendor", "huawei")
        # 选择配置命令
        if vendor in ("huawei", "h3c"):
            cmd = "display current-configuration"
        elif vendor == "cisco":
            cmd = "show running-config"
        else:
            cmd = "show running-config"
        result = tools.execute_tool(
            "run_commands", {"device": dev_id, "commands": [cmd]}
        )
        if result.get("success") and result.get("results"):
            config = result["results"][0].get("output", "")
            device_ip = device.get("ip", device_ip)
        else:
            return jsonify(
                {
                    "success": False,
                    "message": f"采集配置失败: {result.get('message', '未知错误')}",
                }
            )

    if not device_ip or not config:
        return jsonify({"success": False, "message": "缺少 device_ip 或 config"})

    differ = ConfigDiff(storage_dir=os.path.join(_data_dir, "config_snapshots"))
    filepath = differ.save_config(device_ip, config, label)

    return jsonify({"success": True, "snapshot_id": filepath, "filepath": filepath})
