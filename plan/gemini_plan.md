# Vibe Investment Multi-Agent Engine 开发计划 (Phase 1)

**指导原则**: 敏捷开发 (Agile), 最小可行性产品 (MVP), 可验证性 (Verifiability).

## 阶段 1: 基础设施搭建与原型验证 (Phase 1: Infrastructure & Hello World)
**目标**: 建立项目骨架，验证 `uv` 环境与 `LangGraph` 最小链路跑通。

### Iteration 1.1: 环境与基础架构
- [ ] **任务**: Initialize project with `uv`.
- [ ] **任务**: Setup basic directory structure (`src/`, `tests/`, `config/`).
- [ ] **任务**: Install core dependencies (`langgraph`, `langchain`, `pydantic`, `openai` compatible client).
- [ ] **验证**: `uv run python -c "import langgraph; print('Success')"` 无报错。

### Iteration 1.2: 最小 LangGraph run
- [ ] **任务**: 实现一个最简 FSM：`Start -> Node A -> End`。
- [ ] **任务**: 定义基础 State (包含 `vibe` 字段)。
- [ ] **验证**: 运行脚本，输入 "test vibe"，输出经过 Node A 处理后的结果。

---

## 阶段 2: 核心组件实现 (Phase 2: Core Components - MVP)
**目标**: 实现 Planner, Expert, Talent 的核心逻辑（先使用 Mock/Fake LLM 确保流程控制正确，再接入真实 API）。

### Iteration 2.1: Expert Swarm (并发与多样性)
- [ ] **任务**: 定义 `Expert` 类与 Prompt 模板（支持 10 个角色配置）。
- [ ] **任务**: 实现 `Expert_Swarm` 节点，支持并发/扇出 (Fan-out)。
- [ ] **验证**: 单元测试 - 输入一个 Topic，10 个 Expert 节点能并发返回不同的 Mock 观点。

### Iteration 2.2: Talent (收敛与总结)
- [ ] **任务**: 定义 `Talent` 类与 Prompt 模板（支持 战略家/选股手/审计 模式切换）。
- [ ] **任务**: 实现 `Talent` 节点，接收 Expert 列表输出，进行聚合 (Fan-in)。
- [ ] **验证**: 单元测试 - 输入 10 个 Expert 的 Mock 观点，Talent 能输出一个通过 Mock 规则生成的总结。

### Iteration 2.3: Planner (路由与控制)
- [ ] **任务**: 定义 `Planner` 状态评估逻辑 (信息充分度打分)。
- [ ] **任务**: 实现 Workflow 状态机控制 (价值发现 -> 标的锁定 -> 逻辑验证)。
- [ ] **验证**: 单元测试 - 模拟“信息不充分”状态，Planner 能正确返回需继续迭代的指令及 `Vibe_Next`。

---

## 阶段 3: FSM 组装与闭环 (Phase 3: Wiring & Loop)
**目标**: 将组件组装成完整的有向循环图，接入真实 LLM (DeepSeek)，实现动态流转。

### Iteration 3.1: 完整拓扑构建
- [ ] **任务**: 在 LangGraph 中连接 `Planner -> Expert_Swarm -> Talent -> Planner`。
- [ ] **任务**: 实现最大轮数控制 (Max Iterations) 防止死循环。
- [ ] **任务**: 接入 DeepSeek API (Reasoner for Thinking, Chat for Routing)。
- [ ] **验证**: 运行集成测试，系统能在达到最大轮数或信息充分后正常退出。

### Iteration 3.2: 模式切换与配置
- [ ] **任务**: 实现 Config 注入，支持用户选择 “价值发现”、“标的锁定”、“逻辑验证” 模式。
- [ ] **验证**: 分别用三种模式启动，验证 FSM 路径是否符合预期（例如“逻辑验证”模式下不应回到“价值发现”阶段）。

---

## 阶段 4: 用户交互与交付 (Phase 4: CLI & Polish)
**目标**: 构建友好的 CLI，展示思考过程，完成最终验收。

### Iteration 4.1: 交互式 CLI
- [ ] **任务**: 使用 `rich` 或类似库构建 CLI 界面。
- [ ] **任务**: 实现用户输入 Vibe 接口。
- [ ] **任务**: 实时显示当前活跃节点 (Spinner/Progress)。
- [ ] **验证**: 启动 CLI，输入 Vibe，能看到系统在各节点间的流转状态。

### Iteration 4.2: 思考过程流式展示
- [ ] **任务**: 解析并展示 Expert/Talent 的 `<think>` 过程 (DeepSeek Reasoner 特性)。
- [ ] **任务**: 格式化输出最终报告与风险提示。
- [ ] **验证**: 运行完整流程，CLI 清晰展示“思考中...”内容及最终 Markdown 报告。

### Iteration 4.3: 验收测试 (End-to-End)
- [ ] **任务**: 运行需求文档中的 "Neural-Link" 案例。
- [ ] **验证**: 能够复现或近似文档描述的决策链条（发散->收敛->迭代->锁定->验证）。

---

## 待办清单管理
> 每次开始 coding 前，请确认当前 Iteration 目标并 Check `task.md`。

- [ ] Phase 1 完成
- [ ] Phase 2 完成
- [ ] Phase 3 完成
- [ ] Phase 4 完成
