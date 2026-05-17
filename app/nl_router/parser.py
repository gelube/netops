#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
意图解析器 - LLM 驱动的自然语言理解
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import json

from app.llm.config import LLMClient
from app.nl_router.intent_types import requires_ssh
from app.nl_router.language_map import get_language_mapper
from app.network.command_templates import TemplateMatcher

from app.logger import get_logger

log = get_logger(__name__)


class ParsedIntent(BaseModel):
    """解析后的意图"""
    intent_type: str
    confidence: float = 1.0
    parameters: Dict[str, Any] = {}
    raw_input: str = ""

    # 本地执行信息
    requires_ssh: bool = False
    ssh_commands: List[str] = []

    # 设备定位
    device_hostname: Optional[str] = None
    device_ip: Optional[str] = None


# 意图分类 Prompt 模板
INTENT_CLASSIFICATION_PROMPT = """
你是一个网络运维意图分类器。将用户的**通俗语言**请求分类为预定义的意图类型。

## 重要：理解非专业用户的说法

用户可能不懂专业术语，会用通俗说法：

**VLAN 相关：**
- "某个部门/办公室/区域的网络" → VLAN
- "财务部的网"、"访客网络"、"监控网络" → VLAN
- "1-4 号口"、"前 4 个口" → 接口 1-4
- "配个网"、"开通网络" → 配置 VLAN

**故障相关：**
- "上不了网"、"连不上"、"没网了" → 连通性故障
- "某个房间/部门上不了网" → VLAN 故障
- "ping 不通"、"打不开网页" → 连通性故障
- "路由有问题"、"网络绕远了" → 路由故障

**配置相关：**
- "加个口子"、"开个端口" → 配置接口
- "改个 IP"、"换个地址" → 配置接口 IP
- "封掉某个 IP/网站" → ACL
- "设个默认出口" → 默认路由

## 意图类型说明

### 查询类（SSH 执行）
- query_device: 查询设备信息、搜索设备
- query_config: 查看设备配置
- query_neighbors: 查看邻居设备
- query_path: 路径查询/traceroute
- query_events: 查看告警事件
- run_diagnosis: 运行诊断任务

### 本地配置执行类（需要 SSH 登录设备）
- config_vlan: 配置 VLAN（创建 VLAN、添加接口到 VLAN）
- config_interface: 配置接口（IP、描述、开关）
- config_routing: 配置路由（静态路由、OSPF、BGP）
- config_acl: 配置 ACL/防火墙规则

### 故障排查类（自动执行检查序列）
- diagnose_vlan: VLAN 相关故障排查
- diagnose_routing: 路由故障排查
- diagnose_connectivity: 连通性故障排查

## 用户输入
{user_input}

## 输出格式
返回 JSON 格式（只返回 JSON，不要其他内容）：
{{
    "intent_type": "意图类型",
    "confidence": 0.0-1.0 置信度，
    "parameters": {{
        // 根据意图类型填充参数
    }},
    "device_hostname": "设备名（如果有）",
    "device_ip": "设备 IP（如果有）",
    "vlan_id": "VLAN ID（如果能从上下文推断，比如'财务部'对应 VLAN 10）"
}}

## 示例

### 专业说法
输入："查一下 SW-Core 的配置"
输出：{{"intent_type": "query_config", "confidence": 0.95, "parameters": {{}}, "device_hostname": "SW-Core"}}

输入："给 SW-Core 的 1-4 口配 VLAN 10"
输出：{{"intent_type": "config_vlan", "confidence": 0.9, "parameters": {{"interfaces": ["1-4"], "vlan": 10, "mode": "access"}}, "device_hostname": "SW-Core"}}

### 通俗说法（重点）
输入："财务部的电脑上不了网，帮我看看"
输出：{{"intent_type": "diagnose_vlan", "confidence": 0.85, "parameters": {{"vlan_id": 10, "symptom": "上不了网", "department": "财务部"}}, "device_hostname": ""}}

输入："把访客网络的口子开到 1-8"
输出：{{"intent_type": "config_vlan", "confidence": 0.8, "parameters": {{"interfaces": ["1-8"], "vlan_id": 100, "mode": "access", "network_name": "访客网络"}}, "device_hostname": ""}}

输入："1 号到 4 号口都通上网"
输出：{{"intent_type": "config_vlan", "confidence": 0.75, "parameters": {{"interfaces": ["1-4"], "mode": "access"}}, "device_hostname": ""}}

输入："从 10.10.10.1 到 8.8.8.8 怎么走"
输出：{{"intent_type": "query_path", "confidence": 0.95, "parameters": {{"source_ip": "10.10.10.1", "dest_ip": "8.8.8.8"}}}}

输入："监控室没网络了"
输出：{{"intent_type": "diagnose_vlan", "confidence": 0.8, "parameters": {{"symptom": "没网络", "location": "监控室"}}, "device_hostname": ""}}

输入："封掉 192.168.1.100 这个设备"
输出：{{"intent_type": "config_acl", "confidence": 0.85, "parameters": {{"action": "block", "target_ip": "192.168.1.100"}}, "device_hostname": ""}}
"""

