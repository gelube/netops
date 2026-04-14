#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断引擎测试脚本
测试VLAN、路由、连通性诊断功能
"""
import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.diagnosis import DiagnosisEngine, VLANChecker, RoutingChecker, ConnectivityChecker
from app.diagnosis.base import DiagnosisResult, CheckStatus


def print_result(result: DiagnosisResult, title: str = "诊断结果"):
    """打印诊断结果"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")
    
    if result.steps:
        print("\n检查步骤:")
        for step in result.steps:
            icon = "[OK]" if step.status == CheckStatus.PASS else "[FAIL]" if step.status == CheckStatus.FAIL else "[WARN]"
            print(f"  {icon} {step.step}: {step.message}")
            if step.suggestion:
                print(f"       >> {step.suggestion}")
    
    if result.root_cause:
        print(f"\n[根因] {result.root_cause}")
    
    if result.suggestions:
        print("\n[建议]:")
        for sug in result.suggestions:
            print(f"  - {sug}")
    
    print(f"\n状态: {'成功' if result.success else '失败'}")
    print(f"{'='*60}\n")


async def test_vlan_checker():
    """测试VLAN诊断检查器"""
    print("\n" + "="*60)
    print(" 测试 VLAN 诊断检查器")
    print("="*60)
    
    # 模拟测试（无SSH连接）
    checker = VLANChecker(ssh_connection=None, llm_client=None)
    
    result = await checker.diagnose(vlan_id=10, symptom="财务部上不了网")
    print_result(result, "VLAN 10 诊断（模拟）")
    
    # 测试症状推断
    vlan_id = checker._infer_vlan_from_symptom("技术部的电脑上不了网")
    print(f"\n症状推断测试:")
    print(f"  输入: '技术部的电脑上不了网'")
    print(f"  推断VLAN: {vlan_id}")
    
    vlan_id = checker._infer_vlan_from_symptom("VLAN 200 的网络有问题")
    print(f"  输入: 'VLAN 200 的网络有问题'")
    print(f"  推断VLAN: {vlan_id}")


async def test_routing_checker():
    """测试路由诊断检查器"""
    print("\n" + "="*60)
    print(" 测试路由诊断检查器")
    print("="*60)
    
    checker = RoutingChecker(ssh_connection=None, llm_client=None)
    
    result = await checker.diagnose(
        source_ip="10.10.10.1",
        dest_ip="8.8.8.8",
        symptom="ping不通外网"
    )
    print_result(result, "路由诊断（模拟）")


async def test_connectivity_checker():
    """测试连通性诊断检查器"""
    print("\n" + "="*60)
    print(" 测试连通性诊断检查器")
    print("="*60)
    
    checker = ConnectivityChecker(ssh_connection=None, llm_client=None)
    
    result = await checker.diagnose(
        source_ip="192.168.1.10",
        dest_ip="192.168.2.20",
        symptom="两个网段ping不通"
    )
    print_result(result, "连通性诊断（模拟）")


async def test_diagnosis_engine():
    """测试诊断引擎"""
    print("\n" + "="*60)
    print(" 测试诊断引擎")
    print("="*60)
    
    engine = DiagnosisEngine(llm_client=None, credential_manager=None)
    
    # 测试症状分析
    symptoms = [
        "财务部上不了网",
        "ping不通8.8.8.8",
        "路由器OSPF邻居断了",
        "两个网段之间ping不通"
    ]
    
    print("\n症状分析测试:")
    for symptom in symptoms:
        analysis = engine._analyze_symptom(symptom)
        print(f"  '{symptom}'")
        print(f"    → 类型: {analysis['type']}")
        print()


async def test_full_workflow():
    """测试完整诊断流程（模拟）"""
    print("\n" + "="*60)
    print(" 完整诊断流程测试（模拟）")
    print("="*60)
    
    print("\n场景1: 用户报告'财务部上不了网'")
    print("-" * 60)
    checker = VLANChecker(ssh_connection=None)
    result = await checker.diagnose(vlan_id=10, symptom="财务部上不了网")
    print_result(result, "VLAN诊断")
    
    print("\n场景2: 用户报告'ping不通外网'")
    print("-" * 60)
    checker = ConnectivityChecker(ssh_connection=None)
    result = await checker.diagnose(dest_ip="8.8.8.8", symptom="ping不通外网")
    print_result(result, "连通性诊断")


async def main():
    """主测试函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        NetOps AI - 诊断引擎测试                          ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")
    
    # 运行所有测试
    await test_vlan_checker()
    await test_routing_checker()
    await test_connectivity_checker()
    await test_diagnosis_engine()
    await test_full_workflow()
    
    print("\n" + "="*60)
    print(" [OK] 所有测试完成")
    print("="*60)
    print("\n注意: 以上测试为模拟测试（无SSH连接）")
    print("实际使用时需要配置设备SSH连接")
    print("\n使用方法:")
    print("  python main_nl.py")
    print("  然后输入: 'VLAN 10 上不了网，查一下 SW-Core (IP: 192.168.1.1)'")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
