#!/usr/bin/env python3
"""
NetOps AI - SSH/Telnet Tools for LLM
类似 MCP Server，提供工具给 LLM 调用
"""

import json
import subprocess
import os

# 工具定义 - LLM 可以调用的工具
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ssh_connect",
            "description": "通过 SSH 连接网络设备并执行命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "设备名称或 IP 地址"
                    },
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要执行的命令列表"
                    }
                },
                "required": ["device", "commands"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telnet_connect",
            "description": "通过 Telnet 连接网络设备并执行命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "设备名称或 IP 地址"
                    },
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要执行的命令列表"
                    }
                },
                "required": ["device", "commands"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "serial_connect",
            "description": "通过串口连接网络设备并执行命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "port": {
                        "type": "string",
                        "description": "串口设备，如 COM1 或 /dev/ttyUSB0"
                    },
                    "baud": {
                        "type": "integer",
                        "description": "波特率，默认 9600"
                    },
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要执行的命令列表"
                    }
                },
                "required": ["port", "commands"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "列出所有已配置的网络设备",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_info",
            "description": "获取指定设备的详细信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "设备名称"
                    }
                },
                "required": ["device"]
            }
        }
    }
]


class NetOpsTools:
    """NetOps 工具执行器"""
    
    def __init__(self, devices_file):
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
                    "name": d.get("name"),
                    "ip": d.get("ip"),
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
            if d.get("name") == device_name or d.get("ip") == device_name:
                return {"success": True, "device": d}
        return {"success": False, "error": f"设备 {device_name} 不存在"}
    
    def _find_device(self, device_name):
        """查找设备"""
        devices = self.load_devices()
        for d in devices:
            if d.get("name") == device_name or d.get("ip") == device_name:
                return d
        return None
    
    def _ssh_connect(self, device_name, commands):
        """SSH 连接并执行命令"""
        device = self._find_device(device_name)
        if not device:
            return {"success": False, "error": f"设备 {device_name} 不存在"}
        
        if not device.get("username") or not device.get("password"):
            return {"success": False, "error": "设备缺少用户名或密码"}
        
        try:
            from netmiko import ConnectHandler
            
            vendor = device.get("vendor", "huawei")
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
                "timeout": 30,
            }
            
            results = []
            with ConnectHandler(**conn_params) as conn:
                for cmd in commands:
                    output = conn.send_command(cmd, read_timeout=30)
                    results.append({
                        "command": cmd,
                        "output": output
                    })
            
            return {
                "success": True,
                "device": device.get("name"),
                "results": results
            }
        
        except ImportError:
            return {"success": False, "error": "netmiko 未安装，请执行: pip install netmiko"}
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

            telnet_type_map = {
                "huawei": "huawei_telnet",
                "h3c": "hp_comware_telnet",
                "cisco": "cisco_ios_telnet",
            }
            device_type = telnet_type_map.get(vendor, "generic_telnet")

            # 测试模拟器常见为免登录 Telnet，使用 termserver 驱动避免强制登录提示。
            if not username and not password:
                device_type = "generic_termserver_telnet"

            conn_params = {
                "device_type": device_type,
                "host": device.get("ip"),
                "port": device.get("port", 23),
                "username": username,
                "password": password,
                "timeout": 30,
            }

            results = []
            with ConnectHandler(**conn_params) as conn:
                # H3C/Huawei 配置命令通常需要先进入 system-view。
                if vendor in ["h3c", "huawei"]:
                    conn.send_command_timing("system-view", read_timeout=30)

                for cmd in commands:
                    # 免登录 Telnet/模拟器常见无法稳定识别提示符，使用 timing 模式更稳。
                    output = conn.send_command_timing(cmd, read_timeout=30)
                    results.append({
                        "command": cmd,
                        "output": output,
                    })

            return {
                "success": True,
                "device": device.get("name"),
                "results": results,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _serial_connect(self, port, baud, commands):
        """串口连接并执行命令"""
        try:
            import serial
            import time
            
            ser = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=5
            )
            
            time.sleep(1)
            
            # 发送回车
            ser.write(b'\r\n')
            time.sleep(0.5)
            
            results = []
            for cmd in commands:
                ser.write((cmd + '\r\n').encode())
                time.sleep(1)
                output = ser.read(8192).decode('utf-8', errors='ignore')
                results.append({
                    "command": cmd,
                    "output": output
                })
            
            ser.close()
            
            return {
                "success": True,
                "port": port,
                "results": results
            }
        
        except ImportError:
            return {"success": False, "error": "pyserial 未安装，请执行: pip install pyserial"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def get_tools_definition():
    """返回工具定义，用于 LLM 函数调用"""
    return TOOLS