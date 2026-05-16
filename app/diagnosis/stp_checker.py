#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STP/环路诊断检查器
"""
import re
from typing import Optional
from app.diagnosis.base import BaseChecker, DiagnosisResult, CheckStatus


class STPChecker(BaseChecker):
    """STP/环路故障诊断"""

    def __init__(self, ssh_connection=None, llm_client=None):
        super().__init__(ssh_connection)
        self.llm = llm_client

    def diagnose(self, vlan_id: int = 0, symptom: str = "", **kwargs) -> DiagnosisResult:
        """
        执行STP诊断

        Args:
            vlan_id: 检查的VLAN（0=所有）
            symptom: 故障现象（如"广播风暴"、"环路"）
        """
        self.results = []

        if not self.conn:
            return DiagnosisResult(success=False, root_cause="SSH连接未建立")

        # 步骤1: 检查STP是否启用
        stp_enabled = self._check_stp_enabled()

        # 步骤2: 检查STP根桥
        root_bridge = self._check_root_bridge(vlan_id)

        # 步骤3: 检查阻塞端口
        blocked_ports = self._check_blocked_ports(vlan_id)

        # 步骤4: 检查TCN（拓扑变更）
        tcn_status = self._check_tcn(vlan_id)

        # 步骤5: 检查端口状态异常
        port_anomaly = self._check_port_anomaly()

        # LLM分析
        analysis = None
        if self.llm:
            analysis = self._llm_analysis(vlan_id, symptom)

        root_cause, suggestions = self._generate_result(analysis)

        return DiagnosisResult(
            success=all(r.status == CheckStatus.PASS for r in self.results),
            root_cause=root_cause,
            suggestions=suggestions,
            steps=self.results,
        )

    def _check_stp_enabled(self) -> bool:
        """检查STP是否启用"""
        try:
            if self._is_huawei():
                output = self.execute_command("display stp")
            else:
                output = self.execute_command("show spanning-tree")

            if "disabled" in output.lower() or "not enabled" in output.lower():
                self.add_result(
                    step="检查STP启用状态",
                    status=CheckStatus.FAIL,
                    message="STP未启用！存在环路风险",
                    suggestion="启用STP: stp enable（华为）或 spanning-tree vlan all（思科）",
                )
                return False

            if "mstp" in output.lower():
                stp_mode = "MSTP"
            elif "rstp" in output.lower():
                stp_mode = "RSTP"
            elif "pvst" in output.lower():
                stp_mode = "PVST+"
            else:
                stp_mode = "STP"

            self.add_result(
                step="检查STP启用状态",
                status=CheckStatus.PASS,
                message=f"STP已启用，模式: {stp_mode}",
            )
            return True
        except Exception as e:
            self.add_result(
                step="检查STP启用状态",
                status=CheckStatus.WARNING,
                message=f"无法检查STP状态: {e}",
            )
            return True

    def _check_root_bridge(self, vlan_id: int) -> bool:
        """检查根桥是否合理"""
        try:
            if self._is_huawei():
                cmd = f"display stp vlan {vlan_id}" if vlan_id else "display stp"
                output = self.execute_command(cmd)
            else:
                cmd = f"show spanning-tree vlan {vlan_id}" if vlan_id else "show spanning-tree"
                output = self.execute_command(cmd)

            # 提取根桥信息
            root_match = re.search(
                r'(?:Root Bridge|根桥|Designated Root)[:\s]+([^\n,]+)',
                output, re.IGNORECASE,
            )
            root_info = root_match.group(1).strip() if root_match else "未知"

            # 提取本桥信息
            bridge_match = re.search(
                r'(?:Bridge ID|本桥|We are)[:\s]+([^\n,]+)',
                output, re.IGNORECASE,
            )
            bridge_info = bridge_match.group(1).strip() if bridge_match else "未知"

            is_root = "this bridge is root" in output.lower() or "本交换机为根桥" in output

            if is_root:
                self.add_result(
                    step="检查STP根桥",
                    status=CheckStatus.WARNING,
                    message=f"本设备为根桥 — 确认是否预期（核心交换机应为根桥）",
                    details={"root": root_info, "local": bridge_info},
                    suggestion="如果不是核心交换机，调整STP优先级: stp priority 4096",
                )
            else:
                self.add_result(
                    step="检查STP根桥",
                    status=CheckStatus.PASS,
                    message=f"根桥: {root_info}",
                    details={"root": root_info, "local": bridge_info},
                )
            return True
        except Exception as e:
            self.add_result(
                step="检查STP根桥",
                status=CheckStatus.SKIP,
                message=f"跳过根桥检查: {e}",
            )
            return True

    def _check_blocked_ports(self, vlan_id: int) -> bool:
        """检查阻塞端口"""
        try:
            if self._is_huawei():
                output = self.execute_command("display stp brief")
            else:
                output = self.execute_command("show spanning-tree brief")

            blocked = []
            forwarding = []

            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # 华为: GE0/0/1  ALTE  128.1  ...
                # 思科: Gi0/1    BLK    128.2  ...
                if re.search(r'(GE|XGE|Gi|Te|Fa)\S+', line):
                    port_match = re.search(r'(GE|XGE|Gi|Te|Fa)\S+', line)
                    if port_match:
                        port = port_match.group(0)
                        if 'ALTE' in line or 'BLK' in line or 'BLOCK' in line:
                            blocked.append(port)
                        elif 'FORW' in line or 'FWD' in line or 'FORWARD' in line:
                            forwarding.append(port)

            if blocked:
                self.add_result(
                    step="检查阻塞端口",
                    status=CheckStatus.WARNING,
                    message=f"STP阻塞了 {len(blocked)} 个端口: {', '.join(blocked[:5])}",
                    details={"blocked": blocked, "forwarding": forwarding},
                    suggestion="确认阻塞端口是否为预期行为（冗余链路正常会阻塞一个）",
                )
            else:
                self.add_result(
                    step="检查阻塞端口",
                    status=CheckStatus.PASS,
                    message=f"无阻塞端口，{len(forwarding)} 个端口转发中",
                )
            return True
        except Exception as e:
            self.add_result(
                step="检查阻塞端口",
                status=CheckStatus.SKIP,
                message=f"跳过阻塞端口检查: {e}",
            )
            return True

    def _check_tcn(self, vlan_id: int) -> bool:
        """检查拓扑变更通知（频繁TCN=环路或不稳定）"""
        try:
            if self._is_huawei():
                output = self.execute_command("display stp topology-change")
            else:
                output = self.execute_command("show spanning-tree detail")

            tcn_count = 0
            tcn_match = re.search(r'(\d+)\s*(?:times|次)', output, re.IGNORECASE)
            if tcn_match:
                tcn_count = int(tcn_match.group(1))

            # 也检查最近变更时间
            recent_match = re.search(r'Last\s+(?:topology change|变更)[:\s]+([^\n]+)', output, re.IGNORECASE)
            recent = recent_match.group(1).strip() if recent_match else "无记录"

            if tcn_count > 100:
                self.add_result(
                    step="检查拓扑变更",
                    status=CheckStatus.FAIL,
                    message=f"拓扑变更次数异常高: {tcn_count}次，可能存在环路或端口震荡",
                    details={"tcn_count": tcn_count, "last_change": recent},
                    suggestion="检查是否有环路、端口频繁up/down、或终端发送BPDU",
                )
            elif tcn_count > 10:
                self.add_result(
                    step="检查拓扑变更",
                    status=CheckStatus.WARNING,
                    message=f"拓扑变更次数较多: {tcn_count}次",
                    details={"tcn_count": tcn_count, "last_change": recent},
                    suggestion="检查端口稳定性，考虑启用bpdu-guard和portfast",
                )
            else:
                self.add_result(
                    step="检查拓扑变更",
                    status=CheckStatus.PASS,
                    message=f"拓扑变更次数正常: {tcn_count}次",
                    details={"tcn_count": tcn_count, "last_change": recent},
                )
            return True
        except Exception as e:
            self.add_result(
                step="检查拓扑变更",
                status=CheckStatus.SKIP,
                message=f"跳过TCN检查: {e}",
            )
            return True

    def _check_port_anomaly(self) -> bool:
        """检查端口异常（边缘端口未配bpdu-guard等）"""
        try:
            if self._is_huawei():
                output = self.execute_command("display stp brief")
            else:
                output = self.execute_command("show spanning-tree brief")

            anomalies = []

            # 检查边缘端口（接入端口应该配edge/portfast）
            edge_count = output.lower().count('edge') + output.lower().count('portfast')
            total_ports = len(re.findall(r'(GE|XGE|Gi|Te|Fa)\S+', output))

            if total_ports > 0 and edge_count == 0:
                anomalies.append("未发现边缘端口配置（接入端口建议启用edge/portfast）")

            if anomalies:
                self.add_result(
                    step="检查端口STP配置",
                    status=CheckStatus.WARNING,
                    message="; ".join(anomalies),
                    suggestion="接入端口启用 stp edged-port enable 和 stp bpdu-protection enable",
                )
            else:
                self.add_result(
                    step="检查端口STP配置",
                    status=CheckStatus.PASS,
                    message="STP端口配置正常",
                )
            return True
        except Exception as e:
            self.add_result(
                step="检查端口STP配置",
                status=CheckStatus.SKIP,
                message=f"跳过: {e}",
            )
            return True

    def _llm_analysis(self, vlan_id: int, symptom: str) -> Optional[str]:
        try:
            context = f"""
VLAN: {vlan_id or '全部'}
现象: {symptom}
检查结果:
{chr(10).join([f"- {r.step}: {r.message}" for r in self.results])}
"""
            return self.analyze_with_llm(self.llm, context, "STP/环路故障的根因是什么？")
        except:
            return None

    def _generate_result(self, llm_analysis: str) -> tuple:
        failed = [r for r in self.results if r.status == CheckStatus.FAIL]
        if not failed:
            warnings = [r for r in self.results if r.status == CheckStatus.WARNING]
            if warnings:
                return warnings[0].message, [r.suggestion for r in warnings if r.suggestion]
            return None, ["STP配置正常"]
        root_cause = failed[0].message
        suggestions = [r.suggestion for r in failed if r.suggestion]
        if llm_analysis:
            suggestions.append(f"\n智能分析:\n{llm_analysis}")
        return root_cause, suggestions

    def _is_huawei(self) -> bool:
        if not self.conn:
            return True
        return self.conn.vendor.name in ["HUAWEI", "H3C"]
