"""Global state definition for the Vibe Investment Engine FSM."""

from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class ExpertInput(TypedDict):
    """Per-expert input dispatched via Send() during fan-out.

    Each expert receives its own ExpertInput with isolated context.
    This ensures expert nodes do not share message history.
    """
    expert_id: int
    vibe: str
    phase: str
    round: int


class ExpertResult(TypedDict):
    """Structured output from a single expert node."""
    expert_id: int
    expert_name: str
    phase: str                # Which phase produced this result
    round_num: int            # Which round produced this result
    logic_chain: str          # 逻辑链条
    conclusion: str           # 精简结论
    risk_points: str          # 核心风险点
    think_content: str        # 完整思考过程 (<think> content)
    # Phase-specific optional fields
    targets: list[str]        # 标的锁定阶段: 具体标的
    data_logic_chain: str     # 逻辑验证阶段: 数据推导链


class TalentSummary(TypedDict):
    """Structured output from the Talent convergence node."""
    core_contradictions: str  # 核心矛盾点
    emergent_hypothesis: str  # 涌现假设
    synthesis_score: int      # 综合评分 (0-10)
    phase: str                # 产生该总结时的工作流阶段
    round_num: int            # 产生该总结时的轮数
    think_content: str        # 完整思考过程 (reasoning chain)


class PlannerDecision(TypedDict):
    """Structured output from the Planner control node."""
    sufficiency_score: int    # 信息充分度评分 (0-10)
    decision: str             # "proceed" | "iterate" | "abort"
    reasoning: str            # 决策依据
    vibe_next: str            # 变异后的 Vibe (仅 iterate 时生成)
    selected_experts: list[int]  # 下一轮选取的专家 ID 列表


class VibeState(TypedDict):
    """
    Global FSM state for the Vibe Investment Engine.

    Design notes:
    - `messages` uses LangGraph's add_messages reducer for append-only updates.
    - All other fields use last-write-wins semantics (default for TypedDict).
    - `session_id` is reserved for future multi-session support (Phase 2+).
    - The CLI layer reads from this state but never writes back into the graph.
    """

    # --- Core Vibe ---
    vibe: str                        # Current active Vibe (mutates each iterate)
    vibe_original: str               # Immutable original Vibe_0 from user
    vibe_history: list[str]          # Chronological list of all Vibe versions

    # --- Workflow Control ---
    phase: str                       # Current phase: "discovery" | "targeting" | "validation"
    round: int                       # Current round number within the phase
    phase_round: dict[str, int]      # Per-phase round counters {phase: round}

    # --- Expert Outputs ---
    expert_results: Annotated[list[ExpertResult], lambda a, b: a + b]
    # ^ Annotated with a custom reducer so fan-in parallel writes append correctly.
    # Expert results include phase/round_num for filtering by Talent.

    # --- Talent & Planner Outputs ---
    talent_summaries: Annotated[list[TalentSummary], lambda a, b: a + b]
    planner_decisions: Annotated[list[PlannerDecision], lambda a, b: a + b]
    current_talent_summary: TalentSummary | None
    current_planner_decision: PlannerDecision | None

    # --- Final Output ---
    final_report: str | None         # Generated after all phases complete

    # --- Internal / Diagnostics ---
    messages: Annotated[list[Any], add_messages]  # Reserved for LangGraph compat
    selected_experts: list[int]      # Expert IDs selected for the current round
    abort_reason: str | None         # Populated on abort decision

    # --- Routing ---
    routing_action: str | None       # Planner's routing signal: "dispatch" | "report" | "abort"

    # --- Mode Control ---
    target_phases: list[str]         # Phases to run (e.g. ["discovery","targeting","validation"])

    # --- Future Extensions (Phase 2+) ---
    session_id: str | None           # Reserved for multi-session support
