"""
Daily Monitor & Cron Job

每日自动扫描持仓和关注列表，生成简报
运行方式:
    python daily_cron.py
    
或添加到crontab:
    0 8 * * * cd /path/to/vibe-investment && python daily_cron.py
"""
import os
import sys
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.data_mgr import ProfileManager, PortfolioManager, DebateManager
from src.agents.tools import SearchTool
from src.utils.config import settings, get_llm


class DailyMonitor:
    """每日监控器"""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = data_path
        self.profile_mgr = ProfileManager(data_path)
        self.portfolio_mgr = PortfolioManager(data_path)
        self.search_tool = SearchTool()
        
    async def run_daily_check(self, ticker_filter: list = None) -> dict:
        """
        执行每日检查
        
        Args:
            ticker_filter: 可选，只检查指定的ticker列表
            
        Returns:
            检查结果字典
        """
        profile = self.profile_mgr.get_profile()
        
        # 获取所有持仓和关注列表
        holdings = self.portfolio_mgr.list_stocks(status_filter="holding")
        watchlist = self.portfolio_mgr.list_stocks(status_filter="watchlist")
        
        all_stocks = holdings + watchlist
        
        if ticker_filter:
            all_stocks = [s for s in all_stocks if s["metadata"].get("ticker") in ticker_filter]
        
        if not all_stocks:
            print("No stocks to monitor.")
            return {"checked": 0, "alerts": []}
        
        print(f"[{datetime.now()}] Monitoring {len(all_stocks)} stocks...")
        
        # 结果收集
        results = {
            "date": datetime.now().isoformat(),
            "checked": len(all_stocks),
            "stocks": [],
            "alerts": [],
            "briefing": ""
        }
        
        # 逐个检查
        for stock in all_stocks:
            ticker = stock["metadata"].get("ticker", "UNKNOWN")
            try:
                print(f"  Checking {ticker}...")
                stock_result = await self.check_single_stock(ticker, stock, profile)
                results["stocks"].append(stock_result)
                
                if stock_result.get("alert_level") in ["high", "critical"]:
                    results["alerts"].append(stock_result)
                    
            except Exception as e:
                print(f"  Error checking {ticker}: {e}")
                results["stocks"].append({
                    "ticker": ticker,
                    "error": str(e),
                    "alert_level": "error"
                })
        
        # 生成简报
        results["briefing"] = await self.generate_briefing(results, profile)
        
        # 保存简报
        self.save_daily_briefing(results)
        
        return results
    
    async def check_single_stock(self, ticker: str, stock_data: dict, profile: dict) -> dict:
        """
        检查单个股票
        
        策略：
        1. 搜索过去24小时的新闻
        2. 检查是否有重大利空/利好
        3. 对比用户的风险偏好判断是否需要警报
        """
        result = {
            "ticker": ticker,
            "status": stock_data["metadata"].get("status"),
            "checked_at": datetime.now().isoformat(),
            "news_count": 0,
            "sentiment": "neutral",
            "alert_level": "none",  # none, low, medium, high, critical
            "alert_reasons": [],
            "key_events": []
        }
        
        # 获取用户的信息源权重
        source_weights = profile.get("source_weights", {})
        
        # 1. 搜索新闻
        news_queries = [
            f"{ticker} stock news today",
            f"{ticker} earnings guidance update",
        ]
        
        # 如果用户关注社交媒体，添加社交搜索
        if source_weights.get("social_media", 0) > 0.3:
            news_queries.append(f"{ticker} stock twitter reddit sentiment")
        
        search_results = await self.search_tool.search_multi(news_queries, max_results=5)
        
        # 2. 分析搜索结果
        all_news = []
        for sr in search_results:
            if "error" not in sr:
                all_news.extend(sr.get("results", []))
        
        result["news_count"] = len(all_news)
        
        # 3. 使用LLM分析是否有重大事件
        if all_news:
            alert = await self.analyze_for_alerts(ticker, all_news, stock_data, profile)
            result.update(alert)
        
        return result
    
    async def analyze_for_alerts(self, ticker: str, news: list, stock_data: dict, profile: dict) -> dict:
        """
        使用LLM分析新闻，判断是否需要警报
        """
        # 构建新闻摘要
        news_text = "\n".join([
            f"- {n.get('title', '')}: {n.get('content', '')[:200]}"
            for n in news[:5]
        ])
        
        # 获取当前持仓信息
        avg_cost = stock_data["metadata"].get("avg_cost")
        stop_loss = stock_data["metadata"].get("stop_loss")
        
        prompt = f"""You are a monitoring system analyzing daily news for a stock position.

Stock: {ticker}
Status: {stock_data["metadata"].get("status")}
Avg Cost: {avg_cost or "N/A"}
Stop Loss: {stop_loss or "N/A"}
Risk Profile: {profile.get("risk_aversion", "medium")}

Recent News:
{news_text}

Analyze the news and determine:
1. Is there any material information that affects the investment thesis?
2. What's the sentiment (positive/negative/neutral)?
3. Should this trigger an alert to the user?
4. What are the key events (earnings, guidance changes, M&A, etc.)?

Respond in this exact JSON format:
{{
    "sentiment": "positive|negative|neutral",
    "alert_level": "none|low|medium|high|critical",
    "alert_reasons": ["reason 1", "reason 2"],
    "key_events": ["event 1", "event 2"],
    "summary": "Brief summary of what's happening"
}}

Be conservative - only trigger HIGH or CRITICAL alerts for truly material changes."""

        try:
            llm = get_fast_llm(temperature=0.1)
            response = await llm.ainvoke([("human", prompt)])
            
            # 解析JSON响应
            import json
            import re
            
            # 尝试提取JSON
            text = response.content
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            
            if json_match:
                analysis = json.loads(json_match.group())
                return {
                    "sentiment": analysis.get("sentiment", "neutral"),
                    "alert_level": analysis.get("alert_level", "none"),
                    "alert_reasons": analysis.get("alert_reasons", []),
                    "key_events": analysis.get("key_events", []),
                    "summary": analysis.get("summary", "")
                }
        except Exception as e:
            print(f"    Error analyzing alerts for {ticker}: {e}")
        
        return {
            "sentiment": "neutral",
            "alert_level": "none",
            "alert_reasons": [],
            "key_events": [],
            "summary": "Analysis inconclusive"
        }
    
    async def generate_briefing(self, results: dict, profile: dict) -> str:
        """生成每日简报"""
        alerts = results.get("alerts", [])
        stocks = results.get("stocks", [])
        
        lines = [
            f"# Daily Briefing - {datetime.now().strftime('%Y-%m-%d')}",
            "",
            f"**Stocks Monitored**: {results['checked']}",
            f"**Alerts**: {len(alerts)}",
            ""
        ]
        
        # 高优先级警报
        critical_alerts = [a for a in alerts if a.get("alert_level") in ["high", "critical"]]
        if critical_alerts:
            lines.append("## 🚨 High Priority Alerts")
            lines.append("")
            for alert in critical_alerts:
                ticker = alert.get("ticker")
                reasons = alert.get("alert_reasons", [])
                summary = alert.get("summary", "")
                lines.append(f"**{ticker}**: {summary}")
                for reason in reasons:
                    lines.append(f"  - {reason}")
                lines.append("")
        
        # 其他更新
        other_updates = [s for s in stocks if s.get("alert_level") in ["low", "medium"]]
        if other_updates:
            lines.append("## 📋 Other Updates")
            lines.append("")
            for update in other_updates:
                ticker = update.get("ticker")
                summary = update.get("summary", "No significant updates")
                sentiment = update.get("sentiment", "neutral")
                emoji = "📈" if sentiment == "positive" else "📉" if sentiment == "negative" else "➡️"
                lines.append(f"{emoji} **{ticker}**: {summary}")
            lines.append("")
        
        # 无重大事件
        if not critical_alerts and not other_updates:
            lines.append("✅ **No material updates today.**")
            lines.append("")
        
        lines.append("---")
        lines.append("*Generated by Vibe Investment Daily Monitor*")
        
        return "\n".join(lines)
    
    def save_daily_briefing(self, results: dict):
        """保存每日简报到文件"""
        from src.data_mgr.markdown_db import BaseMarkdownDB
        import frontmatter
        
        # 创建debates目录下的daily文件夹
        daily_dir = Path(self.data_path) / "debates" / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{datetime.now().strftime('%Y%m%d')}_briefing.md"
        filepath = daily_dir / filename
        
        post = frontmatter.Post(
            results["briefing"],
            date=datetime.now().isoformat(),
            stocks_checked=results["checked"],
            alert_count=len(results["alerts"]),
            tickers=[s["ticker"] for s in results["stocks"]]
        )
        
        frontmatter.dump(post, str(filepath))
        print(f"\nBriefing saved to: {filepath}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Vibe Investment Daily Monitor")
    parser.add_argument("--ticker", "-t", nargs="+", help="Specific tickers to check")
    parser.add_argument("--data-path", "-d", default="data", help="Data directory path")
    parser.add_argument("--notify", "-n", action="store_true", help="Send notification if alerts found")
    args = parser.parse_args()
    
    # 验证配置
    missing = settings.validate()
    if missing:
        print(f"❌ Missing configuration: {', '.join(missing)}")
        print("Please set up your .env file")
        return
    
    # 运行监控
    monitor = DailyMonitor(data_path=args.data_path)
    results = await monitor.run_daily_check(ticker_filter=args.ticker)
    
    # 打印简报
    print("\n" + "="*60)
    print(results["briefing"])
    print("="*60)
    
    # 如果有警报且需要通知
    if args.notify and results["alerts"]:
        high_alerts = [a for a in results["alerts"] if a.get("alert_level") in ["high", "critical"]]
        if high_alerts:
            # 这里可以集成推送服务如 Pushover, Slack, etc.
            print(f"\n🔔 {len(high_alerts)} high priority alerts require attention!")
            # TODO: 实现具体的通知推送


if __name__ == "__main__":
    asyncio.run(main())
