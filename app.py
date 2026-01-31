"""Vibe Investment - Main Chainlit Application.

This is the entry point for the Chainlit web interface.
Run with: chainlit run app.py
"""

import re
from datetime import datetime

import chainlit as cl

from src.agents.graph import run_investment_analysis
from src.data_mgr.markdown_db import (
    DebateManager,
    PortfolioManager,
    ProfileData,
    ProfileManager,
    StockData,
)
from src.ui.components import (
    confirm_action,
    render_memo,
    render_portfolio,
    render_profile,
    render_watchlist,
    send_agent_message,
    show_debate_round,
    show_loading,
    update_loading,
)
from src.utils.config import get_settings


# Onboarding state machine
ONBOARDING_QUESTIONS = [
    {
        "key": "risk_aversion",
        "question": "首先，请告诉我你的**风险偏好**：\n\n"
        "1. **保守 (low)** - 稳健为主，不喜欢大波动\n"
        "2. **中等 (medium)** - 可以接受一定波动换取更高收益\n"
        "3. **激进 (high)** - 愿意承担高风险追求高回报\n\n"
        "请输入 1、2 或 3：",
        "options": {"1": "low", "2": "medium", "3": "high"},
    },
    {
        "key": "investment_horizon",
        "question": "你的主要**投资周期**是多长？\n\n"
        "1. **短期** - 3个月以内\n"
        "2. **中期** - 3-12个月\n"
        "3. **长期** - 1年以上\n\n"
        "请输入 1、2 或 3：",
        "options": {"1": "short", "2": "medium", "3": "long"},
    },
    {
        "key": "social_weight",
        "question": "你对**社交媒体上的投资信息**持什么态度？\n\n"
        "1. **完全不信任** - 只看权威来源\n"
        "2. **参考但需验证** - 可以作为情绪指标\n"
        "3. **积极采信** - 相信市场情绪的力量\n\n"
        "请输入 1、2 或 3：",
        "options": {"1": 0.1, "2": 0.4, "3": 0.7},
    },
    {
        "key": "decision_style",
        "question": "你希望看到**详细的分析辩论过程**，还是只想看**最终结论**？\n\n"
        "1. **展示辩论** - 我想看到专家们如何思考\n"
        "2. **只要结论** - 直接告诉我该怎么做\n\n"
        "请输入 1 或 2：",
        "options": {"1": "show_debate", "2": "summary_only"},
    },
    {
        "key": "philosophy",
        "question": "最后，请用几句话描述你的**投资理念或原则**（可选，直接回车跳过）：",
        "options": None,
    },
]


def extract_ticker(text: str) -> str | None:
    """Extract stock ticker from user input."""
    # Common patterns: $TSLA, TSLA, 特斯拉(TSLA)
    patterns = [
        r"\$([A-Z]{1,5})",  # $TSLA
        r"\b([A-Z]{2,5})\b",  # TSLA (2-5 uppercase letters)
        r"\(([A-Z]{1,5})\)",  # (TSLA)
    ]

    for pattern in patterns:
        match = re.search(pattern, text.upper())
        if match:
            return match.group(1)

    return None


