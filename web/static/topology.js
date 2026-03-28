/**
 * NetOps AI - 拓扑画布
 * Hacknet风格网络拓扑可视化
 */

class TopologyCanvas {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        
        // 拓扑数据
        this.devices = [];
        this.links = [];
        
        // 视图状态
        this.offsetX = 0;
        this.offsetY = 0;
        this.scale = 1;
        this.focusedDeviceId = null;
        
        // 节点位置缓存
        this.nodePositions = {};
        
        // 动画帧
        this.animationFrame = null;
        this.pulsePhase = 0;
        
        // 绑定事件
        this.bindEvents();
        
        // 初始化画布
        this.resize();
        this.startAnimation();
        
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        
        // 重新布局
        if (this.devices.length > 0) {
            this.layout();
        }
    }
    
    bindEvents() {
        // 鼠标事件
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.onMouseUp());
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e));
        this.canvas.addEventListener('click', (e) => this.onClick(e));
        this.canvas.addEventListener('dblclick', (e) => this.onDoubleClick(e));
        
        // 键盘事件
        document.addEventListener('keydown', (e) => this.onKeyDown(e));
        
        // 拖拽状态
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
    }
    
    setData(devices, links) {
        this.devices = devices;
        this.links = links;
        this.layout();
        this.updateCounts();
    }
    
    // 简单的层级布局算法
    layout() {
        if (this.devices.length === 0) return;
        
        const nodeWidth = 80;
        const nodeHeight = 60;
        const levelGap = 150;
        const nodeGap = 100;
        
        // 找到根节点（连接数最少的）
        let rootDevice = this.devices[0];
        let minConnections = Infinity;
        
        for (const device of this.devices) {
            const connCount = this.getConnectionCount(device.id);
            if (connCount < minConnections) {
                minConnections = connCount;
                rootDevice = device;
            }
        }
        
        // BFS布局
        const visited = new Set();
        const queue = [{ id: rootDevice.id, level: 0, pos: 0 }];
        visited.add(rootDevice.id);
        
        const levelCounts = {};
        const levelPositions = {};
        
        while (queue.length > 0) {
            const { id, level, pos } = queue.shift();
            
            if (!levelCounts[level]) {
                levelCounts[level] = 0;
                levelPositions[level] = 0;
            }
            
            const p = levelPositions[level];
            levelPositions[level]++;
            
            const x = 100 + level * levelGap;
            const y = 100 + p * nodeGap;
            
            this.nodePositions[id] = { x, y, width: nodeWidth, height: nodeHeight };
            
            // 添加邻居
            const neighbors = this.getNeighbors(id);
            for (const neighbor of neighbors) {
                if (!visited.has(neighbor.id)) {
                    visited.add(neighbor.id);
                    queue.push({ id: neighbor.id, level: level + 1, pos: 0 });
                }
            }
        }
        
        // 处理未连接的设备
        let orphanY = 100;
        for (const device of this.devices) {
            if (!this.nodePositions[device.id]) {
                this.nodePositions[device.id] = { 
                    x: this.canvas.width - 150, 
                    y: orphanY, 
                    width: nodeWidth, 
                    height: nodeHeight 
                };
                orphanY += nodeGap;
            }
        }
    }
    
    getConnectionCount(deviceId) {
        let count = 0;
        for (const link of this.links) {
            if (link.source === deviceId || link.target === deviceId) {
                count++;
            }
        }
        return count;
    }
    
    getNeighbors(deviceId) {
        const neighbors = [];
        for (const link of this.links) {
            if (link.source === deviceId) {
                const dev = this.devices.find(d => d.id === link.target);
                if (dev) neighbors.push(dev);
            } else if (link.target === deviceId) {
                const dev = this.devices.find(d => d.id === link.source);
                if (dev) neighbors.push(dev);
            }
        }
        return neighbors;
    }
    
    startAnimation() {
        const animate = () => {
            this.pulsePhase += 0.05;
            this.render();
            this.animationFrame = requestAnimationFrame(animate);
        };
        animate();
    }
    
    stopAnimation() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
    }
    
    render() {
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;
        
        // 清空画布
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, width, height);
        
        // 绘制网格
        this.drawGrid();
        
        // 应用变换
        ctx.save();
        ctx.translate(this.offsetX, this.offsetY);
        ctx.scale(this.scale, this.scale);
        
        // 绘制链路
        this.drawLinks();
        
        // 绘制节点
        this.drawNodes();
        
        ctx.restore();
    }
    
    drawGrid() {
        const ctx = this.ctx;
        const gridSize = 20;
        
        ctx.strokeStyle = 'rgba(0, 255, 0, 0.03)';
        ctx.lineWidth = 1;
        
        for (let x = 0; x < this.canvas.width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.canvas.height);
            ctx.stroke();
        }
        
        for (let y = 0; y < this.canvas.height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.canvas.width, y);
            ctx.stroke();
        }
    }
    
    drawLinks() {
        const ctx = this.ctx;
        
        for (const link of this.links) {
            const sourcePos = this.nodePositions[link.source];
            const targetPos = this.nodePositions[link.target];
            
            if (!sourcePos || !targetPos) continue;
            
            const x1 = sourcePos.x + sourcePos.width / 2;
            const y1 = sourcePos.y + sourcePos.height / 2;
            const x2 = targetPos.x + targetPos.width / 2;
            const y2 = targetPos.y + targetPos.height / 2;
            
            // 获取链路样式
            const linkStyle = this.getLinkStyle(link.link_type);
            
            ctx.strokeStyle = linkStyle.color;
            ctx.lineWidth = 2;
            
            // 聚合链路用粗线
            if (link.port_type === 'aggregate') {
                ctx.lineWidth = 4;
            }
            
            // 虚线样式
            if (linkStyle.dashed) {
                ctx.setLineDash([8, 4]);
            } else {
                ctx.setLineDash([]);
            }
            
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
            ctx.setLineDash([]);
            
            // 链路中点标签
            const midX = (x1 + x2) / 2;
            const midY = (y1 + y2) / 2;
            
            if (link.port_type === 'aggregate') {
                ctx.fillStyle = '#00ffff';
                ctx.font = '10px Consolas';
                ctx.fillText('AP', midX - 8, midY - 5);
            } else if (link.link_type === 'vrrp') {
                ctx.fillStyle = '#ff00ff';
                ctx.font = '10px Consolas';
                ctx.fillText('VRRP', midX - 20, midY - 5);
            }
        }
    }
    
    getLinkStyle(linkType) {
        const styles = {
            physical: { color: '#00ff00', dashed: false },
            aggregate: { color: '#00ffff', dashed: false },
            vrrp: { color: '#ff00ff', dashed: false },
            hsrp: { color: '#ff00ff', dashed: false },
            stack: { color: '#ffaa00', dashed: false },
            ospf: { color: '#00ff00', dashed: true },
            bgp: { color: '#00ff00', dashed: true },
            vpn: { color: '#884488', dashed: true },
            tunnel: { color: '#884488', dashed: true },
        };
        return styles[linkType] || styles.physical;
    }
    
    drawNodes() {
        const ctx = this.ctx;
        
        for (const device of this.devices) {
            const pos = this.nodePositions[device.id];
            if (!pos) continue;
            
            const isFocused = device.id === this.focusedDeviceId;
            const nodeStyle = this.getNodeStyle(device.device_type);
            
            // 焦点发光效果
            if (isFocused) {
                ctx.shadowColor = nodeStyle.color;
                ctx.shadowBlur = 15;
            }
            
            // 绘制设备图标
            this.drawDeviceIcon(pos.x, pos.y, pos.width, pos.height, device.device_type, nodeStyle.color, isFocused);
            
            // 绘制标签
            ctx.shadowBlur = 0;
            ctx.fillStyle = isFocused ? '#00ffff' : '#00ff00';
            ctx.font = 'bold 12px Consolas';
            ctx.textAlign = 'center';
            ctx.fillText(device.name || device.ip, pos.x + pos.width / 2, pos.y + pos.height + 15);
            
            ctx.fillStyle = '#008800';
            ctx.font = '10px Consolas';
            ctx.fillText(device.ip, pos.x + pos.width / 2, pos.y + pos.height + 28);
            
            // 设备类型
            ctx.fillStyle = nodeStyle.color;
            ctx.font = '9px Consolas';
            const typeName = this.getDeviceTypeName(device.device_type);
            ctx.fillText(typeName, pos.x + pos.width / 2, pos.y + pos.height + 40);
            
            // VRRP标识
            if (device.vrrp_master) {
                ctx.fillStyle = '#ff00ff';
                ctx.font = '10px Consolas';
                ctx.fillText('◈ VRRP', pos.x + pos.width / 2, pos.y - 10);
            }
        }
    }
    
    drawDeviceIcon(x, y, width, height, deviceType, color, isFocused) {
        const ctx = this.ctx;
        
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        
        const cx = x + width / 2;
        const cy = y + height / 2;
        const r = Math.min(width, height) / 2 - 5;
        
        if (deviceType === 'router') {
            // 路由器 - 圆形带点
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.stroke();
            
            // 中心点 - 呼吸效果
            const pulseR = r * 0.3 * (0.8 + 0.2 * Math.sin(this.pulsePhase));
            ctx.globalAlpha = 0.3 + 0.2 * Math.sin(this.pulsePhase);
            ctx.beginPath();
            ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalAlpha = 1;
            
            // 十字
            ctx.beginPath();
            ctx.moveTo(cx - r * 0.5, cy);
            ctx.lineTo(cx + r * 0.5, cy);
            ctx.moveTo(cx, cy - r * 0.5);
            ctx.lineTo(cx, cy + r * 0.5);
            ctx.stroke();
            
        } else if (deviceType === 'switch_l2' || deviceType === 'switch_l3') {
            // 交换机 - 方块带点
            const boxSize = r * 1.5;
            ctx.strokeRect(cx - boxSize / 2, cy - boxSize / 2, boxSize, boxSize);
            
            // 中心点
            ctx.globalAlpha = 0.3;
            ctx.fillRect(cx - 5, cy - 5, 10, 10);
            ctx.globalAlpha = 1;
            
            // 四个角点
            const cornerR = 3;
            ctx.fillRect(cx - boxSize / 2 - cornerR / 2, cy - boxSize / 2 - cornerR / 2, cornerR, cornerR);
            ctx.fillRect(cx + boxSize / 2 - cornerR / 2, cy - boxSize / 2 - cornerR / 2, cornerR, cornerR);
            ctx.fillRect(cx - boxSize / 2 - cornerR / 2, cy + boxSize / 2 - cornerR / 2, cornerR, cornerR);
            ctx.fillRect(cx + boxSize / 2 - cornerR / 2, cy + boxSize / 2 - cornerR / 2, cornerR, cornerR);
            
        } else if (deviceType === 'firewall') {
            // 防火墙 - 盾牌
            ctx.beginPath();
            ctx.moveTo(cx, cy - r);
            ctx.lineTo(cx + r, cy - r * 0.5);
            ctx.lineTo(cx + r, cy + r * 0.3);
            ctx.quadraticCurveTo(cx, cy + r, cx, cy + r * 0.3);
            ctx.quadraticCurveTo(cx, cy + r, cx - r, cy + r * 0.3);
            ctx.lineTo(cx - r, cy - r * 0.5);
            ctx.closePath();
            ctx.stroke();
            
            // 内部条纹
            ctx.globalAlpha = 0.3;
            ctx.fill();
            ctx.globalAlpha = 1;
            
        } else if (deviceType === 'server') {
            // 服务器 - 方形带线条
            const boxW = r * 1.4;
            const boxH = r * 1.2;
            ctx.strokeRect(cx - boxW / 2, cy - boxH / 2, boxW, boxH);
            
            // 内部线条
            ctx.globalAlpha = 0.3;
            ctx.beginPath();
            ctx.moveTo(cx - boxW / 2 + 5, cy - boxH / 2 + 5);
            ctx.lineTo(cx + boxW / 2 - 5, cy - boxH / 2 + 5);
            ctx.lineTo(cx + boxW / 2 - 5, cy + boxH / 2 - 5);
            ctx.lineTo(cx - boxW / 2 + 5, cy + boxH / 2 - 5);
            ctx.closePath();
            ctx.fill();
            ctx.globalAlpha = 1;
            
        } else {
            // 默认 - 问号方块
            const boxSize = r * 1.3;
            ctx.strokeRect(cx - boxSize / 2, cy - boxSize / 2, boxSize, boxSize);
            ctx.font = '16px Consolas';
            ctx.fillText('?', cx, cy + 5);
        }
    }
    
    getNodeStyle(deviceType) {
        const styles = {
            router: { color: '#00ffff' },
            switch_l3: { color: '#00ff00' },
            switch_l2: { color: '#00ff00' },
            firewall: { color: '#ff6600' },
            server: { color: '#ff00ff' },
            unknown: { color: '#888888' },
        };
        return styles[deviceType] || styles.unknown;
    }
    
    getDeviceTypeName(deviceType) {
        const names = {
            router: 'ROUTER',
            switch_l3: 'L3 SWITCH',
            switch_l2: 'L2 SWITCH',
            firewall: 'FIREWALL',
            server: 'SERVER',
            unknown: 'UNKNOWN',
        };
        return names[deviceType] || 'UNKNOWN';
    }
    
    // 事件处理
    onMouseDown(e) {
        this.isDragging = true;
        this.dragStartX = e.clientX - this.offsetX;
        this.dragStartY = e.clientY - this.offsetY;
        this.canvas.style.cursor = 'grabbing';
    }
    
    onMouseMove(e) {
        if (this.isDragging) {
            this.offsetX = e.clientX - this.dragStartX;
            this.offsetY = e.clientY - this.dragStartY;
        }
    }
    
    onMouseUp() {
        this.isDragging = false;
        this.canvas.style.cursor = 'default';
    }
    
    onWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(0.25, Math.min(4, this.scale * delta));
        
        // 以鼠标位置为中心缩放
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        this.offsetX = mouseX - (mouseX - this.offsetX) * (newScale / this.scale);
        this.offsetY = mouseY - (mouseY - this.offsetY) * (newScale / this.scale);
        this.scale = newScale;
        
        this.updateZoomDisplay();
    }
    
    onClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - this.offsetX) / this.scale;
        const y = (e.clientY - rect.top - this.offsetY) / this.scale;
        
        // 检查点击是否在节点上
        for (const device of this.devices) {
            const pos = this.nodePositions[device.id];
            if (pos && x >= pos.x && x <= pos.x + pos.width &&
                y >= pos.y && y <= pos.y + pos.height) {
                this.focusedDeviceId = device.id;
                this.showDeviceDetail(device);
                return;
            }
        }
        
        this.focusedDeviceId = null;
    }
    
    onDoubleClick(e) {
        // 双击放大到适应
        this.fitToView();
    }
    
    onKeyDown(e) {
        switch (e.key) {
            case 'Tab':
                e.preventDefault();
                this.focusNext();
                break;
            case 'Enter':
                if (this.focusedDeviceId) {
                    const device = this.devices.find(d => d.id === this.focusedDeviceId);
                    if (device) this.showDeviceDetail(device);
                }
                break;
            case 'ArrowUp':
                this.offsetY += 50;
                break;
            case 'ArrowDown':
                this.offsetY -= 50;
                break;
            case 'ArrowLeft':
                this.offsetX += 50;
                break;
            case 'ArrowRight':
                this.offsetX -= 50;
                break;
            case '+':
            case '=':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.zoomIn();
                }
                break;
            case '-':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.zoomOut();
                }
                break;
            case '0':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.zoomReset();
                }
                break;
        }
    }
    
    focusNext() {
        if (this.devices.length === 0) return;
        
        if (!this.focusedDeviceId) {
            this.focusedDeviceId = this.devices[0].id;
            return;
        }
        
        const idx = this.devices.findIndex(d => d.id === this.focusedDeviceId);
        this.focusedDeviceId = this.devices[(idx + 1) % this.devices.length].id;
        
        // 更新设备列表焦点
        updateDeviceListFocus(this.focusedDeviceId);
    }
    
    showDeviceDetail(device) {
        const panel = document.getElementById('detail-panel');
        const content = document.getElementById('detail-content');
        
        let html = `
            <div class="detail-item">
                <div class="detail-label">名称</div>
                <div class="detail-value">${device.name || '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">IP地址</div>
                <div class="detail-value">${device.ip}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">厂商</div>
                <div class="detail-value">${device.vendor}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">型号</div>
                <div class="detail-value">${device.model || '-'}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">设备类型</div>
                <div class="detail-value">${this.getDeviceTypeName(device.device_type)}</div>
            </div>
            <div class="detail-item">
                <div class="detail-label">OS版本</div>
                <div class="detail-value">${device.os_version || '-'}</div>
            </div>
        `;
        
        if (device.interfaces && device.interfaces.length > 0) {
            html += `<div class="detail-section">
                <div class="detail-label">接口信息</div>
                <table class="interface-table">
                    <tr><th>接口</th><th>IP</th><th>类型</th><th>状态</th></tr>`;
            
            for (const iface of device.interfaces.slice(0, 10)) {
                html += `<tr>
                    <td>${iface.name}</td>
                    <td>${iface.ip || '-'}</td>
                    <td>${iface.port_type}</td>
                    <td style="color: ${iface.status === 'up' ? '#00ff00' : '#ff0000'}">${iface.status}</td>
                </tr>`;
            }
            
            html += `</table></div>`;
        }
        
        content.innerHTML = html;
        panel.style.display = 'block';
        
        // 更新设备列表焦点
        updateDeviceListFocus(device.id);
    }
    
    zoomIn() {
        this.scale = Math.min(4, this.scale * 1.2);
        this.updateZoomDisplay();
    }
    
    zoomOut() {
        this.scale = Math.max(0.25, this.scale / 1.2);
        this.updateZoomDisplay();
    }
    
    zoomReset() {
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.updateZoomDisplay();
    }
    
    fitToView() {
        if (this.devices.length === 0) return;
        
        // 计算边界
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        for (const pos of Object.values(this.nodePositions)) {
            minX = Math.min(minX, pos.x);
            minY = Math.min(minY, pos.y);
            maxX = Math.max(maxX, pos.x + pos.width);
            maxY = Math.max(maxY, pos.y + pos.height);
        }
        
        const contentWidth = maxX - minX + 100;
        const contentHeight = maxY - minY + 100;
        
        const scaleX = this.canvas.width / contentWidth;
        const scaleY = this.canvas.height / contentHeight;
        
        this.scale = Math.min(scaleX, scaleY, 1);
        this.offsetX = (this.canvas.width - contentWidth * this.scale) / 2 - minX * this.scale + 50;
        this.offsetY = (this.canvas.height - contentHeight * this.scale) / 2 - minY * this.scale + 50;
        
        this.updateZoomDisplay();
    }
    
    updateZoomDisplay() {
        document.getElementById('zoom-level').textContent = `缩放: ${Math.round(this.scale * 100)}%`;
    }
    
    updateCounts() {
        document.getElementById('device-count').textContent = `设备: ${this.devices.length}`;
        document.getElementById('link-count').textContent = `链路: ${this.links.length}`;
    }
}

