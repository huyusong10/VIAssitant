# Vibe Investment 多智能体分析引擎（Phase 1）— 特性开发手册（gpt_plan）

> 需求来源：`requirement/req.md`（Phase 1）  
> 方法论：敏捷迭代（Agile）· 最小可行（MVP）· **每一步可验证**  
> 说明：本手册只定义「要做什么 + 如何验证」，不包含实现代码。

---

## 0. 使用方式（建议）

- 勾选规则：完成后将 `[ ]` 改为 `[x]`；未完成保持 `[ ]`。
- 迭代节奏：每次只推进到“能跑通/能演示”的最小闭环，再进入下一迭代。
- 每个任务都带「验证」：优先用命令/测试验证；无法自动化的用明确的人工验收点。
- 变更管理：需求新增/拆分/调整，追加到文末 **Backlog**，并记录日期与原因。

---

## 1. Phase 1 范围与非目标（边界）

### 1.1 In Scope（本期必须交付）

- 基于 `langgraph` 的 FSM（**有向循环图**）：支持发散（Divergence）与收敛（Convergence）与负反馈自循环（Vibe Mutation）。
- 三类核心节点与路由：
  - `Planner`：充分度评估/打分，决策 `proceed / iterate / abort`，控制轮数上限与阶段升降级。
  - `Expert_Swarm`：多专家并发（扇出/扇入），固定结构输出（逻辑链条/精简结论/核心风险点），保留可溯源信息。
  - `Talent`：交叉比对专家意见，输出核心矛盾与新假设，并随阶段切换侧重点。
- 三阶段工作流：价值发现（最多 5 轮）、标的锁定（最多 2 轮）、逻辑验证（最多 1 轮）；均需可配置。
- CLI 交互：可输入 Vibe；可中断；可展示当前阶段/轮数/专家进度；可按需查看详细思考内容；可输出最终报告摘要。
- LLM 供应商与分层（DeepSeek 优先）：Expert/Talent 使用 Reasoner；Planner 路由与抽取使用 Chat（同时提供 Mock LLM 以保证离线可测）。
- 预留“前后端分离”接口：CLI 只是调用 Engine，不把核心逻辑绑定在 UI 层。

### 1.2 Out of Scope（本期不做，但要可扩展）

- 互联网搜索/实时数据抓取（req 明确不考虑）。
- 数据库持久化（req 明确不做；但状态结构要可序列化/可扩展）。
- 多轮对话（本期单轮：一次 Vibe 输入 → 完整工作流 → 输出）。
- Web/TS 前端（只保留接口，不实现 UI）。

---

## 2. 全局验收标准（Definition of Done）

- 工程可安装与可运行：`uv sync` 成功；CLI `--help` 能输出；`--mock` 模式离线可跑通。
- 关键能力可演示：
  - 专家并发能产出多视角且固定结构输出，并汇聚到全局状态。
  - Talent 能做交叉比对，给出核心矛盾/新假设。
  - Planner 能打分并做 `proceed/iterate/abort`，支持最大轮数与 Vibe Mutation。
  - 三阶段（1/2/3）可单独或组合运行。
- 可验证性：核心路径有最小数量的自动化测试（建议 `pytest`），其余用明确人工验收点补齐。

---

## 3. 里程碑总览（MVP → 可用）

| 迭代 | 名称 | 最小交付物（MVP） | 主要验证方式 |
|---|---|---|---|
| I0 | 工程脚手架 | `uv` 项目 + 最小 CLI 入口 | 命令行运行/文件存在 |
| I1 | 图最小闭环 | `START → node → END` 可跑通（Mock） | 运行结果可预测 |
| I2 | 单专家节点 | 1 个 Expert 固定结构输出 + 可溯源字段 | 单元测试/Mock |
| I3 | 专家集群 | N 专家扇出/扇入 + 独立上下文 | 集成测试/断言长度 |
| I4 | Talent 收敛 | Talent 汇总：矛盾/假设/评分（随阶段切换角色） | 单元测试/Mock |
| I5 | Planner 循环 | 充分度评估 + Vibe Mutation + 轮数上限 + 条件路由 | 路径测试（3 决策分支） |
| I6 | 三阶段串联 | discovery→targeting→validation + 模式组合运行 | 端到端（mock） |
| I7 | DeepSeek 接入 | Chat/Reasoner 分层 + Key 缺失自动回退 mock | 手工验证 + 保护性测试 |
| I8 | CLI 可用性 | 进度展示/中断/摘要/按需查看 think | 手工验收清单 |
| I9 | 需求案例验收 | 用 req 示例跑通并输出最终报告 | E2E 验收脚本/手工对照 |

