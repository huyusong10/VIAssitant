"""
LangGraph 编排层
定义多Agent辩论的状态机和流程
"""
import operator
from typing import Annotated, TypedDict, Sequence, List, Dict, Any, Optional, Literal
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from ..utils.config import get_llm
from .prompts import (
    ALPHA_HUNTER_SYSTEM_PROMPT,
    RISK_AUDITOR_SYSTEM_PROMPT,
    CIO_SYSTEM_PROMPT
)
from .tools import TOOLS


# ============================================
# 状态定义
# ============================================
class DebateState(TypedDict):
    """辩论状态机"""
    # 核心输入
    messages: Annotated[Sequence[BaseMessage], operator.add]  # 对话历史
    user_vibe: str  # 用户初始直觉
    ticker: str  # 股票代码
    
    # 用户画像
    profile: Dict[str, Any]  # 用户配置
    
    # 辩论状态
    debate_round: int  # 当前辩论轮次
    max_rounds: int  # 最大轮次
    
    # Agent笔记（累积观点）
    bull_notes: str  # 多头观点累积
    bear_notes: str  # 空头观点累积
    
    # 辩论记录
    debate_log: List[Dict[str, Any]]  # 结构化辩论日志
    
    # 结论
    final_memo: str  # CIO最终备忘录
    decision: Literal["STRONG_BUY", "BUY", "HOLD", "AVOID", "ONGOING"]
    confidence: float  # 置信度 0-100
    
    # 控制流
    next_speaker: Literal["bull", "bear", "cio", "end"]  # 下一个发言者
    should_continue: bool  # 是否继续辩论
    information_gain: float  # 信息增量（用于判断停止）


# ============================================
# 节点函数
# ============================================
def node_initialize(state: DebateState) -> Dict[str, Any]:
    """初始化辩论状态"""
    return {
        "debate_round": 0,
        "bull_notes": "",
        "bear_notes": "",
        "debate_log": [],
        "final_memo": "",
        "decision": "ONGOING",
        "confidence": 0.0,
        "next_speaker": "bull",  # 多头先发言
        "should_continue": True,
        "information_gain": 1.0
    }


def format_tool_result(tool_result: Dict[str, Any]) -> str:
    """格式化工具结果为字符串"""
    if "error" in tool_result:
        return f"Error: {tool_result['error']}"
    
    tool_name = tool_result.get("tool", "unknown")
    result = tool_result.get("result", "")
    
    # 截取前500字符
    if isinstance(result, str):
        result = result[:500]
    else:
        result = str(result)[:500]
    
    return f"[{tool_name}]: {result}"


async def call_llm_with_tools(llm, messages, tools):
    """调用带工具的LLM"""
    # 绑定工具
    llm_with_tools = llm.bind_tools(tools)
    
    # 第一次调用
    response = await llm_with_tools.ainvoke(messages)
    
    # 检查是否有工具调用
    tool_calls = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        # 执行工具调用
        from .tools import search_stock_info, web_search
        
        tool_mapping = {
            "search_stock_info": search_stock_info,
            "web_search": web_search
        }
        
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
            tool_args = tool_call.get("arguments") or tool_call.get("function", {}).get("arguments", {})
            
            if isinstance(tool_args, str):
                import json
                try:
                    tool_args = json.loads(tool_args)
                except:
                    tool_args = {}
            
            if tool_name in tool_mapping:
                try:
                    result = tool_mapping[tool_name].invoke(tool_args)
                    tool_calls.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })
                except Exception as e:
                    tool_calls.append({
                        "tool": tool_name,
                        "error": str(e)
                    })
    
    return response, tool_calls


