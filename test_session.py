#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话管理测试脚本
测试多轮对话、上下文保持、引用解析
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.session import SessionManager
from app.session.models import TurnRole


def test_session_creation():
    """测试会话创建"""
    print("\n" + "="*60)
    print(" 测试会话创建")
    print("="*60)
    
    manager = SessionManager()
    
    # 创建会话
    session = manager.create_session("user_001")
    print(f"\n[OK] 创建会话: {session.id}")
    print(f"    用户ID: {session.user_id}")
    print(f"    状态: {session.status}")
    
    # 获取会话
    retrieved = manager.get_session("user_001")
    print(f"\n[OK] 获取会话: {retrieved.id if retrieved else 'None'}")
    
    # 统计
    stats = manager.get_session_stats()
    print(f"\n[OK] 会话统计: {stats}")


def test_conversation_turns():
    """测试对话轮次"""
    print("\n" + "="*60)
    print(" 测试对话轮次")
    print("="*60)
    
    manager = SessionManager()
    
    # 模拟对话
    manager.add_turn(
        user_id="user_001",
        role=TurnRole.USER,
        content="查一下 SW-Core 的配置",
        intent_type="query_config",
        intent_params={"device_hostname": "SW-Core"},
        referenced_devices=["SW-Core"]
    )
    
    manager.add_turn(
        user_id="user_001",
        role=TurnRole.ASSISTANT,
        content="已查询 SW-Core 的配置",
        execution_success=True
    )
    
    manager.add_turn(
        user_id="user_001",
        role=TurnRole.USER,
        content="VLAN 10 上不了网，查一下",
        intent_type="diagnose_vlan",
        intent_params={"vlan_id": 10},
        referenced_vlans=[10]
    )
    
    # 获取上下文
    context = manager.get_context_for_query("user_001", "再查一下")
    print("\n[OK] 上下文信息:")
    print(context)
    
    # 获取会话
    session = manager.get_session("user_001")
    print(f"\n[OK] 最近操作的设备: {session.last_device}")
    print(f"[OK] 最近操作的VLAN: {session.last_vlan}")


def test_reference_resolution():
    """测试引用解析"""
    print("\n" + "="*60)
    print(" 测试引用解析")
    print("="*60)
    
    manager = SessionManager()
    
    # 先添加一些上下文
    manager.add_turn(
        user_id="user_001",
        role=TurnRole.USER,
        content="查一下 SW-Core (IP: 192.168.1.1) 的配置",
        intent_params={"device_hostname": "SW-Core", "device_ip": "192.168.1.1"},
        referenced_devices=["SW-Core"]
    )
    
    manager.add_turn(
        user_id="user_001",
        role=TurnRole.USER,
        content="VLAN 20 的配置",
        intent_params={"vlan_id": 20},
        referenced_vlans=[20]
    )
    
    # 测试引用解析
    test_cases = [
        ("那台设备怎么样", "那台设备"),
        ("那个VLAN有问题", "那个VLAN"),
        ("再查一下", "再查一下"),
    ]
    
    print("\n引用解析测试:")
    for user_input, reference in test_cases:
        resolved = manager.resolve_reference("user_001", reference)
        print(f"  '{user_input}' -> '{resolved}'")


def test_multi_user():
    """测试多用户"""
    print("\n" + "="*60)
    print(" 测试多用户")
    print("="*60)
    
    manager = SessionManager()
    
    # 用户1
    session1 = manager.create_session("user_001")
    manager.add_turn(
        user_id="user_001",
        role=TurnRole.USER,
        content="查一下 SW-Core",
        referenced_devices=["SW-Core"]
    )
    
    # 用户2
    session2 = manager.create_session("user_002")
    manager.add_turn(
        user_id="user_002",
        role=TurnRole.USER,
        content="查一下 RT-Edge",
        referenced_devices=["RT-Edge"]
    )
    
    # 获取各自的会话
    s1 = manager.get_session("user_001")
    s2 = manager.get_session("user_002")
    
    print(f"\n[OK] 用户1最近设备: {s1.last_device}")
    print(f"[OK] 用户2最近设备: {s2.last_device}")
    
    # 统计
    stats = manager.get_session_stats()
    print(f"\n[OK] 会话统计: {stats}")


def test_session_persistence():
    """测试会话持久化"""
    print("\n" + "="*60)
    print(" 测试会话持久化")
    print("="*60)
    
    import tempfile
    import os
    
    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建管理器并添加会话
        manager1 = SessionManager(storage_dir=tmpdir)
        manager1.add_turn(
            user_id="user_001",
            role=TurnRole.USER,
            content="查一下 SW-Core",
            referenced_devices=["SW-Core"]
        )
        
        # 保存
        session1 = manager1.get_session("user_001")
        print(f"\n[OK] 创建会话: {session1.id}")
        print(f"[OK] 最近设备: {session1.last_device}")
        
        # 新建管理器（从文件加载）
        manager2 = SessionManager(storage_dir=tmpdir)
        session2 = manager2.get_session("user_001")
        
        if session2:
            print(f"\n[OK] 加载会话: {session2.id}")
            print(f"[OK] 最近设备: {session2.last_device}")
        else:
            print("\n[WARN] 会话已过期或不存在")


def main():
    """主测试函数"""
    print("""
========================================
  NetOps AI - 会话管理测试
========================================
""")
    
    test_session_creation()
    test_conversation_turns()
    test_reference_resolution()
    test_multi_user()
    test_session_persistence()
    
    print("\n" + "="*60)
    print(" [OK] 所有测试完成")
    print("="*60)
    print("\n会话管理功能:")
    print("  - 多用户支持")
    print("  - 多轮对话")
    print("  - 上下文保持")
    print("  - 引用解析（'那台设备'、'那个VLAN'）")
    print("  - 会话持久化")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
