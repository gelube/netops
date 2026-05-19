#!/usr/bin/env python3
"""
设备蓝图 - 设备CRUD、发现、信息采集
"""

from flask import Blueprint, request, jsonify
import json
import os
import re
import time
import threading
from datetime import datetime

from app.logger import get_logger
from .shared import load_devices, save_devices, get_devices_lock

log = get_logger(__name__)

device_bp = Blueprint("device", __name__)

# 文件读写锁，保护devices.json并发写入
_devices_lock = get_devices_lock()

_data_dir = ""
_devices_file = ""
_project_root = ""


def init_device_blueprint(data_dir, devices_file, project_root):
    global _data_dir, _devices_file, _project_root
    _data_dir = data_dir
    _devices_file = devices_file
    _project_root = project_root


def _load_devices():
    return load_devices(_devices_file)


def _save_devices(devices):
    with _devices_lock:
        os.makedirs(os.path.dirname(_devices_file), exist_ok=True)
        _tmp = _devices_file + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2, ensure_ascii=False)
        os.replace(_tmp, _devices_file)


@device_bp.route("/api/devices", methods=["GET"])
def get_devices():
    devices = _load_devices()
    # 兼容前端：同时支持直接数组或 {devices:[...]}
    if isinstance(devices, list):
        return jsonify({"success": True, "devices": devices})
    return jsonify(devices)


@device_bp.route("/api/device/add", methods=["POST"])
def add_device():
    """添加设备（支持单个和批量）"""
    data = request.json or {}

    # 批量添加
    if "devices" in data:
        results = []
        for d in data["devices"]:
            r = _add_single_device(d)
            results.append(r)
        ok = sum(1 for r in results if r.get("success"))
        return jsonify(
            {"success": True, "added": ok, "total": len(results), "results": results}
        )

    # 单个添加
    result = _add_single_device(data)
    return jsonify(result)


def _add_single_device(data):
    """添加或更新单个设备"""
    device_id = data.get("device_id", "")
    basic_only = data.get("basic_only", False)
    ip = data.get("ip", "").strip()
    remark = data.get("remark", "").strip()
    username = data.get("username", "")
    password = data.get("password", "")
    vendor = data.get("vendor", "auto")
    port = data.get("port", 22)
    conn_type = data.get("conn_type", "ssh")
    auto_detect = data.get("auto_detect", False)

    devices = _load_devices()

    # 编辑模式：更新已有设备
    if device_id:
        for i, d in enumerate(devices):
            if d.get("id") == device_id:
                if basic_only:
                    # 仅更新基本信息（凭证/备注）
                    d["username"] = username
                    d["password"] = password
                    d["remark"] = remark
                else:
                    # 全量更新
                    if ip:
                        # 去重检查（排除自身）
                        for other in devices:
                            if other.get("id") == device_id:
                                continue
                            if other.get("ip") == ip and int(
                                other.get("port", 22)
                            ) == int(port):
                                return {
                                    "success": False,
                                    "message": f"设备 {ip}:{port} 已存在",
                                }
                        # 验证连通性
                        if conn_type != "serial":
                            import socket as _sock_mod
                            try:
                                _s = _sock_mod.socket(_sock_mod.AF_INET, _sock_mod.SOCK_STREAM)
                                _s.settimeout(5)
                                _r = _s.connect_ex((ip, int(port)))
                                _s.close()
                                if _r != 0:
                                    return {"success": False, "message": f"连接失败：{ip}:{port} 不可达，请检查IP和端口"}
                            except Exception as e:
                                return {"success": False, "message": f"连接测试出错：{e}"}
                        d["ip"] = ip
                        d["port"] = int(port)
                    d["vendor"] = vendor
                    d["conn_type"] = conn_type
                    d["device_type"] = data.get(
                        "device_type", d.get("device_type", "unknown")
                    )
                    d["remark"] = remark
                    d["username"] = username
                    d["password"] = password
                _save_devices(devices)
                return {"success": True, "device": d}
        return {"success": False, "message": f"设备 {device_id} 不存在"}

    # 新增模式
    if not ip:
        return {"success": False, "message": "IP 不能为空"}

    # 去重：IP+端口组合唯一
    for d in devices:
        if d.get("ip") == ip and int(d.get("port", 22)) == int(port):
            return {"success": False, "message": f"设备 {ip}:{port} 已存在"}

    # 自动发现
    if auto_detect and ip:
        detected = _auto_detect_device(ip, username, password, port, conn_type)
        if detected:
            vendor = detected.get("vendor", vendor)
            remark = remark or detected.get("hostname", "")

    # 验证连通性：TCP端口是否可达（serial跳过）
    if conn_type != "serial" and ip:
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, int(port)))
            sock.close()
            if result != 0:
                return {"success": False, "message": f"连接失败：{ip}:{port} 不可达，请检查IP和端口"}
        except Exception as e:
            return {"success": False, "message": f"连接测试出错：{e}"}

    device_id = f"dev_{int(time.time() * 1000)}"
    device = {
        "id": device_id,
        "name": remark or ip,  # name保留为兼容字段，值=remark或IP
        "ip": ip,
        "port": int(port),
        "username": username,
        "password": password,
        "vendor": vendor,
        "conn_type": conn_type,
        "remark": remark,
        "device_type": data.get("device_type", "unknown"),
        "facts": {},
    }

    devices.append(device)
    _save_devices(devices)
    return {"success": True, "device": device}


