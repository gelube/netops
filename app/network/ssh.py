"""
SSH连接模块
使用Netmiko连接网络设备
"""
import socket
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False
    ConnectHandler = None

from app.core.device import Vendor, Device, Interface, PortType, PortStatus
from app.core.vendor import VendorIdentifier
from app.network.commands import CommandBuilder


@dataclass
class ConnectionInfo:
    """连接信息"""
    ip: str
    port: int = 22
    username: str = ""
    password: str = ""
    device_type: str = "auto"  # netmiko device_type


class DeviceConnection:
    """设备连接管理器"""
    
    # Netmiko设备类型映射
    VENDOR_DEVICE_TYPE_MAP = {
        Vendor.HUAWEI: "huawei",
        Vendor.H3C: "hp_comware",
        Vendor.CISCO: "cisco_ios",
        Vendor.JUNIPER: "juniper_junos",
        Vendor.RUIJIE: "ruijie_os",
        # 扩展厂商
        Vendor.ARISTA: "arista_eos",
        Vendor.DELL: "dell_os10",
        Vendor.HP: "hp_procurve",
        Vendor.FORTINET: "fortinet",
        Vendor.PALOALTO: "paloalto_panos",
        Vendor.MIKROTIK: "mikrotik_routeros",
        Vendor.UBNT: "ubiquiti_edgerouter",
        Vendor.ZTE: "zte_zxros",
        Vendor.ZYXEL: "zyxel_os",
        Vendor.TPLINK: "tplink_jetstream",
        Vendor.HUAWEI_CLOUDENGINE: "huawei_vrpv8",
        Vendor.CISCO_NXOS: "cisco_nxos",
        Vendor.CISCO_XR: "cisco_xr",
    }
    
    def __init__(self, conn_info: ConnectionInfo, timeout: int = 30):
        self.conn_info = conn_info
        self.timeout = timeout
        self.connection = None
        self.vendor = Vendor.UNKNOWN
        self.device_info: Optional[Device] = None
    
    def connect(self) -> bool:
        """建立SSH连接"""
        if not NETMIKO_AVAILABLE:
            raise ImportError("netmiko未安装，请运行: pip install netmiko")
        
        # 确定设备类型
        device_type = self._get_device_type()
        
        # 构建连接参数
        device_params = {
            'device_type': device_type,
            'host': self.conn_info.ip,
            'port': self.conn_info.port,
            'username': self.conn_info.username,
            'password': self.conn_info.password,
            'timeout': self.timeout,
            'global_delay_factor': 0.5,
        }
        
        try:
            self.connection = ConnectHandler(**device_params)
            # 获取设备基本信息
            self.vendor = self._identify_vendor()
            return True
        except NetmikoAuthenticationException:
            raise Exception(f"认证失败: {self.conn_info.ip}")
        except NetmikoTimeoutException:
            raise Exception(f"连接超时: {self.conn_info.ip}")
        except Exception as e:
            raise Exception(f"连接失败 {self.conn_info.ip}: {str(e)}")
    
    # prompt/输出特征 → netmiko device_type 映射（用于快速检测）
    PROMPT_VENDOR_MAP = [
        (r'[<\[]\S+[>#\]]', 'huawei'),          # <SW-Core> or [SW-Core]
        (r'\S+[>#]\s*$', 'cisco_ios'),           # SW-Core# or SW-Core>
        (r'\S+:\S+[>#]', 'hp_comware'),           # H3C: <SW-Core> or SW-Core#
        (r'\S+@[\w-]+>', 'juniper_junos'),        # user@router>
        (r'\S+#\s*$', 'ruijie_os'),               # Ruijie#
        (r'\S+>', 'arista_eos'),                   # arista>
        (r'\S+#\s*$', 'cisco_nxos'),              # Nexus#
    ]

    # 版本输出关键词 → device_type 映射
    VERSION_KEYWORDS_MAP = {
        'huawei': ['huawei', 'vrp', 'versal', r's\d{4}', r'ar\d{4}', r'ne\d', 'usg'],
        'hp_comware': ['h3c', 'comware', '3com', r's\d{4}', 'msr'],
        'cisco_ios': ['cisco', 'ios', r'c\d{4}'],
        'cisco_nxos': ['nx-os', 'nexus', 'nxos'],
        'cisco_xr': ['ios-xr', 'ios xr'],
        'juniper_junos': ['juniper', 'junos'],
        'ruijie_os': ['ruijie', 'rgos'],
        'arista_eos': ['arista', 'eos'],
        'huawei_vrpv8': ['cloudengine', r'ce\d{4}', 'vrpv8'],
        'fortinet': ['fortigate', 'fortios'],
        'paloalto_panos': ['paloalto', 'pan-os'],
    }

    def _get_device_type(self) -> str:
        """获取netmiko设备类型 — 智能检测，不再暴力尝试17种类型"""
        if self.conn_info.device_type != "auto":
            return self.conn_info.device_type

        # 策略1：用 autodetect（netmiko内置，1次连接搞定）
        try:
            from netmiko import SSHDetect
            guesser = SSHDetect(
                host=self.conn_info.ip,
                port=self.conn_info.port,
                username=self.conn_info.username,
                password=self.conn_info.password,
                timeout=15,
            )
            best_match = guesser.autodetect()
            guesser.connection.disconnect()
            if best_match:
                return best_match
        except Exception:
            pass

        # 策略2：用cisco_ios连一次，读版本信息本地判断
        try:
            temp_conn = ConnectHandler(
                device_type='cisco_ios',
                host=self.conn_info.ip,
                port=self.conn_info.port,
                username=self.conn_info.username,
                password=self.conn_info.password,
                timeout=15,
            )
            # 读提示符和版本
            prompt = temp_conn.find_prompt() or ''
            try:
                version_output = temp_conn.send_command_timing('show version', delay_factor=1, timeout=10)
            except Exception:
                version_output = ''
            temp_conn.disconnect()

            detected = self._detect_type_from_output(prompt, version_output)
            if detected:
                return detected
        except Exception:
            pass

        # 默认cisco_ios
        return 'cisco_ios'

    @classmethod
    def _detect_type_from_output(cls, prompt: str, version_output: str) -> str:
        """从提示符和版本输出推断netmiko device_type"""
        import re as _re
        text = f'{prompt} {version_output}'.lower()

        # 版本关键词匹配（优先）
        for dtype, keywords in cls.VERSION_KEYWORDS_MAP.items():
            for kw in keywords:
                if _re.search(kw, text, _re.IGNORECASE):
                    return dtype

        # 提示符模式匹配
        for pattern, dtype in cls.PROMPT_VENDOR_MAP:
            if _re.search(pattern, prompt):
                return dtype

        return ''
    
    def _identify_vendor(self) -> Vendor:
        """识别厂商"""
        try:
            version_output = self.execute_command(CommandBuilder.get_version(Vendor.UNKNOWN))
            vendor, model, device_type = VendorIdentifier.identify_from_command_output(version_output)
            return vendor
        except:
            return Vendor.UNKNOWN
    
    def execute_command(self, command: str, timeout: int = 30) -> str:
        """执行命令"""
        if not self.connection:
            raise Exception("未连接设备")
        
        output = self.connection.send_command_timing(
            command,
            delay_factor=1,
            timeout=timeout
        )
        return output
    
    def disconnect(self) -> None:
        """断开连接"""
        if self.connection:
            self.connection.disconnect()
            self.connection = None
    
    def get_device_info(self) -> Device:
        """获取设备完整信息"""
        device = Device(ip=self.conn_info.ip)
        
        try:
            # 获取版本信息
            version_output = self.execute_command(CommandBuilder.get_version(self.vendor))
            vendor, model, device_type = VendorIdentifier.identify_from_command_output(version_output)
            
            device.vendor = vendor if vendor != Vendor.UNKNOWN else self.vendor
            device.model = model
            device.device_type = device_type
            
            # 提取更多信息
            device.os_version = self._parse_os_version(version_output)
            device.name = self._parse_hostname(version_output)
            
            # 获取接口信息
            self._populate_interfaces(device)
            
        except Exception as e:
            print(f"获取设备信息失败: {e}")
        
        return device
    
    def _parse_hostname(self, output: str) -> str:
        """解析主机名"""
        import re
        
        # 华为
        match = re.search(r'Huawei\s+(\S+)', output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 思科
        match = re.search(r'(\S+) uptime', output)
        if match:
            return match.group(1)
        
        return self.conn_info.ip
    
    def _parse_os_version(self, output: str) -> str:
        """解析OS版本"""
        import re
        
        # 华为: Ver V200R019C10SPH200
        match = re.search(r'Ver(?:sion)?\s+([A-Z0-9]+)', output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 思科: Version 15.2(4)E
        match = re.search(r'Version\s+([^\s,]+)', output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return ""
    
    def _populate_interfaces(self, device: Device) -> None:
        """填充接口信息"""
        try:
            # 获取IP接口信息
            output = self.execute_command(CommandBuilder.get_ip_interface_brief(self.vendor))
            interfaces = self._parse_ip_interface_brief(output, self.vendor)
            device.interfaces.extend(interfaces)
        except Exception as e:
            print(f"获取接口信息失败: {e}")
    
    def _parse_ip_interface_brief(self, output: str, vendor: Vendor) -> List[Interface]:
        """解析IP接口简要信息"""
        interfaces = []
        lines = output.strip().split('\n')
        
        # 跳过标题行
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            # 根据厂商解析
            if vendor == Vendor.HUAWEI or vendor == Vendor.H3C:
                # 格式: Interface         IP Address      Physical  Protocol 
                #       GE0/0/0          10.0.0.1      up       up
                parts = line.split()
                if len(parts) >= 4:
                    iface = Interface(name=parts[0])
                    if parts[1] != '--' and parts[1] != 'unassigned':
                        iface.ip = parts[1]
                    
                    if 'up' in line.lower():
                        iface.status = PortStatus.UP
                    elif 'down' in line.lower():
                        iface.status = PortStatus.DOWN
                    
                    # 判断类型
                    if 'Loopback' in parts[0]:
                        iface.port_type = PortType.LOOPBACK
                    elif 'Vlanif' in parts[0] or 'Vlan' in parts[0]:
                        iface.port_type = PortType.VLAN_INTERFACE
                    elif 'Eth-trunk' in parts[0] or 'Po' in parts[0]:
                        iface.port_type = PortType.AGGREGATE
                    
                    interfaces.append(iface)
            
            elif vendor == Vendor.CISCO:
                # 格式: Interface    IP-Address      OK? Method Status    Protocol
                #         GigabitEthernet0/0  10.0.0.1   YES manual up          up
                parts = line.split()
                if len(parts) >= 6:
                    iface = Interface(name=parts[0])
                    if parts[1] != 'unassigned':
                        iface.ip = parts[1]
                    
                    if 'up' in parts[4].lower():
                        iface.status = PortStatus.UP
                    elif 'down' in parts[4].lower():
                        iface.status = PortStatus.DOWN
                    
                    # 判断类型
                    if 'Loopback' in parts[0]:
                        iface.port_type = PortType.LOOPBACK
                    elif 'Vlan' in parts[0]:
                        iface.port_type = PortType.VLAN_INTERFACE
                    elif 'Port-channel' in parts[0]:
                        iface.port_type = PortType.AGGREGATE
                    
                    interfaces.append(iface)
        
        return interfaces
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def test_connection(ip: str, port: int = 22, timeout: int = 5) -> bool:
    """测试IP端口是否可达"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((ip, port))
        return result == 0
    except:
        return False
    finally:
        sock.close()


def get_lldp_neighbors(connection: 'DeviceConnection') -> list:
    """获取 LLDP/CDP 邻居信息（模块级函数）"""
    from app.network.lldp import LLDPNeighborParser
    from app.network.commands import CommandBuilder

    try:
        # 获取 LLDP 邻居
        if connection.vendor in [Vendor.HUAWEI, Vendor.H3C]:
            output = connection.execute_command(CommandBuilder.get_lldp_neighbor(connection.vendor))
        elif connection.vendor == Vendor.CISCO:
            # 思科先试 CDP
            output = connection.execute_command("show cdp neighbors detail")
            if not output or "CDP is not enabled" in output:
                output = connection.execute_command("show lldp neighbors detail")
        else:
            output = connection.execute_command(CommandBuilder.get_lldp_neighbor(connection.vendor))

        # 解析邻居信息
        neighbors = LLDPNeighborParser.parse_lldp_neighbor(output, connection.vendor)
        return neighbors

    except Exception as e:
        print(f"获取 LLDP 邻居失败：{e}")
        return []