// 全局变量
let topologyCanvas;
let socket;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 创建拓扑画布
    topologyCanvas = new TopologyCanvas('topology-canvas');
    
    // 初始化Socket.IO
    socket = io();
    
    socket.on('discovery_complete', (data) => {
        document.getElementById('loading').style.display = 'none';
        
        if (data.success) {
            const topo = data.topology;
            topologyCanvas.setData(topo.devices, topo.links);
            updateDeviceList(topo.devices);
            document.getElementById('status').textContent = '发现完成';
        } else {
            alert('发现失败: ' + data.message);
            document.getElementById('status').textContent = '发现失败';
        }
    });
    
    // 绑定UI事件
    bindUIEvents();
});

function bindUIEvents() {
    // 添加设备按钮
    document.getElementById('btn-add-device').addEventListener('click', () => {
        document.getElementById('add-device-modal').classList.add('active');
    });
    
    // 连接方式切换
    document.querySelectorAll('.btn-connect-type').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.btn-connect-type').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const type = btn.dataset.type;
            const portGroup = document.getElementById('port-group');
            if (type === 'telnet') {
                portGroup.style.display = 'block';
                document.getElementById('device-port').value = '23';
            } else if (type === 'ssh') {
                portGroup.style.display = 'block';
                document.getElementById('device-port').value = '22';
            } else {
                portGroup.style.display = 'none';
            }
        });
    });
    
    // 添加设备
    document.getElementById('btn-add').addEventListener('click', () => {
        const connectType = document.querySelector('.btn-connect-type.active').dataset.type;
        const deviceIp = document.getElementById('device-ip').value;
        const port = document.getElementById('device-port').value || (connectType === 'ssh' ? '22' : '23');
        const username = document.getElementById('device-username').value;
        const password = document.getElementById('device-password').value;
        const autoDiscover = document.getElementById('auto-discover-neighbors').checked;
        
        console.log('前端发送: connectType=' + connectType + ', ip=' + deviceIp + ', port=' + port);
        
        if (!deviceIp) {
            alert('请输入设备IP');
            return;
        }
        
        document.getElementById('add-device-modal').classList.remove('active');
        document.getElementById('loading').style.display = 'block';
        document.getElementById('status').textContent = '正在添加设备...';
        
        fetch('/api/device/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_ip: deviceIp,
                connect_type: connectType,
                port: port,
                username: username,
                password: password,
                auto_discover: autoDiscover
            })
        })
        .then(res => res.json())
        .then(data => {
            document.getElementById('loading').style.display = 'none';
            if (data.success) {
                document.getElementById('status').textContent = data.message;
                // 更新拓扑
                if (data.topology) {
                    topologyCanvas.setData(data.topology.devices, data.topology.links);
                    updateDeviceList(data.topology.devices);
                    document.getElementById('device-count').textContent = `设备: ${data.topology.device_count}`;
                    document.getElementById('link-count').textContent = `链路: ${data.topology.link_count}`;
                }
            } else {
                alert('添加失败: ' + data.message);
                document.getElementById('status').textContent = '添加失败';
            }
        })
        .catch(err => {
            document.getElementById('loading').style.display = 'none';
            alert('添加失败: ' + err);
            document.getElementById('status').textContent = '添加失败';
        });
    });
    
    // 关闭添加设备对话框
    document.getElementById('btn-close-add-device').addEventListener('click', () => {
        document.getElementById('add-device-modal').classList.remove('active');
    });
    
    document.getElementById('btn-cancel-add').addEventListener('click', () => {
        document.getElementById('add-device-modal').classList.remove('active');
    });
    
    // 设置按钮
    document.getElementById('btn-settings').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.add('active');
    });
    
    // 缩放按钮
    document.getElementById('btn-zoom-in').addEventListener('click', () => topologyCanvas.zoomIn());
    document.getElementById('btn-zoom-out').addEventListener('click', () => topologyCanvas.zoomOut());
    document.getElementById('btn-zoom-reset').addEventListener('click', () => topologyCanvas.zoomReset());
    
    // 关闭对话框
    document.getElementById('btn-close-settings').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.remove('active');
    });
    
    document.getElementById('btn-close-detail').addEventListener('click', () => {
        document.getElementById('detail-panel').style.display = 'none';
    });
    
    // 开始发现
    document.getElementById('btn-start-discovery').addEventListener('click', () => {
        const seedIp = document.getElementById('seed-ip').value;
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        if (!seedIp || !username || !password) {
            alert('请填写所有字段');
            return;
        }
        
        document.getElementById('discover-modal').classList.remove('active');
        document.getElementById('loading').style.display = 'block';
        document.getElementById('status').textContent = '正在发现...';
        
        fetch('/api/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ seed_ip: seedIp, username, password })
        });
    });
    
    // LLM设置
    document.querySelectorAll('.btn-provider').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.btn-provider').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 根据选择设置默认 endpoint
            const provider = btn.dataset.provider;
            const endpointInput = document.getElementById('api-endpoint');
            if (provider === 'aliyun') {
                endpointInput.value = 'https://dashscope.aliyuncs.com/compatible-mode/v1';
            } else if (provider === 'openai') {
                endpointInput.value = 'https://api.openai.com/v1';
            } else if (provider === 'anthropic') {
                endpointInput.value = 'https://api.anthropic.com/v1';
            }
        });
    });
    
    // AI对话 - 发送按钮
    document.getElementById('btn-send').addEventListener('click', sendChatMessage);
    
    // AI对话 - Enter键发送
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendChatMessage();
        }
    });
    
    // 关闭聊天面板
    document.getElementById('btn-close-chat').addEventListener('click', () => {
        document.getElementById('chat-panel').classList.add('hidden');
    });
    
    // 显示聊天面板按钮
    document.getElementById('btn-chat').addEventListener('click', () => {
        document.getElementById('chat-panel').classList.remove('hidden');
    });
}

