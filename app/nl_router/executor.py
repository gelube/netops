"""
自然语言执行器 - 纯 SSH 模式
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.nl_router.parser import ParsedIntent, IntentParser


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
    
    def __init__(self, llm_client=None, credential_manager=None):
        """
        初始化
        
        Args:
            llm_client: LLM 客户端
            credential_manager: 凭证管理器（可选）
        """
        self.llm_client = llm_client
        self.credential_manager = credential_manager
        self.intent_parser = IntentParser(llm_client) if llm_client else None
    
    async def execute(self, user_input: str) -> ExecutionResult:
        """
        执行用户自然语言请求
        """
        if not self.intent_parser:
            return ExecutionResult(
                success=False,
                message="LLM 客户端未初始化，无法解析意图"
            )
        
        intent = await self.intent_parser.parse(user_input)
        
        if intent.requires_ssh:
            return await self._execute_ssh_config(intent)
        elif intent.intent_type.startswith("query_"):
            return await self._execute_query(intent)
        elif intent.intent_type.startswith("diagnose_"):
            return await self._execute_diagnosis(intent)
        else:
            return ExecutionResult(
                success=False,
                message=f"未知意图类型：{intent.intent_type}"
            )
    
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
        
        commands = await self.intent_parser.generate_config_commands(
            intent=intent,
            vendor=vendor.value,
            device_hostname=device_hostname or "device"
        )
        
        if not commands:
            return ExecutionResult(success=False, message="未能生成配置命令")
        
        confirmation_details = self._format_confirmation(
            device_hostname or "device", device_ip, vendor.value, commands
        )
        
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
            }
        )
    
    async def confirm_and_execute(
        self, 
        confirmed: bool, 
        device_data: Dict[str, Any],
        username: str, 
        password: str,
    ) -> ExecutionResult:
        """用户确认后执行配置"""
        if not confirmed:
            return ExecutionResult(success=False, message="用户取消配置")
        
        device_ip = device_data.get("device_ip", "")
        commands = device_data.get("commands", [])
        
        if not device_ip or not commands:
            return ExecutionResult(success=False, message="设备数据不完整")
        
        from app.network.ssh import test_connection, DeviceConnection, ConnectionInfo
        
        if not test_connection(device_ip):
            return ExecutionResult(success=False, message=f"无法连接到设备 {device_ip}")
        
        try:
            conn_info = ConnectionInfo(ip=device_ip, username=username, password=password)
            
            with DeviceConnection(conn_info) as conn:
                results = []
                for cmd in commands:
                    output = conn.execute_command(cmd)
                    results.append({"command": cmd, "output": output})
            
            return ExecutionResult(success=True, message="配置执行成功", data={"results": results})
        
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
        
        steps = [
            "检查 VLAN 是否创建",
            "检查接口是否加入 VLAN",
            "检查 Trunk 是否允许 VLAN",
            "检查 SVI 接口状态",
            "检查默认路由",
        ]
        
        diagnosis_plan = {
            "type": "vlan",
            "vlan_id": vlan_id,
            "symptom": symptom,
            "device": device_hostname,
            "device_ip": device_ip,
            "steps": steps,
        }
        
        steps_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(steps)])
        return ExecutionResult(
            success=True,
            message=f"已生成 VLAN {vlan_id} 诊断计划，需要 SSH 凭证",
            requires_confirmation=True,
            confirmation_details=f"诊断目标：{device_hostname or device_ip}\nVLAN: {vlan_id}\n症状：{symptom}\n\n诊断步骤:\n{steps_text}\n\n请提供 SSH 凭证或使用 !save 命令保存凭证",
            data=diagnosis_plan
        )
    
    async def _diagnose_routing(self, params: Dict[str, Any]) -> ExecutionResult:
        """路由故障诊断（基于 SSH）"""
        source_ip = params.get("source_ip", "")
        dest_ip = params.get("dest_ip", "")
        symptom = params.get("symptom", "路由不通")
        
        if not source_ip or not dest_ip:
            return ExecutionResult(success=False, message="需要指定源 IP 和目标 IP")
        
        steps = [
            "检查源设备路由表",
            "检查 OSPF/BGP 邻居状态",
            "检查静态路由配置",
            "检查目标设备路由表",
        ]
        
        diagnosis_plan = {
            "type": "routing",
            "source_ip": source_ip,
            "dest_ip": dest_ip,
            "symptom": symptom,
            "steps": steps,
        }
        
        steps_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(steps)])
        return ExecutionResult(
            success=True,
            message=f"已生成路由诊断计划 ({source_ip} → {dest_ip})",
            requires_confirmation=True,
            confirmation_details=f"诊断路径：{source_ip} → {dest_ip}\n症状：{symptom}\n\n诊断步骤:\n{steps_text}\n\n请提供 SSH 凭证",
            data=diagnosis_plan
        )
    
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
        lines.append("⚠️  配置将立即生效，请确认无误后执行")
        
        return "\n".join(lines)
