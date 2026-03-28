#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置模板库
预定义常用配置模板
"""
import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ConfigTemplate:
    """配置模板"""
    id: str
    name: str
    description: str
    vendor: str  # huawei/cisco/h3c/all
    category: str  # vlan/interface/routing/security
    parameters: List[Dict[str, str]]  # 参数定义
    template_content: str  # 模板内容（带占位符）
    example_usage: str  # 使用示例


class ConfigTemplateLibrary:
    """配置模板库"""
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        初始化
        
        Args:
            template_dir: 模板目录
        """
        self.template_dir = template_dir or os.path.join(
            os.path.expanduser("~/.netops-ai/templates")
        )
        
        # 内置模板
        self._builtin_templates = self._load_builtin_templates()
        
        # 确保模板目录存在
        Path(self.template_dir).mkdir(parents=True, exist_ok=True)
    
    def _load_builtin_templates(self) -> Dict[str, ConfigTemplate]:
        """加载内置模板"""
        templates = {}
        
        # 模板 1: VLAN 批量配置（华为）
        templates["vlan_batch_access"] = ConfigTemplate(
            id="vlan_batch_access",
            name="批量配置 Access VLAN",
            description="给多个接口批量配置 Access VLAN",
            vendor="huawei",
            category="vlan",
            parameters=[
                {"name": "vlan_id", "description": "VLAN ID", "required": True},
                {"name": "interfaces", "description": "接口列表（如 GE0/0/1-4）", "required": True},
            ],
            template_content="""interface range {interfaces}
port link-type access
port default vlan {vlan_id}
quit
""",
            example_usage="给 SW-Core 的 1-4 口配 VLAN 10",
        )
        
        # 模板 2: VLAN 批量配置（思科）
        templates["vlan_batch_access_cisco"] = ConfigTemplate(
            id="vlan_batch_access_cisco",
            name="批量配置 Access VLAN (Cisco)",
            description="给多个接口批量配置 Access VLAN",
            vendor="cisco",
            category="vlan",
            parameters=[
                {"name": "vlan_id", "description": "VLAN ID", "required": True},
                {"name": "interfaces", "description": "接口列表（如 GigabitEthernet0/1-4）", "required": True},
            ],
            template_content="""interface range {interfaces}
switchport mode access
switchport access vlan {vlan_id}
exit
""",
            example_usage="给 SW-Core 的 1-4 口配 VLAN 10",
        )
        
        # 模板 3: Trunk 配置（华为）
        templates["trunk_config"] = ConfigTemplate(
            id="trunk_config",
            name="配置 Trunk 接口",
            description="配置接口为 Trunk 并允许指定 VLAN",
            vendor="huawei",
            category="vlan",
            parameters=[
                {"name": "interface", "description": "接口名", "required": True},
                {"name": "allowed_vlans", "description": "允许的 VLAN 列表", "required": True},
            ],
            template_content="""interface {interface}
port link-type trunk
port trunk allow-pass vlan {allowed_vlans}
quit
""",
            example_usage="把 GE0/0/24 配成 trunk，允许 VLAN 10 20 30",
        )
        
        # 模板 4: SVI 接口配置
        templates["svi_config"] = ConfigTemplate(
            id="svi_config",
            name="配置 SVI 接口",
            description="创建 VLAN 接口并配置 IP",
            vendor="huawei",
            category="vlan",
            parameters=[
                {"name": "vlan_id", "description": "VLAN ID", "required": True},
                {"name": "ip_address", "description": "IP 地址", "required": True},
                {"name": "subnet_mask", "description": "子网掩码", "required": True},
            ],
            template_content="""interface Vlanif{vlan_id}
ip address {ip_address} {subnet_mask}
quit
""",
            example_usage="给 VLAN 10 配网关 192.168.10.1/24",
        )
        
        # 模板 5: 静态路由配置
        templates["static_route"] = ConfigTemplate(
            id="static_route",
            name="配置静态路由",
            description="添加静态路由",
            vendor="huawei",
            category="routing",
            parameters=[
                {"name": "dest_network", "description": "目的网段", "required": True},
                {"name": "subnet_mask", "description": "子网掩码", "required": True},
                {"name": "next_hop", "description": "下一跳", "required": True},
            ],
            template_content="""ip route-static {dest_network} {subnet_mask} {next_hop}
""",
            example_usage="添加静态路由 10.0.0.0/8 下一跳 192.168.1.1",
        )
        
        # 模板 6: 默认路由
        templates["default_route"] = ConfigTemplate(
            id="default_route",
            name="配置默认路由",
            description="添加默认路由",
            vendor="huawei",
            category="routing",
            parameters=[
                {"name": "next_hop", "description": "下一跳/出口", "required": True},
            ],
            template_content="""ip route-static 0.0.0.0 0.0.0.0 {next_hop}
""",
            example_usage="添加默认路由指向 192.168.1.1",
        )
        
        # 模板 7: OSPF 基础配置
        templates["ospf_basic"] = ConfigTemplate(
            id="ospf_basic",
            name="OSPF 基础配置",
            description="启用 OSPF 并配置区域",
            vendor="huawei",
            category="routing",
            parameters=[
                {"name": "process_id", "description": "OSPF 进程 ID", "required": True},
                {"name": "area_id", "description": "区域 ID", "required": True},
                {"name": "network", "description": "宣告网段", "required": True},
                {"name": "wildcard_mask", "description": "反掩码", "required": True},
            ],
            template_content="""ospf {process_id}
area {area_id}
network {network} {wildcard_mask}
quit
quit
""",
            example_usage="配置 OSPF 进程 1 区域 0 宣告 192.168.10.0/24",
        )
        
        # 模板 8: 端口安全配置
        templates["port_security"] = ConfigTemplate(
            id="port_security",
            name="端口安全配置",
            description="配置端口安全（最大 MAC 数）",
            vendor="huawei",
            category="security",
            parameters=[
                {"name": "interface", "description": "接口名", "required": True},
                {"name": "max_mac", "description": "最大 MAC 地址数", "required": True},
            ],
            template_content="""interface {interface}
port-security enable
port-security max-mac-count {max_mac}
quit
""",
            example_usage="给 GE0/0/1 配置端口安全，最大 2 个 MAC",
        )
        
        # 模板 9: 接口描述
        templates["interface_description"] = ConfigTemplate(
            id="interface_description",
            name="配置接口描述",
            description="给接口添加描述",
            vendor="all",
            category="interface",
            parameters=[
                {"name": "interface", "description": "接口名", "required": True},
                {"name": "description", "description": "描述文本", "required": True},
            ],
            template_content="""interface {interface}
description {description}
quit
""",
            example_usage="给 GE0/0/1 加描述 'Link to SW-Access-1'",
        )
        
        # 模板 10: 新交换机初始化
        templates["switch_init"] = ConfigTemplate(
            id="switch_init",
            name="新交换机初始化",
            description="新交换机基础配置模板",
            vendor="huawei",
            category="init",
            parameters=[
                {"name": "hostname", "description": "设备名", "required": True},
                {"name": "mgmt_vlan", "description": "管理 VLAN", "required": True},
                {"name": "mgmt_ip", "description": "管理 IP", "required": True},
                {"name": "subnet_mask", "description": "子网掩码", "required": True},
                {"name": "gateway", "description": "默认网关", "required": True},
            ],
            template_content="""sysname {hostname}
#
vlan batch {mgmt_vlan}
#
interface Vlanif{mgmt_vlan}
ip address {mgmt_ip} {subnet_mask}
quit
#
ip route-static 0.0.0.0 0.0.0.0 {gateway}
#
aaa
local-user admin password irreversible-cipher Admin@123
local-user admin privilege level 15
local-user admin service-type ssh
quit
#
stelnet server enable
#
""",
            example_usage="初始化新交换机 SW-Access-1，管理 VLAN 100，IP 192.168.100.1/24，网关 192.168.100.254",
        )
        
        return templates
    
    def get_template(self, template_id: str) -> Optional[ConfigTemplate]:
        """获取模板"""
        # 先查内置模板
        if template_id in self._builtin_templates:
            return self._builtin_templates[template_id]
        
        # 再查用户模板
        user_template_path = os.path.join(self.template_dir, f"{template_id}.json")
        if os.path.exists(user_template_path):
            try:
                with open(user_template_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return ConfigTemplate(**data)
            except Exception:
                pass
        
        return None
    
    def list_templates(self, category: Optional[str] = None) -> List[ConfigTemplate]:
        """列出所有模板"""
        templates = list(self._builtin_templates.values())
        
        # 按类别过滤
        if category:
            templates = [t for t in templates if t.category == category]
        
        return templates
    
    def render_template(
        self,
        template_id: str,
        parameters: Dict[str, str],
    ) -> Optional[str]:
        """
        渲染模板
        
        Args:
            template_id: 模板 ID
            parameters: 参数值
        
        Returns:
            渲染后的配置，如果模板不存在则返回 None
        """
        template = self.get_template(template_id)
        if not template:
            return None
        
        # 替换占位符
        config = template.template_content
        for key, value in parameters.items():
            config = config.replace(f"{{{key}}}", str(value))
        
        return config
    
    def save_template(self, template: ConfigTemplate) -> bool:
        """保存用户自定义模板"""
        template_path = os.path.join(self.template_dir, f"{template.id}.json")
        
        try:
            with open(template_path, "w", encoding="utf-8") as f:
                json.dump({
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "vendor": template.vendor,
                    "category": template.category,
                    "parameters": template.parameters,
                    "template_content": template.template_content,
                    "example_usage": template.example_usage,
                }, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


# 全局模板库实例
_template_lib: Optional[ConfigTemplateLibrary] = None


def get_template_library() -> ConfigTemplateLibrary:
    """获取全局模板库"""
    global _template_lib
    if _template_lib is None:
        _template_lib = ConfigTemplateLibrary()
    return _template_lib


def render_config(template_id: str, params: Dict[str, str]) -> Optional[str]:
    """渲染配置（便捷函数）"""
    return get_template_library().render_template(template_id, params)


def list_templates(category: Optional[str] = None) -> List[ConfigTemplate]:
    """列出模板（便捷函数）"""
    return get_template_library().list_templates(category)
