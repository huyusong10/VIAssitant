"""
Vibe Investment System - Chainlit Main Application

启动命令: chainlit run app.py -w
"""
import os
import sys
import re
import asyncio
from pathlib import Path
from typing import Optional

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

import chainlit as cl
from chainlit.input_widget import Select, Slider

from src.data_mgr import ProfileManager, PortfolioManager, DebateManager
from src.agents import run_debate
from src.agents.prompts import ONBOARDING_QUESTIONS, ONBOARDING_PROMPT, TICKER_EXTRACT_PROMPT
from src.ui import render_memo_sideview, render_portfolio_dashboard
from src.utils.config import settings, get_fast_llm

# ============================================
# 全局状态管理
# ============================================
class AppState:
    """应用状态管理"""
    def __init__(self):
        self.profile_mgr = None
        self.portfolio_mgr = None
        self.debate_mgr = None
        self.user_profile = None
        self.onboarding_step = 0
        self.onboarding_answers = {}
        self.current_ticker = None

# 初始化全局状态
app_state = AppState()


# ============================================
# 生命周期回调
# ============================================
@cl.on_chat_start
async def on_chat_start():
    """聊天会话开始时初始化"""
    # 验证配置
    missing = settings.validate()
    if missing:
        await cl.Message(
            content=f"⚠️ **配置缺失**: {', '.join(missing)}\n\n"
                    f"请复制 `.env.example` 为 `.env` 并填写必要的API密钥。"
        ).send()
        return
    
    # 初始化数据管理器
    data_path = settings.DATA_PATH
    app_state.profile_mgr = ProfileManager(data_path)
    app_state.portfolio_mgr = PortfolioManager(data_path)
    app_state.debate_mgr = DebateManager(data_path)
    
    # 加载用户画像
    app_state.user_profile = app_state.profile_mgr.get_profile()
    
    # 检查是否是首次使用（需要onboarding）
    if app_state.user_profile.get("onboarding_complete"):
        await show_welcome_back()
    else:
        await start_onboarding()


@cl.on_stop
async def on_stop():
    """停止时的清理"""
    pass


# ============================================
# Onboarding 流程
# ============================================
async def start_onboarding():
    """开始用户引导流程"""
    await cl.Message(
        content="# 🚀 Welcome to Vibe Investment\n\n"
                "This is an AI-powered investment analysis system with multi-agent debate.\n\n"
                "Before we start, let me ask a few questions to personalize your experience."
    ).send()
    
    app_state.onboarding_step = 0
    await ask_onboarding_question()


async def ask_onboarding_question():
    """询问当前的onboarding问题"""
    step = app_state.onboarding_step
    
    if step >= len(ONBOARDING_QUESTIONS):
        await complete_onboarding()
        return
    
    question = ONBOARDING_QUESTIONS[step]
    
    # 构建选项
    options_text = "\n".join([
        f"{i+1}. {opt.split(':')[1].strip() if ':' in opt else opt}"
        for i, opt in enumerate(question["options"])
    ])
    
    msg = ONBOARDING_PROMPT.format(
        current=step + 1,
        total=len(ONBOARDING_QUESTIONS),
        question=question["question"],
        options=options_text
    )
    
    await cl.Message(content=msg).send()


async def complete_onboarding():
    """完成onboarding，保存用户画像"""
    # 更新profile
    app_state.profile_mgr.update_profile({
        **app_state.onboarding_answers,
        "onboarding_complete": True
    })
    
    # 重新加载
    app_state.user_profile = app_state.profile_mgr.get_profile()
    
    await cl.Message(
        content="✅ **Profile Created!**\n\n"
                f"Your preferences:\n"
                f"- Risk Tolerance: {app_state.user_profile.get('risk_aversion', 'medium')}\n"
                f"- Investment Horizon: {app_state.user_profile.get('investment_horizon', 'long')}\n\n"
                f"Let's start investing! Share your investment 'vibe' or intuition.\n"
                f"For example: *'I think Tesla's robotaxi announcement will be huge'*"
    ).send()


