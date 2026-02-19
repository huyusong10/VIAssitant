"""CLI entry point for the Vibe Investment Engine."""

import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.markdown import Markdown
from rich.table import Table

console = Console()

BANNER = """\
██╗   ██╗██╗██████╗ ███████╗
██║   ██║██║██╔══██╗██╔════╝
██║   ██║██║██████╔╝█████╗
╚██╗ ██╔╝██║██╔══██╗██╔══╝
 ╚████╔╝ ██║██████╔╝███████╗
  ╚═══╝  ╚═╝╚═════╝ ╚══════╝
   Investment Multi-Agent Engine  •  Phase 1
"""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="vibe",
        description="Vibe Investment Multi-Agent Analysis Engine",
    )
    parser.add_argument(
        "--mode",
        default="full",
        choices=["discovery", "targeting", "validation", "1+2", "1+2+3", "full"],
        help="Workflow mode to run (default: full)",
    )
    parser.add_argument(
        "--vibe",
        default=None,
        help="Investment thesis / vibe to analyze (skips interactive prompt)",
    )
    parser.add_argument(
        "--expert",
        type=int,
        default=2,
        choices=list(range(1, 11)),
        help=(
            "Expert dimension to use in S1 single-expert mode (1-10, default: 2). "
            "1=宏观冲浪者 2=技术布道者 3=成长股狂热者 4=资金博弈操盘手 5=深度价值卫道士 "
            "6=黑天鹅预言家 7=合规审查官 8=商业模式解构师 9=行为金融学家 10=第二层思维者"
        ),
    )
    return parser.parse_args(argv)


def _display_expert_result(result: dict, show_think: bool = False) -> None:
    """Render a single expert result in the console."""
    expert_name = result.get("expert_name", "Unknown")
    expert_id = result.get("expert_id", "?")

    console.print(Rule(f"[bold cyan]专家 {expert_id} · {expert_name}[/bold cyan]"))

    # Logic chain
    console.print("\n[bold yellow]▶ 逻辑链条[/bold yellow]")
    console.print(result.get("logic_chain", "（无内容）"))

    # Conclusion
    console.print("\n[bold green]▶ 精简结论[/bold green]")
    console.print(result.get("conclusion", "（无内容）"))

    # Risk points
    console.print("\n[bold red]▶ 核心风险点[/bold red]")
    console.print(result.get("risk_points", "（无内容）"))

    # Think content (on demand)
    if show_think and result.get("think_content"):
        console.print("\n[bold magenta]▶ 完整思考过程 (<think>)[/bold magenta]")
        console.print(
            Panel(
                result["think_content"],
                border_style="magenta",
                title="[dim]reasoning trace[/dim]",
            )
        )


def _prompt_think_view(results: list[dict]) -> None:
    """Interactive loop to let user inspect expert think content."""
    if not results:
        return

    while True:
        console.print(
            "\n[dim]输入专家编号查看完整思考过程（如 [bold]2[/bold]），"
            "或按 [bold]Enter[/bold] 跳过：[/dim]",
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

        matched = [r for r in results if r.get("expert_id") == target_id]
        if not matched:
            console.print(f"[red]未找到专家 {target_id} 的结果。[/red]")
            continue

        _display_expert_result(matched[0], show_think=True)


def run_cli(argv=None):
    """Main CLI entrypoint."""
    args = parse_args(argv)

    console.print(Panel(Text(BANNER, style="bold cyan"), border_style="cyan"))
    console.print(
        "[bold green]Vibe Investment Engine[/bold green] — "
        "[dim]S1 · 单专家直通车[/dim]\n"
    )

    vibe = args.vibe
    if not vibe:
        vibe = console.input("[bold yellow]请输入你的投资直觉（Vibe）：[/bold yellow] ").strip()

    if not vibe:
        console.print("[red]未提供 Vibe。退出。[/red]")
        return

    console.print(f"\n[bold]模式：[/bold] {args.mode}")
    console.print(f"[bold]Vibe：[/bold] {vibe}\n")

    # Build initial state
    from vibe_engine.config import EXPERT_DIMENSIONS
    initial_state = {
        "vibe": vibe,
        "vibe_original": vibe,
        "vibe_history": [vibe],
        "phase": "discovery",
        "round": 1,
        "phase_round": {"discovery": 0, "targeting": 0, "validation": 0},
        "expert_results": [],
        "talent_summaries": [],
        "planner_decisions": [],
        "current_talent_summary": None,
        "current_planner_decision": None,
        "final_report": None,
        "messages": [],
        "selected_experts": [args.expert],
        "abort_reason": None,
        "session_id": None,
    }

    # Show which expert is working
    expert_dim = next(
        (d for d in EXPERT_DIMENSIONS if d["id"] == args.expert),
        {"name": "Unknown", "description": ""},
    )
    console.print(
        Panel(
            f"[bold]{expert_dim['name']}[/bold]\n[dim]{expert_dim['description']}[/dim]",
            title=f"[cyan]专家 {args.expert} 正在分析中...[/cyan]",
            border_style="cyan",
        )
    )

    # Run graph
    try:
        from vibe_engine.graph import build_graph

        with console.status(
            f"[cyan]专家 [{expert_dim['name']}] 正在深度思考...[/cyan]",
            spinner="dots",
        ):
            graph = build_graph(expert_id=args.expert)
            final_state = graph.invoke(initial_state)

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断。退出。[/yellow]")
        return
    except Exception as e:
        console.print(f"\n[red]错误：{e}[/red]")
        raise

    # Display results
    console.print(f"\n[bold green]✓ 分析完成[/bold green]\n")

    results = final_state.get("expert_results", [])
    for result in results:
        _display_expert_result(result, show_think=False)

    # Summary table
    console.print(f"\n")
    console.print(Rule("[bold]分析摘要[/bold]"))
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("专家", style="cyan")
    table.add_column("结论摘要", style="white", max_width=80)
    table.add_column("Think 内容长度", style="dim")
    for r in results:
        conclusion_preview = (r.get("conclusion") or "")[:100]
        think_len = len(r.get("think_content") or "")
        table.add_row(
            f"{r['expert_id']}·{r['expert_name']}",
            conclusion_preview,
            f"{think_len} chars",
        )
    console.print(table)

    # Interactive think viewer
    if results:
        console.print(
            f"\n[dim]提示：输入专家编号可查看完整推理过程，或按 Enter 退出[/dim]"
        )
        _prompt_think_view(results)

    console.print("\n[bold green]Vibe 分析会话结束。[/bold green]")
