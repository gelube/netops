#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一命令执行服务 — 唯一的命令执行入口

无论意图通过何种方式解析（function calling / intent parsing / 模板匹配），
所有命令执行必须经过此服务，确保：
1. 安全检查（CommandGuard）
2. 配置备份（ConfigBackup）
3. 审计日志（AuditLogger）
4. SSH 执行

使用方式:
    svc = CommandService()
    result = svc.execute(device_info, commands, user_id="admin")
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from app.network.command_guard import CommandGuard
from app.audit import AuditLogger, AuditEntry

try:
    from netmiko import ConnectHandler
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False


@dataclass
class DeviceInfo:
    """设备信息（统一格式，屏蔽来源差异）"""
    name: str
    ip: str
    vendor: str = "huawei"          # 业务厂商: huawei/h3c/cisco/juniper
    netmiko_type: str = ""          # netmiko 设备类型
    username: str = ""
    password: str = ""
    port: int = 22
    conn_type: str = "ssh"         # ssh / telnet

    def __post_init__(self):
        if not self.netmiko_type:
            _map = {
                'huawei': 'huawei',
                'h3c': 'huawei',
                'cisco': 'cisco_ios',
                'juniper': 'juniper_junos',
            }
            self.netmiko_type = _map.get(self.vendor, 'huawei')
            # telnet免凭证时用generic_termserver_telnet
            if self.conn_type == 'telnet' and not self.username:
                self.netmiko_type = 'generic_termserver_telnet'


@dataclass
class CommandResult:
    """命令执行结果"""
    success: bool
    outputs: List[Dict[str, str]] = field(default_factory=list)  # [{"command": ..., "output": ...}]
    error: str = ""
    blocked_commands: List[str] = field(default_factory=list)
    backup_id: str = ""
    source: str = ""       # "template" | "llm" | "manual"
    risk_level: str = ""   # CommandGuard 判定的风险等级


