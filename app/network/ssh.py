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
    
    def _get_device_type(self) -> str:
        """获取netmiko设备类型"""
        if self.conn_info.device_type != "auto":
            return self.conn_info.device_type
        
        # 尝试自动检测
        for vendor, dtype in self.VENDOR_DEVICE_TYPE_MAP.items():
            try:
                test_conn = ConnectHandler(
                    device_type=dtype,
                    host=self.conn_info.ip,
                    port=self.conn_info.port,
                    username=self.conn_info.username,
                    password=self.conn_info.password,
                    timeout=10,
                )
                test_conn.disconnect()
                return dtype
            except:
                continue
        
        # 默认使用cisco_ios
        return "cisco_ios"
    
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
    
    def get_lldp_neighbors(self) -> List['NeighborInfo']:
        """获取 LLDP/CDP 邻居信息"""
        from app.network.lldp import LLDPNeighborParser
        from app.network.commands import CommandBuilder
        
        try:
            # 获取 LLDP 邻居
            if self.vendor in [Vendor.HUAWEI, Vendor.H3C]:
                output = self.execute_command(CommandBuilder.get_lldp_neighbor(self.vendor))
            elif self.vendor == Vendor.CISCO:
                # 思科先试 CDP
                output = self.execute_command("show cdp neighbors detail")
                if not output or "CDP is not enabled" in output:
                    output = self.execute_command("show lldp neighbors detail")
            else:
                output = self.execute_command(CommandBuilder.get_lldp_neighbor(self.vendor))
            
            # 解析邻居信息
            neighbors = LLDPNeighborParser.parse_lldp_neighbor(output, self.vendor)
            return neighbors
        
        except Exception as e:
            print(f"获取 LLDP 邻居失败：{e}")
            return []