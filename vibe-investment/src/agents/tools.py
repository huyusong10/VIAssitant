"""
工具集：搜索、数据获取等
"""
import asyncio
from typing import List, Dict, Any, Optional
from tavily import TavilyClient
from langchain_core.tools import tool
from langchain_core.callbacks import CallbackManagerForToolRun

from ..utils.config import settings


class SearchTool:
    """Tavily搜索工具封装"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.TAVILY_API_KEY
        self.client = None
        if self.api_key:
            self.client = TavilyClient(api_key=self.api_key)
    
    async def search(
        self, 
        query: str, 
        search_depth: str = "advanced",
        max_results: int = 5,
        include_answer: bool = True
    ) -> Dict[str, Any]:
        """
        执行搜索查询
        
        Args:
            query: 搜索关键词
            search_depth: "basic" 或 "advanced"
            max_results: 返回结果数量
            include_answer: 是否包含AI总结答案
        """
        if not self.client:
            return {
                "error": "Tavily API key not configured",
                "results": [],
                "answer": None
            }
        
        try:
            # Tavily是同步客户端，在线程中运行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.search(
                    query=query,
                    search_depth=search_depth,
                    max_results=max_results,
                    include_answer=include_answer
                )
            )
            return result
        except Exception as e:
            return {
                "error": str(e),
                "results": [],
                "answer": None
            }
    
    async def search_multi(
        self, 
        queries: List[str],
        search_depth: str = "advanced",
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """并行执行多个搜索查询"""
        tasks = [
            self.search(q, search_depth, max_results) 
            for q in queries
        ]
        return await asyncio.gather(*tasks)
    
    def format_results_for_llm(self, search_result: Dict[str, Any]) -> str:
        """将搜索结果格式化为LLM可读的文本"""
        if "error" in search_result and search_result["error"]:
            return f"Search Error: {search_result['error']}"
        
        formatted = []
        
        # 添加AI总结（如果有）
        answer = search_result.get("answer")
        if answer:
            formatted.append(f"AI Summary: {answer}\n")
        
        # 添加搜索结果
        results = search_result.get("results", [])
        if not results:
            return "No results found."
        
        formatted.append("Sources:")
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            content = result.get("content", "No content")
            url = result.get("url", "")
            score = result.get("score", 0)
            
            formatted.append(f"\n[{i}] {title} (Relevance: {score:.2f})")
            formatted.append(f"Content: {content[:300]}...")
            formatted.append(f"URL: {url}")
        
        return "\n".join(formatted)


# 为LangChain创建工具函数
search_tool_instance = SearchTool()


@tool
def web_search(query: str) -> str:
    """
    Search the web for current information about stocks, companies, or market trends.
    Use this when you need real-time data, news, or specific facts.
    
    Args:
        query: The search query string
    """
    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            search_tool_instance.search(query)
        )
        return search_tool_instance.format_results_for_llm(result)
    except Exception as e:
        return f"Search failed: {str(e)}"


@tool
def search_stock_info(ticker: str, info_type: str = "general") -> str:
    """
    Search for specific information about a stock ticker.
    
    Args:
        ticker: The stock ticker symbol (e.g., AAPL, TSLA)
        info_type: Type of information to search for:
            - "financials": Earnings, revenue, margins
            - "news": Recent news and developments  
            - "analyst": Analyst ratings and price targets
            - "sentiment": Social media sentiment
            - "general": Overall overview
    """
    queries = {
        "financials": f"{ticker} stock latest earnings revenue financial results 2024",
        "news": f"{ticker} stock latest news today developments",
        "analyst": f"{ticker} stock analyst rating price target upgrade downgrade",
        "sentiment": f"{ticker} stock twitter reddit sentiment discussion",
        "general": f"{ticker} stock company overview recent performance"
    }
    
    query = queries.get(info_type, queries["general"])
    
    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            search_tool_instance.search(query, max_results=8)
        )
        return search_tool_instance.format_results_for_llm(result)
    except Exception as e:
        return f"Search failed: {str(e)}"


# 工具列表，用于LangChain
TOOLS = [web_search, search_stock_info]
