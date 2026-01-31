"""UI components for Chainlit interface."""

from typing import Optional

import chainlit as cl

from src.data_mgr.markdown_db import PortfolioManager, ProfileManager, StockData


async def render_memo(memo_content: str, ticker: str) -> None:
    """Render investment memo in the side panel.

    Args:
        memo_content: The markdown content of the memo
        ticker: Stock ticker for the title
    """
    elements = [
        cl.Text(
            name=f"{ticker} Investment Memo",
            content=memo_content,
            display="side",
            language="markdown",
        )
    ]

    await cl.Message(
        content=f"**{ticker}** 分析完成！请查看右侧面板的投资备忘录。",
        elements=elements,
    ).send()


async def render_portfolio() -> None:
    """Render current portfolio in the side panel."""
    pm = PortfolioManager()
    holdings = pm.list_holdings()

    if not holdings:
        content = "# 持仓列表\n\n*暂无持仓*"
    else:
        content = "# 持仓列表\n\n"
        content += "| 代码 | 成本 | 仓位 | 止损 | 置信度 |\n"
        content += "|------|------|------|------|--------|\n"

        for stock in holdings:
            content += (
                f"| {stock.ticker} "
                f"| ${stock.avg_cost or 'N/A'} "
                f"| {(stock.position_size or 0) * 100:.1f}% "
                f"| ${stock.stop_loss or 'N/A'} "
                f"| {stock.conviction} |\n"
            )

    elements = [
        cl.Text(
            name="Portfolio",
            content=content,
            display="side",
            language="markdown",
        )
    ]

    await cl.Message(
        content="当前持仓已更新到右侧面板。",
        elements=elements,
    ).send()


async def render_watchlist() -> None:
    """Render watchlist in the side panel."""
    pm = PortfolioManager()
    watchlist = pm.list_watchlist()

    if not watchlist:
        content = "# 关注列表\n\n*暂无关注*"
    else:
        content = "# 关注列表\n\n"
        for stock in watchlist:
            content += f"- **{stock.ticker}** (置信度: {stock.conviction})\n"

    elements = [
        cl.Text(
            name="Watchlist",
            content=content,
            display="side",
            language="markdown",
        )
    ]

    await cl.Message(
        content="关注列表已更新到右侧面板。",
        elements=elements,
    ).send()


async def render_profile() -> None:
    """Render user profile in the side panel."""
    pm = ProfileManager()
    profile, philosophy = pm.get()

    content = f"""# 投资者画像

## 基本设置
- **风险偏好**: {profile.risk_aversion}
- **投资周期**: {profile.investment_horizon}
- **决策风格**: {profile.decision_style}

## 信息源权重
- 财务报表: {profile.source_weights.get('financial_reports', 1.0)}
- 主流媒体: {profile.source_weights.get('news_mainstream', 0.8)}
- 社交媒体: {profile.source_weights.get('social_media', 0.4)}

## 投资理念
{philosophy or '(未设置)'}

*最后更新: {profile.last_updated}*
"""

    elements = [
        cl.Text(
            name="User Profile",
            content=content,
            display="side",
            language="markdown",
        )
    ]

    await cl.Message(
        content="用户画像已更新到右侧面板。",
        elements=elements,
    ).send()


async def show_agent_thinking(agent_name: str, content: str) -> cl.Step:
    """Show agent thinking process as a collapsible step.

    Args:
        agent_name: Name of the agent (bull, bear, cio)
        content: The agent's analysis content

    Returns:
        The Step object for further updates
    """
    icons = {
        "bull": "🐂",
        "bear": "🐻",
        "cio": "👔",
        "search": "🔍",
    }

    names = {
        "bull": "Alpha Hunter (Bull Agent)",
        "bear": "Risk Auditor (Bear Agent)",
        "cio": "Portfolio CIO",
        "search": "Web Search",
    }

    icon = icons.get(agent_name, "🤖")
    name = names.get(agent_name, agent_name)

    step = cl.Step(name=f"{icon} {name}", type="llm")
    step.output = content

    return step


async def send_agent_message(agent_name: str, content: str) -> None:
    """Send a message showing agent output.

    Args:
        agent_name: Name of the agent
        content: The message content
    """
    icons = {
        "bull": "🐂",
        "bear": "🐻",
        "cio": "👔",
    }

    icon = icons.get(agent_name, "🤖")

    await cl.Message(
        content=f"**{icon} {agent_name.upper()}**\n\n{content}",
    ).send()


async def confirm_action(
    action: str,
    ticker: str,
    details: Optional[str] = None,
) -> bool:
    """Ask user to confirm an action.

    Args:
        action: The action to confirm (e.g., "add_to_portfolio")
        ticker: The stock ticker
        details: Optional additional details

    Returns:
        True if user confirmed, False otherwise
    """
    actions = [
        cl.Action(name="confirm", payload={"confirmed": True}, label="✅ 确认"),
        cl.Action(name="cancel", payload={"confirmed": False}, label="❌ 取消"),
    ]

    message_content = f"是否要将 **{ticker}** "
    if action == "add_to_portfolio":
        message_content += "加入持仓列表？"
    elif action == "add_to_watchlist":
        message_content += "加入关注列表？"
    elif action == "remove":
        message_content += "从列表中移除？"
    else:
        message_content += f"执行 {action}？"

    if details:
        message_content += f"\n\n{details}"

    res = await cl.AskActionMessage(
        content=message_content,
        actions=actions,
    ).send()

    if res and res.get("payload", {}).get("confirmed"):
        return True
    return False


async def show_debate_round(round_num: int, max_rounds: int) -> None:
    """Show debate round indicator."""
    await cl.Message(
        content=f"📊 **辩论进行中** - 第 {round_num}/{max_rounds} 轮",
    ).send()


async def show_loading(message: str = "分析中...") -> cl.Message:
    """Show a loading message.

    Returns:
        The message object for later updating
    """
    msg = cl.Message(content=f"⏳ {message}")
    await msg.send()
    return msg


async def update_loading(msg: cl.Message, new_content: str) -> None:
    """Update a loading message."""
    msg.content = new_content
    await msg.update()
