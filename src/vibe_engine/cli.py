"""CLI entry point for the Vibe Investment Engine.

Supports two modes:
1. **REPL mode** (default, no --vibe): Interactive loop for continuous analysis.
   Users can enter Vibes, use slash commands, and inspect results between runs.
2. **One-shot mode** (--vibe provided): Single analysis run, then exit.
   Backward compatible with the original S6 behavior.

Architecture (C1 refactored):
- VibeREPL: Main interactive loop with slash command dispatch
- StreamProcessor: Handles graph stream events and updates Live display
- run_analysis(): Extracted graph execution logic (used by both modes)
- run_cli(): Entry point that selects REPL vs one-shot
"""

import argparse
import os
import readline  # noqa: F401 — enables arrow keys & history in input()
import sys
import time
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich.align import Align

from vibe_engine.cli_display import (
    PHASE_NAMES,
    MODE_TO_PHASES,
    display_welcome,
    display_final_results,
    render_analysis_header,
    render_completion_banner,
)
from vibe_engine.cli_commands import get_registry, CommandContext

console = Console()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="vibe",
        description="Vibe Investment Multi-Agent Analysis Engine",
    )
    parser.add_argument(
        "--mode",
        default="full",
        choices=list(MODE_TO_PHASES.keys()),
        help="Workflow mode (default: full)",
    )
    parser.add_argument(
        "--vibe",
        default=None,
        help="Investment thesis / vibe to analyze (enables one-shot mode)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# StreamProcessor — graph event handler (unchanged from S6)
# ---------------------------------------------------------------------------


class StreamProcessor:
    """Handles graph stream events and updates the CLI UI state."""

    def __init__(self, start_phase: str):
        self.phase = start_phase
        self.round_num = 1
        self.pending_experts: set[int] = set()
        self.completed_experts: list[int] = []
        self.current_action = "Initializing..."
        self.history: list[Any] = []
        self.expert_results = []

        from vibe_engine.config import EXPERT_DIMENSIONS
        self.expert_map = {d["id"]: d["name"] for d in EXPERT_DIMENSIONS}

    def process_chunk(self, chunk: dict) -> None:
        for node, updates in chunk.items():
            handler = getattr(self, f"_handle_{node}", None)
            if handler:
                handler(updates)

    def _handle_planner(self, updates: dict):
        if "phase" in updates:
            self.phase = updates["phase"]
        if "round" in updates:
            self.round_num = updates["round"]
        if "current_planner_decision" in updates:
            dec = updates["current_planner_decision"]
            if dec:
                self.history.append(self._render_planner_decision(dec))
        if "routing_action" in updates:
            action = updates["routing_action"]
            if action == "dispatch":
                selected = updates.get("selected_experts", [])
                if selected:
                    self.pending_experts = set(selected)
                    self.completed_experts = []
                    self.current_action = f"Planner selected {len(selected)} experts..."
            elif action == "report":
                self.current_action = "Generating Final Report..."
            elif action == "abort":
                self.current_action = "Aborting workflow..."

    def _handle_fan_out(self, updates: dict):
        if self.pending_experts:
            self.current_action = "Dispatching Experts..."

    def _handle_expert(self, updates: dict):
        results = updates.get("current_round_results", [])
        for r in results:
            eid = r.get("expert_id")
            if eid in self.pending_experts:
                self.pending_experts.remove(eid)
            if eid not in self.completed_experts:
                self.completed_experts.append(eid)
            self.expert_results.append(r)
            ename = self.expert_map.get(eid, "?")
            self.history.append(
                Text(f"  ✓ Expert {eid} ({ename}) finished", style="green")
            )

    def _handle_talent(self, updates: dict):
        summaries = updates.get("talent_summaries", [])
        if summaries:
            self.history.append(self._render_talent_summary(summaries[-1]))

    def _handle_reporter(self, updates: dict):
        pass

    def get_renderable(self) -> Any:
        phase_name = PHASE_NAMES.get(self.phase, self.phase)
        status_text = Text()
        status_text.append(
            f"Phase: {phase_name} | Round: {self.round_num}\n", style="bold cyan"
        )
        if self.pending_experts:
            status_text.append("\nThinking Experts:\n", style="bold")
            for eid in sorted(self.pending_experts):
                ename = self.expert_map.get(eid, "?")
                status_text.append(f"  ⏳ [{eid}] {ename}...\n", style="dim")
        else:
            status_text.append(f"\n{self.current_action}\n", style="cyan")

        return Panel(
            Align.left(status_text),
            title="[bold cyan]⚡ System Status[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )

    def _render_talent_summary(self, summary: dict):
        phase = summary.get("phase", "?")
        round_num = summary.get("round_num", "?")
        score = summary.get("synthesis_score", "?")
        phase_name = PHASE_NAMES.get(phase, phase)
        return Panel(
            f"[bold]核心矛盾点：[/bold]\n{summary.get('core_contradictions', '（无）')}\n\n"
            f"[bold]涌现假设：[/bold]\n{summary.get('emergent_hypothesis', '（无）')}\n\n"
            f"[bold]综合评分：[/bold] {score}/10",
            title=f"[bold cyan]Talent 收敛 · {phase_name} 第 {round_num} 轮[/bold cyan]",
            border_style="cyan",
        )

    def _render_planner_decision(self, decision: dict):
        action = decision.get("decision", "?")
        score = decision.get("sufficiency_score", "?")
        reasoning = decision.get("reasoning", "")
        action_style = {
            "proceed": "[bold green]PROCEED[/bold green]",
            "iterate": "[bold yellow]ITERATE[/bold yellow]",
            "abort": "[bold red]ABORT[/bold red]",
        }.get(action, action)
        content = (
            f"[bold]决策：[/bold] {action_style}\n"
            f"[bold]充分度评分：[/bold] {score}/10\n"
            f"[bold]理由：[/bold] {reasoning}"
        )
        vibe_next = decision.get("vibe_next", "")
        if vibe_next and action == "iterate":
            content += f"\n\n[bold]Vibe 变异：[/bold]\n{vibe_next}"
        return Panel(
            content,
            title="[bold cyan]Planner 裁决[/bold cyan]",
            border_style="cyan",
        )


# ---------------------------------------------------------------------------
# Analysis runner — shared by REPL and one-shot modes
# ---------------------------------------------------------------------------


def run_analysis(vibe: str, mode: str, target_console: Console | None = None) -> dict:
    """Run a full analysis pipeline and return the accumulated state.

    Args:
        vibe: The investment thesis / vibe text.
        mode: Workflow mode string (e.g. "full", "1+2", "discovery").
        target_console: Console to use for output (defaults to module-level console).

    Returns:
        The accumulated state dict after graph execution.
    """
    con = target_console or console
    target_phases = MODE_TO_PHASES.get(mode, MODE_TO_PHASES["full"])
    start_phase = target_phases[0]

    render_analysis_header(con, vibe, mode, target_phases)

    initial_state = {
        "vibe": vibe,
        "vibe_original": vibe,
        "vibe_history": [vibe],
        "phase": start_phase,
        "round": 1,
        "phase_round": {"discovery": 0, "targeting": 0, "validation": 0},
        "expert_results": [],
        "current_round_results": [],
        "talent_summaries": [],
        "planner_decisions": [],
        "current_talent_summary": None,
        "current_planner_decision": None,
        "final_report": None,
        "messages": [],
        "selected_experts": [],
        "abort_reason": None,
        "routing_action": None,
        "target_phases": target_phases,
        "session_id": None,
    }

    from vibe_engine.graph import build_graph
    graph = build_graph()
    processor = StreamProcessor(start_phase)
    accumulated_state = initial_state.copy()
    start_time = time.time()

    try:
        with Live(
            processor.get_renderable(), refresh_per_second=4, console=con
        ) as live:
            con.print(
                Rule(
                    f"[bold cyan]工作流启动：{PHASE_NAMES.get(start_phase, start_phase)}"
                    f"[/bold cyan]"
                )
            )
            for chunk in graph.stream(initial_state, stream_mode="updates"):
                _merge_chunk(accumulated_state, chunk)
                processor.process_chunk(chunk)
                while processor.history:
                    con.print(processor.history.pop(0))
                live.update(processor.get_renderable())

    except KeyboardInterrupt:
        con.print("\n[yellow]用户中断。正在生成当前结果...[/yellow]")
    except Exception as e:
        con.print(f"\n[red]错误：{e}[/red]")
        raise

    elapsed = time.time() - start_time
    render_completion_banner(con, accumulated_state, elapsed)
    return accumulated_state


def _merge_chunk(accumulated: dict, chunk: dict):
    """Merge a stream chunk into the accumulated state dict."""
    list_fields = {"expert_results", "talent_summaries", "planner_decisions"}
    for _node, update in chunk.items():
        scalar_update = {k: v for k, v in update.items() if k not in list_fields}
        accumulated.update(scalar_update)
        for field in list_fields:
            if field in update:
                accumulated.setdefault(field, []).extend(update[field])
        if "vibe_history" in update:
            accumulated["vibe_history"] = update["vibe_history"]


# ---------------------------------------------------------------------------
# VibeREPL — interactive loop (C1)
# ---------------------------------------------------------------------------


class VibeREPL:
    """Interactive REPL for the Vibe Investment Engine.

    Provides a continuous prompt where users can:
    - Enter Vibe text to start analysis
    - Use /commands to inspect results, change settings, etc.
    - Ctrl+C to interrupt a running analysis
    - Ctrl+D or /exit to quit
    """

    # ANSI-colored prompt with readline width markers.
    # \001(\x01) and \002(\x02) tell readline the enclosed bytes are
    # zero-width, so cursor positioning stays correct for CJK chars.
    _PROMPT = "\x01\033[1;36m\x02vibe>\x01\033[0m\x02 "
    _HISTFILE = os.path.expanduser("~/.config/vibe/input_history")

    def __init__(self, mode: str = "full", target_console: Console | None = None):
        self.console = target_console or console
        self.mode = mode
        self.last_state: dict | None = None
        self.is_analyzing = False
        self._should_exit = False

        self._commands = get_registry()
        self._setup_readline()

    def _setup_readline(self):
        """Load readline history for arrow-key recall."""
        os.makedirs(os.path.dirname(self._HISTFILE), exist_ok=True)
        try:
            readline.read_history_file(self._HISTFILE)
        except (FileNotFoundError, OSError):
            pass
        readline.set_history_length(200)

    def _save_history(self):
        """Persist readline history to disk."""
        try:
            readline.write_history_file(self._HISTFILE)
        except OSError:
            pass

    def run(self):
        """Main REPL loop."""
        display_welcome(self.console, interactive=True)

        while not self._should_exit:
            try:
                raw = input(self._PROMPT).strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                print()  # newline after ^C
                continue

            if not raw:
                continue

            if raw.startswith("/"):
                self._dispatch_command(raw)
            else:
                self._handle_vibe(raw)

        self._save_history()
        self.console.print("\n[dim]再见！👋[/dim]\n")

    def _dispatch_command(self, raw: str):
        """Build context and dispatch a slash command."""
        ctx = CommandContext(
            console=self.console,
            last_state=self.last_state,
            mode=self.mode,
            is_analyzing=self.is_analyzing,
            request_exit=self._request_exit,
            set_mode=self._set_mode,
        )
        self._commands.dispatch(raw, ctx)

    def _handle_vibe(self, vibe: str):
        """Run analysis for the given vibe text."""
        self.is_analyzing = True
        try:
            self.last_state = run_analysis(vibe, self.mode, self.console)
            display_final_results(self.console, self.last_state, interactive_think=False)
            self.console.print(
                "\n[dim]使用 [bold]/think N[/bold] 查看专家推理 · "
                "[bold]/summary[/bold] 查看摘要 · 输入新 Vibe 继续分析[/dim]\n"
            )
        finally:
            self.is_analyzing = False

    def _request_exit(self):
        self._should_exit = True

    def _set_mode(self, new_mode: str):
        self.mode = new_mode


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_cli(argv=None):
    """Main CLI entrypoint — selects REPL or one-shot mode."""
    args = parse_args(argv)

    if args.vibe:
        # One-shot mode: run single analysis and exit (backward compatible)
        display_welcome(console, interactive=False)

        state = run_analysis(args.vibe, args.mode)
        display_final_results(console, state, interactive_think=True)
    else:
        # REPL mode: interactive loop
        repl = VibeREPL(mode=args.mode)
        repl.run()


if __name__ == "__main__":
    run_cli()