@cl.on_chat_start
async def on_chat_start():
    """Handle new chat session start."""
    settings = get_settings()
    profile_mgr = ProfileManager()

    # Check if profile exists
    if not profile_mgr.exists():
        # Start onboarding
        cl.user_session.set("onboarding", True)
        cl.user_session.set("onboarding_step", 0)
        cl.user_session.set("onboarding_data", {})

        await cl.Message(
            content="👋 欢迎使用 **Vibe Investment**！\n\n"
            "在开始之前，让我了解一下你的投资风格。这将帮助我的分析更符合你的需求。\n\n"
            "---\n\n"
            f"{ONBOARDING_QUESTIONS[0]['question']}"
        ).send()
    else:
        # Existing user
        profile, _ = profile_mgr.get()
        await cl.Message(
            content=f"👋 欢迎回来！\n\n"
            f"当前设置：风险偏好 = {profile.risk_aversion}，投资周期 = {profile.investment_horizon}\n\n"
            "**可用命令：**\n"
            "- 输入股票代码和你的直觉开始分析，例如：`TSLA 我觉得机器人业务要起飞了`\n"
            "- `/portfolio` - 查看持仓\n"
            "- `/watchlist` - 查看关注列表\n"
            "- `/profile` - 查看/修改用户画像\n"
            "- `/help` - 帮助信息"
        ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages."""
    text = message.content.strip()

    # Check if in onboarding
    if cl.user_session.get("onboarding"):
        await handle_onboarding(text)
        return

    # Handle commands
    if text.startswith("/"):
        await handle_command(text)
        return

    # Try to extract ticker and start analysis
    ticker = extract_ticker(text)
    if not ticker:
        await cl.Message(
            content="请提供股票代码。例如：`TSLA 我觉得电动车市场还有很大空间`\n\n"
            "或输入 `/help` 查看帮助。"
        ).send()
        return

    # The rest of the text is the user's vibe
    user_vibe = re.sub(r"\$?[A-Z]{1,5}", "", text, count=1).strip()
    if not user_vibe:
        user_vibe = f"请分析 {ticker} 的投资价值"

    # Start analysis
    await run_analysis(ticker, user_vibe)


async def handle_onboarding(text: str):
    """Handle onboarding flow."""
    step = cl.user_session.get("onboarding_step", 0)
    data = cl.user_session.get("onboarding_data", {})

    current_question = ONBOARDING_QUESTIONS[step]

    # Process answer
    if current_question["options"]:
        # Mapped answer
        value = current_question["options"].get(text.strip())
        if value is None:
            await cl.Message(content="请输入有效的选项。").send()
            return
        data[current_question["key"]] = value
    else:
        # Free text answer
        data[current_question["key"]] = text.strip() if text.strip() else ""

    # Move to next step
    step += 1
    cl.user_session.set("onboarding_step", step)
    cl.user_session.set("onboarding_data", data)

    if step < len(ONBOARDING_QUESTIONS):
        # Ask next question
        await cl.Message(content=ONBOARDING_QUESTIONS[step]["question"]).send()
    else:
        # Onboarding complete
        await complete_onboarding(data)


async def complete_onboarding(data: dict):
    """Complete onboarding and create profile."""
    profile_mgr = ProfileManager()

    # Build profile
    profile = ProfileData(
        risk_aversion=data.get("risk_aversion", "medium"),
        investment_horizon=data.get("investment_horizon", "long"),
        source_weights={
            "financial_reports": 1.0,
            "news_mainstream": 0.8,
            "social_media": data.get("social_weight", 0.4),
        },
        decision_style=data.get("decision_style", "show_debate"),
    )

    philosophy = data.get("philosophy", "")
    profile_mgr.create(profile, philosophy)

    # Clear onboarding state
    cl.user_session.set("onboarding", False)

    await cl.Message(
        content="✅ 用户画像创建完成！\n\n"
        f"- 风险偏好: **{profile.risk_aversion}**\n"
        f"- 投资周期: **{profile.investment_horizon}**\n"
        f"- 社交媒体权重: **{profile.source_weights['social_media']}**\n"
        f"- 决策风格: **{profile.decision_style}**\n\n"
        "---\n\n"
        "现在你可以开始分析了！输入股票代码和你的直觉，例如：\n"
        "`TSLA 我觉得机器人业务要起飞了`"
    ).send()


async def handle_command(text: str):
    """Handle slash commands."""
    cmd = text.lower().split()[0]

    if cmd == "/portfolio":
        await render_portfolio()
    elif cmd == "/watchlist":
        await render_watchlist()
    elif cmd == "/profile":
        await render_profile()
    elif cmd == "/help":
        await cl.Message(
            content="## Vibe Investment 帮助\n\n"
            "### 分析股票\n"
            "输入股票代码和你的直觉：\n"
            "- `TSLA 我觉得机器人业务要起飞了`\n"
            "- `NVDA AI热潮还能持续多久？`\n\n"
            "### 命令\n"
            "- `/portfolio` - 查看当前持仓\n"
            "- `/watchlist` - 查看关注列表\n"
            "- `/profile` - 查看用户画像\n"
            "- `/reset` - 重置用户画像（重新设置）\n"
            "- `/help` - 显示此帮助\n\n"
            "### 分析流程\n"
            "1. 你提供直觉 (Vibe)\n"
            "2. 🐂 Bull Agent 寻找支持证据\n"
            "3. 🐻 Bear Agent 进行压力测试\n"
            "4. 👔 CIO 做出最终裁决\n"
            "5. 生成投资备忘录"
        ).send()
    elif cmd == "/reset":
        profile_mgr = ProfileManager()
        if profile_mgr.path.exists():
            profile_mgr.path.unlink()
        cl.user_session.set("onboarding", True)
        cl.user_session.set("onboarding_step", 0)
        cl.user_session.set("onboarding_data", {})
        await cl.Message(
            content="用户画像已重置。让我们重新开始...\n\n"
            f"{ONBOARDING_QUESTIONS[0]['question']}"
        ).send()
    else:
        await cl.Message(content=f"未知命令: {cmd}\n输入 `/help` 查看帮助。").send()


async def run_analysis(ticker: str, user_vibe: str):
    """Run the full investment analysis."""
    profile_mgr = ProfileManager()
    profile, _ = profile_mgr.get()

    # Show loading
    loading_msg = await show_loading(f"正在分析 {ticker}...")

    # Track debate rounds
    debate_rounds = []
    current_round = {"bull": "", "bear": ""}

    async def handle_callback(agent: str, content: str):
        """Handle agent updates during analysis."""
        nonlocal current_round, debate_rounds

        if agent == "bull":
            current_round["bull"] = content
            if profile.decision_style == "show_debate":
                await send_agent_message("bull", content[:1000] + "..." if len(content) > 1000 else content)
        elif agent == "bear":
            current_round["bear"] = content
            if profile.decision_style == "show_debate":
                await send_agent_message("bear", content[:1000] + "..." if len(content) > 1000 else content)
            # Save round and start new one
            debate_rounds.append(current_round.copy())
            current_round = {"bull": "", "bear": ""}
        elif agent == "cio":
            if "继续辩论" in content:
                await show_debate_round(len(debate_rounds) + 1, 3)

    # Run analysis
    try:
        result = await run_investment_analysis(
            ticker=ticker,
            user_vibe=user_vibe,
            callback=handle_callback,
        )

        # Update loading message
        await update_loading(loading_msg, f"✅ {ticker} 分析完成！")

        # Get final memo
        memo = result.get("decision_memo", "无法生成投资备忘录")

        # Show memo in side panel
        await render_memo(memo, ticker)

        # Save debate to archive
        debate_mgr = DebateManager()
        debate_mgr.save_debate(
            ticker=ticker,
            user_vibe=user_vibe,
            debate_rounds=debate_rounds,
            final_memo=memo,
        )

        # Ask if user wants to add to portfolio/watchlist
        confirmed = await confirm_action(
            "add_to_watchlist",
            ticker,
            "系统将保存此分析并添加到关注列表。",
        )

        if confirmed:
            # Create stock entry
            pm = PortfolioManager()
            stock = StockData(
                ticker=ticker,
                status="watchlist",
                conviction="medium",
            )
            content = pm.create_analysis_content(
                ticker=ticker,
                bull_case=result.get("bull_notes", ""),
                bear_case=result.get("bear_notes", ""),
                cio_conclusion=memo,
            )
            pm.save_stock(stock, content)
            await cl.Message(content=f"✅ {ticker} 已添加到关注列表！").send()

    except Exception as e:
        await update_loading(loading_msg, f"❌ 分析出错: {str(e)}")
        raise


if __name__ == "__main__":
    # This is for development/testing
    # Production: chainlit run app.py
    import asyncio
    from src.agents.graph import SimpleDebateRunner

    async def test():
        runner = SimpleDebateRunner()
        result = await runner.run_with_logging("TSLA", "我觉得人形机器人要火")
        print("\n" + "=" * 60)
        print("FINAL MEMO:")
        print(result.get("decision_memo", "No memo generated"))

    asyncio.run(test())
