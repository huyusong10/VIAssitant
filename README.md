# Vibe Investment — 多智能体投资分析引擎

> **Phase 1** · 基于 LangGraph 构建的多智能体发散-收敛投资直觉放大器

## 项目愿景

人类负责给出一个"直觉（Vibe）"，由 AI 多智能体集群进行**发散-收敛-迭代**，从多维正交视角放大并细化投资直觉，最终输出结构化投资建议。

## 核心特性

- **10 维专家集群**：宏观冲浪者、技术布道者、成长股狂热者、资金博弈操盘手、深度价值卫道士、黑天鹅预言家、合规审查官、商业模式解构师、行为金融学家、第二层思维者
- **并发扇出/扇入**：通过 LangGraph `Send()` 机制实现 N 个专家并发分析，结果自动汇聚
- **Talent 收敛**：专家意见交叉比对，涌现新假设，按阶段动态切换角色（战略家/选股手/量化审计）
- **Planner 控制阀**：信息充分度评估 + Vibe 变异循环 + 轮数限制 + 专家动态选取
- **三阶段工作流**：价值发现 → 标的锁定 → 逻辑验证，每阶段内部可迭代循环
- **最终报告生成**：三阶段分析完成后自动生成结构化投资建议报告
- **模式切换**：支持单阶段运行、组合模式（1+2、1+2+3）或完整流程
- **DeepSeek Reasoner 集成**：专家/Talent 使用深度推理模型，保留完整思考链
- **Rich CLI 交互**：美观的命令行界面，实时展示阶段/轮次/决策，按需查看推理过程

## 技术栈

