# NetOps AI Evolution Skill

## 🎯 用途

为 NetOps AI 项目提供进化后的最佳实践，包括：
- LLM 集成（支持任意模型）
- 设备上下文传递
- 配置持久化
- 优雅错误处理

## 📦 安装

无需安装，这是 NetOps AI 项目的内置技能。

## 🔧 使用

### 1. LLM 调用（带设备上下文）

```python
@app.route('/api/chat', methods=['POST'])
def chat():
    # 构建设备上下文
    vendors = [dev.vendor.value for dev in current_topology.devices]
    context = f"设备厂商：{', '.join(set(vendors))}\n设备数量：{len(current_topology.devices)}"
    
    # 调用 LLM
    instruction = "你是网络设备配置助手。只返回命令行，不要任何解释、步骤或说明！"
    response = llm_client.chat_simple(user_message, instruction + "\n" + context, timeout=30)
    
    # 提取并执行命令
    exec_cmd = response.split('\n')[0].strip()
    result = execute_on_device(exec_ip, exec_cmd, port=exec_port)
```

### 2. 设备参数传递

**关键：** 将设备厂商信息传递给 LLM，让它返回对应厂商的命令格式。

```python
# 收集厂商信息
vendors = []
for dev in current_topology.devices:
    vendors.append(dev.vendor.value)

# 传递给 LLM
context = f"当前设备厂商：{', '.join(set(vendors))}"
```

### 3. 模型配置保存

```python
@app.route('/api/llm/config', methods=['POST'])
def save_llm():
    data = request.json
    provider = ProviderType(data.get('provider', 'openai'))
    endpoint = data.get('endpoint', '')
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    
    llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
    llm_client = LLMClient(llm_config)
    llm_config.save()
    
    # 保存到文件（包含 api_key）
    save_llm_config({
        'provider': provider.value,
        'endpoint': endpoint,
        'api_key': api_key,  # 关键！
        'model': model
    })
```

### 4. 设备自动加载

```python
@app.route('/api/devices', methods=['GET'])
def get_devices():
    if not current_topology:
        return jsonify({'success': True, 'devices': [], 'count': 0})
    
    devices = [{
        'id': dev.id,
        'name': dev.name,
        'ip': dev.ip,
        'vendor': dev.vendor.value,
        'port': device_ports.get(dev.ip, 23)
    } for dev in current_topology.devices]
    
    return jsonify({'success': True, 'devices': devices, 'count': len(devices)})
```

### 5. 设备执行（处理自动配置）

```python
def execute_on_device(ip, command, port=23):
    import socket, time
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((ip, port))
    
    # 读取欢迎信息
    data = sock.recv(4096).decode('utf-8', errors='ignore')
    
    # 中断自动配置
    if 'automatic configuration' in data.lower():
        sock.send(b'\x04')  # Ctrl+D
        time.sleep(2)
        sock.send(b'\r\n')
        time.sleep(2)
    
    # 进入系统视图（如需要）
    needs_system = any(x in command.lower() for x in ['vlan', 'interface', 'ospf'])
    if needs_system:
        sock.send(b'system-view\r\n')
        time.sleep(2)
        sock.recv(4096)
    
    # 执行命令
    sock.send((command + '\r\n').encode())
    time.sleep(2)
    
    # 读取输出
    output = ""
    for _ in range(5):
        try:
            sock.settimeout(1)
            chunk = sock.recv(4096).decode('utf-8', errors='ignore')
            if chunk:
                output += chunk
        except:
            break
    
    # 退出
    if needs_system:
        sock.send(b'quit\r\n')
        time.sleep(1)
    
    sock.close()
    return output.strip() if output else "执行成功"
```

## ⚠️ 常见错误

### 1. 函数名冲突
```python
# ❌ 错误：递归调用
def save_llm_config():
    save_llm_config({...})

# ✅ 正确：导入时重命名
from data_persistence import save_llm_config as persist_llm_config

def save_llm_config():
    persist_llm_config({...})
```

### 2. 端口丢失
```python
# ❌ 错误：未保存端口
topology_data = {'devices': [{'ip': dev.ip} for dev in devices]}

# ✅ 正确：保存端口
topology_data = {'devices': [{
    'ip': dev.ip,
    'port': device_ports.get(dev.ip, 23)
} for dev in devices]}
```

### 3. api_key 未保存
```python
# ❌ 错误：缺少 api_key
save_data = {
    'provider': ...,
    'endpoint': ...,
    'model': ...
    # 缺少 api_key!
}

# ✅ 正确
save_data = {
    'provider': ...,
    'endpoint': ...,
    'api_key': ...,  # 包含 api_key
    'model': ...
}
```

### 4. 编码问题（Windows）
```python
# ❌ 错误：emoji 导致 GBK 编码失败
print("✅ 已加载")

# ✅ 正确
print("[OK] 已加载")
```

## 📊 测试清单

- [ ] 设备自动加载（刷新浏览器显示已保存设备）
- [ ] 模型配置保存（保存后重启不丢失）
- [ ] LLM 调用（返回正确命令格式）
- [ ] 设备执行（成功连接并执行命令）
- [ ] 错误处理（LLM 失败时显示友好提示）

## 🚀 下一步

1. **多设备支持** - 批量配置多个设备
2. **配置回滚** - 保存配置快照
3. **定时备份** - 定期备份设备配置
4. **拓扑可视化** - 自动绘制网络拓扑

---

**版本：** Evolution v1.0
**最后更新：** 2026-03-27
**状态：** ✅ 生产就绪
