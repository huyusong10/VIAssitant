"""
配置管理和LLM工厂
"""
import os
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

# 加载环境变量
load_dotenv()


class Settings:
    """应用配置"""
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
    
    # 模型配置
    DEFAULT_MODEL_PROVIDER: str = os.getenv("DEFAULT_MODEL_PROVIDER", "anthropic")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "claude-3-5-sonnet-20241022")
    
    # 备用模型
    FALLBACK_MODEL_PROVIDER: str = os.getenv("FALLBACK_MODEL_PROVIDER", "openai")
    FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "gpt-4o")
    
    # 数据路径
    DATA_PATH: str = os.getenv("DATA_PATH", "data")
    
    # Tavily配置
    TAVILY_MAX_RESULTS: int = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置，返回缺失项列表"""
        missing = []
        if not cls.TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY")
        if not cls.ANTHROPIC_API_KEY and not cls.OPENAI_API_KEY and not cls.DEEPSEEK_API_KEY:
            missing.append("ANTHROPIC_API_KEY or OPENAI_API_KEY or DEEPSEEK_API_KEY")
        return missing


settings = Settings()


def get_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.3
) -> BaseChatModel:
    """
    获取LLM实例
    
    Args:
        provider: 'anthropic' 或 'openai'
        model_name: 具体模型名称
        temperature: 创造性程度
    """
    provider = provider or settings.DEFAULT_MODEL_PROVIDER
    
    if provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY
        model = model_name or settings.DEFAULT_MODEL
        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=4096
        )
    
    elif provider == "openai":
        api_key = settings.OPENAI_API_KEY
        model = model_name or settings.FALLBACK_MODEL
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=4096
        )
    
    elif provider == "deepseek":
        api_key = settings.DEEPSEEK_API_KEY
        model = model_name or "deepseek-chat"
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=temperature,
            max_tokens=4096
        )
    
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def get_fast_llm(temperature: float = 0.1) -> BaseChatModel:
    """获取快速LLM（用于简单任务）"""
    if settings.OPENAI_API_KEY:
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature
        )
    elif settings.DEEPSEEK_API_KEY:
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
            temperature=temperature
        )
    return get_llm(temperature=temperature)
