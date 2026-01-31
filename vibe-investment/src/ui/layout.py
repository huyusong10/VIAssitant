"""
Chainlit UI 布局和渲染辅助函数
"""
import chainlit as cl
from typing import Dict, Any, Optional


async def render_memo_sideview(memo_content: str, ticker: str):
    """
    在侧边栏渲染投资决策备忘录
    
    Args:
        memo_content: Markdown格式的备忘录内容
        ticker: 股票代码
    """
    elements = [
        cl.Text(
            name=f"Investment Memo: {ticker}",
            content=memo_content,
            display="side"
        )
    ]
    
    await cl.Message(
        content=f"📊 **投资决策备忘录已生成：{ticker}**\n\n"
                f"右侧边栏已加载完整分析报告。您可以：\n"
                f"- 点击 **'Add to Portfolio'** 将股票加入持仓\n"
                f"- 点击 **'Watchlist'** 加入关注列表\n"
                f"- 继续输入新的投资想法进行下一轮分析",
        elements=elements
    ).send()
    
    # 添加操作按钮
    actions = [
        cl.Action(
            name="add_to_portfolio",
            value=ticker,
            description="Add to portfolio",
            label="📈 加入持仓"
        ),
        cl.Action(
            name="add_to_watchlist",
            value=ticker,
            description="Add to watchlist",
            label="👁️ 加入关注"
        ),
        cl.Action(
            name="save_debate",
            value=ticker,
            description="Save debate to file",
            label="💾 保存辩论记录"
        )
    ]
    
    await cl.Message(
        content="选择下一步操作：",
        actions=actions
    ).send()


async def render_portfolio_dashboard(portfolio_data: Dict[str, Any]):
    """
    渲染持仓仪表板到侧边栏
    
    Args:
        portfolio_data: PortfolioManager.get_portfolio_summary() 的返回结果
    """
    holdings = portfolio_data.get("holdings", [])
    watchlist = portfolio_data.get("watchlist", [])
    
    # 构建Markdown内容
    content = "# 📊 Portfolio Dashboard\n\n"
    
    # 统计信息
    content += f"**总持仓数**: {portfolio_data.get('holding_count', 0)}\n"
    content += f"**关注列表**: {portfolio_data.get('watchlist_count', 0)}\n"
    content += f"**总仓位**: {portfolio_data.get('total_position', 0) * 100:.1f}%\n\n"
    
    # 持仓列表
    content += "## 🎯 Holdings\n\n"
    if holdings:
        content += "| Ticker | Status | Conviction | Position |\n"
        content += "|--------|--------|------------|----------|\n"
        for stock in holdings:
            meta = stock.get("metadata", {})
            ticker = meta.get("ticker", "N/A")
            status = meta.get("status", "unknown")
            conviction = meta.get("conviction", "medium")
            position = meta.get("position_size", 0) * 100
            content += f"| {ticker} | {status} | {conviction} | {position:.1f}% |\n"
    else:
        content += "*No holdings yet*\n"
    
    content += "\n## 👁️ Watchlist\n\n"
    if watchlist:
        for stock in watchlist:
            meta = stock.get("metadata", {})
            ticker = meta.get("ticker", "N/A")
            content += f"- **{ticker}** - {meta.get('conviction', 'N/A')} conviction\n"
    else:
        content += "*No watchlist items*\n"
    
    # 发送到侧边栏
    await cl.Message(
        content="投资组合仪表板已更新",
        elements=[
            cl.Text(
                name="Portfolio Dashboard",
                content=content,
                display="side"
            )
        ]
    ).send()


async def render_debate_log(debate_log: list, current_round: int):
    """
    在对话中渲染辩论过程（白盒化展示）
    
    Args:
        debate_log: 辩论日志列表
        current_round: 当前轮次
    """
    if not debate_log:
        return
    
    latest_entry = debate_log[-1]
    agent = latest_entry.get("agent", "Unknown")
    content = latest_entry.get("content", "")
    tools = latest_entry.get("tool_calls", [])
    
    # 根据Agent显示不同图标
    icon = "🐂" if "Bull" in agent else "🐻" if "Bear" in agent else "⚖️"
    
    # 构建步骤内容
    step_content = f"**{agent}**\n\n{content[:500]}..."
    
    # 创建可折叠的步骤
    async with cl.Step(name=f"{icon} Round {latest_entry.get('round', '?')}: {agent}", type="llm") as step:
        step.output = step_content
        
        # 如果有工具调用，显示搜索详情
        if tools:
            tool_details = "**🔍 搜索详情：**\n\n"
            for tool in tools:
                if "error" in tool:
                    tool_details += f"- ❌ {tool['error']}\n"
                else:
                    tool_name = tool.get("tool", "unknown")
                    result = tool.get("result", "")[:200]
                    tool_details += f"- **{tool_name}**: {result}...\n"
            
            step.output += "\n\n" + tool_details


async def render_user_profile(profile: Dict[str, Any]):
    """
    渲染用户画像到侧边栏
    """
    content = "# 👤 User Profile\n\n"
    content += f"**风险偏好**: {profile.get('risk_aversion', 'medium').title()}\n"
    content += f"**投资周期**: {profile.get('investment_horizon', 'long').title()}\n"
    content += f"**最大辩论轮次**: {profile.get('max_debate_rounds', 3)}\n"
    content += f"**每日简报时间**: {profile.get('daily_briefing_time', '08:00')}\n\n"
    
    content += "## 信息源权重\n\n"
    weights = profile.get("source_weights", {})
    for source, weight in weights.items():
        bar = "█" * int(weight * 10) + "░" * (10 - int(weight * 10))
        content += f"- {source}: {bar} ({weight})\n"
    
    await cl.Message(
        content="用户画像",
        elements=[
            cl.Text(
                name="User Profile",
                content=content,
                display="side"
            )
        ]
    ).send()


def format_stock_for_display(stock_data: Dict[str, Any]) -> str:
    """
    格式化股票数据为显示字符串
    """
    meta = stock_data.get("metadata", {})
    ticker = meta.get("ticker", "N/A")
    status = meta.get("status", "unknown")
    conviction = meta.get("conviction", "N/A")
    
    emoji = "📈" if status == "holding" else "👁️"
    
    return f"{emoji} **{ticker}** ({status.upper()}) - Conviction: {conviction}"
