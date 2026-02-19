"""LangGraph FSM construction for the Vibe Investment Engine.

Assembly strategy (incremental across sprints):
  S1 — START → expert_node → END          (single expert)
  S2 — fan-out N experts → fan-in         (expert swarm)
  S3 — + talent node                      (convergence)
  S4 — + planner node + conditional edges (control loop)
  S5 — three-phase pipeline               (full workflow)
"""

from langgraph.graph import StateGraph, START, END
from vibe_engine.state import VibeState
from vibe_engine.nodes.expert import make_expert_node


# Default expert to use for the S1 single-expert graph
_DEFAULT_EXPERT_ID = 2  # 技术布道者 — good general-purpose dimension


def build_graph(expert_id: int = _DEFAULT_EXPERT_ID):
    """Build and compile the Vibe Investment FSM.

    S1 implementation: START → expert_node → END

    Args:
        expert_id: Which expert dimension to use (1-10). Defaults to 2.

    Returns:
        A compiled LangGraph graph ready for .invoke() / .stream().
    """
    graph = StateGraph(VibeState)

    expert_node = make_expert_node(expert_id)
    graph.add_node("expert", expert_node)

    graph.add_edge(START, "expert")
    graph.add_edge("expert", END)

    return graph.compile()
