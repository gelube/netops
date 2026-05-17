#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话管理器
支持多用户、多会话、上下文保持
"""
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import threading

from .models import Session, ConversationTurn, TurnRole

from app.logger import get_logger

log = get_logger(__name__)


class SessionManager:
    """会话管理器"""

    def __init__(self, storage_dir: str = None, session_timeout_hours: int = 24):
        """
        初始化会话管理器

        Args:
            storage_dir: 会话存储目录
            session_timeout_hours: 会话超时时间（小时）
        """
        self.sessions: Dict[str, Session] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id
        self.storage_dir = Path(storage_dir) if storage_dir else None
        self.session_timeout = timedelta(hours=session_timeout_hours)
        self.lock = threading.RLock()

        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_sessions()

    def create_session(self, user_id: str) -> Session:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            user_id=user_id,
        )

        with self.lock:
            self.sessions[session_id] = session
            self.user_sessions[user_id] = session_id

        self._save_session(session)
        return session

    def get_session(self, user_id: str, create_if_not_exists: bool = True) -> Optional[Session]:
        """获取用户会话"""
        with self.lock:
            session_id = self.user_sessions.get(user_id)

            if session_id:
                session = self.sessions.get(session_id)
                if session and self._is_session_valid(session):
                    return session
                else:
                    # 会话过期或不存在，清理
                    if session_id in self.sessions:
                        del self.sessions[session_id]
                    if user_id in self.user_sessions:
                        del self.user_sessions[user_id]

            if create_if_not_exists:
                return self.create_session(user_id)

        return None

    def add_turn(self, user_id: str, role: TurnRole, content: str,
                 intent_type: str = None, intent_params: dict = None,
                 execution_success: bool = None, execution_data: dict = None,
                 referenced_devices: List[str] = None, referenced_vlans: List[int] = None) -> ConversationTurn:
        """
        添加对话轮次

        Args:
            user_id: 用户ID
            role: 角色
            content: 内容
            intent_type: 意图类型
            intent_params: 意图参数
            execution_success: 执行是否成功
            execution_data: 执行数据
            referenced_devices: 引用的设备
            referenced_vlans: 引用的VLAN
        """
        session = self.get_session(user_id)
        if not session:
            session = self.create_session(user_id)

        turn = ConversationTurn(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            intent_type=intent_type,
            intent_params=intent_params or {},
            execution_success=execution_success,
            execution_data=execution_data or {},
            referenced_devices=referenced_devices or [],
            referenced_vlans=referenced_vlans or [],
        )

        session.add_turn(turn)
        self._save_session(session)

        return turn

    def get_context_for_query(self, user_id: str, current_query: str) -> str:
        """
        获取查询的上下文

        Args:
            user_id: 用户ID
            current_query: 当前查询

        Returns:
            上下文描述字符串
        """
        session = self.get_session(user_id, create_if_not_exists=False)
        if not session:
            return ""

        context_parts = []

        # 设备上下文
        device_context = session.get_device_context()
        if device_context:
            context_parts.append(device_context)

        # 最近对话摘要
        recent_turns = session.get_recent_context(3)
        if recent_turns:
            context_parts.append("\n最近对话:")
            for turn in recent_turns:
                if turn.role == TurnRole.USER:
                    context_parts.append(f"  用户: {turn.content[:100]}")
                elif turn.role == TurnRole.ASSISTANT:
                    status = "[OK]" if turn.execution_success else "[FAIL]"
                    context_parts.append(f"  助手{status}: {turn.content[:100]}")

        return "\n".join(context_parts) if context_parts else ""

    def resolve_reference(self, user_id: str, reference: str) -> Optional[str]:
        """
        解析引用（如"那台设备"、"那个VLAN"）

        Args:
            user_id: 用户ID
            reference: 引用词

        Returns:
            解析后的值
        """
        session = self.get_session(user_id, create_if_not_exists=False)
        if not session:
            return None

        # 设备引用
        if "那台设备" in reference or "那设备" in reference or "刚才的设备" in reference:
            return session.last_device or session.last_device_ip

        # VLAN引用
        if "那个VLAN" in reference or "那个vlan" in reference or "刚才的VLAN" in reference:
            return str(session.last_vlan) if session.last_vlan else None

        # 接口引用
        if "那个接口" in reference or "刚才的接口" in reference:
            return session.last_interface

        return None

    def close_session(self, user_id: str):
        """关闭会话"""
        with self.lock:
            session_id = self.user_sessions.get(user_id)
            if session_id and session_id in self.sessions:
                self.sessions[session_id].status = "closed"
                self._save_session(self.sessions[session_id])
                del self.sessions[session_id]
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]

    def clear_expired_sessions(self):
        """清理过期会话"""
        with self.lock:
            expired = []
            for session_id, session in self.sessions.items():
                if not self._is_session_valid(session):
                    expired.append(session_id)

            for session_id in expired:
                del self.sessions[session_id]

    def delete_session(self, session_id: str):
        """删除指定会话"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
            # 也删除持久化文件
            if self.storage_dir:
                session_file = os.path.join(self.storage_dir, f"{session_id}.json")
                if os.path.exists(session_file):
                    os.remove(session_file)

            # 清理用户映射
            self.user_sessions = {
                uid: sid for uid, sid in self.user_sessions.items()
                if sid in self.sessions
            }

    def get_session_stats(self) -> Dict[str, int]:
        """获取会话统计"""
        with self.lock:
            return {
                "total_sessions": len(self.sessions),
                "active_sessions": sum(1 for s in self.sessions.values() if s.status == "active"),
                "total_users": len(self.user_sessions),
            }

    def _is_session_valid(self, session: Session) -> bool:
        """检查会话是否有效"""
        if session.status != "active":
            return False

        # 检查超时
        if datetime.now() - session.updated_at > self.session_timeout:
            return False

        return True

    def _save_session(self, session: Session):
        """保存会话到文件"""
        if not self.storage_dir:
            return

        try:
            file_path = self.storage_dir / f"{session.id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error("[SessionManager] 保存会话失败", error=str(e))

    def _load_sessions(self):
        """从文件加载会话"""
        if not self.storage_dir:
            return

        try:
            for file_path in self.storage_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    session = Session.from_dict(data)

                    if self._is_session_valid(session):
                        self.sessions[session.id] = session
                        self.user_sessions[session.user_id] = session.id
                except Exception as e:
                    log.error(f"加载会话失败 {file_path}: {e}")
        except Exception as e:
            log.error("[SessionManager] 加载会话目录失败", error=str(e))
