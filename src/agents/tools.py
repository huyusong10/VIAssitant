"""Search and data tools for agents."""

import os
from typing import Optional

from langchain_core.tools import tool


def get_tavily_client():
    """Get Tavily client if API key is available."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    try:
        from tavily import TavilyClient

        return TavilyClient(api_key=api_key)
    except ImportError:
        return None


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for general information.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    client = get_tavily_client()
    if not client:
        return "[Search unavailable: No API key configured]"

    try:
        response = client.search(query=query, max_results=max_results)
        results = response.get("results", [])

        if not results:
            return f"No results found for: {query}"

        formatted = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', 'No title')}**\n"
                f"   URL: {r.get('url', 'N/A')}\n"
                f"   {r.get('content', 'No content')[:300]}...\n"
            )

        return "\n".join(formatted)
    except Exception as e:
        return f"[Search error: {str(e)}]"


@tool
def search_financial_news(ticker: str, days: int = 7) -> str:
    """Search for recent financial news about a specific stock.

    Args:
        ticker: Stock ticker symbol (e.g., TSLA, AAPL)
        days: Number of days to look back

    Returns:
        Recent news articles about the stock
    """
    client = get_tavily_client()
    if not client:
        return "[Search unavailable: No API key configured]"

    query = f"{ticker} stock news analysis"

    try:
        response = client.search(
            query=query,
            max_results=5,
            search_depth="advanced",
            include_domains=[
                "bloomberg.com",
                "reuters.com",
                "wsj.com",
                "cnbc.com",
                "seekingalpha.com",
                "yahoo.com/finance",
            ],
        )
        results = response.get("results", [])

        if not results:
            return f"No recent news found for {ticker}"

        formatted = [f"Recent news for {ticker}:\n"]
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', 'No title')}**\n"
                f"   Source: {r.get('url', 'N/A')}\n"
                f"   {r.get('content', 'No content')[:400]}...\n"
            )

        return "\n".join(formatted)
    except Exception as e:
        return f"[News search error: {str(e)}]"


@tool
def search_social_sentiment(ticker: str) -> str:
    """Search for social media sentiment about a stock.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Social media discussions and sentiment summary
    """
    client = get_tavily_client()
    if not client:
        return "[Search unavailable: No API key configured]"

    query = f"{ticker} stock reddit twitter sentiment discussion"

    try:
        response = client.search(
            query=query,
            max_results=5,
            include_domains=["reddit.com", "twitter.com", "stocktwits.com"],
        )
        results = response.get("results", [])

        if not results:
            return f"No social discussions found for {ticker}"

        formatted = [
            f"Social sentiment for {ticker} (Note: Verify before acting):\n"
        ]
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. {r.get('title', 'No title')}\n"
                f"   {r.get('content', 'No content')[:300]}...\n"
            )

        return "\n".join(formatted)
    except Exception as e:
        return f"[Social search error: {str(e)}]"


@tool
def get_stock_price(ticker: str) -> str:
    """Get current stock price and basic info.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Current price and basic metrics
    """
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        info = stock.info

        return f"""Stock: {ticker}
Current Price: ${info.get('currentPrice', 'N/A')}
Previous Close: ${info.get('previousClose', 'N/A')}
Market Cap: ${info.get('marketCap', 'N/A'):,}
P/E Ratio: {info.get('trailingPE', 'N/A')}
52 Week High: ${info.get('fiftyTwoWeekHigh', 'N/A')}
52 Week Low: ${info.get('fiftyTwoWeekLow', 'N/A')}
"""
    except ImportError:
        return "[yfinance not installed]"
    except Exception as e:
        return f"[Price lookup error: {str(e)}]"


# List of all available tools for agents
AGENT_TOOLS = [
    search_web,
    search_financial_news,
    search_social_sentiment,
    get_stock_price,
]


def get_tools_for_agent(agent_type: str) -> list:
    """Get appropriate tools for each agent type.

    Args:
        agent_type: One of 'bull', 'bear', 'cio'

    Returns:
        List of tools appropriate for that agent
    """
    if agent_type == "bull":
        return [search_web, search_financial_news, search_social_sentiment, get_stock_price]
    elif agent_type == "bear":
        return [search_web, search_financial_news, get_stock_price]
    elif agent_type == "cio":
        return [get_stock_price]  # CIO mainly synthesizes, less searching
    return AGENT_TOOLS
