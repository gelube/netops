#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VLAN 诊断检查器
"""
import re
from typing import Dict, Any, Optional
from app.diagnosis.base import BaseChecker, DiagnosisResult, CheckStatus


class VLANChecker(BaseChecker):
    """VLAN故障诊断"""
    
    def __init__(self, ssh_connection=None, llm_client=None):
        super().__init__(ssh_connection)
        self.llm = llm_client
    
    def diagnose(self, vlan_id: int = 0, symptom: str = "", 
                      device_ip: str = "", **kwargs) -> DiagnosisResult:
        """
        执行VLAN诊断
        
        Args:
            vlan_id: VLAN ID
            symptom: 故障现象
            device_ip: 设备IP
        """
        self.results = []
        
        if not self.conn:
            return DiagnosisResult(
                success=False,
                root_cause="SSH连接未建立"
            )
        
        if not vlan_id:
            # 尝试从症状推断VLAN
            vlan_id = self._infer_vlan_from_symptom(symptom)
        
        # 步骤1: 检查VLAN是否存在
        vlan_exists = self._check_vlan_exists(vlan_id)
        
        # 步骤2: 检查接口状态
        interface_status = self._check_interface_status(vlan_id)
        
        # 步骤3: 检查SVI接口
        svi_status = self._check_svi_interface(vlan_id)
        
        # 步骤4: 检查Trunk配置
        trunk_status = self._check_trunk_config(vlan_id)
        
        # 步骤5: 使用LLM综合分析
        if self.llm:
            analysis = self._llm_analysis(vlan_id, symptom)
        else:
            analysis = None
        
        # 生成根因和建议
        root_cause, suggestions = self._generate_root_cause(vlan_id, analysis)
        
        return DiagnosisResult(
            success=all(r.status == CheckStatus.PASS for r in self.results),
            root_cause=root_cause,
            suggestions=suggestions,
            steps=self.results
        )
    
    def _infer_vlan_from_symptom(self, symptom: str) -> int:
        """从症状推断VLAN"""
        # 简单的映射（可以后续用LLM增强）
        mappings = {
            "财务": 10, "人事": 20, "技术": 30, "访客": 100, "监控": 200
        }
        
        for keyword, vlan_id in mappings.items():
            if keyword in symptom:
                return vlan_id
        
        # 尝试提取数字
        match = re.search(r'vlan\s*(\d+)', symptom, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return 0
    
    def _check_vlan_exists(self, vlan_id: int) -> bool:
        """检查VLAN是否创建"""
        try:
            # 获取VLAN信息
            output = self.execute_command("display vlan" if self._is_huawei() else "show vlan brief")
            
            if str(vlan_id) in output:
                self.add_result(
                    step="检查VLAN创建",
                    status=CheckStatus.PASS,
                    message=f"VLAN {vlan_id} 已创建",
                    details={"vlan_id": vlan_id}
                )
                return True
            else:
                self.add_result(
                    step="检查VLAN创建",
                    status=CheckStatus.FAIL,
                    message=f"VLAN {vlan_id} 不存在",
                    suggestion=f"创建VLAN: vlan {vlan_id}"
                )
                return False
        
        except Exception as e:
            self.add_result(
                step="检查VLAN创建",
                status=CheckStatus.FAIL,
                message=f"检查失败: {str(e)}"
            )
            return False
    
    def _check_interface_status(self, vlan_id: int) -> bool:
        """检查接口是否加入VLAN"""
        try:
            # 获取接口信息
            if self._is_huawei():
                output = self.execute_command(f"display vlan {vlan_id}")
            else:
                output = self.execute_command(f"show vlan id {vlan_id}")
            
            # 检查是否有接口
            interfaces = self._parse_interfaces_from_vlan(output)
            
            if interfaces:
                self.add_result(
                    step="检查接口状态",
                    status=CheckStatus.PASS,
                    message=f"VLAN {vlan_id} 包含接口: {', '.join(interfaces)}",
                    details={"interfaces": interfaces}
                )
                return True
            else:
                self.add_result(
                    step="检查接口状态",
                    status=CheckStatus.FAIL,
                    message=f"VLAN {vlan_id} 没有任何接口",
                    suggestion=f"将接口加入VLAN: interface X; port default vlan {vlan_id}"
                )
                return False
        
        except Exception as e:
            self.add_result(
                step="检查接口状态",
                status=CheckStatus.WARNING,
                message=f"检查失败: {str(e)}"
            )
            return False
    
    def _check_svi_interface(self, vlan_id: int) -> bool:
        """检查SVI接口（三层网关）"""
        try:
            # 检查Vlanif接口
            if self._is_huawei():
                output = self.execute_command(f"display interface Vlanif{vlan_id}")
            else:
                output = self.execute_command(f"show interface Vlan{vlan_id}")
            
            if "not exist" in output.lower() or "error" in output.lower():
                self.add_result(
                    step="检查SVI接口",
                    status=CheckStatus.WARNING,
                    message=f"VLAN {vlan_id} 没有三层接口（如果需要跨网段通信，需要创建SVI）",
                    suggestion=f"创建SVI: interface Vlanif{vlan_id}; ip address X.X.X.X"
                )
                return False
            
            # 检查状态
            if "up" in output.lower():
                self.add_result(
                    step="检查SVI接口",
                    status=CheckStatus.PASS,
                    message=f"Vlanif{vlan_id} 状态正常"
                )
                return True
            else:
                self.add_result(
                    step="检查SVI接口",
                    status=CheckStatus.FAIL,
                    message=f"Vlanif{vlan_id} 状态为down",
                    suggestion="检查VLAN内是否有UP的物理接口"
                )
                return False
        
        except Exception as e:
            self.add_result(
                step="检查SVI接口",
                status=CheckStatus.SKIP,
                message="跳过SVI检查（可能是二层交换机）"
            )
            return True
    
    def _check_trunk_config(self, vlan_id: int) -> bool:
        """检查Trunk是否允许VLAN"""
        try:
            # 获取Trunk接口
            if self._is_huawei():
                output = self.execute_command("display port vlan")
            else:
                output = self.execute_command("show interfaces trunk")
            
            # 检查Trunk是否允许该VLAN
            if str(vlan_id) in output or "all" in output.lower():
                self.add_result(
                    step="检查Trunk配置",
                    status=CheckStatus.PASS,
                    message=f"Trunk接口允许VLAN {vlan_id} 通过"
                )
                return True
            else:
                self.add_result(
                    step="检查Trunk配置",
                    status=CheckStatus.WARNING,
                    message=f"未找到允许VLAN {vlan_id} 的Trunk接口",
                    suggestion="检查上行Trunk接口配置"
                )
                return False
        
        except Exception as e:
            self.add_result(
                step="检查Trunk配置",
                status=CheckStatus.SKIP,
                message=f"跳过Trunk检查: {str(e)}"
            )
            return True
    
    def _llm_analysis(self, vlan_id: int, symptom: str) -> Optional[str]:
        """使用LLM分析"""
        try:
            context = f"""
