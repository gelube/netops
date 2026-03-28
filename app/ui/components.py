"""
拓扑画布组件
支持缩放、平移、焦点、设备节点渲染
"""
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
import math

from app.core.device import Topology, Device, Link, PortType, DeviceType
from app.ui.styles import (
    HacknetColors, HacknetStyles, DEVICE_ICONS, get_link_symbol
)


@dataclass
class Viewport:
    """视口状态"""
    offset_x: float = 0
    offset_y: float = 0
    scale: float = 1.0  # 缩放比例
    
    MIN_SCALE = 0.25
    MAX_SCALE = 4.0
    
    def zoom_in(self) -> None:
        """放大"""
        self.scale = min(self.scale * 1.2, self.MAX_SCALE)
    
    def zoom_out(self) -> None:
        """缩小"""
        self.scale = max(self.scale / 1.2, self.MIN_SCALE)
    
    def reset(self) -> None:
        """重置"""
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0


@dataclass
class NodePosition:
    """节点位置"""
    device_id: str
    x: float
    y: float
    width: float = 10
    height: float = 6


class TopologyCanvas:
    """拓扑画布渲染器"""
    
    def __init__(self, topology: Topology):
        self.topology = topology
        self.viewport = Viewport()
        self.focused_device_id: Optional[str] = None
        self.node_positions: Dict[str, NodePosition] = {}
        
        # 自动布局
        self._auto_layout()
    
    def _auto_layout(self) -> None:
        """自动布局算法 - 简单的层级布局"""
        if not self.topology.devices:
            return
        
        # 找到根节点 (度为1的节点，或者第一个节点)
        root = self._find_root_device()
        
        # BFS布局
        visited = set()
        queue = [(root.id, 0, 0)]  # (device_id, level, position)
        visited.add(root.id)
        
        level_counts = {}  # 每层的节点数
        level_positions = {}  # 每层的位置计数
        
        node_width = 14
        node_height = 8
        level_gap = 18
        node_gap = 12
        
        while queue:
            device_id, level, _ = queue.pop(0)
            
            # 记录层级
            if level not in level_counts:
                level_counts[level] = 0
                level_positions[level] = 0
            
            pos = level_positions[level]
            level_positions[level] += 1
            
            # 计算位置
            x = 5 + level * (node_width + level_gap)
            y = 5 + pos * (node_height + node_gap)
            
            self.node_positions[device_id] = NodePosition(
                device_id=device_id,
                x=x,
                y=y
            )
            
            # 添加邻居到队列
            neighbors = self.topology.get_neighbors(device_id)
            for neighbor in neighbors:
                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    queue.append((neighbor.id, level + 1, 0))
        
        # 处理未连接的设备
        for device in self.topology.devices:
            if device.id not in self.node_positions:
                # 放到右侧
                x = 200
                y = 5 + len(self.node_positions) * (node_height + node_gap)
                self.node_positions[device.id] = NodePosition(
                    device_id=device.id,
                    x=x,
                    y=y
                )
    
    def _find_root_device(self) -> Device:
        """找到根节点"""
        if not self.topology.devices:
            return None
        
        # 找度数最小的
        min_degree = float('inf')
        root = self.topology.devices[0]
        
        for device in self.topology.devices:
            degree = len(self.topology.get_neighbors(device.id))
            if degree < min_degree:
                min_degree = degree
                root = device
        
        return root
    
    def focus_next(self) -> None:
        """焦点切换到下一个设备"""
        if not self.topology.devices:
            return
        
        if self.focused_device_id is None:
            self.focused_device_id = self.topology.devices[0].id
            return
        
        # 找到当前焦点索引
        ids = [d.id for d in self.topology.devices]
        try:
            idx = ids.index(self.focused_device_id)
            self.focused_device_id = ids[(idx + 1) % len(ids)]
        except ValueError:
            self.focused_device_id = ids[0]
    
    def focus_previous(self) -> None:
        """焦点切换到上一个设备"""
        if not self.topology.devices:
            return
        
        if self.focused_device_id is None:
            self.focused_device_id = self.topology.devices[-1].id
            return
        
        ids = [d.id for d in self.topology.devices]
        try:
            idx = ids.index(self.focused_device_id)
            self.focused_device_id = ids[(idx - 1) % len(ids)]
        except ValueError:
            self.focused_device_id = ids[0]
    
    def get_focused_device(self) -> Optional[Device]:
        """获取焦点设备"""
        if self.focused_device_id:
            return self.topology.get_device(self.focused_device_id)
        return None
    
    def render(self, canvas_width: int, canvas_height: int) -> List[str]:
        """
        渲染拓扑图到字符画布
        
        Returns:
            行列表
        """
        # 创建空画布
        canvas = [[' ' for _ in range(canvas_width)] for _ in range(canvas_height)]
        
        # 渲染链路
        self._render_links(canvas, canvas_width, canvas_height)
        
        # 渲染设备节点
        self._render_nodes(canvas, canvas_width, canvas_height)
        
        # 转换为字符串
        lines = [''.join(row) for row in canvas]
        
        return lines
    
    def _render_links(self, canvas: List[List[str]], width: int, height: int) -> None:
        """渲染链路"""
        for link in self.topology.links:
            source_pos = self.node_positions.get(link.source_device)
            target_pos = self.node_positions.get(link.target_device)
            
            if not source_pos or not target_pos:
                continue
            
            # 获取链路符号
            symbol = get_link_symbol(link.link_type)
            
            # 计算线条位置 (简单直线)
            x1 = int(source_pos.x + source_pos.width / 2)
            y1 = int(source_pos.y + source_pos.height / 2)
            x2 = int(target_pos.x + target_pos.width / 2)
            y2 = int(target_pos.y + target_pos.height / 2)
            
            # 获取颜色
            link_color = HacknetStyles.get_link_style(link.link_type)
            
            # 绘制直线
            self._draw_line(canvas, x1, y1, x2, y2, symbol[0], link_color)
            
            # 在链路中点显示链路类型
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            if 0 <= mid_y < height and 0 <= mid_x < width:
                # 简化的链路标识
                if link.port_type == PortType.AGGREGATE:
                    self._put_char(canvas, mid_x, mid_y, "AP", link_color)
                elif link.link_type in ["vrrp", "hsrp"]:
                    self._put_char(canvas, mid_x, mid_y, "VRRP", link_color)
    
    def _draw_line(self, canvas: List[List[str]], x1: int, y1: int, 
                   x2: int, y2: int, char: str, color: str) -> None:
        """绘制直线 (简单Bresenham)"""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        
        while True:
            if 0 <= y1 < len(canvas) and 0 <= x1 < len(canvas[0]):
                canvas[y1][x1] = char
            
            if x1 == x2 and y1 == y2:
                break
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy
    
    def _render_nodes(self, canvas: List[List[str]], width: int, height: int) -> None:
        """渲染设备节点"""
        for device in self.topology.devices:
            pos = self.node_positions.get(device.id)
            if not pos:
                continue
            
            # 缩放变换
            scaled_x = int(pos.x * self.viewport.scale + self.viewport.offset_x)
            scaled_y = int(pos.y * self.viewport.scale + self.viewport.offset_y)
            scaled_w = int(pos.width * self.viewport.scale)
            scaled_h = int(pos.height * self.viewport.scale)
            
            # 视口裁剪
            if scaled_x < 0 or scaled_x >= width or scaled_y < 0 or scaled_y >= height:
                continue
            
            # 获取节点颜色
            is_focused = device.id == self.focused_device_id
            node_color = HacknetStyles.get_node_color(device.device_type.value)
            if is_focused:
                node_color = HacknetColors.FOCUS
            
            # 渲染设备信息
            self._render_device_node(canvas, device, scaled_x, scaled_y, 
                                    scaled_w, scaled_h, node_color, is_focused)
    
    def _render_device_node(self, canvas: List[List[str]], device: Device,
                           x: int, y: int, width: int, height: int,
                           color: str, is_focused: bool) -> None:
        """渲染单个设备节点"""
        # 获取设备图标
        icon = DEVICE_ICONS.get(device.device_type.value, DEVICE_ICONS["unknown"])
        icon_lines = icon.split('\n')
        
        # 渲染图标
        for i, line in enumerate(icon_lines):
            if y + i < len(canvas) and x < len(canvas[0]):
                for j, char in enumerate(line):
                    if x + j < len(canvas[0]):
                        canvas[y + i][x + j] = char
        
        # 渲染设备信息
        info_y = y + len(icon_lines) + 1
        
        # 设备名称/IP
        name_text = device.name if device.name else device.ip
        if len(name_text) > width:
            name_text = name_text[:width-2] + ".."
        
        for i, char in enumerate(name_text):
            if info_y < len(canvas) and x + i < len(canvas[0]):
                canvas[info_y][x + i] = char
        
        # IP地址
        ip_text = device.ip
        if len(ip_text) > width:
            ip_text = ip_text[:width-2] + ".."
        
        for i, char in enumerate(ip_text):
            if info_y + 1 < len(canvas) and x + i < len(canvas[0]):
                canvas[info_y + 1][x + i] = char
        
        # VRRP标识
        if device.vrrp_master:
            vrrp_text = "◈ VRRP"
            for i, char in enumerate(vrrp_text):
                if info_y + 2 < len(canvas) and x + i < len(canvas[0]):
                    canvas[info_y + 2][x + i] = char
        
        # 焦点边框
        if is_focused:
            # 绘制边框
            border_char = "╔" if x > 0 and y > 0 else "┌"
            # 简化: 只画角标
            if 0 <= y < len(canvas) and 0 <= x < len(canvas[0]):
                canvas[y][x] = "┌"
            if 0 <= y < len(canvas) and x + width - 1 < len(canvas[0]):
                canvas[y][x + width - 1] = "┐"
            if y + height < len(canvas) and 0 <= x < len(canvas[0]):
                canvas[y + height - 1][x] = "└"
            if y + height < len(canvas) and x + width - 1 < len(canvas[0]):
                canvas[y + height - 1][x + width - 1] = "┘"
    
    def _put_char(self, canvas: List[List[str]], x: int, y: int, text: str, color: str) -> None:
        """在画布上放置字符"""
        for i, char in enumerate(text):
            if 0 <= y < len(canvas) and 0 <= x + i < len(canvas[0]):
                canvas[y][x + i] = char