def node_alpha_hunter(state: DebateState) -> Dict[str, Any]:
    """想象专家 (多头) 节点 - 同步版本"""
    import asyncio
    
    llm = get_llm(temperature=0.4)
    
    profile = state["profile"]
    risk_profile = profile.get("risk_aversion", "medium")
    horizon = profile.get("investment_horizon", "long")
    
    # 构建系统提示
    system_prompt = ALPHA_HUNTER_SYSTEM_PROMPT.format(
        risk_profile=risk_profile,
        investment_horizon=horizon
    )
    
    # 构建消息列表
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User's investment vibe: {state['user_vibe']}")
    ]
    
    # 添加空头观点（如果有）- 用于反驳
    if state["bear_notes"]:
        messages.append(HumanMessage(
            content=f"The Risk Auditor has raised these concerns you must address:\n{state['bear_notes']}"
        ))
    
    messages.append(HumanMessage(
        content=f"Analyze {state['ticker']} and build your bull case. Use search tools to find current data. "
                f"Respond with structured analysis including price targets and catalysts."
    ))
    
    # 调用LLM (在同步函数中运行异步代码)
    loop = asyncio.get_event_loop()
    response, tool_calls = loop.run_until_complete(call_llm_with_tools(llm, messages, TOOLS))
    
    # 更新状态
    debate_entry = {
        "round": state["debate_round"],
        "agent": "Alpha Hunter (Bull)",
        "content": response.content,
        "tool_calls": tool_calls,
        "timestamp": datetime.now().isoformat()
    }
    
    return {
        "bull_notes": state["bull_notes"] + "\n\n" + response.content,
        "debate_log": state["debate_log"] + [debate_entry],
        "next_speaker": "bear"
    }


def node_risk_auditor(state: DebateState) -> Dict[str, Any]:
    """做空专家 (空头) 节点 - 同步版本"""
    import asyncio
    
    llm = get_llm(temperature=0.3)
    
    profile = state["profile"]
    risk_profile = profile.get("risk_aversion", "medium")
    
    # 构建系统提示
    system_prompt = RISK_AUDITOR_SYSTEM_PROMPT.format(
        risk_profile=risk_profile
    )
    
    # 构建消息列表
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Analyzing: {state['ticker']}")
    ]
    
    # 添加多头观点进行批判
    if state["bull_notes"]:
        messages.append(HumanMessage(
            content=f"The Alpha Hunter has made these bullish claims:\n{state['bull_notes']}\n\n"
                    f"Your job is to tear these claims apart with hard data. Find risks, red flags, and reasons to avoid this investment."
        ))
    
    messages.append(HumanMessage(
        content="Use search tools to find financial data, valuation metrics, and risk factors. "
                "Be ruthless but factual. Identify specific red flags and downside scenarios."
    ))
    
    # 调用LLM
    loop = asyncio.get_event_loop()
    response, tool_calls = loop.run_until_complete(call_llm_with_tools(llm, messages, TOOLS))
    
    # 更新状态
    debate_entry = {
        "round": state["debate_round"],
        "agent": "Risk Auditor (Bear)",
        "content": response.content,
        "tool_calls": tool_calls,
        "timestamp": datetime.now().isoformat()
    }
    
    return {
        "bear_notes": state["bear_notes"] + "\n\n" + response.content,
        "debate_log": state["debate_log"] + [debate_entry],
        "next_speaker": "cio"
    }


def node_cio(state: DebateState) -> Dict[str, Any]:
    """统筹专家 (CIO) 节点 - 判断和裁决"""
    import asyncio
    
    llm = get_llm(temperature=0.2)
    
    profile = state["profile"]
    risk_profile = profile.get("risk_aversion", "medium")
    
    # 构建系统提示
    system_prompt = CIO_SYSTEM_PROMPT.format(
        risk_profile=risk_profile
    )
    
    # 构建完整上下文
    context = f"""
Ticker: {state['ticker']}
User's Vibe: {state['user_vibe']}
Debate Round: {state['debate_round']} / {state['max_rounds']}

=== BULL CASE (Alpha Hunter) ===
{state['bull_notes']}

=== BEAR CASE (Risk Auditor) ===
{state['bear_notes']}
"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
        HumanMessage(content=f"""
Evaluate the debate so far. You must decide:
1. Should the debate continue? (Is there significant information gain?)
2. Or should we conclude and generate the final memo?

Current round is {state['debate_round']} of max {state['max_rounds']}.

