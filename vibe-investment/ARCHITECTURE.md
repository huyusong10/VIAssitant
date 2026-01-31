# Vibe Investment - 架构设计文档

## 系统架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面层 (UI)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Chat对话   │  │  侧边仪表盘   │  │  交互按钮    │          │
│  │  (Chainlit)  │  │  (Markdown)  │  │  (Actions)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Agent 编排层 (LangGraph)                    │
│                                                                 │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐    │
│   │ 🐂 Alpha    │ ───▶ │ 🐻 Risk     │ ───▶ │ ⚖️ CIO      │    │
│   │   Hunter    │      │   Auditor   │      │  (Judge)    │    │
│   │  (Bull)     │      │   (Bear)    │      │             │    │
│   └─────────────┘      └─────────────┘      └─────────────┘    │
│          │                    │                    │            │
│          └────────────────────┴────────────────────┘            │
│                         Loop (Max 3)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      工具层 (Tools)                             │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │  Tavily Search  │  │   Stock Info    │                      │
│  │  (实时互联网)    │  │   (财务数据)     │                      │
│  └─────────────────┘  └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      数据层 (Markdown DB)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ profile.md  │  │  TSLA.md    │  │ debates/    │             │
│  │  用户画像   │  │  持仓档案   │  │  历史记录   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## 核心模块说明

### 1. 数据层 (`src/data_mgr/`)

#### `markdown_db.py`
- **ProfileManager**: 管理 `profile.md`，存储用户风险偏好、信息源权重
- **PortfolioManager**: 管理 `data/portfolio/*.md`，持仓和关注列表
- **DebateManager**: 管理 `data/debates/*.md`，保存历史辩论记录

所有数据使用 **YAML Frontmatter + Markdown Body** 格式，人类可读且LLM友好。

### 2. Agent编排层 (`src/agents/`)

#### `graph.py`
- 定义 `DebateState` TypedDict 状态机
- 使用 LangGraph 构建循环辩论流程
- 三个核心节点：
  - `node_alpha_hunter`: 构建多头案例
  - `node_risk_auditor`: 构建空头案例
  - `node_cio`: 判断并决策

#### `prompts.py`
- 定义三个专家的角色提示词
- Onboarding对话流程
- 各种辅助提示词

#### `tools.py`
- Tavily搜索工具封装
- `web_search`: 通用搜索
- `search_stock_info`: 股票专用搜索

### 3. 界面层 (`src/ui/`)

#### `layout.py`
- `render_memo_sideview()`: 右侧渲染投资备忘录
- `render_portfolio_dashboard()`: 持仓仪表板
- `render_debate_log()`: 辩论过程白盒展示

### 4. 主应用 (`app.py`)

Chainlit主应用，处理：
- 用户会话管理
- Onboarding流程
- 消息处理（投资Vibe）
- 调用Agent编排
- 显示结果

### 5. 每日监控 (`daily_cron.py`)

独立脚本，用于：
- 扫描所有持仓
- 检查新闻和事件
- 生成每日简报
- 触发重要警报

## 数据流

```
用户输入: "我觉得Tesla的机器人业务被低估了"
    │
    ▼
提取股票代码: TSLA
    │
    ▼
初始化辩论状态
    │
    ▼
┌────────────────────────────────────────┐
│ Round 0                                │
│ 🐂 Alpha Hunter 搜索数据 → 构建多头案例 │
│    └─ 使用Tavily搜索TSLA相关新闻       │
│    └─ 生成看涨分析和价格目标           │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│ 🐻 Risk Auditor 搜索数据 → 构建空头案例 │
│    └─ 使用Tavily搜索TSLA风险因素       │
│    └─ 识别估值过高、竞争等风险         │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│ ⚖️ CIO 评估双方论点                    │
│    └─ 计算概率和预期收益               │
│    └─ 判断是否继续辩论                 │
└────────────────────────────────────────┘
    │
    ├── 继续? ──▶ Round 1, 2, 3...
    │
    └── 结束 ──▶ 生成投资决策备忘录
                      │
                      ▼
              保存到 data/portfolio/TSLA.md
              保存辩论记录到 data/debates/
              显示在右侧边栏
```

## 关键设计决策

### 1. 为什么选择 Python + Chainlit？
- **Python**: 投资分析生态（Pandas, LangChain）统治级
- **Chainlit**: 专为AI Chat应用设计，支持：
  - 双栏布局（Chat + Side View）
  - 流式显示Agent思考过程
  - 无需写前端代码

### 2. 为什么选择 Markdown 作为数据库？
- 人类可读，方便手动检查和编辑
- LLM原生理解，便于生成和解析
- 无需安装数据库，零配置
- 天然支持版本控制（Git）

### 3. 辩论终止机制
- **硬性限制**: 最多3轮
- **信息增量**: CIO判断新信息是否重复
- **置信度阈值**: >80%置信度时提前结束

### 4. 信息源权重
用户可以在profile中设置：
- 财报数据: 权重1.0 (最高信任)
- 主流新闻: 权重0.8
- 社交媒体: 权重0.4 (仅作参考)

## 文件结构

```
vibe-investment/
├── app.py                      # Chainlit主入口
├── daily_cron.py              # 每日监控脚本
├── requirements.txt           # Python依赖
├── .env.example              # 环境变量模板
├── .chainlit/                # Chainlit配置
│   ├── config.toml
│   └── translations/
├── data/                     # Markdown数据库
│   ├── profile.md            # 用户画像
│   ├── portfolio/            # 持仓目录
│   │   ├── TSLA.md
│   │   └── .gitkeep
│   └── debates/              # 辩论历史
│       ├── 20260201_TSLA.md
│       └── .gitkeep
└── src/
    ├── agents/               # Agent编排
    │   ├── __init__.py
    │   ├── graph.py          # LangGraph状态机
    │   ├── prompts.py        # 提示词定义
    │   └── tools.py          # 搜索工具
    ├── data_mgr/             # 数据层
    │   ├── __init__.py
    │   └── markdown_db.py    # Markdown数据库
    ├── ui/                   # 界面层
    │   ├── __init__.py
    │   └── layout.py         # 渲染辅助
    └── utils/                # 工具
        ├── __init__.py
        └── config.py         # 配置管理
```

## 扩展建议

### 1. 添加更多数据源
- 在 `tools.py` 中添加新的工具：
  - Yahoo Finance API (股价数据)
  - SEC EDGAR API (财报数据)
  - Reddit API (社交媒体情绪)

### 2. 自定义Agent角色
- 在 `prompts.py` 中修改System Prompt
- 可以添加第四方专家 (例如: "技术面分析师")

### 3. 更多可视化
- 在 `layout.py` 中添加：
  - 股价K线图 (使用Plotly)
  - 持仓饼图
  - 风险热力图

### 4. 通知集成
- 在 `daily_cron.py` 中添加：
  - Pushover推送
  - Slack/Discord Webhook
  - Email通知

## 启动流程

```bash
# 1. 进入项目目录
cd vibe-investment

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置API密钥
cp .env.example .env
# 编辑 .env 填入你的API密钥

# 4. 启动应用
chainlit run app.py -w

# 5. 浏览器访问
open http://localhost:8000
```

## 注意事项

1. **API成本**: Tavily和LLM API都有成本，注意使用量
2. **数据延迟**: 搜索结果是准实时的，不是Level 2行情
3. **免责声明**: 系统建议仅供参考，不构成投资建议
4. **隐私**: 所有数据存储在本地，API密钥不要提交到Git
