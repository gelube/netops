#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令模板库 - 模板优先，LLM兜底

常见配置操作用模板生成（100%可靠），复杂场景才走LLM。
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.logger import get_logger

log = get_logger(__name__)


@dataclass
class CommandTemplate:
    """命令模板"""
    name: str                # 模板名称
    intent_type: str         # 对应意图类型
    vendor: str              # 厂商 (huawei/cisco/h3c/juniper 等, "common" 表示通用)
    description: str         # 模板描述
    param_keys: List[str]    # 需要的参数键名
    generate: callable       # 生成函数 → List[str]


def _mask_to_cidr(mask: str) -> str:
    """子网掩码转CIDR，已是CIDR格式则直接返回

    '255.255.255.0' → '24'
    '24' → '24'
    """
    if isinstance(mask, int):
        return str(mask)
    mask = str(mask).strip()
    # 已经是CIDR格式
    if mask.isdigit():
        return mask
    # 点分十进制 → CIDR
    try:
        parts = mask.split('.')
        if len(parts) == 4:
            binary = ''.join(format(int(p), '08b') for p in parts)
            return str(binary.count('1'))
    except Exception as e:
        log.debug("mask转换失败", mask=mask, error=str(e))
        pass
    return '24'  # 默认 /24


def _expand_interfaces(iface_str: str, vendor: str, context: Dict[str, Any] = None) -> Tuple[str, List[str]]:
    """
    展开接口范围字符串

    "1-4" → 华为返回 ("GE0/0/1 to GE0/0/4", ["GE0/0/1","GE0/0/2","GE0/0/3","GE0/0/4"])
    "GE0/0/1-4" → 同上

    context参数可传入 {"interface_prefix": "XGE1/0/", "slot": "1"} 等设备特定信息
    """
    # 已有完整接口名
    if any(iface_str.startswith(p) for p in ('GE', 'Gigabit', 'XGE', '10GE', 'Eth', 'Loop', 'Vlan', 'Port', 'Bridge')):
        return iface_str, [iface_str]

    # 纯数字范围
    parts = iface_str.split('-')
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        start, end = int(parts[0]), int(parts[1])
        if start > end:
            start, end = end, start

        if vendor in ('huawei', 'huawei_vrpv8'):
            iface_list = [f"GE0/0/{i}" for i in range(start, end + 1)]
            if len(iface_list) > 1:
                return f"GE0/0/{start} to GE0/0/{end}", iface_list
            return iface_list[0], iface_list
        elif vendor in ('hp_comware', 'h3c'):
            iface_list = [f"GigabitEthernet1/0/{i}" for i in range(start, end + 1)]
            if len(iface_list) > 1:
                return f"GigabitEthernet1/0/{start} to GigabitEthernet1/0/{end}", iface_list
            return iface_list[0], iface_list
        elif vendor in ('cisco_ios', 'cisco_nxos', 'ruijie_os', 'arista_eos'):
            iface_list = [f"GigabitEthernet0/{i}" for i in range(start, end + 1)]
            if len(iface_list) > 1:
                return f"GigabitEthernet0/{start} - {end}", iface_list
            return iface_list[0], iface_list
        elif vendor == 'juniper_junos':
            # Juniper用set命令，不需要range语法
            return iface_str, [f"ge-0/0/{i}" for i in range(start, end + 1)]

    # 单个接口号
    if iface_str.isdigit():
        port = int(iface_str)
        if vendor in ('huawei', 'huawei_vrpv8'):
            name = f"GE0/0/{port}"
        elif vendor in ('hp_comware', 'h3c'):
            name = f"GigabitEthernet1/0/{port}"
        elif vendor in ('cisco_ios', 'cisco_nxos', 'ruijie_os', 'arista_eos'):
            name = f"GigabitEthernet0/{port}"
        elif vendor == 'juniper_junos':
            name = f"ge-0/0/{port}"
        else:
            name = f"GigabitEthernet0/{port}"
        return name, [name]

    return iface_str, [iface_str]


# ============================================================
# 华为 (huawei) 模板
# ============================================================

