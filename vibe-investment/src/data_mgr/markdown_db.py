"""
Markdown Database Layer
使用Markdown + YAML Frontmatter作为数据存储
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import frontmatter
import yaml


class BaseMarkdownDB:
    """Markdown数据库基类"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _load_file(self, filepath: Path) -> Optional[frontmatter.Post]:
        """安全加载Markdown文件"""
        try:
            if filepath.exists():
                return frontmatter.load(str(filepath))
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
        return None
    
    def _save_file(self, filepath: Path, post: frontmatter.Post) -> bool:
        """安全保存Markdown文件"""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            frontmatter.dump(post, str(filepath))
            return True
        except Exception as e:
            print(f"Error saving {filepath}: {e}")
            return False


class ProfileManager(BaseMarkdownDB):
    """用户画像管理器"""
    
    DEFAULT_PROFILE = {
        "risk_aversion": "medium",
        "investment_horizon": "long",
        "source_weights": {
            "financial_reports": 1.0,
            "news_mainstream": 0.8,
            "social_media": 0.4
        },
        "max_debate_rounds": 3,
        "daily_briefing_time": "08:00",
        "last_updated": datetime.now().isoformat()
    }
    
    def __init__(self, data_path: str = "data"):
        super().__init__(data_path)
        self.profile_path = self.base_path / "profile.md"
        self._ensure_profile_exists()
    
    def _ensure_profile_exists(self):
        """确保profile.md存在"""
        if not self.profile_path.exists():
            self.create_default_profile()
    
    def create_default_profile(self) -> bool:
        """创建默认用户画像"""
        post = frontmatter.Post(
            "# User Investment Profile\n\n"
            "This file stores your investment preferences and risk profile.\n\n"
            "## Philosophy\n"
            "Long-term compounder with focus on growth opportunities.\n\n"
            "## Notes\n"
            "- Prefer data-driven decisions\n"
            "- Willing to accept volatility for growth\n",
            **self.DEFAULT_PROFILE
        )
        return self._save_file(self.profile_path, post)
    
    def get_profile(self) -> Dict[str, Any]:
        """获取用户画像"""
        post = self._load_file(self.profile_path)
        if post:
            return dict(post.metadata)
        return self.DEFAULT_PROFILE.copy()
    
    def update_profile(self, updates: Dict[str, Any], notes: str = "") -> bool:
        """更新用户画像"""
        post = self._load_file(self.profile_path)
        if not post:
            post = frontmatter.Post("", **self.DEFAULT_PROFILE)
        
        # 更新元数据
        post.metadata.update(updates)
        post.metadata["last_updated"] = datetime.now().isoformat()
        
        # 如果有注释，追加到内容
        if notes:
            post.content += f"\n\n## Update {datetime.now().strftime('%Y-%m-%d')}\n{notes}"
        
        return self._save_file(self.profile_path, post)
    
    def get_prompt_context(self) -> str:
        """生成用于Agent Prompt的上下文字符串"""
        profile = self.get_profile()
        
        risk = profile.get("risk_aversion", "medium")
        horizon = profile.get("investment_horizon", "long")
        weights = profile.get("source_weights", {})
        
        return f"""[USER PROFILE]
Risk Tolerance: {risk}
Investment Horizon: {horizon}
Source Weights:
- Financial Reports: {weights.get('financial_reports', 1.0)}
- Mainstream News: {weights.get('news_mainstream', 0.8)}
- Social Media: {weights.get('social_media', 0.4)}

When providing analysis, consider these preferences and adjust confidence accordingly.
[/USER PROFILE]"""