---

## 4. 迭代明细（每步可验证）

> 约定：除特别说明外，每个迭代都要求“可演示”。  
> 建议：每次只做 1 个迭代；迭代结束时补齐最小测试与文档记录。

### I0 — 工程脚手架（可运行空壳）

- [ ] **I0 状态**：TODO / DOING / DONE（手动标记）
- [ ] **I0.1** 初始化 `uv` 工程与最小包结构（先能 import）
  - 验证：`test -f pyproject.toml` 且 `uv sync` 成功（无依赖也可）
- [ ] **I0.2** 约定入口命令与目录结构（建议包名 `vibe_engine`；Engine 与 CLI 分离）
  - 验证：`uv run python -m vibe_engine.cli --help` 能输出帮助（placeholder 也可）
- [ ] **I0.3** 引入最小测试框架（建议 `pytest`）与基础任务脚本（可选）
  - 验证：`uv run pytest -q` 能运行并返回（允许 0 tests，但建议至少 1 个 smoke test）
- [ ] **I0.4** 环境变量约定：`DEEPSEEK_API_KEY`、Reasoner/Chat 模型名、`--mock` 开关
  - 验证：`uv run python -c "import os; print('DEEPSEEK_API_KEY' in os.environ)"`（人工确认文档写明）

**I0 验收记录**
- 完成日期：
- 备注：

---

### I1 — LangGraph 最小闭环（Mock 先行）

- [ ] **I1 状态**：TODO / DOING / DONE
- [ ] **I1.1** 定义全局 State（最小字段：`vibe`, `phase`, `round`, `expert_results`, `talent_summary`, `planner_decision`）
  - 验证：最小单元测试断言字段存在；或运行后输出可见字段
- [ ] **I1.2** 构建最小 LangGraph：`START → passthrough_node → END`
  - 验证：`graph.invoke()` 返回的 State 中 `vibe` 未丢失，且 `passthrough_node` 追加了可识别标记
- [ ] **I1.3** 引入 `--mock` 模式（不依赖外部 API），输出确定性结果（便于测试）
  - 验证：同一输入 Vibe，多次运行输出一致（至少关键字段一致）

**I1 验收记录**
- 完成日期：
- 备注：

---

### I2 — 单专家节点（固定结构输出 + 可溯源）

- [ ] **I2 状态**：TODO / DOING / DONE
- [ ] **I2.1** 设计 Expert 输出结构（建议统一为 dict/模型）：
  - 必含：`expert_id`, `expert_name`, `logic_chain`, `conclusion`, `core_risks`
  - 可选溯源：`raw_output`, `think`（若模型/供应商支持）
  - 验证：单元测试断言“必含字段非空”
- [ ] **I2.2** 实现 1 个 Expert（Mock LLM 先行），输入为 `vibe + phase`
  - 验证：运行一次后 `expert_results` 长度为 1，且字段满足 I2.1
- [ ] **I2.3** 固定输出格式约束（不满足则重试/降级/标记错误）
  - 验证：构造一个“坏输出”的 mock，确保系统能识别并给出可读错误（不中断整个程序更佳）

**I2 验收记录**
- 完成日期：
- 备注：

---

### I3 — Expert_Swarm 扇出/扇入（并发与隔离）

- [ ] **I3 状态**：TODO / DOING / DONE
- [ ] **I3.1** 定义 10 个专家维度的配置（name/role_prompt/适用阶段等）
  - 验证：配置项数量为 10；每项包含必要字段（最小：`id`,`name`,`prompt`）