class CommandService:
    """统一命令执行服务"""

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self.audit = audit_logger or AuditLogger()

    def execute(
        self,
        device: DeviceInfo,
        commands: List[str],
        *,
        user_id: str = "default",
        source: str = "manual",
        skip_guard: bool = False,
        auto_backup: bool = True,
        dry_run: bool = False,
    ) -> CommandResult:
        """
        执行命令的统一入口

        Args:
            device: 设备信息
            commands: 要执行的命令列表
            user_id: 操作者
            source: 命令来源 (template/llm/manual)
            skip_guard: 跳过安全检查（仅限查询命令）
            auto_backup: 修改类命令自动备份
            dry_run: 只检查不执行

        Returns:
            CommandResult
        """
        audit_entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            action="command_execute",
            target=device.name or device.ip,
            details={"source": source, "commands": commands},
            result="pending",
        )

        # 1. 安全检查
        blocked = []
        risk_level = "safe"
        if not skip_guard and commands:
            try:
                guard = CommandGuard(vendor=device.netmiko_type)
                guard_result = guard.check_commands(commands)
                blocked = guard_result.blocked_commands
                risk_level = guard_result.max_risk.label if hasattr(guard_result, 'max_risk') else "unknown"

                if blocked:
                    audit_entry.result = "blocked"
                    audit_entry.error = f"安全检查拦截: {blocked}"
                    self.audit.log(audit_entry)
                    return CommandResult(
                        success=False,
                        blocked_commands=blocked,
                        error=f"安全检查未通过，被拦截的命令: {blocked}",
                        source=source,
                        risk_level=risk_level,
                    )

                # 需要备份的修改类命令
                if auto_backup and guard_result.requires_backup and not dry_run:
                    self._backup_before_execute(device, commands, user_id)

            except Exception as guard_err:
                # CommandGuard 不可用时仅记录，不阻断查询命令
                import logging
                logging.getLogger(__name__).warning(f"CommandGuard 不可用: {guard_err}")

        # 2. dry_run 模式
        if dry_run:
            audit_entry.result = "dry_run"
            self.audit.log(audit_entry)
            return CommandResult(
                success=True,
                source=source,
                risk_level=risk_level,
                error="(dry run, 未执行)",
            )

        # 3. SSH 执行
        try:
            outputs = self._ssh_execute(device, commands)
            audit_entry.result = "success"
            self.audit.log(audit_entry)
            return CommandResult(
                success=True,
                outputs=outputs,
                source=source,
                risk_level=risk_level,
            )
        except Exception as e:
            audit_entry.result = "failed"
            audit_entry.error = str(e)
            self.audit.log(audit_entry)
            return CommandResult(
                success=False,
                error=str(e),
                source=source,
                risk_level=risk_level,
            )

    def check_only(self, device: DeviceInfo, commands: List[str]) -> CommandResult:
        """仅检查安全性，不执行"""
        return self.execute(device, commands, dry_run=True, auto_backup=False)

    def _ssh_execute(self, device: DeviceInfo, commands: List[str]) -> List[Dict[str, str]]:
        """通过 SSH/Telnet 执行命令，返回输出列表"""
        from app.network.ssh import DeviceConnection, ConnectionInfo

        conn_info = ConnectionInfo(
            ip=device.ip,
            username=device.username,
            password=device.password,
            port=device.port,
            device_type=device.netmiko_type,
        )

        outputs = []
        conn = DeviceConnection(conn_info)
        try:
            # telnet免凭证设备需要特殊连接处理
            if device.conn_type == 'telnet' and not device.username:
                conn = self._telnet_connect(device)
            else:
                conn.connect()

            for cmd in commands:
                try:
                    # telnet免凭证用原始通道
                    if device.conn_type == 'telnet' and not device.username:
                        output = self._telnet_execute(conn, cmd)
                    else:
                        output = conn.execute_command(cmd)
                    outputs.append({"command": cmd, "output": output})
                except Exception as e:
                    outputs.append({"command": cmd, "output": "", "error": str(e)})
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

        return outputs

    def _telnet_connect(self, device: DeviceInfo):
        """Telnet免凭证连接"""
        from app.network.ssh import DeviceConnection, ConnectionInfo

        conn_info = ConnectionInfo(
            ip=device.ip,
            username='',
            password='',
            port=device.port,
            device_type='generic_termserver_telnet',
        )
        conn = DeviceConnection(conn_info)
        conn.connection = ConnectHandler(
            device_type='generic_termserver_telnet',
            host=device.ip,
            port=device.port,
            username='',
            password='',
            timeout=30,
        )
        # 发 Ctrl+C 中断 auto-config
        import time
        conn.connection.write_channel('\x03')
        time.sleep(1)
        _ = conn.connection.read_channel()
        return conn

    def _telnet_execute(self, conn, cmd: str) -> str:
        """Telnet免凭证执行命令"""
        import time
        conn.connection.write_channel(cmd + '\n')
        time.sleep(2)
        output = conn.connection.read_channel()
        # 去掉回显
        lines = output.split('\n')
        filtered = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped != cmd:
                filtered.append(line)
        return '\n'.join(filtered)

    def _backup_before_execute(self, device: DeviceInfo, commands: List[str], user_id: str):
        """修改前自动备份当前配置"""
        try:
            from app.config_backup import get_backup_manager
            # 读取当前配置 — 复用_ssh_execute的telnet支持
            if device.conn_type == 'telnet' and not device.username:
                config_cmd = "display current-configuration"
                results = self._ssh_execute(device, [config_cmd])
                current_config = results[0].get('output', '') if results else ''
            else:
                from app.network.ssh import DeviceConnection, ConnectionInfo
                conn_info = ConnectionInfo(
                    ip=device.ip,
                    username=device.username,
                    password=device.password,
                    port=device.port,
                    device_type=device.netmiko_type,
                )
                with DeviceConnection(conn_info) as conn:
                    if device.netmiko_type in ('huawei', 'huawei_vrpv8', 'hp_comware'):
                        current_config = conn.execute_command("display current-configuration")
                    elif device.netmiko_type == 'juniper_junos':
                        current_config = conn.execute_command("show configuration | display set")
                    else:
                        current_config = conn.execute_command("show running-config")

                backup_mgr = get_backup_manager()
                backup = backup_mgr.backup_config(
                    hostname=device.name or device.ip,
                    config_content=current_config,
                    comment=f"自动备份 (执行前): {', '.join(commands[:3])}{'...' if len(commands) > 3 else ''}",
                )
                return backup.backup_path
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"自动备份失败: {e}")
            return None

    @staticmethod
    def device_from_dict(device_dict: Dict[str, Any], credentials: Optional[Dict[str, str]] = None) -> DeviceInfo:
        """从设备字典（devices.json 格式）创建 DeviceInfo"""
        creds = credentials or {}
        return DeviceInfo(
            name=device_dict.get('name', '') or device_dict.get('remark', ''),
            ip=device_dict.get('ip', ''),
            vendor=device_dict.get('vendor', 'huawei'),
            username=creds.get('username', device_dict.get('username', '')),
            password=creds.get('password', device_dict.get('password', '')),
            port=device_dict.get('port', 22),
            conn_type=device_dict.get('conn_type', 'ssh'),
        )
