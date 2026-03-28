"""
设备数据模型定义
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class Vendor(str, Enum):
    """网络设备厂商"""
    HUAWEI = "huawei"
    H3C = "h3c"
    CISCO = "cisco"
    JUNIPER = "juniper"
    RUIJIE = "ruijie"
    UNKNOWN = "unknown"


class DeviceType(str, Enum):
    """设备类型"""
    ROUTER = "router"
    SWITCH_L3 = "switch_l3"
    SWITCH_L2 = "switch_l2"
    FIREWALL = "firewall"
    SERVER = "server"
    WIRELESS_AP = "wireless_ap"
    ENDPOINT = "endpoint"
    FIREWALL_NEXTGEN = "fw_ng"
    LOAD_BALANCER = "lb"
    UNKNOWN = "unknown"


class PortType(str, Enum):
    """端口类型"""
    NORMAL = "normal"
    AGGREGATE = "aggregate"
    VRRP = "vrrp"
    HSRP = "hsrp"
    GLBP = "glbp"
    STACK = "stack"
    LOOPBACK = "loopback"
    VLAN_INTERFACE = "vlan"
    TUNNEL = "tunnel"
    TRUNK = "trunk"
    OSPF = "ospf"
    BGP = "bgp"
    IPSEC = "ipsec"


class PortStatus(str, Enum):
    """端口状态"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class Interface(BaseModel):
    """接口模型"""
    name: str
    ip: Optional[str] = None
    status: PortStatus = PortStatus.UNKNOWN
    port_type: PortType = PortType.NORMAL
    bandwidth: Optional[int] = None  # Mbps
    description: Optional[str] = None
    vlan: Optional[int] = None
    mac: Optional[str] = None
    
    # 邻居信息
    neighbor_device: Optional[str] = None
    neighbor_interface: Optional[str] = None


class Device(BaseModel):
    """网络设备模型"""
    id: str = Field(default="")
    name: str = ""
    ip: str = ""
    vendor: Vendor = Vendor.UNKNOWN
    model: str = ""
    device_type: DeviceType = DeviceType.UNKNOWN
    os_version: str = ""
    serial_number: str = ""
    
    # 接口信息
    interfaces: List[Interface] = Field(default_factory=list)
    
    # 位置信息 (拓扑布局用)
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    
    # 额外信息
    management_vlan: Optional[int] = None
    vrrp_master: Optional[str] = None  # VRRP虚拟IP
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = self.ip or self.name
    
    @property
    def primary_ip(self) -> str:
        """获取主IP地址"""
        for iface in self.interfaces:
            if iface.ip and iface.port_type not in [PortType.LOOPBACK, PortType.VLAN_INTERFACE]:
                return iface.ip.split('/')[0]
        # 尝试获取第一个有效IP
        for iface in self.interfaces:
            if iface.ip:
                return iface.ip.split('/')[0]
        return self.ip
    
    @property
    def loopback_ip(self) -> str:
        """获取Loopback地址"""
        for iface in self.interfaces:
            if iface.port_type == PortType.LOOPBACK and iface.ip:
                return iface.ip.split('/')[0]
        return ""


class Link(BaseModel):
    """链路模型"""
    source_device: str  # 设备ID
    source_interface: str
    target_device: str
    target_interface: str
    link_type: str = "physical"  # physical, aggregate, vrrp, stack, ospf, bgp, vpn
    
    # 显示属性
    port_type: PortType = PortType.NORMAL
    
    @property
    def display_name(self) -> str:
        return f"{self.source_interface} → {self.target_interface}"


class Topology(BaseModel):
    """拓扑模型"""
    devices: List[Device] = Field(default_factory=list)
    links: List[Link] = Field(default_factory=list)
    
    def add_device(self, device: Device) -> None:
        """添加设备"""
        if not self.get_device(device.id):
            self.devices.append(device)
    
    def add_link(self, link: Link) -> None:
        """添加链路"""
        self.links.append(link)
    
    def get_device(self, device_id: str) -> Optional[Device]:
        """根据ID获取设备"""
        for dev in self.devices:
            if dev.id == device_id or dev.ip == device_id or dev.name == device_id:
                return dev
        return None
    
    def get_device_by_ip(self, ip: str) -> Optional[Device]:
        """根据IP获取设备"""
        return self.get_device(ip)
    
    def get_neighbors(self, device_id: str) -> List[Device]:
        """获取邻居设备列表"""
        neighbors = []
        dev = self.get_device(device_id)
        if not dev:
            return []
        
        for link in self.links:
            neighbor_id = None
            if link.source_device == device_id:
                neighbor_id = link.target_device
            elif link.target_device == device_id:
                neighbor_id = link.source_device
            
            if neighbor_id:
                neighbor = self.get_device(neighbor_id)
                if neighbor and neighbor not in neighbors:
                    neighbors.append(neighbor)
        
        return neighbors
    
    def remove_device(self, device_id: str) -> bool:
        """删除设备及其关联链路"""
        # 找到并删除设备
        device = self.get_device(device_id)
        if not device:
            return False
        
        self.devices.remove(device)
        
        # 删除与该设备关联的所有链路
        self.links = [link for link in self.links 
                      if link.source_device != device_id and link.target_device != device_id]
        
        return True