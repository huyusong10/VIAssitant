"""Display components for the Vibe Investment Engine CLI.

Pure rendering functions — no state, no side effects beyond console output.
All styles follow the Oceanic theme (cyan chrome, semantic accents).

IMPORTANT: Avoids the ANSI 'dim' attribute (SGR 2) entirely because it
renders incorrectly in many terminals (Tabby, some iTerm2 profiles, etc.).
Secondary text is conveyed through lack of bold/color, or via 'italic'.

C3 additions:
- PHASE_REQUIREMENTS: per-phase output expectations (used in dispatch briefs)
- render_phase_transition(): animated phase transition banner with stats
- render_elapsed_stats_table(): final elapsed-time statistics after analysis
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.markdown import Markdown
from rich.table import Table
from rich.align import Align
from rich.columns import Columns

VERSION = "0.1.0"

PHASE_NAMES = {
    "discovery": "价值发现",
    "targeting": "标的锁定",
    "validation": "逻辑验证",
}

MODE_TO_PHASES = {
    "discovery": ["discovery"],
    "targeting": ["targeting"],
    "validation": ["validation"],
    "1+2": ["discovery", "targeting"],
    "1+2+3": ["discovery", "targeting", "validation"],
    "full": ["discovery", "targeting", "validation"],
}

# C3: Per-phase output requirements — displayed in dispatch briefs for context
PHASE_REQUIREMENTS = {
    "discovery": "挖掘核心逻辑链条与风险点",
    "targeting": "输出具体投资标的",
    "validation": "构建数据推导链验证标的",
}


def _fmt_elapsed(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def display_welcome(console: Console, interactive: bool = True):
    """Display the welcome banner and quick help.

    Uses Rule instead of Panel for the banner — better resize tolerance
    and avoids box-drawing issues in some terminals.
    Uses Rich Table for help items — proper CJK width calculation.
    """
    console.print()
    console.print(
        Rule(
            "[bold cyan]⚡ VIBE · Multi-Agent Investment Engine[/bold cyan]",
            style="cyan",
        )
    )
    console.print(Align.center(Text(f"v{VERSION} · Phase 1 · DeepSeek Powered")))
    console.print()

    if interactive:
        console.print("  输入你的投资直觉开始分析，或使用以下命令：")
        console.print()
        # Use Rich Table for proper CJK character width alignment.
        # Manual f-string padding like {text:<12} is broken for CJK
        # because Python counts characters, not display width.
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
            show_edge=False,
            pad_edge=True,
        )
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_row("/help", "显示帮助", "/think N", "查看专家思考")
        table.add_row("/experts", "专家列表", "/mode M", "切换模式")
        table.add_row("/summary", "查看摘要", "/exit", "退出")
        console.print(table)
        console.print()


def display_expert_result(console: Console, result: dict, show_think: bool = False):
    """Render a single expert result in the console."""
    expert_name = result.get("expert_name", "Unknown")
    expert_id = result.get("expert_id", "?")

    console.print(Rule(f"[bold cyan]专家 {expert_id} · {expert_name}[/bold cyan]"))

    console.print("\n[bold yellow]▶ 逻辑链条[/bold yellow]")
    console.print(result.get("logic_chain", "（无内容）"))

    console.print("\n[bold green]▶ 精简结论[/bold green]")
    console.print(result.get("conclusion", "（无内容）"))

    console.print("\n[bold red]▶ 核心风险点[/bold red]")
    console.print(result.get("risk_points", "（无内容）"))

    targets = result.get("targets", [])
    if targets:
        console.print("\n[bold blue]▶ 推荐标的[/bold blue]")
        for t in targets:
            console.print(f"  {t}")

    data_chain = result.get("data_logic_chain", "")
    if data_chain:
        console.print("\n[bold blue]▶ 数据推导链[/bold blue]")
        console.print(data_chain)

    if show_think and result.get("think_content"):
        console.print("\n[bold magenta]▶ 完整思考过程[/bold magenta]")
        console.print(
            Panel(
                result["think_content"],
                border_style="cyan",
                title="reasoning trace",
            )
        )


def display_expert_summary_table(console: Console, expert_results: list[dict]):
    """Display a summary table of all expert results."""
    console.print(Rule("[bold cyan]专家分析摘要[/bold cyan]"))
    table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("专家", style="cyan", max_width=20)
    table.add_column("阶段/轮次", max_width=15)
    table.add_column("结论摘要", max_width=50)
    table.add_column("Think", justify="right")
    for r in expert_results:
        phase_label = PHASE_NAMES.get(r.get("phase", ""), r.get("phase", "?"))
        round_label = f"R{r.get('round_num', '?')}"
        conclusion_preview = (r.get("conclusion") or "")[:80]
        think_len = len(r.get("think_content") or "")
        table.add_row(
            f"{r['expert_id']}·{r.get('expert_name', '?')}",
            f"{phase_label} {round_label}",
            conclusion_preview,
            f"{think_len} chars",
        )
    console.print(table)


def display_final_results(console: Console, state: dict, interactive_think: bool = False):
    """Display the complete results after graph execution."""
    expert_results = state.get("expert_results", [])
    final_report = state.get("final_report")
    abort_reason = state.get("abort_reason")
    vibe_history = state.get("vibe_history", [])

    if len(vibe_history) > 1:
        console.print(Rule("[bold cyan]Vibe 演变轨迹[/bold cyan]"))
        for i, v in enumerate(vibe_history):
            label = "Vibe_0 (原始)" if i == 0 else f"Vibe_{i} (变异)"
            console.print(f"  {label}: {v}")

    if abort_reason:
        console.print(
            Panel(abort_reason, title="[bold red]工作流终止[/bold red]", border_style="red")
        )

    if final_report:
        console.print(Rule("[bold cyan]最终投资分析报告[/bold cyan]"))
        console.print(Markdown(final_report))

    if expert_results:
        display_expert_summary_table(console, expert_results)

    if interactive_think and expert_results:
        console.print("\n输入专家编号可查看完整推理过程，按 Enter 退出")
        _prompt_think_view_legacy(console, expert_results)


def _prompt_think_view_legacy(console: Console, all_results: list[dict]):
    """Legacy interactive loop for think viewing (non-REPL mode)."""
    while True:
        console.print(
            "\n输入专家编号查看完整思考过程（如 [bold]2[/bold]），"
            "或按 [bold]Enter[/bold] 退出：",
            end=" ",
        )
        try:
            raw = input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            break
        try:
            target_id = int(raw)
        except ValueError:
            console.print("[red]请输入有效的专家编号（1-10）。[/red]")
            continue
        matched = [r for r in all_results if r.get("expert_id") == target_id]
        if not matched:
            console.print(f"[red]未找到专家 {target_id} 的结果。[/red]")
            continue
        for m in matched:
            phase_label = PHASE_NAMES.get(m.get("phase", ""), m.get("phase", "?"))
            console.print(f"\n[bold]{phase_label} Round {m.get('round_num')}[/bold]")
            display_expert_result(console, m, show_think=True)


def render_analysis_header(console: Console, vibe: str, mode: str, target_phases: list[str]):
    """Display analysis configuration before starting."""
    phase_labels = " → ".join(PHASE_NAMES.get(p, p) for p in target_phases)
    console.print(f"[bold]模式：[/bold] {mode} ({phase_labels})")
    console.print(f"[bold]Vibe：[/bold] {vibe}")
    console.print()


def render_completion_banner(console: Console, state: dict, elapsed: float):
    """Display a one-line completion summary after analysis."""
    expert_count = len(state.get("expert_results", []))
    phases_run = {r.get("phase", "") for r in state.get("expert_results", [])}

    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    has_report = state.get("final_report") is not None
    icon = "✓" if has_report else "⚠"
    style = "green" if has_report else "yellow"
    label = "完成" if has_report else "中断"

    console.print(
        f"\n[bold {style}]{icon} 分析{label}[/bold {style}]"
        f" · {len(phases_run)} 阶段"
        f" · {expert_count} 位专家"
        f" · 耗时 {time_str}"
    )


# ---------------------------------------------------------------------------
# C3.3 — Phase transition rendering
# ---------------------------------------------------------------------------


def render_phase_transition(
    old_phase: str, new_phase: str, phase_stat: dict
) -> Panel:
    """Render a visual phase transition banner with stats.

    Shows: old phase completion stats → new phase announcement.
    C3.3: Clear visual separation between phases with timing info.

    Args:
        old_phase: The phase that just completed.
        new_phase: The phase about to start.
        phase_stat: Stats dict with keys: phase, rounds, experts, elapsed.

    Returns:
        A Rich Panel renderable.
    """
    old_name = PHASE_NAMES.get(old_phase, old_phase)
    new_name = PHASE_NAMES.get(new_phase, new_phase)
    elapsed_str = _fmt_elapsed(phase_stat.get("elapsed", 0))
    rounds = phase_stat.get("rounds", 0)
    experts = phase_stat.get("experts", 0)

    new_req = PHASE_REQUIREMENTS.get(new_phase, "")
    req_line = f"\n[bold]阶段目标：[/bold]{new_req}" if new_req else ""

    content = (
        f"[bold green]✓ {old_name} 完成[/bold green]"
        f"  ({rounds} 轮 · {experts} 位专家 · {elapsed_str})\n"
        f"\n[bold cyan]→ 进入 {new_name}[/bold cyan]"
        f"{req_line}"
    )

    return Panel(
        content,
        title=f"[bold yellow]⚡ 阶段转换[/bold yellow]",
        border_style="yellow",
        padding=(0, 2),
    )


# ---------------------------------------------------------------------------
# C3.5 — Elapsed time statistics table
# ---------------------------------------------------------------------------


def render_elapsed_stats_table(
    phase_stats: list[dict],
    expert_elapsed: dict[int, float],
    expert_map: dict[int, str],
    total_elapsed: float,
) -> Panel:
    """Render a comprehensive timing statistics panel.

    C3.5: Shown after analysis completes — total, per-phase, per-expert breakdown.

    Args:
        phase_stats: List of per-phase stats dicts.
        expert_elapsed: Maps expert_id → elapsed seconds.
        expert_map: Maps expert_id → expert name.
        total_elapsed: Overall elapsed time.

    Returns:
        A Rich Panel renderable.
    """
    content_parts = []

    # Total elapsed
    content_parts.append(
        f"[bold]总耗时：[/bold] {_fmt_elapsed(total_elapsed)}\n"
    )

    # Per-phase breakdown
    if phase_stats:
        phase_table = Table(
            show_header=True, header_style="bold cyan",
            border_style="cyan", padding=(0, 1),
            title="[bold]阶段耗时[/bold]",
        )
        phase_table.add_column("阶段", style="cyan", min_width=10)
        phase_table.add_column("轮次", justify="center", min_width=6)
        phase_table.add_column("专家数", justify="center", min_width=6)
        phase_table.add_column("耗时", justify="right", min_width=8)
        phase_table.add_column("占比", justify="right", min_width=8)

        for ps in phase_stats:
            phase_name = PHASE_NAMES.get(ps["phase"], ps["phase"])
            elapsed = ps.get("elapsed", 0)
            pct = (elapsed / total_elapsed * 100) if total_elapsed > 0 else 0
            phase_table.add_row(
                phase_name,
                str(ps.get("rounds", 0)),
                str(ps.get("experts", 0)),
                _fmt_elapsed(elapsed),
                f"{pct:.1f}%",
            )

        content_parts.append(phase_table)

    # Per-expert breakdown (sorted by elapsed time, descending)
    if expert_elapsed:
        expert_table = Table(
            show_header=True, header_style="bold cyan",
            border_style="cyan", padding=(0, 1),
            title="\n[bold]专家耗时排名[/bold]",
        )
        expert_table.add_column("排名", justify="center", min_width=4)
        expert_table.add_column("专家", style="cyan", min_width=14)
        expert_table.add_column("耗时", justify="right", min_width=8)

        sorted_experts = sorted(
            expert_elapsed.items(), key=lambda x: x[1], reverse=True
        )
        for rank, (eid, elapsed) in enumerate(sorted_experts, 1):
            ename = expert_map.get(eid, f"专家 {eid}")
            expert_table.add_row(
                str(rank),
                f"[{eid}] {ename}",
                _fmt_elapsed(elapsed),
            )

        content_parts.append(expert_table)

    # Build final renderables
    from rich.console import Group
    return Panel(
        Group(*content_parts),
        title="[bold cyan]⏱ 耗时统计[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    )
