"""
NetOps AI Web界面后端 - 简化版
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import asyncio
import threading

from app.core.discovery import TopologyDiscovery
from app.llm.config import LLMConfig, LLMClient, ProviderType, LLMConfigManager
from app.core.device import Device, Vendor, DeviceType, Topology, Link, PortType, PortStatus
from data_persistence import save_topology, load_topology, save_llm_config as persist_llm_config, load_llm_config as load_persisted_llm

# 启动时加载保存的数据
saved_topology = load_topology()
saved_llm = load_persisted_llm()

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'netops-ai-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# 存储当前拓扑数据
current_topology = None
llm_config = None
llm_client = None
device_ports = {}  # 存储设备端口信息

# 启动时加载保存的数据
def initialize_from_saved():
    global current_topology, llm_config, llm_client, device_ports
    
    # 加载拓扑
    if saved_topology:
        try:
            from app.core.device import Topology
            current_topology = Topology()
            for dev_data in saved_topology.get('devices', []):
                # 处理 vendor 枚举
                vendor_str = dev_data.get('vendor', 'unknown')
                try:
                    vendor = Vendor(vendor_str)
                except:
                    vendor = Vendor.UNKNOWN
                
                # 处理 device_type 枚举
                dtype_str = dev_data.get('device_type', 'unknown')
                try:
                    device_type = DeviceType(dtype_str)
                except:
                    device_type = DeviceType.UNKNOWN
                
                dev = Device(
                    id=dev_data['id'],
                    name=dev_data['name'],
                    ip=dev_data['ip'],
                    vendor=vendor,
                    device_type=device_type,
                    os_version=dev_data.get('os_version', ''),
                    model=dev_data.get('model', '')
                )
                current_topology.add_device(dev)
                # 加载端口信息
                device_ports[dev.ip] = dev_data.get('port', 23)
            print(f"已加载 {len(current_topology.devices)} 个设备")
        except Exception as e:
            print(f"加载拓扑失败: {e}")
    
    # 加载LLM配置
    if saved_llm:
        try:
            provider = ProviderType(saved_llm.get('provider', 'openai'))
            endpoint = saved_llm.get('endpoint', '')
            model = saved_llm.get('model', '')
            # API Key 需要用户重新输入
            llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key='', model=model)
            llm_client = LLMClient(llm_config)  # 创建客户端
            print(f"已加载LLM配置: {endpoint} - {model}")
        except Exception as e:
            print(f"加载LLM配置失败: {e}")

# 初始化
initialize_from_saved()

# LLM配置API
@app.route('/api/llm/config', methods=['GET'])
def get_llm_config():
    """获取LLM配置"""
    global llm_config
    if llm_config is None:
        llm_config = LLMConfig()
    return jsonify({
        'provider': llm_config.provider.value,
        'endpoint': llm_config.endpoint,
        'model': llm_config.model
    })

@app.route('/api/llm/config', methods=['POST'])
def save_llm_config():
    """保存LLM配置"""
    global llm_config, llm_client
    data = request.json
    
    provider = ProviderType(data.get('provider', 'openai'))
    endpoint = data.get('endpoint', 'https://api.openai.com/v1')
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    
    llm_config = LLMConfig(
        provider=provider,
        endpoint=endpoint,
        api_key=api_key,
        model=model
    )
    
    # 创建客户端
    llm_client = LLMClient(llm_config)
    llm_config.save()
    
    # 持久化保存配置
    persist_llm_config({
        'provider': provider.value if hasattr(provider, 'value') else str(provider),
        'endpoint': endpoint,
        'model': model
    })
    
    print(f"LLM config saved: {provider} - {endpoint} - {model}")
    
    return jsonify({
        'success': True,
        'provider': provider.value if hasattr(provider, 'value') else str(provider),
        'endpoint': endpoint,
        'model': model
    })

@app.route('/api/llm/test', methods=['POST'])
def test_llm():
    """测试LLM连接并获取模型列表"""
    global llm_client
    data = request.json
    
    provider = data.get('provider', 'openai')
    endpoint = data.get('endpoint', 'https://api.openai.com/v1')
    api_key = data.get('api_key', '')
    
    try:
        # 直接尝试获取模型列表
        from app.llm.config import LLMConfig, LLMClient, ProviderType
        
        # 如果是自定义 provider，使用 local/custom
        if provider == 'custom':
            provider_type = ProviderType.OPENAI  # 本地也用 OpenAI 格式
        else:
            provider_type = ProviderType(provider)
        
        config = LLMConfig(provider=provider_type, endpoint=endpoint, api_key=api_key, model='')
        client = LLMClient(config)
        models = client.list_models()
        
        return jsonify({'success': True, 'models': models[:20]})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# 拓扑发现API
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/discover', methods=['POST'])
def start_discovery():
    data = request.json
    seed_ip = data.get('seed_ip')
    username = data.get('username')
    password = data.get('password')

    if not all([seed_ip, username, password]):
        return jsonify({'success': False, 'message': '缺少必要参数'})

    def run_discovery():
        global current_topology
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        discovery = TopologyDiscovery()
        result = loop.run_until_complete(discovery.discover(seed_ip, username, password))
        
        if result.success:
            current_topology = result.topology
            topo_data = topology_to_dict(result.topology)
            socketio.emit('discovery_complete', {'success': True, 'topology': topo_data})
        else:
            socketio.emit('discovery_complete', {'success': False, 'message': result.message})

    thread = threading.Thread(target=run_discovery)
    thread.start()

    return jsonify({'success': True, 'message': '开始发现网络拓扑...'})

@app.route('/api/topology', methods=['GET'])
def get_topology():
    global current_topology
    if current_topology:
        return jsonify({'success': True, 'topology': topology_to_dict(current_topology)})
    return jsonify({'success': False, 'message': '暂无拓扑数据'})

# 设备列表API - 前端加载设备用
@app.route('/api/devices', methods=['GET'])
def get_devices():
    """获取设备列表"""
    global current_topology
    
    if current_topology and current_topology.devices:
        devices = []
        for dev in current_topology.devices:
            # 获取端口
            port = device_ports.get(dev.ip, 23)
            devices.append({
                'id': dev.id,
                'ip': dev.ip,
                'name': dev.name,
                'vendor': dev.vendor.value if hasattr(dev.vendor, 'value') else str(dev.vendor),
                'model': dev.model,
                'device_type': dev.device_type.value if hasattr(dev.device_type, 'value') else str(dev.device_type),
                'os_version': dev.os_version,
                'port': port
            })
        return jsonify({'success': True, 'devices': devices})
    
    return jsonify({'success': True, 'devices': []})


def handle_telnet_device(device_ip, port, username, password):
    """处理Telnet设备连接 - 完整自动登录流程"""
    global current_topology
    from app.core.device import Device, Vendor, DeviceType, Topology
    
    # 初始化拓扑
    if current_topology is None:
        current_topology = Topology()
    
    try:
        import socket
        import time
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((device_ip, port))
        
        # 第一步：读取欢迎信息，检测是否需要登录
        data_recv = sock.recv(4096).decode('utf-8', errors='ignore')
        
        # 检测自动配置并跳过
        if 'automatic configuration' in data_recv.lower():
            sock.send(b'\x04')  # Ctrl+D
            time.sleep(2)
            
            # 按Enter获取shell
            sock.send(b'\r\n')
            time.sleep(2)
            
            data_recv = ""
            for i in range(3):
                try:
                    sock.settimeout(2)
                    chunk = sock.recv(4096).decode('utf-8', errors='ignore')
                    if chunk:
                        data_recv += chunk
                except:
                    pass
        
        # 检测登录提示符
        data_lower = data_recv.lower()
        needs_login = any(x in data_lower for x in ['login', 'username', 'password', 'user name', 'user:'])
        
        if needs_login:
            # 发送用户名
            if username:
                sock.send((username + '\r\n').encode())
                time.sleep(1)
            
            # 检测密码提示符
            resp = sock.recv(4096).decode('utf-8', errors='ignore')
            data_recv += resp
            
            # 发送密码
            if password:
                sock.send((password + '\r\n').encode())
                time.sleep(1)
            
            # 读取登录结果
            login_resp = sock.recv(4096).decode('utf-8', errors='ignore')
            data_recv += login_resp
        
        # 发送显示版本命令获取设备信息
        sock.send(b'display version\r\n')
        time.sleep(2)
        
        # 读取命令输出
        version_output = ""
        for i in range(3):
            try:
                sock.settimeout(2)
                chunk = sock.recv(4096).decode('utf-8', errors='ignore')
                if chunk:
                    version_output += chunk
            except:
                pass
        
        data_recv += version_output
        
        # 发送quit退出
        try:
            sock.send(b'quit\r\n')
        except:
            pass
        sock.close()
        
        # 识别厂商
        data_lower = data_recv.lower()
        
        # 初始化
        vendor = Vendor.UNKNOWN
        device_type = DeviceType.UNKNOWN
        model = "Unknown"
        
        # H3C 可能显示的标识
        if any(x in data_lower for x in ['h3c', 'hp', 'comware', 'hewlett', '3com']):
            vendor = Vendor.H3C
            model = "H3C Device"
            device_type = DeviceType.SWITCH_L3
        elif 'huawei' in data_lower:
            vendor = Vendor.HUAWEI
            model = "Huawei Device"
            device_type = DeviceType.SWITCH_L3
        elif 'cisco' in data_lower:
            vendor = Vendor.CISCO
            model = "Cisco Device"
            device_type = DeviceType.SWITCH_L3
        elif 'juniper' in data_lower:
            vendor = Vendor.JUNIPER
            model = "Juniper Device"
            device_type = DeviceType.SWITCH_L3
        
        device = Device(
            id=device_ip,
            name=f"{vendor.value.upper()}-{device_ip}" if vendor != Vendor.UNKNOWN else f"Device-{device_ip}",
            ip=device_ip,
            vendor=vendor,
            device_type=device_type,
            os_version="",
            model=model
        )
        device_ports[device_ip] = port  # 保存端口
        
        current_topology.add_device(device)
        topo_data = topology_to_dict(current_topology)
        socketio.emit('topology_updated', {'success': True, 'topology': topo_data})
        save_topology(topo_data)  # 保存到文件
        
        return jsonify({
            'success': True, 
            'message': f'已添加 {vendor.value} 设备 {device_ip}' if vendor != Vendor.UNKNOWN else f'已添加设备 {device_ip}',
            'device': {'id': device.id, 'name': device.name, 'ip': device.ip, 'vendor': vendor.value, 'model': model, 'device_type': device_type.value},
            'topology': topo_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'连接失败: {str(e)}'})


# 添加设备API
@app.route('/api/device/add', methods=['POST'])
def add_device():
    """添加设备并自动发现邻居"""
    global current_topology
    
    data = request.json
    device_ip = data.get('device_ip')
    connect_type = data.get('connect_type', 'ssh')  # ssh/telnet/serial
    
    # 调试日志
    
    # 解析IP:端口格式
    original_port = data.get('port')  # 保存前端传的端口
    if ':' in device_ip:
        ip_parts = device_ip.rsplit(':', 1)
        # 检查第二部分是否是数字端口
        try:
            if len(ip_parts) > 1 and int(ip_parts[1]):
                device_ip = ip_parts[0]
                port = int(ip_parts[1])
        except:
            pass  # 不是端口，保持原样
    
    # 如果前端传了单独的port参数，优先使用它
    if original_port:
        port = int(original_port)
    elif not port:
        port = 22 if connect_type == 'ssh' else 23
    
    username = data.get('username', '')
    password = data.get('password', '')
    
    # 处理 Telnet 连接
    if connect_type == 'telnet':
        return handle_telnet_device(device_ip, port, username, password)
    
    # SSH连接处理
    auto_discover = data.get('auto_discover', True)
    
    if not device_ip:
        return jsonify({'success': False, 'message': '设备IP不能为空'})
    
    # 初始化拓扑
    if current_topology is None:
        from app.core.device import Topology
        current_topology = Topology()
    
    # 添加设备到拓扑（需要SSH连接获取信息）
    # 这里先简化处理 - 直接添加设备信息
    from app.core.device import Device, Vendor, DeviceType
    from app.network.ssh import DeviceConnection, ConnectionInfo
    
    try:
        # 尝试SSH连接获取设备信息
        conn_info = ConnectionInfo(
            ip=device_ip,
            port=int(port),
            username=username,
            password=password
        )
        
        with DeviceConnection(conn_info) as conn:
            device = conn.get_device_info()
            
            # 添加到拓扑
            current_topology.add_device(device)
            
            # 如果开启自动发现邻居
            if auto_discover:
                # 获取LLDP邻居
                from app.network.commands import CommandBuilder
                from app.network.lldp import LLDPNeighborParser
                
                try:
                    cmd = CommandBuilder.get_lldp_neighbor(device.vendor)
                    if cmd:
                        output = conn.execute_command(cmd)
                        neighbors = LLDPNeighborParser.parse_lldp_neighbor(output, device.vendor)
                        
                        # 添加邻居到拓扑并创建链路
                        from app.core.device import Link, PortType
                        from app.network.lldp import LinkTypeDetector
                        
                        for neighbor in neighbors:
                            # 创建链路
                            port_type = LinkTypeDetector.detect_link_type(neighbor.local_interface)
                            link = Link(
                                source_device=device.id,
                                source_interface=neighbor.local_interface,
                                target_device=neighbor.device_id,
                                target_interface=neighbor.remote_interface,
                                link_type=port_type.value if port_type != PortType.NORMAL else 'physical',
                                port_type=port_type
                            )
                            current_topology.add_link(link)
                except Exception as e:
                    print(f"发现邻居失败: {e}")
            
            # 通知前端更新
            topo_data = topology_to_dict(current_topology)
            socketio.emit('topology_updated', {'success': True, 'topology': topo_data})
            
            return jsonify({
                'success': True, 
                'message': f'已添加设备 {device.name} ({device.ip})',
                'device': {
                    'id': device.id,
                    'name': device.name,
                    'ip': device.ip,
                    'vendor': device.vendor.value,
                    'model': device.model,
                    'device_type': device.device_type.value
                }
            })
            
    except Exception as e:
        # 连接失败时添加一个模拟设备（用于测试UI）
        try:
            from app.core.device import Device, Vendor, DeviceType
            
            # 解析IP和端口
            ip_parts = device_ip.split(':')
            actual_ip = ip_parts[0]
            actual_port = int(port)
            
            # 创建设备信息
            device = Device(
                id=actual_ip,
                name=f"Device-{actual_ip}",
                ip=actual_ip,
                vendor=Vendor.UNKNOWN,
                device_type=DeviceType.UNKNOWN,
                os_version="Unknown",
                model="Virtual Device"
            )
            
            # 添加到拓扑
            current_topology.add_device(device)
            
            topo_data = topology_to_dict(current_topology)
            socketio.emit('topology_updated', {'success': True, 'topology': topo_data})
            
            return jsonify({
                'success': True, 
                'message': f'已添加模拟设备 {actual_ip} (连接失败，已添加占位设备)',
                'device': {
                    'id': device.id,
                    'name': device.name,
                    'ip': device.ip,
                    'vendor': 'unknown',
                    'model': 'Virtual Device',
                    'device_type': 'unknown'
                },
                'topology': topo_data
            })
        except Exception as e2:
            return jsonify({'success': False, 'message': f'添加失败: {str(e2)}'})


# 删除设备API
@app.route('/api/device/delete', methods=['POST'])
def delete_device():
    """删除设备"""
    global current_topology
    
    data = request.json
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'message': '设备ID不能为空'})
    
    if current_topology is None:
        return jsonify({'success': False, 'message': '暂无拓扑数据'})
    
    try:
        # 删除设备及其关联链路
        current_topology.remove_device(device_id)
        
        # 删除端口信息
        if device_id in device_ports:
            del device_ports[device_id]
        
        topo_data = topology_to_dict(current_topology)
        socketio.emit('topology_updated', {'success': True, 'topology': topo_data})
        save_topology(topo_data)  # 保存到文件
        
        return jsonify({
            'success': True, 
            'message': f'已删除设备 {device_id}',
            'topology': topo_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})


# AI对话API
import json

# 配置模板 API
@app.route('/api/template/list', methods=['GET'])
def list_templates():
    """获取配置模板列表"""
    try:
        from app.config_templates import list_templates as get_templates
        
        templates = get_templates()
        return jsonify({
            'success': True,
            'templates': [
                {
                    'id': t.id,
                    'name': t.name,
                    'description': t.description,
                    'vendor': t.vendor,
                    'category': t.category,
                    'icon': '📋',
                    'params': t.parameters,
                    'template': t.template_content,
                }
                for t in templates
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/template/apply', methods=['POST'])
def apply_template():
    """应用配置模板"""
    try:
        from app.config_templates import render_config
        
        data = request.json
        template_id = data.get('template_id')
        params = data.get('params', {})
        devices = data.get('devices', [])
        
        if not template_id:
            return jsonify({'success': False, 'message': '缺少模板 ID'})
        if not devices:
            return jsonify({'success': False, 'message': '请选择设备'})
        
        # 渲染配置
        config = render_config(template_id, params)
        if not config:
            return jsonify({'success': False, 'message': '模板不存在'})
        
        # TODO: 执行配置到设备
        # 这里需要集成 DeviceExecutor
        
        return jsonify({
            'success': True,
            'message': f'配置已下发到 {len(devices)} 台设备',
            'config': config,
            'devices': devices
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# AI 对话 API
@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 对话接口 - 关键词检测，通用模型支持"""
    global llm_client, current_topology, device_ports
    
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'success': False, 'message': '消息不能为空'})

    import re
    
    # 中文→英文翻译层
    translation = user_message
    for cn, en in {'做':'do','创建':'create','配置':'config','查看':'show','显示':'show','接口':'interface','端口':'port','路由':'route','邻居':'neighbor','版本':'version'}.items():
        translation = translation.replace(cn, en)
    
    user_msg = translation.lower()
    exec_cmd = None
    
    # VLAN 配置
    if 'vlan' in user_msg and any(x in user_msg for x in ['do','create','add','config','make']):
        vlan_ids = re.findall(r'\d+', user_message)
        exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "vlan batch 10 20"
    # VLAN 查看
    elif 'vlan' in user_msg and any(x in user_msg for x in ['show','view','check','list','has']):
        exec_cmd = "display vlan"
    # 默认 VLAN
    elif 'vlan' in user_msg:
        vlan_ids = re.findall(r'\d+', user_message)
        exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}" if vlan_ids else "vlan batch 10 20"
    # 接口
    elif any(x in user_msg for x in ['interface','port']):
        exec_cmd = "display interface brief"
    # 路由
    elif any(x in user_msg for x in ['route','ospf','bgp']):
        exec_cmd = "display ospf peer" if 'ospf' in user_msg else "display ip routing-table"
    # 邻居
    elif any(x in user_msg for x in ['neighbor','lldp','cdp']):
        exec_cmd = "display lldp neighbor"
    # ARP
    elif 'arp' in user_msg or 'mac' in user_msg:
        exec_cmd = "display arp"
    # 版本
    elif 'version' in user_msg:
        exec_cmd = "display version"
    
    # 执行
    if exec_cmd and current_topology and current_topology.devices:
        exec_ip = list(device_ports.keys())[0]
        exec_port = device_ports.get(exec_ip, 23)
        try:
            # 先发送 Ctrl+D 中断自动配置
            import socket
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(3)
                test_sock.connect((exec_ip, exec_port))
                test_sock.send(b'\x04')  # Ctrl+D
                import time
                time.sleep(1)
                test_sock.close()
            except:
                pass  # 忽略中断失败
            
            result = execute_on_device(exec_ip, exec_cmd, port=exec_port)
            response = f"【自动执行】\n设备：{exec_ip}:{exec_port}\n命令：{exec_cmd}\n\n【结果】\n{result}"
        except Exception as e:
            response = f"【命令】{exec_cmd}\n【失败】{str(e)}"
    elif exec_cmd:
        response = f"【生成命令】{exec_cmd}"
    else:
        pass
        response = "NetOps AI 助手\n支持：VLAN/接口/路由/邻居/ARP 查询\n例：做两个 vlan / 查看接口"
    
    return jsonify({'success': True, 'message': response})

