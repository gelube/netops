# NetOps AI

网络工程师智能助手 - 基于 LLM 的自动化网络管理工具

**纯 SSH 模式** - 无需 NetBrain，直接 SSH 连接设备

## 特性

- 🎮 **Hacknet 风格终端 UI** - 黑客终端风格界面
- 🔍 **自动拓扑发现** - 从种子设备自动发现整个网络拓扑
- 🖥️ **多厂商支持** - 华为、华三、思科、Juniper、锐捷
- 🔗 **链路关系显示** - 聚合、VRRP、堆叠、OSPF 等
- 🧠 **AI 助手** - 基于 LLM 的网络排障辅助
- 💬 **自然语言配置** - 用自然语言配置网络
- 🔌 **纯 SSH 模式** - 无需 NetBrain，直接连接设备
- 📦 **配置模板库** - 10 个预定义模板
- 🔐 **凭证加密存储** - 支持系统 keyring
- 💾 **配置备份/回滚** - 自动备份，支持恢复

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

**自然语言命令行（推荐）:**
```bash
python main_nl.py
```

**传统 TUI 界面:**
```bash
python main.py
```

### 配置 LLM

编辑 `main_nl.py`:

```python
llm_config = LLMConfig(
    provider="openai",
    endpoint="http://localhost:11434/v1",  # Ollama 本地
    api_key="ollama",
    model="qwen2.5:7b"
)
```

## 使用说明

### 自然语言命令

**支持通俗说法，不需要懂专业术语！**

```bash
# 启动
python main_nl.py

# 专业说法（支持）
🔹 NetOps> 给 SW-Core (IP: 192.168.1.1) 的 1-4 口配 VLAN 10
🔹 NetOps> VLAN 10 上不了网，帮我查一下

# 通俗说法（也支持！）
🔹 NetOps> 财务部的电脑上不了网，帮我看看
🔹 NetOps> 把访客网络的口子开到 1-8
🔹 NetOps> 1 号到 4 号口都通上网
🔹 NetOps> 监控室没网络了
🔹 NetOps> 封掉 192.168.1.100 这个设备

# 保存凭证（避免每次输入）
🔹 NetOps> !save SW-Core 192.168.1.1 admin password123

# 列出已保存的设备
🔹 NetOps> !list
```

### 特殊命令

| 命令 | 说明 |
|------|------|
| `!save hostname ip user pass [port]` | 保存设备凭证 |
| `!list` | 列出已保存的设备 |
| `quit` / `exit` | 退出程序 |

### 配置模板

内置 10 个模板，自动匹配：

| 模板 | 专业说法 | 通俗说法 |
|------|---------|---------|
| 批量 Access VLAN | "给 SW-Core 的 1-4 口配 VLAN 10" | "1 号到 4 号口都通上网" |
| Trunk 配置 | "把 GE0/0/24 配成 trunk，允许 VLAN 10 20 30" | - |
| SVI 配置 | "给 VLAN 10 配网关 192.168.10.1/24" | "给财务部配个网关" |
| 静态路由 | "添加静态路由 10.0.0.0/8 下一跳 192.168.1.1" | - |
| 默认路由 | "添加默认路由指向 192.168.1.1" | "设个默认出口" |
| OSPF 配置 | "配置 OSPF 进程 1 区域 0 宣告 192.168.10.0/24" | - |
| 端口安全 | "给 GE0/0/1 配置端口安全，最大 2 个 MAC" | - |
| 接口描述 | "给 GE0/0/1 加描述 'Link to SW-Access-1'" | - |
| 交换机初始化 | "初始化新交换机 SW-Access-1..." | - |
| ACL 封禁 | "禁止访问 192.168.1.100" | "封掉 192.168.1.100" |

**部门/区域自动映射：**
- "财务部" → VLAN 10
- "人事部/行政部" → VLAN 20
- "技术部/研发部" → VLAN 30
- "访客/会议室" → VLAN 100
- "监控室/安防" → VLAN 200

### 诊断功能

**VLAN 诊断（5 步检查）:**
```
🔹 NetOps> VLAN 10 上不了网，帮我查一下

✅ VLAN 10 诊断完成

诊断步骤:
  ✅ 检查 VLAN 10 是否创建
  ❌ 检查接口是否加入 VLAN
  ✅ 检查 Trunk 是否允许 VLAN
  ✅ 检查 SVI 接口状态
  ✅ 检查默认路由

根因：接口未加入 VLAN
建议:
  • 将接口加入 VLAN：interface <name> → port default vlan 10
```

**路由诊断:**
```
🔹 NetOps> OSPF 邻居起不来

✅ OSPF 路由诊断完成

诊断步骤:
  ❌ 检查 OSPF 邻居状态
  ✅ 检查 OSPF 接口配置
  ...
```

## 项目结构

```
netops-ai/
├── app/
│   ├── core/           # 核心模块
│   │   ├── device.py
│   │   ├── vendor.py
│   │   └── discovery.py
│   ├── network/        # 网络接入
│   │   ├── ssh.py
│   │   ├── lldp.py
│   │   └── commands.py
│   ├── llm/            # LLM 客户端
│   │   └── config.py
│   ├── nl_router/      # 自然语言路由
│   │   ├── parser.py      # 意图解析
│   │   ├── executor.py    # 执行器
│   │   ├── intent_types.py # 意图类型定义
│   │   └── language_map.py # 通俗语言映射
│   ├── credentials.py     # 凭证管理
│   ├── config_backup.py   # 配置备份/回滚
│   └── config_templates.py # 配置模板库（10 个）
├── scripts/
│   ├── proactive_monitor.py # 健康检查
│   └── run_heartbeat.ps1    # 心跳脚本
├── notes/              # 主动发现记录
├── main.py             # TUI 入口
├── main_nl.py          # 自然语言入口
└── tests/
    └── test_nl_router.py
```

## 运行测试

```bash
pytest tests/test_nl_router.py -v
# 16 passed
```

## 健康检查

```bash
python scripts/proactive_monitor.py
```

## Proactive Agent 模式

本项目采用 **Proactive Agent** 架构：

- **自动健康检查** - 每次会话前自动运行
- **心跳自检** - 每日自动检查
- **用户行为模式** - 记录重复需求，主动建议
- **惊喜想法池** - 定期实现高价值功能

详见：`HEARTBEAT.md`, `SESSION-STATE.md`

## 可选：NetBrain 集成

如果有 NetBrain 商业软件，配置环境变量：

```bash
export NETBRAIN_URL=https://your-netbrain-instance.com
export NETBRAIN_USERNAME=api_user
export NETBRAIN_PASSWORD=***
export NETBRAIN_DOMAIN=your_domain
```

系统会自动启用 NetBrain 能力，否则降级到纯 SSH 模式。

## License

MIT License
