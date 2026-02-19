# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI interactively
uv run python main.py

# Run with a pre-set vibe (skips prompt)
uv run python main.py --vibe "看好固态电池"

# Run specific mode combinations
uv run python main.py --vibe "..." --mode 1+2      # 价值发现 + 标的锁定
uv run python main.py --vibe "..." --mode full      # 完整三阶段

# Quick import / smoke test (no LLM call)
uv run python -c "import sys; sys.path.insert(0,'src'); from vibe_engine.graph import build_graph; print(build_graph())"
```

`src/` must be on `sys.path` — `main.py` handles this via `sys.path.insert`. When running scripts directly under `src/`, add the same insert.

## Architecture

This is a **LangGraph FSM** implementing a multi-agent investment analysis engine. Development follows a sprint plan (`plan/claude_plan.md`); S0–S5 are implemented.

### Data flow (Planner-first topology — Phase A corrected)
```
User Vibe → Planner (select experts / evaluate / decide)
              ├── dispatch → fan_out → Expert_Swarm (N parallel via Send())
              │                → fan-in (reducer) → Talent (convergence)
              │                    → back to Planner (loop)
              ├── report → Reporter → Final Report → END
              └── abort → END

Each cycle: Planner → Expert_Swarm → Talent → Planner
  - First round: Planner receives Vibe, selects experts → dispatch
  - After Talent: Planner evaluates sufficiency
    - iterate → mutate Vibe, select new experts → dispatch (same phase)
    - proceed + next phase → transition phase → dispatch
    - proceed + last phase → reporter
    - abort → END
```

### Three-phase pipeline
1. **Discovery** (价值发现): max 5 rounds, 3-6 experts, Talent as strategist
2. **Targeting** (标的锁定): max 2 rounds, 2-4 experts, Talent as stock_picker
3. **Validation** (逻辑验证): max 1 round, 1-3 experts, Talent as auditor

Mode switching via `--mode` controls which phases run (`discovery`, `targeting`, `validation`, `1+2`, `1+2+3`, `full`).

### Key files

| File | Role |
|------|------|
| `src/vibe_engine/state.py` | Single source of truth for `VibeState` TypedDict. All node outputs are partial dicts. `expert_results`, `talent_summaries`, `planner_decisions` use Annotated reducers for append. `ExpertResult` includes `phase`/`round_num` for filtering. `routing_action` drives graph conditional edges. `target_phases` controls mode switching. |
| `src/vibe_engine/graph.py` | Builds and compiles the LangGraph `StateGraph`. Planner-first topology: `planner → fan_out → expert(s) → talent → planner (loop)`. |
| `src/vibe_engine/nodes/expert.py` | `expert_node(state: ExpertInput)` — calls DeepSeek Reasoner, parses 3-section output + phase-specific fields (targets, data_logic_chain). Uses raw `openai.OpenAI` client to capture `reasoning_content`. |
| `src/vibe_engine/nodes/talent.py` | `talent_node(state)` — convergence node. Cross-compares expert results, outputs core_contradictions, emergent_hypothesis, synthesis_score. Role switches by phase. |
| `src/vibe_engine/nodes/planner.py` | `planner_node(state)` — entry point and control valve. First round: selects experts based on Vibe. Subsequent rounds: evaluates Talent result, decides proceed/iterate/abort, generates Vibe mutations. Returns `routing_action` for graph routing. Uses DeepSeek Chat. |
| `src/vibe_engine/nodes/reporter.py` | `reporter_node(state)` — generates final structured investment report from all accumulated analysis. Uses DeepSeek Chat. |
| `src/vibe_engine/prompts/` | Prompt templates. Expert: `.md` files in `experts/`. Talent/Planner/Report templates inline in `__init__.py`. |
| `src/vibe_engine/config.py` | `EXPERT_DIMENSIONS` (10 entries), `PHASE_CONFIGS`, `PHASE_ORDER`, model names, DeepSeek base URL. |
| `src/vibe_engine/llm.py` | `get_chat_llm()` / `get_reasoner_llm()` — LangChain wrappers. **Not used by expert/talent nodes** (they use raw client for `reasoning_content`). |
| `src/vibe_engine/cli.py` | Rich-based CLI with full pipeline display. Must not be imported by graph/nodes (front-end separation constraint). |

### Model tiering (architecture constraint)
- **Planner / Reporter** → `deepseek-chat` (fast routing, JSON extraction, report writing)
- **Expert / Talent** → `deepseek-reasoner` (deep reasoning); access via raw `openai.OpenAI` client to capture `msg.reasoning_content`

### Prompt file convention
Expert prompt templates live in `src/vibe_engine/prompts/experts/expert_N.md`. Generic template in `expert_system.md`. Phase-specific instructions (targeting: require targets, validation: require data chain) injected via `EXPERT_PHASE_INSTRUCTIONS`. Talent/Planner/Report prompts are inline in `prompts/__init__.py` — use Python `str.format()` placeholders.

### FSM state update rules
- Nodes return **partial dicts** — only the fields they modify.
- `expert_results`, `talent_summaries`, `planner_decisions`: Annotated with append reducers — fan-in writes append, not overwrite.
- All other fields use last-write-wins.
- `cli.py` reads state but never writes back into the graph.
- `expert_results` is a full historical archive (never cleared). Talent filters by `phase`/`round_num` to get current round results.
- Planner sets `routing_action` to drive graph conditional edges (`"dispatch"` / `"report"` / `"abort"`).

### Sprint plan
S0–S5 are done. Remaining: S6 CLI interactivity (real-time streaming, `/think`, `/stop`), S7 config file override, S8 E2E validation. See `plan/claude_plan.md` for per-task checklists.
