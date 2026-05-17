#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拓扑蓝图 - 拓扑发现、渲染、模板管理
"""

from flask import Blueprint, request, jsonify
import json
import os
import re
import time

from app.logger import get_logger

log = get_logger(__name__)

topology_bp = Blueprint("topology", __name__)

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
    with open(tf, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _load_topology_templates():
    ttf = _templates_file()
    if os.path.exists(ttf):
        with open(ttf, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_topology_templates(templates):
    ttf = _templates_file()
    os.makedirs(os.path.dirname(ttf), exist_ok=True)
    with open(ttf, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)


def _load_devices():
    if os.path.exists(_devices_file):
        with open(_devices_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ===== 路由 =====


@topology_bp.route("/api/topology/state", methods=["GET", "PATCH"])
def topology_state():
    if request.method == "GET":
        state = _load_topology_state()
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
    return jsonify(_load_topology_templates())


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
    if re.search(r"Local(?:If| Interface)\s+(?:Nbr\s+)?(?:Chassis|chassis)\s+ID", text, re.IGNORECASE):
        for line in text.strip().split("\n"):
            # 跳过表头行
            if re.match(r'Local', line.strip(), re.IGNORECASE):
                continue
            # 尝试4列匹配（含System Name）
            m = re.match(
                r"((?:GE|XGE|10GE|40GE|100GE|Eth|Ethernet|GigabitEthernet)\S+)\s+(\S+)\s+(\S+)\s+(\S+)", line.strip()
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
                r"((?:GE|XGE|10GE|40GE|100GE|Eth|Ethernet|GigabitEthernet)\S+)\s+(\S+)\s+(\S+)", line.strip()
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
            m = re.search(r"(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?", line, re.IGNORECASE)
            if m:
                current_entry["local_port"] = m.group(0)

        elif "Neighbor interface" in line or "neighbor interface" in line.lower():
            m = re.search(r"(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?", line, re.IGNORECASE)
            if m:
                current_entry["neighbor_port"] = m.group(0)

        elif "Neighbor port id" in line or "port id" in line.lower():
            m = re.search(r"(GE|XGE|10GE|40GE|100GE|Eth|Ethernet)\d+(?:/\d+)*/\d+(?:\.\d+)?", line, re.IGNORECASE)
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

        elif "Interface" in line and re.search(r"GigabitEthernet|FastEthernet|TenGig", line):
            m = re.search(r"(GigabitEthernet|FastEthernet|TenGig|Gi|Te|Fa)\d+(?:/\d+)*(?:\.\d+)?", line, re.IGNORECASE)
            if m:
                if "local_port" not in current_entry:
                    current_entry["local_port"] = m.group(0)
                else:
                    current_entry["neighbor_port"] = m.group(0)

        # 空行表示一条记录结束
        if not line and current_entry.get("neighbor_name") and current_entry.get("local_port"):
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


def ensure_lldp_on_all_devices(devices, force=False):
    """确保所有设备的LLDP信息已采集"""
    from netops_tools import NetOpsTools

    tools = NetOpsTools(_devices_file)
    updated = []
    log.info(f"ensure_lldp: processing {len(devices)} devices, force={force}")

    for d in devices:
        name = d.get("remark") or d.get("name")
        if not name:
            continue

        # 已有LLDP数据则跳过（除非force）
        if d.get("lldp_neighbors") and not force:
            log.info(f"ensure_lldp: {name} already has LLDP data, skipping")
            updated.append(d)
            continue

        # 读取LLDP信息
        try:
            vendor = d.get("vendor", "auto")
            if vendor in ("huawei", "h3c"):
                cmds_list = [["display lldp neighbor-information list"]]
            elif vendor in ("cisco", "ruckus"):
                cmds_list = [["show lldp neighbors detail"]]
            elif vendor == "juniper":
                cmds_list = [["show lldp neighbors"]]
            else:
                # auto/unknown: 尝试所有厂商命令
                cmds_list = [
                    ["display lldp neighbor-information list"],  # H3C/华为
                    ["show lldp neighbors detail"],  # Cisco
                    ["show lldp neighbors"],  # Juniper
                ]

            for cmds in cmds_list:
                log.info(f"LLDP discover: device={name}, vendor={vendor}, cmds={cmds}")
                result = tools.execute_tool("run_commands", {"device": name, "commands": cmds})
                if result.get("success") and result.get("results"):
                    lldp_text = result["results"][0].get("output", "")
                    # 检查是否命令失败（含错误提示）
                    if any(
                        err in lldp_text
                        for err in ["Unrecognized command", "Invalid input", "% Error", "Error:", "Syntax error"]
                    ):
                        log.info(f"LLDP discover: {name} command failed for {cmds}, trying next")
                        continue
                    d["lldp_neighbors"] = _extract_topology_links(lldp_text, name)
                    log.info(
                        f"LLDP discover: {name} parsed {len(d.get('lldp_neighbors', []))} neighbors, output_len={len(lldp_text)}"
                    )
                    if not d["lldp_neighbors"] and lldp_text:
                        log.info(f"LLDP discover: {name} raw output: {lldp_text[:300]}")
                    updated.append(d)
                    break
            else:
                log.warning(f"LLDP discover: {name} all LLDP commands failed")
                updated.append(d)
        except Exception as e:
            log.warning(f"LLDP discover: {name} exception: {e}")
            updated.append(d)

    log.info(f"ensure_lldp: done, {sum(1 for d in updated if d.get('lldp_neighbors'))} devices have LLDP data")
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
        devices = [d for d in devices if (d.get("remark") or d.get("name")) in device_filter]

    if not devices:
        return jsonify({"success": False, "message": "没有可发现的设备"})

    # 1. 先确保所有设备有LLDP数据（强制重新采集，确保拓扑最新）
    devices = ensure_lldp_on_all_devices(devices, force=True)
    # 1.1 将LLDP数据写回devices.json，避免下次重新采集
    try:
        with open(_devices_file, "w", encoding="utf-8") as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"discover: failed to save devices.json: {e}")

    # 2. 收集所有链路
    all_links = []
    for d in devices:
        name = d.get("remark") or d.get("name")
        lldp = d.get("lldp_neighbors", [])
        log.info(f"discover: {name} has {len(lldp)} lldp_neighbors")
        for link in lldp:
            link["from_name"] = name
            all_links.append(link)

    log.info(f"discover: total all_links={len(all_links)}")

    # 2.1 补全to_name为空的链路（用chassis_id匹配）
    # 先构建chassis_id→设备映射：从每台设备的LLDP输出提取chassis_id
    chassis_to_device = {}  # chassis_id -> device_name
    for link in all_links:
        cid = link.get("chassis_id", "")
        if cid and link.get("from_name"):
            # 这条链路的from_name设备看到的邻居chassis_id
            pass
    # 从所有链路中，每台from设备自己也有chassis_id
    # 但更简单的方法：同一chassis_id出现在多条链路的to端，可以推断
    # 先尝试：如果有设备名与chassis_id对应记录
    # 实际上我们无法直接获取设备自身chassis_id，但可以用交叉匹配
    # 策略：如果A看到chassis_id=xxx, port=P1, 而B的from_port=P1，则A的邻居是B
    # 这在后面的单方向匹配中处理

    # 3. 去重（A→B 和 B→A 可能重复）
    seen = set()
    uniq_links = []
    for link in all_links:
        from_name = link.get("from_name", "")
        to_name = link.get("to_name", "")
        from_port = link.get("from_port", "")
        to_port = link.get("to_port", "")
        # 排序时端口也要跟着名字一起换
        if from_name > to_name:
            key = (to_name, to_port, from_name, from_port)
        else:
            key = (from_name, from_port, to_name, to_port)
        if key not in seen:
            seen.add(key)
            uniq_links.append(link)

    # 4. 构建节点
    old_state = _load_topology_state()
    old_nodes = old_state.get("nodes", [])

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
            }
        )

    # 5. 构建边（从链路映射到节点ID）
    # 先建name/remark/sysname→id映射，sysname重复时不加入
    device_map = {d.get("name"): d.get("id") for d in devices}
    device_map.update({d.get("remark"): d.get("id") for d in devices if d.get("remark")})
    sysname_count = {}
    for d in devices:
        sn = d.get("sysname", "")
        if sn:
            sysname_count[sn] = sysname_count.get(sn, 0) + 1
    for d in devices:
        sn = d.get("sysname", "")
        if sn and sysname_count.get(sn, 1) == 1:
            device_map[sn] = d.get("id")

    # 如果sysname全部重复，用交叉验证匹配
    all_sysnames_same = len(sysname_count) == 1 and len(devices) > 1

    def _normalize_port(port):
        """归一化端口名称: GE1/0/2 → GigabitEthernet1/0/2, XGE→10GigabitEthernet等"""
        if not port:
            return port
        import re as _re

        # H3C/华为缩写映射
        mappings = [
            (r"^GE(\d)", r"GigabitEthernet\1"),
            (r"^XGE(\d)", r"10GigabitEthernet\1"),
            (r"^10GE(\d)", r"10GigabitEthernet\1"),
            (r"^XE(\d)", r"10GigabitEthernet\1"),
            (r"^FE(\d)", r"FastEthernet\1"),
            (r"^E(\d)", r"Ethernet\1"),
        ]
        for pattern, repl in mappings:
            port = _re.sub(pattern, repl, port)
        return port

    edges = []
    if all_sysnames_same:
        log.info(f"discover: all sysnames same={sysname_count}, using cross-validation")
        # 先尝试双向交叉验证
        for i, la in enumerate(uniq_links):
            for lb in uniq_links[i + 1 :]:
                la_fp = _normalize_port(la.get("from_port", ""))
                la_tp = _normalize_port(la.get("to_port", ""))
                lb_fp = _normalize_port(lb.get("from_port", ""))
                lb_tp = _normalize_port(lb.get("to_port", ""))
                if la_fp == lb_tp and la_tp == lb_fp and la.get("to_name") == lb.get("to_name"):
                    fid = next(
                        (
                            d.get("id")
                            for d in devices
                            if d.get("name") == la.get("from_name") or d.get("remark") == la.get("from_name")
                        ),
                        None,
                    )
                    tid = next(
                        (
                            d.get("id")
                            for d in devices
                            if d.get("name") == lb.get("from_name") or d.get("remark") == lb.get("from_name")
                        ),
                        None,
                    )
                    if fid and tid:
                        edges.append(
                            {
                                "from": fid,
                                "to": tid,
                                "id": f"link_{len(edges) + 1}",
                                "from_name": la.get("from_name"),
                                "to_name": lb.get("from_name"),
                                "from_port": la.get("from_port"),
                                "to_port": lb.get("from_port"),
                                "link_type": "unknown",
                                "protocol": "lldp",
                            }
                        )
        # 如果双向验证0链路，用chassis_id交叉匹配
        if not edges:
            log.info("discover: cross-validation found 0 links, trying chassis_id matching")
            # 构建chassis_id到设备名的映射：从所有链路中，同一chassis_id被多台设备看到
            # 说明这些设备连着同一台邻居（或互为邻居）
            cid_seen_by = {}  # chassis_id -> [(device_name, from_port, to_port)]
            for link in uniq_links:
                cid = link.get("chassis_id", "")
                if not cid:
                    continue
                fname = link.get("from_name", "")
                fport = link.get("from_port", "")
                tport = link.get("to_port", "")
                cid_seen_by.setdefault(cid, []).append((fname, fport, tport))

            # 如果同一chassis_id被2台设备看到，且A.to_port归一化后匹配B.from_port，则A↔B
            for cid, sightings in cid_seen_by.items():
                if len(sightings) < 2:
                    continue
                for i, (name_a, fport_a, tport_a) in enumerate(sightings):
                    for name_b, fport_b, tport_b in sightings[i + 1 :]:
                        # A看到邻居port=tport_a, B看到自己port=fport_b
                        # 如果tport_a归一化后==fport_b归一化，则A的邻居是B
                        matched = False
                        if _normalize_port(tport_a) == _normalize_port(fport_b):
                            # A的邻居是B
                            fid = next((d.get("id") for d in devices if d.get("name") == name_a or d.get("remark") == name_a), None)
                            tid = next((d.get("id") for d in devices if d.get("name") == name_b or d.get("remark") == name_b), None)
                            if fid and tid:
                                edges.append({"from": fid, "to": tid, "id": f"link_{len(edges) + 1}",
                                    "from_name": name_a, "to_name": name_b,
                                    "from_port": fport_a, "to_port": fport_b,
                                    "link_type": "unknown", "protocol": "lldp"})
                                matched = True
                        if not matched and _normalize_port(tport_b) == _normalize_port(fport_a):
                            # B的邻居是A
                            fid = next((d.get("id") for d in devices if d.get("name") == name_b or d.get("remark") == name_b), None)
                            tid = next((d.get("id") for d in devices if d.get("name") == name_a or d.get("remark") == name_a), None)
                            if fid and tid:
                                edges.append({"from": fid, "to": tid, "id": f"link_{len(edges) + 1}",
                                    "from_name": name_b, "to_name": name_a,
                                    "from_port": fport_b, "to_port": fport_a,
                                    "link_type": "unknown", "protocol": "lldp"})
    else:
        for link in uniq_links:
            fid = device_map.get(link.get("from_name"))
            tid = device_map.get(link.get("to_name"))
            if fid and tid:
                fp = link.get("from_port", "")
                tp = link.get("to_port", "")
                key = f"{fid}-{fp}-{tid}-{tp}"
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

    # 6. 保存
    state = _load_topology_state()
    state["nodes"] = nodes
    state["links"] = edges
    state["version"] = int(state.get("version", 1)) + 1
    _save_topology_state(state)

    # debug日志
    debug_path = os.path.join(_data_dir, "_discover_debug.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(f"Links: {len(edges)}\n")
        for link in edges:
            f.write(f"  {link['from_name']} {link['from_port']} -> {link['to_name']} {link['to_port']}\n")

    return jsonify({"success": True, "nodes": len(nodes), "links": len(edges), "state": state})


@topology_bp.route("/api/topology/apply", methods=["POST"])
def topology_apply():
    """应用拓扑变更到设备"""
    data = request.json or {}
    changes = data.get("changes", [])
    if not changes:
        return jsonify({"success": False, "message": "没有变更"})

    results = []
    for change in changes:
        results.append({"change": change, "status": "skipped", "message": "暂不支持自动应用拓扑变更"})

    return jsonify({"success": True, "results": results})
