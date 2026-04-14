# NetOps AI 功能补全设计文档

**日期：** 2026-04-14  
**方案：** B - 功能补全（3-4 小时）  
**状态：** 设计已确认，待实施

---

## 目标

完善 NetOps AI 项目的核心功能，提升诊断能力和可追溯性。

---

## 功能清单

### 1. 会话管理集成

**目标：** 支持多轮对话和上下文引用

**实现：**
- 在 `executor.py` 中集成 `SessionManager`
- 支持场景：
  - "查一下 SW-Core 的 VLAN" → 记住 SW-Core
  - "再查一下它的接口" → 自动引用 SW-Core
  - "那台设备的配置呢？" → 自动引用最近设备

**文件：**
- 修改：`app/nl_router/executor.py`
- 使用：`app/session/manager.py`（已存在）

---

### 2. 知识库模块

**目标：** 诊断引擎能积累经验，快速定位相似问题

**实现：**
- 创建 `app/diagnosis/knowledge_base.py`
- 数据结构：`DiagnosisCase`（问题、症状、根因、解决方案）
- 功能：
  - `save_case()` - 保存诊断案例
  - `search_similar()` - 搜索相似案例
  - `get_common_solutions()` - 获取常见解决方案
- 集成到 `DiagnosisEngine`

**文件：**
- 新增：`app/diagnosis/knowledge_base.py`
- 修改：`app/diagnosis/engine.py`

---

### 3. 审计日志

**目标：** 记录所有操作，满足合规要求，支持问题追溯

**实现：**
- 创建 `app/audit/audit_log.py`
- 数据结构：`AuditEntry`（时间、用户、操作、目标、结果）
- 功能：
  - `log()` - 记录审计日志
  - `query()` - 查询审计日志
  - `export()` - 导出审计日志（CSV/Excel）
- 集成到 `NaturalLanguageExecutor`

**文件：**
- 新增：`app/audit/__init__.py`
- 新增：`app/audit/audit_log.py`
- 修改：`app/nl_router/executor.py`

---

## 实施计划

### Phase 2: Writing Plans（待启动）

任务拆解（每个 2-5 分钟）：

1. **会话管理集成**
   - [ ] 在 executor.py 中导入 SessionManager
   - [ ] 修改 execute() 方法，添加会话管理逻辑
   - [ ] 测试多轮对话

2. **知识库模块**
   - [ ] 创建 knowledge_base.py
   - [ ] 实现 DiagnosisCase 数据结构
   - [ ] 实现 KnowledgeBase 类
   - [ ] 集成到 engine.py
   - [ ] 测试案例保存和检索

3. **审计日志**
   - [ ] 创建 app/audit/ 目录
   - [ ] 创建 audit_log.py
   - [ ] 实现 AuditEntry 数据结构
   - [ ] 实现 AuditLogger 类
   - [ ] 集成到 executor.py
   - [ ] 测试日志记录

4. **代码提交**
   - [ ] 提交设计文档
   - [ ] 提交功能代码
   - [ ] 更新 README

---

## 预期效果

- **多轮对话：** 用户可以说"再查一下那台设备"，系统自动引用上下文
- **经验积累：** 诊断引擎能从历史案例中学习，快速定位问题
- **合规审计：** 所有操作有记录，可追溯，可导出

---

## 风险

- 知识库检索可能不够智能（关键词匹配）
- 审计日志可能影响性能（异步写入可缓解）

---

**下一步：** 进入 Phase 2: Writing Plans，拆解详细任务
