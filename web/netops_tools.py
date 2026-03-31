import os
import json
import re
import time

DEVICES_FILE = r'Z:\netops-ai\web\data\devices.json'
CONFIG_FILE = r'Z:\netops-ai\web\data\llm_config.json'

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
            for _ in range(5):
                conn.write_channel('\x03')
                time.sleep(2)
                buf = conn.read_channel()
                if '<' in buf or '[' in buf or 'aborted' in buf.lower():
                    break
            conn.write_channel('\n')
            time.sleep(2)
            conn.read_channel()
        except Exception:
            pass

    def execute_tool(self, tool_name, arguments):
        """执行工具调用"""
        if tool_name == "list_devices":
            return self._list_devices()
        elif tool_name == "get_device_info":
            return self._get_device_info(arguments.get("device", ""))
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
        elif tool_name == "serial_connect":
            return self._serial_connect(
                arguments.get("port", "COM1"),
                arguments.get("baud", 9600),
                arguments.get("commands", [])
            )
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

    def _send_cmd(self, conn, cmd, vendor):
        """在设备上执行单条命令，自动处理系统视图"""
        # 需要系统视图的配置命令
        sys_view_keywords = [
            'lldp enable', 'lldp disable', 'interface ', 'vlan ',
            'ospf', 'bgp', 'acl ', 'ssh server', 'telnet server',
            'ip route', 'ip address', 'dhcp ', 'nat ', 'security-zone',
            'password', 'local-user', 'radius', 'hostname',
        ]
        need_sys_view = any(cmd.strip().lower().startswith(k) for k in sys_view_keywords)

        if need_sys_view:
            conn.write_channel('system-view\n')
            time.sleep(2)
            conn.read_channel()

        conn.write_channel(cmd + '\n')
        time.sleep(5)
        output = conn.read_channel()

        # 如果输出还在自动配置，跳过再执行一次
        if 'Automatic' in output:
            self._skip_auto_config(conn, vendor)
            if need_sys_view:
                conn.write_channel('system-view\n')
                time.sleep(2)
                conn.read_channel()
            conn.write_channel(cmd + '\n')
            time.sleep(5)
            output = conn.read_channel()

        if need_sys_view:
            conn.write_channel('return\n')
            time.sleep(1)
            conn.read_channel()

        # 清理回显
        lines = output.split('\n')
        filtered = [l for l in lines if cmd not in l]
        return '\n'.join(filtered).strip()

    def _ssh_connect(self, device_name, commands):
        """SSH 连接并执行命令"""
        device = self._find_device(device_name)
        if not device:
            return {"success": False, "error": f"设备 {device_name} 不存在"}

        if not device.get("username"):
            device = dict(device)
            device["username"] = ""
        if not device.get("password"):
            device = dict(device)
            device["password"] = ""

        try:
            from netmiko import ConnectHandler

            vendor = device.get("vendor", "huawei")
            conn_type = device.get("conn_type", "ssh")
            device_type_map = {
                "huawei": "huawei",
                "h3c": "huawei",
                "cisco": "cisco_ios",
                "juniper": "juniper_junos"
            }

            conn_params = {
                "device_type": device_type_map.get(vendor, "huawei"),
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

            return {"success": True, "device": device.get("remark") or device.get("name"), "results": results}

        except ImportError:
            return {"success": False, "error": "netmiko 未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _telnet_connect(self, device_name, commands):
        """Telnet 连接并执行命令"""
        device = self._find_device(device_name)
        if not device:
            return {"success": False, "error": f"设备 {device_name} 不存在"}

        try:
            from netmiko import ConnectHandler

            vendor = device.get("vendor", "huawei")
            username = device.get("username") or ""
            password = device.get("password") or ""

            # 免凭证 Telnet 用 generic_termserver_telnet
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
                "username": username,
                "password": password,
                "timeout": 15,
                "conn_timeout": 8,
            }

            results = []
            with ConnectHandler(**conn_params) as conn:
                self._skip_auto_config(conn, vendor)
                for cmd in commands:
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
                "name": "ssh_connect",
                "description": "SSH连接到网络设备执行命令",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device": {"type": "string", "description": "设备备注名或IP"},
                        "commands": {"type": "array", "items": {"type": "string"}, "description": "要执行的命令列表"}
                    },
                    "required": ["device", "commands"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "telnet_connect",
                "description": "Telnet连接到网络设备执行命令",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device": {"type": "string", "description": "设备备注名或IP"},
                        "commands": {"type": "array", "items": {"type": "string"}, "description": "要执行的命令列表"}
                    },
                    "required": ["device", "commands"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_devices",
                "description": "列出所有已添加的设备",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_device_info",
                "description": "获取设备详细信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device": {"type": "string", "description": "设备备注名或IP"}
                    },
                    "required": ["device"]
                }
            }
        }
    ]