HUAWEI_TEMPLATES = [
    CommandTemplate(
        name="huawei_config_vlan_access",
        intent_type="config_vlan",
        vendor="huawei",
        description="华为：创建VLAN并添加接口(access模式)",
        param_keys=["interfaces", "vlan_id", "mode"],
        generate=lambda p: _huawei_vlan_access(p),
    ),
    CommandTemplate(
        name="huawei_config_vlan_trunk",
        intent_type="config_vlan",
        vendor="huawei",
        description="华为：配置接口为trunk并允许VLAN通过",
        param_keys=["interfaces", "vlan_id", "mode"],
        generate=lambda p: _huawei_vlan_trunk(p),
    ),
    CommandTemplate(
        name="huawei_config_interface_ip",
        intent_type="config_interface",
        vendor="huawei",
        description="华为：配置接口IP地址",
        param_keys=["interface", "ip", "mask"],
        generate=lambda p: [
            "system-view",
            f"interface {p.get('interface', 'Vlanif1')}",
            f"ip address {p.get('ip', '0.0.0.0')} {p.get('mask', '255.255.255.0')}",
            "quit",
        ],
    ),
    CommandTemplate(
        name="huawei_config_static_route",
        intent_type="config_routing",
        vendor="huawei",
        description="华为：配置静态路由",
        param_keys=["dest", "mask", "next_hop"],
        generate=lambda p: [
            "system-view",
            f"ip route-static {p.get('dest', '0.0.0.0')} {p.get('mask', '0.0.0.0')} {p.get('next_hop', '')}",
            "quit",
        ],
    ),
    CommandTemplate(
        name="huawei_config_acl_block",
        intent_type="config_acl",
        vendor="huawei",
        description="华为：配置ACL封禁IP",
        param_keys=["target_ip"],
        generate=lambda p: [
            "system-view",
            f"acl number {p.get('acl_number', 3000)}",
            f"rule deny ip source {p.get('target_ip', '0.0.0.0')} 0",
            "quit",
        ],
    ),
]

def _huawei_vlan_access(params: Dict[str, Any]) -> List[str]:
    iface_str = str(params.get("interfaces", "1"))
    if isinstance(params.get("interfaces"), list):
        iface_str = params["interfaces"][0]
    vlan_id = params.get("vlan_id", params.get("vlan", 1))

    range_str, iface_list = _expand_interfaces(str(iface_str), "huawei")

    cmds = ["system-view"]
    cmds.append(f"vlan batch {vlan_id}")
    cmds.append(f"interface range {range_str}")
    cmds.append("port link-type access")
    cmds.append(f"port default vlan {vlan_id}")
    cmds.append("quit")
    return cmds

def _huawei_vlan_trunk(params: Dict[str, Any]) -> List[str]:
    iface_str = str(params.get("interfaces", "1"))
    if isinstance(params.get("interfaces"), list):
        iface_str = params["interfaces"][0]
    vlan_id = params.get("vlan_id", params.get("vlan", 1))

    range_str, _ = _expand_interfaces(str(iface_str), "huawei")

    cmds = ["system-view"]
    cmds.append(f"vlan batch {vlan_id}")
    cmds.append(f"interface range {range_str}")
    cmds.append("port link-type trunk")
    cmds.append(f"port trunk allow-pass vlan {vlan_id}")
    cmds.append("quit")
    return cmds


# ============================================================
# 思科 (cisco_ios) 模板
# ============================================================

CISCO_TEMPLATES = [
    CommandTemplate(
        name="cisco_config_vlan_access",
        intent_type="config_vlan",
        vendor="cisco_ios",
        description="思科：创建VLAN并添加接口(access模式)",
        param_keys=["interfaces", "vlan_id", "mode"],
        generate=lambda p: _cisco_vlan_access(p),
    ),
    CommandTemplate(
        name="cisco_config_vlan_trunk",
        intent_type="config_vlan",
        vendor="cisco_ios",
        description="思科：配置接口为trunk并允许VLAN",
        param_keys=["interfaces", "vlan_id", "mode"],
        generate=lambda p: _cisco_vlan_trunk(p),
    ),
    CommandTemplate(
        name="cisco_config_interface_ip",
        intent_type="config_interface",
        vendor="cisco_ios",
        description="思科：配置接口IP地址",
        param_keys=["interface", "ip", "mask"],
        generate=lambda p: [
            "enable",
            "configure terminal",
            f"interface {p.get('interface', 'Vlan1')}",
            f"ip address {p.get('ip', '0.0.0.0')} {p.get('mask', '255.255.255.0')}",
            "no shutdown",
            "end",
        ],
    ),
    CommandTemplate(
        name="cisco_config_static_route",
        intent_type="config_routing",
        vendor="cisco_ios",
        description="思科：配置静态路由",
        param_keys=["dest", "mask", "next_hop"],
        generate=lambda p: [
            "enable",
            "configure terminal",
            f"ip route {p.get('dest', '0.0.0.0')} {p.get('mask', '0.0.0.0')} {p.get('next_hop', '')}",
            "end",
        ],
    ),
    CommandTemplate(
        name="cisco_config_acl_block",
        intent_type="config_acl",
        vendor="cisco_ios",
        description="思科：配置ACL封禁IP",
        param_keys=["target_ip"],
        generate=lambda p: [
            "enable",
            "configure terminal",
            f"ip access-list extended {p.get('acl_name', 'NETOPS_BLOCK')}",
            f"deny ip host {p.get('target_ip', '0.0.0.0')} any",
            "permit ip any any",
            "end",
        ],
    ),
]