# 配置命令生成 Prompt 模板
CONFIG_COMMAND_PROMPT = """
你是一个网络配置命令生成器。根据意图参数和设备厂商，生成具体的 CLI 配置命令。

## 设备厂商
Vendor: {vendor}

## 配置意图
Intent: {intent_type}
Parameters: {parameters}

## 输出格式
返回 JSON 数组，每个元素是一条命令：
["command1", "command2", ...]

## 厂商命令风格

### 华为 (huawei)
- 进入系统视图：system-view
- 批量接口：interface range GE0/0/1 to GE0/0/4
- VLAN 配置：port link-type access, port default vlan 10
- 退出：quit

### H3C (h3c)
- 进入系统视图：system-view
- 批量接口：interface range GigabitEthernet1/0/1 to GigabitEthernet1/0/4
- VLAN 配置：port link-mode bridge, port access vlan 10
- 退出：quit

### 思科 (cisco)
- 进入特权模式：enable, configure terminal
- 批量接口：interface range GigabitEthernet0/1 - 4
- VLAN 配置：switchport mode access, switchport access vlan 10
- 退出：exit

### 瞻博 (juniper)
- 进入配置模式：configure
- 批量接口：set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members 10
- 提交：commit
- 退出：exit

### 锐捷 (ruijie)
- 进入特权模式：enable, configure terminal
- 类似思科风格

### Arista (arista)
- 类似思科风格，但使用 EOS 语法

### 华为 CloudEngine (huawei_ce)
- 数据中心交换机，使用 VRPV8 语法

### Cisco Nexus (cisco_nxos)
- NX-OS 语法，支持 VPC、FabricPath

## 示例

Vendor: huawei
Intent: config_vlan
Parameters: {{"interfaces": ["GE0/0/1", "GE0/0/2", "GE0/0/3", "GE0/0/4"], "vlan": 10, "mode": "access"}}
输出：["system-view", "vlan batch 10", "interface range GE0/0/1 to GE0/0/4", "port link-type access", "port default vlan 10", "quit"]

Vendor: cisco
Intent: config_vlan
Parameters: {{"interfaces": ["GigabitEthernet0/1", "GigabitEthernet0/2"], "vlan": 20, "mode": "access"}}
输出：["enable", "configure terminal", "vlan 20", "exit", "interface range GigabitEthernet0/1 - 2", "switchport mode access", "switchport access vlan 20", "end"]

Vendor: h3c
Intent: config_vlan
Parameters: {{"interfaces": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2"], "vlan": 30, "mode": "access"}}
输出：["system-view", "vlan 30", "quit", "interface range GigabitEthernet1/0/1 to GigabitEthernet1/0/2", "port link-mode bridge", "port access vlan 30", "quit"]

Vendor: juniper
Intent: config_vlan
Parameters: {{"interfaces": ["ge-0/0/1", "ge-0/0/2"], "vlan": 40, "mode": "access"}}
输出：["configure", "set vlans v40 vlan-id 40", "set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members v40", "set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members v40", "commit", "exit"]

Vendor: huawei
Intent: config_interface
Parameters: {{"interface": "Vlanif10", "ip": "192.168.10.1", "mask": "255.255.255.0"}}
输出：["system-view", "interface Vlanif10", "ip address 192.168.10.1 255.255.255.0", "quit"]

Vendor: cisco
Intent: config_interface
Parameters: {{"interface": "Vlan20", "ip": "192.168.20.1", "mask": "255.255.255.0"}}
输出：["enable", "configure terminal", "interface Vlan20", "ip address 192.168.20.1 255.255.255.0", "no shutdown", "end"]

Vendor: huawei
Intent: config_routing
Parameters: {{"type": "static", "dest": "0.0.0.0", "mask": "0.0.0.0", "next_hop": "192.168.1.1"}}
输出：["system-view", "ip route-static 0.0.0.0 0.0.0.0 192.168.1.1", "quit"]

Vendor: cisco
Intent: config_routing
Parameters: {{"type": "static", "dest": "10.0.0.0", "mask": "255.255.255.0", "next_hop": "192.168.1.254"}}
输出：["enable", "configure terminal", "ip route 10.0.0.0 255.255.255.0 192.168.1.254", "end"]

Vendor: huawei
Intent: config_acl
Parameters: {{"action": "block", "target_ip": "192.168.100.10", "acl_number": 3000}}
输出：["system-view", "acl number 3000", "rule deny ip source 192.168.100.10 0", "quit"]

Vendor: cisco
Intent: config_acl
Parameters: {{"action": "block", "target_ip": "192.168.100.20", "acl_name": "NETOPS_BLOCK"}}
输出：["enable", "configure terminal", "ip access-list extended NETOPS_BLOCK", "deny ip host 192.168.100.20 any", "permit ip any any", "end"]
"""


