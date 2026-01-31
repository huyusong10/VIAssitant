"""LangGraph state graph for investment analysis debate."""

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.nodes import (
    bear_node,
    bull_node,
    cio_node,
    init_node,
    route_after_cio,
)


class AgentState(TypedDict):
    """State shared across all agents in the graph."""

    # Input from user
    user_vibe: str
    ticker: str

    # Debate state
    round_count: int
    bull_notes: str
    bear_notes: str

    # Output
    decision_memo: str
    next_step: str

    # Message history for UI display
    messages: Annotated[list[dict[str, Any]], operator.add]


def create_investment_graph() -> StateGraph:
    """Create the investment analysis state graph.

    Flow:
    1. init -> bull: Initialize and start with Bull analysis
    2. bull -> bear: Bull presents case, Bear responds
    3. bear -> cio: Bear presents counter, CIO evaluates
    4. cio -> bull OR end: Continue debate or finalize

    Returns:
        Compiled StateGraph ready to execute
    """
    # Create the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("init", init_node)
    graph.add_node("bull", bull_node)
    graph.add_node("bear", bear_node)
    graph.add_node("cio", cio_node)

    # Define edges
    graph.set_entry_point("init")
    graph.add_edge("init", "bull")
    graph.add_edge("bull", "bear")
    graph.add_edge("bear", "cio")

    # Conditional edge from CIO
    graph.add_conditional_edges(
        "cio",
        route_after_cio,
        {
            "bull": "bull",
            "end": END,
        },
    )

    return graph.compile()


async def run_investment_analysis(
    ticker: str,
    user_vibe: str,
    callback=None,
) -> dict:
    """Run a complete investment analysis.

    Args:
        ticker: Stock ticker symbol to analyze
        user_vibe: User's initial intuition/thesis
        callback: Optional async callback for streaming updates
            callback(agent: str, content: str)

    Returns:
        Final state including decision_memo
    """
    graph = create_investment_graph()

    initial_state = {
        "user_vibe": user_vibe,
        "ticker": ticker.upper(),
        "round_count": 0,
        "bull_notes": "",
        "bear_notes": "",
        "decision_memo": "",
        "next_step": "",
        "messages": [],
    }

    # Stream through the graph
    final_state = None

    async for state in graph.astream(initial_state):
        final_state = state

        # Call callback with updates
        if callback:
            for node_name, node_state in state.items():
                if isinstance(node_state, dict):
                    if "messages" in node_state:
                        for msg in node_state.get("messages", []):
                            if isinstance(msg, dict):
                                await callback(msg.get("role", "system"), msg.get("content", ""))

    # Get the final merged state
    if final_state:
        # The final state from astream is a dict with node names as keys
        # We need to merge them
        merged_state = initial_state.copy()
        for node_name, node_state in final_state.items():
            if isinstance(node_state, dict):
                merged_state.update(node_state)
        return merged_state

    return initial_state


class SimpleDebateRunner:
    """Simplified debate runner for testing and CLI usage."""

    def __init__(self):
        self.graph = create_investment_graph()

    async def run(self, ticker: str, user_vibe: str) -> dict:
        """Run analysis and return results."""
        initial_state = {
            "user_vibe": user_vibe,
            "ticker": ticker.upper(),
            "round_count": 0,
            "bull_notes": "",
            "bear_notes": "",
            "decision_memo": "",
            "next_step": "",
            "messages": [],
        }

        result = await self.graph.ainvoke(initial_state)
        return result

    async def run_with_logging(self, ticker: str, user_vibe: str) -> dict:
        """Run analysis with console logging."""
        print(f"\n{'='*60}")
        print(f"Analyzing: {ticker}")
        print(f"User Vibe: {user_vibe}")
        print(f"{'='*60}\n")

        initial_state = {
            "user_vibe": user_vibe,
            "ticker": ticker.upper(),
            "round_count": 0,
            "bull_notes": "",
            "bear_notes": "",
            "decision_memo": "",
            "next_step": "",
            "messages": [],
        }

        async for state in self.graph.astream(initial_state):
            for node_name, node_state in state.items():
                if isinstance(node_state, dict) and "messages" in node_state:
                    for msg in node_state.get("messages", []):
                        if isinstance(msg, dict):
                            role = msg.get("role", "system")
                            content = msg.get("content", "")
                            print(f"\n[{role.upper()}]")
                            print("-" * 40)
                            print(content[:500] + "..." if len(content) > 500 else content)

        # Get final result
        result = await self.graph.ainvoke(initial_state)
        return result
