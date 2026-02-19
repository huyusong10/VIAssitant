"""Planner node — control valve for the FSM.

Architecture notes:
- The Planner is the decision-making hub of the workflow.
  It evaluates information sufficiency, decides whether to proceed / iterate / abort,
  and — when iterating — generates a mutated Vibe that incorporates the Talent's
  emergent insights.
- Uses DeepSeek **Chat** model (fast routing, structured extraction) per arch constraint.
- Round limits are enforced locally: even if the LLM says "iterate", the Planner
  overrides to "abort" when `max_rounds` for the current phase is reached.
- Expert selection is delegated to the LLM but validated against [1, 10] bounds
  and clamped to the phase's allowed expert count range.
"""

import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from vibe_engine.state import VibeState, PlannerDecision
from vibe_engine.prompts import get_planner_system_prompt, get_planner_user_prompt
from vibe_engine.config import (
    DEEPSEEK_BASE_URL,
    MODEL_CHAT,
    PHASE_CONFIGS,
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
    expert_min = phase_config["expert_count_min"]
    expert_max = phase_config["expert_count_max"]
    valid_expert_ids = {d["id"] for d in EXPERT_DIMENSIONS}

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

    # --- S4.4: Round limit enforcement ---
    # If we have already reached max_rounds and the LLM still wants to iterate,
    # override to abort. The Planner's own reasoning is preserved.
    if decision == "iterate" and round_num >= max_rounds:
        decision = "abort"

    # --- reasoning ---
    reasoning = parsed.get("reasoning", "")

    # --- vibe_next ---
    vibe_next = parsed.get("vibe_next", "") if decision == "iterate" else ""

    # --- selected_experts ---
    raw_experts = parsed.get("selected_experts", [])
    if not isinstance(raw_experts, list):
        raw_experts = []

    # Filter to valid IDs, deduplicate
    selected = []
    seen = set()
    for eid in raw_experts:
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
        # Pad with random unseen experts
        remaining = [eid for eid in sorted(valid_expert_ids) if eid not in seen]
        while len(selected) < expert_min and remaining:
            selected.append(remaining.pop(0))
    elif len(selected) > expert_max:
        selected = selected[:expert_max]

    return PlannerDecision(
        sufficiency_score=score,
        decision=decision,
        reasoning=reasoning,
        vibe_next=vibe_next,
        selected_experts=selected,
    )


def planner_node(state: VibeState) -> dict:
    """LangGraph node function for the Planner control valve (S4).

    Receives the current VibeState (including talent summary),
    calls DeepSeek Chat for a fast routing decision, and returns
    a state update that drives the conditional routing logic.

    Core responsibilities:
    1. Evaluate information sufficiency based on Talent's synthesis
    2. Generate Vibe mutation (vibe_next) when iterating
    3. Select experts for the next round
    4. Enforce round limits per phase (auto-abort)

    Returns:
        A partial VibeState update dict with:
        - planner_decisions: appended decision record
        - current_planner_decision: latest decision (for routing)
        - vibe / vibe_history: updated on iterate
        - selected_experts: for next round's fan-out
        - round: incremented on iterate
        - abort_reason: populated on abort
    """
    phase = state.get("phase", "discovery")
    round_num = state.get("round", 1)
    vibe = state.get("vibe", "")
    vibe_original = state.get("vibe_original", vibe)
    talent_summary = state.get("current_talent_summary")

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
        # Vibe mutation: replace current vibe with the evolved version
        new_vibe = decision["vibe_next"] or vibe
        vibe_history = list(state.get("vibe_history", [vibe]))
        vibe_history.append(new_vibe)
        update["vibe"] = new_vibe
        update["vibe_history"] = vibe_history
        update["selected_experts"] = decision["selected_experts"]
        update["round"] = round_num + 1
        # Clear expert_results for the next round so Talent sees only fresh results
        update["expert_results"] = []

    elif decision["decision"] == "abort":
        abort_reason = (
            f"阶段 [{phase}] 第 {round_num}/{max_rounds} 轮后终止。"
            f"充分度评分: {decision['sufficiency_score']}/10。"
            f"原因: {decision['reasoning']}"
        )
        update["abort_reason"] = abort_reason

    elif decision["decision"] == "proceed":
        update["selected_experts"] = decision["selected_experts"]

    return update
