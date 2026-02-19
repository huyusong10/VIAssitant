"""Display components for the Vibe Investment Engine CLI.

Extracted from cli.py to support the REPL architecture (C1).
Pure rendering functions — no state, no side effects beyond console output.
"""

from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.markdown import Markdown
from rich.table import Table
from rich.align import Align

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


def display_welcome(console: Console, interactive: bool = True):
    """Display the compact welcome banner and quick help."""
    title = Text()
    title.append("⚡ ", style="yellow")
    title.append("VIBE", style="bold")
    title.append(" · ", style="dim")
    title.append("Multi-Agent Investment Engine", style="cyan")

    subtitle = Text()
    subtitle.append(f"v{VERSION}", style="dim")
    subtitle.append(" · Phase 1 · ", style="dim")
    subtitle.append("DeepSeek Powered", style="dim blue")

    banner_content = Group(Align.center(title), Align.center(subtitle))

    console.print()
    console.print(Panel(banner_content, border_style="cyan", padding=(0, 2), expand=False))

    if interactive:
        console.print()
        console.print("  [dim]输入你的投资直觉开始分析，或使用以下命令：[/dim]")
        console.print()
        help_items = [
            ("/help", "显示帮助"),
            ("/think N", "查看专家思考"),
            ("/experts", "专家列表"),
            ("/mode M", "切换模式"),
            ("/summary", "查看摘要"),
            ("/exit", "退出"),
        ]
        for i in range(0, len(help_items), 2):
            left = help_items[i]
            right = help_items[i + 1] if i + 1 < len(help_items) else None
            line = f"  [bold cyan]{left[0]:<12}[/bold cyan] [dim]{left[1]:<12}[/dim]"
            if right:
                line += f"    [bold cyan]{right[0]:<12}[/bold cyan] [dim]{right[1]}[/dim]"
            console.print(line)
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
                border_style="magenta",
                title="[dim]reasoning trace[/dim]",
            )
        )


def display_expert_summary_table(console: Console, expert_results: list[dict]):
    """Display a summary table of all expert results."""
    console.print(Rule("[bold]专家分析摘要[/bold]"))
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("专家", style="cyan", max_width=20)
    table.add_column("阶段/轮次", style="dim", max_width=15)
    table.add_column("结论摘要", max_width=50)
    table.add_column("Think", style="dim", justify="right")
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
        console.print(Rule("[bold]Vibe 演变轨迹[/bold]"))
        for i, v in enumerate(vibe_history):
            label = "Vibe_0 (原始)" if i == 0 else f"Vibe_{i} (变异)"
            console.print(f"  [dim]{label}:[/dim] {v}")

    if abort_reason:
        console.print(
            Panel(abort_reason, title="[bold red]工作流终止[/bold red]", border_style="red")
        )

    if final_report:
        console.print(Rule("[bold green]最终投资分析报告[/bold green]"))
        console.print(Markdown(final_report))

    if expert_results:
        display_expert_summary_table(console, expert_results)

    if interactive_think and expert_results:
        console.print("\n[dim]输入专家编号可查看完整推理过程，按 Enter 退出[/dim]")
        _prompt_think_view_legacy(console, expert_results)


def _prompt_think_view_legacy(console: Console, all_results: list[dict]):
    """Legacy interactive loop for think viewing (non-REPL mode)."""
    while True:
        console.print(
            "\n[dim]输入专家编号查看完整思考过程（如 [bold]2[/bold]），"
            "或按 [bold]Enter[/bold] 退出：[/dim]",
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
        f" [dim]·[/dim] {len(phases_run)} 阶段"
        f" [dim]·[/dim] {expert_count} 位专家"
        f" [dim]·[/dim] 耗时 {time_str}"
    )
