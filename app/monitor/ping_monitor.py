#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ping 监控模块
简单的连通性监控，只用 ping
"""
import asyncio
import subprocess
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class PingResult:
    """Ping 结果"""
    host: str
    success: bool
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    error: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "host": self.host,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "packet_loss": self.packet_loss,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }


@dataclass
class DeviceStatus:
    """设备状态"""
    hostname: str
    ip: str
    is_online: bool = False
    last_ping: Optional[PingResult] = None
    history: List[PingResult] = field(default_factory=list)
    
    # 统计信息
    avg_latency: float = 0.0
    uptime_percent: float = 0.0
    
    def update(self, result: PingResult):
        """更新状态"""
        self.last_ping = result
        self.is_online = result.success
        self.history.append(result)
        
        # 保留最近 100 次记录
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        # 计算统计信息
        if self.history:
            successful = [r for r in self.history if r.success]
            self.avg_latency = sum(r.latency_ms for r in successful) / len(successful) if successful else 0
            self.uptime_percent = len(successful) / len(self.history) * 100


class PingMonitor:
    """Ping 监控器"""
    
    def __init__(self, devices: Dict[str, str] = None, interval: int = 60, count: int = 3, timeout: int = 2):
        """
        初始化
        
        Args:
            devices: 设备字典 {hostname: ip}
            interval: 监控间隔（秒）
            count: 每次 ping 的包数
            timeout: 超时时间（秒）
        """
        self.devices = devices or {}
        self.interval = interval
        self.count = count
        self.timeout = timeout
        
        # 设备状态
        self.status: Dict[str, DeviceStatus] = {}
        for hostname, ip in self.devices.items():
            self.status[hostname] = DeviceStatus(hostname=hostname, ip=ip)
        
        # 运行状态
        self._running = False
        self._task = None
    
    def add_device(self, hostname: str, ip: str):
        """添加设备"""
        self.devices[hostname] = ip
        self.status[hostname] = DeviceStatus(hostname=hostname, ip=ip)
    
    def remove_device(self, hostname: str):
        """移除设备"""
        if hostname in self.devices:
            del self.devices[hostname]
        if hostname in self.status:
            del self.status[hostname]
    
    async def ping(self, host: str) -> PingResult:
        """
        执行 ping
        
        Args:
            host: 目标 IP 或主机名
        
        Returns:
            PingResult
        """
        # Windows ping 命令
        # -n: 包数
        # -w: 超时（毫秒）
        cmd = ["ping", "-n", str(self.count), "-w", str(self.timeout * 1000), host]
        
        try:
            # 执行 ping
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout * self.count + 5
            )
            
            output = stdout.decode("gbk", errors="ignore")
            
            # 解析结果
            return self._parse_ping_output(host, output)
        
        except asyncio.TimeoutError:
            return PingResult(host=host, success=False, error="timeout")
        except Exception as e:
            return PingResult(host=host, success=False, error=str(e))
    
    def _parse_ping_output(self, host: str, output: str) -> PingResult:
        """解析 ping 输出"""
        # Windows ping 输出格式：
        # Reply from 192.168.1.1: bytes=32 time<1ms TTL=64
        # Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)
        # Minimum = 0ms, Maximum = 0ms, Average = 0ms
        
        # 检查是否有回复
        if "Reply from" not in output and "来自" not in output:
            return PingResult(host=host, success=False, error="no reply")
        
        # 解析延迟
        # 格式1: time=1ms 或 time<1ms
        # 格式2: 时间=1ms 或 时间<1ms
        latency = 0.0
        latency_match = re.search(r"(?:time|时间)[=<]?(\d+)ms", output, re.IGNORECASE)
        if latency_match:
            latency = float(latency_match.group(1))
        
        # 解析丢包率
        # 格式: Lost = 0 (0% loss) 或 丢失 = 0 (0% 丢失)
        packet_loss = 0.0
        loss_match = re.search(r"\((\d+)%\s*(?:loss|丢失)\)", output, re.IGNORECASE)
        if loss_match:
            packet_loss = float(loss_match.group(1))
        
        # 判断成功
        success = "Reply from" in output or "来自" in output
        success = success and packet_loss < 100
        
        return PingResult(
            host=host,
            success=success,
            latency_ms=latency,
            packet_loss=packet_loss,
        )
    
    async def check_all(self) -> Dict[str, PingResult]:
        """检查所有设备"""
        results = {}
        
        # 并发 ping 所有设备
        tasks = {hostname: self.ping(ip) for hostname, ip in self.devices.items()}
        
        if tasks:
            done = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            for (hostname, _), result in zip(tasks.items(), done):
                if isinstance(result, Exception):
                    results[hostname] = PingResult(
                        host=self.devices[hostname],
                        success=False,
                        error=str(result)
                    )
                else:
                    results[hostname] = result
                
                # 更新状态
                if hostname in self.status:
                    self.status[hostname].update(results[hostname])
        
        return results
    
    async def start(self):
        """启动监控"""
        self._running = True
        
        while self._running:
            await self.check_all()
            await asyncio.sleep(self.interval)
    
    def stop(self):
        """停止监控"""
        self._running = False
    
    def get_status(self, hostname: str = None) -> Dict:
        """获取状态"""
        if hostname:
            if hostname in self.status:
                s = self.status[hostname]
                return {
                    "hostname": s.hostname,
                    "ip": s.ip,
                    "is_online": s.is_online,
                    "avg_latency": round(s.avg_latency, 2),
                    "uptime_percent": round(s.uptime_percent, 2),
                    "last_ping": s.last_ping.to_dict() if s.last_ping else None,
                }
            return {}
        
        # 返回所有设备状态
        return {
            hostname: {
                "hostname": s.hostname,
                "ip": s.ip,
                "is_online": s.is_online,
                "avg_latency": round(s.avg_latency, 2),
                "uptime_percent": round(s.uptime_percent, 2),
            }
            for hostname, s in self.status.items()
        }
    
    def get_offline_devices(self) -> List[Dict]:
        """获取离线设备列表"""
        return [
            {
                "hostname": s.hostname,
                "ip": s.ip,
                "last_seen": s.last_ping.timestamp.isoformat() if s.last_ping else None,
            }
            for s in self.status.values()
            if not s.is_online
        ]
    
    def save_status(self, filepath: str):
        """保存状态到文件"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "devices": self.get_status(),
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_devices(self, filepath: str):
        """从文件加载设备列表"""
        if not os.path.exists(filepath):
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for device in data.get("devices", []):
            hostname = device.get("hostname")
            ip = device.get("ip")
            if hostname and ip:
                self.add_device(hostname, ip)


# 便捷函数
async def quick_ping(host: str, count: int = 3, timeout: int = 2) -> PingResult:
    """快速 ping 单个主机"""
    monitor = PingMonitor(count=count, timeout=timeout)
    return await monitor.ping(host)


async def check_network(hosts: List[str]) -> Dict[str, bool]:
    """检查多个主机的连通性"""
    monitor = PingMonitor()
    results = await asyncio.gather(*[monitor.ping(h) for h in hosts])
    return {h: r.success for h, r in zip(hosts, results)}
