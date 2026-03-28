"""
LLDP/CDP邻居解析模块
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from app.core.device import Vendor, Link, PortType


@dataclass
class NeighborInfo:
    """邻居信息"""
    device_id: str          # 邻居设备ID (hostname 或 MAC)
    ip: str                 # 邻居IP
    local_interface: str    # 本地接口
    remote_interface: str   # 远端接口
    platform: str           # 平台/型号
    capability: str         # 能力 (Router, Bridge, etc.)
    port_description: str    # 端口描述
    system_description: str # 系统描述


class LLDPNeighborParser:
    """LLDP邻居信息解析器"""
    
    @staticmethod
    def parse_lldp_neighbor(output: str, vendor: Vendor) -> List[NeighborInfo]:
        """解析LLDP邻居信息"""
        neighbors = []
        
        if vendor == Vendor.HUAWEI or vendor == Vendor.H3C:
            neighbors = LLDPNeighborParser._parse_huawei_lldp(output)
        elif vendor == Vendor.CISCO:
            # 思科优先尝试CDP，其次LLDP
            neighbors = LLDPNeighborParser._parse_cisco_cdp(output)
            if not neighbors:
                neighbors = LLDPNeighborParser._parse_cisco_lldp(output)
        elif vendor == Vendor.JUNIPER:
            neighbors = LLDPNeighborParser._parse_juniper_lldp(output)
        
        return neighbors
    
    @staticmethod
    def _parse_huawei_lldp(output: str) -> List[NeighborInfo]:
        """解析华为LLDP输出"""
        neighbors = []
        
        # 格式:
        # Local Interface    Neighbor Device ID     Neighbor Port ID  Description
        # GE0/0/1            CORE-SW-01              GE0/0/1            Description
        
        lines = output.strip().split('\n')
        for line in lines:
            # 跳过标题行和空行
            if 'Local Interface' in line or not line.strip():
                continue
            
            # 分割处理
            parts = line.split()
            if len(parts) >= 3:
                neighbor = NeighborInfo(
                    local_interface=parts[0],
                    device_id=parts[1] if len(parts) > 1 else "",
                    remote_interface=parts[2] if len(parts) > 2 else "",
                    ip="",
                    platform="",
                    capability="",
                    port_description="",
                    system_description=""
                )
                
                # 尝试获取更多信息
                if len(parts) > 3:
                    neighbor.port_description = ' '.join(parts[3:])
                
                # 如果设备ID像MAC地址，尝试获取IP
                if re.match(r'^[0-9a-fA-F]{4}\.', neighbor.device_id) or \
                   re.match(r'^[0-9a-fA-F]{2}:', neighbor.device_id):
                    # 这是MAC地址
                    pass
                
                neighbors.append(neighbor)
        
        return neighbors
    
    @staticmethod
    def _parse_cisco_lldp(output: str) -> List[NeighborInfo]:
        """解析思科LLDP输出"""
        neighbors = []
        
        # 格式:
        # Device ID           Local Intrfce     Holdtime  Capability  Port ID   Platform
        # CORE-SW-01         Gig 0/0/1          120       R           Gig 0/0/1  S5720
        
        lines = output.strip().split('\n')
        for line in lines:
            if 'Device ID' in line or not line.strip():
                continue
            
            # 使用正则匹配
            # Device ID可能包含空格，需要特殊处理
            pattern = r'^(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(.+)$'
            match = re.match(pattern, line)
            
            if match:
                neighbor = NeighborInfo(
                    device_id=match.group(1),
                    local_interface=match.group(2),
                    capability=match.group(4),
                    remote_interface=match.group(5),
                    platform=match.group(6).strip(),
                    ip="",
                    port_description="",
                    system_description=""
                )
                neighbors.append(neighbor)
        
        return neighbors
    
    @staticmethod
    def _parse_cisco_cdp(output: str) -> List[NeighborInfo]:
        """解析思科CDP输出"""
        neighbors = []
        
        # 格式:
        # Device ID          Local Intrfce   Holdtime  Capability  Platform     Port ID
        # CORE-SW-01        Gig 0/0/1       160       R S I      Cisco S5720  Gig 0/0/1
        
        lines = output.strip().split('\n')
        for line in lines:
            if 'Device ID' in line or not line.strip():
                continue
            
            pattern = r'^(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(.+)$'
            match = re.match(pattern, line)
            
            if match:
                neighbor = NeighborInfo(
                    device_id=match.group(1),
                    local_interface=match.group(2),
                    capability=match.group(4),
                    platform=match.group(5).strip(),
                    remote_interface=match.group(6).strip(),
                    ip="",
                    port_description="",
                    system_description=""
                )
                neighbors.append(neighbor)
        
        return neighbors
    
    @staticmethod
    def _parse_juniper_lldp(output: str) -> List[NeighborInfo]:
        """解析Juniper LLDP输出"""
        neighbors = []
        
        # Juniper格式是表格形式
        lines = output.strip().split('\n')
        
        for line in lines:
            # 跳过标题
            if 'Local Interface' in line or 'Hostname' in line:
                continue
            
            parts = line.split()
            if len(parts) >= 5:
                neighbor = NeighborInfo(
                    local_interface=parts[0],
                    device_id=parts[1] if len(parts) > 1 else "",
                    remote_interface=parts[2] if len(parts) > 2 else "",
                    capability=parts[3] if len(parts) > 3 else "",
                    platform=parts[4] if len(parts) > 4 else "",
                    ip="",
                    port_description="",
                    system_description=""
                )
                neighbors.append(neighbor)
        
        return neighbors


class LinkTypeDetector:
    """链路类型检测器"""
    
    # 聚合端口标识
    AGGREGATE_PATTERNS = [
        r'eth-trunk\d+',      # 华为
        r'AE\d+',             # Juniper
        r'Port-channel\d+',   # 思科
        r'Po\d+',             # 简写
        r'LACP',              # LACP关键字
    ]
    
    # VRRP标识
    VRRP_PATTERNS = [
        r'vrrp',
        r'Virtual-IP',
        r'VRRP',
    ]
    
    # 堆叠标识
    STACK_PATTERNS = [
        r'stack',
        r'Stack',
        r'STACK',
    ]
    
    @staticmethod
    def detect_link_type(interface_name: str, description: str = "", 
                         neighbor_info: Optional[NeighborInfo] = None) -> PortType:
        """检测链路类型"""
        text = f"{interface_name} {description}".lower()
        
        # 检查聚合
        for pattern in LinkTypeDetector.AGGREGATE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return PortType.AGGREGATE
        
        # 检查VRRP
        for pattern in LinkTypeDetector.VRRP_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return PortType.VRRP
        
        # 检查堆叠
        for pattern in LinkTypeDetector.STACK_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return PortType.STACK
        
        # 检查Trunk
        if 'trunk' in text:
            return PortType.TRUNK
        
        # 检查Loopback
        if 'loopback' in text.lower() or 'lo' in interface_name.lower():
            return PortType.LOOPBACK
        
        # 检查VLAN接口
        if 'vlan' in interface_name.lower() or 'vlanif' in interface_name.lower():
            return PortType.VLAN_INTERFACE
        
        # 检查Tunnel
        if 'tunnel' in interface_name.lower():
            return PortType.TUNNEL
        
        return PortType.NORMAL
    
    @staticmethod
    def create_link_from_neighbor(local_device_id: str, neighbor: NeighborInfo, 
                                  port_type: PortType = PortType.NORMAL) -> Link:
        """根据邻居信息创建链路"""
        return Link(
            source_device=local_device_id,
            source_interface=neighbor.local_interface,
            target_device=neighbor.device_id,
            target_interface=neighbor.remote_interface,
            link_type="physical" if port_type == PortType.NORMAL else port_type.value,
            port_type=port_type
        )