VLAN ID: {vlan_id}
故障现象: {symptom}
检查结果:
{chr(10).join([f"- {r.step}: {r.message}" for r in self.results])}
"""
            analysis = self.analyze_with_llm(
                self.llm,
                context,
                f"VLAN {vlan_id} 故障的根因是什么？如何修复？"
            )
            return analysis
        except:
            return None
    
    def _generate_root_cause(self, vlan_id: int, llm_analysis: str) -> tuple:
        """生成根因和建议"""
        failed_checks = [r for r in self.results if r.status == CheckStatus.FAIL]
        
        if not failed_checks:
            return None, ["VLAN配置正常，请检查其他原因（如终端配置、IP地址冲突等）"]
        
        # 提取失败原因
        root_cause = failed_checks[0].message
        
        suggestions = []
        for check in failed_checks:
            if check.suggestion:
                suggestions.append(check.suggestion)
        
        # 添加LLM建议
        if llm_analysis:
            suggestions.append(f"\n智能分析:\n{llm_analysis}")
        
        return root_cause, suggestions
    
    def _is_huawei(self) -> bool:
        """判断是否华为设备"""
        if not self.conn:
            return True  # 默认华为
        return self.conn.vendor.name in ["HUAWEI", "H3C"]
    
    def _parse_interfaces_from_vlan(self, output: str) -> list:
        """从VLAN信息中解析接口"""
        interfaces = []
        # 简单匹配（华为/思科格式）
        for line in output.split('\n'):
            if re.search(r'GE\d+/\d+/\d+|GigabitEthernet\d+/\d+', line):
                match = re.search(r'(GE\d+/\d+/\d+|GigabitEthernet\d+/\d+)', line)
                if match:
                    interfaces.append(match.group(1))
        return interfaces
