#!/usr/bin/env python3
"""
路由诊断检查器
"""
import re
from typing import Optional
from app.diagnosis.base import BaseChecker, DiagnosisResult, CheckStatus

from app.logger import get_logger

log = get_logger(__name__)


class RoutingChecker(BaseChecker):
    """路由故障诊断"""

    def __init__(self, ssh_connection=None, llm_client=None):
        super().__init__(ssh_connection)
        self.llm = llm_client

    def diagnose(self, source_ip: str = "", dest_ip: str = "",
                      symptom: str = "", **kwargs) -> DiagnosisResult:
        """
        执行路由诊断

        Args:
            source_ip: 源IP
            dest_ip: 目标IP
            symptom: 故障现象
        """
        self.results = []

        if not self.conn:
            return DiagnosisResult(
                success=False,
                root_cause="SSH连接未建立"
            )

        # 步骤1: 检查路由表
        self._check_routing_table(dest_ip)

        # 步骤2: 检查动态路由协议
        self._check_dynamic_routing()

        # 步骤3: 检查默认路由
        self._check_default_route()

        # 步骤4: 执行traceroute测试
        self._check_traceroute(dest_ip) if dest_ip else None

        # 步骤5: LLM分析
        if self.llm:
            analysis = self._llm_analysis(source_ip, dest_ip, symptom)
        else:
            analysis = None

        # 生成结果
        root_cause, suggestions = self._generate_result(analysis)

        return DiagnosisResult(
            success=all(r.status == CheckStatus.PASS for r in self.results),
            root_cause=root_cause,
            suggestions=suggestions,
            steps=self.results
        )

    def _check_routing_table(self, dest_ip: str) -> bool:
        """检查路由表"""
        try:
            # 获取路由表
            if self._is_huawei():
                output = self.execute_command("display ip routing-table")
            else:
                output = self.execute_command("show ip route")

            # 检查是否有目标路由
            if dest_ip and dest_ip in output:
                self.add_result(
                    step="检查路由表",
                    status=CheckStatus.PASS,
                    message=f"找到到 {dest_ip} 的路由",
                    details={"dest": dest_ip}
                )
                return True
            elif dest_ip:
                # 检查默认路由
                if "0.0.0.0" in output:
                    self.add_result(
                        step="检查路由表",
                        status=CheckStatus.WARNING,
                        message=f"无到 {dest_ip} 的具体路由，但有默认路由"
                    )
                    return True
                else:
                    self.add_result(
                        step="检查路由表",
                        status=CheckStatus.FAIL,
                        message=f"无到 {dest_ip} 的路由",
                        suggestion=f"添加路由: ip route {dest_ip} <mask> <next-hop>"
                    )
                    return False
            else:
                self.add_result(
                    step="检查路由表",
                    status=CheckStatus.PASS,
                    message="路由表检查完成"
                )
                return True

        except Exception as e:
            self.add_result(
                step="检查路由表",
                status=CheckStatus.FAIL,
                message=f"检查失败: {str(e)}"
            )
            return False

    def _check_dynamic_routing(self) -> bool:
        """检查动态路由协议"""
        try:
            results = []

            # 检查OSPF
            if self._is_huawei():
                ospf_output = self.execute_command("display ospf peer")
            else:
                ospf_output = self.execute_command("show ip ospf neighbor")

            if "Full" in ospf_output or "DR" in ospf_output:
                self.add_result(
                    step="检查OSPF",
                    status=CheckStatus.PASS,
                    message="OSPF邻居正常"
                )
                results.append(True)
            elif "OSPF not enabled" in ospf_output or "not running" in ospf_output.lower():
                self.add_result(
                    step="检查OSPF",
                    status=CheckStatus.SKIP,
                    message="OSPF未启用"
                )
                results.append(True)
            else:
                self.add_result(
                    step="检查OSPF",
                    status=CheckStatus.WARNING,
                    message="OSPF状态异常",
                    suggestion="检查OSPF配置和邻居状态"
                )
                results.append(False)

            # 检查BGP
            if self._is_huawei():
                bgp_output = self.execute_command("display bgp peer")
            else:
                bgp_output = self.execute_command("show ip bgp summary")

            if "Established" in bgp_output:
                self.add_result(
                    step="检查BGP",
                    status=CheckStatus.PASS,
                    message="BGP邻居正常"
                )
                results.append(True)
            elif "BGP not enabled" in bgp_output or "not running" in bgp_output.lower():
                self.add_result(
                    step="检查BGP",
                    status=CheckStatus.SKIP,
                    message="BGP未启用"
                )
                results.append(True)
            else:
                self.add_result(
                    step="检查BGP",
                    status=CheckStatus.WARNING,
                    message="BGP状态异常",
                    suggestion="检查BGP配置和邻居状态"
                )
                results.append(False)

            return all(results)

        except Exception as e:
            self.add_result(
                step="检查动态路由",
                status=CheckStatus.SKIP,
                message=f"跳过动态路由检查: {str(e)}"
            )
            return True

    def _check_default_route(self) -> bool:
        """检查默认路由"""
        try:
            if self._is_huawei():
                output = self.execute_command("display ip routing-table | include 0.0.0.0")
            else:
                output = self.execute_command("show ip route 0.0.0.0")

            if "0.0.0.0" in output:
                self.add_result(
                    step="检查默认路由",
                    status=CheckStatus.PASS,
                    message="存在默认路由"
                )
                return True
            else:
                self.add_result(
                    step="检查默认路由",
                    status=CheckStatus.WARNING,
                    message="未配置默认路由",
                    suggestion="配置默认路由: ip route 0.0.0.0 0.0.0.0 <next-hop>"
                )
                return False

        except Exception as e:
            self.add_result(
                step="检查默认路由",
                status=CheckStatus.SKIP,
                message=f"跳过默认路由检查: {str(e)}"
            )
            return True

    def _check_traceroute(self, dest_ip: str) -> bool:
        """执行traceroute测试"""
        try:
            if self._is_huawei():
                output = self.execute_command(f"tracert {dest_ip}", timeout=60)
            else:
                output = self.execute_command(f"traceroute {dest_ip}", timeout=60)

            # 分析traceroute结果
            if "* *" in output or "timeout" in output.lower():
                # 找到中断点
                lines = output.split('\n')
                last_hop = None
                for line in lines:
                    if re.search(r'\d+\s+\d+\.\d+\.\d+\.\d+', line):
                        last_hop = line

                self.add_result(
                    step="Traceroute测试",
                    status=CheckStatus.FAIL,
                    message=f"到 {dest_ip} 的路径中断",
                    details={"last_hop": last_hop},
                    suggestion=f"检查路径上的设备: {last_hop}"
                )
                return False
            else:
                self.add_result(
                    step="Traceroute测试",
                    status=CheckStatus.PASS,
                    message=f"到 {dest_ip} 的路径正常"
                )
                return True

        except Exception as e:
            self.add_result(
                step="Traceroute测试",
                status=CheckStatus.SKIP,
                message=f"跳过Traceroute: {str(e)}"
            )
            return True

    def _llm_analysis(self, source_ip: str, dest_ip: str, symptom: str) -> Optional[str]:
        """LLM分析"""
        try:
            context = f"""
源IP: {source_ip}
目标IP: {dest_ip}
故障现象: {symptom}
检查结果:
{chr(10).join([f"- {r.step}: {r.message}" for r in self.results])}
"""
            return self.analyze_with_llm(
                self.llm,
                context,
                "路由故障的根因是什么？如何修复？"
            )
        except Exception:
            return None

    def _generate_result(self, llm_analysis: str) -> tuple:
        """生成诊断结果"""
        failed = [r for r in self.results if r.status == CheckStatus.FAIL]

        if not failed:
            return None, ["路由配置正常"]

        root_cause = failed[0].message
        suggestions = [r.suggestion for r in failed if r.suggestion]

        if llm_analysis:
            suggestions.append(f"\n智能分析:\n{llm_analysis}")

        return root_cause, suggestions

    def _is_huawei(self) -> bool:
        if not self.conn:
            return True
        return self.conn.vendor.name in ["HUAWEI", "H3C"]
