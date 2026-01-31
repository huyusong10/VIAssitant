"""Agent node implementations for the investment analysis graph."""

import json
from datetime import datetime
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate

from src.agents.prompts import BASE_CONTEXT, BEAR_PROMPT, BULL_PROMPT, CIO_PROMPT
from src.agents.tools import get_tools_for_agent
from src.data_mgr.markdown_db import ProfileData, ProfileManager
from src.utils.config import get_settings


def get_llm(with_tools: bool = False, tools: list = None):
    """Get the configured LLM instance."""
    settings = get_settings()

    if settings.default_llm == "claude":
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=settings.claude_model,
            api_key=settings.anthropic_api_key,
            temperature=0.7,
        )
    elif settings.default_llm == "deepseek":
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.7,
        )
    else:  # openai
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
        )

    if with_tools and tools:
        return llm.bind_tools(tools)
    return llm


def format_base_context(state: dict) -> str:
    """Format the base context with current state."""
    profile_mgr = ProfileManager()
    profile, _ = profile_mgr.get()

    return BASE_CONTEXT.format(
        risk_aversion=profile.risk_aversion,
        investment_horizon=profile.investment_horizon,
        financial_weight=profile.source_weights.get("financial_reports", 1.0),
        news_weight=profile.source_weights.get("news_mainstream", 0.8),
        social_weight=profile.source_weights.get("social_media", 0.4),
        ticker=state.get("ticker", "Unknown"),
        user_vibe=state.get("user_vibe", ""),
    )


class BullAgent:
    """Alpha Hunter - seeks growth opportunities."""

    def __init__(self):
        self.tools = get_tools_for_agent("bull")
        self.llm_with_tools = get_llm(with_tools=True, tools=self.tools)
        self.llm_no_tools = get_llm(with_tools=False)
        self.tool_map = {t.name: t for t in self.tools}

    async def analyze(self, state: dict) -> dict:
        """Generate bull case analysis."""
        base_context = format_base_context(state)
        prompt = BULL_PROMPT.format(base_context=base_context)

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content=f"请分析 {state['ticker']}，用户直觉是：{state['user_vibe']}"
            ),
        ]

        # If there's previous bear arguments to respond to
        if state.get("bear_notes"):
            messages.append(
                HumanMessage(
                    content=f"Bear Agent 提出了以下反驳，请回应：\n{state['bear_notes']}"
                )
            )

        # First call - may return tool calls
        response = await self.llm_with_tools.ainvoke(messages)

        # Handle tool calls if any (up to 3 iterations)
        for _ in range(3):
            if not hasattr(response, "tool_calls") or not response.tool_calls:
                break

            # Execute tools and create proper ToolMessage responses
            messages.append(response)
            tool_messages = await self._execute_tools_as_messages(response.tool_calls)
            messages.extend(tool_messages)

            # Get next response
            response = await self.llm_with_tools.ainvoke(messages)

        # If response still has tool_calls but no content, get a final summary
        if not response.content or response.content.strip() == "":
            # Collect all tool results for context
            tool_results = self._collect_tool_results(messages)
            summary_messages = [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=f"基于以下搜索结果，请分析 {state['ticker']}：\n\n{tool_results}"
                ),
            ]
            response = await self.llm_no_tools.ainvoke(summary_messages)

        return {
            "bull_notes": response.content,
            "messages": state.get("messages", [])
            + [{"role": "bull", "content": response.content}],
        }

    async def _execute_tools_as_messages(self, tool_calls: list) -> list[ToolMessage]:
        """Execute tool calls and return ToolMessage objects."""
        tool_messages = []

        for call in tool_calls:
            tool_name = call.get("name") or call.get("function", {}).get("name")
            tool_args = call.get("args") or call.get("function", {}).get("arguments", {})
            tool_call_id = call.get("id", f"call_{tool_name}")

            # Parse args if string
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {}

            tool = self.tool_map.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    tool_messages.append(
                        ToolMessage(content=str(result), tool_call_id=tool_call_id)
                    )
                except Exception as e:
                    tool_messages.append(
                        ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call_id)
                    )
            else:
                tool_messages.append(
                    ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_call_id)
                )

        return tool_messages

    def _collect_tool_results(self, messages: list) -> str:
        """Collect all tool results from messages."""
        results = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                results.append(msg.content)
        return "\n\n".join(results) if results else "无搜索结果"


