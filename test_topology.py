#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拓扑发现测试脚本
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_topology_discovery():
    """测试拓扑发现"""
    from app.core.discovery import TopologyDiscovery
    
    print("""
+------------------------------------------------------------+
|                                                            |
|        NetOps AI - 拓扑发现测试                            |
|                                                            |
+------------------------------------------------------------+
""")
    
    # 创建发现引擎
    discovery = TopologyDiscovery(max_depth=3, max_concurrent=5)
    
    # 测试导出功能（不需要真实设备）
    print("\n[测试] 拓扑导出功能...")
    
    # 手动创建测试拓扑
    from app.core.device import Device, Link, Vendor, PortType, Topology
    
    test_topology = Topology()
    
    # 添加设备
    core_sw = Device(hostname="CORE-SW-01", ip="192.168.1.1", vendor=Vendor.HUAWEI, model="S5720")
    access_sw1 = Device(hostname="ACCESS-SW-01", ip="192.168.1.2", vendor=Vendor.HUAWEI, model="S5720")
    access_sw2 = Device(hostname="ACCESS-SW-02", ip="192.168.1.3", vendor=Vendor.HUAWEI, model="S5720")
    
    test_topology.add_device(core_sw)
    test_topology.add_device(access_sw1)
    test_topology.add_device(access_sw2)
    
    # 添加链路
    link1 = Link(
        source_device=core_sw.id,
        source_interface="GE0/0/1",
        target_device=access_sw1.id,
        target_interface="GE0/0/24",
        link_type="physical",
        port_type=PortType.NORMAL,
    )
    
    link2 = Link(
        source_device=core_sw.id,
        source_interface="GE0/0/2",
        target_device=access_sw2.id,
        target_interface="GE0/0/24",
        link_type="physical",
        port_type=PortType.NORMAL,
    )
    
    test_topology.add_link(link1)
    test_topology.add_link(link2)
    
    # 临时替换拓扑
    original_topology = discovery.topology
    discovery.topology = test_topology
    
    # 测试导出
    print("\n1. JSON 格式:")
    print("-" * 60)
    json_output = discovery.export_topology("json")
    print(json_output[:500])
    
    print("\n2. Mermaid 格式:")
    print("-" * 60)
    mermaid_output = discovery.export_topology("mermaid")
    print(mermaid_output)
    
    print("\n3. Graphviz 格式:")
    print("-" * 60)
    graphviz_output = discovery.export_topology("graphviz")
    print(graphviz_output)
    
    # 恢复
    discovery.topology = original_topology
    
    print("\n[OK] 拓扑导出测试完成")


async def test_lldp_parsing():
    """测试 LLDP 解析"""
    from app.network.lldp import LLDPNeighborParser
    from app.core.device import Vendor
    
    print("\n" + "=" * 60)
    print("测试 LLDP 解析")
    print("=" * 60)
    
    # 华为 LLDP 输出示例
    huawei_output = """
Lldp neighbor information
------------------------------------------------
Local interface    : GigabitEthernet0/0/1
Chassis ID         : mac-address 00e0-fc12-3456
Port ID            : GigabitEthernet0/0/24
Port description   : TO-ACCESS-SW-01
System name        : ACCESS-SW-01
System description : Huawei S5720-28P-LI
System capability  : Bridge,Router
Management address : 192.168.1.2
------------------------------------------------
"""
    
    neighbors = LLDPNeighborParser.parse_lldp_neighbor(huawei_output, Vendor.HUAWEI)
    
    print(f"\n解析结果：{len(neighbors)} 个邻居")
    for n in neighbors:
        print(f"  设备：{n.device_id}")
        print(f"  接口：{n.local_interface} -> {n.remote_interface}")
        print(f"  IP: {n.ip}")
        print(f"  描述：{n.port_description}")
    
    print("\n[OK] LLDP 解析测试完成")


async def main():
    """主函数"""
    await test_topology_discovery()
    await test_lldp_parsing()
    
    print("\n" + "=" * 60)
    print("所有拓扑发现测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
