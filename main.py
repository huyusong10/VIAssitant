"""Program entry point."""

import sys
import os

# Make src/ importable when running as `uv run python main.py`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from vibe_engine.cli import run_cli


def main():
    run_cli()


if __name__ == "__main__":
    main()