class IntentParser:
    """意图解析器"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        # 导入通俗语言映射器
        self.language_mapper = get_language_mapper()

    def parse(self, user_input: str, context: str = "") -> ParsedIntent:
        """
        解析用户输入（支持通俗语言）

        Args:
            user_input: 用户自然语言输入
            context: 会话上下文（如之前的设备、VLAN等）

        Returns:
            ParsedIntent
        """
        # 第零步：通俗语言解析（提取部门、位置、接口等）
        lang_parse = self.language_mapper.parse_user_input(user_input)

        # 第一步：意图分类（附带上文）
        intent = self._classify_intent(user_input, context=context)
        intent.raw_input = user_input

        # 第二步：合并通俗语言解析结果
        if lang_parse["parameters"]:
            # 合并参数（用户明确指定的优先）
            for key, value in lang_parse["parameters"].items():
                if key not in intent.parameters or not intent.parameters[key]:
                    intent.parameters[key] = value

        # 提取的信息存入 parameters
        if lang_parse.get("extracted_info"):
            for key, value in lang_parse["extracted_info"].items():
                if key not in intent.parameters:
                    intent.parameters[key] = value

        # 第三步：标记 SSH 执行
        if requires_ssh(intent.intent_type):
            intent.requires_ssh = True

        return intent

    def _classify_intent(self, user_input: str, context: str = "") -> ParsedIntent:
        """使用 LLM 分类意图"""
        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_input=user_input)

        # 如果有上下文，附加到 prompt 中
        if context:
            prompt += f"\n\n## 上下文\n{context}"

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # 低温度保证输出稳定
            )

            content = response.get("content", "")

            # 解析 JSON 输出
            # 清理可能的 markdown 标记
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)

            return ParsedIntent(
                intent_type=data.get("intent_type", ""),
                confidence=data.get("confidence", 1.0),
                parameters=data.get("parameters", {}),
                device_hostname=data.get("device_hostname"),
                device_ip=data.get("device_ip"),
            )

        except Exception as e:
            # 降级：返回基础意图
            return ParsedIntent(
                intent_type="query_device",
                confidence=0.5,
                parameters={"fallback_reason": str(e)},
                raw_input=user_input,
            )

    def generate_config_commands(
        self,
        intent: ParsedIntent,
        vendor: str,
        device_hostname: str
    ) -> List[str]:
        """
        生成配置命令 — 模板优先，LLM兜底

        Args:
            intent: 解析后的意图
            vendor: 设备厂商 (huawei/cisco/h3c/juniper)
            device_hostname: 设备名

        Returns:
            配置命令列表
        """
        # 1. 先尝试模板匹配（100%可靠）
        template_commands = TemplateMatcher.match(
            intent_type=intent.intent_type,
            vendor=vendor,
            parameters=intent.parameters
        )

        if template_commands:
            return template_commands

        # 2. 模板未匹配，走LLM生成
        prompt = CONFIG_COMMAND_PROMPT.format(
            vendor=vendor,
            intent_type=intent.intent_type,
            parameters=intent.parameters
        )

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            content = response.get("content", "")

            # 清理 markdown
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            commands = json.loads(content)
            return commands

        except Exception as e:
            # 降级：返回空命令列表
            log.error("生成配置命令失败", error=str(e))
            return []
