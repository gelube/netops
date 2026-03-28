# Web 界面修复

## 问题 1：LLM 状态显示不正确

**原因：** 
- 保存配置后没有更新前端状态
- `/api/llm/config` GET 接口返回的数据格式问题

**修复方案：**
1. 保存配置后返回完整配置
2. 前端收到响应后立即更新状态栏
3. 添加错误提示

---

## 问题 2：生成 VLAN 报错（符号不对）

**原因：**
- Telnet 设备需要先进入系统视图 (`system-view`)
- 命令之间需要适当的延迟
- 多条命令需要分开发送

**华为设备正确流程：**
```
<HW> system-view          # 进入系统视图
[~HW] vlan batch 10 20    # 创建 VLAN
[~HW] quit                # 退出
```

**当前问题：**
- 直接发送 `vlan batch 10 20`（在用户视图，无效）
- 没有等待命令完成

**修复方案：**
1. 检测命令类型，自动添加 `system-view`
2. 多条命令分开发送，每条等待 2 秒
3. 最后发送 `quit` 退出

---

## 修复代码

### 1. 修复 netbrain_integration.py

```python
def execute_command(self, ip: str, port: int, command: str, ...):
    # ... 连接代码 ...
    
    # 进入系统视图（如果需要）
    needs_system_view = any(x in command.lower() for x in [
        'vlan', 'interface', 'ospf', 'bgp', 'ip route', 
        'port-security', 'sysname'
    ])
    
    if needs_system_view:
        sock.send(b'system-view\r\n')
        time.sleep(2)
        sock.recv(4096)  # 清空缓冲区
    
    # 执行命令
    sock.send((command + '\r\n').encode())
    time.sleep(2)
    
    # 退出系统视图
    if needs_system_view:
        sock.send(b'quit\r\n')
        time.sleep(1)
    
    # ... 读取输出 ...
```

### 2. 修复前端状态显示

在 `save_llm_config` 函数中：
```javascript
fetch('/api/llm/config', {
    method: 'POST',
    ...
})
.then(res => res.json())
.then(data => {
    if (data.success) {
        // 立即更新状态栏
        const statusEl = document.getElementById('llm-status');
        statusEl.textContent = `LLM: ${data.model || data.endpoint}`;
        document.getElementById('settings-modal').classList.remove('active');
    }
})
```

---

## 测试步骤

### 测试 1：LLM 配置
1. 点击"⚙️ 模型设置"
2. 配置 API Endpoint 和 Key
3. 选择模型
4. 点击"保存配置"
5. **检查：** 状态栏应该显示 `LLM: qwen2.5:7b` 或模型名

### 测试 2：创建 VLAN
1. 在聊天框输入："创建 VLAN 10 和 20"
2. **检查：** 应该成功执行，显示：
   ```
   【自动执行命令】
   设备：127.0.0.1:30001
   命令：vlan batch 10 20
   
   【执行结果】
   Success
   ```

---

## 待办事项

- [ ] 修复 netbrain_integration.py（添加 system-view）
- [ ] 修复前端 LLM 状态更新
- [ ] 测试 VLAN 创建
- [ ] 测试 LLM 配置保存
