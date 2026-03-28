# NetOps Natural Language Router Skill

用自然语言配置网络和排查故障的 AI 能力封装。

## 能力说明

将网络工程师的自然语言请求转换为：
1. **MCP 工具调用** - 查询设备、配置、邻居、路径、事件、触发诊断
2. **SSH 配置执行** - VLAN、接口、路由、ACL 配置（带确认机制）
3. **自动诊断工作流** - VLAN/路由/连通性故障排查

## 触发条件

用户输入包含以下意图时自动激活：

**查询类**
- "查一下 XXX 的配置"
- "XXX 的邻居有哪些"
- "从 A 到 B 的路径"
- "最近有什么告警"

**配置类**
- "给 XXX 配 VLAN X"
- "把 X 口加入 VLAN Y"
- "配置静态路由"
- "加一条 ACL 规则"

**排障类**
- "VLAN X 上不了网"
- "XXX  ping 不通"
- "帮我查一下为什么..."

## 使用方式

### 方式 1：直接调用 Python 模块

```python
from app.llm.config import LLMConfig, LLMClient
from app.nl_router.executor import NLExecutor

# 初始化
llm_config = LLMConfig(
    provider="openai",
    endpoint="http://localhost:11434/v1",
    api_key="ollama",
    model="qwen2.5:7b"
)

executor = NLExecutor(llm_client=llm_client)

# 执行自然语言请求
result = await executor.execute("给 SW-Core 的 1-4 口配 VLAN 10")

if result.requires_confirmation:
    print(result.confirmation_details)
    # 用户确认后执行
    # await executor.confirm_and_execute(...)
```

### 方式 2：命令行交互

```bash
python main_nl.py
```

### 方式 3：MCP 工具暴露（待实现）

将 `nl_router` 封装为 MCP Server，供其他 Agent 调用。

## 核心组件

```
nl_router/
├── parser.py       # 意图解析器（LLM Prompt 驱动）
│   ├── IntentParser
│   │   ├── parse()           # 主入口：自然语言 → ParsedIntent
│   │   ├── _classify_intent() # LLM 意图分类
│   │   ├── _map_to_mcp_tool() # 映射到 MCP 工具
│   │   └── generate_config_commands() # LLM 生成配置命令
│   └── ParsedIntent          # 结构化意图数据模型
│
└── executor.py     # 执行器
    ├── NLExecutor
    │   ├── execute()              # 主入口：执行用户请求
    │   ├── _execute_mcp()         # MCP 工具调用
    │   ├── _execute_ssh_config()  # SSH 配置执行
    │   ├── confirm_and_execute()  # 用户确认后执行
    │   └── _execute_diagnosis()   # 诊断工作流
    └── ExecutionResult            # 执行结果数据模型
```

## 支持的意图类型

| 类型 | 意图 | MCP 工具 | SSH 执行 |
|------|------|---------|---------|
| query_device | 查询设备 | search_devices | ❌ |
| query_config | 查询配置 | get_device_config | ❌ |
| query_neighbors | 查询邻居 | get_neighbors | ❌ |
| query_path | 路径查询 | calculate_path | ❌ |
| query_events | 事件查询 | get_events | ❌ |
| run_diagnosis | 触发诊断 | trigger_diagnosis | ❌ |
| config_vlan | 配置 VLAN | ❌ | ✅ |
| config_interface | 配置接口 | ❌ | ✅ |
| config_routing | 配置路由 | ❌ | ✅ |
| config_acl | 配置 ACL | ❌ | ✅ |
| diagnose_vlan | VLAN 诊断 | 组合工具 | 部分 |
| diagnose_routing | 路由诊断 | 组合工具 | 部分 |
| diagnose_connectivity | 连通性诊断 | 组合工具 | 部分 |

## 配置命令生成示例

**输入：**
> "给 SW-Core 的 1-4 口配 VLAN 10"

**华为设备输出：**
```
interface range GE0/0/1 to GE0/0/4
port link-type access
port default vlan 10
quit
```

**思科设备输出：**
```
interface range GigabitEthernet0/1 - 4
switchport mode access
switchport access vlan 10
exit
```

## 诊断工作流示例

**VLAN 连通性诊断流程：**

1. 检查 VLAN 是否创建 → `get_device_config` + 解析
2. 检查接口成员 → `get_device_config` + 解析
3. 检查 Trunk 允许列表 → `get_device_config` + 解析
4. 检查 SVI 状态 → `get_device_attributes`
5. 检查默认路由 → `calculate_path`

**输出格式：**
```
VLAN 10 诊断报告
━━━━━━━━━━━━━━━━
✅ VLAN 10 已创建
❌ GE0/0/1 未加入 VLAN 10
✅ Vlanif10 状态 UP
✅ 默认路由存在

根因：接入端口未配置 VLAN 成员
建议：执行以下配置命令：...
```

## 依赖

- Python 3.12+
- LLM 客户端（OpenAI/Anthropic/Ollama）
- NetBrain MCP 客户端（可选，用于查询）
- Netmiko（可选，用于 SSH 配置执行）

## 安全注意

1. **配置执行前必须用户确认** - `requires_confirmation=True`
2. **敏感信息不日志化** - 密码、API Key 不打印
3. **幂等性检查** - 避免重复配置
4. **配置备份** - 执行前自动备份（待实现）

## 扩展方向

1. **增加意图类型** - QoS、SNMP、NetFlow 等
2. **增加诊断工作流** - BGP、OSPF、STP 专项诊断
3. **配置回滚** - 执行失败自动回滚
4. **批量操作** - 多台设备同时配置
5. **配置审计** - 记录所有配置变更

## 测试用例

```python
# 意图解析测试
test_cases = [
    ("查一下 SW-Core 的配置", "query_config", {"device": "SW-Core"}),
    ("给 SW-Core 的 1-4 口配 VLAN 10", "config_vlan", {"vlan": 10, "interfaces": ["1-4"]}),
    ("VLAN 10 上不了网", "diagnose_vlan", {"vlan_id": 10}),
    ("从 10.10.10.1 到 8.8.8.8 的路径", "query_path", {"source": "10.10.10.1", "dest": "8.8.8.8"}),
]
```

## 状态

- ✅ 意图解析框架完成
- ✅ 配置命令生成完成
- ✅ 执行器框架完成
- ⚠️ MCP 客户端集成待完成
- ⚠️ 诊断工作流待实现
- ⚠️ 配置备份/回滚待实现
