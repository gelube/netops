"""
Hacknet风格样式定义
"""
from typing import Dict


class HacknetColors:
    """Hacknet风格颜色"""
    # 背景
    BACKGROUND = "#000000"      # 纯黑
    BACKGROUND_LIGHT = "#0a0a0a"  # 深灰
    PANEL = "#111111"            # 面板背景
    
    # 主色调
    PRIMARY = "#00FF00"          # 亮绿 - 主文字
    PRIMARY_DARK = "#008800"      # 深绿 - 次要文字
    SECONDARY = "#00FFFF"        # 青色 - 强调
    
    # 功能色
    ACCENT = "#FF00FF"          # 霓虹粉 - 高亮
    WARNING = "#FFAA00"         # 橙色 - 警告
    ERROR = "#FF0000"           # 红色 - 错误
    SUCCESS = "#00FF00"          # 绿色 - 成功
    
    # 特殊元素
    BORDER = "#00FF00"           # 边框
    BORDER_DIM = "#004400"       # 暗边框
    SELECTED = "#00FF00"         # 选中项
    FOCUS = "#00FFFF"            # 焦点
    
    # 节点类型颜色
    NODE_ROUTER = "#00FF00"     # 路由器
    NODE_SWITCH = "#00FFFF"      # 交换机
    NODE_FIREWALL = "#FF6600"    # 防火墙
    NODE_SERVER = "#FF00FF"      # 服务器
    NODE_UNKNOWN = "#888888"     # 未知
    
    # 链路颜色
    LINK_PHYSICAL = "#00FF00"   # 物理链路
    LINK_AGGREGATE = "#00FFFF"  # 聚合链路
    LINK_VRRP = "#FF00FF"       # VRRP
    LINK_STACK = "#FFAA00"      # 堆叠
    LINK_OSPF = "#00FF00"       # OSPF邻居 (点)
    LINK_VPN = "#884488"        # VPN


class HacknetStyles:
    """Hacknet样式生成器"""
    
    @staticmethod
    def get_base_style() -> Dict:
        """基础样式"""
        return {
            "background": HacknetColors.BACKGROUND,
            "color": HacknetColors.PRIMARY,
        }
    
    @staticmethod
    def get_panel_style() -> Dict:
        """面板样式"""
        return {
            "background": HacknetColors.PANEL,
            "color": HacknetColors.PRIMARY,
            "border": (HacknetColors.BORDER, "green"),
        }
    
    @staticmethod
    def get_header_style() -> Dict:
        """标题样式"""
        return {
            "background": HacknetColors.BACKGROUND,
            "color": HacknetColors.PRIMARY,
            "text-style": "bold",
        }
    
    @staticmethod
    def get_button_style(hover: bool = False) -> Dict:
        """按钮样式"""
        if hover:
            return {
                "background": HacknetColors.PRIMARY,
                "color": HacknetColors.BACKGROUND,
                "text-style": "bold",
            }
        return {
            "background": HacknetColors.BACKGROUND,
            "color": HacknetColors.PRIMARY,
            "border": (HacknetColors.PRIMARY, "green"),
        }
    
    @staticmethod
    def get_input_style() -> Dict:
        """输入框样式"""
        return {
            "background": HacknetColors.BACKGROUND_LIGHT,
            "color": HacknetColors.PRIMARY,
            "border": (HacknetColors.PRIMARY_DARK, "green"),
        }
    
    @staticmethod
    def get_focus_style() -> Dict:
        """焦点样式"""
        return {
            "background": HacknetColors.BACKGROUND,
            "color": HacknetColors.FOCUS,
            "text-style": "bold",
            "border": (HacknetColors.FOCUS, "green"),
        }
    
    @staticmethod
    def get_node_color(device_type: str) -> str:
        """获取设备节点颜色"""
        colors = {
            "router": HacknetColors.NODE_ROUTER,
            "switch_l3": HacknetColors.NODE_SWITCH,
            "switch_l2": HacknetColors.NODE_SWITCH,
            "firewall": HacknetColors.NODE_FIREWALL,
            "server": HacknetColors.NODE_SERVER,
            "unknown": HacknetColors.NODE_UNKNOWN,
        }
        return colors.get(device_type.lower(), HacknetColors.NODE_UNKNOWN)
    
    @staticmethod
    def get_link_style(link_type: str) -> str:
        """获取链路颜色"""
        colors = {
            "physical": HacknetColors.LINK_PHYSICAL,
            "aggregate": HacknetColors.LINK_AGGREGATE,
            "vrrp": HacknetColors.LINK_VRRP,
            "hsrp": HacknetColors.LINK_VRRP,
            "stack": HacknetColors.LINK_STACK,
            "ospf": HacknetColors.LINK_OSPF,
            "bgp": HacknetColors.LINK_OSPF,
            "vpn": HacknetColors.LINK_VPN,
            "tunnel": HacknetColors.LINK_VPN,
            "loopback": HacknetColors.PRIMARY_DARK,
            "vlan": HacknetColors.SECONDARY,
        }
        return colors.get(link_type.lower(), HacknetColors.LINK_PHYSICAL)


# 设备图标 (ASCII Art)
DEVICE_ICONS = {
    "router": """  ┌───┐
  │ ○ │
  ══╪═
    │
  └───┘""",
    
    "switch_l3": """  ┌───┐
  │ ■ │
  ══╪═
  │ ■ │
  └───┘""",
    
    "switch_l2": """  ┌───┐
  │ ■ │
  ══╪═
  │ ■ │
  └───┘""",
    
    "firewall": """  ┌───┐
  │▓▓▓│
  ══╪═
  │▓▓▓│
  └───┘""",
    
    "server": """  ┌───┐
  │╔═╗│
  │║▦║│
  │╚═╝│
  └───┘""",
    
    "unknown": """  ┌───┐
  │ ? │
  ══╪═
    │
  └───┘""",
}


# 连接线样式
LINK_SYMBOLS = {
    "physical": "─",
    "aggregate": "══",
    "vrrp": "◈",
    "hsrp": "◈",
    "stack": "≡",
    "trunk": "───◆───",
    "ospf": "●",
    "bgp": "●",
    "vpn": "- - -",
    "loopback": "□",
    "vlan": "◇",
    "tunnel": "◬",
}


# 链路符号获取
def get_link_symbol(link_type: str) -> str:
    return LINK_SYMBOLS.get(link_type.lower(), "─")