| 组件 | 技术 |
|------|------|
| 编排框架 | [LangGraph](https://github.com/langchain-ai/langgraph) (FSM 有向图) |
| LLM 提供商 | [DeepSeek](https://deepseek.com) (Reasoner + Chat 双模型) |
| 包管理 | [uv](https://github.com/astral-sh/uv) |
| CLI 界面 | [Rich](https://github.com/Textualize/rich) |
| 语言 | Python 3.13+ |

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd VIAssitant

# 安装依赖（使用 uv）
uv sync
```

### 2. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. 运行

```bash
# 交互模式（会提示输入 Vibe）
uv run python main.py

# 直接传入 Vibe（完整流程）
uv run python main.py --vibe "看好脑机接口，Neural-Link 宣称突破双向读写"

# 指定初始专家数量
uv run python main.py --vibe "看好新能源汽车" --expert 4

# 仅运行价值发现阶段
uv run python main.py --vibe "看好固态电池" --mode discovery

# 运行价值发现 + 标的锁定
uv run python main.py --vibe "看好AI芯片" --mode 1+2

# 完整三阶段流程
uv run python main.py --vibe "看好脑机接口" --mode full

# 查看帮助
uv run python main.py --help
```

### 模式说明

| 模式 | 包含阶段 | 说明 |
|------|----------|------|
| `discovery` | 价值发现 | 宽口径扫描，提炼核心矛盾 |
| `targeting` | 标的锁定 | 将逻辑具象化为具体投资标的 |
| `validation` | 逻辑验证 | 对标的进行严谨数据推导 |
| `1+2` | 价值发现 + 标的锁定 | 从发现到锁定 |
| `1+2+3` / `full` | 全部三阶段 | 完整分析流程 |

### 专家维度一览

| ID | 名称 | 定位 |
|----|------|------|
| 1 | 宏观冲浪者 | 宏观经济周期、利率环境、地缘政治格局 |
| 2 | 技术布道者 | 技术奇点与颠覆式创新、技术可行性评估 |
| 3 | 成长股狂热者 | 高速成长赛道、收入增速、竞争壁垒 |
| 4 | 资金博弈操盘手 | 主力资金流向、筹码分布、市场情绪 |
| 5 | 深度价值卫道士 | 内在价值评估、安全边际、低估资产 |
| 6 | 黑天鹅预言家 | 尾部风险、系统性脆弱点、极端事件 |
| 7 | 合规审查官 | 监管合规、法律风险、政策敏感性 |
| 8 | 商业模式解构师 | 护城河、定价权、飞轮效应、可持续性 |
| 9 | 行为金融学家 | 认知偏差、情绪周期、非理性行为 |
| 10 | 第二层思维者 | 超越共识的反向逻辑、二阶思维 |

## 架构设计

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         │
                    ┌────┴─────┐
                    │ fan_out  │◄────────────────────┐
                    └────┬─────┘                     │
                         │                           │
                    route_to_experts()               │
                    (Send() fan-out)                  │
                         │                           │
              ┌──────────┼──────────┐                │
              ▼          ▼          ▼                │
        ┌──────────┐ ┌──────────┐ ┌──────────┐      │
        │ Expert 1 │ │ Expert N │ │ Expert M │      │  iterate
        └────┬─────┘ └────┬─────┘ └────┬─────┘      │  (Vibe 变异)
              │          │          │                │
              └──────────┼──────────┘                │
                    (fan-in reducer)                  │
                         │                           │
                    ┌────┴─────┐                     │
                    │  Talent  │  收敛 + 涌现          │
                    └────┬─────┘                     │
                         │                           │
                    ┌────┴─────┐                     │
                    │ Planner  │  充分度评估            │
                    └────┬─────┘                     │
                         │                           │
            ┌────────────┼────────────┐              │
            ▼            ▼            ▼              │
        [abort]      [proceed]    [iterate]──────────┘
            │            │
            ▼            ▼
           END     has next phase?
                     │         │
                     ▼         ▼
                  fan_out    reporter → END
                (next phase)  (最终报告)
```

### 数据流

```
User Vibe → Planner → fan-out Expert_Swarm (N 并发)
         → fan-in → Talent (收敛)
         → Planner (循环/推进/终止)
         → ... (阶段内迭代)
         → Reporter (最终报告) → END
```

### 项目结构

```
VIAssitant/
├── main.py                    # 程序入口
├── pyproject.toml             # 项目配置与依赖
├── .env.example               # 环境变量模板
├── src/
│   └── vibe_engine/
│       ├── __init__.py
│       ├── config.py          # 配置常量（专家维度、阶段参数、模型选择）
│       ├── state.py           # 全局状态定义（VibeState、ExpertInput 等）
│       ├── graph.py           # LangGraph FSM 构建（三阶段 + 循环）
│       ├── llm.py             # LLM 客户端工厂（Chat / Reasoner）
│       ├── cli.py             # CLI 交互入口
│       ├── nodes/
│       │   ├── expert.py      # 专家节点（工厂模式 + Send() 扇出）
│       │   ├── talent.py      # 天才收敛节点（阶段角色切换）
│       │   ├── planner.py     # 规划器控制阀（充分度评估 + Vibe 变异）
│       │   └── reporter.py    # 最终报告生成
│       └── prompts/
│           ├── __init__.py    # Prompt 模板管理（含 Talent/Planner/Report 模板）
│           ├── expert_system.md
│           ├── expert_user.md
│           └── experts/       # 10 位专家独立深度角色 Prompt
│               ├── expert_1.md ~ expert_10.md
├── plan/                      # 开发计划
└── requirement/               # 需求文档
```

## 开发路线图

| 迭代 | 状态 | 名称 | 核心交付 |
|------|------|------|----------|
| S0 | Done | 项目脚手架 | 可运行的空壳项目 |
| S1 | Done | 单专家直通车 | 1个专家节点 → 直接输出 |
| S2 | Done | 专家集群扇出/扇入 | N个专家并发 + 结果汇聚 |
| S3 | Done | Talent 收敛节点 | 专家意见交叉比对 + 涌现 |
| S4 | Done | Planner 控制阀 | 充分度评估 + Vibe 变异循环 |
| S5 | Done | 三阶段工作流串联 | 价值发现→标的锁定→逻辑验证 + 最终报告 |
| S6 | Planned | CLI 交互体验 | 实时状态展示 + 人工打断 |
| S7 | Planned | 模式切换与配置 | 配置文件覆盖 |
| S8 | Planned | 端到端验收 | 完整流程跑通 + 输出报告 |

## 架构约束

1. **前后端分离**：`graph.py` 和 `nodes/` 不 import `cli.py`
2. **可扩展性**：Expert 节点使用工厂模式，未来可升级为子工作流
3. **模型分级**：Planner 使用 Chat 模型（快速），Expert/Talent 使用 Reasoner 模型（深思）
4. **无持久化**：Phase 1 不引入数据库，所有状态仅存在于内存
5. **单轮对话**：不考虑多轮历史，但 State 设计预留 `session_id` 字段

## 许可

Private — 仅供内部使用