- [ ] **I3.2** 实现扇出：Planner（先用固定选择器替代）选择 N 个专家执行
  - 验证：当选择 N=3 时，`expert_results` 恰好产生 3 条记录
- [ ] **I3.3** 实现扇入：汇聚所有专家输出到 State（保持可追溯到 expert_id）
  - 验证：`set(expert_id)` 数量与 N 一致；无重复覆盖
- [ ] **I3.4** 上下文隔离：专家之间不共享 message history（只共享输入 vibe/phase/约束）
  - 验证：对比任意两个专家的输入上下文（日志/结构）不包含对方输出

**I3 验收记录**
- 完成日期：
- 备注：

---

### I4 — Talent 收敛节点（交叉比对 + 阶段化角色）

- [ ] **I4 状态**：TODO / DOING / DONE
- [ ] **I4.1** 定义 Talent 输出结构（建议）：
  - discovery：`core_conflicts`, `new_hypotheses`, `info_gaps`
  - targeting：`candidate_targets`, `fit_assessment`, `anomalies`
  - validation：`data_logic_audit`, `fatal_flaws`, `risk_summary`
  - 验证：不同 phase 下输出字段满足约定（单元测试/断言）
- [ ] **I4.2** Talent 汇总逻辑（Mock 先行）：输入 `expert_results`，输出 `talent_summary`
  - 验证：`talent_summary` 必须引用 ≥2 个专家观点（可通过 expert_id 出现次数/引用结构断言）
- [ ] **I4.3** 将图拓展为：`START → Expert_Swarm → Talent → END`
  - 验证：一次 invoke 后同时存在 `expert_results` 与 `talent_summary`

**I4 验收记录**
- 完成日期：
- 备注：

---

### I5 — Planner 控制阀（打分/决策/循环/Vibe Mutation）

- [ ] **I5 状态**：TODO / DOING / DONE
- [ ] **I5.1** Planner 输出结构：
  - `sufficiency_score`（0-10）
  - `decision`：`proceed | iterate | abort`
  - `selected_experts`（下一轮选择列表）
  - `reason`（人类可读）
  - 验证：三种 decision 都能被构造并触发不同路径（路径测试）
- [ ] **I5.2** Vibe Mutation：当 `iterate` 时，生成 `vibe_next`（融合 talent 的假设/缺口）
  - 验证：`vibe_next != vibe_0` 且包含 talent_summary 的关键信息（关键字/字段断言）
- [ ] **I5.3** 最大轮数控制（按阶段不同上限）：超过上限强制 `abort`
  - 验证：将某阶段上限设为 1，第二轮必 abort，并输出矛盾点/缺口
- [ ] **I5.4** LangGraph 条件边与有向循环：
  - `iterate` → 回到 Expert_Swarm
  - `proceed` → 进入下一阶段或结束
  - `abort` → END（失败但可读输出）
  - 验证：对三种 decision 做集成测试，断言执行路径与最终 state

**I5 验收记录**
- 完成日期：
- 备注：

---

### I6 — 三阶段工作流与模式组合（核心能力闭环）

- [ ] **I6 状态**：TODO / DOING / DONE
- [ ] **I6.1** 阶段配置表（最小可配项）：max_rounds、专家数量范围、Talent 角色、专家选择偏好
  - 验证：修改配置后运行行为发生可观察变化（轮数/专家数量）
- [ ] **I6.2** 阶段递进：discovery → targeting → validation（或按 mode 子集）
  - 验证：`--mode discovery` 只跑 discovery；`--mode 1+2` 不进入 validation；`--mode full` 跑完三阶段
- [ ] **I6.3** 阶段特化输出：
  - targeting 的专家输出必须包含“具体标的”（ticker/token/产业链节点）
  - validation 的专家输出必须包含“数据推导/审计链条”
  - 验证：对不同阶段断言对应字段存在
- [ ] **I6.4** 最终报告生成（结构化）：结论/候选标的/风险提示/关键矛盾/流程摘要
  - 验证：E2E（mock）运行后 `final_report` 字段存在且包含上述章节标题（字符串断言）