def _cisco_vlan_access(params: Dict[str, Any]) -> List[str]:
    iface_str = str(params.get("interfaces", "1"))
    if isinstance(params.get("interfaces"), list):
        iface_str = params["interfaces"][0]
    vlan_id = params.get("vlan_id", params.get("vlan", 1))

    range_str, _ = _expand_interfaces(str(iface_str), "cisco_ios")

    cmds = ["enable", "configure terminal", f"vlan {vlan_id}", "exit"]
    cmds.append(f"interface range {range_str}")
    cmds.append("switchport mode access")
    cmds.append(f"switchport access vlan {vlan_id}")
    cmds.append("end")
    return cmds

def _cisco_vlan_trunk(params: Dict[str, Any]) -> List[str]:
    iface_str = str(params.get("interfaces", "1"))
    if isinstance(params.get("interfaces"), list):
        iface_str = params["interfaces"][0]
    vlan_id = params.get("vlan_id", params.get("vlan", 1))

    range_str, _ = _expand_interfaces(str(iface_str), "cisco_ios")

    cmds = ["enable", "configure terminal", f"vlan {vlan_id}", "exit"]
    cmds.append(f"interface range {range_str}")
    cmds.append("switchport mode trunk")
    cmds.append(f"switchport trunk allowed vlan add {vlan_id}")
    cmds.append("end")
    return cmds


# ============================================================
# H3C (hp_comware) 模板
# ============================================================

H3C_TEMPLATES = [
    CommandTemplate(
        name="h3c_config_vlan_access",
        intent_type="config_vlan",
        vendor="hp_comware",
        description="H3C：创建VLAN并添加接口(access模式)",
        param_keys=["interfaces", "vlan_id", "mode"],
        generate=lambda p: _h3c_vlan_access(p),
    ),
    CommandTemplate(
        name="h3c_config_vlan_trunk",
        intent_type="config_vlan",
        vendor="hp_comware",
        description="H3C：配置接口为trunk",
        param_keys=["interfaces", "vlan_id", "mode"],
        generate=lambda p: _h3c_vlan_trunk(p),
    ),
    CommandTemplate(
        name="h3c_config_interface_ip",
        intent_type="config_interface",
        vendor="hp_comware",
        description="H3C：配置接口IP地址",
        param_keys=["interface", "ip", "mask"],
        generate=lambda p: [
            "system-view",
            f"interface {p.get('interface', 'Vlan-interface1')}",
            f"ip address {p.get('ip', '0.0.0.0')} {p.get('mask', '255.255.255.0')}",
            "quit",
        ],
    ),
    CommandTemplate(
        name="h3c_config_static_route",
        intent_type="config_routing",
        vendor="hp_comware",
        description="H3C：配置静态路由",
        param_keys=["dest", "mask", "next_hop"],
        generate=lambda p: [
            "system-view",
            f"ip route-static {p.get('dest', '0.0.0.0')} {p.get('mask', '0.0.0.0')} {p.get('next_hop', '')}",
            "quit",
        ],
    ),
    CommandTemplate(
        name="h3c_config_acl_block",
        intent_type="config_acl",
        vendor="hp_comware",
        description="H3C：配置ACL封禁IP",
        param_keys=["target_ip"],
        generate=lambda p: [
            "system-view",
            f"acl basic {p.get('acl_number', 2000)}",
            f"rule deny source {p.get('target_ip', '0.0.0.0')} 0",
            "quit",
        ],
    ),
]