# ============================================
# 欢迎回来
# ============================================
async def show_welcome_back():
    """显示欢迎回来界面"""
    profile = app_state.user_profile
    
    # 显示投资组合摘要
    summary = app_state.portfolio_mgr.get_portfolio_summary()
    
    await cl.Message(
        content=f"# 👋 Welcome Back!\n\n"
                f"**Your Profile**: {profile.get('risk_aversion', 'medium')} risk | "
                f"{profile.get('investment_horizon', 'long')} term\n\n"
                f"**Portfolio Status**: {summary['holding_count']} holdings | "
                f"{summary['watchlist_count']} watching\n\n"
                f"Share your latest investment idea or vibe! 🎯"
    ).send()
    
    # 显示持仓仪表板
    await render_portfolio_dashboard(summary)


# ============================================
# 主要消息处理
# ============================================
@cl.on_message
async def on_message(message: cl.Message):
    """处理用户消息"""
    user_input = message.content.strip()
    
    # 检查是否还在onboarding
    if not app_state.user_profile.get("onboarding_complete"):
        await handle_onboarding_response(user_input)
        return
    
    # 检查是否是特殊命令
    if await handle_command(user_input):
        return
    
    # 提取股票代码
    ticker = await extract_ticker(user_input)
    
    if not ticker:
        # 检查是否是API key问题
        from src.utils.config import settings
        missing = settings.validate()
        
        if missing:
            await cl.Message(
                content="⚠️ **Configuration Issue**\n\n"
                        f"Missing: {', '.join(missing)}\n\n"
                        f"Please check your `.env` file:\n"
                        f"1. Copy `.env.example` to `.env`\n"
                        f"2. Add your API keys (DEEPSEEK_API_KEY or TAVILY_API_KEY)\n"
                        f"3. Restart the application"
            ).send()
        else:
            await cl.Message(
                content="❓ I couldn't identify a specific stock ticker in your message.\n\n"
                        "**Try these formats:**\n"
                        "- Direct ticker: `TSLA`, `AAPL`, `NVDA`\n"
                        "- With parentheses: `Tesla (TSLA)`\n"
                        "- With dollar sign: `$TSLA`\n"
                        "- Full sentence: `What do you think about NVDA?`\n\n"
                        "**Examples:**\n"
                        "- `TSLA robotaxi could be huge`\n"
                        "- `Is $AAPL overvalued?`\n"
                        "- `Buy NVDA (NVDA) on the dip`"
            ).send()
        return
    
    # 保存当前ticker
    app_state.current_ticker = ticker
    
    # 启动投资分析流程
    await run_investment_analysis(ticker, user_input)


async def handle_onboarding_response(user_input: str):
    """处理onboarding阶段的回答"""
    step = app_state.onboarding_step
    question = ONBOARDING_QUESTIONS[step]
    
    # 解析回答 (支持数字或文本)
    answer_value = None
    
    # 尝试解析数字选择
    if user_input.isdigit():
        choice = int(user_input) - 1
        if 0 <= choice < len(question["options"]):
            answer_value = question["options"][choice].split(":")[0].strip()
    else:
        # 尝试匹配选项文本
        for opt in question["options"]:
            key = opt.split(":")[0].strip()
            if key.lower() in user_input.lower():
                answer_value = key
                break
    
    if not answer_value:
        await cl.Message(
            content="Please select a valid option (enter the number or keyword)."
        ).send()
        return
    
    # 保存答案
    app_state.onboarding_answers[question["key"]] = answer_value
    app_state.onboarding_step += 1
    
    # 继续下一个问题
    await ask_onboarding_question()