class PortfolioManager(BaseMarkdownDB):
    """持仓和关注列表管理器"""
    
    def __init__(self, data_path: str = "data"):
        super().__init__(data_path)
        self.portfolio_path = self.base_path / "portfolio"
        self.portfolio_path.mkdir(exist_ok=True)
    
    def _get_stock_path(self, ticker: str) -> Path:
        """获取股票文件路径"""
        return self.portfolio_path / f"{ticker.upper()}.md"
    
    def get_stock(self, ticker: str) -> Optional[Dict[str, Any]]:
        """获取单个股票信息"""
        filepath = self._get_stock_path(ticker)
        post = self._load_file(filepath)
        if post:
            return {
                "ticker": ticker.upper(),
                "metadata": dict(post.metadata),
                "content": post.content
            }
        return None
    
    def list_stocks(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有股票，可选状态过滤"""
        stocks = []
        for file_path in self.portfolio_path.glob("*.md"):
            ticker = file_path.stem.upper()
            stock_data = self.get_stock(ticker)
            if stock_data:
                if status_filter is None or stock_data["metadata"].get("status") == status_filter:
                    stocks.append(stock_data)
        return stocks
    
    def add_or_update_stock(
        self, 
        ticker: str, 
        status: str = "watchlist",
        metadata: Optional[Dict[str, Any]] = None,
        content: str = "",
        thesis_bull: str = "",
        thesis_bear: str = "",
        cio_conclusion: str = ""
    ) -> bool:
        """添加或更新股票"""
        ticker = ticker.upper()
        filepath = self._get_stock_path(ticker)
        
        # 尝试加载现有数据
        existing = self._load_file(filepath)
        if existing:
            existing_meta = dict(existing.metadata)
            existing_content = existing.content
        else:
            existing_meta = {}
            existing_content = ""
        
        # 更新元数据
        new_metadata = existing_meta.copy()
        new_metadata.update(metadata or {})
        new_metadata.update({
            "ticker": ticker,
            "status": status,
            "last_updated": datetime.now().isoformat()
        })
        
        # 构建内容
        if not existing_content and not content:
            # 新文件，使用模板
            content = f"""# {ticker} Investment Thesis

## Overview
- **Status**: {status}
- **Last Review**: {datetime.now().strftime('%Y-%m-%d')}

## Bull Case (Alpha Hunter)
{thesis_bull or "(To be filled)"}

## Bear Case (Risk Auditor)
{thesis_bear or "(To be filled)"}

## CIO Conclusion
{cio_conclusion or "(To be filled)"}

## User Notes

"""
        
        post = frontmatter.Post(content, **new_metadata)
        return self._save_file(filepath, post)
    
    def update_stock_analysis(
        self, 
        ticker: str, 
        bull_case: Optional[str] = None,
        bear_case: Optional[str] = None,
        cio_conclusion: Optional[str] = None,
        conviction: Optional[str] = None
    ) -> bool:
        """更新股票分析内容"""
        ticker = ticker.upper()
        stock = self.get_stock(ticker)
        if not stock:
            return False
        
        filepath = self._get_stock_path(ticker)
        post = self._load_file(filepath)
        
        # 更新元数据
        if conviction:
            post.metadata["conviction"] = conviction
        post.metadata["last_updated"] = datetime.now().isoformat()
        
        # 更新内容（简单替换策略，实际可以更复杂）
        content = post.content
        
        if bull_case:
            content = self._replace_section(content, "Bull Case (Alpha Hunter)", bull_case)
        if bear_case:
            content = self._replace_section(content, "Bear Case (Risk Auditor)", bear_case)
        if cio_conclusion:
            content = self._replace_section(content, "CIO Conclusion", cio_conclusion)
        
        post.content = content
        return self._save_file(filepath, post)
    
    def _replace_section(self, content: str, section_name: str, new_text: str) -> str:
        """替换Markdown中的特定章节"""
        pattern = rf"(## {re.escape(section_name)}\n)(.*?)(?=\n## |$)"
        replacement = rf"\1{new_text}\n\n"
        return re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    def remove_stock(self, ticker: str) -> bool:
        """删除股票记录"""
        filepath = self._get_stock_path(ticker)
        try:
            if filepath.exists():
                filepath.unlink()
                return True
        except Exception as e:
            print(f"Error removing {ticker}: {e}")
        return False
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """获取持仓摘要"""
        all_stocks = self.list_stocks()
        holding = [s for s in all_stocks if s["metadata"].get("status") == "holding"]
        watchlist = [s for s in all_stocks if s["metadata"].get("status") == "watchlist"]
        
        total_position = sum(
            s["metadata"].get("position_size", 0) 
            for s in holding
        )
        
        return {
            "total_stocks": len(all_stocks),
            "holding_count": len(holding),
            "watchlist_count": len(watchlist),
            "total_position": total_position,
            "holdings": holding,
            "watchlist": watchlist
        }


class DebateManager(BaseMarkdownDB):
    """历史辩论记录管理器"""
    
    def __init__(self, data_path: str = "data"):
        super().__init__(data_path)
        self.debates_path = self.base_path / "debates"
        self.debates_path.mkdir(exist_ok=True)
    
    def save_debate(
        self, 
        ticker: str, 
        debate_log: List[Dict[str, Any]], 
        final_memo: str,
        user_vibe: str = ""
    ) -> str:
        """保存辩论记录，返回文件路径"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{ticker.upper()}.md"
        filepath = self.debates_path / filename
        
        # 构建辩论日志内容
        debate_content = "## Debate Log\n\n"
        for i, entry in enumerate(debate_log, 1):
            agent = entry.get("agent", "Unknown")
            content = entry.get("content", "")
            sources = entry.get("sources", [])
            
            debate_content += f"### Round {i} - {agent}\n\n"
            debate_content += f"{content}\n\n"
            if sources:
                debate_content += "**Sources:**\n"
                for src in sources:
                    debate_content += f"- {src}\n"
            debate_content += "\n---\n\n"
        
        content = f"""# Investment Decision Debate: {ticker}

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Ticker**: {ticker}
**User Vibe**: {user_vibe or "N/A"}

{debate_content}

## Final Decision Memo

{final_memo}

---
*Generated by Vibe Investment System*
"""
        
        post = frontmatter.Post(
            content,
            ticker=ticker.upper(),
            timestamp=datetime.now().isoformat(),
            rounds=len(debate_log),
            has_conclusion=bool(final_memo)
        )
        
        self._save_file(filepath, post)
        return str(filepath)
    
    def list_debates(self, ticker: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """列出历史辩论记录"""
        debates = []
        files = sorted(self.debates_path.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        for file_path in files[:limit]:
            post = self._load_file(file_path)
            if post:
                meta = post.metadata
                if ticker is None or meta.get("ticker") == ticker.upper():
                    debates.append({
                        "filename": file_path.name,
                        "ticker": meta.get("ticker"),
                        "timestamp": meta.get("timestamp"),
                        "rounds": meta.get("rounds"),
                        "has_conclusion": meta.get("has_conclusion")
                    })
        
        return debates
