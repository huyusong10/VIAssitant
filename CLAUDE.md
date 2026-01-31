# Vibe Investment - AI 投资顾问专家系统

## 项目概述

Vibe Investment 是一个基于多智能体（Multi-Agent）的人机协同投资分析工具。借鉴 "Vibe Coding" 的理念，将用户的模糊直觉（Vibe）转化为经过严密数据验证、风险评估后的可执行投资策略。

### 核心理念
- **人类直觉 (Vibe) + AI 对抗性验证 (Verification) = 高胜率决策**
- 系统不寻求替代人类决策，而是作为认知增强工具
- 所有分析过程白盒化，用户可查看完整辩论过程

## 技术栈

- **编程语言**: Python 3.10+
- **Web 界面**: Chainlit (双栏布局 Chat UI)
- **Agent 编排**: LangGraph (状态机、循环辩论逻辑)
- **LLM 接口**: 支持多种 LLM 提供商
  - DeepSeek (默认，性价比高)
  - Claude (Anthropic)
  - GPT-4 (OpenAI)
- **数据存储**: Markdown + YAML Frontmatter (无 SQL)
- **网络搜索**: Tavily API
- **数据分析**: Pandas

## 目录结构

```
vibe-investment/
├── data/                       # [Markdown DB] 数据存储层
│   ├── profile.md              # 用户画像 (风险偏好、配置)
│   ├── portfolio/              # 持仓列表
│   │   └── {TICKER}.md         # 单个标的详细档案
│   ├── watchlist/              # 关注列表
│   │   └── {TICKER}.md
│   └── debates/                # 历史辩论归档
│       └── {DATE}_{TICKER}.md
├── src/
│   ├── agents/                 # [Agent Layer] 智能体定义
│   │   ├── __init__.py
│   │   ├── prompts.py          # 所有角色的 System Prompts
│   │   ├── graph.py            # LangGraph 状态图定义 (核心逻辑)
│   │   ├── nodes.py            # 各 Agent 节点实现
│   │   └── tools.py            # Tavily 搜索工具封装
│   ├── data_mgr/               # [Data Layer] 数据读写接口
│   │   ├── __init__.py
│   │   └── markdown_db.py      # 封装 frontmatter 的 CRUD 操作
│   ├── ui/                     # [Presentation Layer] 界面逻辑
│   │   ├── __init__.py
│   │   └── components.py       # Chainlit 界面元素渲染
│   └── utils/
│       ├── __init__.py
│       └── config.py           # 环境变量加载
├── app.py                      # [Entry Point] Chainlit 主程序
├── daily_cron.py               # [Automation] 每日后台监控脚本
├── requirements.txt
├── .env.example
└── CLAUDE.md
```

## 核心 Agent 系统

### 1. 想象专家 (Bull Agent / Alpha Hunter)
- **目标函数**: 寻找非共识的增长机会
- **职责**: 构建 "Bull Case"，寻找支持性证据
- **思维模型**: 索罗斯的反身性理论
- **输入**: 用户 Vibe、社交媒体热点、技术突破新闻
- **输出**: 潜在上涨逻辑、催化剂事件

### 2. 做空专家 (Bear Agent / Risk Auditor)
- **目标函数**: 寻找系统脆弱性
- **职责**: 压力测试，构建 "Bear Case"
- **思维模型**: 查理·芒格的"反过来想"、塔勒布的"反脆弱"
- **输入**: 财务报表、宏观流动性、历史泡沫案例
- **输出**: 下行风险评估、证伪条件、财务红旗

### 3. 统筹专家 (CIO Agent / Portfolio Manager)
- **目标函数**: 风险调整后的收益最大化
- **职责**: 主持辩论、裁决、生成最终建议
- **思维模型**: 凯利公式、概率思维
- **输入**: Bull/Bear 辩论、用户画像、当前持仓
- **输出**: 决策备忘录、量化操作建议

## 辩论协议 (Debate Protocol)

### 终止条件
1. **回合制限制**: 最大 3 轮辩论
2. **边际信息增量检测**: CIO 判断新一轮是否引入新数据/逻辑
3. **强制裁决**: 达到终止条件后 CIO 强制接管，生成概率加权的最终结论

### 辩论流程
```
User Vibe → Bull 初始观点 → Bear 反驳 → Bull 补充 → Bear 再攻击 → CIO 评估 →
(继续/停止) → Final Memo
```

## 数据格式规范

### 用户画像 (profile.md)
```yaml
---
risk_aversion: "medium"       # low, medium, high
investment_horizon: "long"    # short, medium, long
source_weights:
  financial_reports: 1.0
  news_mainstream: 0.8
  social_media: 0.4
decision_style: "show_debate" # show_debate, summary_only
last_updated: "2026-02-01"
---
# 投资理念
(用户自然语言描述)
```

### 标的档案 ({TICKER}.md)
```yaml
---
ticker: "TSLA"
status: "holding"             # holding, watchlist, sold
avg_cost: 210.0
position_size: 0.05
stop_loss: 180.0
target_price: 280.0
conviction: "high"            # low, medium, high
last_review: "2026-02-01"
---
# Investment Thesis

## Bull Case
...

## Bear Case
...

## CIO Conclusion
...

## User Notes
(用户手动添加的笔记)
```

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys

# 运行主程序
chainlit run app.py

# 运行每日监控 (手动测试)
python daily_cron.py

# 设置定时任务 (crontab)
# 0 8 * * * cd /path/to/project && python daily_cron.py
```

## 环境变量

```bash
# LLM API Keys (至少配置一个)
DEEPSEEK_API_KEY=your_deepseek_api_key    # 推荐，性价比高
ANTHROPIC_API_KEY=your_anthropic_api_key  # Claude
OPENAI_API_KEY=your_openai_api_key        # GPT-4