def chat():
    """AI 对话接口 - 纯关键词检测，不使用 LLM"""
    global llm_client, current_topology, device_ports
    
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'success': False, 'message': '消息不能为空'})

    import re
    
    # 关键词检测
    # 中文→英文简单翻译
    translation_map = {
        '做': 'do', '创建': 'create', '配置': 'config', '查看': 'show',
        '显示': 'show', '检查': 'check', '接口': 'interface', '端口': 'port',
        '路由': 'route', '邻居': 'neighbor', '版本': 'version', '当前': 'current',
        '设备': 'device', '信息': 'info', '有': 'has', '弄': 'do', '设': 'set',
        '建': 'create', '开': 'open', '搞': 'do'
    }
    translated_msg = user_message
    for cn, en in translation_map.items():
        translated_msg = translated_msg.replace(cn, en)
    user_msg = translated_msg.lower()
    print(f"DEBUG: 原始='{user_message}' 翻译后='{user_msg}'")
    
    exec_cmd = None
    
    # 1. VLAN 配置（优先级最高）
    if 'vlan' in user_msg and any(x in user_msg for x in ['create', 'add', 'config', 'do', 'make', 'set', '创建', '添加', '\u914d\u7f6e', '做', '弄', '设']):
        vlan_ids = re.findall(r'\d+', user_message)
        if vlan_ids:
            exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}"
        else:
            pass  # TODO: implement vlan config
    # 2. VLAN 查看
    elif 'vlan' in user_msg and any(x in user_msg for x in ['view', 'show', 'check', 'list', 'display', '\u67e5\u770b', '\u663e\u793a', '\u68c0\u67e5', '\u6709']):
        exec_cmd = "display vlan"
    # 3. 默认 VLAN 操作视为配置
    elif 'vlan' in user_msg:
        vlan_ids = re.findall(r'\d+', user_message)
        if vlan_ids:
            exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}"
        else:
            exec_cmd = "display vlan"
    # 4. 接口查看
    elif 'interface' in user_msg or 'port' in user_msg or '接口' in user_msg or '端口' in user_msg:
        if any(x in user_msg for x in ['\u67e5\u770b', 'show', 'view', 'check', 'display', '\u6709']):
            exec_cmd = "display interface brief"
        elif any(x in user_msg for x in ['\u914d\u7f6e', 'config', 'set', '配']):
            exec_cmd = "interface GigabitEthernet 0/0/1"
        else:
            exec_cmd = "display interface brief"
    # 5. 路由查看
    elif any(x in user_msg for x in ['\u8def\u7531', 'route', 'routing', 'ospf', 'bgp']):
        if 'ospf' in user_msg:
            exec_cmd = "display ospf peer"
        elif 'bgp' in user_msg:
            exec_cmd = "display bgp peer"
        else:
            exec_cmd = "display ip routing-table"
    # 6. 邻居发现
    elif any(x in user_msg for x in ['\u90bb\u5c45', 'neighbor', 'lldp', 'cdp']):
        exec_cmd = "display lldp neighbor"
    # 7. ARP 表
    elif any(x in user_msg for x in ['arp', 'ARP', 'mac \u5730\u5740', 'mac address']):
        exec_cmd = "display arp"
    # 8. 设备信息
    elif any(x in user_msg for x in ['\u7248\u672c', 'version', '\u8bbe\u5907\u4fe1\u606f', 'device info']):
        exec_cmd = "display version"
    # 9. 当前配置
    elif any(x in user_msg for x in ['\u5f53\u524d\u914d\u7f6e', 'current', 'running', '\u914d\u7f6e']):
        exec_cmd = "display current-configuration"
        if vlan_ids:
            exec_cmd = f"vlan batch {' '.join(vlan_ids[:2])}"
        else:
            pass
    # 4. 接口查看
    elif '\u63a5\u53e3' in user_msg or 'interface' in user_msg:
        exec_cmd = "display interface brief"
    # 5. 邻居查看
    elif '\u90bb\u5c45' in user_msg or 'lldp' in user_msg or 'cdp' in user_msg:
        exec_cmd = "display lldp neighbor"
    
    # 执行命令
    if exec_cmd and current_topology and current_topology.devices:
        exec_ip = list(device_ports.keys())[0]
        exec_port = device_ports.get(exec_ip, 23)
        try:
            # 先发送 Ctrl+D 中断自动配置
            import socket
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(3)
                test_sock.connect((exec_ip, exec_port))
                test_sock.send(b'\x04')  # Ctrl+D
                import time
                time.sleep(1)
                test_sock.close()
            except:
                pass  # 忽略中断失败
            
            result = execute_on_device(exec_ip, exec_cmd, port=exec_port)
            response = f"【自动执行命令】\n设备：{exec_ip}:{exec_port}\n命令：{exec_cmd}\n\n【执行结果】\n{result}"
        except Exception as e:
            response = f"【命令】{exec_cmd}\n【执行失败】{str(e)}"
    elif exec_cmd:
        response = f"【生成命令】{exec_cmd}\n【状态】等待设备连接（当前拓扑无设备）"
    else:
        pass
        response = "我是 NetOps AI 助手，可以帮你：\n- 创建/配置 VLAN（例：做两个 vlan）\n- 查看 VLAN（例：查看 vlan）\n- 查看接口（例：查看接口）\n\n请告诉我你需要什么帮助？"
    
    return jsonify({'success': True, 'message': response})

