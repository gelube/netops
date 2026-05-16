#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接口诊断检查器 — 检查物理接口状态、错误计数、双工/速率协商
"""
import re
from typing import Optional
from app.diagnosis.base import BaseChecker, DiagnosisResult, CheckStatus


class InterfaceChecker(BaseChecker):
    """接口故障诊断"""

    def __init__(self, ssh_connection=None, llm_client=None):
        super().__init__(ssh_connection)
        self.llm = llm_client

    async def diagnose(self, interface: str = "", symptom: str = "", **kwargs) -> DiagnosisResult:
        """
        执行接口诊断

        Args:
            interface: 接口名（如 GE0/0/1），空=检查所有
            symptom: 故障现象
        """
        self.results = []

        if not self.conn:
            return DiagnosisResult(success=False, root_cause="SSH连接未建立")

        # 步骤1: 检查接口状态
        self._check_interface_status(interface)

        # 步骤2: 检查错误计数
        self._check_error_counters(interface)

        # 步骤3: 检查双工/速率协商
        self._check_duplex_speed(interface)

        # 步骤4: 检查流量统计
        self._check_traffic(interface)

        # LLM分析
        analysis = None
        if self.llm:
            analysis = self._llm_analysis(interface, symptom)

        root_cause, suggestions = self._generate_result(analysis)

        return DiagnosisResult(
            success=all(r.status == CheckStatus.PASS for r in self.results),
            root_cause=root_cause,
            suggestions=suggestions,
            steps=self.results,
        )

    def _check_interface_status(self, interface: str) -> bool:
        """检查接口up/down状态"""
        try:
            if self._is_huawei():
                if interface:
                    output = self.execute_command(f"display interface {interface}")
                else:
                    output = self.execute_command("display interface brief")
            else:
                if interface:
                    output = self.execute_command(f"show interface {interface}")
                else:
                    output = self.execute_command("show ip interface brief")

            down_interfaces = []
            up_interfaces = []

            for line in output.split('\n'):
                # 华为: GE0/0/1  up  up
                # 思科: Gi0/1    up  up
                port_match = re.search(r'((?:GE|XGE|Gi|Te|Fa|Eth)\S+)', line)
                if port_match:
                    port = port_match.group(1)
                    line_lower = line.lower()
                    # 检查物理层和管理层状态
                    phys_down = bool(re.search(r'\bdown\b', line_lower.split(port, 1)[1].split()[0:2]))
                    admin_down = 'administratively' in line_lower

                    if admin_down:
                        down_interfaces.append((port, 'admin-down'))
                    elif phys_down:
                        down_interfaces.append((port, 'phys-down'))
                    else:
                        up_interfaces.append(port)

            if not interface:
                if down_interfaces:
                    self.add_result(
                        step="检查接口状态",
                        status=CheckStatus.WARNING,
                        message=f"{len(down_interfaces)} 个接口Down: {', '.join([f'{p}({s})' for p, s in down_interfaces[:5]])}",
                        details={"down": down_interfaces, "up_count": len(up_interfaces)},
                        suggestion="检查物理连接和接口配置",
                    )
                else:
                    self.add_result(
                        step="检查接口状态",
                        status=CheckStatus.PASS,
                        message=f"所有 {len(up_interfaces)} 个接口UP",
                    )
            else:
                if down_interfaces:
                    port, reason = down_interfaces[0]
                    self.add_result(
                        step=f"检查接口 {interface} 状态",
                        status=CheckStatus.FAIL,
                        message=f"接口 {interface} 状态: {reason}",
                        suggestion="检查物理连接、对端设备、接口shutdown配置",
                    )
                else:
                    self.add_result(
                        step=f"检查接口 {interface} 状态",
                        status=CheckStatus.PASS,
                        message=f"接口 {interface} 状态UP",
                    )
            return True
        except Exception as e:
            self.add_result(step="检查接口状态", status=CheckStatus.FAIL, message=f"检查失败: {e}")
            return False

    def _check_error_counters(self, interface: str) -> bool:
        """检查错误计数（CRC、丢包等）"""
        try:
            if self._is_huawei():
                cmd = f"display interface {interface}" if interface else "display interface brief"
            else:
                cmd = f"show interface {interface}" if interface else "show interfaces summary"

            output = self.execute_command(cmd)

            errors = {}

            # CRC错误
            crc_match = re.search(r'CRC[:\s]+(\d+)', output, re.IGNORECASE)
            if crc_match and int(crc_match.group(1)) > 0:
                errors['CRC'] = int(crc_match.group(1))

            # 输入错误
            in_err = re.search(r'(?:input errors|Input Errors)[:\s]+(\d+)', output, re.IGNORECASE)
            if in_err and int(in_err.group(1)) > 0:
                errors['input_errors'] = int(in_err.group(1))

            # 输出错误
            out_err = re.search(r'(?:output errors|Output Errors)[:\s]+(\d+)', output, re.IGNORECASE)
            if out_err and int(out_err.group(1)) > 0:
                errors['output_errors'] = int(out_err.group(1))

            # 丢弃
            discard = re.search(r'(?:discard|drops|Drop)[:\s]+(\d+)', output, re.IGNORECASE)
            if discard and int(discard.group(1)) > 0:
                errors['discards'] = int(discard.group(1))

            if errors:
                total = sum(errors.values())
                if total > 1000:
                    self.add_result(
                        step="检查错误计数",
                        status=CheckStatus.FAIL,
                        message=f"错误计数高: {errors}",
                        details=errors,
                        suggestion="检查线缆质量、双工协商、光模块状态",
                    )
                else:
                    self.add_result(
                        step="检查错误计数",
                        status=CheckStatus.WARNING,
                        message=f"有错误计数: {errors}",
                        details=errors,
                        suggestion="持续观察错误计数是否增长",
                    )
            else:
                self.add_result(
                    step="检查错误计数",
                    status=CheckStatus.PASS,
                    message="无错误计数",
                )
            return True
        except Exception as e:
            self.add_result(step="检查错误计数", status=CheckStatus.SKIP, message=f"跳过: {e}")
            return True

    def _check_duplex_speed(self, interface: str) -> bool:
        """检查双工/速率协商"""
        try:
            if self._is_huawei():
                cmd = f"display interface {interface}" if interface else "display interface brief"
            else:
                cmd = f"show interface {interface}" if interface else "show interfaces status"

            output = self.execute_command(cmd)

            half_duplex = []
            speed_mismatch = []

            for line in output.split('\n'):
                # 检测半双工
                if 'half' in line.lower() and 'duplex' in line.lower():
                    port_match = re.search(r'((?:GE|XGE|Gi|Te|Fa)\S+)', line)
                    if port_match:
                        half_duplex.append(port_match.group(1))

                # 检测速率协商
                speed_match = re.search(r'(\d+)(?:Mbps|Gbps)', line, re.IGNORECASE)
                if speed_match:
                    port_match = re.search(r'((?:GE|XGE|Gi|Te|Fa)\S+)', line)
                    if port_match:
                        speed = int(speed_match.group(1))
                        # 千兆口跑百兆 = 协商异常
                        if port_match.group(1).startswith('GE') and speed == 100:
                            speed_mismatch.append((port_match.group(1), speed))

            if half_duplex:
                self.add_result(
                    step="检查双工协商",
                    status=CheckStatus.WARNING,
                    message=f"半双工接口: {', '.join(half_duplex[:5])}",
                    suggestion="两端配置相同的双工模式: duplex full",
                )
            elif speed_mismatch:
                self.add_result(
                    step="检查速率协商",
                    status=CheckStatus.WARNING,
                    message=f"速率协商异常: {speed_mismatch[:3]}",
                    suggestion="检查对端速率配置，或强制协商: speed 1000",
                )
            else:
                self.add_result(
                    step="检查双工/速率",
                    status=CheckStatus.PASS,
                    message="双工和速率协商正常",
                )
            return True
        except Exception as e:
            self.add_result(step="检查双工/速率", status=CheckStatus.SKIP, message=f"跳过: {e}")
            return True

    def _check_traffic(self, interface: str) -> bool:
        """检查流量统计"""
        try:
            if self._is_huawei():
                cmd = f"display interface {interface}" if interface else "display interface brief"
            else:
                cmd = f"show interface {interface}" if interface else "show interfaces"

            output = self.execute_command(cmd)

            # 提取流量信息
            in_rate = re.search(r'(?:Input|input|In)\s+(?:rate|bandwidth)[:\s]+(\d+)', output, re.IGNORECASE)
            out_rate = re.search(r'(?:Output|output|Out)\s+(?:rate|bandwidth)[:\s]+(\d+)', output, re.IGNORECASE)

            in_bytes = re.search(r'(?:bytes|Bytes)[:\s]+(\d+)', output)

            details = {}
            if in_rate:
                details['input_rate'] = int(in_rate.group(1))
            if out_rate:
                details['output_rate'] = int(out_rate.group(1))

            if details:
                self.add_result(
                    step="检查流量",
                    status=CheckStatus.PASS,
                    message=f"流量统计: {details}",
                    details=details,
                )
            else:
                self.add_result(
                    step="检查流量",
                    status=CheckStatus.PASS,
                    message="流量统计已检查",
                )
            return True
        except Exception as e:
            self.add_result(step="检查流量", status=CheckStatus.SKIP, message=f"跳过: {e}")
            return True

    def _llm_analysis(self, interface: str, symptom: str) -> Optional[str]:
        try:
            context = f"""
接口: {interface or '全部'}
现象: {symptom}
检查结果:
{chr(10).join([f"- {r.step}: {r.message}" for r in self.results])}
"""
            return self.analyze_with_llm(self.llm, context, "接口故障的根因是什么？如何修复？")
        except:
            return None

    def _generate_result(self, llm_analysis: str) -> tuple:
        failed = [r for r in self.results if r.status == CheckStatus.FAIL]
        if not failed:
            warnings = [r for r in self.results if r.status == CheckStatus.WARNING]
            if warnings:
                return warnings[0].message, [r.suggestion for r in warnings if r.suggestion]
            return None, ["接口状态正常"]
        root_cause = failed[0].message
        suggestions = [r.suggestion for r in failed if r.suggestion]
        if llm_analysis:
            suggestions.append(f"\n智能分析:\n{llm_analysis}")
        return root_cause, suggestions

    def _is_huawei(self) -> bool:
        if not self.conn:
            return True
        return self.conn.vendor.name in ["HUAWEI", "H3C"]