// 聊天功能
function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // 添加用户消息
    addChatMessage(message, 'user');
    input.value = '';
    
    // 发送请求
    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            addChatMessage(data.message, 'ai');
        } else {
            addChatMessage('抱歉，出错了: ' + data.message, 'ai');
        }
    })
    .catch(err => {
        addChatMessage('网络错误，请稍后重试', 'ai');
    });
}

function addChatMessage(content, role) {
    const container = document.getElementById('chat-messages');
    
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = content.replace(/\n/g, '<br>');
    
    msgDiv.appendChild(contentDiv);
    container.appendChild(msgDiv);
    
    // 滚动到底部
    container.scrollTop = container.scrollHeight;
    
    // 更新设备计数
    if (role === 'ai' && content.includes('当前网络拓扑')) {
        const deviceCount = document.querySelectorAll('.device-item').length;
        document.getElementById('chat-device-count').textContent = deviceCount;
    }
}

// 绑定聊天事件
document.getElementById('btn-send')?.addEventListener('click', sendChatMessage);
document.getElementById('chat-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendChatMessage();
    }
});


function updateDeviceList(devices) {
    const list = document.getElementById('device-list');
    
    if (devices.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>暂无设备</p><p class="hint">点击"添加设备"开始</p></div>';
        return;
    }
    
    let html = '';
    for (const device of devices) {
        const vendorColors = {
            huawei: '#00ff00',
            cisco: '#00ffff',
            h3c: '#ffaa00',
            juniper: '#ff00ff',
            unknown: '#888888'
        };
        
        html += `
            <div class="device-item" data-id="${device.id}" onclick="focusDevice('${device.id}')">
                <div class="name">${device.name || device.ip}</div>
                <div class="ip">${device.ip}</div>
                <div class="vendor" style="color: ${vendorColors[device.vendor] || '#888888'}">${device.vendor} ${device.model || ''}</div>
                <button class="btn-delete" onclick="event.stopPropagation(); deleteDevice('${device.id}')" title="删除设备">×</button>
            </div>
        `;
    }
    
    list.innerHTML = html;
}

