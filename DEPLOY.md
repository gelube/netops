# NetOps AI 部署指南

## 快速开始

### 1. 安装依赖

```bash
cd Z:\netops-ai
pip install -r requirements.txt
```

### 2. 配置 NetBrain MCP（可选）

如果需要使用 NetBrain 集成功能：

```bash
cd netbrain-mcp
uv sync
cp .env.example .env
# 编辑 .env 填入 NetBrain 凭证
```

### 3. 配置 LLM

编辑 `main_nl.py` 或 `test_nl_parser.py`：

```python
llm_config = LLMConfig(
    provider="openai",
    endpoint="http://localhost:11434/v1",  # 或 https://api.openai.com/v1
    api_key="your-api-key",
    model="qwen2.5:7b"  # 或 gpt-4, claude-3-sonnet 等
)
```

**推荐配置：**

| 场景 | Provider | Endpoint | Model |
|------|----------|----------|-------|
| 本地测试 | openai | http://localhost:11434/v1 | qwen2.5:7b |
| 生产环境 | openai | https://api.openai.com/v1 | gpt-4-turbo |
| 国产模型 | openai | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-max |
| Anthropic | anthropic | https://api.anthropic.com | claude-3-sonnet-20240229 |

---

## 测试

### 测试意图解析

```bash
python test_nl_parser.py
```

预期输出：
```
🔍 测试 LLM 连接...
✅ LLM 连接成功，可用模型：['qwen2.5:7b', ...]

============================================================
开始测试意图解析
============================================================

输入：查一下 SW-Core 的配置
期望：query_config
✅ 通过 (置信度：0.95)
------------------------------------------------------------
...
```

### 测试自然语言命令行

```bash
python main_nl.py
```

预期输出：
```
╔══════════════════════════════════════════════════════════╗
║        NETOPS AI - 自然语言网络运维                      ║
╚══════════════════════════════════════════════════════════╝

✅ LLM 连接成功：qwen2.5:7b

🔹 NetOps> 查一下 SW-Core 的配置
```

### 测试 TUI 界面

```bash
python main.py
```

---

## 使用示例

### 查询类

```
🔹 NetOps> 查一下 SW-Core 的配置
🔹 NetOps> SW-Core 的邻居有哪些
🔹 NetOps> 查看最近的告警事件
🔹 NetOps> 从 10.10.10.1 到 8.8.8.8 的路径是什么
```

### 配置类

```
🔹 NetOps> 给 SW-Core 的 1-4 口配 VLAN 10
🔹 NetOps> 把 GE0/0/1 的 IP 改成 192.168.1.1
🔹 NetOps> 添加一条默认路由到 10.0.0.1
```

配置流程：
1. 解析意图，生成命令
2. 显示确认信息（设备、IP、命令列表）
3. 输入 y 确认
4. 输入 SSH 用户名密码
5. 执行配置

### 诊断类

```
🔹 NetOps> VLAN 10 上不了网，帮我查一下
🔹 NetOps> 路由不通，帮我查一下
🔹 NetOps> 为什么 ping 不通网关
```

诊断输出：
```
✅ VLAN 10 诊断完成：发现 1 个问题

诊断步骤:
  ✅ 搜索相关设备 - 找到 3 台相关设备
  ❌ 检查 VLAN 10 配置 - VLAN 未创建
  ✅ 检查邻居关系 - 找到 5 个邻居
  ✅ 检查相关事件 - 无相关事件

建议:
  • 创建 VLAN 10: vlan 10
```

---

## 故障排查

### LLM 连接失败

检查点：
1. LLM 服务是否运行（Ollama: `ollama list`）
2. Endpoint URL 是否正确
3. API Key 是否需要

### MCP 连接失败

检查点：
1. `netbrain-mcp/.env` 是否配置
2. NetBrain 实例是否可达
3. 凭证是否正确

### SSH 执行失败

检查点：
1. 设备 IP 是否可达（`ping <ip>`）
2. SSH 端口是否开放（`telnet <ip> 22`）
3. 用户名密码是否正确

---

## 项目结构

```
netops-ai/
├── app/
│   ├── core/           # 核心模块
│   ├── network/        # SSH/命令映射
│   ├── llm/            # LLM 客户端
│   ├── nl_router/      # 自然语言路由（新增）
│   │   ├── parser.py   # 意图解析
│   │   └── executor.py # 执行器
│   ├── ui/             # TUI 界面
│   └── mcp_client.py   # MCP 客户端包装器（新增）
├── netbrain-mcp/       # NetBrain MCP 服务器
├── main.py             # TUI 入口
├── main_nl.py          # 自然语言入口（新增）
├── test_nl_parser.py   # 意图解析测试（新增）
├── requirements.txt
├── README.md
└── DEPLOY.md           # 本文件
```

---

## 下一步

1. **生产环境部署**
   - 配置持久化（凭证加密存储）
   - 日志记录
   - 配置审计

2. **功能扩展**
   - 批量配置（多台设备同时配置）
   - 配置模板（常用配置保存为模板）
   - 配置对比（变更前后对比）

3. **集成优化**
   - 拓扑发现结果喂给 LLM
   - 诊断工作流可视化
   - Web 界面集成自然语言输入
