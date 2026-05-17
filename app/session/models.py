#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class TurnRole(Enum):
    """对话角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ConversationTurn:
    """单轮对话"""
    id: str
    role: TurnRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    # 意图信息（如果是用户输入）
    intent_type: Optional[str] = None
    intent_params: Dict[str, Any] = field(default_factory=dict)

    # 执行结果（如果是助手响应）
    execution_success: Optional[bool] = None
    execution_data: Dict[str, Any] = field(default_factory=dict)

    # 上下文引用
    referenced_devices: List[str] = field(default_factory=list)
    referenced_vlans: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "intent_type": self.intent_type,
            "intent_params": self.intent_params,
            "execution_success": self.execution_success,
            "execution_data": self.execution_data,
            "referenced_devices": self.referenced_devices,
            "referenced_vlans": self.referenced_vlans,
        }


@dataclass
class Session:
    """会话"""
    id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 对话历史
    turns: List[ConversationTurn] = field(default_factory=list)

    # 上下文状态
    context: Dict[str, Any] = field(default_factory=dict)

    # 最近引用的设备
    last_device: Optional[str] = None
    last_device_ip: Optional[str] = None

    # 最近操作的VLAN
    last_vlan: Optional[int] = None

    # 最近操作的接口
    last_interface: Optional[str] = None

    # 会话状态
    status: str = "active"  # active, closed, archived

    def add_turn(self, turn: ConversationTurn):
        """添加对话轮次"""
        self.turns.append(turn)
        self.updated_at = datetime.now()

        # 更新上下文
        if turn.referenced_devices:
            self.last_device = turn.referenced_devices[-1]
        if turn.referenced_vlans:
            self.last_vlan = turn.referenced_vlans[-1]
        if turn.intent_params:
            if "device_ip" in turn.intent_params:
                self.last_device_ip = turn.intent_params["device_ip"]
            if "interface" in turn.intent_params:
                self.last_interface = turn.intent_params["interface"]

    def get_recent_context(self, n: int = 3) -> List[ConversationTurn]:
        """获取最近n轮对话"""
        return self.turns[-n:] if self.turns else []

    def get_device_context(self) -> str:
        """获取设备上下文描述"""
        parts = []
        if self.last_device:
            parts.append(f"最近操作的设备: {self.last_device}")
        if self.last_device_ip:
            parts.append(f"IP: {self.last_device_ip}")
        if self.last_vlan:
            parts.append(f"最近操作的VLAN: {self.last_vlan}")
        if self.last_interface:
            parts.append(f"最近操作的接口: {self.last_interface}")
        return "\n".join(parts) if parts else ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "turns": [t.to_dict() for t in self.turns],
            "context": self.context,
            "last_device": self.last_device,
            "last_device_ip": self.last_device_ip,
            "last_vlan": self.last_vlan,
            "last_interface": self.last_interface,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """从字典创建"""
        session = cls(
            id=data["id"],
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            context=data.get("context", {}),
            last_device=data.get("last_device"),
            last_device_ip=data.get("last_device_ip"),
            last_vlan=data.get("last_vlan"),
            last_interface=data.get("last_interface"),
            status=data.get("status", "active"),
        )

        for turn_data in data.get("turns", []):
            turn = ConversationTurn(
                id=turn_data["id"],
                role=TurnRole(turn_data["role"]),
                content=turn_data["content"],
                timestamp=datetime.fromisoformat(turn_data["timestamp"]),
                intent_type=turn_data.get("intent_type"),
                intent_params=turn_data.get("intent_params", {}),
                execution_success=turn_data.get("execution_success"),
                execution_data=turn_data.get("execution_data", {}),
                referenced_devices=turn_data.get("referenced_devices", []),
                referenced_vlans=turn_data.get("referenced_vlans", []),
            )
            session.turns.append(turn)

        return session
