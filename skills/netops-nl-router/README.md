# NetOps 自然语言路由 Skill

## 快速开始

```bash
# 进入项目目录
cd Z:\netops-ai

# 测试自然语言交互
python main_nl.py
```

## 示例对话

```
🔹 NetOps> 查一下 SW-Core 的配置
✅ MCP 工具 get_device_config 执行成功
[返回配置文本]

🔹 NetOps> 给 SW-Core 的 1-4 口配 VLAN 10
⚠️  待确认配置:
设备：SW-Core
即将执行 4 条配置命令：
  1. interface range GE0/0/1 to GE0/0/4
  2. port link-type access
  3. port default vlan 10
  4. quit

⚠️  配置将立即生效，请确认无误后执行

是否执行？(y/n): y
⚠️  需要配置设备凭证（待实现）

🔹 NetOps> VLAN 10 上不了网，帮我查一下
✅ VLAN 10 诊断报告
[诊断步骤和结果]
```

## 配置 LLM

编辑 `main_nl.py`：

```python
llm_config = LLMConfig(
    provider="openai",           # 或 "anthropic" / "aliyun" / "custom"
    endpoint="http://localhost:11434/v1",  # Ollama 本地
    # endpoint="https://api.openai.com/v1",  # OpenAI
    api_key="ollama",
    model="qwen2.5:7b"           # 或 "gpt-4o", "claude-sonnet-4-20250514"
)
```

## 集成到现有项目

```python
# 1. 导入模块
from app.nl_router.executor import NLExecutor
from app.llm.config import LLMClient, LLMConfig

# 2. 初始化
llm = LLMClient(LLMConfig(provider="openai", endpoint="...", api_key="..."))
executor = NLExecutor(llm_client=llm)

# 3. 执行
result = await executor.execute("用户输入")

# 4. 处理结果
if result.requires_confirmation:
    # 显示确认信息
    print(result.confirmation_details)
elif result.success:
    # 处理成功结果
    print(result.data)
else:
    # 处理错误
    print(result.message)
```

## 下一步开发

1. **集成 NetBrain MCP 客户端**
   ```python
   from netbrain_mcp.client import NetBrainClient
   from netbrain_mcp.config import get_settings
   
   settings = get_settings()
   mcp_client = NetBrainClient(settings)
   executor = NLExecutor(mcp_client=mcp_client, llm_client=llm)
   ```

2. **实现诊断工作流**
   - `nl_router/executor.py` 中的 `_diagnose_vlan()` 等方法
   - 组合多个 MCP 工具执行检查序列

3. **配置凭证管理**
   - 加密存储设备 SSH 凭证
   - 从 MCP 自动获取设备 IP/厂商

4. **单元测试**
   ```bash
   pytest tests/test_nl_router.py -v
   ```

## 文件结构

```
skills/netops-nl-router/
├── SKILL.md          # 技能说明文档
├── README.md         # 本文件
└── examples/         # 示例（待添加）
    ├── intent_examples.json
    └── diagnosis_examples.json
```

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## License

MIT License