class DeviceDetailRenderer:
    """设备详情面板渲染器"""
    
    @staticmethod
    def render(device: Device, width: int) -> List[str]:
        """渲染设备详情"""
        lines = []
        
        # 标题
        lines.append("┌" + "─" * (width - 2) + "┐")
        title = f" DEVICE: {device.name or device.ip} "
        lines.append("│" + title + " " * (width - 2 - len(title)) + "│")
        lines.append("├" + "─" * (width - 2) + "┤")
        
        # 基本信息
        lines.append(f"│  Name:     {device.name:<{width - 17}}│")
        lines.append(f"│  IP:       {device.ip:<{width - 17}}│")
        lines.append(f"│  Vendor:   {device.vendor.value:<{width - 17}}│")
        lines.append(f"│  Model:    {device.model:<{width - 17}}│")
        lines.append(f"│  Type:     {device.device_type.value:<{width - 17}}│")
        lines.append(f"│  OS:       {device.os_version:<{width - 17}}│")
        
        # 分隔
        lines.append("├" + "─" * (width - 2) + "┤")
        
        # 接口信息标题
        interface_header = " INTERFACES "
        lines.append("│" + interface_header + " " * (width - 2 - len(interface_header)) + "│")
        
        # 表头
        lines.append("│  " + "-" * (width - 4) + "│")
        lines.append(f"│  {'Interface':<15} {'IP':<18} {'Type':<12} {'Status':<8}│")
        lines.append("│  " + "-" * (width - 4) + "│")
        
        # 接口列表
        for iface in device.interfaces[:10]:  # 最多显示10个
            name = iface.name[:14]
            ip = (iface.ip or "-")[:17]
            ptype = iface.port_type.value[:11]
            status = iface.status.value[:7]
            lines.append(f"│  {name:<15} {ip:<18} {ptype:<12} {status:<8}│")
        
        # 底部
        lines.append("└" + "─" * (width - 2) + "┘")
        
        return lines