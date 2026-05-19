#!/usr/bin/env python3
"""
拓扑蓝图 - 拓扑发现、渲染、模板管理
"""

from flask import Blueprint, request, jsonify
import json
import os
import re
import time
import threading

from app.logger import get_logger
from .shared import load_devices, save_devices, get_devices_lock, atomic_write_json
import threading

log = get_logger(__name__)

topology_bp = Blueprint("topology", __name__)

# 文件读写锁，防止并发写入导致JSON损坏
_devices_lock = get_devices_lock()
_topo_lock = threading.Lock()

# 这些在 register 时由 init_app 注入
_data_dir = ""
_devices_file = ""


def init_topology_blueprint(data_dir, devices_file):
    global _data_dir, _devices_file
    _data_dir = data_dir
    _devices_file = devices_file


def _topology_file():
    return os.path.join(_data_dir, "topology_state.json")


def _templates_file():
    return os.path.join(_data_dir, "topology_templates.json")


def _load_topology_state():
    tf = _topology_file()
    if os.path.exists(tf):
        with open(tf, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"nodes": [], "links": [], "version": 1}


def _save_topology_state(state):
    tf = _topology_file()
    os.makedirs(os.path.dirname(tf), exist_ok=True)
    with _topo_lock:
        _tmp = tf + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(_tmp, tf)


def _load_topology_templates():
    ttf = _templates_file()
    if os.path.exists(ttf):
        with open(ttf, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_topology_templates(templates):
    ttf = _templates_file()
    os.makedirs(os.path.dirname(ttf), exist_ok=True)
    _tmp = ttf + ".tmp"
    with open(_tmp, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)
    os.replace(_tmp, ttf)


def _load_devices():
    return load_devices(_devices_file)


# ===== 路由 =====


@topology_bp.route("/api/topology/state", methods=["GET", "PATCH"])
def topology_state():
    if request.method == "GET":
        state = _load_topology_state()
        # 动态合并 devices.json 的 last_collected 到节点
        devices = _load_devices()
        dev_map = {d.get("id"): d for d in devices}
        for n in state.get("nodes", []):
            d = dev_map.get(n.get("id"))
            if d and d.get("facts", {}).get("last_collected"):
                if not n.get("facts"):
                    n["facts"] = {}
                n["facts"]["last_collected"] = d["facts"]["last_collected"]
        state["success"] = True
        return jsonify(state)
    else:
        data = request.json or {}
        state = _load_topology_state()
        if "nodes" in data:
            state["nodes"] = data["nodes"]
        if "links" in data:
            state["links"] = data["links"]
        state["version"] = int(state.get("version", 1)) + 1
        _save_topology_state(state)
        return jsonify({"success": True})


@topology_bp.route("/api/topology/template/list", methods=["GET"])
def topology_template_list():
    templates = _load_topology_templates()
    return jsonify({"success": True, "templates": templates})


@topology_bp.route("/api/topology/template/save", methods=["POST"])
def topology_template_save():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "message": "模板名称不能为空"})

    templates = _load_topology_templates()
    state = _load_topology_state()

    template = {
        "name": name,
        "nodes": state.get("nodes", []),
        "links": state.get("links", []),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 更新或追加
    for i, t in enumerate(templates):
        if t.get("name") == name:
            templates[i] = template
            break
    else:
        templates.append(template)

    _save_topology_templates(templates)
    return jsonify({"success": True})


@topology_bp.route("/api/topology/template/load", methods=["POST"])
def topology_template_load():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "message": "模板名称不能为空"})

    templates = _load_topology_templates()
    for t in templates:
        if t.get("name") == name:
            state = _load_topology_state()
            state["nodes"] = t.get("nodes", [])
            state["links"] = t.get("links", [])
            state["version"] = int(state.get("version", 1)) + 1
            _save_topology_state(state)
            return jsonify({"success": True})

    return jsonify({"success": False, "message": f'模板 "{name}" 不存在'})


