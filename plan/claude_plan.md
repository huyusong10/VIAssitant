# Vibe Investment 多智能体分析引擎 — 特性开发手册

> 指导原则：敏捷开发 · 最小功能实现 · 每步可验证
> 需求来源：`requirement/req.md` (Phase 1)

---

## 迭代总览

| 迭代 | 名称 | 核心交付 | 预计工作量 |
|------|------|----------|-----------|
| S0 | 项目脚手架 | 可运行的空壳项目 | 小 |
| S1 | 单专家直通车 | 1个专家节点 → 直接输出 | 小 |
| S2 | 专家集群扇出/扇入 | N个专家并发 + 结果汇聚 | 中 |
| S3 | Talent 收敛节点 | 专家意见交叉比对 + 涌现 | 中 |
| S4 | Planner 控制阀 | 充分度评估 + Vibe 变异循环 | 大 |
| S5 | 三阶段工作流串联 | 价值发现→标的锁定→逻辑验证 | 大 |
| S6 | CLI 交互体验 | 可交互命令行界面 | 中 |
| S7 | 模式切换与配置 | 自由组合工作流阶段 | 小 |
| S8 | 端到端验收 | 完整流程跑通 + 输出报告 | 中 |

---

## S0 — 项目脚手架

**目标**：建立可运行的最小项目结构，确保工具链畅通。

- [x] **S0.1** 使用 `uv` 初始化 Python 项目，创建 `pyproject.toml`
  - 验证：`uv sync` 成功，无报错
- [x] **S0.2** 安装核心依赖：`langgraph`, `langchain-openai`（DeepSeek 兼容）, `rich`（CLI 美化）
  - 验证：`uv run python -c "import langgraph; print('ok')"` 输出 ok
- [x] **S0.3** 创建项目目录结构：
  ```
  src/
    vibe_engine/
      __init__.py
      state.py        # 全局状态定义
      graph.py         # LangGraph FSM 构建
      nodes/
        __init__.py
        planner.py
        expert.py
        talent.py
      prompts/
        __init__.py    # Prompt 模板管理
      config.py        # 配置常量（轮数上限、模型选择等）
      cli.py           # CLI 入口
    main.py            # 程序入口
  ```
  - 验证：`uv run python src/main.py --help` 能输出帮助信息（哪怕只有 placeholder）
- [x] **S0.4** 配置 DeepSeek API 连接（通过环境变量 `DEEPSEEK_API_KEY`）
  - 验证：写一个最小脚本调用 DeepSeek Chat 模型，返回 "Hello"
- [x] **S0.5** 定义全局 `State` TypedDict，包含最小字段：`vibe`, `messages`, `phase`, `round`
  - 验证：能 import State 且类型检查通过（`mypy` 或手动 assert）

**完成标志**：项目能安装、能运行、能连通 LLM API。

---

## S1 — 单专家直通车

**目标**：验证"LLM 节点接收 Vibe → 输出结构化分析"的最小闭环。

- [x] **S1.1** 实现 1 个 Expert 节点函数，接收 State，调用 DeepSeek Reasoner，返回结构化输出
  - 输出格式要求：`逻辑链条` / `精简结论` / `核心风险点` 三段
  - 验证：传入一段硬编码 Vibe，检查返回的字典包含三个必须字段且非空
- [x] **S1.2** 构建最小 LangGraph 图：`START → expert_node → END`
  - 验证：`graph.invoke({"vibe": "看好新能源"})` 返回包含 expert 分析的 State
- [x] **S1.3** 实现 Prompt 模板管理：专家的系统 prompt 从配置加载，包含维度名称和角色描述
  - 验证：修改配置中的专家维度名称，输出的分析风格随之变化（人工判读）
- [x] **S1.4** 保留专家完整思考过程（`<think>` 内容）到 State 中
  - 验证：State 中存在 `expert_thoughts` 字段，内容长度 > 0

**完成标志**：一个专家能独立完成从 Vibe 到结构化分析的完整路径。

---

## S2 — 专家集群扇出/扇入

**目标**：验证多专家并发执行与结果汇聚机制。

- [x] **S2.1** 定义 10 个专家维度的 Prompt 配置（宏观冲浪者、技术布道者……第二层思维者）
  - 验证：配置文件/字典包含 10 条记录，每条有 `name`, `role_prompt` 字段
- [x] **S2.2** 实现 LangGraph `Send()` 扇出机制：Planner（此处先用简单路由替代）选取 N 个专家并发执行
  - 验证：传入选取 3 个专家的指令，State 中出现 3 条独立的专家分析结果
