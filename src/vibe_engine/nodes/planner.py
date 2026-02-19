"""Planner node — control valve and planning hub for the FSM.

Architecture notes (post-refactor — Phase A correction):
- The Planner is now the ENTRY POINT of each iteration cycle.
  The graph topology is: START → planner → fan_out → expert(s) → talent → planner (loop)
- On the first round of each phase (no Talent input yet), the Planner:
    1. Evaluates the current Vibe
    2. Selects the initial batch of experts
    3. Returns decision="dispatch" to trigger fan-out
- On subsequent rounds (after Talent convergence), the Planner:
    1. Evaluates sufficiency based on Talent's synthesis
    2. Decides proceed / iterate / abort
    3. On iterate: mutates Vibe, selects new experts → routes to "dispatch"
    4. On proceed + next phase exists: transitions phase, selects experts → "dispatch"
    5. On proceed + last phase: routes to "report"
    6. On abort: routes to END
- Uses DeepSeek **Chat** model (fast routing, structured extraction) per arch constraint.
- Round limits are enforced locally: even if the LLM says "iterate", the Planner
  overrides to "abort" when `max_rounds` for the current phase is reached.
"""

import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from vibe_engine.state import VibeState, PlannerDecision
from vibe_engine.prompts import (
    get_planner_system_prompt,
    get_planner_user_prompt,
    get_planner_initial_system_prompt,
    get_planner_initial_user_prompt,
)
from vibe_engine.config import (
    DEEPSEEK_BASE_URL,
    MODEL_CHAT,
    PHASE_CONFIGS,
    PHASE_ORDER,
    EXPERT_DIMENSIONS,
)