def _extract_topology_links(text, local_name):
    """从LLDP/CDP输出提取拓扑链接"""
    links = []
    if not text or not local_name:
        return links

    # H3C/华为 list格式: 表格行
    # 格式1: "Local Interface  Chassis ID  Port ID  System Name"
    # 格式2: "LocalIf  Nbr chassis ID  Nbr port ID  Nbr system name"
    if re.search(
        r"Local(?:If| Interface)\s+(?:Nbr\s+)?(?:Chassis|chassis)\s+ID",
        text,
        re.IGNORECASE,
    ):
        for line in text.strip().split("\n"):
            # 跳过表头行
            if re.match(r"Local", line.strip(), re.IGNORECASE):
                continue
            # 尝试4列匹配（含System Name）
            m = re.match(
                r"((?:GE|XGE|10GE|40GE|100GE|Eth|Ethernet|GigabitEthernet)\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
                line.strip(),
            )
            if m:
                links.append(
                    {
                        "from_name": local_name,
                        "from_port": m.group(1),
                        "to_name": m.group(4),
                        "to_port": m.group(3),
                        "chassis_id": m.group(2),
                    }
                )
                continue
            # 3列匹配（无System Name，用Chassis ID标识）
            m = re.match(
                r"((?:GE|XGE|10GE|40GE|100GE|Eth|Ethernet|GigabitEthernet)\S+)\s+(\S+)\s+(\S+)",
                line.strip(),
            )
            if m:
                links.append(
                    {
                        "from_name": local_name,
                        "from_port": m.group(1),
                        "to_name": "",  # 无System Name，后续用chassis_id匹配
                        "to_port": m.group(3),
                        "chassis_id": m.group(2),
                    }
                )
        if links:
            return links

    lines = text.strip().split("\n")
    current_entry = {}

    for line in lines:
        line = line.strip()

        # 华为 LLDP 格式
        if "Port identifier" in line or "local interface" in line.lower():
            m = re.search(
                r"(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?",
                line,
                re.IGNORECASE,
            )
            if m:
                current_entry["local_port"] = m.group(0)

        elif "Neighbor interface" in line or "neighbor interface" in line.lower():
            m = re.search(
                r"(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?",
                line,
                re.IGNORECASE,
            )
            if m:
                current_entry["neighbor_port"] = m.group(0)

        elif "Neighbor port id" in line or "port id" in line.lower():
            m = re.search(
                r"(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?",
                line,
                re.IGNORECASE,
            )
            if not m:
                m = re.search(r"(Gi|Te|Fa)\d+/\d+", line, re.IGNORECASE)
            if m:
                if "neighbor_port" not in current_entry:
                    current_entry["neighbor_port"] = m.group(0)

        elif "System name" in line or "system name" in line.lower():
            m = re.search(r"System name\s*:\s*(.+)", line)
            if not m:
                m = re.search(r"System Name\s*:\s*(.+)", line)
            if m:
                current_entry["neighbor_name"] = m.group(1).strip()

        # 思科 CDP 格式
        elif "Platform" in line and "cisco" in line.lower():
            m = re.search(r"Platform:\s*(\S+)", line)
            if m:
                current_entry["neighbor_platform"] = m.group(1)

        elif "Interface" in line and re.search(
            r"GigabitEthernet|FastEthernet|TenGig", line
        ):
            m = re.search(
                r"(GigabitEthernet|FastEthernet|TenGig|Gi|Te|Fa)\d+(?:/\d+)*(?:\.\d+)?",
                line,
                re.IGNORECASE,
            )
            if m:
                if "local_port" not in current_entry:
                    current_entry["local_port"] = m.group(0)
                else:
                    current_entry["neighbor_port"] = m.group(0)

        # 空行表示一条记录结束
        if (
            not line
            and current_entry.get("neighbor_name")
            and current_entry.get("local_port")
        ):
            links.append(
                {
                    "from_name": local_name,
                    "from_port": current_entry["local_port"],
                    "to_name": current_entry["neighbor_name"],
                    "to_port": current_entry.get("neighbor_port", ""),
                }
            )
            current_entry = {}

    # 最后一条
    if current_entry.get("neighbor_name") and current_entry.get("local_port"):
        links.append(
            {
                "from_name": local_name,
                "from_port": current_entry["local_port"],
                "to_name": current_entry["neighbor_name"],
                "to_port": current_entry.get("neighbor_port", ""),
            }
        )

    return links


