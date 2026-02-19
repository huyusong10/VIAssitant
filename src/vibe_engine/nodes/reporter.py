"""Reporter node — final report generation after all phases complete.

Architecture notes:
- The Reporter node runs after all workflow phases have completed (or after
  the final phase's Planner says "proceed").
- It uses DeepSeek **Chat** model (fast, good at structured writing).
- Collects all accumulated analysis data from the state and produces
  a comprehensive structured investment report.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from vibe_engine.state import VibeState
from vibe_engine.prompts import get_final_report_system_prompt, get_final_report_user_prompt
from vibe_engine.config import DEEPSEEK_BASE_URL, MODEL_CHAT


def _get_openai_client() -> OpenAI:
    """Return a raw OpenAI client pointed at DeepSeek."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example → .env and add your API key."
        )
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def reporter_node(state: VibeState) -> dict:
    """LangGraph node for final report generation (S5.5).

    Collects all expert results, talent summaries, planner decisions,
    and vibe history to produce a comprehensive investment report.

    Returns:
        A partial VibeState update with final_report populated.
    """
    vibe_original = state.get("vibe_original", "")
    vibe_history = state.get("vibe_history", [])
    talent_summaries = state.get("talent_summaries", [])
    planner_decisions = state.get("planner_decisions", [])
    expert_results = state.get("expert_results", [])

    system_prompt = get_final_report_system_prompt()
    user_prompt = get_final_report_user_prompt(
        vibe_original=vibe_original,
        vibe_history=vibe_history,
        talent_summaries=talent_summaries,
        planner_decisions=planner_decisions,
        expert_results=expert_results,
    )

    client = _get_openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=MODEL_CHAT,
        messages=messages,
    )
    report = response.choices[0].message.content or ""

    return {"final_report": report}