async def handle_command(user_input: str) -> bool:
    """
    处理特殊命令
    返回True如果消息是命令
    """
    cmd = user_input.lower().strip()
    
    if cmd in ["/portfolio", "/holdings", "show portfolio"]:
        summary = app_state.portfolio_mgr.get_portfolio_summary()
        await render_portfolio_dashboard(summary)
        return True
    
    elif cmd in ["/profile", "/settings", "show profile"]:
        await render_user_profile()
        return True
    
    elif cmd.startswith("/add "):
        # 快速添加: /add TSLA
        ticker = cmd.split()[-1].upper()
        if ticker.isalpha():
            app_state.portfolio_mgr.add_or_update_stock(
                ticker, status="watchlist"
            )
            await cl.Message(content=f"✅ Added {ticker} to watchlist").send()
            return True
    
    elif cmd.startswith("/remove "):
        # 快速移除: /remove TSLA
        ticker = cmd.split()[-1].upper()
        app_state.portfolio_mgr.remove_stock(ticker)
        await cl.Message(content=f"🗑️ Removed {ticker}").send()
        return True
    
    elif cmd in ["/help", "help"]:
        await show_help()
        return True
    
    return False


async def show_help():
    """显示帮助信息"""
    await cl.Message(
        content="# 📖 Vibe Investment Help\n\n"
                "## Basic Usage\n"
                "Simply share your investment intuition or 'vibe':\n"
                "- *'TSLA robotaxi could be huge'*\n"
                "- *'Is NVDA overvalued after the runup?'*\n\n"
                "## Commands\n"
                "- `/portfolio` - Show your holdings and watchlist\n"
                "- `/profile` - Show your risk profile\n"
                "- `/add TICKER` - Quick add to watchlist\n"
                "- `/remove TICKER` - Remove a stock\n"
                "- `/help` - Show this help\n\n"
                "## How It Works\n"
                "1. **Alpha Hunter** (🐂) builds the bull case\n"
                "2. **Risk Auditor** (🐻) identifies risks and red flags\n"
                "3. **CIO** (⚖️) synthesizes and gives recommendation\n\n"
                "All analysis is transparent - you can see the debate process!"
    ).send()


async def extract_ticker(message: str) -> Optional[str]:
    """
    从消息中提取股票代码
    使用简单的LLM调用或正则匹配
    """
    # 转换为大写以便匹配
    message_upper = message.upper()
    
    # 模式1: 括号中的代码，如 "Tesla (TSLA)" 或 "Tesla(TSLA)"
    bracket_match = re.search(r'\(([A-Z]{1,5})\)', message_upper)
    if bracket_match:
        return bracket_match.group(1)
    
    # 模式2: 美元符号前缀，如 "$TSLA"
    dollar_match = re.search(r'\$([A-Z]{1,5})\b', message_upper)
    if dollar_match:
        return dollar_match.group(1)
    
    # 模式3: 独立的2-5位大写字母（常见股票代码格式）
    # 排除常见单词
    common_words = {'I', 'A', 'AN', 'AS', 'AT', 'BE', 'BY', 'DO', 'GO', 'IF', 'IN', 'IS', 'IT', 'MY', 'NO', 'OF', 'ON', 'OR', 'SO', 'TO', 'UP', 'US', 'WE', 'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HAD', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'MAN', 'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WAY', 'WHO', 'BOY', 'DID', 'ITS', 'LET', 'PUT', 'SAY', 'SHE', 'TOO', 'USE', 'AI', 'API', 'APP', 'IPO', 'EPS', 'GDP', 'CPI', 'PPI', 'Fed', 'USD', 'ETF', 'NAV', 'ROE', 'ROA', 'P_E', 'P_B'}
    
    words = re.findall(r'\b([A-Z]{2,5})\b', message_upper)
    for word in words:
        if word not in common_words:
            # 检查是否是已知的持仓
            stock = app_state.portfolio_mgr.get_stock(word)
            if stock:
                return word
            # 返回第一个看起来像是股票代码的
            return word
    
    # 模式4: 单个大写字母（如 'I bought A' 可能指 Apple）
    single_letter = re.findall(r'\b([A-Z])\b', message_upper)
    for letter in single_letter:
        if letter not in {'A', 'I'}:  # 排除常见单字母词
            return letter
    
    # 模式5: 使用LLM提取（如果以上都失败）
    try:
        # 检查是否有API key
        from src.utils.config import settings
        if not settings.DEEPSEEK_API_KEY and not settings.OPENAI_API_KEY and not settings.ANTHROPIC_API_KEY:
            print("No API key configured for LLM extraction")
            return None
            
        llm = get_fast_llm()
        prompt = TICKER_EXTRACT_PROMPT.format(message=message)
        response = await llm.ainvoke([("human", prompt)])
        ticker = response.content.strip().upper()
        
        if ticker and ticker != "NONE" and len(ticker) <= 5:
            return ticker
    except Exception as e:
        print(f"Error extracting ticker with LLM: {e}")
    
    return None


