"""LLM client factory for the Vibe Investment Engine.

Two tiers per architecture constraint:
  - Chat model   → Planner (fast routing, structured extraction)
  - Reasoner model → Expert / Talent (deep reasoning)
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

from vibe_engine.config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_API_KEY,
    MODEL_CHAT,
    MODEL_REASONER,
)


def _get_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
    if not key:
        raise EnvironmentError(
            "DEEPSEEK_API_KEY is not set. "
            "Copy .env.example → .env and add your API key."
        )
    return key


def get_chat_llm(**kwargs) -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at the DeepSeek Chat model."""
    return ChatOpenAI(
        model=MODEL_CHAT,
        api_key=_get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
        **kwargs,
    )


def get_reasoner_llm(**kwargs) -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at the DeepSeek Reasoner model."""
    return ChatOpenAI(
        model=MODEL_REASONER,
        api_key=_get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
        **kwargs,
    )