# Search API
TAVILY_API_KEY=your_tavily_api_key

# LLM 选择: deepseek, claude, openai
DEFAULT_LLM=deepseek

# 模型配置 (可选)
DEEPSEEK_MODEL=deepseek-chat              # 或 deepseek-reasoner
DEEPSEEK_BASE_URL=https://api.deepseek.com
CLAUDE_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o
```

## 关键设计决策

### 1. Markdown as Database
- 所有数据使用 Markdown + YAML Frontmatter 存储
- 便于人类阅读和版本控制
- LLM 训练数据包含大量 Markdown，理解能力强

### 2. 白盒化对抗
- 所有 Agent 辩论过程可展开查看
- 每个观点都附带数据来源链接
- 用户可随时介入修正

### 3. 用户画像驱动
- Profile 作为所有 Agent 的 System Prompt 基础
- 信息源权重由用户风险偏好决定
- 最终建议考虑用户投资周期

### 4. 信息边际效用递减
- 当新信息无法显著改变概率分布时停止搜索
- 避免无限迭代消耗资源

## UI 布局

### 左侧: 交互区 (Chat Interface)
- 多 Session 支持，不同话题分开
- 折叠/展开 Agent 思考过程
- 用户输入 Vibe 和确认操作

### 右侧: 仪表盘 (Dashboard)
- Tab 1: 持仓全景 (Portfolio View)
- Tab 2: 决策备忘录 (Memo)
- Tab 3: 实时数据 (Live Data)
- Tab 4: 用户画像 (Profile)

## 测试检查清单

- [ ] Profile 创建和读取
- [ ] 单个标的分析流程
- [ ] Bull/Bear 辩论至少 2 轮
- [ ] CIO 正确终止并生成 Memo
- [ ] Markdown 文件正确保存
- [ ] 每日监控脚本运行
- [ ] Chainlit UI 双栏显示

## 注意事项

1. **API 调用成本**: 每次完整分析约消耗 10-20K tokens
2. **Tavily 限制**: 免费层每月 1000 次搜索
3. **数据安全**: Profile 和持仓数据仅存本地
4. **LLM 幻觉**: CIO 会标注置信度，低置信度建议需人工核实

---

## 实现细节

### LangGraph 状态机

状态定义在 `src/agents/graph.py`:

```python
class AgentState(TypedDict):
    user_vibe: str          # 用户初始直觉
    ticker: str             # 股票代码
    round_count: int        # 当前辩论轮次
    bull_notes: str         # Bull Agent 累积观点
    bear_notes: str         # Bear Agent 累积观点
    decision_memo: str      # CIO 最终备忘录
    next_step: str          # 路由控制
    messages: list          # 消息历史
```

### 节点流转

```
init → bull → bear → cio → [bull|END]
                      ↑       ↓
                      └───────┘
```

- `init`: 初始化状态
- `bull`: Alpha Hunter 分析
- `bear`: Risk Auditor 反驳
- `cio`: 评估并决定是否继续

### 核心函数

#### run_investment_analysis()

```python
async def run_investment_analysis(
    ticker: str,
    user_vibe: str,
    callback=None,  # 可选回调用于流式更新UI
) -> dict:
    """执行完整投资分析流程"""
```

#### MarkdownDB

```python
class MarkdownDB:
    @staticmethod
    def read_file(path) -> tuple[dict, str]
    @staticmethod
    def write_file(path, metadata, content)
    @staticmethod
    def update_metadata(path, updates)
```

#### ProfileManager

```python
class ProfileManager:
    def exists() -> bool
    def get() -> tuple[ProfileData, str]
    def create(profile, philosophy)
    def update(updates)
```

#### PortfolioManager

```python
class PortfolioManager:
    def get_stock(ticker) -> tuple[StockData, str]
    def save_stock(stock, content)
    def list_holdings() -> list[StockData]
    def list_watchlist() -> list[StockData]
```

---

## Chainlit 命令

用户可在聊天界面使用以下命令：

| 命令 | 功能 |
|------|------|
| `/portfolio` | 查看当前持仓 |
| `/watchlist` | 查看关注列表 |
| `/profile` | 查看用户画像 |
| `/reset` | 重置用户画像 |
| `/help` | 显示帮助信息 |

---

## 扩展开发

### 添加新的数据源

1. 在 `src/agents/tools.py` 中创建新的 `@tool` 函数
2. 在 `get_tools_for_agent()` 中为相应 Agent 添加工具
3. 在 prompts 中说明何时使用新工具

### 修改辩论规则

1. 在 `src/utils/config.py` 修改 `max_debate_rounds`
2. 在 `src/agents/nodes.py` 的 `CIOAgent._should_continue()` 修改终止逻辑

### 添加新的通知渠道

在 `daily_cron.py` 的 `DailyMonitor.send_notifications()` 中实现：

```python
# 示例：添加邮件通知
import smtplib
# ...
```

---

## 常见问题

### Q: 如何切换 LLM 提供商？

修改 `.env` 中的 `DEFAULT_LLM`:
```bash
DEFAULT_LLM=deepseek  # 推荐，性价比高
DEFAULT_LLM=claude    # Claude Sonnet
DEFAULT_LLM=openai    # GPT-4o
```

DeepSeek 支持的模型:
- `deepseek-chat` - 通用对话模型 (默认)
- `deepseek-reasoner` - 推理增强模型

### Q: 如何调整社交媒体信息的权重？

1. 运行 `/reset` 命令重新设置画像
2. 或直接编辑 `data/profile.md` 中的 `source_weights.social_media`

### Q: 分析结果保存在哪里？

- 辩论记录: `data/debates/`
- 标的分析: `data/portfolio/` 或 `data/watchlist/`

---

## 许可证

MIT License
