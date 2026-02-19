"""LangGraph FSM construction for the Vibe Investment Engine.

Assembly strategy (incremental across sprints):
  S1 — START → expert_node → END          (single expert)
  S2 — fan-out N experts → fan-in         (expert swarm)
  S3 — + talent node                      (convergence)
  S4 — + planner node + conditional edges (control loop)
  S5 — three-phase pipeline               (full workflow)

Phase A correction — Planner-first topology:

  START → planner → conditional_edges
                      ├── "dispatch" → fan_out → expert(s) → talent → planner (loop)
                      ├── "report"  → reporter → END
                      └── "abort"   → END

  The Planner is the ENTRY POINT of each cycle:
  - First round: Planner receives Vibe, selects experts → dispatch
  - After Talent: Planner evaluates sufficiency → iterate/proceed/abort
  - Iterate: Planner mutates Vibe, selects experts → dispatch (same phase)
  - Proceed + next phase: Planner transitions phase → dispatch (new phase)
  - Proceed + last phase: → reporter → END
  - Abort: → END
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from vibe_engine.state import VibeState, ExpertInput
from vibe_engine.nodes.expert import expert_node
from vibe_engine.nodes.talent import talent_node
from vibe_engine.nodes.planner import planner_node
from vibe_engine.nodes.reporter import reporter_node


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

    Routes based on the Planner's routing_action:
    - "dispatch" → fan_out (send experts for analysis)
    - "report"   → reporter (generate final report)
    - "abort"    → END

    Returns:
        The name of the next node to transition to.
    """
    action = state.get("routing_action", "abort")

    if action == "dispatch":
        return "fan_out"
    elif action == "report":
        return "reporter"
    else:
        # "abort" or unknown → END
        return END


def fan_out_node(state: VibeState) -> dict:
    """Passthrough node that acts as the fan-out anchor.

    LangGraph requires conditional edges to originate from a node name
    (not directly from another conditional edge). This node serves as
    the dispatch point for Send() to parallel expert nodes.

    It does not modify state — the actual fan-out is driven by
    `route_to_experts` via conditional edges from this node.
    """
    return {}


def build_graph():
    """Build and compile the Vibe Investment FSM.

    Phase A corrected topology — Planner-first:
      START → planner → [dispatch]  → fan_out → expert(s) → talent → planner (loop)
                       → [report]   → reporter → END
                       → [abort]    → END

    Supports:
    - Planner as the entry point and decision hub for each cycle
    - First-round intelligent expert selection based on Vibe
    - Multi-round iteration within each phase (discovery, targeting, validation)
    - Phase transitions (discovery → targeting → validation)
    - Final report generation after all phases complete
    - Abort at any point with partial results

    Returns:
        A compiled LangGraph graph ready for .invoke() / .stream().
    """
    graph = StateGraph(VibeState)

    # ── Nodes ──
    graph.add_node("planner", planner_node)
    graph.add_node("fan_out", fan_out_node)
    graph.add_node("expert", expert_node)
    graph.add_node("talent", talent_node)
    graph.add_node("reporter", reporter_node)

    # ── Edges ──
    # START → planner (Planner is the entry point)
    graph.add_edge(START, "planner")

    # planner → conditional routing (dispatch/report/abort)
    graph.add_conditional_edges("planner", route_after_planner)

    # fan_out → conditional dispatch to parallel expert nodes
    graph.add_conditional_edges("fan_out", route_to_experts)

    # expert → talent (fan-in: all expert results merge via reducer)
    graph.add_edge("expert", "talent")

    # talent → planner (back to Planner for evaluation)
    graph.add_edge("talent", "planner")

    # reporter → END (final report generated)
    graph.add_edge("reporter", END)

    return graph.compile()