function updateDeviceListFocus(deviceId) {
    document.querySelectorAll('.device-item').forEach(item => {
        item.classList.remove('focused');
        if (item.dataset.id === deviceId) {
            item.classList.add('focused');
        }
    });
}

function focusDevice(deviceId) {
    topologyCanvas.focusedDeviceId = deviceId;
    
    const device = topologyCanvas.devices.find(d => d.id === deviceId);
    if (device) {
        topologyCanvas.showDeviceDetail(device);
    }
    
    updateDeviceListFocus(deviceId);
}

// ========== 设备管理功能 ==========
let savedDevicesList = [];

// 添加设备按钮
document.getElementById('btn-add-device').addEventListener('click', () => {
    document.getElementById('add-device-modal').classList.add('active');
});

// 删除设备函数
function deleteDevice(deviceId) {
    if (!confirm('确定要删除这个设备吗？')) {
        return;
    }
    
    fetch('/api/device/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            document.getElementById('status').textContent = data.message;
            if (data.topology) {
                topologyCanvas.setData(data.topology.devices, data.topology.links);
                updateDeviceList(data.topology.devices);
                document.getElementById('device-count').textContent = `设备: ${data.topology.device_count}`;
                document.getElementById('link-count').textContent = `链路: ${data.topology.link_count}`;
            }
        } else {
            alert('删除失败: ' + data.message);
        }
    })
    .catch(err => {
        alert('删除失败: ' + err);
    });
}

