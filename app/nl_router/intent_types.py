#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
意图类型定义 - 纯 SSH 模式
"""
from enum import Enum
from typing import Dict, Optional


class IntentType(str, Enum):
    """意图类型枚举"""
    
    # === 查询类（SSH 执行）===
    QUERY_DEVICE = "query_device"          # 查询设备信息
    QUERY_CONFIG = "query_config"          # 查看设备配置
    QUERY_NEIGHBORS = "query_neighbors"    # 查看邻居设备
    QUERY_PATH = "query_path"              # 路径查询
    QUERY_EVENTS = "query_events"          # 事件查询（本地日志）
    RUN_DIAGNOSIS = "run_diagnosis"        # 触发诊断
    
    # === 配置类（SSH 执行）===
    CONFIG_VLAN = "config_vlan"            # 配置 VLAN
    CONFIG_INTERFACE = "config_interface"  # 配置接口
    CONFIG_ROUTING = "config_routing"      # 配置路由
    CONFIG_ACL = "config_acl"              # 配置 ACL
    
    # === 诊断类（SSH 工作流）===
    DIAGNOSE_VLAN = "diagnose_vlan"        # VLAN 诊断
    DIAGNOSE_ROUTING = "diagnose_routing"  # 路由诊断
    DIAGNOSE_CONNECTIVITY = "diagnose_connectivity"  # 连通性诊断


# 需要 SSH 执行的意图
SSH_INTENT_TYPES = {
    IntentType.QUERY_DEVICE,
    IntentType.QUERY_CONFIG,
    IntentType.QUERY_NEIGHBORS,
    IntentType.QUERY_PATH,
    IntentType.QUERY_EVENTS,
    IntentType.RUN_DIAGNOSIS,
    IntentType.CONFIG_VLAN,
    IntentType.CONFIG_INTERFACE,
    IntentType.CONFIG_ROUTING,
    IntentType.CONFIG_ACL,
    IntentType.DIAGNOSE_VLAN,
    IntentType.DIAGNOSE_ROUTING,
    IntentType.DIAGNOSE_CONNECTIVITY,
}


def requires_ssh(intent_type: str) -> bool:
    """判断是否需要 SSH 执行"""
    return intent_type in SSH_INTENT_TYPES


def is_diagnosis(intent_type: str) -> bool:
    """判断是否是诊断类型"""
    return intent_type in {
        IntentType.DIAGNOSE_VLAN,
        IntentType.DIAGNOSE_ROUTING,
        IntentType.DIAGNOSE_CONNECTIVITY,
    }


# 意图描述（用于帮助文档）
INTENT_DESCRIPTIONS: Dict[str, str] = {
    IntentType.QUERY_DEVICE: "查询设备信息、搜索设备",
    IntentType.QUERY_CONFIG: "查看设备配置",
    IntentType.QUERY_NEIGHBORS: "查看邻居设备（LLDP/CDP）",
    IntentType.QUERY_PATH: "路径查询/traceroute",
    IntentType.QUERY_EVENTS: "查看设备日志/告警事件",
    IntentType.RUN_DIAGNOSIS: "运行诊断任务",
    IntentType.CONFIG_VLAN: "配置 VLAN（创建 VLAN、添加接口到 VLAN）",
    IntentType.CONFIG_INTERFACE: "配置接口（IP、描述、开关）",
    IntentType.CONFIG_ROUTING: "配置路由（静态路由、OSPF、BGP）",
    IntentType.CONFIG_ACL: "配置 ACL/防火墙规则",
    IntentType.DIAGNOSE_VLAN: "VLAN 相关故障排查",
    IntentType.DIAGNOSE_ROUTING: "路由故障排查",
    IntentType.DIAGNOSE_CONNECTIVITY: "连通性故障排查",
}
