"""Configuration management for Vibe Investment."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file
load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    deepseek_api_key: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    tavily_api_key: str = Field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    # LLM Configuration
    default_llm: Literal["claude", "openai", "deepseek"] = Field(
        default_factory=lambda: os.getenv("DEFAULT_LLM", "deepseek")
    )
    claude_model: str = Field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    )
    openai_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o")
    )
    deepseek_model: str = Field(
        default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    )
    deepseek_base_url: str = Field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )

    # Debate Configuration
    max_debate_rounds: int = Field(
        default_factory=lambda: int(os.getenv("MAX_DEBATE_ROUNDS", "3"))
    )

    # Paths
    data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", "data"))
    )

    @property
    def profile_path(self) -> Path:
        return self.data_dir / "profile.md"

    @property
    def portfolio_dir(self) -> Path:
        return self.data_dir / "portfolio"

    @property
    def watchlist_dir(self) -> Path:
        return self.data_dir / "watchlist"

    @property
    def debates_dir(self) -> Path:
        return self.data_dir / "debates"

    def ensure_dirs(self) -> None:
        """Create all necessary directories if they don't exist."""
        self.portfolio_dir.mkdir(parents=True, exist_ok=True)
        self.watchlist_dir.mkdir(parents=True, exist_ok=True)
        self.debates_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