# ============================================
# 核心分析流程 - 流式版本
# ============================================
async def run_investment_analysis_streaming(ticker: str, user_vibe: str):
    """
    运行完整的投资分析流程 - 流式展示每个Agent的思考过程
    """
    # 获取用户画像
    profile = app_state.user_profile
    max_rounds = profile.get("max_debate_rounds", 3)
    
    # 初始化状态
    state = {
        "messages": [],
        "user_vibe": user_vibe,
        "ticker": ticker,
        "profile": profile,
        "debate_round": 0,
        "max_rounds": max_rounds,
        "bull_notes": "",
        "bear_notes": "",
        "debate_log": [],
        "final_memo": "",
        "decision": "ONGOING",
        "confidence": 0.0,
        "next_speaker": "bull",
        "should_continue": True,
        "information_gain": 1.0
    }
    
    # 显示开始消息
    await cl.Message(
        content=f"🔍 **开始分析 {ticker}**\n\n"
                f"**投资直觉**: _{user_vibe}_\n\n"
                f"即将开始三方辩论，每位专家将实时展示其研究过程..."
    ).send()
    
    try:
        round_num = 0
        while round_num < max_rounds and state["should_continue"]:
            round_num += 1
            state["debate_round"] = round_num
            
            # ============ Round Start ============
            await cl.Message(
                content=f"---\n## 🔄 第 {round_num} 轮辩论\n"
            ).send()
            
            # ============ 🐂 Alpha Hunter ============
            async with cl.Step(name=f"🐂 Alpha Hunter 正在研究 {ticker}...", type="llm") as step:
                await step.stream_token(f"**正在搜索 {ticker} 的看涨因素...**\n\n")
                
                # 执行 Alpha Hunter
                from src.agents.graph import node_alpha_hunter
                result = node_alpha_hunter(state)
                
                # 更新状态
                state["bull_notes"] = result["bull_notes"]
                state["debate_log"] = result["debate_log"]
                state["next_speaker"] = result["next_speaker"]
                
                # 获取最新的辩论记录
                latest_log = state["debate_log"][-1]
                content = latest_log["content"]
                tool_calls = latest_log.get("tool_calls", [])
                
                # 流式展示内容
                await step.stream_token(f"**观点形成中...**\n\n")
                
                # 展示搜索的工具
                if tool_calls:
                    await step.stream_token("**📊 搜索数据来源:**\n")
                    for tool in tool_calls[:3]:
                        tool_name = tool.get("tool", "search")
                        await step.stream_token(f"- 🔍 {tool_name}\n")
                    await step.stream_token("\n")
                
                # 展示主要观点（分段展示）
                await step.stream_token("**📝 多头分析:**\n\n")
                # 分段流式输出
                chunks = [content[i:i+100] for i in range(0, min(len(content), 2000), 100)]
                for chunk in chunks:
                    await step.stream_token(chunk)
                    await asyncio.sleep(0.05)  # 小延迟让流式效果更明显
                
                step.output = f"✅ Alpha Hunter 完成分析 ({len(content)} 字符)"
            
            # ============ 🐻 Risk Auditor ============
            async with cl.Step(name=f"🐻 Risk Auditor 正在审查 {ticker}...", type="llm") as step:
                await step.stream_token(f"**正在搜索 {ticker} 的风险因素...**\n\n")
                
                # 执行 Risk Auditor
                from src.agents.graph import node_risk_auditor
                result = node_risk_auditor(state)
                
                # 更新状态
                state["bear_notes"] = result["bear_notes"]
                state["debate_log"] = result["debate_log"]
                state["next_speaker"] = result["next_speaker"]
                
                # 获取最新的辩论记录
                latest_log = state["debate_log"][-1]
                content = latest_log["content"]
                tool_calls = latest_log.get("tool_calls", [])
                
                # 展示搜索的工具
                if tool_calls:
                    await step.stream_token("**📊 风险数据来源:**\n")
                    for tool in tool_calls[:3]:
                        tool_name = tool.get("tool", "search")
                        await step.stream_token(f"- 🔍 {tool_name}\n")
                    await step.stream_token("\n")
                
                # 展示风险分析
                await step.stream_token("**⚠️ 风险分析:**\n\n")
                chunks = [content[i:i+100] for i in range(0, min(len(content), 2000), 100)]
                for chunk in chunks:
                    await step.stream_token(chunk)
                    await asyncio.sleep(0.05)
                
                step.output = f"✅ Risk Auditor 完成审查 ({len(content)} 字符)"
            
            # ============ ⚖️ CIO Decision ============
            async with cl.Step(name="⚖️ CIO 正在权衡决策...", type="llm") as step:
                await step.stream_token("**正在评估双方论点...**\n\n")
                
                # 执行 CIO
                from src.agents.graph import node_cio
                result = node_cio(state)
                
                # 更新状态
                state["debate_round"] = result["debate_round"]
                state["should_continue"] = result["should_continue"]
                state["next_speaker"] = result["next_speaker"]
                state["final_memo"] = result["final_memo"]
                state["confidence"] = result["confidence"]
                state["decision"] = result["decision"]
                
                # 展示CIO的思考
                if result["should_continue"] and round_num < max_rounds:
                    await step.stream_token(f"**📊 评估结果:**\n")
                    await step.stream_token(f"- 当前轮次: {round_num}/{max_rounds}\n")
                    await step.stream_token(f"- 置信度: {result['confidence']}%\n")
                    await step.stream_token(f"- 结论: 需要更多信息，进入下一轮辩论\n\n")
                    step.output = "🔄 需要更多信息，继续辩论"
                else:
                    await step.stream_token(f"**✅ 最终评估完成**\n")
                    await step.stream_token(f"- 置信度: {result['confidence']}%\n")
                    await step.stream_token(f"- 决策: {result['decision']}\n")
                    step.output = "✅ 辩论结束，生成最终报告"
            
            # 检查是否结束
            if not state["should_continue"]:
                break
        
        # ============ 展示最终结果 ============
        final_memo = state["final_memo"]
        decision = state["decision"]
        confidence = state["confidence"]
        
        if final_memo:
            await cl.Message(
                content=f"---\n## ✅ 辩论完成！\n\n"
                        f"**共进行 {round_num} 轮辩论**\n"
                        f"**最终置信度**: {confidence}%\n"
                        f"**决策建议**: {decision}\n\n"
                        f"📄 **完整投资备忘录已生成**，请查看右侧边栏 →"
            ).send()
            
            # 渲染侧边栏备忘录
            await render_memo_sideview(final_memo, ticker)
            
            # 保存到数据库
            app_state.portfolio_mgr.add_or_update_stock(
                ticker=ticker,
                status="watchlist",
                metadata={
                    "latest_confidence": confidence,
                    "latest_decision": decision,
                    "last_analysis": asyncio.get_event_loop().time()
                },
                cio_conclusion=final_memo[:1000]
            )
            
            # 保存辩论记录
            debate_path = app_state.debate_mgr.save_debate(
                ticker=ticker,
                debate_log=state["debate_log"],
                final_memo=final_memo,
                user_vibe=user_vibe
            )
            
            await cl.Message(
                content=f"💾 **辩论记录已保存**: `{debate_path}`"
            ).send()
        else:
            await cl.Message(
                content="⚠️ 辩论完成但未生成最终备忘录。"
            ).send()
            
    except Exception as e:
        await cl.Message(
            content=f"❌ **分析过程中出错**: {str(e)}\n\n"
                    f"请检查API密钥和网络连接后重试。"
        ).send()
        import traceback
        print(traceback.format_exc())
        raise