def _h3c_vlan_access(params: Dict[str, Any]) -> List[str]:
    iface_str = str(params.get("interfaces", "1"))
    if isinstance(params.get("interfaces"), list):
        iface_str = params["interfaces"][0]
    vlan_id = params.get("vlan_id", params.get("vlan", 1))

    range_str, _ = _expand_interfaces(str(iface_str), "hp_comware")

    cmds = ["system-view", f"vlan {vlan_id}", "quit"]
    cmds.append(f"interface range {range_str}")
    cmds.append("port link-mode bridge")
    cmds.append(f"port access vlan {vlan_id}")
    cmds.append("quit")
    return cmds

def _h3c_vlan_trunk(params: Dict[str, Any]) -> List[str]:
    iface_str = str(params.get("interfaces", "1"))
    if isinstance(params.get("interfaces"), list):
        iface_str = params["interfaces"][0]
    vlan_id = params.get("vlan_id", params.get("vlan", 1))

    range_str, _ = _expand_interfaces(str(iface_str), "hp_comware")

    cmds = ["system-view", f"vlan {vlan_id}", "quit"]
    cmds.append(f"interface range {range_str}")
    cmds.append("port link-type trunk")
    cmds.append(f"port trunk permit vlan {vlan_id}")
    cmds.append("quit")
    return cmds


# ============================================================
# Juniper (junos) 模板
# ============================================================

JUNIPER_TEMPLATES = [
    CommandTemplate(
        name="juniper_config_vlan_access",
        intent_type="config_vlan",
        vendor="juniper_junos",
        description="Juniper：创建VLAN并添加接口",
        param_keys=["interfaces", "vlan_id", "mode"],
        generate=lambda p: _juniper_vlan_access(p),
    ),
    CommandTemplate(
        name="juniper_config_interface_ip",
        intent_type="config_interface",
        vendor="juniper_junos",
        description="Juniper：配置接口IP",
        param_keys=["interface", "ip", "mask"],
        generate=lambda p: [
            "configure",
            f"set interfaces {p.get('interface', 'ge-0/0/0')} unit 0 family inet address {p.get('ip', '0.0.0.0')}/{_mask_to_cidr(p.get('mask', '24'))}",
            "commit",
            "exit",
        ],
    ),
    CommandTemplate(
        name="juniper_config_static_route",
        intent_type="config_routing",
        vendor="juniper_junos",
        description="Juniper：配置静态路由",
        param_keys=["dest", "next_hop"],
        generate=lambda p: [
            "configure",
            f"set routing-options static route {p.get('dest', '0.0.0.0/0')} next-hop {p.get('next_hop', '')}",
            "commit",
            "exit",
        ],
    ),
]

def _juniper_vlan_access(params: Dict[str, Any]) -> List[str]:
    iface_str = str(params.get("interfaces", "1"))
    if isinstance(params.get("interfaces"), list):
        iface_str = params["interfaces"][0]
    vlan_id = params.get("vlan_id", params.get("vlan", 1))

    _, iface_list = _expand_interfaces(str(iface_str), "juniper_junos")
    vlan_name = f"v{vlan_id}"

    cmds = ["configure", f"set vlans {vlan_name} vlan-id {vlan_id}"]
    for iface in iface_list:
        cmds.append(f"set interfaces {iface} unit 0 family ethernet-switching vlan members {vlan_name}")
    cmds.extend(["commit", "exit"])
    return cmds


# ============================================================
# 模板匹配器
# ============================================================

# 按厂商分组的模板索引
_TEMPLATES_BY_VENDOR_INTENT: Dict[str, Dict[str, List[CommandTemplate]]] = {}

def _build_index():
    """构建模板索引"""
    all_templates = HUAWEI_TEMPLATES + CISCO_TEMPLATES + H3C_TEMPLATES + JUNIPER_TEMPLATES
    for t in all_templates:
        key = f"{t.vendor}"
        if key not in _TEMPLATES_BY_VENDOR_INTENT:
            _TEMPLATES_BY_VENDOR_INTENT[key] = {}
        if t.intent_type not in _TEMPLATES_BY_VENDOR_INTENT[key]:
            _TEMPLATES_BY_VENDOR_INTENT[key][t.intent_type] = []
        _TEMPLATES_BY_VENDOR_INTENT[key][t.intent_type].append(t)