def _auto_detect_device(ip, username, password, port=22, conn_type="ssh"):
    """自动探测设备厂商和型号"""
    try:
        from netmiko import ConnectHandler

        # 根据连接方式选择探测类型序列
        if conn_type == "telnet" or (port not in (22, 2222) and port >= 23):
            # Telnet 免凭证：厂商驱动强制认证，只能用 generic_termserver_telnet
            if not username and not password:
                probe_types = ["generic_termserver_telnet"]
            else:
                probe_types = ["hp_comware_telnet", "huawei_telnet", "cisco_ios_telnet"]
        else:
            probe_types = ["huawei", "cisco_ios", "hp_comware", "juniper_junos"]

        vendor_map = {
            "huawei": "huawei",
            "cisco_ios": "cisco",
            "hp_comware": "h3c",
            "juniper_junos": "juniper",
            "huawei_telnet": "huawei",
            "cisco_ios_telnet": "cisco",
            "hp_comware_telnet": "h3c",
            "generic_termserver_telnet": "unknown",
        }

        for device_type in probe_types:
            try:
                conn_params = {
                    "device_type": device_type,
                    "host": ip,
                    "port": port,
                    "timeout": 10,
                    "conn_timeout": 8,
                }
                # 免凭证不需要username/password
                if username:
                    conn_params["username"] = username
                if password:
                    conn_params["password"] = password

                conn = ConnectHandler(**conn_params)

                # 免凭证 telnet 用原始通道（generic_termserver 不支持 send_command）
                is_noauth_telnet = (
                    not username and not password and "telnet" in device_type
                )

                if is_noauth_telnet:
                    # H3C/Huawei 免凭证：先中断 auto-config
                    import time

                    conn.write_channel("\x03")  # Ctrl+C
                    time.sleep(2)
                    conn.write_channel("\n")
                    time.sleep(1)
                    conn.read_channel()  # 丢弃提示

                    # 发送版本命令
                    conn.write_channel("display version\n")
                    time.sleep(3)
                    output = conn.read_channel()
                    prompt = ""
                else:
                    prompt = conn.find_prompt() or ""
                    vendor = vendor_map.get(device_type, "unknown")
                    if vendor in ("huawei", "h3c"):
                        output = conn.send_command_timing(
                            "display version", delay_factor=1
                        )
                    elif vendor == "cisco":
                        output = conn.send_command_timing(
                            "show version", delay_factor=1
                        )
                    else:
                        output = conn.send_command_timing(
                            "display version", delay_factor=1
                        )

                conn.disconnect()

                # 免凭证 telnet 从输出推断厂商
                if is_noauth_telnet:
                    if "H3C" in output or "Comware" in output:
                        vendor = "h3c"
                    elif "Huawei" in output:
                        vendor = "huawei"
                    elif "Cisco" in output:
                        vendor = "cisco"
                    else:
                        vendor = "unknown"
                else:
                    vendor = vendor_map.get(device_type, "unknown")

                hostname = prompt.strip("<>[]#>").strip()

                return {
                    "vendor": vendor,
                    "hostname": hostname,
                    "version_output": output[:500],
                }
            except Exception as e:
                log.debug("探测设备类型失败", device_type=device_type, error=str(e))
                continue
    except ImportError:
        pass
    return None