def _check_port_status(tools, device_name, vendor, port_name):
    """检查端口物理/协议状态，返回 (phy_up, proto_up, raw_line)"""
    # 先关闭分页，避免长输出被截断
    if vendor in ("huawei", "h3c", "auto"):
        cmds = ["screen-length disable", f"display interface {port_name}"]
    elif vendor in ("cisco", "ruckus"):
        cmds = ["terminal length 0", f"show interface {port_name}"]
    elif vendor == "juniper":
        cmds = ["set cli screen-length 0", f"show interface {port_name} extensive"]
    else:
        cmds = ["screen-length disable", f"display interface {port_name}"]

    try:
        result = tools.execute_tool(
            "run_commands",
            {"device": device_name, "commands": cmds},
        )
        # run_commands 返回 {success, results: [{command, output}]}
        # 取最后一条命令的输出（display/show命令）
        if isinstance(result, dict) and result.get("success") and result.get("results"):
            output = result["results"][-1].get("output", "")
        elif isinstance(result, dict) and result.get("error"):
            log.warning(f"_check_port_status: {device_name} {port_name} error: {result['error']}")
            return None, None, ""
        else:
            log.warning(f"_check_port_status: {device_name} {port_name} unexpected result: {str(result)[:200]}")
            output = str(result)
    except Exception as e:
        log.warning(f"_check_port_status: {device_name} {port_name} failed: {e}")
        return None, None, ""

    # 解析端口状态
    phy_up = None
    proto_up = None

    if vendor in ("huawei", "h3c", "auto"):
        # H3C/华为/auto: "current state: UP/DOWN"  和  "Line protocol current state: UP/DOWN"
        import re
        m_phy = re.search(r"current state\s*:\s*(UP|DOWN)", output, re.IGNORECASE)
        m_proto = re.search(r"Line protocol.*?(?:current state\s*:\s*|state\s*:\s*)(UP|DOWN)", output, re.IGNORECASE)
        if m_phy:
            phy_up = m_phy.group(1).upper() == "UP"
        if m_proto:
            proto_up = m_proto.group(1).upper() == "UP"
    elif vendor in ("cisco", "ruckus"):
        import re
        # Cisco: "... is up/down, line protocol is up/down"
        m = re.search(r"is\s+(up|down|administratively down).*?line protocol is\s+(up|down)", output, re.IGNORECASE)
        if m:
            admin_down = "administratively" in m.group(1).lower()
            phy_up = False if admin_down else m.group(1).lower() == "up"
            proto_up = m.group(2).lower() == "up"
    elif vendor == "juniper":
        import re
        m = re.search(r"operational:\s*(up|down)", output, re.IGNORECASE)
        m2 = re.search(r"admin:\s*(up|down)", output, re.IGNORECASE)
        if m:
            phy_up = m.group(1).lower() == "up"
        if m2 and m2.group(1).lower() == "down":
            phy_up = False  # admin down

    log.debug(f"_check_port_status: {device_name} {port_name} phy_up={phy_up} proto_up={proto_up}")
    return phy_up, proto_up, output


def _classify_lost_link(phy_up, proto_up):
    """根据端口状态分类链路丢失原因
    返回: physical_down / admin_down / lldp_timeout
    """
    if phy_up is None:
        return "lldp_timeout"  # 无法检测，默认LLDP超时
    if not phy_up and proto_up is not None and not proto_up:
        return "physical_down"  # 物理down
    if not phy_up and proto_up is None:
        return "admin_down"  # 管理down (administratively down)
    if phy_up and not proto_up:
        return "admin_down"  # 物理up协议down → shutdown
    if phy_up and proto_up:
        return "lldp_timeout"  # 端口正常但LLDP邻居消失
    # 不应该到这里
    return "lldp_timeout"


def _try_enable_lldp(tools, device_name, vendor):
    """尝试在设备上开启LLDP"""
    enable_cmds = {
        "h3c": ["return", "system-view", "lldp global enable", "return"],
        "huawei": ["return", "system-view", "lldp enable", "return"],
        "cisco": ["end", "configure terminal", "lldp run", "end"],
        "ruckus": ["end", "configure terminal", "lldp run", "end"],
        "juniper": ["exit", "configure", "set protocols lldp interface all", "commit and-quit"],
    }
    cmds = enable_cmds.get(vendor)
    if not cmds:
        for v in ("h3c", "cisco", "juniper"):
            c = enable_cmds.get(v)
            if c:
                log.info(f"LLDP enable: trying {v} commands on {device_name}")
                result = tools.execute_tool(
                    "run_commands", {"device": device_name, "commands": c}
                )
                if result.get("success"):
                    log.info(f"LLDP enable: {device_name} enabled with {v} commands")
                    return True
        return False
    log.info(f"LLDP enable: enabling on {device_name} with {vendor} commands")
    result = tools.execute_tool(
        "run_commands", {"device": device_name, "commands": cmds}
    )
    return result.get("success", False)


def _is_lldp_not_enabled(text):
    """检查LLDP输出是否表明LLDP未开启"""
    not_enabled_hints = [
        "LLDP is not enabled",
        "LLDP is not enabled globally",
        "LLDP is disabled",
        "LLDP is not configured",
        "lldp is not configured",
        "lldp not enabled",
        "lldp is not running",
        "LLDP is not running",
        "Global status of LLDP: Disable",
        "global status of lldp: disable",
    ]
    t = (text or "").strip()
    if not t:
        return True
    return any(hint.lower() in t.lower() for hint in not_enabled_hints)


