#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket推送服务 — 诊断进度、命令执行结果实时推送
"""
import threading
from typing import Optional, Dict, Any
from flask_socketio import SocketIO, emit

# 全局SocketIO实例
socketio: Optional[SocketIO] = None


def init_socketio(app):
    """初始化SocketIO（在app创建后调用）"""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins=["http://localhost:*", "http://127.0.0.1:*"], async_mode='threading')
    return socketio


def get_socketio() -> Optional[SocketIO]:
    return socketio


class ProgressPusher:
    """诊断/执行进度推送器"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id

    def push_step(self, step_name: str, status: str, message: str, details: Dict = None):
        """推送诊断步骤"""
        if socketio:
            socketio.emit('diagnosis_step', {
                'session_id': self.session_id,
                'step': step_name,
                'status': status,
                'message': message,
                'details': details or {},
            })

    def push_progress(self, current: int, total: int, message: str = ""):
        """推送进度"""
        if socketio:
            socketio.emit('progress', {
                'session_id': self.session_id,
                'current': current,
                'total': total,
                'percent': round(current / total * 100) if total > 0 else 0,
                'message': message,
            })

    def push_command_result(self, device: str, command: str, output: str,
                            success: bool = True, duration: float = 0):
        """推送命令执行结果"""
        if socketio:
            socketio.emit('command_result', {
                'session_id': self.session_id,
                'device': device,
                'command': command,
                'output': output[:5000],  # 限制推送长度
                'success': success,
                'duration': round(duration, 2),
            })

    def push_diagnosis_complete(self, root_cause: str, suggestions: list, success: bool):
        """推送诊断完成"""
        if socketio:
            socketio.emit('diagnosis_complete', {
                'session_id': self.session_id,
                'root_cause': root_cause,
                'suggestions': suggestions,
                'success': success,
            })

    def push_notification(self, level: str, message: str):
        """推送通知"""
        if socketio:
            socketio.emit('notification', {
                'session_id': self.session_id,
                'level': level,  # info/warning/error
                'message': message,
            })