- [x] **S2.3** 实现扇入汇聚：所有并发专家完成后，结果合并到 `expert_results` 列表
  - 验证：`len(state["expert_results"])` 等于扇出数量
- [x] **S2.4** 并发隔离性验证：每个专家的上下文完全独立（不共享 message history）
  - 验证：检查任意两个专家的 `messages` 列表无交叉引用

**完成标志**：N 个专家能并发工作，结果正确汇聚，互不干扰。

---

## S3 — Talent 收敛节点

**目标**：实现专家意见的交叉比对与涌现机制。

- [x] **S3.1** 实现 Talent 节点函数，接收全部 `expert_results`，调用 DeepSeek Reasoner
  - 输出：`核心矛盾点` / `涌现假设` / `综合评分`
  - 验证：传入 mock 的 3 条专家意见，输出包含必须字段且逻辑上引用了多个专家观点
- [x] **S3.2** 将图拓展为：`START → fan_out(experts) → fan_in → talent → END`
  - 验证：完整 invoke 后，State 同时包含 `expert_results` 和 `talent_summary`
- [x] **S3.3** Talent 的角色 Prompt 支持根据工作流阶段动态切换（战略家/选股手/量化审计）
  - 验证：分别传入 `phase="discovery"` / `"targeting"` / `"validation"`，Talent 输出的分析侧重点明显不同（人工判读）

**完成标志**：专家→Talent 的发散-收敛单轮闭环跑通。

---

## S4 — Planner 控制阀

**目标**：实现信息充分度评估、Vibe 变异循环、轮数控制。

- [x] **S4.1** 实现 Planner 节点：接收 `talent_summary`，调用 DeepSeek Chat 模型进行充分度评估
  - 输出：`sufficiency_score`（0-10）, `decision`（"proceed" / "iterate" / "abort"）, `reasoning`
  - 验证：传入一个明显信息不足的 talent_summary，decision 应为 "iterate"
- [x] **S4.2** 实现 Vibe 变异（Vibe Mutation）：当 decision="iterate" 时，Planner 融合 talent 总结生成 `vibe_next`
  - 验证：`vibe_next` 与 `vibe_0` 不同，且包含 talent 总结中的关键信息
- [x] **S4.3** 实现条件路由：在 LangGraph 中添加 conditional_edge
  - `proceed` → 进入下一阶段（或 END）
  - `iterate` → 回到 expert_swarm 重新发散
  - `abort` → 直接 END 并输出失败报告
  - 验证：分别 mock 三种 decision，检查图的执行路径是否正确
- [x] **S4.4** 实现轮数限制：每个阶段有独立的 `max_rounds` 配置，达到上限自动 abort
  - 验证：设置 max_rounds=1，第二轮时 decision 被强制设为 "abort"
- [x] **S4.5** 实现专家选取逻辑：Planner 根据当前阶段和信息缺口选择 3-6 个专家
  - 验证：Planner 输出的 `selected_experts` 列表长度在 [1, 10] 范围内，且含专家 ID

**完成标志**：Planner 能动态评估、变异 Vibe、控制循环次数，图具备有向循环能力。

---

## S5 — 三阶段工作流串联

**目标**：将价值发现、标的锁定、逻辑验证三个阶段串联为完整流水线。

- [x] **S5.1** 定义阶段枚举与配置：
  ```python
  phases = {
    "discovery":  {"max_rounds": 5, "expert_count": (3, 6), "talent_role": "strategist"},
    "targeting":  {"max_rounds": 2, "expert_count": (2, 4), "talent_role": "stock_picker"},
    "validation": {"max_rounds": 1, "expert_count": (1, 3), "talent_role": "auditor"},
  }
  ```
  - 验证：配置可被 Planner 和 Talent 正确读取
- [x] **S5.2** 实现阶段转换：当 Planner 判定当前阶段 proceed 时，State 的 `phase` 自动递进
  - 验证：从 discovery 开始，经过 proceed 后 State.phase 变为 targeting
- [x] **S5.3** 实现标的锁定阶段的特殊输出：专家需输出具体标的（股票代码/Token/产业链节点）
  - 验证：targeting 阶段的 expert_results 中包含 `targets` 字段
- [x] **S5.4** 实现逻辑验证阶段的特殊输出：专家需输出数据推导链
  - 验证：validation 阶段的 expert_results 中包含 `data_logic_chain` 字段
