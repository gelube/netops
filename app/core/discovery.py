#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拓扑发现模块 - 完善版
支持 LLDP/CDP 自动发现
"""
import asyncio
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

from app.core.device import Topology, Device, Link, Vendor, PortType
from app.core.vendor import VendorIdentifier
from app.network.commands import CommandBuilder
from app.network.lldp import LLDPNeighborParser, LinkTypeDetector, NeighborInfo


@dataclass
class DiscoveryResult:
    """发现结果"""
    success: bool
    message: str
    topology: Optional[Topology] = None
    devices_found: int = 0
    links_found: int = 0


class TopologyDiscovery:
    """拓扑发现引擎"""
    
    def __init__(self, max_depth: int = 3, max_concurrent: int = 5):
        """
        初始化
        
        Args:
            max_depth: 最大递归深度
            max_concurrent: 最大并发数
        """
        self.max_depth = max_depth
        self.max_concurrent = max_concurrent
        self.visited: Set[str] = set()
        self.topology = Topology()
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def discover(self, seed_ip: str, username: str = "", password: str = "", port: int = 22) -> DiscoveryResult:
        """
        从种子设备开始发现整个网络拓扑
        
        Args:
            seed_ip: 种子设备 IP
            username: 用户名
            password: 密码
            port: 端口（22=SSH, 23=Telnet）
        
        Returns:
            DiscoveryResult
        """
        try:
            # 清空状态
            self.visited.clear()
            self.topology = Topology()
            
            # 递归发现
            await self._discover_device(seed_ip, username, password, port, depth=0)
            
            return DiscoveryResult(
                success=True,
                message=f"发现完成，共 {len(self.topology.devices)} 台设备，{len(self.topology.links)} 条链路",
                topology=self.topology,
                devices_found=len(self.topology.devices),
                links_found=len(self.topology.links),
            )
        
        except Exception as e:
            return DiscoveryResult(
                success=False,
                message=f"发现失败：{str(e)}",
                topology=None,
            )
    
    async def _discover_device(self, ip: str, username: str, password: str, port: int, depth: int) -> None:
        """
        递归发现设备及其邻居
        
        Args:
            ip: 设备 IP
            username: 用户名
            password: 密码
            port: 端口
            depth: 当前深度
        """
        # 检查是否已访问
        if ip in self.visited:
            return
        
        # 检查深度
        if depth > self.max_depth:
            return
        
        self.visited.add(ip)
        
        async with self.semaphore:
            try:
                # 延迟导入避免循环依赖
                from app.network.ssh import DeviceConnection, ConnectionInfo
                
                # 连接设备
                conn_info = ConnectionInfo(
                    ip=ip,
                    port=port,
                    username=username,
                    password=password,
                )
                
                with DeviceConnection(conn_info) as conn:
                    # 1. 获取设备信息
                    device = conn.get_device_info()
                    device.ip = ip
                    
                    # 添加到拓扑
                    self.topology.add_device(device)
                    
                    # 2. 获取 LLDP/CDP 邻居
                    neighbors = conn.get_lldp_neighbors()
                    
                    # 3. 解析邻居 IP（需要 DNS 或手动映射）
                    for neighbor in neighbors:
                        # 创建链路
                        link = Link(
                            src_device=device,
                            src_interface=neighbor.local_interface,
                            dst_device_id=neighbor.device_id,
                            dst_interface=neighbor.remote_interface,
                            port_type=LinkTypeDetector.detect_link_type(
                                neighbor.port_description,
                                neighbor.capability,
                            ),
                        )
                        self.topology.add_link(link)
                        
                        # 4. 递归发现邻居设备
                        # 注意：这里需要邻居的 IP，但 LLDP 通常只返回主机名
                        # 需要 DNS 解析或手动映射
                        neighbor_ip = self._resolve_neighbor_ip(neighbor.device_id)
                        
                        if neighbor_ip and neighbor_ip not in self.visited:
                            await self._discover_device(
                                neighbor_ip,
                                username,
                                password,
                                port,
                                depth + 1,
                            )
            
            except Exception as e:
                print(f"发现设备 {ip} 失败：{e}")
    
    def _resolve_neighbor_ip(self, device_id: str) -> Optional[str]:
        """
        解析邻居设备 ID 到 IP
        
        方法：
        1. DNS 解析
        2. 手动映射表
        3. 从 device_id 提取（如果包含 IP）
        
        Args:
            device_id: 设备 ID（主机名或 MAC）
        
        Returns:
            IP 地址，无法解析返回 None
        """
        import re
        
        # 方法 1: 如果 device_id 本身就是 IP
        ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        match = re.search(ip_pattern, device_id)
        if match:
            return match.group(0)
        
        # 方法 2: DNS 解析（需要网络配置）
        # import socket
        # try:
        #     ip = socket.gethostbyname(device_id)
        #     return ip
        # except:
        #     pass
        
        # 方法 3: 手动映射表（从配置文件加载）
        # manual_mapping = {
        #     "CORE-SW-01": "192.168.1.1",
        #     "ACCESS-SW-01": "192.168.1.2",
        # }
        # return manual_mapping.get(device_id)
        
        # 暂时返回 None，需要用户提供映射
        return None
    
    def set_manual_mapping(self, mapping: Dict[str, str]):
        """
        设置手动映射表
        
        Args:
            mapping: {设备名：IP}
        """
        # 可以保存到配置文件或数据库
        pass
    
    def export_topology(self, format: str = "json") -> str:
        """
        导出拓扑
        
        Args:
            format: 导出格式（json/graphviz/mermaid）
        
        Returns:
            导出的拓扑字符串
        """
        if format == "json":
            import json
            return json.dumps({
                "devices": [
                    {
                        "hostname": d.name,
                        "ip": d.ip,
                        "vendor": d.vendor.value,
                        "model": d.model,
                    }
                    for d in self.topology.devices
                ],
                "links": [
                    {
                        "src": f"{l.source_device}/{l.source_interface}",
                        "dst": f"{l.target_device}/{l.target_interface}",
                        "type": l.port_type.value,
                    }
                    for l in self.topology.links
                ],
            }, indent=2, ensure_ascii=False)
        
        elif format == "mermaid":
            # Mermaid 流程图格式
            lines = ["graph TD"]
            
            for device in self.topology.devices:
                lines.append(f"    {device.name.replace('-', '_')}[\"{device.name}<br/>{device.ip}\"]")
            
            for link in self.topology.links:
                src = link.source_device.replace('-', '_')
                dst = link.target_device.replace('-', '_')
                lines.append(f"    {src} -- \"{link.source_interface}<->{link.target_interface}\" --> {dst}")
            
            return "\n".join(lines)
        
        elif format == "graphviz":
            # Graphviz DOT 格式
            lines = ["digraph Topology {"]
            lines.append("    rankdir=LR;")
            
            for device in self.topology.devices:
                lines.append(f"    \"{device.name}\" [label=\"{device.name}\\n{device.ip}\"];")
            
            for link in self.topology.links:
                lines.append(f"    \"{link.source_device}\" -> \"{link.target_device}\" [label=\"{link.source_interface}<->{link.target_interface}\"];")
            
            lines.append("}")
            return "\n".join(lines)
        
        return ""


async def main():
    """测试拓扑发现"""
    print("""
+------------------------------------------------------------+
|                                                            |
|        NetOps AI - 拓扑发现测试                            |
|                                                            |
+------------------------------------------------------------+
""")
    
    # 示例用法
    discovery = TopologyDiscovery(max_depth=3, max_concurrent=5)
    
    # 需要用户提供种子设备 IP 和凭证
    seed_ip = input("种子设备 IP: ").strip()
    username = input("用户名: ").strip()
    password = input("密码: ").strip()
    port = int(input("端口 (22=SSH, 23=Telnet): ").strip() or "22")
    
    print("\n开始发现拓扑...")
    result = await discovery.discover(seed_ip, username, password, port)
    
    if result.success:
        print(f"\n[OK] {result.message}")
        
        # 导出拓扑
        print("\n导出格式选择:")
        print("1. JSON")
        print("2. Mermaid")
        print("3. Graphviz")
        
        choice = input("选择 (1/2/3): ").strip()
        
        if choice == "1":
            print(result.export_topology("json"))
        elif choice == "2":
            print(result.export_topology("mermaid"))
        elif choice == "3":
            print(result.export_topology("graphviz"))
    else:
        print(f"\n[FAIL] {result.message}")


if __name__ == "__main__":
    asyncio.run(main())
