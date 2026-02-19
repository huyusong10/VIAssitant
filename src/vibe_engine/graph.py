"""LangGraph FSM construction for the Vibe Investment Engine.

Assembly strategy (incremental across sprints):
  S1 — START → expert_node → END          (single expert)
  S2 — fan-out N experts → fan-in         (expert swarm)
  S3 — + talent node                      (convergence)
  S4 — + planner node + conditional edges (control loop)
  S5 — three-phase pipeline               (full workflow)

S5 graph topology:

  START → fan_out → expert(s)  [fan-out via Send()]
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
            ▼           │           ▼
         fan_out        │          END
         (loop)         │
                        ▼
              ┌─────────┴─────────┐
              │                   │
         has next phase?     last phase?
              │                   │
              ▼                   ▼
           fan_out             reporter → END
           (next phase)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from vibe_engine.state import VibeState, ExpertInput
from vibe_engine.nodes.expert import expert_node
from vibe_engine.nodes.talent import talent_node
from vibe_engine.nodes.planner import planner_node
from vibe_engine.nodes.reporter import reporter_node
from vibe_engine.config import PHASE_ORDER


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
    """Conditional router after Planner decision (S5).

    Routes based on the Planner's decision:
    - "iterate" → back to fan_out for another round in the same phase
    - "proceed" → either fan_out (next phase) or reporter (last phase done)
    - "abort"   → END with abort_reason populated

    The phase transition itself is handled by the Planner node's state update.
    By the time we route, state["phase"] already reflects the new phase
    (if proceed was to a next phase) or remains at the last phase (if no
    next phase exists, meaning workflow is complete).

    Returns:
        The name of the next node to transition to.
    """
    decision = state.get("current_planner_decision")
    if decision is None:
        return END

    action = decision.get("decision", "abort")

    if action == "iterate":
        return "fan_out"

    elif action == "proceed":
        # Check if we've transitioned to a new phase or completed the workflow.
        # The planner_node already updated state["phase"] to the next phase
        # if one exists within target_phases. If no next phase, it didn't change
        # the phase, meaning we should generate the final report.
        current_phase = state.get("phase", "discovery")
        target_phases = state.get("target_phases", PHASE_ORDER)

        # If the current phase is the last target phase, workflow is done
        if current_phase == target_phases[-1]:
            return "reporter"

        # Otherwise, we've transitioned to a new phase — re-enter the loop
        return "fan_out"

    else:
        # "abort" → END
        return END


def fan_out_node(state: VibeState) -> dict:
    """Passthrough node that acts as the fan-out anchor.

    LangGraph requires conditional edges to originate from a node name
    (not directly from another conditional edge). This node serves as
    the re-entry point for both iterate loops and phase transitions.

    It does not modify state — the actual fan-out is driven by
    `route_to_experts` via conditional edges from this node.
    """
    return {}


def build_graph():
    """Build and compile the Vibe Investment FSM.

    S5 implementation — three-phase pipeline:
      fan_out → expert(s) [fan-out via Send]
                     → talent [convergence]
                         → planner [control valve]
                             → iterate  → fan_out (loop)
                             → proceed  → fan_out (next phase) or reporter (done)
                             → abort    → END

    Supports:
    - Multi-round iteration within each phase (discovery, targeting, validation)
    - Phase transitions (discovery → targeting → validation)
    - Final report generation after all phases complete
    - Abort at any point with partial results

    Returns:
        A compiled LangGraph graph ready for .invoke() / .stream().
    """
    graph = StateGraph(VibeState)

    # ── Nodes ──
    graph.add_node("fan_out", fan_out_node)
    graph.add_node("expert", expert_node)
    graph.add_node("talent", talent_node)
    graph.add_node("planner", planner_node)
    graph.add_node("reporter", reporter_node)

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

    # reporter → END (final report generated)
    graph.add_edge("reporter", END)

    return graph.compile()