class BearAgent:
    """Risk Auditor - identifies vulnerabilities."""

    def __init__(self):
        self.tools = get_tools_for_agent("bear")
        self.llm_with_tools = get_llm(with_tools=True, tools=self.tools)
        self.llm_no_tools = get_llm(with_tools=False)
        self.tool_map = {t.name: t for t in self.tools}

    async def analyze(self, state: dict) -> dict:
        """Generate bear case analysis."""
        base_context = format_base_context(state)
        prompt = BEAR_PROMPT.format(
            base_context=base_context,
            bull_arguments=state.get("bull_notes", "尚无 Bull Case"),
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content=f"请对 {state['ticker']} 的 Bull Case 进行压力测试和反驳"
            ),
        ]

        # First call - may return tool calls
        response = await self.llm_with_tools.ainvoke(messages)

        # Handle tool calls if any (up to 3 iterations)
        for _ in range(3):
            if not hasattr(response, "tool_calls") or not response.tool_calls:
                break

            # Execute tools and create proper ToolMessage responses
            messages.append(response)
            tool_messages = await self._execute_tools_as_messages(response.tool_calls)
            messages.extend(tool_messages)

            # Get next response
            response = await self.llm_with_tools.ainvoke(messages)

        # If response still has tool_calls but no content, get a final summary
        if not response.content or response.content.strip() == "":
            tool_results = self._collect_tool_results(messages)
            summary_messages = [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=f"基于以下搜索结果，请对 {state['ticker']} 进行风险分析：\n\n{tool_results}"
                ),
            ]
            response = await self.llm_no_tools.ainvoke(summary_messages)

        return {
            "bear_notes": response.content,
            "messages": state.get("messages", [])
            + [{"role": "bear", "content": response.content}],
        }

    async def _execute_tools_as_messages(self, tool_calls: list) -> list[ToolMessage]:
        """Execute tool calls and return ToolMessage objects."""
        tool_messages = []

        for call in tool_calls:
            tool_name = call.get("name") or call.get("function", {}).get("name")
            tool_args = call.get("args") or call.get("function", {}).get("arguments", {})
            tool_call_id = call.get("id", f"call_{tool_name}")

            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {}

            tool = self.tool_map.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    tool_messages.append(
                        ToolMessage(content=str(result), tool_call_id=tool_call_id)
                    )
                except Exception as e:
                    tool_messages.append(
                        ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call_id)
                    )
            else:
                tool_messages.append(
                    ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_call_id)
                )

        return tool_messages

    def _collect_tool_results(self, messages: list) -> str:
        """Collect all tool results from messages."""
        results = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                results.append(msg.content)
        return "\n\n".join(results) if results else "无搜索结果"


class CIOAgent:
    """Portfolio CIO - synthesizes and decides."""

    def __init__(self):
        self.llm = get_llm()
        self.settings = get_settings()

    async def evaluate(self, state: dict) -> dict:
        """Evaluate debate and decide whether to continue or conclude."""
        base_context = format_base_context(state)

        prompt = CIO_PROMPT.format(
            base_context=base_context,
            ticker=state.get("ticker", "Unknown"),
            date=datetime.now().strftime("%Y-%m-%d"),
            bull_arguments=state.get("bull_notes", "尚无"),
            bear_arguments=state.get("bear_notes", "尚无"),
            round_count=state.get("round_count", 1),
            max_rounds=self.settings.max_debate_rounds,
        )

        # First, decide whether to continue
        should_continue = await self._should_continue(state)

        if should_continue and state.get("round_count", 1) < self.settings.max_debate_rounds:
            return {
                "next_step": "continue",
                "round_count": state.get("round_count", 1) + 1,
                "messages": state.get("messages", [])
                + [{"role": "cio", "content": "继续辩论，请双方深入分析..."}],
            }

        # Generate final memo
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="请生成最终投资决策备忘录"),
        ]

        response = await self.llm.ainvoke(messages)

        return {
            "next_step": "end",
            "decision_memo": response.content,
            "messages": state.get("messages", [])
            + [{"role": "cio", "content": response.content}],
        }

    async def _should_continue(self, state: dict) -> bool:
        """Determine if debate should continue based on information gain."""
        # Always run at least 2 rounds
        if state.get("round_count", 1) < 2:
            return True

        # Check max rounds
        if state.get("round_count", 1) >= self.settings.max_debate_rounds:
            return False

        # Use LLM to evaluate information gain
        eval_prompt = f"""评估当前辩论状态：

Bull Case:
{state.get('bull_notes', '无')}

Bear Case:
{state.get('bear_notes', '无')}

当前是第 {state.get('round_count', 1)} 轮辩论。

请判断：继续辩论是否能带来有价值的新信息？
回答 YES 或 NO，并简要说明原因。"""

        messages = [HumanMessage(content=eval_prompt)]
        response = await self.llm.ainvoke(messages)

        return "YES" in response.content.upper()


async def init_node(state: dict) -> dict:
    """Initialize analysis state."""
    return {
        "round_count": 1,
        "bull_notes": "",
        "bear_notes": "",
        "decision_memo": "",
        "next_step": "bull",
        "messages": [],
    }


async def bull_node(state: dict) -> dict:
    """Bull agent analysis node."""
    agent = BullAgent()
    return await agent.analyze(state)


async def bear_node(state: dict) -> dict:
    """Bear agent analysis node."""
    agent = BearAgent()
    return await agent.analyze(state)


async def cio_node(state: dict) -> dict:
    """CIO evaluation node."""
    agent = CIOAgent()
    return await agent.evaluate(state)


def route_after_cio(state: dict) -> Literal["bull", "end"]:
    """Determine next step after CIO evaluation."""
    if state.get("next_step") == "continue":
        return "bull"
    return "end"
