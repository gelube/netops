#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令安全守卫 - 在 LLM 生成命令后、SSH 执行前进行校验和防护

三层防护：
1. 危险模式检测（正则匹配）
2. 命令语法校验（厂商规则）
3. 自动备份+回滚机制
"""
import re
from typing import List
from dataclasses import dataclass, field
from enum import Enum

from app.logger import get_logger

log = get_logger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    SAFE = 0           # 安全（只读查询）
    LOW = 1            # 低风险（常规配置）
    MEDIUM = 2         # 中风险（修改路由/ACL/接口）
    HIGH = 3           # 高风险（删除/重置/关机）
    CRITICAL = 4       # 极高风险（擦除配置/重启设备）

    @property
    def label(self) -> str:
        """人类可读的标签"""
        _labels = {0: "safe", 1: "low", 2: "medium", 3: "high", 4: "critical"}
        return _labels.get(self.value, "unknown")


@dataclass
class CommandCheckResult:
    """命令检查结果"""
    command: str
    risk_level: RiskLevel
    is_allowed: bool = True
    warnings: List[str] = field(default_factory=list)
    blocked_reason: str = ""


@dataclass
class GuardResult:
    """完整检查结果"""
    is_safe: bool = True
    results: List[CommandCheckResult] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    max_risk: RiskLevel = RiskLevel.SAFE
    requires_backup: bool = False


class CommandGuard:
    """命令安全守卫"""

    # 极高风险命令 → 直接拦截
    CRITICAL_PATTERNS = [
        r'\b(erase|delete)\s+(flash|nvram|startup-config|running-config)\b',
        r'\b(format)\s+(flash|slot)\b',
        r'\b(factory-reset)\b',
        r'\b(reset)\s+(saved-configuration|current-configuration)\b',
        r'\b(write\s+erase|write\s+erase\b)',
        r'\b(delete)\s+(vlan\.dat)\b',
        r'\b(clear)\s+(startup-config|running-config|current-configuration)\b',
        r'\b(reset)\s+(stack|cluster)\b',
        r'\b(undo)\s+(startup-configuration|current-configuration)\b',
        r'\b(erase)\s+(configuration)\b',
        r'\b(startup\s+config)\s*(=|:)\s*$\b',
    ]

    # 高风险命令 → 允许但需额外确认
    HIGH_PATTERNS = [
        r'\breload\b',
        r'\breboot\b',
        r'(?:^|\n)\s*shutdown\b',                    # 关接口（仅在行首或配置块内）
        r'\binterface\s+\S+[\s\S]*?shutdown\b',  # 接口下 shutdown
        r'\bno\s+(vlan|interface)\s+\d+',      # 删VLAN/接口
        r'\bno\s+ip\s+route\b',                # 删路由
        r'\bundo\s+(vlan|interface)\b',        # 华为删VLAN/接口
        r'\bundo\s+ip\s+route-static\b',       # 华为删路由
        r'\bundo\s+stp\s+enable\b',            # 关STP
        r'\bno\s+spanning-tree\b',             # 关STP
        r'\bport\s+link-type\s+trunk\b',       # 改trunk可能影响多VLAN
        r'\bswitchport\s+mode\s+trunk\b',      # 同上
        r'\bacl\s+\d+\s+rule\s+permit\s+ip\s+any\s+any\b',  # 全放行ACL
        r'\baccess-list\s+\d+\s+permit\s+ip\s+any\s+any\b', # 同上
        r'\bclear\s+(arp|mac|ip\s+route|ospf|bgp)\b',   # 清除表项
        r'\breset\s+(ospf|bgp|stp|lldp)\b',    # 重置协议
        r'\bundo\s+(ospf|bgp|isis)\s+\d*\b',  # 删除路由协议
        r'\bno\s+(router\s+ospf|router\s+bgp)\b',  # 同上
    ]

    # 中风险命令 → 需要备份
    MEDIUM_PATTERNS = [
        r'\b(ip\s+route-static|ip\s+route)\b',         # 静态路由
        r'\b(ospf|bgp|isis)\b',                         # 动态路由协议
        r'\b(acl|access-list)\s+\d+',                   # ACL规则
        r'\b(vlan)\s+\d+\b',                            # VLAN操作
        r'\b(port\s+default\s+vlan|switchport\s+access\s+vlan)\b',  # 接口VLAN
        r'\b(port\s+link-type|switchport\s+mode)\b',    # 端口模式
        r'\b(trunk|port\s+trunk)\b',                    # Trunk配置
        r'\b(nat|static\s+nat|easy\s+ip)\b',            # NAT配置
    ]

    # 安全命令（只读查询）
    SAFE_PATTERNS = [
        r'^(show|display|get|ping|traceroute)\b',
        r'^(show|display)\s+(version|running-config|current-config|ip|interface|vlan|arp|mac|route|lldp|cdp|ntp|clock|logging|acl|ospf|bgp|stp|environment|alarm|cpu|memory)\b',
    ]

    # 厂商特定的命令前缀
    VENDOR_VIEW_PREFIXES = {
        "huawei": ["display"],
        "huawei_vrpv8": ["display"],
        "hp_comware": ["display"],
        "cisco_ios": ["show"],
        "cisco_nxos": ["show"],
        "cisco_xr": ["show"],
        "juniper_junos": ["show"],
        "ruijie_os": ["show"],
        "arista_eos": ["show"],
    }

    # 厂商配置模式入口（需要确认进入配置模式）
    VENDOR_CONFIG_ENTERS = {
        "huawei": ["system-view"],
        "huawei_vrpv8": ["system-view"],
        "hp_comware": ["system-view"],
        "cisco_ios": ["configure terminal", "enable"],
        "cisco_nxos": ["configure terminal"],
        "cisco_xr": ["configure"],
        "juniper_junos": ["configure"],
        "ruijie_os": ["configure terminal", "enable"],
        "arista_eos": ["configure"],
    }

    def __init__(self, vendor: str = "", strict_mode: bool = False):
        """
        Args:
            vendor: 设备厂商(netmiko device_type)
            strict_mode: 严格模式下，未识别的命令默认为MEDIUM风险
        """
        self.vendor = vendor
        self.strict_mode = strict_mode

    def check_commands(self, commands: List[str]) -> GuardResult:
        """
        检查命令列表的安全性

        Returns:
            GuardResult 包含每个命令的风险等级和是否允许执行
        """
        result = GuardResult()
        in_config_mode = False

        for cmd in commands:
            cmd_stripped = cmd.strip()
            if not cmd_stripped:
                continue

            # 检测是否进入配置模式
            if self._is_config_enter(cmd_stripped):
                in_config_mode = True
                check = CommandCheckResult(
                    command=cmd_stripped,
                    risk_level=RiskLevel.SAFE,
                    is_allowed=True,
                )
                result.results.append(check)
                continue

            # 检测退出配置模式
            if cmd_stripped.lower() in ('quit', 'exit', 'end', 'return'):
                in_config_mode = False
                check = CommandCheckResult(
                    command=cmd_stripped,
                    risk_level=RiskLevel.SAFE,
                    is_allowed=True,
                )
                result.results.append(check)
                continue

            # 逐层检查风险
            check = self._check_single_command(cmd_stripped, in_config_mode)
            result.results.append(check)

            # 汇总结果
            if not check.is_allowed:
                result.is_safe = False
                result.blocked_commands.append(cmd_stripped)

            if check.warnings:
                result.warnings.extend(check.warnings)

            if check.risk_level.value > result.max_risk.value:
                result.max_risk = check.risk_level

            if check.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
                result.requires_backup = True

        return result

    def _is_config_enter(self, cmd: str) -> bool:
        """判断是否是进入配置模式的命令"""
        enters = self.VENDOR_CONFIG_ENTERS.get(self.vendor, [])
        return any(cmd.lower().strip().startswith(e) for e in enters)

    def _check_single_command(self, cmd: str, in_config_mode: bool) -> CommandCheckResult:
        """检查单条命令"""
        cmd_lower = cmd.lower()

        # 1. 检查安全命令（只读查询）
        for pattern in self.SAFE_PATTERNS:
            if re.search(pattern, cmd_lower):
                return CommandCheckResult(
                    command=cmd,
                    risk_level=RiskLevel.SAFE,
                    is_allowed=True,
                )

        # 2. 检查极高风险 → 直接拦截
        for pattern in self.CRITICAL_PATTERNS:
            if re.search(pattern, cmd_lower):
                return CommandCheckResult(
                    command=cmd,
                    risk_level=RiskLevel.CRITICAL,
                    is_allowed=False,
                    blocked_reason=f"极高风险操作：匹配到禁止模式 '{pattern}'",
                )

        # 3. 检查高风险 → 需额外确认
        for pattern in self.HIGH_PATTERNS:
            if re.search(pattern, cmd_lower):
                return CommandCheckResult(
                    command=cmd,
                    risk_level=RiskLevel.HIGH,
                    is_allowed=True,
                    warnings=[f"⚠️ 高风险操作：'{cmd}'，执行前请确认已备份配置"],
                )

        # 4. 检查中风险 → 需要备份
        for pattern in self.MEDIUM_PATTERNS:
            if re.search(pattern, cmd_lower):
                return CommandCheckResult(
                    command=cmd,
                    risk_level=RiskLevel.MEDIUM,
                    is_allowed=True,
                    warnings=[f"配置变更：'{cmd}'，建议先备份"],
                )

        # 5. 未匹配规则
        if in_config_mode or self.strict_mode:
            return CommandCheckResult(
                command=cmd,
                risk_level=RiskLevel.LOW,
                is_allowed=True,
                warnings=["未识别的配置命令，请确认正确性"],
            )

        return CommandCheckResult(
            command=cmd,
            risk_level=RiskLevel.SAFE,
            is_allowed=True,
        )

    def get_backup_commands(self) -> List[str]:
        """生成备份当前配置的命令"""
        view_prefixes = self.VENDOR_VIEW_PREFIXES.get(self.vendor, ["show"])
        prefix = view_prefixes[0]

        if self.vendor in ("huawei", "huawei_vrpv8", "hp_comware"):
            return [f"{prefix} current-configuration"]
        elif self.vendor in ("cisco_ios", "cisco_nxos", "cisco_xr", "ruijie_os", "arista_eos"):
            return [f"{prefix} running-config"]
        elif self.vendor == "juniper_junos":
            return [f"{prefix} configuration | display set"]
        else:
            return [f"{prefix} running-config"]

    def format_guard_report(self, guard_result: GuardResult) -> str:
        """格式化安全检查报告"""
        if not guard_result.results:
            return "没有命令需要检查"

        lines = ["📋 命令安全检查报告", "=" * 40]

        risk_emoji = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.LOW: "🔵",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }

        for r in guard_result.results:
            emoji = risk_emoji.get(r.risk_level, "⚪")
            status = "✅" if r.is_allowed else "🚫"
            lines.append(f"  {emoji} {status} {r.command}")

            if r.blocked_reason:
                lines.append(f"     └─ {r.blocked_reason}")
            for w in r.warnings:
                lines.append(f"     └─ {w}")

        lines.append("")
        lines.append(f"最高风险等级: {risk_emoji.get(guard_result.max_risk, '⚪')} {guard_result.max_risk.label}")

        if guard_result.blocked_commands:
            lines.append(f"🚫 被拦截的命令: {len(guard_result.blocked_commands)} 条")
            for bc in guard_result.blocked_commands:
                lines.append(f"   - {bc}")

        if guard_result.warnings:
            lines.append(f"⚠️  警告: {len(guard_result.warnings)} 条")

        if guard_result.requires_backup:
            lines.append("💾 建议: 执行前先备份当前配置")

        return "\n".join(lines)


class ConfigBackupHelper:
    """配置备份与回滚辅助器（配置diff和回滚命令生成）"""

    def __init__(self, ssh_connection, vendor: str = ""):
        self.conn = ssh_connection
        self.vendor = vendor
        self.backup_config: str = ""

    def backup(self) -> bool:
        """备份当前配置"""
        guard = CommandGuard(vendor=self.vendor)
        backup_cmds = guard.get_backup_commands()

        try:
            outputs = []
            for cmd in backup_cmds:
                output = self.conn.execute_command(cmd, timeout=60)
                outputs.append(output)
            self.backup_config = "\n".join(outputs)
            return bool(self.backup_config.strip())
        except Exception as e:
            log.error("备份配置失败", error=str(e))
            return False

    def get_rollback_commands(self) -> List[str]:
        """
        生成回滚命令（概念性框架）

        注意：
        - 华为需要 configuration rollback commit，需提前开启 rollback 功能
        - 思科需要 configure replace，需事先 archive 配置
        - Juniper 的 rollback 最简单，自动保存前50个commit
        - 完整回滚应基于配置diff生成 undo/no 命令，而非整体替换
        此方法仅返回指导性命令模板，不可直接执行。
        """
        if self.vendor in ("huawei", "huawei_vrpv8", "hp_comware"):
            return [
                "# 华为回滚需先开启: rollback configuration commit",
                "# 然后执行: rollback configuration to commit-id <ID>",
                "# 或: compare configuration (查看差异)",
            ]
        elif self.vendor in ("cisco_ios", "cisco_nxos", "ruijie_os", "arista_eos"):
            return [
                "# 思科回滚需先配置: archive",
                "# 然后执行: configure replace flash:<filename>",
                "# 或: show archive (查看历史)",
            ]
        elif self.vendor == "juniper_junos":
            return [
                "configure",
                "rollback <N>",  # N = 回滚编号，0是最前一个commit
                "commit",
            ]
        else:
            return ["# 未知厂商，请手动回滚"]

    def get_config_diff_commands(self) -> List[str]:
        """获取配置变更差异的命令"""
        if self.vendor in ("huawei", "huawei_vrpv8", "hp_comware"):
            return ["display configuration commit changes"]
        elif self.vendor in ("cisco_ios", "cisco_nxos"):
            return ["show archive config differences"]
        elif self.vendor == "juniper_junos":
            return ["show configuration | compare rollback ?"]
        return []
