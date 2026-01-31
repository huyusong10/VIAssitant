#!/usr/bin/env python3
"""Daily monitoring cron job for Vibe Investment.

This script runs daily to check for significant changes in tracked stocks.
It can be run manually or scheduled via crontab:

    # Run every day at 8:00 AM
    0 8 * * * cd /path/to/vibe-investment && python daily_cron.py

Usage:
    python daily_cron.py              # Run once
    python daily_cron.py --daemon     # Run as daemon (check every hour)
"""

import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from src.agents.nodes import BearAgent, get_llm
from src.agents.tools import search_financial_news
from src.data_mgr.markdown_db import (
    DebateManager,
    MarkdownDB,
    PortfolioManager,
    ProfileManager,
    StockData,
)
from src.utils.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("daily_monitor.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class DailyMonitor:
    """Daily monitoring for portfolio stocks."""

    def __init__(self):
        self.settings = get_settings()
        self.portfolio_mgr = PortfolioManager()
        self.profile_mgr = ProfileManager()
        self.debate_mgr = DebateManager()
        self.alerts = []

    async def run(self) -> list[dict]:
        """Run daily monitoring check.

        Returns:
            List of alerts generated
        """
        logger.info("Starting daily monitoring...")

        # Get all tracked stocks
        all_stocks = self.portfolio_mgr.list_all()

        if not all_stocks:
            logger.info("No stocks to monitor.")
            return []

        logger.info(f"Monitoring {len(all_stocks)} stocks...")

        # Check each stock
        for stock in all_stocks:
            try:
                alert = await self.check_stock(stock)
                if alert:
                    self.alerts.append(alert)
            except Exception as e:
                logger.error(f"Error checking {stock.ticker}: {e}")

        # Generate daily briefing
        await self.generate_briefing()

        logger.info(f"Daily monitoring complete. {len(self.alerts)} alerts generated.")
        return self.alerts

    async def check_stock(self, stock: StockData) -> dict | None:
        """Check a single stock for significant changes.

        Args:
            stock: Stock data to check

        Returns:
            Alert dict if significant change detected, None otherwise
        """
        logger.info(f"Checking {stock.ticker}...")

        # Get recent news
        news = search_financial_news.invoke({"ticker": stock.ticker, "days": 1})

        if "[error]" in news.lower() or "no recent news" in news.lower():
            logger.info(f"No news for {stock.ticker}")
            return None

        # Use LLM to evaluate significance
        llm = get_llm()

        profile, _ = self.profile_mgr.get()

        eval_prompt = f"""你是一个投资风险监控系统。

请评估以下新闻对 {stock.ticker} 的影响。

当前持仓信息：
- 状态: {stock.status}
- 成本: ${stock.avg_cost or 'N/A'}
- 止损: ${stock.stop_loss or 'N/A'}
- 置信度: {stock.conviction}

用户风险偏好: {profile.risk_aversion}

最新新闻:
{news}

请判断：
1. 这些新闻是否包含重大信息？(YES/NO)
2. 如果 YES，简要说明原因和建议行动

回答格式：
SIGNIFICANT: YES/NO
REASON: (原因，如果 NO 则留空)
ACTION: (建议行动，如果 NO 则留空)
SEVERITY: HIGH/MEDIUM/LOW (如果 NO 则留空)
"""

        from langchain_core.messages import HumanMessage

        response = await llm.ainvoke([HumanMessage(content=eval_prompt)])

        # Parse response
        content = response.content
        is_significant = "SIGNIFICANT: YES" in content.upper()

        if not is_significant:
            logger.info(f"{stock.ticker}: No significant changes")
            return None

        # Extract details
        severity = "MEDIUM"
        if "SEVERITY: HIGH" in content.upper():
            severity = "HIGH"
        elif "SEVERITY: LOW" in content.upper():
            severity = "LOW"

        reason = ""
        for line in content.split("\n"):
            if line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()
                break

        action = ""
        for line in content.split("\n"):
            if line.startswith("ACTION:"):
                action = line.replace("ACTION:", "").strip()
                break

        alert = {
            "ticker": stock.ticker,
            "severity": severity,
            "reason": reason,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "news_summary": news[:500],
        }

        logger.warning(f"ALERT for {stock.ticker}: {severity} - {reason}")

        return alert

    async def generate_briefing(self):
        """Generate and save daily briefing."""
        date_str = datetime.now().strftime("%Y-%m-%d")

        content = f"""# 每日简报 - {date_str}

## 监控摘要
- 监控标的数量: {len(self.portfolio_mgr.list_all())}
- 触发警报数量: {len(self.alerts)}

"""

        if self.alerts:
            content += "## 警报详情\n\n"
            for alert in self.alerts:
                content += f"""### {alert['ticker']} - {alert['severity']}

**原因:** {alert['reason']}

**建议行动:** {alert['action']}

---

"""
        else:
            content += "## 市场状态\n\n✅ 所有持仓无重大异常。\n"

        # Save briefing
        briefing_path = self.settings.debates_dir / f"{date_str}_Daily_Briefing.md"

        metadata = {
            "type": "daily_briefing",
            "date": date_str,
            "alerts_count": len(self.alerts),
        }

        MarkdownDB.write_file(briefing_path, metadata, content)
        logger.info(f"Daily briefing saved to {briefing_path}")

    def send_notifications(self):
        """Send notifications for alerts (placeholder).

        TODO: Implement actual notification (email, push, etc.)
        """
        for alert in self.alerts:
            if alert["severity"] == "HIGH":
                # High severity: immediate notification
                logger.critical(
                    f"HIGH ALERT: {alert['ticker']} - {alert['reason']}"
                )
            else:
                logger.warning(
                    f"ALERT: {alert['ticker']} - {alert['reason']}"
                )


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Vibe Investment Daily Monitor")
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon (check every hour)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Check interval in seconds (default: 3600)",
    )

    args = parser.parse_args()

    monitor = DailyMonitor()

    if args.daemon:
        logger.info(f"Running in daemon mode, interval: {args.interval}s")
        while True:
            try:
                await monitor.run()
                monitor.send_notifications()
            except Exception as e:
                logger.error(f"Monitor error: {e}")

            # Wait for next check
            await asyncio.sleep(args.interval)
    else:
        # Single run
        await monitor.run()
        monitor.send_notifications()


if __name__ == "__main__":
    asyncio.run(main())