def identify_device(device):
    """识别设备厂商和型号"""
    from app.core.vendor import VendorIdentifier

    facts = device.get("facts", {})
    sys_descr = facts.get("sys_descr", "")
    sys_object_id = facts.get("sys_object_id", "")

    vendor, model, dtype = VendorIdentifier.identify_from_snmp(sys_descr, sys_object_id)

    return {
        "vendor": vendor.value if vendor else "unknown",
        "model": model,
        "device_type": dtype.value if dtype else "unknown",
        "display_vendor": VendorIdentifier.get_vendor_display_name(vendor),
        "display_type": VendorIdentifier.get_device_type_display_name(dtype),
    }


@device_bp.route("/api/discover", methods=["POST"])
def discover():
    """网络发现"""
    data = request.json or {}
    ip_range = data.get("ip_range", "")
    username = data.get("username", "")
    password = data.get("password", "")

    if not ip_range:
        return jsonify({"success": False, "message": "请指定IP范围"})

    # 解析IP范围
    ips = _parse_ip_range(ip_range)
    if not ips:
        return jsonify({"success": False, "message": "无效的IP范围"})

    results = []
    for ip in ips:
        detected = _auto_detect_device(ip, username, password)
        if detected:
            results.append(
                {
                    "ip": ip,
                    "vendor": detected.get("vendor", "unknown"),
                    "hostname": detected.get("hostname", ""),
                }
            )

    return jsonify({"success": True, "discovered": results, "total": len(results)})


def _parse_ip_range(ip_range_str):
    """解析IP范围字符串"""
    ips = []
    parts = [p.strip() for p in ip_range_str.replace("，", ",").split(",")]

    for part in parts:
        if "-" in part:
            base, suffix = part.rsplit("-", 1)
            try:
                start = int(base.split(".")[-1])
                end = int(suffix)
                prefix = ".".join(base.split(".")[:-1])
                for i in range(min(start, end), max(start, end) + 1):
                    ips.append(f"{prefix}.{i}")
            except (ValueError, IndexError):
                continue
        else:
            if re.match(r"\d+\.\d+\.\d+\.\d+", part):
                ips.append(part)

    return ips


@device_bp.route("/api/device/delete", methods=["POST"])
def delete_device():
    """删除设备"""
    data = request.json or {}
    device_id = data.get("id", "")
    device_name = data.get("name", "") or data.get("remark", "")

    if not device_id and not device_name:
        return jsonify({"success": False, "message": "请指定设备ID或名称"})

    devices = _load_devices()
    original_len = len(devices)

    devices = [
        d
        for d in devices
        if d.get("id") != device_id
        and d.get("remark") != device_name
        and d.get("ip") != device_name
    ]

    if len(devices) == original_len:
        return jsonify({"success": False, "message": "设备不存在"})

    _save_devices(devices)
    return jsonify({"success": True})


