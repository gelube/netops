#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ping 监控测试脚本
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.monitor.ping_monitor import PingMonitor, quick_ping, check_network


async def test_single_ping():
    """测试单个 ping"""
    print("\n" + "="*60)
    print(" 测试单个 Ping")
    print("="*60)
    
    # 测试常用地址
    hosts = ["127.0.0.1", "192.168.1.1", "8.8.8.8", "baidu.com"]
    
    for host in hosts:
        print(f"\n[Ping] {host}...")
        result = await quick_ping(host, count=2, timeout=2)
        
        if result.success:
            print(f"  [OK] 延迟: {result.latency_ms:.1f}ms, 丢包率: {result.packet_loss:.0f}%")
        else:
            print(f"  [FAIL] 错误: {result.error}")


async def test_multi_ping():
    """测试批量 ping"""
    print("\n" + "="*60)
    print(" 测试批量 Ping")
    print("="*60)
    
    hosts = ["127.0.0.1", "8.8.8.8", "114.114.114.114", "192.168.999.999"]  # 最后一个无效
    
    results = await check_network(hosts)
    
    print("\n结果:")
    for host, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {host}")


async def test_monitor():
    """测试监控器"""
    print("\n" + "="*60)
    print(" 测试 Ping 监控器")
    print("="*60)
    
    # 创建监控器
    devices = {
        "本机回环": "127.0.0.1",
        "Google DNS": "8.8.8.8",
        "114 DNS": "114.114.114.114",
    }
    
    monitor = PingMonitor(devices=devices, count=2, timeout=2)
    
    # 检查一次
    print("\n[检查所有设备...]")
    results = await monitor.check_all()
    
    for hostname, result in results.items():
        status = "[OK]" if result.success else "[FAIL]"
        latency = f"{result.latency_ms:.1f}ms" if result.success else "-"
        print(f"  {status} {hostname} ({result.host}) - 延迟: {latency}")
    
    # 获取状态
    print("\n[设备状态]")
    status = monitor.get_status()
    for hostname, info in status.items():
        print(f"  {info['hostname']}: {'在线' if info['is_online'] else '离线'}, "
              f"平均延迟: {info['avg_latency']:.1f}ms, "
              f"在线率: {info['uptime_percent']:.1f}%")


async def test_offline_detection():
    """测试离线检测"""
    print("\n" + "="*60)
    print(" 测试离线设备检测")
    print("="*60)
    
    devices = {
        "本机": "127.0.0.1",
        "无效设备1": "192.168.999.1",
        "无效设备2": "10.255.255.1",
    }
    
    monitor = PingMonitor(devices=devices, count=1, timeout=1)
    await monitor.check_all()
    
    offline = monitor.get_offline_devices()
    
    if offline:
        print(f"\n离线设备 ({len(offline)}):")
        for dev in offline:
            print(f"  - {dev['hostname']} ({dev['ip']})")
    else:
        print("\n所有设备在线")


async def main():
    """主测试函数"""
    print("""
========================================
  NetOps AI - Ping 监控测试
========================================
""")
    
    await test_single_ping()
    await test_multi_ping()
    await test_monitor()
    await test_offline_detection()
    
    print("\n" + "="*60)
    print(" [OK] 所有测试完成")
    print("="*60)
    print("\nPing 监控功能:")
    print("  - 单个/批量 ping")
    print("  - 设备状态追踪")
    print("  - 离线设备检测")
    print("  - 延迟/丢包统计")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
