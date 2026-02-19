"""CLI entry point for the Vibe Investment Engine.

Supports two modes:
1. **REPL mode** (default, no --vibe): Interactive loop for continuous analysis.
   Users can enter Vibes, use slash commands, and inspect results between runs.
2. **One-shot mode** (--vibe provided): Single analysis run, then exit.
   Backward compatible with the original S6 behavior.

Architecture (C1+C2+C3):
- VibeREPL: Main interactive loop with prompt_toolkit input + slash autocomplete
- StreamProcessor: Handles graph stream events and updates Live display
- run_analysis(): Extracted graph execution logic (used by both modes)
- run_cli(): Entry point that selects REPL vs one-shot

C2 enhancements:
- prompt_toolkit input with slash command autocomplete + descriptions
- Complete command set: /help, /stop, /clear, /status, /think, /experts,
  /summary, /mode, /export, /config
"""

import argparse
import os
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
    PHASE_REQUIREMENTS,
    display_welcome,
    display_final_results,
    render_analysis_header,
    render_completion_banner,
    render_phase_transition,
    render_elapsed_stats_table,
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


def _fmt_elapsed(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# ---------------------------------------------------------------------------
# StreamProcessor — graph event handler (C3 enhanced + white-box)
# ---------------------------------------------------------------------------


class StreamProcessor:
    """Handles graph stream events and updates the CLI UI state.

    C3 enhancements:
    - Expert-level timing (start/end per expert)
    - Progress bar in Live panel
    - Dispatch brief panel (why experts were chosen, what Vibe they receive)
    - Expert content summary on completion (conclusion + risk preview)
    - Phase transition detection and stats tracking
    - Elapsed statistics panel (C3.5)

    White-box process transparency:
    - Planner initial-round reasoning (why these experts, strategy analysis)
    - Planner evaluation-round decisions (sufficiency, iterate/proceed/abort)
    - Expert selection rationale at every dispatch
    - Phase transition announcements with statistics
    """

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

        # --- C3: Timing ---
        self.expert_timers: dict[int, float] = {}
        self.expert_elapsed: dict[int, float] = {}
        now = time.time()
        self.phase_start_time: float = now
        self.dispatch_start_time: float = now
        self.total_start_time: float = now
        self.phase_stats: list[dict] = []

        # --- C3: Progress ---
        self.total_experts_in_round: int = 0
        self.completed_in_round: int = 0

        # --- C3: Vibe tracking (for dispatch brief) ---
        self._current_vibe: str = ""
        # Track per-phase expert counts and round counts for stats
        self._phase_expert_count: int = 0
        self._phase_round_count: int = 0

        # --- White-box: track if initial planner was already shown ---
        self._initial_planner_shown: bool = False

    def process_chunk(self, chunk: dict) -> None:
        for node, updates in chunk.items():
            handler = getattr(self, f"_handle_{node}", None)
            if handler:
                handler(updates)

    def _handle_planner(self, updates: dict):
        old_phase = self.phase

        # Track vibe changes
        if "vibe" in updates:
            self._current_vibe = updates["vibe"]

        # Phase transition detection — before updating self.phase
        if "phase" in updates and updates["phase"] != old_phase:
            self._record_phase_stats(old_phase)
            self.history.append(
                render_phase_transition(
                    old_phase, updates["phase"], self.phase_stats[-1]
                )
            )
            self.phase_start_time = time.time()
            self._phase_expert_count = 0
            self._phase_round_count = 0

        if "phase" in updates:
            self.phase = updates["phase"]
        if "round" in updates:
            self.round_num = updates["round"]

        decision = updates.get("current_planner_decision")
        routing = updates.get("routing_action")

        # --- White-box: Show initial-round Planner reasoning ---
        if (
            decision
            and decision.get("sufficiency_score", 0) == 0
            and not self._initial_planner_shown
        ):
            self._initial_planner_shown = True
            self.history.append(self._render_planner_initial_brief(decision, updates))

        # Render evaluation-round decision (has real sufficiency score)
        if decision and decision.get("sufficiency_score", 0) > 0:
            self.history.append(self._render_planner_decision(decision))

        # Dispatch brief (when routing to experts)
        if routing == "dispatch":
            selected = updates.get("selected_experts", [])
            if selected:
                self.pending_experts = set(selected)
                self.completed_experts = []
                self.total_experts_in_round = len(selected)
                self.completed_in_round = 0
                self._phase_round_count += 1
                reasoning = decision.get("reasoning", "") if decision else ""
                vibe = updates.get("vibe", self._current_vibe)
                self.history.append(
                    self._render_dispatch_brief(selected, reasoning, vibe)
                )
        elif routing == "report":
            self.current_action = "Generating Final Report..."
            self.history.append(
                Panel(
                    "[bold cyan]所有阶段分析完成，正在生成最终投资报告...[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
        elif routing == "abort":
            self.current_action = "Aborting workflow..."

    def _handle_fan_out(self, updates: dict):
        now = time.time()
        self.dispatch_start_time = now
        for eid in self.pending_experts:
            self.expert_timers[eid] = now
        self.current_action = "Experts analyzing..."

    def _handle_expert(self, updates: dict):
        results = updates.get("current_round_results", [])
        for r in results:
            eid = r.get("expert_id")
            elapsed = time.time() - self.expert_timers.get(eid, time.time())
            self.expert_elapsed[eid] = elapsed
            if eid in self.pending_experts:
                self.pending_experts.remove(eid)
            if eid not in self.completed_experts:
                self.completed_experts.append(eid)
            self.expert_results.append(r)
            self.completed_in_round += 1
            self._phase_expert_count += 1

            self.history.append(self._render_expert_brief(r, elapsed))

    def _handle_talent(self, updates: dict):
        summaries = updates.get("talent_summaries", [])
        if summaries:
            self.history.append(self._render_talent_summary(summaries[-1]))

    def _handle_reporter(self, updates: dict):
        if updates.get("final_report"):
            self.history.append(
                Panel(
                    "[bold green]✓ 最终报告已生成[/bold green]",
                    border_style="green",
                    padding=(0, 1),
                )
            )

    # --- C3: Enhanced Live panel ---

    def get_renderable(self) -> Any:
        phase_name = PHASE_NAMES.get(self.phase, self.phase)
        now = time.time()
        total_elapsed = _fmt_elapsed(now - self.total_start_time)
        status_text = Text()

        # Header: phase + round + total elapsed
        status_text.append(
            f"{phase_name} · 第 {self.round_num} 轮", style="bold cyan"
        )
        status_text.append(f"  [{total_elapsed}]\n", style="cyan")

        if self.pending_experts or self.completed_in_round > 0:
            # Progress bar
            total = self.total_experts_in_round
            done = self.completed_in_round
            if total > 0:
                bar_width = 20
                filled = int(bar_width * done / total)
                bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
                dispatch_elapsed = _fmt_elapsed(now - self.dispatch_start_time)
                status_text.append(
                    f"{bar}  {done}/{total} experts  [{dispatch_elapsed}]\n\n"
                )

            # Completed experts (with timing)
            for eid in self.completed_experts:
                ename = self.expert_map.get(eid, "?")
                elapsed = self.expert_elapsed.get(eid, 0)
                status_text.append(
                    f"  \u2713 [{eid}] {ename}  ({_fmt_elapsed(elapsed)})\n",
                    style="green",
                )

            # In-progress experts (with live timer)
            for eid in sorted(self.pending_experts):
                ename = self.expert_map.get(eid, "?")
                running = now - self.expert_timers.get(eid, now)
                status_text.append(
                    f"  \u23f3 [{eid}] {ename}  ({_fmt_elapsed(running)})\n",
                    style="yellow",
                )
        else:
            status_text.append(f"\n{self.current_action}\n", style="cyan")

        return Panel(
            Align.left(status_text),
            title=f"[bold cyan]\u26a1 {phase_name}[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )

    # --- C3: Phase stats tracking ---

    def _record_phase_stats(self, phase: str):
        elapsed = time.time() - self.phase_start_time
        self.phase_stats.append({
            "phase": phase,
            "rounds": max(self._phase_round_count, 1),
            "experts": self._phase_expert_count,
            "elapsed": elapsed,
        })

    def finalize_stats(self):
        """Record stats for the final phase (called after stream ends)."""
        if not self.phase_stats or (
            self.phase_stats and self.phase_stats[-1]["phase"] != self.phase
        ):
            self._record_phase_stats(self.phase)

    # --- Render helpers ---

    def _render_planner_initial_brief(self, decision: dict, updates: dict):
        """White-box: Render Planner's initial-round reasoning."""
        phase_name = PHASE_NAMES.get(self.phase, self.phase)
        reasoning = decision.get("reasoning", "首轮规划")
        selected = updates.get("selected_experts", decision.get("selected_experts", []))

        expert_lines = []
        for eid in selected:
            ename = self.expert_map.get(eid, "?")
            expert_lines.append(f"  [{eid}] {ename}")
        experts_str = "\n".join(expert_lines) if expert_lines else "  （未指定）"

        phase_req = PHASE_REQUIREMENTS.get(self.phase, "")
        req_line = f"\n[bold]阶段目标：[/bold]{phase_req}" if phase_req else ""

        content = (
            f"[bold]Planner 策略分析：[/bold]\n"
            f"  {reasoning}\n"
            f"\n[bold]选定专家 ({len(selected)}人)：[/bold]\n"
            f"{experts_str}\n"
            f"{req_line}"
        )

        return Panel(
            content,
            title=f"[bold cyan]🧠 Planner 首轮规划 · {phase_name}[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )

    def _render_dispatch_brief(self, selected: list[int], reasoning: str, vibe: str):
        """Render a dispatch brief panel showing WHY experts were chosen."""
        phase_name = PHASE_NAMES.get(self.phase, self.phase)
        phase_req = PHASE_REQUIREMENTS.get(self.phase, "")

        expert_lines = []
        for eid in selected:
            ename = self.expert_map.get(eid, "?")
            expert_lines.append(f"  [{eid}] {ename}")
        experts_str = "\n".join(expert_lines)

        vibe_display = vibe if len(vibe) <= 120 else vibe[:117] + "..."

        content = ""
        if reasoning:
            content += f"[bold]调度策略：[/bold]\n  {reasoning}\n\n"
        content += f"[bold]选定专家 ({len(selected)}人)：[/bold]\n{experts_str}\n"
        content += f"\n[bold]下发指令：[/bold]\n  Vibe: {vibe_display}"
        content += f"\n  阶段: {phase_name}"
        if phase_req:
            content += f" · {phase_req}"

        return Panel(
            content,
            title=f"[bold cyan]📋 调度简报 · {phase_name} 第 {self.round_num} 轮[/bold cyan]",
            border_style="cyan",
        )

    def _render_expert_brief(self, result: dict, elapsed: float):
        """Render a brief content summary when an expert finishes."""
        eid = result.get("expert_id", "?")
        ename = result.get("expert_name", "?")
        conclusion = (result.get("conclusion") or "")[:80]
        risk = (result.get("risk_points") or "")[:80]
        think_len = len(result.get("think_content") or "")
        elapsed_str = _fmt_elapsed(elapsed)

        content = ""
        if conclusion:
            content += f"[bold]结论：[/bold]{conclusion}"
            if len(result.get("conclusion") or "") > 80:
                content += "..."
            content += "\n"
        if risk:
            content += f"[bold]风险：[/bold]{risk}"
            if len(result.get("risk_points") or "") > 80:
                content += "..."
            content += "\n"
        targets = result.get("targets", [])
        if targets:
            content += f"[bold]标的：[/bold]{', '.join(targets[:5])}\n"
        content += f"[italic]推理过程: {think_len:,} 字 | /think {eid} 查看[/italic]"

        return Panel(
            content,
            title=f"[bold green]\u2713 专家 {eid} · {ename} ({elapsed_str})[/bold green]",
            border_style="green",
            padding=(0, 1),
        )

    def _render_talent_summary(self, summary: dict):
        phase = summary.get("phase", "?")
        round_num = summary.get("round_num", "?")
        score = summary.get("synthesis_score", "?")
        phase_name = PHASE_NAMES.get(phase, phase)
        think_len = len(summary.get("think_content") or "")
        think_hint = f"\n\n[italic]推理过程: {think_len:,} 字 | /think talent 查看[/italic]" if think_len else ""
        return Panel(
            f"[bold]核心矛盾点：[/bold]\n{summary.get('core_contradictions', '（无）')}\n\n"
            f"[bold]涌现假设：[/bold]\n{summary.get('emergent_hypothesis', '（无）')}\n\n"
            f"[bold]综合评分：[/bold] {score}/10"
            f"{think_hint}",
            title=f"[bold cyan]🎯 Talent 收敛 · {phase_name} 第 {round_num} 轮[/bold cyan]",
            border_style="cyan",
        )

    def _render_planner_decision(self, decision: dict):
        """White-box: Render Planner's evaluation-round decision with full reasoning."""
        action = decision.get("decision", "?")
        score = decision.get("sufficiency_score", "?")
        reasoning = decision.get("reasoning", "")
        selected = decision.get("selected_experts", [])
        action_style = {
            "proceed": "[bold green]PROCEED ✓[/bold green]",
            "iterate": "[bold yellow]ITERATE ⟳[/bold yellow]",
            "abort": "[bold red]ABORT ✗[/bold red]",
        }.get(action, action)
        content = (
            f"[bold]决策：[/bold] {action_style}\n"
            f"[bold]充分度评分：[/bold] {score}/10\n"
            f"[bold]推理依据：[/bold] {reasoning}"
        )
        vibe_next = decision.get("vibe_next", "")
        if vibe_next and action == "iterate":
            content += f"\n\n[bold]Vibe 变异：[/bold]\n{vibe_next}"
        if selected and action == "iterate":
            expert_names = [
                f"[{eid}] {self.expert_map.get(eid, '?')}" for eid in selected
            ]
            content += f"\n\n[bold]下轮专家：[/bold] {', '.join(expert_names)}"
        if action == "proceed":
            from vibe_engine.config import PHASE_ORDER
            try:
                idx = PHASE_ORDER.index(self.phase)
                if idx + 1 < len(PHASE_ORDER):
                    next_name = PHASE_NAMES.get(PHASE_ORDER[idx + 1], "?")
                    content += f"\n\n[bold cyan]→ 即将进入: {next_name}[/bold cyan]"
                else:
                    content += "\n\n[bold cyan]→ 所有阶段完成，即将生成报告[/bold cyan]"
            except ValueError:
                pass

        return Panel(
            content,
            title="[bold cyan]⚖️ Planner 裁决[/bold cyan]",
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

    # C3.5: Record final phase stats and display elapsed statistics
    processor.finalize_stats()

    render_completion_banner(con, accumulated_state, elapsed)

    # C3.5: Show elapsed statistics table
    if processor.phase_stats or processor.expert_elapsed:
        con.print(
            render_elapsed_stats_table(
                phase_stats=processor.phase_stats,
                expert_elapsed=processor.expert_elapsed,
                expert_map=processor.expert_map,
                total_elapsed=elapsed,
            )
        )

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
# prompt_toolkit — Slash command completer (C2 autocomplete)
# ---------------------------------------------------------------------------


def _build_vibe_completer():
    """Build a prompt_toolkit completer for slash commands.

    Provides inline command suggestions with descriptions when the user
    types '/', similar to Claude Code's slash menu.
    """
    from prompt_toolkit.completion import Completer, Completion

    class SlashCompleter(Completer):
        """Auto-complete slash commands with descriptions inline.

        Triggered when user types '/' — shows all matching commands
        with their descriptions in a dropdown popup menu.  The menu
        stays open as the user keeps typing to narrow the results.
        """

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor.lstrip()

            # Only trigger for text starting with /
            if not text.startswith("/"):
                return

            # Extract the typed portion after /
            # If user already typed a space, they're entering args — stop
            after_slash = text[1:]
            if " " in after_slash:
                return

            typed = after_slash.lower()  # e.g. "" for "/", "he" for "/he"

            registry = get_registry()
            for cmd in registry.get_all_commands():
                cmd_name = cmd.name
                if cmd_name.startswith(typed):
                    # Build description: help_text + usage hint
                    usage_hint = f"  用法: /{cmd_name} {cmd.usage}" if cmd.usage else ""
                    meta = cmd.help_text + usage_hint

                    yield Completion(
                        # Insert the bare command (user adds args themselves)
                        f"/{cmd_name}",
                        start_position=-len(text),
                        display=f"/{cmd_name}",
                        display_meta=meta,
                    )

    return SlashCompleter()


def _build_prompt_style():
    """Build the prompt_toolkit style for the REPL prompt.

    Uses hex colors for a premium Oceanic theme that looks clean on
    both dark and light terminal backgrounds.
    """
    from prompt_toolkit.styles import Style
    return Style.from_dict({
        # Prompt
        "prompt": "bold #5ccfe6",

        # Completion menu — Oceanic palette
        "completion-menu":                        "bg:#1a2332 #c7d5e0",
        "completion-menu.completion":             "bg:#1a2332 #c7d5e0",
        "completion-menu.completion.current":     "bg:#0d7377 #ffffff bold",
        "completion-menu.meta.completion":         "bg:#1a2332 #5f8799",
        "completion-menu.meta.completion.current":  "bg:#0d7377 #a0e8eb",

        # Scrollbar
        "scrollbar.background": "bg:#1a2332",
        "scrollbar.button":     "bg:#0d7377",
    })


def _build_prompt_session():
    """Build a prompt_toolkit PromptSession with slash autocomplete.

    Features:
    - Typing '/' at the start of a line opens a dropdown of all commands
    - Each completion shows the command name + a description (display_meta)
    - Continue typing to narrow the list (e.g. '/ex' → /exit, /experts, /export)
    - Arrow keys or Tab to navigate, Enter to select
    - Input history persisted across sessions
    - Oceanic-themed color palette
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    histfile = os.path.expanduser("~/.config/vibe/input_history_ptk")
    os.makedirs(os.path.dirname(histfile), exist_ok=True)

    session = PromptSession(
        message=[("class:prompt", "vibe> ")],
        style=_build_prompt_style(),
        completer=_build_vibe_completer(),
        complete_while_typing=True,
        complete_in_thread=False,
        reserve_space_for_menu=12,
        history=FileHistory(histfile),
        enable_history_search=True,
    )
    return session


# ---------------------------------------------------------------------------
# VibeREPL — interactive loop (C1 + C2 prompt_toolkit)
# ---------------------------------------------------------------------------


class VibeREPL:
    """Interactive REPL for the Vibe Investment Engine.

    Provides a continuous prompt where users can:
    - Enter Vibe text to start analysis
    - Type '/' to see all available commands with descriptions (autocomplete)
    - Use /commands to inspect results, change settings, etc.
    - Ctrl+C to interrupt a running analysis
    - Ctrl+D or /exit to quit

    Uses prompt_toolkit for:
    - Slash command autocomplete with inline descriptions
    - Input history (persistent across sessions)
    - Better CJK character support
    """

    def __init__(self, mode: str = "full", target_console: Console | None = None):
        self.console = target_console or console
        self.mode = mode
        self.last_state: dict | None = None
        self.is_analyzing = False
        self._should_exit = False

        self._commands = get_registry()
        self._session = _build_prompt_session()

    def run(self):
        """Main REPL loop."""
        display_welcome(self.console, interactive=True)

        while not self._should_exit:
            try:
                raw = self._session.prompt().strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                continue

            if not raw:
                continue

            if raw.startswith("/"):
                self._dispatch_command(raw)
            else:
                self._handle_vibe(raw)

        self.console.print("\n再见！👋\n")

    def _dispatch_command(self, raw: str):
        """Build context and dispatch a slash command."""
        ctx = CommandContext(
            console=self.console,
            last_state=self.last_state,
            mode=self.mode,
            is_analyzing=self.is_analyzing,
            request_exit=self._request_exit,
            set_mode=self._set_mode,
            request_stop=None,
        )
        self._commands.dispatch(raw, ctx)

    def _handle_vibe(self, vibe: str):
        """Run analysis for the given vibe text."""
        self.is_analyzing = True
        try:
            self.last_state = run_analysis(vibe, self.mode, self.console)
            display_final_results(self.console, self.last_state, interactive_think=False)
            self.console.print(
                "\n[italic]使用 [bold]/think N[/bold] 查看专家推理 · "
                "[bold]/summary[/bold] 查看摘要 · 输入新 Vibe 继续分析[/italic]\n"
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
