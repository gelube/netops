#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断引擎 - 协调各种诊断检查器
"""
from typing import Dict, Any, Optional
from datetime import datetime
from app.diagnosis.base import DiagnosisResult
from app.diagnosis.vlan_checker import VLANChecker
from app.diagnosis.routing_checker import RoutingChecker
from app.diagnosis.connectivity_checker import ConnectivityChecker
from app.diagnosis.stp_checker import STPChecker
from app.diagnosis.interface_checker import InterfaceChecker
from app.diagnosis.knowledge_base import KnowledgeBase, DiagnosisCase
from app.core.device import Vendor

try:
    from web.ws_push import ProgressPusher
except ImportError:
    ProgressPusher = None


class DiagnosisEngine:
    """诊断引擎"""
    
    def __init__(self, llm_client=None, credential_manager=None):
        """
        初始化诊断引擎
        
        Args:
            llm_client: LLM客户端（用于智能分析）
            credential_manager: 凭证管理器
        """
        self.llm_client = llm_client
        self.credential_manager = credential_manager
        self.knowledge_base = KnowledgeBase()
        self.pusher = ProgressPusher() if ProgressPusher else None
    
    async def diagnose(self, diagnosis_type: str, params: Dict[str, Any], 
                       ssh_connection=None) -> DiagnosisResult:
        """
        执行诊断
        
        Args:
            diagnosis_type: 诊断类型（vlan/routing/connectivity）
            params: 诊断参数
            ssh_connection: SSH连接对象
        
        Returns:
            DiagnosisResult
        """
        # 提取问题描述（用于知识库搜索）
        problem = params.get("symptom", diagnosis_type)

        # 推送开始
        if self.pusher:
            self.pusher.push_notification('info', f'开始{diagnosis_type}诊断...')

        # 1. 先搜索相似案例
        similar_cases = self.knowledge_base.search_similar(problem)
        if similar_cases:
            print(f"\n📚 找到 {len(similar_cases)} 个相似案例:")
            for i, case in enumerate(similar_cases[:3], 1):
                print(f"  {i}. {case.problem}")
                print(f"     根因: {case.root_cause}")
        
        # 2. 执行诊断（原有逻辑）
        if diagnosis_type == "vlan":
            checker = VLANChecker(ssh_connection, self.llm_client)
            result = await checker.diagnose(**params)
        
        elif diagnosis_type == "routing":
            checker = RoutingChecker(ssh_connection, self.llm_client)
            result = await checker.diagnose(**params)
        
        elif diagnosis_type == "connectivity":
            checker = ConnectivityChecker(ssh_connection, self.llm_client)
            result = await checker.diagnose(**params)
        
        elif diagnosis_type == "stp":
            checker = STPChecker(ssh_connection, self.llm_client)
            result = await checker.diagnose(**params)
        
        elif diagnosis_type == "interface":
            checker = InterfaceChecker(ssh_connection, self.llm_client)
            result = await checker.diagnose(**params)
        
        else:
            result = DiagnosisResult(
                success=False,
                root_cause=f"未知诊断类型：{diagnosis_type}"
            )
        
        # 3. 保存新案例
        if result.root_cause:
            # 推送诊断完成
            if self.pusher:
                self.pusher.push_diagnosis_complete(
                    result.root_cause, result.suggestions or [], result.success
                )
            # 获取设备类型（从 SSH 连接或默认值）
            device_type = "unknown"
            if ssh_connection and hasattr(ssh_connection, 'device_type'):
                device_type = ssh_connection.device_type
            
            case = DiagnosisCase(
                id=f"{datetime.now().strftime('%Y%m%d%H%M%S')}",
                problem=problem,
                symptoms=[r.message for r in result.steps] if result.steps else [],
                root_cause=result.root_cause,
                solution=result.suggestions[0] if result.suggestions else "",
                device_type=device_type,
                timestamp=datetime.now().isoformat(),
                success=result.success,
                tags=[diagnosis_type],
            )
            self.knowledge_base.save_case(case)
        
        return result
    
    async def quick_diagnose(self, symptom: str, device_ip: str, 
                            username: str, password: str) -> DiagnosisResult:
        """
        快速诊断（自动判断类型）
        
        Args:
            symptom: 故障现象（自然语言描述）
            device_ip: 设备IP
            username: SSH用户名
            password: SSH密码
        
        Returns:
            DiagnosisResult
        """
        # 使用LLM分析症状，判断诊断类型
        if not self.llm_client:
            return DiagnosisResult(
                success=False,
                root_cause="LLM客户端未初始化"
            )
        
        # 分析症状
        analysis = self._analyze_symptom(symptom)
        
        # 连接设备
        from app.network.ssh import DeviceConnection, ConnectionInfo
        conn_info = ConnectionInfo(
            ip=device_ip,
            username=username,
            password=password
        )
        
        try:
            with DeviceConnection(conn_info) as conn:
                # 执行诊断
                result = await self.diagnose(
                    diagnosis_type=analysis["type"],
                    params=analysis["params"],
                    ssh_connection=conn
                )
                return result
        
        except Exception as e:
            return DiagnosisResult(
                success=False,
                root_cause=f"设备连接失败：{str(e)}"
            )
    
    def _analyze_symptom(self, symptom: str) -> Dict[str, Any]:
        """分析症状，判断诊断类型"""
        symptom_lower = symptom.lower()
        
        # VLAN相关关键词
        vlan_keywords = ["vlan", "部门", "网段", "不能上网", "上不了网", "局域网"]
        # 路由相关关键词
        routing_keywords = ["路由", "ospf", "bgp", "路由器", "网关", "ping不通"]
        # 连通性相关关键词
        connectivity_keywords = ["ping", "连通", "访问", "连接", "丢包", "延迟", "不通"]
        # STP/环路关键词
        stp_keywords = ["stp", "环路", "广播风暴", "生成树", "拓扑变更", "mac地址漂移"]
        # 接口关键词
        interface_keywords = ["接口", "端口", "interface", "down", "up/down", "crc", "错包"]

        if any(kw in symptom_lower for kw in stp_keywords):
            return {"type": "stp", "params": {"symptom": symptom}}
        elif any(kw in symptom_lower for kw in interface_keywords):
            return {"type": "interface", "params": {"symptom": symptom}}
        elif any(kw in symptom_lower for kw in vlan_keywords):
            return {"type": "vlan", "params": {"symptom": symptom}}
        elif any(kw in symptom_lower for kw in routing_keywords):
            return {"type": "routing", "params": {"symptom": symptom}}
        elif any(kw in symptom_lower for kw in connectivity_keywords):
            return {"type": "connectivity", "params": {"symptom": symptom}}
        else:
            return {"type": "connectivity", "params": {"symptom": symptom}}
