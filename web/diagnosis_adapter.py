#!/usr/bin/env python3
"""
Web 诊断适配器 - 让诊断引擎可以复用 netops_tools 的 SSH 连接
"""
from typing import Dict, Any


class WebSSHAdapter:
    """适配器：让 BaseChecker.execute_command() 走 netops_tools 而不是 app.network.ssh

    用法：
        adapter = WebSSHAdapter(device_name, vendor)
        checker = VLANChecker(ssh_connection=adapter)
        result = await checker.diagnose(vlan_id=10)
    """

    def __init__(self, device_name: str, vendor: str = 'unknown'):
        self.device_name = device_name
        self.device_type = vendor  # BaseChecker 可能读取
        self._last_output = ''

    def execute_command(self, command: str, timeout: int = 30) -> str:
        """执行命令，通过 netops_tools 公共接口"""
        import sys
        import os
        _web_dir = os.path.dirname(os.path.abspath(__file__))
        if _web_dir not in sys.path:
            sys.path.insert(0, _web_dir)
        from netops_tools import NetOpsTools
        tools = NetOpsTools()

        result = tools.execute_command_on_device(self.device_name, [command], skip_backup=True)

        if result.get('success') and result.get('results'):
            output = result['results'][0].get('output', '')
            self._last_output = output
            return output
        else:
            error = result.get('error', '未知错误')
            raise Exception(f"命令执行失败: {error}")


def run_diagnosis_sync(diagnosis_type: str, device_name: str, vendor: str = 'unknown',
                       vlan_id: int = 0, symptom: str = '') -> Dict[str, Any]:
    """同步执行诊断（Web 端调用入口）

    Args:
        diagnosis_type: vlan / routing / connectivity
        device_name: 设备名/备注
        vendor: 设备厂商
        vlan_id: VLAN ID（vlan 诊断时使用）
        symptom: 故障现象描述

    Returns:
        dict: {success, root_cause, suggestions, steps}
    """
    import asyncio
    from app.diagnosis.engine import DiagnosisEngine

    adapter = WebSSHAdapter(device_name, vendor)
    engine = DiagnosisEngine(llm_client=None)

    # 创建事件循环运行异步诊断
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已有事件循环（Flask 开发服务器），用 nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            result = loop.run_until_complete(
                engine.diagnose(diagnosis_type, {'vlan_id': vlan_id, 'symptom': symptom}, adapter)
            )
        else:
            result = loop.run_until_complete(
                engine.diagnose(diagnosis_type, {'vlan_id': vlan_id, 'symptom': symptom}, adapter)
            )
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            engine.diagnose(diagnosis_type, {'vlan_id': vlan_id, 'symptom': symptom}, adapter)
        )

    # 转换 DiagnosisResult 为 dict
    steps = []
    if result.steps:
        for s in result.steps:
            steps.append({
                'step': s.step,
                'status': s.status.value if hasattr(s.status, 'value') else str(s.status),
                'message': s.message,
                'suggestion': s.suggestion,
            })

    return {
        'success': result.success,
        'root_cause': result.root_cause,
        'suggestions': result.suggestions or [],
        'steps': steps,
    }
