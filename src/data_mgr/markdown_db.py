"""Markdown-based data storage for Vibe Investment.

All data is stored as Markdown files with YAML frontmatter for metadata.
This provides human-readable storage and easy version control.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import frontmatter
from pydantic import BaseModel, Field

from src.utils.config import get_settings


class ProfileData(BaseModel):
    """User investment profile data."""

    risk_aversion: str = "medium"  # low, medium, high
    investment_horizon: str = "long"  # short, medium, long
    source_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "financial_reports": 1.0,
            "news_mainstream": 0.8,
            "social_media": 0.4,
        }
    )
    decision_style: str = "show_debate"  # show_debate, summary_only
    last_updated: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))


class StockData(BaseModel):
    """Individual stock/asset data."""

    ticker: str
    status: str = "watchlist"  # holding, watchlist, sold
    avg_cost: Optional[float] = None
    position_size: Optional[float] = None  # percentage of portfolio
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    conviction: str = "medium"  # low, medium, high
    last_review: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))


class MarkdownDB:
    """Base class for Markdown file operations."""

    @staticmethod
    def read_file(path: Path) -> tuple[dict[str, Any], str]:
        """Read a Markdown file and return (metadata, content)."""
        if not path.exists():
            return {}, ""
        post = frontmatter.load(path)
        return dict(post.metadata), post.content

    @staticmethod
    def write_file(path: Path, metadata: dict[str, Any], content: str) -> None:
        """Write metadata and content to a Markdown file."""
        post = frontmatter.Post(content, **metadata)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

    @staticmethod
    def update_metadata(path: Path, updates: dict[str, Any]) -> None:
        """Update specific metadata fields without changing content."""
        metadata, content = MarkdownDB.read_file(path)
        metadata.update(updates)
        MarkdownDB.write_file(path, metadata, content)

    @staticmethod
    def append_content(path: Path, new_content: str) -> None:
        """Append content to an existing file."""
        metadata, content = MarkdownDB.read_file(path)
        content = content.strip() + "\n\n" + new_content
        MarkdownDB.write_file(path, metadata, content)


class ProfileManager:
    """Manage user investment profile."""

    def __init__(self):
        self.settings = get_settings()
        self.path = self.settings.profile_path

    def exists(self) -> bool:
        """Check if profile exists."""
        return self.path.exists()

    def get(self) -> tuple[ProfileData, str]:
        """Get profile data and content."""
        metadata, content = MarkdownDB.read_file(self.path)
        if not metadata:
            return ProfileData(), ""
        return ProfileData(**metadata), content

    def create(self, profile: ProfileData, philosophy: str = "") -> None:
        """Create or update profile."""
        metadata = profile.model_dump()
        content = f"# 投资理念\n\n{philosophy}" if philosophy else "# 投资理念\n\n(待填写)"
        MarkdownDB.write_file(self.path, metadata, content)

    def update(self, updates: dict[str, Any]) -> None:
        """Update profile metadata."""
        updates["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        MarkdownDB.update_metadata(self.path, updates)

    def get_source_weight(self, source_type: str) -> float:
        """Get weight for a specific source type."""
        profile, _ = self.get()
        return profile.source_weights.get(source_type, 0.5)


class PortfolioManager:
    """Manage portfolio and watchlist stocks."""

    def __init__(self):
        self.settings = get_settings()

    def _get_path(self, ticker: str, status: str = "holding") -> Path:
        """Get file path for a ticker."""
        ticker = ticker.upper()
        if status == "watchlist":
            return self.settings.watchlist_dir / f"{ticker}.md"
        return self.settings.portfolio_dir / f"{ticker}.md"

    def get_stock(self, ticker: str) -> tuple[Optional[StockData], str]:
        """Get stock data. Checks portfolio first, then watchlist."""
        ticker = ticker.upper()

        # Check portfolio first
        path = self.settings.portfolio_dir / f"{ticker}.md"
        if path.exists():
            metadata, content = MarkdownDB.read_file(path)
            return StockData(**metadata), content

        # Check watchlist
        path = self.settings.watchlist_dir / f"{ticker}.md"
        if path.exists():
            metadata, content = MarkdownDB.read_file(path)
            return StockData(**metadata), content

        return None, ""

    def save_stock(self, stock: StockData, content: str) -> None:
        """Save stock data to appropriate directory."""
        path = self._get_path(stock.ticker, stock.status)

        # If status changed, remove from old location
        old_path = (
            self.settings.watchlist_dir / f"{stock.ticker}.md"
            if stock.status == "holding"
            else self.settings.portfolio_dir / f"{stock.ticker}.md"
        )
        if old_path.exists() and old_path != path:
            old_path.unlink()

        stock.last_review = datetime.now().strftime("%Y-%m-%d")
        MarkdownDB.write_file(path, stock.model_dump(), content)

    def list_holdings(self) -> list[StockData]:
        """List all stocks in portfolio."""
        holdings = []
        for path in self.settings.portfolio_dir.glob("*.md"):
            metadata, _ = MarkdownDB.read_file(path)
            if metadata:
                holdings.append(StockData(**metadata))
        return holdings

    def list_watchlist(self) -> list[StockData]:
        """List all stocks in watchlist."""
        watchlist = []
        for path in self.settings.watchlist_dir.glob("*.md"):
            metadata, _ = MarkdownDB.read_file(path)
            if metadata:
                watchlist.append(StockData(**metadata))
        return watchlist

    def list_all(self) -> list[StockData]:
        """List all tracked stocks (holdings + watchlist)."""
        return self.list_holdings() + self.list_watchlist()

    def create_analysis_content(
        self,
        ticker: str,
        bull_case: str,
        bear_case: str,
        cio_conclusion: str,
        user_notes: str = "",
    ) -> str:
        """Generate standard content for a stock analysis file."""
        return f"""# {ticker} Investment Thesis

