"""LangGraph FSM construction for the Vibe Investment Engine.

Assembly strategy (incremental across sprints):
  S1 — START → expert_node → END          (single expert)
  S2 — fan-out N experts → fan-in         (expert swarm)
  S3 — + talent node                      (convergence)
  S4 — + planner node + conditional edges (control loop)
  S5 — three-phase pipeline               (full workflow)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from vibe_engine.state import VibeState, ExpertInput
from vibe_engine.nodes.expert import expert_node
from vibe_engine.nodes.talent import talent_node


def route_to_experts(state: VibeState) -> list[Send]:
    """Fan-out router: dispatch Send() to each selected expert.

    Each Send() creates an independent sub-invocation of the expert_node
    with its own ExpertInput (containing expert_id + shared vibe/phase/round).
    LangGraph guarantees parallel execution and context isolation.

    Returns:
        A list of Send objects, one per selected expert.
    """
    selected = state.get("selected_experts", [2])  # default to expert 2
    vibe = state.get("vibe", "")
    phase = state.get("phase", "discovery")
    round_num = state.get("round", 1)

    sends = []
    for expert_id in selected:
        sends.append(
            Send(
                "expert",
                {
                    "expert_id": expert_id,
                    "vibe": vibe,
                    "phase": phase,
                    "round": round_num,
                },
            )
        )
    return sends


def build_graph():
    """Build and compile the Vibe Investment FSM.

    S3 implementation: START → fan-out(experts) → fan-in → talent → END

    The fan-out is driven by `route_to_experts`, which reads
    `selected_experts` from the state and dispatches one Send()
    per expert. LangGraph handles parallel execution and
    fan-in via the expert_results reducer (list append).

    After all experts complete, the Talent convergence node
    cross-compares their results and surfaces emergent insights.

    Returns:
        A compiled LangGraph graph ready for .invoke() / .stream().
    """
    graph = StateGraph(VibeState)

    # Expert node — receives ExpertInput via Send().
    # The factory pattern is replaced by a single node function
    # that reads expert_id from its input. LangGraph fan-out
    # ensures each invocation is isolated.
    graph.add_node("expert", expert_node)

    # Talent node — convergence: cross-compare expert results (S3)
    graph.add_node("talent", talent_node)

    # Fan-out: START → conditional edges → parallel expert nodes
    graph.add_conditional_edges(START, route_to_experts)

    # Fan-in: expert → talent (all expert results auto-merge via reducer)
    graph.add_edge("expert", "talent")

    # Talent → END (S3; in S4+ this will route to Planner)
    graph.add_edge("talent", END)

    return graph.compile()