def ensure_lldp_on_all_devices(devices, force=False):
    """确保所有设备的LLDP信息已采集"""
    from netops_tools import NetOpsTools

    tools = NetOpsTools(_devices_file)
    updated = []

    for d in devices:
        name = d.get("remark") or d.get("name")
        if not name:
            continue

        # 跳过离线设备（TCP端口检测）
        _ip = d.get("ip", "")
        _port = d.get("port", 22)
        if _ip:
            try:
                import socket as _sock
                _s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                _s.settimeout(3)
                _r = _s.connect_ex((_ip, int(_port)))
                _s.close()
                if _r != 0:
                    log.info(f"ensure_lldp: {name} offline (port {_port} unreachable), skipping")
                    d["_lldp_status"] = "offline"
                    updated.append(d)
                    continue
            except Exception as _e:
                log.debug(f"ensure_lldp: {name} online check failed: {_e}, skipping")
                d["_lldp_status"] = "offline"
                updated.append(d)
                continue

        if d.get("lldp_neighbors") and not force:
            log.debug(f"ensure_lldp: {name} already has LLDP data, skipping")
            updated.append(d)
            continue

        try:
            vendor = d.get("vendor", "auto")
            if vendor in ("huawei", "h3c"):
                cmds_list = [["display lldp neighbor-information list"]]
            elif vendor in ("cisco", "ruckus"):
                cmds_list = [["show lldp neighbors detail"]]
            elif vendor == "juniper":
                cmds_list = [["show lldp neighbors"]]
            else:
                cmds_list = [
                    ["display lldp neighbor-information list"],
                    ["show lldp neighbors detail"],
                    ["show lldp neighbors"],
                ]

            lldp_ok = False
            for cmds in cmds_list:
                log.debug(f"LLDP discover: device={name}, vendor={vendor}, cmds={cmds}")
                result = tools.execute_tool(
                    "run_commands", {"device": name, "commands": cmds}
                )
                if result.get("success") and result.get("results"):
                    lldp_text = result["results"][0].get("output", "")
                    if any(
                        err in lldp_text
                        for err in [
                            "Unrecognized command",
                            "Invalid input",
                            "% Error",
                            "Error:",
                            "Syntax error",
                        ]
                    ):
                        log.info(f"LLDP discover: {name} command failed for {cmds}, trying next")
                        continue

                    # LLDP未开启 → 自动尝试开启
                    if _is_lldp_not_enabled(lldp_text):
                        if _try_enable_lldp(tools, name, vendor):
                            log.info(f"LLDP discover: {name} LLDP not enabled, auto-enabling")
                            d["_lldp_status"] = "auto_enabled"
                            time.sleep(2)
                            result2 = tools.execute_tool(
                                "run_commands", {"device": name, "commands": cmds}
                            )
                            if result2.get("success") and result2.get("results"):
                                lldp_text = result2["results"][0].get("output", "")
                                log.info(f"LLDP discover: {name} re-read after enable, output_len={len(lldp_text)}")
                        else:
                            log.warning(f"LLDP discover: {name} failed to enable LLDP")
                            d["_lldp_status"] = "enable_failed"
                    else:
                        d["_lldp_status"] = "enabled"

                    d["lldp_neighbors"] = _extract_topology_links(lldp_text, name)
                    # LLDP已开启但无邻居 → enabled_no_nbr
                    if d.get("_lldp_status") == "enabled" and not d["lldp_neighbors"]:
                        d["_lldp_status"] = "enabled_no_nbr"
                    log.debug(
                        f"LLDP discover: {name} parsed {len(d.get('lldp_neighbors', []))} neighbors, output_len={len(lldp_text)}"
                    )
                    if not d["lldp_neighbors"] and lldp_text:
                        log.info(f"LLDP discover: {name} raw output: {lldp_text[:300]}")
                    updated.append(d)
                    lldp_ok = True
                    break
            if not lldp_ok:
                log.warning(f"LLDP discover: {name} all LLDP commands failed")
                d["_lldp_status"] = "disabled"
                updated.append(d)

            # 采集sysname/hostname（不管LLDP是否成功）
            try:
                if not d.get("sysname") or not (d.get("facts") or {}).get("hostname"):
                    # H3C/华为: display current-configuration | include sysname
                    # Cisco: show hostname
                    # 通用: 从任意命令输出的提示符中提取 <sysname> 或 [sysname]
                    sysname_cmds = ["display current-configuration | include sysname"]
                    sn_result = tools.execute_tool(
                        "run_commands", {"device": name, "commands": sysname_cmds}
                    )
                    # 如果上面失败，尝试 display version（提示符包含sysname）
                    if not sn_result.get("success") or not sn_result.get("results"):
                        sn_result2 = tools.execute_tool(
                            "run_commands", {"device": name, "commands": ["display version"]}
                        )
                        if sn_result2.get("success") and sn_result2.get("results"):
                            sn_result = sn_result2
                    if sn_result.get("success") and sn_result.get("results"):
                        sn_text = sn_result["results"][0].get("output", "")
                        sn = ""
                        # 方法1: 从sysname配置行提取
                        import re as _re
                        m = _re.search(r'^\s*sysname\s+(\S+)', sn_text, _re.MULTILINE)
                        if m:
                            sn = m.group(1)
                        else:
                            # 方法2: 从提示符提取 <sysname> 或 [sysname]
                            prompts = _re.findall(r'[<\[]([\w\-]+)[>\]]', sn_text)
                            if prompts:
                                sn = prompts[-1]  # 最后一个提示符最可靠
                        if sn:
                            d["sysname"] = sn
                            if not d.get("facts"):
                                d["facts"] = {}
                            d["facts"]["hostname"] = sn
                            log.info(f"LLDP discover: {name} sysname={sn}")
            except Exception as e:
                log.debug(f"LLDP discover: {name} sysname collection skipped: {e}")

            # 采集本地chassis_id（用于LLDP邻居匹配，比sysname更可靠）
            try:
                if not d.get("chassis_id"):
                    cid_cmds = ["screen-length disable", "display lldp local-information"]
                    cid_result = tools.execute_tool(
                        "run_commands", {"device": name, "commands": cid_cmds}
                    )
                    if cid_result.get("success") and cid_result.get("results"):
                        for res in cid_result.get("results", []):
                            cid_text = res.get("output", "")
                            m = re.search(r"Chassis ID\s*:\s*(\S+)", cid_text)
                            if m:
                                d["chassis_id"] = m.group(1)
                                log.info(f"LLDP discover: {name} local chassis_id={m.group(1)}")
                                break
                    if not d.get("chassis_id"):
                        log.debug(f"LLDP discover: {name} failed to get local chassis_id")
            except Exception as e:
                log.debug(f"LLDP discover: {name} chassis_id collection skipped: {e}")

        except Exception as e:
            log.warning(f"LLDP discover: {name} exception: {e}")
            updated.append(d)

    log.info(
        f"ensure_lldp done: {sum(1 for d in updated if d.get('lldp_neighbors'))}/{len(devices)} devices have LLDP"
    )
    return updated


