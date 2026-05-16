"""
自然语言执行器 - 纯 SSH 模式
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from app.nl_router.parser import ParsedIntent, IntentParser
from app.session import SessionManager
from app.session.models import TurnRole
from app.audit import AuditLogger, AuditEntry
from app.network.command_guard import CommandGuard, ConfigBackup


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    message: str
    data: Optional[Any] = None
    requires_confirmation: bool = False
    confirmation_details: Optional[str] = None


class NLExecutor:
    """自然语言执行器（纯 SSH 模式）"""
    
    def __init__(self, llm_client=None, credential_manager=None, session_manager=None, audit_logger=None):
        """
        初始化
        
        Args:
            llm_client: LLM 客户端
            credential_manager: 凭证管理器（可选）
            session_manager: 会话管理器（可选）
            audit_logger: 审计日志器（可选）
        """
        self.llm_client = llm_client
        self.credential_manager = credential_manager
        self.session_manager = session_manager or SessionManager()
        self.audit_logger = audit_logger or AuditLogger()
        self.intent_parser = IntentParser(llm_client) if llm_client else None
    
    async def execute(self, user_input: str, user_id: str = "default") -> ExecutionResult:
        """
        执行用户自然语言请求
        
        Args:
            user_input: 用户输入
            user_id: 用户ID（支持多用户）
        """
        # 创建审计条目
        audit_entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            action="unknown",
            target="",
            details={"input": user_input},
            result="pending"
        )
        
        if not self.intent_parser:
            audit_entry.result = "failed"
            audit_entry.error = "LLM 客户端未初始化"
            self.audit_logger.log(audit_entry)
            return ExecutionResult(
                success=False,
                message="LLM 客户端未初始化，无法解析意图"
            )
        
        try:
            # 解析引用（如"那台设备"、"那个VLAN"）
            resolved_input = self._resolve_references(user_input, user_id)
            
            # 获取上下文
            context = self.session_manager.get_context_for_query(user_id, resolved_input)
            
            # 记录用户输入
            self.session_manager.add_turn(
                user_id=user_id,
                role=TurnRole.USER,
                content=user_input
            )
            
            # 解析意图（带上下文）
            intent = await self.intent_parser.parse(resolved_input, context=context)
            
            if intent.requires_ssh:
                result = await self._execute_ssh_config(intent)
            elif intent.intent_type.startswith("query_"):
                result = await self._execute_query(intent)
            elif intent.intent_type.startswith("diagnose_"):
                result = await self._execute_diagnosis(intent)
            else:
                result = ExecutionResult(
                    success=False,
                    message=f"未知意图类型：{intent.intent_type}"
                )
            
            # 记录助手响应
            self.session_manager.add_turn(
                user_id=user_id,
                role=TurnRole.ASSISTANT,
                content=result.message,
                execution_success=result.success,
                execution_data=result.data or {}
            )
            
            # 更新审计条目
            audit_entry.action = intent.intent_type
            audit_entry.target = str(intent.device_hostname) if intent.device_hostname else ""
            audit_entry.details = intent.parameters
            audit_entry.result = "success"
            
            return result
        
        except Exception as e:
            audit_entry.result = "failed"
            audit_entry.error = str(e)
            raise
        finally:
            self.audit_logger.log(audit_entry)
    
    async def _execute_query(self, intent: ParsedIntent) -> ExecutionResult:
        """执行查询类请求"""
        device_ip = intent.device_ip or intent.parameters.get("device_ip", "")
        device_hostname = intent.device_hostname
        
        if not device_ip and not device_hostname:
            return ExecutionResult(
                success=False,
                message="查询需要指定设备。用法：'查一下 SW-Core (IP: 192.168.1.1) 的配置'"
            )
        
        return ExecutionResult(
            success=True,
            message="已生成查询命令，需要 SSH 凭证",
            requires_confirmation=True,
            confirmation_details=f"查询设备：{device_hostname or device_ip}\n\n请提供 SSH 凭证或使用 !save 命令保存凭证",
            data={
                "query_type": intent.intent_type,
                "device": device_hostname,
                "device_ip": device_ip,
            }
        )
    
    async def _execute_ssh_config(self, intent: ParsedIntent) -> ExecutionResult:
        """执行 SSH 配置"""
        if not self.llm_client:
            return ExecutionResult(success=False, message="LLM 客户端未初始化")
        
        device_hostname = intent.device_hostname
        device_ip = intent.parameters.get("device_ip", "")
        vendor_str = intent.parameters.get("vendor", "huawei")
        
        if not device_hostname and not device_ip:
            return ExecutionResult(success=False, message="未指定设备，无法执行配置")
        
        if not device_ip:
            return ExecutionResult(
                success=False,
                message=f"需要指定设备 IP。用法：给 {device_hostname} (IP: 192.168.1.1) 配...",
                requires_confirmation=True,
                confirmation_details=f"请在命令中指定设备 IP，例如：\n给 {device_hostname} (IP: 192.168.1.1) 配 VLAN 10"
            )
        
        from app.core.device import Vendor
        vendor_map = {
            "huawei": Vendor.HUAWEI,
            "cisco": Vendor.CISCO,
            "h3c": Vendor.H3C,
            "juniper": Vendor.JUNIPER,
        }
        vendor = vendor_map.get(vendor_str.lower(), Vendor.HUAWEI)
        
        # 确定netmiko device_type用于安全校验
        from app.network.ssh import DeviceConnection
        netmiko_type = DeviceConnection.VENDOR_DEVICE_TYPE_MAP.get(vendor, "cisco_ios")
        
        commands = await self.intent_parser.generate_config_commands(
            intent=intent,
            vendor=vendor.value,
            device_hostname=device_hostname or "device"
        )
        
        if not commands:
            return ExecutionResult(success=False, message="未能生成配置命令")
        
        # ===== 新增：命令安全校验 =====
        guard = CommandGuard(vendor=netmiko_type, strict_mode=True)
        guard_result = guard.check_commands(commands)
        
        # 如果有被拦截的命令，拒绝执行
        if guard_result.blocked_commands:
            report = guard.format_guard_report(guard_result)
            return ExecutionResult(
                success=False,
                message=f"命令安全检查未通过，{len(guard_result.blocked_commands)} 条命令被拦截",
                requires_confirmation=False,
                confirmation_details=report,
                data={"guard_result": guard_result, "commands": commands},
            )
        
        confirmation_details = self._format_confirmation(
            device_hostname or "device", device_ip, vendor.value, commands
        )
        
        # 附加安全检查报告
        if guard_result.warnings or guard_result.requires_backup:
            report = guard.format_guard_report(guard_result)
            confirmation_details += f"\n\n{report}"
        
        return ExecutionResult(
            success=True,
            message="已生成配置命令，等待确认",
            requires_confirmation=True,
            confirmation_details=confirmation_details,
            data={
                "commands": commands,
                "device": device_hostname,
                "device_ip": device_ip,
                "vendor": vendor.value,
                "guard_result": guard_result,  # 传递安全检查结果
            }
        )
    
    async def confirm_and_execute(
        self, 
        confirmed: bool, 
        device_data: Dict[str, Any],
        username: str, 
        password: str,
    ) -> ExecutionResult:
        """用户确认后执行配置（含自动备份）"""
        if not confirmed:
            return ExecutionResult(success=False, message="用户取消配置")
        
        device_ip = device_data.get("device_ip", "")
        commands = device_data.get("commands", [])
        vendor = device_data.get("vendor", "")
        guard_result = device_data.get("guard_result")
        
        if not device_ip or not commands:
            return ExecutionResult(success=False, message="设备数据不完整")
        
        # 检查安全校验结果——如果有被拦截的命令，不允许执行
        if guard_result and guard_result.blocked_commands:
            return ExecutionResult(
                success=False,
                message=f"安全检查未通过，{len(guard_result.blocked_commands)} 条命令被拦截，拒绝执行"
            )
        
        from app.network.ssh import test_connection, DeviceConnection, ConnectionInfo
        
        if not test_connection(device_ip):
            return ExecutionResult(success=False, message=f"无法连接到设备 {device_ip}")
        
        try:
            conn_info = ConnectionInfo(ip=device_ip, username=username, password=password)
            
            with DeviceConnection(conn_info) as conn:
                # 如果有配置变更，先备份
                backup = ConfigBackup(conn, vendor=vendor)
                needs_backup = guard_result.requires_backup if guard_result else any(
                    cmd.strip().lower() not in ('quit', 'exit', 'end', 'return', 'y')
                    for cmd in commands
                )
                
                backup_ok = False
                if needs_backup:
                    backup_ok = backup.backup()
                    if not backup_ok:
                        return ExecutionResult(
                            success=False,
                            message="⚠️ 配置备份失败，为安全起见取消执行。请检查设备连接和权限。"
                        )
                
                # 过滤被拦截的命令
                if guard_result:
                    safe_commands = [
                        r.command for r in guard_result.results 
                        if r.is_allowed
                    ]
                else:
                    safe_commands = commands
                
                # 执行命令
                results = []
                for cmd in safe_commands:
                    try:
                        output = conn.execute_command(cmd)
                        results.append({"command": cmd, "output": output, "success": True})
                    except Exception as e:
                        results.append({"command": cmd, "output": str(e), "success": False})
                        # 命令执行失败，停止后续命令
                        break
                
                # 检查是否有失败的命令
                failed = [r for r in results if not r["success"]]
                if failed:
                    return ExecutionResult(
                        success=False,
                        message=f"执行到第 {len(results)} 条命令时失败：{failed[0]['output']}\n\n💾 已备份配置，可手动回滚。",
                        data={"results": results, "backup_available": backup_ok}
                    )
            
            return ExecutionResult(
                success=True,
                message=f"配置执行成功（{len(results)} 条命令）" + ("，已备份原配置" if backup_ok else ""),
                data={"results": results, "backup_available": backup_ok}
            )
        
        except Exception as e:
            return ExecutionResult(success=False, message=f"配置执行失败：{str(e)}")
    
    async def _execute_diagnosis(self, intent: ParsedIntent) -> ExecutionResult:
        """执行诊断工作流（基于 SSH）"""
        diagnosis_type = intent.intent_type
        params = intent.parameters
        
        if diagnosis_type == "diagnose_vlan":
            return await self._diagnose_vlan(params)
        elif diagnosis_type == "diagnose_routing":
            return await self._diagnose_routing(params)
        elif diagnosis_type == "diagnose_connectivity":
            return await self._diagnose_connectivity(params)
        else:
            return ExecutionResult(success=False, message=f"未知诊断类型：{diagnosis_type}")
    
    async def _diagnose_vlan(self, params: Dict[str, Any]) -> ExecutionResult:
        """VLAN 故障诊断（基于 SSH）"""
        vlan_id = params.get("vlan_id", 0)
        symptom = params.get("symptom", "")
        device_ip = params.get("device_ip", "")
        device_hostname = params.get("device_hostname", "")
        
        if not vlan_id:
            return ExecutionResult(success=False, message="未指定 VLAN ID")
        
        if not device_ip and not device_hostname:
            return ExecutionResult(
                success=False,
                message="诊断需要指定设备。用法：'VLAN 10 上不了网，查一下 SW-Core (IP: 192.168.1.1)'"
            )
        
        # 检查凭证
        if device_hostname and self.credential_manager:
            cred = self.credential_manager.get_credential(device_hostname)
        else:
            cred = None
        
        if not cred:
            # 需要用户提供凭证
            steps = ["检查 VLAN 是否创建", "检查接口是否加入 VLAN", "检查 Trunk 是否允许 VLAN", "检查 SVI 接口状态", "检查默认路由"]
            steps_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(steps)])
            return ExecutionResult(
                success=True,
                message=f"已生成 VLAN {vlan_id} 诊断计划，需要 SSH 凭证",
                requires_confirmation=True,
                confirmation_details=f"诊断目标：{device_hostname or device_ip}\nVLAN: {vlan_id}\n症状：{symptom}\n\n诊断步骤:\n{steps_text}\n\n请提供 SSH 凭证或使用 !save 命令保存凭证",
                data={"type": "vlan", "vlan_id": vlan_id, "symptom": symptom, "device": device_hostname, "device_ip": device_ip}
            )
        
        # 执行实际诊断
        return await self._run_diagnosis("vlan", params, device_ip or cred.ip, cred.username, cred.password)
    
    async def _diagnose_routing(self, params: Dict[str, Any]) -> ExecutionResult:
        """路由故障诊断（基于 SSH）"""
        source_ip = params.get("source_ip", "")
        dest_ip = params.get("dest_ip", "")
        symptom = params.get("symptom", "路由不通")
        device_ip = params.get("device_ip", "")
        device_hostname = params.get("device_hostname", "")
        
        if not source_ip or not dest_ip:
            return ExecutionResult(success=False, message="需要指定源 IP 和目标 IP")
        
        # 检查凭证
        if device_hostname and self.credential_manager:
            cred = self.credential_manager.get_credential(device_hostname)
        else:
            cred = None
        
        if not cred and not device_ip:
            steps = ["检查源设备路由表", "检查 OSPF/BGP 邻居状态", "检查静态路由配置", "检查目标设备路由表"]
            steps_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(steps)])
            return ExecutionResult(
                success=True,
                message=f"已生成路由诊断计划 ({source_ip} → {dest_ip})，需要 SSH 凭证",
                requires_confirmation=True,
                confirmation_details=f"诊断路径：{source_ip} → {dest_ip}\n症状：{symptom}\n\n诊断步骤:\n{steps_text}\n\n请提供 SSH 凭证",
                data={"type": "routing", "source_ip": source_ip, "dest_ip": dest_ip, "symptom": symptom}
            )
        
        # 执行实际诊断
        return await self._run_diagnosis("routing", params, device_ip or (cred.ip if cred else ""), 
                                         cred.username if cred else "", cred.password if cred else "")
    
    async def _diagnose_connectivity(self, params: Dict[str, Any]) -> ExecutionResult:
        """连通性故障诊断（基于 SSH）"""
        source_ip = params.get("source_ip", "")
        dest_ip = params.get("dest_ip", "")
        symptom = params.get("symptom", "ping 不通")
        
        if not source_ip or not dest_ip:
            return ExecutionResult(success=False, message="需要指定源 IP 和目标 IP")
        
        steps = [
            "检查源设备接口状态",
            "检查 ACL/防火墙规则",
            "检查 NAT 配置",
            "执行 ping 测试",
            "执行 traceroute 测试",
        ]
        
        diagnosis_plan = {
            "type": "connectivity",
            "source_ip": source_ip,
            "dest_ip": dest_ip,
            "symptom": symptom,
            "steps": steps,
        }
        
        steps_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(steps)])
        return ExecutionResult(
            success=True,
            message=f"已生成连通性诊断计划 ({source_ip} → {dest_ip})",
            requires_confirmation=True,
            confirmation_details=f"诊断路径：{source_ip} → {dest_ip}\n症状：{symptom}\n\n诊断步骤:\n{steps_text}\n\n请提供 SSH 凭证",
            data=diagnosis_plan
        )
    
    def _format_confirmation(self, device: str, device_ip: str, vendor: str, commands: List[str]) -> str:
        """格式化确认信息"""
        lines = [
            f"📌 设备：{device}",
            f"📍 IP: {device_ip}",
            f"🏷️ 厂商：{vendor}",
            "",
            f"📝 即将执行 {len(commands)} 条配置命令：",
            ""
        ]
        
        for i, cmd in enumerate(commands, 1):
            lines.append(f"  {i}. {cmd}")
        
        lines.append("")
        lines.append("配置将立即生效，请确认无误后执行")
        
        return "\n".join(lines)
    
    def _resolve_references(self, user_input: str, user_id: str) -> str:
        """
        解析用户输入中的引用（如"那台设备"、"那个VLAN"）
        
        Args:
            user_input: 用户输入
            user_id: 用户ID
        
        Returns:
            解析后的输入
        """
        resolved = user_input
        
        # 解析"那台设备"引用
        if "那台设备" in user_input or "那设备" in user_input or "刚才的设备" in user_input:
            device = self.session_manager.resolve_reference(user_id, "那台设备")
            if device:
                resolved = resolved.replace("那台设备", device).replace("那设备", device).replace("刚才的设备", device)
        
        # 解析"那个VLAN"引用
        if "那个VLAN" in user_input or "那个vlan" in user_input or "刚才的VLAN" in user_input:
            vlan = self.session_manager.resolve_reference(user_id, "那个VLAN")
            if vlan:
                resolved = resolved.replace("那个VLAN", f"VLAN {vlan}").replace("那个vlan", f"VLAN {vlan}").replace("刚才的VLAN", f"VLAN {vlan}")
        
        # 解析"那个接口"引用
        if "那个接口" in user_input or "刚才的接口" in user_input:
            interface = self.session_manager.resolve_reference(user_id, "那个接口")
            if interface:
                resolved = resolved.replace("那个接口", interface).replace("刚才的接口", interface)
        
        # 解析"再查一下"等模糊引用
        if "再查一下" in user_input or "再看看" in user_input:
            # 获取最近操作的设备
            session = self.session_manager.get_session(user_id, create_if_not_exists=False)
            if session and session.last_device:
                # 在输入前添加设备上下文
                if "再查一下" in user_input:
                    resolved = user_input.replace("再查一下", f"查一下 {session.last_device}")
                elif "再看看" in user_input:
                    resolved = user_input.replace("再看看", f"看看 {session.last_device}")
        
        return resolved


# Alias for backwards compatibility
NaturalLanguageExecutor = NLExecutor
