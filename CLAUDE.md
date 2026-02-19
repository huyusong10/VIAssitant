# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI interactively
uv run python main.py

# Run with a pre-set vibe (skips prompt)
uv run python main.py --vibe "看好固态电池" --expert 2

# Run with a specific expert (1-10) and mode
uv run python main.py --vibe "..." --expert 7 --mode discovery

# Quick import / smoke test (no LLM call)
uv run python -c "import sys; sys.path.insert(0,'src'); from vibe_engine.graph import build_graph; print(build_graph())"
```

`src/` must be on `sys.path` — `main.py` handles this via `sys.path.insert`. When running scripts directly under `src/`, add the same insert.

## Architecture

This is a **LangGraph FSM** implementing a multi-agent investment analysis engine. Development follows a sprint plan (`plan/claude_plan.md`); only S0–S1 are currently implemented.

### Data flow (target, S1–S5)
```
User Vibe → Planner → fan-out Expert_Swarm (N parallel) → fan-in → Talent → Planner (loop/proceed/abort) → Final Report
```

### Key files

| File | Role |
|------|------|
| `src/vibe_engine/state.py` | Single source of truth for `VibeState` TypedDict. All node outputs are partial dicts that update this state. `expert_results` uses an Annotated reducer for fan-in appends. |
| `src/vibe_engine/graph.py` | Builds and compiles the LangGraph `StateGraph`. Currently S1: `START → expert → END`. Grows each sprint. |
| `src/vibe_engine/nodes/expert.py` | Factory `make_expert_node(expert_id)` — returns a closure that calls DeepSeek Reasoner and parses the 3-section output. Uses raw `openai.OpenAI` client (not LangChain) to capture `reasoning_content`. |
| `src/vibe_engine/prompts/` | Prompt templates. Expert templates are `.md` files (`expert_system.md`, `expert_user.md`); loaded at call time via `_load()`. Talent/Planner templates still inline — migrate to `.md` in S3/S4. |
| `src/vibe_engine/config.py` | `EXPERT_DIMENSIONS` (10 entries), `PHASE_CONFIGS`, model names, DeepSeek base URL. |
| `src/vibe_engine/llm.py` | `get_chat_llm()` / `get_reasoner_llm()` — LangChain wrappers. **Not used by expert node** (use raw client there to get `reasoning_content`). Available for Planner (chat) in S4. |
| `src/vibe_engine/cli.py` | Rich-based CLI. Must not be imported by graph/nodes (front-end separation constraint). |

### Model tiering (architecture constraint)
- **Planner** → `deepseek-chat` (fast routing, JSON extraction)
- **Expert / Talent** → `deepseek-reasoner` (deep reasoning); access via raw `openai.OpenAI` client to capture `msg.reasoning_content`

### Prompt file convention
All new prompt templates go in `src/vibe_engine/prompts/` as `.md` files. Load with `_load("filename.md")` from `prompts/__init__.py`. Templates use Python `str.format()` placeholders (`{name}`, `{vibe}`, etc.).

### FSM state update rules
- Nodes return **partial dicts** — only the fields they modify.
- `expert_results: Annotated[list[ExpertResult], lambda a, b: a + b]` — fan-in writes append, not overwrite.
- All other fields use last-write-wins.
- `cli.py` reads state but never writes back into the graph.

### Sprint plan
S0 (scaffold) and S1 (single expert) are done. Remaining: S2 fan-out/fan-in, S3 Talent, S4 Planner loop, S5 three-phase pipeline, S6 CLI interactivity, S7 mode switching, S8 E2E validation. See `plan/claude_plan.md` for per-task checklists.