- [x] **S5.5** 实现最终报告生成：三个阶段全部完成后，汇总生成结构化投资建议报告
  - 验证：最终 State 包含 `final_report` 字段，内容覆盖"结论 / 推荐标的 / 风险提示 / 全流程摘要"

**完成标志**：三阶段顺序串联跑通，每个阶段内部可循环，最终输出完整报告。

---

## S6 — CLI 交互体验

**目标**：实现可交互的命令行界面，满足用户体验要求。

- [x] **S6.1** 使用 `rich` 实现基础 CLI 框架：欢迎信息、Vibe 输入提示、退出命令
  - 验证：运行 `main.py`，能看到美化的欢迎界面，能输入 Vibe 文本
- [x] **S6.2** 实现实时状态展示：显示当前阶段、当前轮数、正在思考的专家列表
  - 验证：运行时 CLI 动态显示 "专家 [宏观冲浪者, 技术布道者] 正在分析中..."
- [x] **S6.3** 实现格式化摘要输出：每轮结束后展示 Talent 总结和 Planner 决策
  - 验证：每轮结束时 CLI 输出可读的摘要面板
- [x] **S6.4** 实现详细思考过程的按需读取：用户可输入命令查看任意专家的完整 think 内容
  - 验证：输入 `/think 专家2` 后显示该专家的完整思考过程
- [x] **S6.5** 实现人工打断：用户可在任意时刻通过 `Ctrl+C` 或 `/stop` 安全中断工作流
  - 验证：在专家分析过程中按 Ctrl+C，程序优雅退出并输出当前已有结果

**完成标志**：CLI 可用于完整的交互式分析流程，信息展示清晰、可控。

---

## S7 — 模式切换与配置

**目标**：让用户可自由选择运行哪些阶段。

- [ ] **S7.1** 实现模式参数解析：支持 `--mode discovery`, `--mode 1+2`, `--mode full` 等
  - 验证：`main.py --mode discovery` 只运行价值发现阶段
- [ ] **S7.2** 实现混合模式：`1+2` = 价值发现+标的锁定，`1+2+3` = 全流程
  - 验证：`--mode 1+2` 运行后 State 经历了 discovery 和 targeting，但没有 validation
- [ ] **S7.3** 实现配置文件覆盖：允许通过 YAML/TOML 文件自定义每阶段的 max_rounds、expert_count
  - 验证：修改配置文件中 discovery 的 max_rounds 为 2，运行时最多循环 2 次

**完成标志**：用户可灵活控制运行范围和参数。

---

## S8 — 端到端验收

**目标**：使用需求文档中的示例 Case 进行完整验收。

- [ ] **S8.1** 使用 req.md 中的 BCI 案例作为输入，完整运行 `--mode full`
  - 验证：系统完成三阶段分析，输出最终报告
- [ ] **S8.2** 验证报告内容质量：报告应包含多个专家的不同视角、矛盾点分析、具体标的建议
  - 验证：人工审阅报告，确认信息维度 ≥ 3，有明确的 "建议/否决" 结论
- [ ] **S8.3** 验证循环机制：至少出现一次 Vibe 变异（iterate），证明负反馈循环生效
  - 验证：运行日志中存在 `vibe_next` 生成记录
- [ ] **S8.4** 验证容错性：传入极度模糊的 Vibe（如 "赚钱"），系统应在 max_rounds 后 abort 并给出有用反馈
  - 验证：系统输出 abort 状态，包含 "信息不足" 提示和已有分析结论
- [ ] **S8.5** 前后端分离接口检查：核心逻辑不依赖 CLI，graph.invoke() 可独立调用
  - 验证：写一个不含 CLI 的脚本直接调用 graph，结果与 CLI 运行一致

**完成标志**：系统端到端可用，质量达到 Phase 1 交付标准。

---

## 架构约束备忘

以下约束贯穿所有迭代，在每个 Sprint 的代码审查中检查：

1. **前后端分离**：`graph.py` 和 `nodes/` 不得 import `cli.py` 中的任何内容
2. **可扩展性**：Expert 节点使用工厂模式创建，未来可将单个专家升级为子工作流
3. **模型分级**：Planner 使用 Chat 模型（快速），Expert/Talent 使用 Reasoner 模型（深思）
4. **无持久化**：Phase 1 不引入数据库，所有状态仅存在于内存
5. **单轮对话**：不考虑多轮历史，但 State 设计需预留 `session_id` 字段

---

*最后更新：2026-02-18*
