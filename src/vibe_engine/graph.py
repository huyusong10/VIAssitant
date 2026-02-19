"""LangGraph FSM construction for the Vibe Investment Engine.

Assembly strategy (incremental across sprints):
  S1 — START → expert_node → END          (single expert)
  S2 — fan-out N experts → fan-in         (expert swarm)
  S3 — + talent node                      (convergence)
  S4 — + planner node + conditional edges (control loop)
  S5 — three-phase pipeline               (full workflow)

S4 graph topology:

  START ─── route_to_experts ───→ expert(s)  [fan-out via Send()]
                                     │
                                     ▼
                                   talent    [convergence]
                                     │
                                     ▼
                                  planner    [control valve]
                                     │
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                     [iterate]   [proceed]    [abort]
                         │           │           │
                         ▼           ▼           ▼
              route_to_experts      END         END
              (loop back)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from vibe_engine.state import VibeState, ExpertInput
from vibe_engine.nodes.expert import expert_node
from vibe_engine.nodes.talent import talent_node
from vibe_engine.nodes.planner import planner_node


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


def route_after_planner(state: VibeState) -> str:
    """Conditional router after Planner decision.

    Routes based on the Planner's decision:
    - "proceed" → END (in S5+ this will advance to the next phase)
    - "iterate" → back to expert fan-out for another round
    - "abort"   → END with abort_reason populated

    Returns:
        The name of the next node to transition to.
    """
    decision = state.get("current_planner_decision")
    if decision is None:
        return END

    action = decision.get("decision", "abort")

    if action == "iterate":
        return "fan_out"
    else:
        # Both "proceed" and "abort" lead to END in S4.
        # In S5+, "proceed" will transition to the next phase.
        return END


def fan_out_node(state: VibeState) -> dict:
    """Dummy passthrough node that acts as the fan-out anchor.

    LangGraph requires conditional edges to originate from a node name
    (not directly from another conditional edge). This node serves as
    the re-entry point for the iterate loop.

    It does not modify state — the actual fan-out is driven by
    `route_to_experts` via conditional edges from this node.
    """
    return {}


def build_graph():
    """Build and compile the Vibe Investment FSM.

    S4 implementation:
      fan_out → expert(s) [fan-out via Send]
                     → talent [convergence]
                         → planner [control valve]
                             → conditional: iterate → fan_out (loop)
                                            proceed → END
                                            abort   → END

    The fan-out is driven by `route_to_experts`, which reads
    `selected_experts` from the state and dispatches one Send()
    per expert. LangGraph handles parallel execution and
    fan-in via the expert_results reducer (list append).

    After all experts complete, the Talent convergence node
    cross-compares their results and surfaces emergent insights.

    The Planner then evaluates sufficiency, decides the next action,
    and conditionally loops back or terminates.

    Returns:
        A compiled LangGraph graph ready for .invoke() / .stream().
    """
    graph = StateGraph(VibeState)

    # ── Nodes ──
    # Fan-out anchor — passthrough that triggers conditional expert dispatch
    graph.add_node("fan_out", fan_out_node)

    # Expert node — receives ExpertInput via Send()
    graph.add_node("expert", expert_node)

    # Talent node — convergence: cross-compare expert results
    graph.add_node("talent", talent_node)

    # Planner node — control valve: sufficiency evaluation + routing
    graph.add_node("planner", planner_node)

    # ── Edges ──
    # START → fan_out (entry point)
    graph.add_edge(START, "fan_out")

    # fan_out → conditional dispatch to parallel expert nodes
    graph.add_conditional_edges("fan_out", route_to_experts)

    # expert → talent (fan-in: all expert results merge via reducer)
    graph.add_edge("expert", "talent")

    # talent → planner
    graph.add_edge("talent", "planner")

    # planner → conditional routing (iterate/proceed/abort)
    graph.add_conditional_edges("planner", route_after_planner)

    return graph.compile()