# 保留旧函数以兼容
async def run_investment_analysis(ticker: str, user_vibe: str):
    """兼容旧接口，调用流式版本"""
    await run_investment_analysis_streaming(ticker, user_vibe)


async def display_debate_process(debate_log: list):
    """显示辩论过程（可折叠）"""
    if not debate_log:
        return
    
    # 为每个辩论条目创建步骤
    for entry in debate_log:
        agent = entry.get("agent", "Unknown")
        content = entry.get("content", "")
        round_num = entry.get("round", 0)
        tools = entry.get("tool_calls", [])
        
        # 选择图标
        icon = "🐂" if "Bull" in agent else "🐻" if "Bear" in agent else "⚖️"
        
        # 创建步骤
        async with cl.Step(name=f"{icon} {agent} (Round {round_num})") as step:
            step_content = content[:800] + "..." if len(content) > 800 else content
            
            # 添加工具调用信息
            if tools:
                step_content += "\n\n**🔍 Research Sources:**\n"
                for tool in tools[:3]:  # 只显示前3个
                    if "error" not in tool:
                        tool_name = tool.get("tool", "search")
                        result = tool.get("result", "")[:150]
                        step_content += f"- `{tool_name}`: {result}...\n"
            
            step.output = step_content


async def render_user_profile():
    """显示用户画像"""
    profile = app_state.user_profile
    
    content = f"""# 👤 Your Investment Profile

**Risk Tolerance**: {profile.get('risk_aversion', 'medium').title()}
**Investment Horizon**: {profile.get('investment_horizon', 'long').title()}
**Max Debate Rounds**: {profile.get('max_debate_rounds', 3)}
**Daily Briefing**: {profile.get('daily_briefing_time', '08:00')}

## Information Source Weights
"""
    
    weights = profile.get("source_weights", {})
    for source, weight in weights.items():
        bar = "█" * int(weight * 10) + "░" * (10 - int(weight * 10))
        content += f"- {source}: {bar} {weight}\n"
    
    await cl.Message(
        content=content,
        elements=[
            cl.Text(name="Profile", content=content, display="side")
        ]
    ).send()


