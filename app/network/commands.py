"""
厂商命令映射表
不同厂商的命令差异统一封装
"""
from typing import Dict, List
from enum import Enum
from app.core.device import Vendor, PortType


class CommandSet:
    """命令集定义"""
    
    # 获取设备基本信息
    GET_VERSION = "get_version"
    GET_SYSTEM_INFO = "get_system_info"
    
    # 接口信息
    GET_INTERFACE_BRIEF = "get_interface_brief"
    GET_INTERFACE_STATUS = "get_interface_status"
    GET_IP_INTERFACE_BRIEF = "get_ip_interface_brief"
    
    # LLDP/CDP发现
    GET_LLDP_NEIGHBOR = "get_lldp_neighbor"
    GET_LLDP_NEIGHBOR_DETAIL = "get_lldp_neighbor_detail"
    GET_CDP_NEIGHBOR = "get_cdp_neighbor"
    GET_CDP_NEIGHBOR_DETAIL = "get_cdp_neighbor_detail"
    
    # 聚合端口
    GET_AGGREGATE = "get_aggregate"
    GET_AGGREGATE_MEMBER = "get_aggregate_member"
    
    # VRRP/HSRP
    GET_VRRP = "get_vrrp"
    GET_HSRP = "get_hsrp"
    
    # 堆叠信息
    GET_STACK_INFO = "get_stack_info"
    
    # VLAN信息
    GET_VLAN = "get_vlan"
    GET_PORT_VLAN = "get_port_vlan"
    
    # 路由协议邻居
    GET_OSPF_NEIGHBOR = "get_ospf_neighbor"
    GET_BGP_NEIGHBOR = "get_bgp_neighbor"
    
    # 配置文件
    GET_RUNNING_CONFIG = "get_running_config"
    GET_STARTUP_CONFIG = "get_startup_config"
    
    # Ping
    PING = "ping"
    
    # Traceroute
    TRACEROUTE = "traceroute"


# 厂商命令映射
VENDOR_COMMANDS: Dict[Vendor, Dict[str, str]] = {
    Vendor.HUAWEI: {
        # 基本信息
        CommandSet.GET_VERSION: "display version",
        CommandSet.GET_SYSTEM_INFO: "display device manuinfo",
        
        # 接口信息
        CommandSet.GET_INTERFACE_BRIEF: "display interface brief",
        CommandSet.GET_INTERFACE_STATUS: "display interface status",
        CommandSet.GET_IP_INTERFACE_BRIEF: "display ip interface brief",
        
        # LLDP
        CommandSet.GET_LLDP_NEIGHBOR: "display lldp neighbor",
        CommandSet.GET_LLDP_NEIGHBOR_DETAIL: "display lldp neighbor detail",
        
        # 聚合
        CommandSet.GET_AGGREGATE: "display eth-trunk",
        CommandSet.GET_AGGREGATE_MEMBER: "display eth-trunk {interface}",
        
        # VRRP
        CommandSet.GET_VRRP: "display vrrp",
        
        # 堆叠
        CommandSet.GET_STACK_INFO: "display stack",
        
        # VLAN
        CommandSet.GET_VLAN: "display vlan",
        CommandSet.GET_PORT_VLAN: "display port vlan {interface}",
        
        # OSPF
        CommandSet.GET_OSPF_NEIGHBOR: "display ospf peer",
        
        # BGP
        CommandSet.GET_BGP_NEIGHBOR: "display bgp peer",
        
        # 配置
        CommandSet.GET_RUNNING_CONFIG: "display current-configuration",
        
        # 测试
        CommandSet.PING: "ping {target}",
        CommandSet.TRACEROUTE: "tracert {target}",
    },
    
    Vendor.CISCO: {
        # 基本信息
        CommandSet.GET_VERSION: "show version",
        CommandSet.GET_SYSTEM_INFO: "show hardware",
        
        # 接口信息
        CommandSet.GET_INTERFACE_BRIEF: "show interface brief",
        CommandSet.GET_INTERFACE_STATUS: "show interface status",
        CommandSet.GET_IP_INTERFACE_BRIEF: "show ip interface brief",
        
        # CDP (思科专用)
        CommandSet.GET_CDP_NEIGHBOR: "show cdp neighbors",
        CommandSet.GET_CDP_NEIGHBOR_DETAIL: "show cdp neighbors detail",
        
        # 同时也支持LLDP
        CommandSet.GET_LLDP_NEIGHBOR: "show lldp neighbors",
        CommandSet.GET_LLDP_NEIGHBOR_DETAIL: "show lldp neighbors detail",
        
        # 聚合
        CommandSet.GET_AGGREGATE: "show etherchannel summary",
        CommandSet.GET_AGGREGATE_MEMBER: "show etherchannel {interface} port",
        
        # HSRP (思科专用)
        CommandSet.GET_HSRP: "show standby brief",
        
        # VRRP (思科也支持)
        CommandSet.GET_VRRP: "show vrrp brief",
        
        # 堆叠
        CommandSet.GET_STACK_INFO: "show switch",
        
        # VLAN
        CommandSet.GET_VLAN: "show vlan",
        CommandSet.GET_PORT_VLAN: "show interface {interface} switchport",
        
        # OSPF
        CommandSet.GET_OSPF_NEIGHBOR: "show ip ospf neighbor",
        
        # BGP
        CommandSet.GET_BGP_NEIGHBOR: "show bgp summary",
        
        # 配置
        CommandSet.GET_RUNNING_CONFIG: "show running-config",
        
        # 测试
        CommandSet.PING: "ping {target}",
        CommandSet.TRACEROUTE: "traceroute {target}",
    },
    
    Vendor.H3C: {
        # 基本信息
        CommandSet.GET_VERSION: "display version",
        CommandSet.GET_SYSTEM_INFO: "display device-info",
        
        # 接口信息
        CommandSet.GET_INTERFACE_BRIEF: "display interface brief",
        CommandSet.GET_INTERFACE_STATUS: "display interface status",
        CommandSet.GET_IP_INTERFACE_BRIEF: "display ip interface brief",
        
        # LLDP
        CommandSet.GET_LLDP_NEIGHBOR: "display lldp neighbor",
        CommandSet.GET_LLDP_NEIGHBOR_DETAIL: "display lldp neighbor detail",
        
        # 聚合
        CommandSet.GET_AGGREGATE: "display link-aggregation summary",
        CommandSet.GET_AGGREGATE_MEMBER: "display link-aggregation member-port {interface}",
        
        # VRRP
        CommandSet.GET_VRRP: "display vrrp",
        
        # 堆叠
        CommandSet.GET_STACK_INFO: "display stack",
        
        # VLAN
        CommandSet.GET_VLAN: "display vlan",
        CommandSet.GET_PORT_VLAN: "display port hybrid {interface}",
        
        # OSPF
        CommandSet.GET_OSPF_NEIGHBOR: "display ospf peer",
        
        # BGP
        CommandSet.GET_BGP_NEIGHBOR: "display bgp peer",
        
        # 配置
        CommandSet.GET_RUNNING_CONFIG: "display current-configuration",
        
        # 测试
        CommandSet.PING: "ping {target}",
        CommandSet.TRACEROUTE: "tracert {target}",
    },
    
    Vendor.JUNIPER: {
        # 基本信息
        CommandSet.GET_VERSION: "show version",
        CommandSet.GET_SYSTEM_INFO: "show chassis hardware",
        
        # 接口信息
        CommandSet.GET_INTERFACE_BRIEF: "show interface terse",
        CommandSet.GET_INTERFACE_STATUS: "show interface status",
        CommandSet.GET_IP_INTERFACE_BRIEF: "show ip interface terse",
        
        # LLDP
        CommandSet.GET_LLDP_NEIGHBOR: "show lldp neighbors",
        CommandSet.GET_LLDP_NEIGHBOR_DETAIL: "show lldp neighbors detail",
        
        # 聚合
        CommandSet.GET_AGGREGATE: "show chassis aggregated-devices",
        CommandSet.GET_AGGREGATE_MEMBER: "show interface ae* detail",
        
        # VRRP
        CommandSet.GET_VRRP: "show vrrp",
        
        # 路由协议
        CommandSet.GET_OSPF_NEIGHBOR: "show ospf neighbor",
        CommandSet.GET_BGP_NEIGHBOR: "show bgp summary",
        
        # 配置
        CommandSet.GET_RUNNING_CONFIG: "show configuration",
        
        # 测试
        CommandSet.PING: "ping {target}",
        CommandSet.TRACEROUTE: "traceroute {target}",
    },
    
    # 默认使用华为命令集
    Vendor.UNKNOWN: {},
}


