import os
import json
import sys
import time
import logging

log = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_DIR, 'data')
os.makedirs(_DATA_DIR, exist_ok=True)
DEVICES_FILE = os.path.join(_DATA_DIR, 'devices.json')
CONFIG_FILE = os.path.join(_DATA_DIR, 'llm_config.json')

# 导入命令安全守卫
try:
    sys.path.insert(0, os.path.dirname(_DIR))
    from app.network.command_guard import CommandGuard
    COMMAND_GUARD_AVAILABLE = True
except ImportError:
    COMMAND_GUARD_AVAILABLE = False

PORT_RE = r'(?:GigabitEthernet|Ten-GigabitEthernet|FortyGigE|HundredGigE|XGE|10GE|40GE|100GE|Ethernet|Eth|GE|Port-channel|Vlanif|LoopBack|NULL|Vlan|Bridge-Aggregation|Route-Aggregation)\d+(?:/\d+)*(?:\.\d+)?'


class NetOpsTools:
    """NetOps 工具执行器"""

    def __init__(self, devices_file=DEVICES_FILE):
        self.devices_file = devices_file

    def load_devices(self):
        if os.path.exists(self.devices_file):
            with open(self.devices_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def save_devices(self, devices):
        os.makedirs(os.path.dirname(self.devices_file), exist_ok=True)
        with open(self.devices_file, 'w', encoding='utf-8') as f:
            json.dump(devices, f, indent=2, ensure_ascii=False)

    def _skip_auto_config(self, conn, vendor):
        """跳过 H3C/Huawei 'Automatic configuration is running' 提示"""
        if vendor not in ('h3c', 'huawei'):
            return
        try:
            for _ in range(3):
                conn.write_channel('\x03')
                time.sleep(1)
                buf = conn.read_channel()
                if '<' in buf or '[' in buf or 'aborted' in buf.lower():
                    break
            conn.write_channel('\n')
            time.sleep(1)
            conn.read_channel()
        except Exception as e:
            log.debug("跳过启动提示失败", error=str(e))
            pass

    def execute_tool(self, tool_name, arguments):
        """执行工具调用"""
        if tool_name == "run_commands":
            device_name = arguments.get("device", "")
            commands = arguments.get("commands", [])
            device = self._find_device(device_name)
            if not device:
                return {"success": False, "error": f"找不到设备 '{device_name}'，请用 list_devices 查看可用设备"}
            conn_type = device.get('conn_type', 'ssh')
            if conn_type == 'telnet':
                return self._telnet_connect(device_name, commands)
            else:
                return self._ssh_connect(device_name, commands)
        elif tool_name == "list_devices":
            return self._list_devices()
        elif tool_name == "ssh_connect":
            return self._ssh_connect(
                arguments.get("device", ""),
                arguments.get("commands", [])
            )
        elif tool_name == "telnet_connect":
            return self._telnet_connect(
                arguments.get("device", ""),
                arguments.get("commands", [])
            )
        elif tool_name == "get_device_info":
            return self._get_device_info(arguments.get("device", ""))
        else:
            return {"success": False, "error": f"未知工具: {tool_name}"}

    def _list_devices(self):
        """列出所有设备"""
        devices = self.load_devices()
        return {
            "success": True,
            "devices": [
                {
                    "name": d.get("remark") or d.get("name"),
                    "ip": d.get("ip"),
                    "port": d.get("port"),
                    "type": d.get("conn_type", "ssh"),
                    "vendor": d.get("vendor", "unknown")
                }
                for d in devices
            ]
        }

    def _get_device_info(self, device_name):
        """获取设备信息"""
        devices = self.load_devices()
        for d in devices:
            if d.get("name") == device_name or d.get("ip") == device_name or d.get("remark") == device_name:
                return {"success": True, "device": d}
        return {"success": False, "error": f"设备 {device_name} 不存在"}

    def execute_command_on_device(self, device_name: str, commands: list, skip_backup: bool = False) -> dict:
        """在设备上执行命令（公共接口，自动判断 SSH/Telnet）

        供 WebSSHAdapter、diagnosis_adapter 等外部模块调用，
        不应直接调用 _ssh_connect / _telnet_connect 等私有方法。

        Args:
            device_name: 设备名/备注/IP
            commands: 命令列表
            skip_backup: 跳过自动备份（备份操作调用时设为 True）

        Returns:
            dict: {success, device, results, snapshot_id?}
        """
        device = self._find_device(device_name)
        if not device:
            return {"success": False, "error": f"设备 {device_name} 不存在"}

        conn_type = device.get('conn_type', 'ssh')
        if conn_type == 'telnet':
            return self._telnet_connect(device_name, commands, skip_backup=skip_backup)
        else:
            return self._ssh_connect(device_name, commands, skip_backup=skip_backup)

    def find_device(self, device_name: str):
        """查找设备（公共接口）

        供外部模块调用，不应直接访问 _find_device。
        Returns:
            dict or None: 设备信息
        """
        return self._find_device(device_name)

    def _find_device(self, device_name):
        """查找设备（支持 name、remark、ip，模糊匹配）"""
        devices = self.load_devices()
        # 精确匹配优先：remark > ip > name
        for d in devices:
            if d.get("remark") == device_name:
                return d
        for d in devices:
            if d.get("ip") == device_name:
                return d
        for d in devices:
            if d.get("name") == device_name:
                return d
        # 模糊匹配
        for d in devices:
            if device_name and device_name in (d.get("remark") or ""):
                return d
            if device_name and device_name in (d.get("name") or ""):
                return d
        # IP:端口 格式
        if ':' in device_name:
            ip_part = device_name.split(':')[0]
            for d in devices:
                if d.get("ip") == ip_part:
                    return d
        return None

    # 查看命令前缀 —— 这些永远不进系统视图
    _QUERY_PREFIXES = ('display ', 'show ', 'dir ', 'ping ', 'tracert ', 'traceroute ')
    # 进入配置模式的命令 —— 不需要自动加 system-view
    _ENTER_CONFIG_PREFIXES = ('system-view', 'configure terminal', 'conf t')
    # 退出配置模式的命令 —— 不需要自动加 system-view
    _EXIT_PREFIXES = ('return', 'quit', 'exit', 'end')
    # 需要系统视图的配置命令前缀（仅当不是查看命令时才生效）
    _CONFIG_PREFIXES = [
        'lldp enable', 'lldp disable', 'lldp global',
        'interface ', 'vlan ', 'port ', 'undo ',
        'ospf', 'bgp', 'acl ',
        'ssh server', 'telnet server',
        'ip route', 'ip address', 'dhcp ', 'nat ', 'security-zone',
        'password', 'local-user', 'radius', 'hostname',
        'stp ', 'mac-address', 'description', 'shutdown', 'undo shutdown',
    ]

    # ====== 厂商命令映射 ======
    # 华为/H3C 系用 display/system-view/undo/save
    # 思科系用 show/configure terminal/no/write
    # 锐捷类似华为
    # Juniper 类似思科但用 set/delete
    _VENDOR_COMMAND_MAP = {
        'huawei': {
            'view_cmd': 'display',
            'config_enter': 'system-view',
            'negate': 'undo',
            'save': 'save',
            'bad_prefixes': ('show ', 'configure terminal', 'conf t', 'write', 'no '),
        },
        'h3c': {
            'view_cmd': 'display',
            'config_enter': 'system-view',
            'negate': 'undo',
            'save': 'save',
            'bad_prefixes': ('show ', 'configure terminal', 'conf t', 'write', 'no '),
        },
        'cisco': {
            'view_cmd': 'show',
            'config_enter': 'configure terminal',
            'negate': 'no',
            'save': 'write',
            'bad_prefixes': ('display ', 'system-view', 'undo '),
        },
        'cisco_nxos': {
            'view_cmd': 'show',
            'config_enter': 'configure terminal',
            'negate': 'no',
            'save': 'copy running-config startup-config',
            'bad_prefixes': ('display ', 'system-view', 'undo '),
        },
        'ruijie': {
            'view_cmd': 'show',
            'config_enter': 'configure terminal',
            'negate': 'no',
            'save': 'write',
            'bad_prefixes': ('display ', 'system-view', 'undo '),
        },
        'juniper': {
            'view_cmd': 'show',
            'config_enter': 'configure',
            'negate': 'delete',
            'save': 'commit',
            'bad_prefixes': ('display ', 'system-view', 'undo '),
        },
        'arista': {
            'view_cmd': 'show',
            'config_enter': 'configure terminal',
            'negate': 'no',
            'save': 'write',
            'bad_prefixes': ('display ', 'system-view', 'undo '),
        },
    }

    def _validate_vendor_command(self, cmd, vendor):
        """校验命令是否符合设备厂商语法，返回错误信息或 None"""
        cmd_stripped = cmd.strip()
        if not cmd_stripped:
            return None  # 空命令不校验

        # 通用命令不校验（ping/tracert/quit/return 等）
        _SKIP_CHECK = ('ping', 'tracert', 'traceroute', 'quit', 'return', 'exit', 'end', 'save')
        if any(cmd_stripped.lower().startswith(s) for s in _SKIP_CHECK):
            return None

        vendor_map = self._VENDOR_COMMAND_MAP.get(vendor)
        if not vendor_map:
            return None  # 未知厂商不校验

        bad = vendor_map.get('bad_prefixes', ())
        for bp in bad:
            if cmd_stripped.lower().startswith(bp.lower()):
                correct_view = vendor_map['view_cmd']
                correct_config = vendor_map['config_enter']
                correct_negate = vendor_map['negate']
                # 生成修正建议
                if bp.strip().lower() in ('show', 'configure terminal', 'conf t', 'write', 'no'):
                    # 思科命令用在华为设备上
                    return (f'当前设备是 {vendor} 系列，不应使用 "{bp.strip()}" 命令。'
                            f'请用 "{correct_view}" 代替 "show"，'
                            f'"{correct_config}" 代替 "configure terminal"，'
                            f'"{correct_negate}" 代替 "no"')
                elif bp.strip().lower() in ('display', 'system-view', 'undo'):
                    # 华为命令用在思科设备上
                    return (f'当前设备是 {vendor} 系列，不应使用 "{bp.strip()}" 命令。'
                            f'请用 "{correct_view}" 代替 "display"，'
                            f'"{correct_config}" 代替 "system-view"，'
                            f'"{correct_negate}" 代替 "undo"')
                else:
                    return f'当前设备是 {vendor} 系列，命令 "{cmd_stripped[:50]}" 语法不符'

        return None

    def _send_cmd(self, conn, cmd, vendor):
        """在设备上执行单条命令，自动处理系统视图

        核心逻辑：
        1. display/show 开头 → 查看命令，不进系统视图
        2. system-view/conf t 开头 → 用户手动进配置模式，不重复进
        3. return/quit/exit/end → 退出命令，不进系统视图
        4. 其余匹配配置关键词 → 自动进系统视图，执行后 return 退出
        5. save → 在用户视图执行，不进系统视图
        """
        # ====== 厂商命令校验 ======
        err = self._validate_vendor_command(cmd, vendor)
        if err:
            return f'⚠️ 命令校验失败: {err}'

        cmd_lower = cmd.strip().lower()

        is_query = any(cmd_lower.startswith(p) for p in self._QUERY_PREFIXES)
        is_entering_config = any(cmd_lower.startswith(p) for p in self._ENTER_CONFIG_PREFIXES)
        is_exiting = any(cmd_lower.startswith(p) for p in self._EXIT_PREFIXES)
        is_save = cmd_lower == 'save' or cmd_lower.startswith('save ')

        need_sys_view = (not is_query and not is_entering_config
                         and not is_exiting and not is_save
                         and any(cmd_lower.startswith(k) for k in self._CONFIG_PREFIXES))

        if need_sys_view:
            conn.write_channel('system-view\n')
            time.sleep(1)
            conn.read_channel()

        conn.write_channel(cmd + '\n')
        # 自适应等待：根据命令类型和输出长度调整
        base_wait = 2.0  # 默认等待
        if any(k in cmd_lower for k in ('save', 'display current', 'show running')):
            base_wait = 4.0  # 保存/全量配置需要更久
        elif any(k in cmd_lower for k in ('ping', 'tracert', 'traceroute')):
            base_wait = 5.0  # ping 需要等结果
        time.sleep(base_wait)
        output = conn.read_channel()

        # 如果输出还在自动配置，跳过再执行一次
        if 'Automatic' in output:
            self._skip_auto_config(conn, vendor)
            if need_sys_view:
                conn.write_channel('system-view\n')
                time.sleep(1)
                conn.read_channel()
            conn.write_channel(cmd + '\n')
            time.sleep(3)
            output = conn.read_channel()

        if need_sys_view:
            conn.write_channel('return\n')
            time.sleep(0.5)
            conn.read_channel()

        # 清理回显
        lines = output.split('\n')
        filtered = [link for link in lines if cmd not in link]
        return '\n'.join(filtered).strip()

    def _ssh_connect(self, device_name, commands, skip_backup=False):
        """SSH 连接并执行命令

        自动在执行配置命令前备份当前配置（用于回滚）
        安全守卫检查命令风险等级

        Args:
            skip_backup: 内部用，备份操作调用时跳过再备份（避免无限递归）
        """
        device = self._find_device(device_name)
        if not device:
            return {"success": False, "error": f"设备 {device_name} 不存在"}

        # ====== 命令安全检查 ======
        vendor = device.get("vendor", "huawei")
        device_type_map = {
            "huawei": "huawei",
            "h3c": "huawei",
            "cisco": "cisco_ios",
            "juniper": "juniper_junos"
        }
        netmiko_type = device_type_map.get(vendor, "huawei")

        if COMMAND_GUARD_AVAILABLE:
            guard = CommandGuard(vendor=netmiko_type)
            guard_result = guard.check_commands(commands)
            # 拦截极高风险命令
            if guard_result.blocked_commands:
                return {
                    "success": False,
                    "error": f"安全检查未通过，{len(guard_result.blocked_commands)} 条命令被拦截",
                    "blocked_commands": guard_result.blocked_commands,
                    "guard_report": guard.format_guard_report(guard_result),
                }

        # ====== 自动备份：如果有配置命令，先存快照 ======
        has_config_cmd = any(
            not any(c.strip().lower().startswith(p) for p in self._QUERY_PREFIXES)
            and not any(c.strip().lower().startswith(p) for p in self._EXIT_PREFIXES)
            for c in commands
        )
        snapshot_id = None
        if has_config_cmd and not skip_backup:
            snapshot_id = self._save_config_snapshot(device)

        if not device.get("username"):
            device = dict(device)
            device["username"] = ""
        if not device.get("password"):
            device = dict(device)
            device["password"] = ""

        try:
            from netmiko import ConnectHandler

            conn_params = {
                "device_type": netmiko_type,
                "host": device.get("ip"),
                "port": device.get("port", 22),
                "username": device.get("username"),
                "password": device.get("password"),
                "timeout": 10,
                "conn_timeout": 8,
            }

            results = []
            with ConnectHandler(**conn_params) as conn:
                self._skip_auto_config(conn, vendor)
                for cmd in commands:
                    output = self._send_cmd(conn, cmd, vendor)
                    results.append({"command": cmd, "output": output})

            return {"success": True, "device": device.get("remark") or device.get("name"), "results": results, "snapshot_id": snapshot_id}

        except ImportError:
            return {"success": False, "error": "netmiko 未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _save_config_snapshot(self, device):
        """执行配置命令前，自动备份当前 running-config"""
        try:
            from datetime import datetime
            dev_label = device.get('remark') or device.get('name') or 'unknown'
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            snapshot_id = f"{dev_label}_{timestamp}"

            # 获取当前配置
            vendor = device.get('vendor', 'huawei')
            if vendor in ('huawei', 'h3c'):
                backup_cmd = 'display current-configuration'
            else:
                backup_cmd = 'show running-config'

            conn_type = device.get('conn_type', 'ssh')
            if conn_type == 'telnet':
                result = self._telnet_connect(dev_label, [backup_cmd])
            else:
                # skip_backup=True 防止无限递归：备份操作不再触发备份
                result = self._ssh_connect(dev_label, [backup_cmd], skip_backup=True)

            if result.get('success') and result.get('results'):
                config_text = result['results'][0].get('output', '')
                snapshot_dir = os.path.join(os.path.dirname(self.devices_file), 'snapshots')
                os.makedirs(snapshot_dir, exist_ok=True)
                snapshot_path = os.path.join(snapshot_dir, f'{snapshot_id}.cfg')
                with open(snapshot_path, 'w', encoding='utf-8') as f:
                    f.write(config_text)
                return snapshot_id
            else:
                return None
        except Exception as e:
            import sys
            sys.stderr.write(f'Snapshot error: {e}\n')
            return None

    def rollback_config(self, device_name, snapshot_id):
        """回滚到指定快照配置"""
        snapshot_dir = os.path.join(os.path.dirname(self.devices_file), 'snapshots')
        snapshot_path = os.path.join(snapshot_dir, f'{snapshot_id}.cfg')

        if not os.path.exists(snapshot_path):
            return {"success": False, "error": f"快照 {snapshot_id} 不存在"}

        with open(snapshot_path, 'r', encoding='utf-8') as f:
            saved_config = f.read()

        device = self._find_device(device_name)
        if not device:
            return {"success": False, "error": f"设备 {device_name} 不存在"}

        dev_label = device.get('remark') or device.get('name')
        config_lines = [link.strip() for link in saved_config.split('\n') if link.strip() and not link.startswith('#')]

        if len(config_lines) > 100:
            return {"success": False, "error": f"配置超过 100 行({len(config_lines)}行)，建议手动回滚。快照已保存: {snapshot_path}"}

        conn_type = device.get('conn_type', 'ssh')
        if conn_type == 'telnet':
            result = self._telnet_connect(dev_label, config_lines)
        else:
            result = self._ssh_connect(dev_label, config_lines)

        if result.get('success'):
            result['rolled_back'] = True
            result['snapshot_id'] = snapshot_id
        return result

    def list_snapshots(self, device_name=None):
        """列出配置快照"""
        snapshot_dir = os.path.join(os.path.dirname(self.devices_file), 'snapshots')
        if not os.path.exists(snapshot_dir):
            return []

        snapshots = []
        for f in sorted(os.listdir(snapshot_dir), reverse=True):
            if not f.endswith('.cfg'):
                continue
            name = f[:-4]
            if device_name and not name.startswith(device_name):
                continue
            snapshots.append({
                'id': name,
                'file': f,
                'size': os.path.getsize(os.path.join(snapshot_dir, f)),
            })
        return snapshots[:20]

    def _telnet_connect(self, device_name, commands, skip_backup=False):
        """Telnet 连接并执行命令"""
        device = self._find_device(device_name)
        if not device:
            return {"success": False, "error": f"设备 {device_name} 不存在"}

        try:
            import time
            from netmiko import ConnectHandler

            vendor = device.get("vendor", "huawei")
            username = device.get("username") or ""
            password = device.get("password") or ""

            # 免凭证 Telnet：用 generic_termserver_telnet（厂商驱动强制认证，免凭证连不上）
            # 有凭证时用厂商驱动（能自动识别prompt和分页）
            if not username and not password:
                device_type = "generic_termserver_telnet"
            else:
                telnet_type_map = {
                    "huawei": "huawei_telnet",
                    "h3c": "hp_comware_telnet",
                    "cisco": "cisco_ios_telnet",
                }
                device_type = telnet_type_map.get(vendor, "generic_telnet")

            conn_params = {
                "device_type": device_type,
                "host": device.get("ip"),
                "port": device.get("port", 23),
                "timeout": 15,
                "conn_timeout": 8,
            }
            if username:
                conn_params["username"] = username
            if password:
                conn_params["password"] = password

            results = []
            with ConnectHandler(**conn_params) as conn:
                # H3C/Huawei 免凭证：中断 auto-config 提示
                if not username and not password and vendor in ("h3c", "huawei"):
                    conn.write_channel("\x03")  # Ctrl+C
                    time.sleep(2)
                    conn.write_channel("\n")   # Enter to get prompt
                    time.sleep(1)
                    conn.read_channel()  # 丢弃 auto-config 提示

                for cmd in commands:
                    if not username and not password:
                        # generic_termserver 不支持 send_command，用原始通道
                        conn.write_channel(cmd + "\n")
                        time.sleep(2)
                        output = conn.read_channel()
                    else:
                        output = self._send_cmd(conn, cmd, vendor)
                    results.append({"command": cmd, "output": output})

            return {"success": True, "device": device.get("remark") or device.get("name"), "results": results}

        except ImportError:
            return {"success": False, "error": "netmiko 未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _serial_connect(self, port, baud, commands):
        """串口连接并执行命令"""
        try:
            import serial as pyserial

            ser = pyserial.Serial(
                port=port,
                baudrate=baud,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=5
            )

            time.sleep(1)
            ser.write(b'\r\n')
            time.sleep(0.5)

            results = []
            for cmd in commands:
                ser.write((cmd + '\r\n').encode('utf-8'))
                time.sleep(2)
                output = ser.read(ser.in_waiting or 4096).decode('utf-8', errors='ignore')
                results.append({"command": cmd, "output": output})

            ser.close()
            return {"success": True, "device": port, "results": results}

        except ImportError:
            return {"success": False, "error": "pyserial 未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def get_tools_definition():
    """返回工具定义（供 LLM tool calling 使用）"""
    return [
        {
            "type": "function",
            "function": {
                "name": "run_commands",
                "description": "登录网络设备执行命令。自动根据设备的连接类型（SSH/Telnet）选择连接方式，你不需要关心连接方式。支持查询命令和配置命令，配置命令会自动进入配置模式。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device": {"type": "string", "description": "设备备注名（如'核心交换机'、'接入交换机'、'出口路由'）或IP地址"},
                        "commands": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要执行的命令列表。不要写system-view/return/quit，系统自动处理。例如查看VLAN: [\"display vlan brief\"], 配置trunk口: [\"interface GigabitEthernet1/0/1\", \"port link-type trunk\", \"port trunk permit vlan all\"]"
                        }
                    },
                    "required": ["device", "commands"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_devices",
                "description": "列出所有已管理的网络设备及其基本信息",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]
