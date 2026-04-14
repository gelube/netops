"""
会话管理模块
支持多轮对话、上下文保持、历史记录
"""
from .manager import SessionManager
from .models import Session, ConversationTurn

__all__ = ["SessionManager", "Session", "ConversationTurn"]