@topology_bp.route("/api/topology/discover", methods=["POST", "GET"])
def topology_discover():
    """拓扑发现"""
    from netops_tools import NetOpsTools

    NetOpsTools(_devices_file)
    data = request.json or {}
    device_filter = data.get("devices", [])

    devices = _load_devices()
    if device_filter:
        devices = [
            d for d in devices if (d.get("remark") or d.get("name")) in device_filter
        ]

    if not devices:
        return jsonify({"success": False, "message": "没有可发现的设备"})

    # 0. 提前加载旧state，用于merge
    _old_state = _load_topology_state()

    # 1. 先确保所有设备有LLDP数据（强制重新采集，确保拓扑最新）
    devices = ensure_lldp_on_all_devices(devices, force=True)
    # 2. 收集所有链路
    all_links = []
    for d in devices:
        name = d.get("remark") or d.get("name")
        lldp = d.get("lldp_neighbors", [])
        log.debug(f"discover: {name} has {len(lldp)} lldp_neighbors")
        for link in lldp:
            link["from_name"] = name
            all_links.append(link)

    log.debug(f"discover: total all_links={len(all_links)}")

    # 2.1 构建chassis_id→设备名映射（比sysname更可靠）
    chassis_to_dev = {}  # chassis_id -> device_name (remark or name)
    for d in devices:
        cid = d.get("chassis_id", "")
        if cid:
            dname = d.get("remark") or d.get("name")
            chassis_to_dev[cid] = dname
    log.debug(f"discover: chassis_id mapping: {chassis_to_dev}")

    # 2.2 用chassis_id解析链路的to_name（解决sysname重复问题）
    resolved_count = 0
    for link in all_links:
        cid = link.get("chassis_id", "")
        if cid and cid in chassis_to_dev:
            real_name = chassis_to_dev[cid]
            if link.get("to_name", "") != real_name:
                link["to_name"] = real_name
                resolved_count += 1
    if resolved_count:
        log.info(f"discover: resolved {resolved_count} neighbor names via chassis_id")

    # 3. 去重（A→B 和 B→A 可能重复）
    # 去重key = sorted(设备A+归一化端口A, 设备B+归一化端口B)
    def _normalize_port(port):
        """归一化端口名称: GE1/0/2 → GigabitEthernet1/0/2, XGE→10GigabitEthernet等"""
        if not port:
            return port
        for pat, repl in [
            (r"^GE(\d)", r"GigabitEthernet\1"),
            (r"^XGE(\d)", r"10GigabitEthernet\1"),
            (r"^10GE(\d)", r"10GigabitEthernet\1"),
            (r"^XE(\d)", r"10GigabitEthernet\1"),
            (r"^FE(\d)", r"FastEthernet\1"),
            (r"^E(\d)", r"Ethernet\1"),
        ]:
            port = re.sub(pat, repl, port)
        return port

    seen = set()
    uniq_links = []
    for link in all_links:
        fn = link.get("from_name", "")
        tn = link.get("to_name", "")
        fp = _normalize_port(link.get("from_port", ""))
        tp = _normalize_port(link.get("to_port", ""))
        side_a = (fn, fp)
        side_b = (tn, tp)
        # 排序两端，保证A→B和B→A得到同一key
        if side_a > side_b:
            key = (side_b, side_a)
        else:
            key = (side_a, side_b)
        if key not in seen:
            seen.add(key)
            uniq_links.append(link)

    # 4. 节点构建移至步骤6.4（merge时一起处理）

    # 5. 构建边（从链路映射到节点ID）
    # device_map: name/remark/sysname→id，sysname重复时不加入
    device_map = {d.get("name"): d.get("id") for d in devices}
    device_map.update(
        {d.get("remark"): d.get("id") for d in devices if d.get("remark")}
    )
    sysname_count = {}
    for d in devices:
        sn = d.get("sysname", "")
        if sn:
            sysname_count[sn] = sysname_count.get(sn, 0) + 1
    for d in devices:
        sn = d.get("sysname", "")
        if sn and sysname_count.get(sn, 1) == 1:
            device_map[sn] = d.get("id")
    # chassis_id也加入device_map（最可靠的匹配方式）
    for d in devices:
        cid = d.get("chassis_id", "")
        if cid:
            device_map[cid] = d.get("id")

    edges = []
    # 统一匹配：chassis_id已解析to_name，直接用device_map查找
    for link in uniq_links:
        fid = device_map.get(link.get("from_name"))
        tid = device_map.get(link.get("to_name"))
        if fid and tid and fid != tid:
            fp = link.get("from_port", "")
            tp = link.get("to_port", "")
            edges.append(
                {
                    "from": fid,
                    "to": tid,
                    "id": f"link_{len(edges) + 1}",
                    "from_name": link.get("from_name"),
                    "to_name": link.get("to_name"),
                    "from_port": fp,
                    "to_port": tp,
                    "link_type": "unknown",
                    "protocol": "lldp",
                }
            )
        elif not tid:
            # to_name无法通过device_map匹配（chassis_id也没解析到）
            # 尝试双向端口验证：找其他链路的from_name/to_port是否匹配
            fn = link.get("from_name", "")
            tp = link.get("to_port", "")
            fp = link.get("from_port", "")
            fnp = _normalize_port(fp)
            tnp = _normalize_port(tp)
            for other in uniq_links:
                if other is link:
                    continue
                # 如果other的from_port归一化后==本链路的to_port归一化后，且本链路的from_port归一化后==other的to_port归一化后
                ofp = _normalize_port(other.get("from_port", ""))
                otp = _normalize_port(other.get("to_port", ""))
                if ofp == tnp and otp == fnp:
                    other_from = other.get("from_name", "")
                    other_id = device_map.get(other_from)
                    if other_id and other_id != fid:
                        edges.append(
                            {
                                "from": fid,
                                "to": other_id,
                                "id": f"link_{len(edges) + 1}",
                                "from_name": fn,
                                "to_name": other_from,
                                "from_port": fp,
                                "to_port": other.get("from_port", ""),
                                "link_type": "unknown",
                                "protocol": "lldp",
                            }
                        )
                        break
    log.info(f"discover: matched {len(edges)} edges from {len(uniq_links)} unique links")

    # 6. 保存
    # 6. Merge链路：新发现+旧链路，不删除
    old_state = _old_state
    old_nodes = old_state.get("nodes", [])
    old_links = old_state.get("links", [])

    # 6.1 给新发现的edges加status/source字段
    from datetime import datetime
    now_iso = datetime.now().isoformat()
    log.info(f"discover merge: edges={len(edges)}, old_links={len(old_links)}")
    for edge in edges:
        edge["source"] = "lldp"
        edge["status"] = "active"
        edge["last_seen"] = now_iso
        edge["lost_at"] = None

    # 6.2 merge: 旧链路中不在新发现里的标为lost
    def _link_key(e):
        fn = e.get('from_name', '') or e.get('from', '')
        tn = e.get('to_name', '') or e.get('to', '')
        fp = _normalize_port(e.get('from_port', ''))
        tp = _normalize_port(e.get('to_port', ''))
        side_a = f"{fn}|{fp}"
        side_b = f"{tn}|{tp}"
        if side_a > side_b:
            return f"{side_b}||{side_a}"
        else:
            return f"{side_a}||{side_b}"

    new_edge_keys = set()
    for e in edges:
        new_edge_keys.add(_link_key(e))

    # 新链路by key
    new_edges_by_key = {}
    for e in edges:
        new_edges_by_key[_link_key(e)] = e

    merged_links = []
    # 处理旧链路
    for old_link in old_links:
        k = _link_key(old_link)
        if k in new_edge_keys:
            # 新发现中仍有 → 跳过旧链路，新数据由步骤6.2.2追加
            continue
        else:
            # 新发现中没有 → 标为lost，查端口状态判断原因
            old_link["status"] = "lost"
            if not old_link.get("lost_at"):
                old_link["lost_at"] = now_iso

            # 检测lost原因：查from端口的接口状态
            lost_reason = "lldp_timeout"  # 默认
            from_name = old_link.get("from_name", "")
            from_port = old_link.get("from_port", "")
            # 端口名归一化：缩写→全称，否则display interface不认
            if from_port:
                from_port = _normalize_port(from_port)
            # 找from设备的vendor
            from_dev = next((d for d in devices if (d.get("remark") or d.get("name")) == from_name), None)
            if from_dev and from_port:
                try:
                    from netops_tools import NetOpsTools as _NT
                    _chk_tools = _NT(_devices_file)
                    vendor = from_dev.get("vendor", "auto")
                    phy_up, proto_up, raw_out = _check_port_status(_chk_tools, from_name, vendor, from_port)
                    lost_reason = _classify_lost_link(phy_up, proto_up)
                    log.info(f"lost link {from_name} {from_port}: phy={phy_up} proto={proto_up} → {lost_reason} raw={raw_out[:100]}")
                except Exception as e:
                    log.warning(f"lost link check failed for {from_name} {from_port}: {e}")
            else:
                log.warning(f"lost link SKIP: from_dev={'FOUND' if from_dev else 'NOT_FOUND'} from_port={from_port}")
            old_link["lost_reason"] = lost_reason

            # 物理断线 → 直接移除链路，不保留lost状态
            if lost_reason == "physical_down":
                log.info(f"link {from_name} {from_port} physical_down, removing from topology")
                continue

            merged_links.append(old_link)

    # 追加所有新发现的链路（旧链路已跳过匹配的，只需加入新数据）
    for e in edges:
        merged_links.append(e)

    # 6.3 收集LLDP状态提示
    lldp_messages = []
    for d in devices:
        name = d.get("remark") or d.get("name")
        status = d.get("_lldp_status", "")
        if status == "auto_enabled":
            lldp_messages.append(f"✅ {name} 已自动开启LLDP协议")
        elif status == "enable_failed":
            lldp_messages.append(f"❌ {name} LLDP开启失败")
        elif status == "disabled":
            lldp_messages.append(f"⛔ {name} LLDP未开启")
        elif status == "enabled_no_nbr":
            lldp_messages.append(f"ℹ️ {name} LLDP已开启，无邻居")
        # 6.3只收集消息，不pop临时标记（6.4节点构建需要）

    # 6.4 节点状态：保留旧坐标，叠加在线信息
    nodes = []
    for d in devices:
        old = next((n for n in old_nodes if n.get("id") == d.get("id")), {})
        nodes.append(
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "label": d.get("remark") or d.get("name") or d.get("ip") or "N/A",
                "remark": d.get("remark", ""),
                "ip": d.get("ip") or d.get("serial_port") or "N/A",
                "vendor": d.get("vendor", "unknown"),
                "deviceType": d.get("device_type", "unknown"),
                "x": old.get("x"),
                "y": old.get("y"),
                "facts": d.get("facts"),
                "lldp_status": d.get("_lldp_status", ""),
            }
        )

    # 6.5 重新映射链路的 from/to 设备ID（设备重建后ID会变）
    # 构建 name→id 映射（包含 remark/name/sysname）
    name_to_id = {}
    for d in devices:
        did = d.get("id")
        for key in [d.get("remark"), d.get("name"), d.get("sysname"), (d.get("facts") or {}).get("hostname")]:
            if key and key not in name_to_id:
                name_to_id[key] = did
    # 旧节点ID→name映射（用于旧链路只有from/to ID没有from_name的情况）
    old_id_to_name = {}
    for n in old_nodes:
        old_id_to_name[n.get("id", "")] = n.get("name") or n.get("remark") or n.get("label", "")

    for link in merged_links:
        # 确保 from_name 存在
        fn = link.get("from_name", "")
        if not fn and link.get("from") in old_id_to_name:
            fn = old_id_to_name[link["from"]]
            link["from_name"] = fn
        tn = link.get("to_name", "")
        if not tn and link.get("to") in old_id_to_name:
            tn = old_id_to_name[link["to"]]
            link["to_name"] = tn
        # 根据 from_name/to_name 重新映射 from/to 设备ID
        if fn and fn in name_to_id:
            link["from"] = name_to_id[fn]
        if tn and tn in name_to_id:
            link["to"] = name_to_id[tn]

    # 6.6 过滤掉无法匹配节点的链路
    valid_node_ids = {n.get("id") for n in nodes}
    merged_links = [l for l in merged_links if l.get("from") in valid_node_ids and l.get("to") in valid_node_ids]
    removed = len(merged_links) - len([l for l in merged_links if l.get("from") in valid_node_ids and l.get("to") in valid_node_ids])
    if removed:
        log.info(f"discover: removed {removed} links with unmatched node IDs")

    # 7. 保存
    state = _load_topology_state()
    state["nodes"] = nodes
    state["links"] = merged_links
    state["version"] = int(state.get("version", 1)) + 1
    _save_topology_state(state)

    # 清理临时标记
    for d in devices:
        d.pop("_lldp_status", None)

    # 写回devices.json前，重新读取文件合并可能被ping更新的last_collected
    try:
        _fresh_devices = _load_devices()
        _fresh_map = {(fd.get('remark') or fd.get('name','')): fd for fd in _fresh_devices}
        for d in devices:
            _fname = d.get('remark') or d.get('name','')
            _fd = _fresh_map.get(_fname)
            if _fd and _fd.get('facts', {}).get('last_collected'):
                if not d.get('facts'):
                    d['facts'] = {}
                d['facts']['last_collected'] = _fd['facts']['last_collected']
    except Exception as e:
        log.debug(f"discover: skip merge last_collected: {e}")

    # 写回devices.json（原子写入，防止并发/断电导致损坏）
    try:
        _tmp = _devices_file + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
        os.replace(_tmp, _devices_file)
    except Exception as e:
        log.warning(f"discover: failed to save devices.json: {e}")

    # 动态合并devices.json的last_collected到返回的state中
    # (discover过程中devices.json可能被ping更新了last_collected)
    _dev_map = {d.get("id"): d for d in devices}
    for n in state.get("nodes", []):
        _dv = _dev_map.get(n.get("id"))
        if _dv and _dv.get("facts", {}).get("last_collected"):
            if not n.get("facts"):
                n["facts"] = {}
            n["facts"]["last_collected"] = _dv["facts"]["last_collected"]

    return jsonify(
        {
            "success": True,
            "nodes": len(nodes),
            "links": len(merged_links),
            "state": state,
            "messages": lldp_messages,
        }
    )