document.getElementById('btn-close-add-device').addEventListener('click', () => {
    document.getElementById('add-device-modal').classList.remove('active');
});

document.getElementById('btn-cancel-add-device').addEventListener('click', () => {
    document.getElementById('add-device-modal').classList.remove('active');
});

// 确认添加设备
document.getElementById('btn-confirm-add-device').addEventListener('click', async () => {
    const ip = document.getElementById('device-ip').value;
    const name = document.getElementById('device-name').value;
    const username = document.getElementById('device-username').value;
    const password = document.getElementById('device-password').value;
    
    if (!ip || !username || !password) {
        alert('请填写IP、用户名和密码');
        return;
    }
    
    document.getElementById('status').textContent = '正在连接设备...';
    
    try {
        const response = await fetch('/api/devices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, name, username, password })
        });
        
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('add-device-modal').classList.remove('active');
            // 刷新设备列表
            loadDevices();
            document.getElementById('status').textContent = '设备添加成功';
            addChatMessage('system', `设备 ${result.device.name} (${result.device.ip}) 添加成功，厂商: ${result.device.vendor}`);
        } else {
            alert('添加失败: ' + result.message);
            document.getElementById('status').textContent = '设备添加失败';
        }
    } catch (e) {
        alert('添加失败: ' + e);
        document.getElementById('status').textContent = '设备添加失败';
    }
});


