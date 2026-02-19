"""Minimal DeepSeek API connectivity check.

Usage:
    uv run python scripts/check_api.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vibe_engine.llm import get_chat_llm

def main():
    print("Connecting to DeepSeek Chat API...")
    llm = get_chat_llm()
    response = llm.invoke("Say exactly: Hello")
    print(f"Response: {response.content}")
    assert response.content, "Empty response from API"
    print("API check passed.")

if __name__ == "__main__":
    main()
