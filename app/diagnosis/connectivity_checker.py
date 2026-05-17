#!/usr/bin/env python3
"""
连通性诊断检查器
"""
import re
from typing import Optional
from app.diagnosis.base import BaseChecker, DiagnosisResult, CheckStatus

from app.logger import get_logger

log = get_logger(__name__)


class ConnectivityChecker(BaseChecker):
    """连通性故障诊断"""

    def __init__(self, ssh_connection=None, llm_client=None):
        super().__init__(ssh_connection)
        self.llm = llm_client

    def diagnose(self, source_ip: str = "", dest_ip: str = "",
                      symptom: str = "", **kwargs) -> DiagnosisResult:
        """
        执行连通性诊断

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

        # 步骤1: 检查接口状态
        self._check_interface_status()

        # 步骤2: 检查ACL配置
        self._check_acl(dest_ip)

        # 步骤3: 检查NAT配置
        self._check_nat()

        # 步骤4: 执行Ping测试
        self._check_ping(dest_ip) if dest_ip else None

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

    def _check_interface_status(self) -> bool:
        """检查接口状态"""
        try:
            # 获取接口简要信息
            if self._is_huawei():
                output = self.execute_command("display interface brief")
            else:
                output = self.execute_command("show ip interface brief")

            # 统计UP/Down接口
            up_count = output.lower().count("up")
            down_count = output.lower().count("down")

            if up_count > 0:
                self.add_result(
                    step="检查接口状态",
                    status=CheckStatus.PASS,
                    message=f"接口状态正常 (UP: {up_count}, Down: {down_count})",
                    details={"up": up_count, "down": down_count}
                )
                return True
            else:
                self.add_result(
                    step="检查接口状态",
                    status=CheckStatus.FAIL,
                    message="没有UP的接口",
                    suggestion="检查物理连接和接口配置"
                )
                return False

        except Exception as e:
            self.add_result(
                step="检查接口状态",
                status=CheckStatus.FAIL,
                message=f"检查失败: {str(e)}"
            )
            return False

    def _check_acl(self, dest_ip: str) -> bool:
        """检查ACL配置"""
        try:
            # 获取ACL配置
            if self._is_huawei():
                output = self.execute_command("display acl all")
            else:
                output = self.execute_command("show access-lists")

            if not output or "no acl" in output.lower() or "no access-list" in output.lower():
                self.add_result(
                    step="检查ACL",
                    status=CheckStatus.PASS,
                    message="无ACL配置"
                )
                return True

            # 检查是否有deny规则阻止目标IP
            if dest_ip and dest_ip in output:
                # 检查上下文
                lines = output.split('\n')
                for i, line in enumerate(lines):
                    if dest_ip in line and "deny" in line.lower():
                        self.add_result(
                            step="检查ACL",
                            status=CheckStatus.FAIL,
                            message=f"ACL可能阻止了 {dest_ip}",
                            details={"acl_line": line},
                            suggestion=f"修改ACL规则允许 {dest_ip}"
                        )
                        return False

            self.add_result(
                step="检查ACL",
                status=CheckStatus.PASS,
                message="ACL配置正常"
            )
            return True

        except Exception as e:
            self.add_result(
                step="检查ACL",
                status=CheckStatus.SKIP,
                message=f"跳过ACL检查: {str(e)}"
            )
            return True

    def _check_nat(self) -> bool:
        """检查NAT配置"""
        try:
            if self._is_huawei():
                output = self.execute_command("display nat session all")
            else:
                output = self.execute_command("show ip nat translations")

            if "no session" in output.lower() or "no translation" in output.lower():
                self.add_result(
                    step="检查NAT",
                    status=CheckStatus.WARNING,
                    message="无NAT会话（可能是正常现象）"
                )
                return True

            if output.strip():
                self.add_result(
                    step="检查NAT",
                    status=CheckStatus.PASS,
                    message="NAT配置正常"
                )
                return True
            else:
                self.add_result(
                    step="检查NAT",
                    status=CheckStatus.SKIP,
                    message="跳过NAT检查"
                )
                return True

        except Exception as e:
            self.add_result(
                step="检查NAT",
                status=CheckStatus.SKIP,
                message=f"跳过NAT检查: {str(e)}"
            )
            return True

    def _check_ping(self, dest_ip: str) -> bool:
        """执行Ping测试"""
        try:
            if self._is_huawei():
                output = self.execute_command(f"ping {dest_ip}", timeout=30)
            else:
                output = self.execute_command(f"ping {dest_ip}", timeout=30)

            # 分析ping结果
            if "100% packet loss" in output or "0/5" in output:
                self.add_result(
                    step="Ping测试",
                    status=CheckStatus.FAIL,
                    message=f"Ping {dest_ip} 失败（100%丢包）",
                    suggestion=f"检查到 {dest_ip} 的路由和中间设备"
                )
                return False
            elif "packet loss" in output.lower() or "/" in output:
                # 部分丢包
                match = re.search(r'(\d+)%\s*packet\s*loss', output)
                loss_rate = match.group(1) if match else "unknown"

                self.add_result(
                    step="Ping测试",
                    status=CheckStatus.WARNING,
                    message=f"Ping {dest_ip} 部分丢包（{loss_rate}%）",
                    suggestion="检查链路质量和中间设备"
                )
                return True
            else:
                self.add_result(
                    step="Ping测试",
                    status=CheckStatus.PASS,
                    message=f"Ping {dest_ip} 正常"
                )
                return True

        except Exception as e:
            self.add_result(
                step="Ping测试",
                status=CheckStatus.SKIP,
                message=f"跳过Ping测试: {str(e)}"
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
                "连通性故障的根因是什么？如何修复？"
            )
        except Exception:
            return None

    def _generate_result(self, llm_analysis: str) -> tuple:
        """生成诊断结果"""
        failed = [r for r in self.results if r.status == CheckStatus.FAIL]

        if not failed:
            return None, ["连通性正常"]

        root_cause = failed[0].message
        suggestions = [r.suggestion for r in failed if r.suggestion]

        if llm_analysis:
            suggestions.append(f"\n智能分析:\n{llm_analysis}")

        return root_cause, suggestions

    def _is_huawei(self) -> bool:
        if not self.conn:
            return True
        return self.conn.vendor.name in ["HUAWEI", "H3C"]