**I6 验收记录**
- 完成日期：
- 备注：

---

### I7 — DeepSeek 接入与模型分级（真实 LLM 可跑）

- [ ] **I7 状态**：TODO / DOING / DONE
- [ ] **I7.1** 封装 LLM Provider（DeepSeek / Mock）统一接口（便于测试与未来替换）
  - 验证：同一套节点逻辑可在 `--mock` 与 `--provider deepseek` 下运行（至少启动不报错）
- [ ] **I7.2** 模型分级策略落地：
  - Expert/Talent：Reasoner
  - Planner：Chat
  - 验证：日志/调试输出可明确显示每次调用使用的模型类型
- [ ] **I7.3** 可溯源信息抓取（若供应商支持）：保存原始输出与 think/reasoning（或明确标记不可用）
  - 验证：真实模式下 state 中包含 `raw_output`；若有 think 则可在 CLI 查看
- [ ] **I7.4** Key 缺失/调用失败的降级策略：自动回退到 mock（或以可读错误退出）
  - 验证：不设置 `DEEPSEEK_API_KEY` 运行时行为符合预期（不出现难懂堆栈）

**I7 验收记录**
- 完成日期：
- 备注：

---

### I8 — CLI 交互体验（可用性达标）

- [ ] **I8 状态**：TODO / DOING / DONE
- [ ] **I8.1** 基础交互：输入 Vibe、选择 mode、退出/帮助
  - 验证：`--help` 清晰；手工跑一轮可得到报告
- [ ] **I8.2** 运行中可视化：显示当前阶段/轮数/正在执行的专家列表（progress/spinner）
  - 验证：运行时能看到“哪些专家在思考”的动态提示
- [ ] **I8.3** 可中断：`Ctrl+C` 或 `/stop` 能安全停止并输出当前已获得的内容
  - 验证：中断后程序不崩溃，并给出“已完成/未完成”的摘要
- [ ] **I8.4** 按需查看详细过程：支持查看某专家的 raw/think（若存在）
  - 验证：输入命令（如 `/think expert_2`）能打印对应内容
- [ ] **I8.5** 输出格式化：摘要面板 + 最终报告（可复制的 Markdown/纯文本）
  - 验证：人工阅读 2 分钟内能定位“结论/风险/矛盾点/标的”

**I8 验收记录**
- 完成日期：
- 备注：

---

### I9 — 需求案例验收（BCI 示例端到端）

- [ ] **I9 状态**：TODO / DOING / DONE
- [ ] **I9.1** 使用 req.md 的 BCI 示例作为输入（full mode）跑通一次
  - 验证：完整经历三阶段；最终输出包含“结论 + 否决/通过 + 原因 + 风险点 + 标的（若有）”
- [ ] **I9.2** 对照需求中的动态流转要点做检查（不要求逐字一致，但结构一致）
  - 验证：至少出现 1 次“发散→收敛→Planner 决策→（可能）迭代→推进下一阶段”的链条
- [ ] **I9.3** 文档补齐：运行方式、环境变量、mock/real 模式、常见问题
  - 验证：新手按文档从零到跑通 ≤15 分钟（人工走读）

**I9 验收记录**
- 完成日期：
- 备注：

---

## 5. Backlog（后续迭代候选）

> 规则：新增条目请写明日期与动机；优先写“用户价值 + 验证方式”。

- [ ]（YYYY-MM-DD）将 Expert 升级为“子工作流”示例（验证：某专家内部包含二级图）
- [ ]（YYYY-MM-DD）状态序列化与回放（验证：保存/加载后输出一致）
- [ ]（YYYY-MM-DD）Prompt/模板版本化与 A/B（验证：同输入对比质量指标）
- [ ]（YYYY-MM-DD）更强的错误恢复与重试策略（验证：注入故障仍能产出部分结果）
- [ ]（YYYY-MM-DD）Web/TS 前端对接（验证：通过 HTTP/SDK 调用 Engine 返回 JSON）