@topology_bp.route("/api/topology/enable_lldp", methods=["POST"])
def topology_enable_lldp():
    """手动开启设备LLDP协议"""
    from netops_tools import NetOpsTools

    data = request.json or {}
    device_name = data.get("device", "")
    if not device_name:
        return jsonify({"success": False, "message": "缺少设备名"})

    devices = _load_devices()
    device = next((d for d in devices if (d.get("remark") or d.get("name")) == device_name), None)
    if not device:
        return jsonify({"success": False, "message": f"找不到设备 {device_name}"})

    vendor = device.get("vendor", "unknown")
    tools = NetOpsTools(_devices_file)

    if _try_enable_lldp(tools, device_name, vendor):
        return jsonify({"success": True, "message": f"{device_name} LLDP已开启"})
    else:
        return jsonify({"success": False, "message": f"{device_name} LLDP开启失败，请检查设备连接"})


@topology_bp.route("/api/topology/apply", methods=["POST"])
def topology_apply():
    """应用拓扑变更到设备"""
    data = request.json or {}
    changes = data.get("changes", [])
    if not changes:
        return jsonify({"success": False, "message": "没有变更"})

    results = []
    for change in changes:
        results.append(
            {
                "change": change,
                "status": "skipped",
                "message": "暂不支持自动应用拓扑变更",
            }
        )

    return jsonify({"success": True, "results": results})