// 开始发现邻居
document.getElementById('btn-start-neighbor-discovery').addEventListener('click', async () => {
    const selected = document.querySelector('input[name="neighbor-device"]:checked');
    if (!selected) {
        alert('请选择要发现邻居的设备');
        return;
    }
    
    const ip = selected.value;
    document.getElementById('status').textContent = '正在发现邻居...';
    
    try {
        const response = await fetch(`/api/devices/${ip}/discover_neighbors`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        document.getElementById('neighbors-result').style.display = 'block';
        const content = document.getElementById('neighbors-content');
        
        if (result.success) {
            let html = `<p>发现 ${result.neighbors.length} 个邻居：</p>`;
            result.neighbors.forEach(n => {
                html += `<div class="neighbor-item">
                    ${n.device_id} (${n.local_interface} → ${n.remote_interface})
                </div>`;
            });
            content.innerHTML = html;
            
            // 如果发现新邻居，添加到拓扑
            if (result.neighbors.length > 0) {
                const currentDevices = [...(topologyCanvas.devices || [])];
                const currentLinks = [...(topologyCanvas.links || [])];
                
                result.neighbors.forEach(n => {
                    // 检查是否已存在
                    if (!currentDevices.find(d => d.ip === n.device_id || d.id === n.device_id)) {
                        currentDevices.push({
                            id: n.device_id,
                            name: n.device_id,
                            ip: n.device_id,
                            vendor: 'unknown',
                            model: n.platform || '',
                            device_type: 'unknown'
                        });
                    }
                    
                    // 添加链路
                    currentLinks.push({
                        source: ip,
                        source_interface: n.local_interface,
                        target: n.device_id,
                        target_interface: n.remote_interface,
                        link_type: 'physical',
                        port_type: 'normal'
                    });
                });
                
                topologyCanvas.setData(currentDevices, currentLinks);
                updateDeviceList(currentDevices);
            }
            
            document.getElementById('status').textContent = '邻居发现完成';
            addChatMessage('system', `从设备 ${ip} 发现 ${result.neighbors.length} 个邻居`);
        } else {
            content.innerHTML = `<p style="color: #ff0000;">发现失败: ${result.message}</p>`;
            document.getElementById('status').textContent = '邻居发现失败';
        }
    } catch (e) {
        alert('发现失败: ' + e);
        document.getElementById('status').textContent = '邻居发现失败';
    }
});

// 加载设备列表
async function loadDevices() {
    try {
        const response = await fetch('/api/devices');
        const result = await response.json();
        
        if (result.success) {
            savedDevicesList = result.devices || [];
            
            // 更新拓扑
            const devices = savedDevicesList.map(d => ({
                id: d.ip,
                name: d.name,
                ip: d.ip,
                vendor: d.vendor,
                model: d.model || '',
                device_type: d.device_type,
                os_version: d.os_version || ''
            }));
            
            topologyCanvas.setData(devices, []);
            updateDeviceList(devices);
            document.getElementById('chat-device-count').textContent = devices.length;
        }
    } catch (e) {
        console.error('加载设备失败:', e);
    }
}

// 加载 LLM 状态
async function loadLLMStatus() {
    try {
        const response = await fetch('/api/llm/config');
        const data = await response.json();
        
        const statusEl = document.getElementById('llm-status');
        if (data.endpoint && data.endpoint !== 'https://api.openai.com/v1') {
            statusEl.textContent = `LLM: ${data.endpoint.split('/v1')[0].split('/').pop()}`;
        } else if (data.model) {
            statusEl.textContent = `LLM: ${data.model}`;
        } else {
            statusEl.textContent = 'LLM: 未配置';
        }
    } catch (e) {
        document.getElementById('llm-status').textContent = 'LLM: 未配置';
    }
}

// 页面加载时调用
loadDevices();
loadLLMStatus();
function addChatMessage(role, content) {
    const messagesEl = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    messageDiv.innerHTML = `
        <div class="message-label">${role === 'user' ? '你' : 'AI'}</div>
        <div class="message-content">${content}</div>
    `;
    messagesEl.appendChild(messageDiv);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// 发送消息
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // 显示用户消息
    addChatMessage('user', message);
    input.value = '';
    
    // 显示等待消息
    const waitingDiv = document.createElement('div');
    waitingDiv.className = 'chat-message ai';
    waitingDiv.innerHTML = '<div class="message-label">AI</div><div class="message-content">正在思考...</div>';
    document.getElementById('chat-messages').appendChild(waitingDiv);
    document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        
        const result = await response.json();
        
        // 移除等待消息
        waitingDiv.remove();
        
        if (result.success) {
            addChatMessage('ai', result.message);
        } else {
            addChatMessage('ai', '抱歉，出了点问题: ' + result.message);
        }
    } catch (e) {
        waitingDiv.remove();
        addChatMessage('ai', '发送失败: ' + e);
    }
}