_build_index()


class TemplateMatcher:
    """模板匹配器 — 模板优先，LLM兜底"""

    # vendor枚举值 → netmiko device_type → 模板分组键
    VENDOR_TO_TEMPLATE_KEY = {
        "huawei": "huawei",
        "huawei_ce": "huawei",
        "h3c": "hp_comware",
        "cisco": "cisco_ios",
        "cisco_nxos": "cisco_ios",
        "cisco_xr": "cisco_ios",
        "juniper": "juniper_junos",
        "ruijie": "cisco_ios",        # 锐捷类似思科
        "arista": "cisco_ios",         # Arista类似思科
    }

    @classmethod
    def match(cls, intent_type: str, vendor: str, parameters: Dict[str, Any]) -> Optional[List[str]]:
        """
        尝试用模板生成命令

        Args:
            intent_type: 意图类型 (config_vlan, config_interface 等)
            vendor: 厂商 (netmiko device_type)
            parameters: 意图参数

        Returns:
            命令列表，或 None（无匹配模板时返回None，走LLM兜底）
        """
        template_key = cls.VENDOR_TO_TEMPLATE_KEY.get(vendor, vendor)

        # 查找模板
        vendor_templates = _TEMPLATES_BY_VENDOR_INTENT.get(template_key, {})
        candidates = vendor_templates.get(intent_type, [])

        if not candidates:
            # 尝试直接用vendor值查找
            vendor_templates = _TEMPLATES_BY_VENDOR_INTENT.get(vendor, {})
            candidates = vendor_templates.get(intent_type, [])

        if not candidates:
            return None

        # 匹配最合适的模板
        for template in candidates:
            # 检查必需参数是否齐全
            if cls._params_match(template, parameters):
                try:
                    commands = template.generate(parameters)
                    if commands:
                        return commands
                except Exception as e:
                    log.error(f"模板 {template.name} 生成失败", error=str(e))
                    continue

        return None

    # 参数别名映射
    _PARAM_ALIASES = {
        "vlan_id": ["vlan", "vlanid", "vid"],
        "interfaces": ["interface", "iface", "port"],
        "next_hop": ["nexthop", "gateway", "gw"],
        "target_ip": ["target", "ip", "src_ip"],
    }

    # 可选参数（缺失时模板有合理默认值）
    _OPTIONAL_PARAMS = {"mode", "mask"}

    # 关键参数（缺失会导致生成错误命令，如 0.0.0.0）
    _CRITICAL_PARAMS = {"ip", "next_hop", "dest", "target_ip", "vlan_id"}

    @classmethod
    def _params_match(cls, template: CommandTemplate, parameters: Dict[str, Any]) -> bool:
        """检查参数是否匹配模板需求

        规则：
        - 可选参数缺失 → OK（模板有默认值）
        - 别名匹配 → OK（vlan_id 匹配 vlan）
        - 关键参数缺失 → FAIL（会生成 0.0.0.0 之类错误命令）
        - 非关键参数缺失 → OK
        """
        for key in template.param_keys:
            if key in parameters and parameters[key]:
                continue

            # 别名检查
            aliases = cls._PARAM_ALIASES.get(key, [])
            if any(a in parameters and parameters[a] for a in aliases):
                continue

            # 可选参数
            if key in cls._OPTIONAL_PARAMS:
                continue

            # 关键参数缺失 → 不匹配
            if key in cls._CRITICAL_PARAMS:
                return False

            # 其他参数缺失 → 允许但记录警告
            # （模板会用默认值，但如果模板默认值是 0.0.0.0 等占位符，
            #   应该标记该参数为 _CRITICAL_PARAMS）
        return True

    @classmethod
    def list_templates(cls, vendor: str = None) -> List[Dict[str, Any]]:
        """列出可用模板"""
        result = []
        for vkey, intents in _TEMPLATES_BY_VENDOR_INTENT.items():
            if vendor and vkey != vendor:
                continue
            for itype, templates in intents.items():
                for t in templates:
                    result.append({
                        "name": t.name,
                        "vendor": t.vendor,
                        "intent_type": t.intent_type,
                        "description": t.description,
                        "param_keys": t.param_keys,
                    })
        return result