class CommandBuilder:
    """命令构建器"""
    
    @staticmethod
    def get_command(vendor: Vendor, command_type: str, **params) -> str:
        """获取指定类型的命令"""
        commands = VENDOR_COMMANDS.get(vendor, VENDOR_COMMANDS[Vendor.HUAWEI])
        
        if command_type not in commands:
            # 尝试使用华为的命令集
            commands = VENDOR_COMMANDS[Vendor.HUAWEI]
            if command_type not in commands:
                return ""
        
        cmd = commands.get(command_type, "")
        
        # 替换参数
        for key, value in params.items():
            cmd = cmd.replace(f"{{{key}}}", str(value))
        
        return cmd
    
    @staticmethod
    def ping(vendor: Vendor, target: str) -> str:
        """构建Ping命令"""
        return CommandBuilder.get_command(vendor, CommandSet.PING, target=target)
    
    @staticmethod
    def traceroute(vendor: Vendor, target: str) -> str:
        """构建Tracert命令"""
        return CommandBuilder.get_command(vendor, CommandSet.TRACEROUTE, target=target)
    
    @staticmethod
    def get_version(vendor: Vendor) -> str:
        """构建获取版本命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_VERSION)
    
    @staticmethod
    def get_lldp_neighbor(vendor: Vendor) -> str:
        """构建获取LLDP邻居命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_LLDP_NEIGHBOR)
    
    @staticmethod
    def get_lldp_neighbor_detail(vendor: Vendor) -> str:
        """构建获取LLDP邻居详情命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_LLDP_NEIGHBOR_DETAIL)
    
    @staticmethod
    def get_cdp_neighbor(vendor: Vendor) -> str:
        """构建获取CDP邻居命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_CDP_NEIGHBOR)
    
    @staticmethod
    def get_ip_interface_brief(vendor: Vendor) -> str:
        """构建获取IP接口简要信息命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_IP_INTERFACE_BRIEF)
    
    @staticmethod
    def get_interface_brief(vendor: Vendor) -> str:
        """构建获取接口简要信息命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_INTERFACE_BRIEF)
    
    @staticmethod
    def get_aggregate(vendor: Vendor) -> str:
        """构建获取聚合端口命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_AGGREGATE)
    
    @staticmethod
    def get_vrrp(vendor: Vendor) -> str:
        """构建获取VRRP命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_VRRP)
    
    @staticmethod
    def get_running_config(vendor: Vendor) -> str:
        """构建获取运行配置命令"""
        return CommandBuilder.get_command(vendor, CommandSet.GET_RUNNING_CONFIG)