# ============================================
# 动作回调
# ============================================
@cl.action_callback("add_to_portfolio")
async def on_add_to_portfolio(action):
    """添加到持仓"""
    ticker = action.value
    
    # 更新状态
    app_state.portfolio_mgr.add_or_update_stock(
        ticker=ticker,
        status="holding",
        metadata={"added_at": asyncio.get_event_loop().time()}
    )
    
    await cl.Message(content=f"✅ **{ticker}** added to your portfolio (holding)").send()
    
    # 更新仪表板
    summary = app_state.portfolio_mgr.get_portfolio_summary()
    await render_portfolio_dashboard(summary)


@cl.action_callback("add_to_watchlist")
async def on_add_to_watchlist(action):
    """添加到关注列表"""
    ticker = action.value
    
    app_state.portfolio_mgr.add_or_update_stock(
        ticker=ticker,
        status="watchlist"
    )
    
    await cl.Message(content=f"👁️ **{ticker}** added to watchlist").send()


@cl.action_callback("save_debate")
async def on_save_debate(action):
    """保存辩论记录"""
    await cl.Message(content="💾 Debate already auto-saved to data/debates/").send()


# ============================================
# 主入口
# ============================================
if __name__ == "__main__":
    # 这行在chainlit run时不会执行
    pass