@device_bp.route("/api/device/collect", methods=["POST"])
def device_collect():
    """采集设备信息"""
    data = request.json or {}
    device_name = data.get("device", "") or data.get("name", "")
    device_id = data.get("id", "")
    collect_type = data.get("type", data.get("collect_type", "all"))

    from netops_tools import NetOpsTools

    tools = NetOpsTools(_devices_file)
    device = None
    for d in tools.load_devices():
        if device_id and d.get("id") == device_id:
            device = d
            break
        if (
            d.get("remark") == device_name
            or d.get("ip") == device_name
            or d.get("name") == device_name
        ):
            device = d
            break

    if not device:
        return jsonify({"success": False, "message": f"设备 {device_name} 不存在"})

    vendor = device.get("vendor", "huawei")
    commands = _get_collect_commands(vendor, collect_type)
    # 用设备名/备注/IP传给NetOpsTools
    dev_identifier = device.get("remark") or device.get("name") or device.get("ip")
    result = tools.execute_tool(
        "run_commands", {"device": dev_identifier, "commands": commands}
    )

    if result.get("success"):
        # 解析采集结果更新设备信息
        _update_device_facts(device, result.get("results", []), vendor)
        devices = _load_devices()
        for i, d in enumerate(devices):
            if d.get("id") == device.get("id"):
                devices[i] = device
                break
        _save_devices(devices)

    return jsonify(result)


def _get_collect_commands(vendor, collect_type):
    """获取采集命令列表"""
    if vendor in ("huawei", "h3c"):
        cmd_map = {
            "all": [
                "display version",
                "display device",
                "display current-configuration",
            ],
            "version": ["display version"],
            "interface": ["display interface brief"],
            "arp": ["display arp"],
            "route": ["display ip routing-table"],
            "lldp": ["display lldp neighbor-information list"],
        }
    else:
        cmd_map = {
            "all": ["show version", "show inventory", "show running-config"],
            "version": ["show version"],
            "interface": ["show ip interface brief"],
            "arp": ["show arp"],
            "route": ["show ip route"],
        }
    return cmd_map.get(collect_type, cmd_map["all"])


def _update_device_facts(device, results, vendor):
    """更新设备facts"""
    from app.core.vendor import VendorIdentifier
    from app.core.device import Vendor as VendorEnum

    facts = device.get("facts", {})

    for r in results:
        cmd = r.get("command", "")
        output = r.get("output", "")

        if "version" in cmd:
            vendor_result, model, dtype = VendorIdentifier.identify_from_command_output(
                output
            )
            if vendor_result != VendorEnum.UNKNOWN:
                device["vendor"] = vendor_result.value
            if model:
                facts["model"] = model
            if dtype:
                device["device_type"] = dtype.value
            facts["version_output"] = output[:2000]

        # 提取sysname
        if "current-configuration" in cmd or "running-config" in cmd:
            import re

            m = re.search(r"sysname\s+(\S+)", output)
            if m:
                device["sysname"] = m.group(1)
                facts["hostname"] = m.group(1)

    device["facts"] = facts


@device_bp.route("/api/device/ping", methods=["POST"])
def device_ping():
    """检测设备连通性"""
    data = request.json or {}
    device_name = data.get("device", "")
    if not device_name:
        return jsonify({"success": False, "message": "请指定设备名", "online": False})

    devices = _load_devices()
    dev = None
    for d in devices:
        if (
            d.get("remark") == device_name
            or d.get("ip") == device_name
            or d.get("name") == device_name
        ):
            dev = d
            break
    if not dev:
        return jsonify({"success": False, "message": "设备不存在", "online": False})

    import socket

    ip = dev.get("ip", "")
    port = dev.get("port", 22)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, int(port)))
        sock.close()
        online = result == 0
        # 在线时更新facts时间
        if online:
            dev["facts"] = dev.get("facts", {})
            dev["facts"]["last_collected"] = datetime.now().isoformat()
            _save_devices(devices)
        return jsonify({"success": True, "online": online, "ip": ip, "port": port})
    except Exception as e:
        log.warning(f"Ping {device_name} failed: {e}")
        return jsonify({"success": False, "message": str(e), "online": False})


@device_bp.route("/api/device/facts", methods=["GET"])
def device_facts():
    """获取设备facts"""
    device_name = request.args.get("device", "")
    if not device_name:
        return jsonify({"success": False, "message": "请指定设备名"})

    devices = _load_devices()
    for d in devices:
        if (
            d.get("remark") == device_name
            or d.get("ip") == device_name
            or d.get("name") == device_name
        ):
            return jsonify({"success": True, "facts": d.get("facts", {})})

    return jsonify({"success": False, "message": "设备不存在"})