## Bull Case (Alpha Hunter)
{bull_case}

## Bear Case (Risk Auditor)
{bear_case}

## CIO Conclusion
{cio_conclusion}

## User Notes
{user_notes if user_notes else "(暂无)"}
"""

    def update_analysis(
        self,
        ticker: str,
        bull_case: Optional[str] = None,
        bear_case: Optional[str] = None,
        cio_conclusion: Optional[str] = None,
    ) -> None:
        """Update specific sections of analysis."""
        stock, content = self.get_stock(ticker)
        if not stock:
            return

        # Parse existing content
        sections = self._parse_sections(content)

        # Update sections
        if bull_case:
            sections["bull_case"] = bull_case
        if bear_case:
            sections["bear_case"] = bear_case
        if cio_conclusion:
            sections["cio_conclusion"] = cio_conclusion

        # Rebuild content
        new_content = self.create_analysis_content(
            ticker,
            sections.get("bull_case", ""),
            sections.get("bear_case", ""),
            sections.get("cio_conclusion", ""),
            sections.get("user_notes", ""),
        )

        self.save_stock(stock, new_content)

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Parse markdown content into sections."""
        sections = {}
        current_section = None
        current_content = []

        for line in content.split("\n"):
            if line.startswith("## Bull Case"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "bull_case"
                current_content = []
            elif line.startswith("## Bear Case"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "bear_case"
                current_content = []
            elif line.startswith("## CIO Conclusion"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "cio_conclusion"
                current_content = []
            elif line.startswith("## User Notes"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "user_notes"
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections


class DebateManager:
    """Manage debate history archives."""

    def __init__(self):
        self.settings = get_settings()

    def save_debate(
        self,
        ticker: str,
        user_vibe: str,
        debate_rounds: list[dict[str, str]],
        final_memo: str,
    ) -> Path:
        """Save a complete debate to archive."""
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{date_str}_{ticker.upper()}.md"
        path = self.settings.debates_dir / filename

        metadata = {
            "ticker": ticker.upper(),
            "date": datetime.now().isoformat(),
            "user_vibe": user_vibe,
            "rounds": len(debate_rounds),
        }

        # Build content
        content_parts = [
            f"# {ticker.upper()} 投资辩论记录",
            f"\n## 用户直觉 (Vibe)\n{user_vibe}",
            "\n## 辩论过程",
        ]

        for i, round_data in enumerate(debate_rounds, 1):
            content_parts.append(f"\n### Round {i}")
            if "bull" in round_data:
                content_parts.append(f"\n**Bull Agent:**\n{round_data['bull']}")
            if "bear" in round_data:
                content_parts.append(f"\n**Bear Agent:**\n{round_data['bear']}")

        content_parts.append(f"\n## 最终结论\n{final_memo}")

        content = "\n".join(content_parts)
        MarkdownDB.write_file(path, metadata, content)

        return path

    def list_debates(self, ticker: Optional[str] = None) -> list[Path]:
        """List debate files, optionally filtered by ticker."""
        pattern = f"*_{ticker.upper()}.md" if ticker else "*.md"
        return sorted(self.settings.debates_dir.glob(pattern), reverse=True)