// 对话事件绑定
document.getElementById('chat-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendChatMessage();
    }
});

document.getElementById('btn-send').addEventListener('click', sendChatMessage);

// 页面加载时加载设备列表
loadDevices();

// 添加设备处理函数
function handleAddDevice() {
    const connectType = document.querySelector('.btn-connect-type.active')?.dataset.type || 'ssh';
    const deviceIp = document.getElementById('device-ip').value;
    const port = document.getElementById('device-port').value || (connectType === 'ssh' ? '22' : '23');
    const username = document.getElementById('device-username').value;
    const password = document.getElementById('device-password').value;
    const autoDiscover = document.getElementById('auto-discover-neighbors')?.checked || true;
    
    if (!deviceIp) {
        alert('请输入设备IP');
        return;
    }
    
    console.log('添加设备:', { deviceIp, connectType, port, username, autoDiscover });
    
    document.getElementById('add-device-modal').classList.remove('active');
    document.getElementById('loading').style.display = 'block';
    document.getElementById('status').textContent = '正在添加设备...';
    
    fetch('/api/device/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            device_ip: deviceIp,
            connect_type: connectType,
            port: port,
            username: username,
            password: password,
            auto_discover: autoDiscover
        })
    })
    .then(res => res.json())
    .then(data => {
        console.log('添加结果:', data);
        document.getElementById('loading').style.display = 'none';
        if (data.success) {
            document.getElementById('status').textContent = data.message;
            if (data.topology) {
                topologyCanvas.setData(data.topology.devices, data.topology.links);
                updateDeviceList(data.topology.devices);
                document.getElementById('device-count').textContent = `设备: ${data.topology.device_count}`;
                document.getElementById('link-count').textContent = `链路: ${data.topology.link_count}`;
            }
        } else {
            alert('添加失败: ' + data.message);
            document.getElementById('status').textContent = '添加失败';
        }
    })
    .catch(err => {
        console.error('添加失败:', err);
        document.getElementById('loading').style.display = 'none';
        alert('添加失败: ' + err);
        document.getElementById('status').textContent = '添加失败';
    });
}

