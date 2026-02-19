"""Talent node — convergence and emergence from expert outputs.

Architecture notes:
- The Talent node receives all expert_results from the fan-in stage,
  performs cross-comparison, and surfaces emergent insights.
- Uses DeepSeek Reasoner for deep reasoning (per architecture constraint).
- The role prompt dynamically switches based on the current workflow phase:
    * discovery  → strategist  (战略家: extract core contradictions, emerge new hypotheses)
    * targeting  → stock_picker (选股手: evaluate whether targets align with original Vibe)
    * validation → auditor     (量化审计: cross-verify data logic chains)
- Think content (reasoning_content) is captured via the raw OpenAI client,
  mirroring the approach used in expert.py.
"""

import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from vibe_engine.state import VibeState, TalentSummary
from vibe_engine.prompts import get_talent_system_prompt, get_talent_user_prompt
from vibe_engine.config import DEEPSEEK_BASE_URL, MODEL_REASONER, PHASE_CONFIGS


def _get_openai_client() -> OpenAI:
    """Return a raw OpenAI client pointed at DeepSeek."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example → .env and add your API key."
        )
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def _parse_talent_output(raw: str) -> dict:
    """Parse the structured sections from Talent output.

    Expected sections:
    - ### 核心矛盾点
    - ### 涌现假设
    - ### 综合评分

    Returns a dict with keys: core_contradictions, emergent_hypothesis, synthesis_score.
    """
    sections = {
        "core_contradictions": "",
        "emergent_hypothesis": "",
        "synthesis_score": 5,  # default middle score
    }

    patterns = [
        ("core_contradictions", r"###\s*核心矛盾点\s*\n(.*?)(?=###|\Z)"),
        ("emergent_hypothesis", r"###\s*涌现假设\s*\n(.*?)(?=###|\Z)"),
    ]

    for key, pattern in patterns:
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            sections[key] = match.group(1).strip()

    # Extract score: look for pattern like "评分：X/10" or "评分: X/10" or just "X/10"
    score_match = re.search(r"评分[：:]\s*(\d+)\s*/\s*10", raw)
    if score_match:
        sections["synthesis_score"] = int(score_match.group(1))
    else:
        # Fallback: any digit/10 pattern in the score section
        score_section_match = re.search(
            r"###\s*综合评分\s*\n(.*?)(?=###|\Z)", raw, re.DOTALL
        )
        if score_section_match:
            score_text = score_section_match.group(1)
            digit_match = re.search(r"(\d+)\s*/\s*10", score_text)
            if digit_match:
                sections["synthesis_score"] = int(digit_match.group(1))

    # Fallback: if nothing parsed, dump everything into core_contradictions
    if not sections["core_contradictions"] and not sections["emergent_hypothesis"]:
        sections["core_contradictions"] = raw.strip()

    return sections


def talent_node(state: VibeState) -> dict:
    """LangGraph node function for Talent convergence (S3).

    Cross-compares all expert results from the current round,
    surfaces emergent insights, and provides a synthesis score
    to guide the Planner's sufficiency evaluation.

    The role prompt is dynamically selected based on the current phase:
    - discovery  → strategist
    - targeting  → stock_picker
    - validation → auditor

    Returns:
        A partial VibeState update dict with talent_summaries,
        current_talent_summary, and think content.
    """
    phase = state.get("phase", "discovery")
    round_num = state.get("round", 1)

    # Filter expert_results to only the current round's results
    all_results = state.get("expert_results", [])
    expert_results = [
        r for r in all_results
        if r.get("phase") == phase and r.get("round_num") == round_num
    ]

    # Determine Talent role from phase configuration
    phase_config = PHASE_CONFIGS.get(phase, PHASE_CONFIGS["discovery"])
    talent_role = phase_config["talent_role"]

    # Build prompts
    system_prompt = get_talent_system_prompt(talent_role)
    user_prompt = get_talent_user_prompt(expert_results, phase, round_num)

    # Call DeepSeek Reasoner via raw OpenAI client (to capture reasoning_content)
    client = _get_openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=MODEL_REASONER,
        messages=messages,
    )
    msg = response.choices[0].message
    raw_content = msg.content or ""

    # Capture reasoning_content (DeepSeek Reasoner's chain-of-thought)
    think_content = getattr(msg, "reasoning_content", "") or ""

    # Fallback: extract from <think> tags if reasoning_content is absent
    if not think_content:
        think_match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL)
        if think_match:
            think_content = think_match.group(1).strip()
            raw_content = re.sub(
                r"<think>.*?</think>", "", raw_content, flags=re.DOTALL
            ).strip()

    # Parse structured output
    parsed = _parse_talent_output(raw_content)

    talent_summary: TalentSummary = {
        "core_contradictions": parsed["core_contradictions"],
        "emergent_hypothesis": parsed["emergent_hypothesis"],
        "synthesis_score": parsed["synthesis_score"],
        "phase": phase,
        "round_num": round_num,
        "think_content": think_content,
    }

    return {
        "talent_summaries": [talent_summary],
        "current_talent_summary": talent_summary,
    }
