# 🚀 Vibe Investment

AI驱动的投资决策系统，采用多专家辩论模式，将人类直觉转化为数据验证的投资建议。

## ✨ 核心特性

- **🐂 想象专家 (Alpha Hunter)**: 寻找非共识的增长机会
- **🐻 做空专家 (Risk Auditor)**: 识别风险和逻辑漏洞  
- **⚖️ 统筹专家 (CIO)**: 基于概率做出客观决策
- **🔍 实时搜索**: Tavily-powered 互联网数据获取
- **📊 白盒化**: 透明展示Agent辩论全过程
- **📝 Markdown数据库**: 人类可读的数据持久化
- **⏰ 每日监控**: 自动扫描持仓，生成简报

## 🏗️ 架构

```
vibe-investment/
├── app.py                    # Chainlit主应用
├── daily_cron.py             # 每日监控脚本
├── data/                     # Markdown数据库
│   ├── profile.md            # 用户画像
│   ├── portfolio/            # 持仓记录
│   └── debates/              # 辩论历史
└── src/
    ├── agents/               # Agent编排
    │   ├── graph.py          # LangGraph状态机
│   ├── data_mgr/           # 数据层
│   └── ui/                 # 界面辅助
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd vibe-investment
pip install -r requirements.txt
```

### 2. 配置API密钥

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥
```

需要的API密钥（**三选一即可**，推荐DeepSeek性价比最高）：
- `DEEPSEEK_API_KEY`: DeepSeek API (⭐ **推荐**，性价比高，国内可用)
- `ANTHROPIC_API_KEY`: Claude API (能力强，较贵)
- `OPENAI_API_KEY`: OpenAI API (备选)
- `TAVILY_API_KEY`: Tavily搜索API (⭐ **必需**，用于实时搜索)

### 3. 启动应用

```bash
chainlit run app.py -w
```

访问 http://localhost:8000

### 4. 每日监控 (可选)

```bash
# 手动运行
python daily_cron.py

# 或添加到crontab (每天早晨8点)
0 8 * * * cd /path/to/vibe-investment && python daily_cron.py
```

## 🔑 DeepSeek 配置（推荐）

DeepSeek API 是**性价比最高**的选择，推理能力强且价格便宜：

### 获取 DeepSeek API Key

1. 访问：https://platform.deepseek.com
2. 注册账号（支持国内手机号）
3. 充值（新用户有5000万tokens免费额度）
4. 创建 API Key

### 配置 .env

```bash
# 使用 DeepSeek
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
DEFAULT_MODEL_PROVIDER=deepseek
DEFAULT_MODEL=deepseek-chat

# Tavily 仍然需要
TAVILY_API_KEY=tvly-xxxxxxxxxxxx
```

### DeepSeek 模型选择

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| `deepseek-chat` | DeepSeek-V3，通用对话 | 投资分析（推荐） |
| `deepseek-reasoner` | DeepSeek-R1，推理模型 | 复杂逻辑分析 |

---

## 💡 使用指南

### 首次使用

系统会引导你完成用户画像设置：
- 风险偏好 (低/中/高)
- 投资周期 (短期/长期)
- 信息源权重设置

### 投资分析

直接输入你的投资直觉或"Vibe"：

```
我觉得Tesla的机器人业务被低估了
NVDA可能快要回调了，想减仓
苹果的新AI功能会不会带动股价？
```

系统会自动：
1. 提取股票代码
2. 启动Agent辩论
3. 生成投资决策备忘录
4. 提供操作建议

### 快捷命令

- `/portfolio` - 查看持仓
- `/profile` - 查看用户画像
- `/add TICKER` - 快速加入关注
- `/remove TICKER` - 移除股票
- `/help` - 显示帮助

### 数据存储

所有数据以Markdown格式存储在 `data/` 目录：

```yaml
---
ticker: TSLA
status: watchlist
conviction: high
---
# Tesla Investment Thesis

## Bull Case
...

## Bear Case
...
```

## ⚙️ 配置说明

### 用户画像 (profile.md)

```yaml
risk_aversion: medium      # low | medium | high
investment_horizon: long   # short | long
source_weights:            # 信息源权重
  financial_reports: 1.0
  news_mainstream: 0.8
  social_media: 0.4
max_debate_rounds: 3       # 最大辩论轮次
```

### 环境变量 (.env)

```bash
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
TAVILY_API_KEY=your_key
DEFAULT_MODEL_PROVIDER=anthropic
DEFAULT_MODEL=claude-3-5-sonnet-20241022
```

## 🎯 决策流程

```
用户输入Vibe
    ↓
提取股票代码
    ↓
🐂 Alpha Hunter 搜索数据，构建多头案例
    ↓
🐻 Risk Auditor 搜索风险，构建空头案例
    ↓
⚖️ CIO 评估双方论点
    ↓
是否继续辩论？
    ↓ 是 → 继续下一轮 (最多3轮)
    ↓ 否 → 生成最终备忘录
    ↓
输出投资建议
保存到 Markdown
```

## 📁 项目结构

```
vibe-investment/
├── app.py                    # 主应用入口
├── daily_cron.py             # 每日监控
├── requirements.txt          # 依赖
├── .env.example             # 环境变量模板
├── .chainlit/               # Chainlit配置
│   ├── config.toml
│   └── translations/
├── data/                    # 数据存储 (Markdown)
│   ├── profile.md
│   ├── portfolio/
│   └── debates/
└── src/
    ├── agents/
    │   ├── __init__.py
    │   ├── graph.py         # LangGraph编排
    │   ├── prompts.py       # Agent提示词
    │   └── tools.py         # 搜索工具
    ├── data_mgr/
    │   ├── __init__.py
    │   └── markdown_db.py   # Markdown数据库
    ├── ui/
    │   ├── __init__.py
    │   └── layout.py        # 界面渲染
    └── utils/
        ├── __init__.py
        └── config.py        # 配置管理
```

## ⚠️ 免责声明

本系统提供的所有建议仅供参考，不构成投资建议。投资有风险，决策需谨慎。请根据自己的风险承受能力做出独立判断。

## 📄 许可证

MIT License