If concluding, output the complete Investment Decision Memo in the required format.
If continuing, explain what specific information would be valuable in the next round.
""")
    ]
    
    loop = asyncio.get_event_loop()
    response = loop.run_until_complete(llm.ainvoke(messages))
    content = response.content
    
    # 判断逻辑
    current_round = state["debate_round"]
    max_rounds = state["max_rounds"]
    
    # 判断是否继续辩论
    should_continue = False
    next_speaker = "end"
    
    if current_round < max_rounds:
        # 检查是否有明显结论
        has_strong_conclusion = any([
            "STRONG BUY" in content.upper(),
            "STRONG CONVICTION" in content.upper(),
            "AVOID" in content.upper() and "MUST AVOID" in content.upper()
        ])
        
        # 检查是否信息重复（简单启发式）
        information_gain = 0.5  # 默认中等增益
        if "no new information" in content.lower() or "repetition" in content.lower():
            information_gain = 0.1
        
        if not has_strong_conclusion and information_gain > 0.2:
            should_continue = True
            next_speaker = "bull"  # 继续下一轮，让多头先回应
    
    # 尝试提取置信度
    confidence = 50.0  # 默认
    try:
        if "confidence" in content.lower():
            import re
            match = re.search(r'confidence[\s:]*(\d+)', content.lower())
            if match:
                confidence = float(match.group(1))
    except:
        pass
    
    # 尝试提取决策
    decision = "ONGOING"
    if "STRONG BUY" in content.upper():
        decision = "STRONG_BUY"
    elif "BUY" in content.upper():
        decision = "BUY"
    elif "HOLD" in content.upper():
        decision = "HOLD"
    elif "AVOID" in content.upper():
        decision = "AVOID"
    
    return {
        "debate_round": current_round + 1,
        "information_gain": 0.5 if should_continue else 0.0,
        "should_continue": should_continue,
        "next_speaker": next_speaker,
        "final_memo": content if not should_continue else state.get("final_memo", ""),
        "confidence": confidence,
        "decision": decision if not should_continue else "ONGOING"
    }


def router(state: DebateState) -> str:
    """路由函数 - 决定下一个节点"""
    next_speaker = state.get("next_speaker", "end")
    
    if next_speaker == "bull":
        return "bull_agent"
    elif next_speaker == "bear":
        return "bear_agent"
    elif next_speaker == "cio":
        return "cio_agent"
    else:
        return "end"


# ============================================
# 构建Graph
# ============================================
def create_debate_graph() -> StateGraph:
    """创建辩论状态图"""
    
    # 创建图
    workflow = StateGraph(DebateState)
    
    # 添加节点
    workflow.add_node("initialize", node_initialize)
    workflow.add_node("bull_agent", node_alpha_hunter)
    workflow.add_node("bear_agent", node_risk_auditor)
    workflow.add_node("cio_agent", node_cio)
    
    # 添加边
    workflow.set_entry_point("initialize")
    
    # 初始化 -> 多头
    workflow.add_edge("initialize", "bull_agent")
    
    # 多头 -> 空头
    workflow.add_edge("bull_agent", "bear_agent")
    
    # 空头 -> CIO (判断)
    workflow.add_edge("bear_agent", "cio_agent")
    
    # CIO -> 条件路由
    workflow.add_conditional_edges(
        "cio_agent",
        router,
        {
            "bull_agent": "bull_agent",
            "bear_agent": "bear_agent",
            "cio_agent": "cio_agent",
            "end": END
        }
    )
    
    return workflow.compile()


# ============================================
# 简化接口
# ============================================
async def run_debate(
    ticker: str,
    user_vibe: str,
    profile: Dict[str, Any],
    max_rounds: int = 3
) -> Dict[str, Any]:
    """
    运行完整的辩论流程
    
    Args:
        ticker: 股票代码
        user_vibe: 用户直觉
        profile: 用户画像
        max_rounds: 最大辩论轮次
    
    Returns:
        包含最终状态和结果的dict
    """
    graph = create_debate_graph()
    
    initial_state = {
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
    
    result = await graph.ainvoke(initial_state)
    return result
