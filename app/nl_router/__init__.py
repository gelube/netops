"""
自然语言路由模块
将用户自然语言映射到 MCP 工具调用或本地 SSH 执行
"""
from .parser import IntentParser
from .executor import NLExecutor

__all__ = ["IntentParser", "NLExecutor"]
