#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯文本演示 - 不需要交互式终端
"""
import io
import sys
# 设置UTF-8输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sys
sys.path.insert(0, '.')

from app.core.device import Topology, Device, Vendor, DeviceType, Link, PortType
from app.core.vendor import VendorIdentifier
from app.ui.components import TopologyCanvas
from app.ui.styles import HacknetColors, DEVICE_ICONS


def create_demo_topology():
    """创建演示拓扑"""
    topo = Topology()

    # 核心交换机 (VRRP Master)
    core = Device(
        id='10.1.1.254',
        name='CORE-SW-01',
        ip='10.1.1.254',
        vendor=Vendor.HUAWEI,
        model='S5720S-28P',
        device_type=DeviceType.SWITCH_L3,
        os_version='V200R019C10'
    )
    core.vrrp_master = '10.1.1.254'
    topo.add_device(core)

    # 汇聚交换机 1
    dist1 = Device(
        id='10.1.1.1',
        name='DIST-SW-01',
        ip='10.1.1.1',
        vendor=Vendor.HUAWEI,
        model='S5735S',
        device_type=DeviceType.SWITCH_L2,
        os_version='V200R010C10'
    )
    topo.add_device(dist1)

    # 汇聚交换机 2
    dist2 = Device(
        id='10.1.1.2',
        name='DIST-SW-02',
        ip='10.1.1.2',
        vendor=Vendor.HUAWEI,
        model='S5735S',
        device_type=DeviceType.SWITCH_L2,
        os_version='V200R010C10'
    )
    topo.add_device(dist2)

    # 接入交换机 1
    acc1 = Device(
        id='10.1.2.10',
        name='ACC-SW-01',
        ip='10.1.2.10',
        vendor=Vendor.CISCO,
        model='2960',
        device_type=DeviceType.SWITCH_L2,
        os_version='15.2'
    )
    topo.add_device(acc1)

    # 接入交换机 2
    acc2 = Device(
        id='10.1.2.11',
        name='ACC-SW-02',
        ip='10.1.2.11',
        vendor=Vendor.CISCO,
        model='2960',
        device_type=DeviceType.SWITCH_L2,
        os_version='15.2'
    )
    topo.add_device(acc2)

    # 服务器
    server = Device(
        id='10.1.3.100',
        name='SERVER-01',
        ip='10.1.3.100',
        vendor=Vendor.UNKNOWN,
        model='VMware',
        device_type=DeviceType.SERVER
    )
    topo.add_device(server)

    # 防火墙
    fw = Device(
        id='10.1.0.1',
        name='FIREWALL-01',
        ip='10.1.0.1',
        vendor=Vendor.HUAWEI,
        model='USG6550',
        device_type=DeviceType.FIREWALL,
        os_version='V500R019C10'
    )
    topo.add_device(fw)

    # 添加链路 - 聚合链路
    topo.add_link(Link(
        source_device='10.1.1.254',
        source_interface='GE0/0/1',
        target_device='10.1.1.1',
        target_interface='GE0/0/1',
        link_type='aggregate',
        port_type=PortType.AGGREGATE
    ))

    topo.add_link(Link(
        source_device='10.1.1.254',
        source_interface='GE0/0/2',
        target_device='10.1.1.2',
        target_interface='GE0/0/1',
        link_type='aggregate',
        port_type=PortType.AGGREGATE
    ))

    # 普通链路
    topo.add_link(Link(
        source_device='10.1.1.1',
        source_interface='GE0/0/3',
        target_device='10.1.2.10',
        target_interface='Gig0/1',
        link_type='physical',
        port_type=PortType.NORMAL
    ))

    topo.add_link(Link(
        source_device='10.1.1.1',
        source_interface='GE0/0/4',
        target_device='10.1.2.11',
        target_interface='Gig0/1',
        link_type='physical',
        port_type=PortType.NORMAL
    ))

    # 防火墙链路
    topo.add_link(Link(
        source_device='10.1.0.1',
        source_interface='GE0/0/1',
        target_device='10.1.1.254',
        target_interface='GE0/0/10',
        link_type='physical',
        port_type=PortType.NORMAL
    ))

    # 服务器链路
    topo.add_link(Link(
        source_device='10.1.1.2',
        source_interface='GE0/0/5',
        target_device='10.1.3.100',
        target_interface='Eth0',
        link_type='physical',
        port_type=PortType.NORMAL
    ))

    return topo


def print_header():
    """打印标题"""
    print()
    print("█"*60)
    print("██╗   ███╗ ██████╗ ███╗   ██╗███████╗████████╗███████╗ ██████╗ ██╗     ")
    print("███╗ ████║██╔═══██╗████╗  ██║██╔════╝╚══██╔══╝██╔════╝██╔═══██╗██║     ")
    print("██╔████╔██║██║   ██║██╔██╗ ██║███████╗   ██║   █████╗  ██║   ██║██║     ")
    print("██║╚██╔╝██║██║   ██║██║╚██╗██║╚════██║   ██║   ██╔══╝  ██║   ██║██║     ")
    print("██║ ╚═╝ ██║╚██████╔╝██║ ╚████║███████║   ██║   ███████╗╚██████╔╝███████╗")
    print("╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝")
    print("                    NETOPS AI v1.0.0                              ")
    print("█"*60)
    print()


def main():
    """主函数"""
    print_header()

    # 创建演示拓扑
    print("[*] 创建演示网络拓扑...")
    topo = create_demo_topology()
    print(f"   + 添加了 {len(topo.devices)} 台设备")
    print(f"   + 添加了 {len(topo.links)} 条链路")
    print()

    # 渲染拓扑
    print("[*] 渲染拓扑画布...")
    canvas = TopologyCanvas(topo)
    lines = canvas.render(90, 30)

    print("="*60)
    print("                    网络拓扑图")
    print("="*60)
    for line in lines:
        print(line)
    print("="*60)
    print()

    # 打印图例
    print("[*] 图例:")
    print("   ─  物理链路      ═══  聚合链路 (LACP)")
    print("   ◈  VRRP/HSRP    ≡≡≡  堆叠")
    print("   ●  OSPF/BGP     - - -  VPN")
    print()

    # 测试焦点切换
    print("[*] 测试焦点切换:")
    canvas.focus_next()
    print(f"   焦点切换到: {canvas.focused_device_id}")
    canvas.focus_next()
    print(f"   焦点切换到: {canvas.focused_device_id}")
    print()

    # 测试缩放
    print("[*] 测试缩放:")
    print(f"   当前缩放: {canvas.viewport.scale * 100}%")
    canvas.viewport.zoom_in()
    print(f"   放大后: {canvas.viewport.scale * 100}%")
    canvas.viewport.zoom_out()
    print(f"   缩小后: {canvas.viewport.scale * 100}%")
    print()

    # 厂商识别测试
    print("[*] 厂商识别测试:")
    test_strings = [
        "Huawei S5720S-28P-SI Ver V200R019C10SPH200",
        "Cisco IOS Software, C2960X Series",
        "HP J9772A 2920-48G PoE+",
    ]
    for s in test_strings:
        vendor, model, dtype = VendorIdentifier.identify_from_snmp(s)
        print(f"   '{s[:30]}...'")
        print(f"      → {vendor.value}, {model}, {dtype.value}")
    print()

    print("="*60)
    print("                      演示完成!")
    print("="*60)
    print()
    print("运行 'python main.py' 启动完整UI")
    print()


if __name__ == "__main__":
    main()