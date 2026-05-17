#!/usr/bin/env python3
"""
诊断基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class CheckStatus(str, Enum):
    """检查状态"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    """检查结果"""
    step: str
    status: CheckStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None


@dataclass
class DiagnosisResult:
    """诊断结果"""
    success: bool
    root_cause: Optional[str] = None
    suggestions: List[str] = None
    steps: List[CheckResult] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []
        if self.steps is None:
            self.steps = []


class BaseChecker(ABC):
    """诊断检查器基类"""

    def __init__(self, ssh_connection=None):
        """
        初始化

        Args:
            ssh_connection: SSH连接对象（DeviceConnection）
        """
        self.conn = ssh_connection
        self.results: List[CheckResult] = []

    @abstractmethod
    def diagnose(self, **kwargs) -> DiagnosisResult:
        """执行诊断"""
        pass

    def add_result(self, step: str, status: CheckStatus, message: str,
                   details: Dict = None, suggestion: str = None):
        """添加检查结果"""
        self.results.append(CheckResult(
            step=step,
            status=status,
            message=message,
            details=details,
            suggestion=suggestion
        ))

    def execute_command(self, command: str, timeout: int = 30) -> str:
        """执行命令"""
        if not self.conn:
            raise Exception("SSH连接未建立")
        return self.conn.execute_command(command, timeout)

    def analyze_with_llm(self, llm_client, context: str, question: str) -> str:
        """使用LLM分析"""
        prompt = f"""
{context}

问题：{question}

请分析以上设备输出，给出：
1. 发现的问题
2. 可能的原因
3. 建议的解决方案
"""
        response = llm_client.chat_simple(question, context=prompt, timeout=30)
        return response or "LLM分析超时"
