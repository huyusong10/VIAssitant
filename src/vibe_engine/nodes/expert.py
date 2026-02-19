"""Expert node — single expert analysis unit.

Architecture notes:
- In S2+, the expert node receives per-expert ExpertInput via LangGraph's Send().
  This ensures each expert runs with completely isolated context — no shared
  message history between concurrent experts.
- The factory pattern (make_expert_node) is retained for backward compatibility
  and direct testing, but the graph now uses the unified `expert_node` function.
- The think content (reasoning_content) is extracted via the raw OpenAI client,
  because LangChain's wrapper does not expose DeepSeek's reasoning_content field.
"""

import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from vibe_engine.state import VibeState, ExpertInput, ExpertResult
from vibe_engine.prompts import get_expert_system_prompt, get_expert_user_prompt
from vibe_engine.config import EXPERT_DIMENSIONS, DEEPSEEK_BASE_URL, MODEL_REASONER


def _get_openai_client() -> OpenAI:
    """Return a raw OpenAI client pointed at DeepSeek."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example → .env and add your API key."
        )
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def _extract_think(raw: str) -> tuple[str, str]:
    """Extract <think>...</think> content from model response.

    Returns (think_content, cleaned_response).
    DeepSeek Reasoner wraps its chain-of-thought in <think> tags.
    """
    think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
    think_content = think_match.group(1).strip() if think_match else ""
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    return think_content, cleaned


def _parse_expert_output(raw: str) -> dict[str, str]:
    """Parse the structured sections from expert output.

    Expected sections (in Chinese):
    - ### 逻辑链条
    - ### 精简结论
    - ### 核心风险点

    Returns a dict with keys: logic_chain, conclusion, risk_points.
    Falls back to the full raw text if parsing fails.
    """
    sections = {
        "logic_chain": "",
        "conclusion": "",
        "risk_points": "",
    }

    # Pattern: ### <section header>\n<content until next ### or end>
    patterns = [
        ("logic_chain", r"###\s*逻辑链条\s*\n(.*?)(?=###|\Z)"),
        ("conclusion", r"###\s*精简结论\s*\n(.*?)(?=###|\Z)"),
        ("risk_points", r"###\s*核心风险点\s*\n(.*?)(?=###|\Z)"),
    ]

    for key, pattern in patterns:
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            sections[key] = match.group(1).strip()

    # Fallback: put everything in logic_chain if parsing completely fails
    if not any(sections.values()):
        sections["logic_chain"] = raw.strip()

    return sections


def _call_expert(expert_id: int, vibe: str, phase: str, round_num: int) -> ExpertResult:
    """Core expert analysis logic — shared by both fan-out and standalone modes.

    Args:
        expert_id: The expert dimension ID (1-10).
        vibe: The current Vibe text.
        phase: Current workflow phase.
        round_num: Current round number.

    Returns:
        A populated ExpertResult dict.
    """
    expert_dim = next(d for d in EXPERT_DIMENSIONS if d["id"] == expert_id)
    system_prompt = get_expert_system_prompt(expert_id)
    user_prompt = get_expert_user_prompt(vibe, phase, round_num)

    client = _get_openai_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Use raw OpenAI client to capture reasoning_content from DeepSeek Reasoner.
    # LangChain's wrapper does not expose this field.
    response = client.chat.completions.create(
        model=MODEL_REASONER,
        messages=messages,
    )
    msg = response.choices[0].message
    raw_content = msg.content or ""

    # reasoning_content is DeepSeek Reasoner's chain-of-thought
    think_content = getattr(msg, "reasoning_content", "") or ""

    # Fallback: extract from <think> tags if reasoning_content is absent
    if not think_content:
        think_content, raw_content = _extract_think(raw_content)

    parsed = _parse_expert_output(raw_content)

    result: ExpertResult = {
        "expert_id": expert_id,
        "expert_name": expert_dim["name"],
        "logic_chain": parsed["logic_chain"],
        "conclusion": parsed["conclusion"],
        "risk_points": parsed["risk_points"],
        "think_content": think_content,
        # Phase-specific fields — empty by default, filled in S5+
        "targets": [],
        "data_logic_chain": "",
    }
    return result


def expert_node(state: ExpertInput) -> dict:
    """LangGraph node function for expert analysis (S2+ fan-out mode).

    Called via Send() with an ExpertInput containing expert_id and context.
    Each invocation is isolated — no shared state between parallel experts.

    Returns:
        A partial VibeState update dict with expert_results (list append via reducer).
    """
    expert_id = state["expert_id"]
    vibe = state["vibe"]
    phase = state.get("phase", "discovery")
    round_num = state.get("round", 1)

    result = _call_expert(expert_id, vibe, phase, round_num)

    # Append to expert_results using the annotated reducer (list append)
    return {"expert_results": [result]}


def make_expert_node(expert_id: int):
    """Factory: return a LangGraph node function for a specific expert dimension.

    Retained for backward compatibility and direct testing.
    The S2+ graph uses `expert_node` directly via Send().

    Args:
        expert_id: Which expert dimension to use (1-10).

    Returns:
        A node function with signature: (state: VibeState) -> dict
    """
    valid_ids = {d["id"] for d in EXPERT_DIMENSIONS}
    if expert_id not in valid_ids:
        raise ValueError(f"Invalid expert_id={expert_id}. Must be one of {sorted(valid_ids)}.")

    def _node(state: VibeState) -> dict:
        vibe = state.get("vibe", "")
        phase = state.get("phase", "discovery")
        round_num = state.get("round", 1)
        result = _call_expert(expert_id, vibe, phase, round_num)
        return {"expert_results": [result]}

    _node.__name__ = f"expert_{expert_id}"
    _node.__qualname__ = f"expert_{expert_id}"
    return _node