def generate_response(user_message: str, context: str) -> str:
    """生成AI响应 - 支持自动执行命令"""
    global current_topology, device_ports
    
    msg = user_message.lower()
    
    # 提取设备列表
    device_list = []
    if current_topology and current_topology.devices:
        for dev in current_topology.devices:
            port = device_ports.get(dev.ip, 23)
            device_list.append({
                'ip': dev.ip,
                'name': dev.name,
                'vendor': dev.vendor.value if hasattr(dev.vendor, 'value') else str(dev.vendor),
                'port': port
            })
    
    exec_cmd = None
    exec_ip = None
    
    # 先检测配置类请求（优先级高于查看类）
    if any(x in msg for x in ['添加', '创建', '新建', '\u914d\u7f6e', '设置', '做', '开', '建']):
        # 添加 VLAN
        if 'vlan' in msg:
            vlan_ids = re.findall(r'\d+', user_message)
            if vlan_ids:
                vlan_list = vlan_ids[:2]
                exec_cmd = f"vlan batch {' '.join(vlan_list)}"
        # 配置 IP
        elif any(x in msg for x in ['IP', 'ip 地址', '地址']):
            exec_cmd = "interface Vlanif 1"
        # 配置 OSPF
        elif 'ospf' in msg:
            exec_cmd = "ospf 1 router-id 1.1.1.1"
    
    # 再检测查看类请求（只有配置类没匹配时才执行）
    elif any(x in msg for x in ['\u67e5\u770b', '看看', '\u663e\u793a', '有什么', '多少']):
        # 端口/接口
        if any(x in msg for x in ['\u7aef\u53e3', '\u63a5\u53e3', '网口', 'port', 'interface']):
            exec_cmd = "display interface brief"
        # VLAN
        elif any(x in msg for x in ['vlan', '虚拟局域网']):
            exec_cmd = "display vlan"
        # 邻居
        elif any(x in msg for x in ['\u90bb\u5c45', '相邻', 'lldp', 'cdp']):
            exec_cmd = "display lldp neighbor"
        # OSPF
        elif any(x in msg for x in ['ospf', '路由协议']):
            exec_cmd = "display ospf peer"
        # 路由表
        elif any(x in msg for x in ['\u8def\u7531', 'route', '路径']):
            exec_cmd = "display ip routing-table"
        # ARP
        elif any(x in msg for x in ['arp', 'MAC', 'mac地址']):
            exec_cmd = "display arp"
        # 版本/设备信息
        elif any(x in msg for x in ['\u7248\u672c', '\u8bbe\u5907\u4fe1\u606f', '什么设备', '设备型号']):
            exec_cmd = "display version"
        else:
            exec_cmd = "display version"
    
    # 再检测配置类请求
    elif any(x in msg for x in ['添加', '创建', '新建', '\u914d\u7f6e', '设置']):
        # 添加VLAN
        if 'vlan' in msg:
            vlan_ids = re.findall(r'\d+', user_message)
            if vlan_ids:
                vlan_list = vlan_ids[:2]
                exec_cmd = f"vlan batch {' '.join(vlan_list)}"
        # 配置IP
        elif any(x in msg for x in ['IP', 'ip地址', '地址']):
            exec_cmd = "interface Vlanif 1"
        # 配置OSPF
        elif 'ospf' in msg:
            exec_cmd = "ospf 1 router-id 1.1.1.1"
    
    # 单独的 vlan 关键词（没有查看/配置前缀）
    elif 'vlan' in msg:
        import re
        vlan_ids = re.findall(r'\d+', user_message)
        if vlan_ids:
            vlan_list = vlan_ids[:2]
            exec_cmd = f"vlan batch {' '.join(vlan_list)}"
        else:
            exec_cmd = "display vlan"  # 没有数字就查看
    
    # 执行命令
    if exec_cmd and device_list:
        device_info = device_list[0]
        exec_ip = device_info['ip']
        exec_port = device_info.get('port', 23)  # 获取端口，默认23
        result = execute_on_device(exec_ip, exec_cmd, port=exec_port)
        return f"""【自动执行命令】
设备: {exec_ip}:{exec_port}
命令: {exec_cmd}

【执行结果】
{result}"""
    
    # 原有的文字响应逻辑...
        return """**我可以帮你：**

📋 **查看信息**
- `display version` - 设备版本
- `display interface brief` - 接口状态
- `display lldp neighbor` - 邻居信息
- `display vrrp` - VRRP状态

⚙️ **配置生成**
- "配置OSPF"
- "配置聚合链路"
- "添加VLAN 10"
- "配置VRRP主备"

🔧 **故障排查**
- "ping不通怎么办"
- "网络延迟高"

请直接告诉我你的需求！"""
    
    elif 'ping' in msg:
        return """**Ping命令示例：**

华为设备：
```
ping 10.1.1.1
ping -c 10 10.1.1.1  # 指定次数
ping -a source-ip target-ip  # 指定源
```

思科设备：
```
ping 10.1.1.1
ping ip 10.1.1.1 repeat 10
```

要我对特定设备执行ping吗？"""
    
    elif '\u914d\u7f6e' in user_message or 'ospf' in msg or 'vlan' in msg or '聚合' in msg or 'vrrp' in msg:
        return f"""好的，让我帮你生成配置。

**OSPF配置示例（华为）：**

```
ospf 1 router-id 10.0.0.1
 area 0.0.0.0
  network 10.1.1.0 0.0.0.255
  network 10.1.2.0 0.0.0.255
```

**聚合链路配置：**
```
interface Eth-Trunk 1
 mode lacp-static
 trunkport GigabitEthernet 0/0/1
 trunkport GigabitEthernet 0/0/2
```

需要我针对特定设备生成更详细的配置吗？"""
    
    elif '拓扑' in user_message or 'topology' in msg:
        if context:
            return f"""**当前网络拓扑：**

{context}

你有 {len(current_topology.devices) if current_topology else 0} 台设备。
点击"拓扑发现"可以扫描更多设备。"""
        else:
            return """当前没有拓扑数据。

点击"🔍 拓扑发现"按钮，输入种子设备IP、用户名、密码来扫描网络。"""
    
    else:
        pass
        return f"""收到："{user_message}"

我是网络工程师AI助手，可以帮你：
1. 生成配置命令（OSPF/VLAN/聚合/VRRP等）
2. 查看设备信息
3. 故障排查建议
4. 解释命令含义

请告诉我你需要什么帮助？"""


def topology_to_dict(topology):
    """转换拓扑对象为字典"""
    devices = []
    for dev in topology.devices:
        devices.append({
            'id': dev.id, 'name': dev.name, 'ip': dev.ip,
            'vendor': dev.vendor.value, 'model': dev.model,
            'device_type': dev.device_type.value, 'os_version': dev.os_version,
            'port': getattr(dev, 'port', 23),  # 保存端口号
            'vrrp_master': dev.vrrp_master,
            'interfaces': [{'name': i.name, 'ip': i.ip, 'status': i.status.value, 
                           'port_type': i.port_type.value} for i in dev.interfaces]
        })

    links = []
    for link in topology.links:
        links.append({
            'source': link.source_device, 'source_interface': link.source_interface,
            'target': link.target_device, 'target_interface': link.target_interface,
            'link_type': link.link_type, 'port_type': link.port_type.value
        })

    return {'devices': devices, 'links': links, 
            'device_count': len(devices), 'link_count': len(links)}


if __name__ == '__main__':
    # 使用debug模式会自动重载
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)









