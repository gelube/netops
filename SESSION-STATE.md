# NetOps AI - 会话状态

**最后更新：** 2026-03-27 20:35

---

## 当前任务：Web 界面重构

### 问题描述
1. 前端按钮点击无响应
2. ID 冲突（HTML 与 topology.js 不匹配）
3. 界面需要中文化
4. 代码结构混乱

### 用户需求（WAL 记录）
- 使用本地 LLM（Ollama），API Key 可留空
- 填完 URL 后自动获取模型列表
- 中文界面
- 保存设备和模型配置
- **设备连接方式**：支持 Telnet/SSH/串口
- **设备配置能力**：LLM 能够对设备进行配置操作
- **设备自动识别**：添加设备后自动识别设备类型和名字
- **LLM 行动能力**：模型收到要求后执行操作，不只是回复（类似 OpenClaw）

### 解决方案
按照 Proactive Agent 架构重构：
1. 清晰的前后端分离
2. 统一的事件绑定方式
3. 中文化界面
4. 自动获取模型功能

---

## 项目结构

```
Z:\netops-ai\
├── web/
│   ├── app_local.py          # 后端服务
│   ├── templates/
│   │   └── index.html        # 前端页面
│   ├── static/
│   │   ├── style.css         # 样式
│   │   └── topology.js       # 拓扑画布
│   └── data/
│       ├── llm_config.json   # LLM 配置
│       └── devices.json      # 设备列表
├── app/
│   ├── nl_router/            # 自然语言路由
│   ├── llm/                  # LLM 客户端
│   └── network/              # 网络操作
└── SESSION-STATE.md
```

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/llm/config` | GET/POST | LLM 配置 |
| `/api/llm/test` | POST | 测试连接 + 获取模型 |
| `/api/devices` | GET | 设备列表 |
| `/api/device/add` | POST | 添加设备 |
| `/api/device/delete` | POST | 删除设备 |
| `/api/discover` | POST | 拓扑发现 |
| `/api/chat` | POST | AI 对话 |
| `/api/template/list` | GET | 模板列表 |

---

## 已保存配置

**LLM:**
```json
{
  "endpoint": "http://localhost:11434/v1",
  "model": "qwen2.5:7b",
  "api_key": ""
}
```

**设备:**
```json
[{
  "id": "dev_1",
  "name": "SW-Core",
  "ip": "192.168.1.1",
  "port": 23
}]
```

---

## 下一步
1. 重写前端（不依赖 topology.js 的事件绑定）
2. 简化界面
3. 测试所有按钮功能