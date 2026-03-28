# NetOps AI 进化记忆 - 2026-03-27

## 🧬 进化历程

### 阶段 1：初始架构
- **复用 NetBrain MCP** - 9 个工具（设备清单/拓扑/路径/诊断）
- **补充 LLM 路由层** - `app/nl_router/` 负责意图解析
- **SSH 执行** - Netmiko 驱动

### 阶段 2：问题发现
- **LLM 模型不固定** - 用户可能切换不同模型（Ollama/Qwen/其他）
- **关键词检测冲突** - 硬编码的关键词覆盖 LLM 判断
- **模型返回废话** - 需要 prompt 工程优化
- **设备端口丢失** - 保存时未正确存储端口信息
- **函数命名冲突** - `save_llm_config` 递归调用

### 阶段 3：关键决策

#### 1. LLM 策略
**决策：** 删除关键词检测，完全信任 LLM
**原因：**
- 关键词检测优先级高于 LLM，导致误判
- LLM 能更好理解上下文
- 通过 prompt 工程可以控制输出格式

**Prompt 优化：**
```python
instruction = "你是网络设备配置助手。只返回命令行，不要任何解释、步骤或说明！"
context = f"设备厂商：{', '.join(set(vendors))}\n设备数量：{len(devices)}"
```

#### 2. 设备参数传递
**决策：** 将设备厂商信息传递给 LLM
**实现：**
```python
vendors = [dev.vendor.value for dev in current_topology.devices]
context = f"设备厂商：{', '.join(set(vendors))}"
```

#### 3. 模型保存修复
**问题：** `save_llm_config` 函数名冲突
**解决：**
```python
# app.py 中
from data_persistence import save_llm_config as persist_llm_config

# 调用时
persist_llm_config({
    'provider': provider.value,
    'endpoint': endpoint,
    'api_key': api_key,  # 关键：保存 api_key
    'model': model
})
```

#### 4. 设备自动加载
**添加 API：**
```python
@app.route('/api/devices', methods=['GET'])
def get_devices():
    devices = [{
        'id': dev.id,
        'name': dev.name,
        'ip': dev.ip,
        'vendor': dev.vendor.value,
        'port': device_ports.get(dev.ip, 23)
    } for dev in current_topology.devices]
    return jsonify({'success': True, 'devices': devices})
```

### 阶段 4：最终架构

```
NetOps AI (Evolution Version)
├── 前端
│   ├── 设备自动加载 (/api/devices)
│   └── 模型配置保存 (/api/llm/config)
├── 后端
│   ├── LLM 调用（带设备上下文）
│   ├── 设备执行（Ctrl+D 中断自动配置）
│   └── 状态持久化
└── 数据层
    ├── topology.json (设备 + 端口)
    └── llm_config.json (含 api_key)
```

## 📊 关键代码

### LLM 调用（带厂商信息）
```python
@app.route('/api/chat', methods=['POST'])
def chat():
    # 构建设备上下文
    vendors = [dev.vendor.value for dev in current_topology.devices]
    context = f"设备厂商：{', '.join(set(vendors))}\n"
    
    # 调用 LLM
    instruction = "只返回命令行，不要任何解释！"
    response = llm_client.chat_simple(user_message, instruction + "\n" + context, timeout=30)
    
    # 执行命令
    exec_cmd = response.split('\n')[0].strip()
    result = execute_on_device(exec_ip, exec_cmd, port=exec_port)
```

### 设备执行（处理自动配置）
```python
def execute_on_device(ip, command, port=23):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    
    # 中断自动配置
    data = sock.recv(4096).decode()
    if 'automatic configuration' in data.lower():
        sock.send(b'\x04')  # Ctrl+D
        time.sleep(2)
    
    # 进入系统视图
    if 'vlan' in command.lower():
        sock.send(b'system-view\r\n')
        time.sleep(2)
    
    # 执行命令
    sock.send((command + '\r\n').encode())
```

## 🎯 测试用例

### VLAN 配置
```
输入："创建 H3C vlan 10 20"
期望输出：vlan batch 10 20
执行：成功
```

### VLAN 查看
```
输入："查看 vlan"
期望输出：display vlan
执行：成功
```

### 接口查看
```
输入："查看接口"
期望输出：display interface brief
执行：成功
```

## ⚠️ 踩坑记录

### 1. 函数名冲突
```python
# ❌ 错误
def save_llm_config():
    save_llm_config({...})  # 递归调用自己！

# ✅ 正确
from data_persistence import save_llm_config as persist_llm_config

def save_llm_config():
    persist_llm_config({...})  # 调用模块函数
```

### 2. 端口丢失
```python
# ❌ 错误：保存时未包含 port
topology_data = {'devices': [{'ip': dev.ip} for dev in devices]}

# ✅ 正确：保存端口
topology_data = {'devices': [{
    'ip': dev.ip,
    'port': device_ports.get(dev.ip, 23)
} for dev in devices]}
```

### 3. api_key 未保存
```python
# ❌ 错误：data_persistence.py 未保存 api_key
save_data = {
    'provider': config_data.get('provider'),
    'endpoint': config_data.get('endpoint'),
    'model': config_data.get('model')
    # 缺少 api_key!
}

# ✅ 正确
save_data = {
    'provider': config_data.get('provider'),
    'endpoint': config_data.get('endpoint'),
    'api_key': config_data.get('api_key', ''),  # 包含 api_key
    'model': config_data.get('model')
}
```

### 4. 编码问题
```python
# ❌ 错误：print 包含 emoji 导致 Windows GBK 编码失败
print("✅ 已加载")

# ✅ 正确：使用 ASCII 或处理编码
print("[OK] 已加载")
# 或
print("✅ 已加载".encode('utf-8'))
```

## 🚀 下一步进化

### 高优先级
1. **多设备支持** - 支持批量配置多个设备
2. **配置回滚** - 保存配置快照，支持一键回滚
3. **错误重试** - 设备连接失败自动重试

### 中优先级
4. **配置模板** - 预定义常用配置模板
5. **定时任务** - 定期备份配置
6. **日志审计** - 记录所有配置操作

### 低优先级
7. **Web 终端** - 浏览器直接 SSH 到设备
8. **拓扑可视化** - 自动绘制网络拓扑图
9. **配置对比** - 对比 running-config 和 backup

## 📝 核心原则

1. **LLM 优先** - 让 LLM 理解意图，不用硬编码关键词
2. **上下文传递** - 设备厂商、数量等信息传给 LLM
3. **简洁输出** - Prompt 强调"只返回命令，不要解释"
4. **状态持久化** - 设备、模型配置自动保存和加载
5. **优雅降级** - LLM 失败时显示友好错误信息

---

**最后更新：** 2026-03-27 15:43
**版本：** Evolution v1.0
**状态：** ✅ 生产就绪