def _get_openai_client() -> OpenAI:
    """Return a raw OpenAI client pointed at DeepSeek."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example → .env and add your API key."
        )
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def _extract_json(raw: str) -> dict:
    """Extract a JSON object from the LLM response.

    Tries multiple strategies:
    1. Direct JSON parse of the full response
    2. Extract from ```json ... ``` code block
    3. Find first { ... } block via regex
    """
    # Strategy 1: direct parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: Markdown code block
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: first { ... } block
    brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Complete failure — return a safe default that forces abort
    return {
        "sufficiency_score": 0,
        "decision": "abort",
        "reasoning": f"无法解析 Planner 输出。原始内容: {raw[:200]}",
        "vibe_next": "",
        "selected_experts": [],
    }


def _validate_experts(raw_experts: list, phase: str) -> list[int]:
    """Validate and clamp expert selection to phase bounds."""
    phase_config = PHASE_CONFIGS.get(phase, PHASE_CONFIGS["discovery"])
    expert_min = phase_config["expert_count_min"]
    expert_max = phase_config["expert_count_max"]
    valid_expert_ids = {d["id"] for d in EXPERT_DIMENSIONS}

    # Filter to valid IDs, deduplicate
    selected = []
    seen = set()
    for eid in (raw_experts or []):
        if isinstance(eid, str):
            try:
                eid = int(eid)
            except ValueError:
                continue
        if isinstance(eid, int) and eid in valid_expert_ids and eid not in seen:
            seen.add(eid)
            selected.append(eid)

    # Clamp to phase bounds
    if len(selected) < expert_min:
        remaining = [eid for eid in sorted(valid_expert_ids) if eid not in seen]
        while len(selected) < expert_min and remaining:
            selected.append(remaining.pop(0))
    elif len(selected) > expert_max:
        selected = selected[:expert_max]

    return selected


def _validate_and_clamp(parsed: dict, phase: str, round_num: int) -> PlannerDecision:
    """Validate and sanitize the raw parsed JSON into a well-typed PlannerDecision.

    Enforces:
    - sufficiency_score in [0, 10]
    - decision in {"proceed", "iterate", "abort"}
    - selected_experts are valid IDs (1-10) and within phase count bounds
    - Round limit override: if round_num >= max_rounds, force abort
    """
    phase_config = PHASE_CONFIGS.get(phase, PHASE_CONFIGS["discovery"])
    max_rounds = phase_config["max_rounds"]

    # --- sufficiency_score ---
    score = parsed.get("sufficiency_score", 5)
    if isinstance(score, str):
        try:
            score = int(score)
        except ValueError:
            score = 5
    score = max(0, min(10, score))

    # --- decision ---
    decision = parsed.get("decision", "iterate")
    if decision not in ("proceed", "iterate", "abort"):
        decision = "iterate"

    # --- Round limit enforcement ---
    if decision == "iterate" and round_num >= max_rounds:
        decision = "abort"

    # --- reasoning ---
    reasoning = parsed.get("reasoning", "")

    # --- vibe_next ---
    vibe_next = parsed.get("vibe_next", "") if decision == "iterate" else ""

    # --- selected_experts ---
    # For proceed, use next phase bounds for expert count validation
    expert_phase = phase
    if decision == "proceed":
        next_phase = _get_next_phase_in(phase, PHASE_ORDER)
        if next_phase:
            expert_phase = next_phase

    selected = _validate_experts(parsed.get("selected_experts", []), expert_phase)

    return PlannerDecision(
        sufficiency_score=score,
        decision=decision,
        reasoning=reasoning,
        vibe_next=vibe_next,
        selected_experts=selected,
    )


def _get_next_phase_in(current_phase: str, target_phases: list[str]) -> str | None:
    """Return the next phase within the target phases list, or None if last."""
    try:
        idx = target_phases.index(current_phase)
        if idx + 1 < len(target_phases):
            return target_phases[idx + 1]
    except ValueError:
        pass
    return None


def _planner_initial_round(state: VibeState) -> dict:
    """Handle the first round of a phase — no Talent input yet.

    The Planner evaluates the Vibe and selects the initial batch of experts.
    Always returns routing_action="dispatch".
    """
    phase = state.get("phase", "discovery")
    vibe = state.get("vibe", "")

    system_prompt = get_planner_initial_system_prompt(phase)
    user_prompt = get_planner_initial_user_prompt(vibe, phase)

    client = _get_openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=MODEL_CHAT,
        messages=messages,
    )
    raw_content = response.choices[0].message.content or ""

    parsed = _extract_json(raw_content)
    selected = _validate_experts(parsed.get("selected_experts", []), phase)
    reasoning = parsed.get("reasoning", "首轮规划")

    decision = PlannerDecision(
        sufficiency_score=0,
        decision="iterate",  # Semantically: "we need to gather info"
        reasoning=reasoning,
        vibe_next="",
        selected_experts=selected,
    )

    return {
        "planner_decisions": [decision],
        "current_planner_decision": decision,
        "selected_experts": selected,
        "routing_action": "dispatch",
    }


def _planner_evaluate_round(state: VibeState) -> dict:
    """Handle subsequent rounds — evaluate Talent result and decide next action.

    Returns routing_action: "dispatch" | "report" | "abort"
    """
    phase = state.get("phase", "discovery")
    round_num = state.get("round", 1)
    vibe = state.get("vibe", "")
    vibe_original = state.get("vibe_original", vibe)
    talent_summary = state.get("current_talent_summary")
    target_phases = state.get("target_phases", PHASE_ORDER)

    phase_config = PHASE_CONFIGS.get(phase, PHASE_CONFIGS["discovery"])
    max_rounds = phase_config["max_rounds"]

    # Build prompts
    system_prompt = get_planner_system_prompt(phase, round_num, max_rounds)
    user_prompt = get_planner_user_prompt(
        talent_summary=talent_summary,
        vibe_current=vibe,
        vibe_original=vibe_original,
        phase=phase,
        round_num=round_num,
        max_rounds=max_rounds,
    )

    # Call DeepSeek Chat (fast model)
    client = _get_openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=MODEL_CHAT,
        messages=messages,
    )
    raw_content = response.choices[0].message.content or ""

    # Parse and validate
    parsed = _extract_json(raw_content)
    decision = _validate_and_clamp(parsed, phase, round_num)

    # Build state update
    update: dict = {
        "planner_decisions": [decision],
        "current_planner_decision": decision,
    }

    if decision["decision"] == "iterate":
        # Vibe mutation + dispatch next round
        new_vibe = decision["vibe_next"] or vibe
        vibe_history = list(state.get("vibe_history", [vibe]))
        vibe_history.append(new_vibe)
        update["vibe"] = new_vibe
        update["vibe_history"] = vibe_history
        update["selected_experts"] = decision["selected_experts"]
        update["round"] = round_num + 1
        update["routing_action"] = "dispatch"

    elif decision["decision"] == "proceed":
        next_phase = _get_next_phase_in(phase, target_phases)
        if next_phase:
            # Transition to next phase — Planner selects experts for it
            update["phase"] = next_phase
            update["round"] = 1
            update["selected_experts"] = decision["selected_experts"]
            update["current_talent_summary"] = None  # Reset for new phase
            update["routing_action"] = "dispatch"
        else:
            # Last phase completed — route to reporter
            update["routing_action"] = "report"

    elif decision["decision"] == "abort":
        abort_reason = (
            f"阶段 [{phase}] 第 {round_num}/{max_rounds} 轮后终止。"
            f"充分度评分: {decision['sufficiency_score']}/10。"
            f"原因: {decision['reasoning']}"
        )
        update["abort_reason"] = abort_reason
        update["routing_action"] = "abort"

    return update


def planner_node(state: VibeState) -> dict:
    """LangGraph node function for the Planner (Phase A refactored).

    The Planner is the ENTRY POINT of each cycle. It runs at the start
    of every iteration, not after Talent.

    Two modes:
    1. Initial round (no Talent summary): select experts based on Vibe
    2. Evaluation round (has Talent summary): assess sufficiency → decide

    Returns:
        A partial VibeState update dict including routing_action.
    """
    has_talent = state.get("current_talent_summary") is not None

    if not has_talent:
        return _planner_initial_round(state)
    else:
        return _planner_evaluate_round(state)