// LLM 测试连接
function handleTestApi() {
    const provider = document.querySelector('.btn-provider.active')?.dataset.provider || 'openai';
    const endpoint = document.getElementById('api-endpoint').value;
    const apiKey = document.getElementById('api-key').value;
    
    console.log('测试API - provider:', provider);
    console.log('测试API - endpoint:', endpoint);
    console.log('测试API - apiKey:', apiKey);
    
    if (!endpoint) {
        alert('请输入 Endpoint');
        return;
    }
    
    document.getElementById('status').textContent = '正在测试连接...';
    
    fetch('/api/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            provider: provider,
            endpoint: endpoint,
            api_key: apiKey
        })
    })
    .then(res => {
        console.log('响应状态:', res.status);
        return res.json();
    })
    .then(data => {
        console.log('测试结果:', data);
        if (data.success) {
            document.getElementById('status').textContent = '连接成功!';
            const modelSelect = document.getElementById('model-select');
            modelSelect.innerHTML = '<option value="">请选择模型</option>';
            if (data.models && data.models.length > 0) {
                data.models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m;
                    modelSelect.appendChild(opt);
                });
                document.getElementById('model-list-container').style.display = 'block';
            }
        } else {
            document.getElementById('status').textContent = '连接失败: ' + data.message;
            alert('连接失败: ' + data.message);
        }
    })
    .catch(err => {
        console.error('测试失败:', err);
        document.getElementById('status').textContent = '测试失败: ' + err;
        alert('测试失败: ' + err);
    });
}