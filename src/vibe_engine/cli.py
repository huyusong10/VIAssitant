"""CLI entry point for the Vibe Investment Engine."""

import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.markdown import Markdown
from rich.table import Table
from rich.columns import Columns

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
        "--experts",
        type=str,
        default=None,
        help=(
            "Comma-separated expert IDs to dispatch (1-10). "
            "E.g. --experts 1,2,6 dispatches 宏观冲浪者, 技术布道者, 黑天鹅预言家. "
            "Defaults to 2,6,8 (3 experts) if not specified."
        ),
    )
    return parser.parse_args(argv)


def _parse_expert_ids(raw: str | None) -> list[int]:
    """Parse comma-separated expert IDs string into a list of ints."""
    if not raw:
        return [2, 6, 8]  # Default: 技术布道者, 黑天鹅预言家, 商业模式解构师

    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                eid = int(part)
                if 1 <= eid <= 10:
                    ids.append(eid)
                else:
                    console.print(f"[yellow]警告：忽略无效专家 ID {eid}（有效范围 1-10）[/yellow]")
            except ValueError:
                console.print(f"[yellow]警告：忽略无效输入 '{part}'[/yellow]")

    if not ids:
        console.print("[yellow]未提供有效专家 ID，使用默认专家组[/yellow]")
        return [2, 6, 8]

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for eid in ids:
        if eid not in seen:
            seen.add(eid)
            unique.append(eid)
    return unique


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
        "[dim]S2 · 专家集群扇出/扇入[/dim]\n"
    )

    vibe = args.vibe
    if not vibe:
        vibe = console.input("[bold yellow]请输入你的投资直觉（Vibe）：[/bold yellow] ").strip()

    if not vibe:
        console.print("[red]未提供 Vibe。退出。[/red]")
        return

    # Parse expert selection
    selected_experts = _parse_expert_ids(args.experts)

    console.print(f"\n[bold]模式：[/bold] {args.mode}")
    console.print(f"[bold]Vibe：[/bold] {vibe}")
    console.print(f"[bold]专家数量：[/bold] {len(selected_experts)}\n")

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
        "selected_experts": selected_experts,
        "abort_reason": None,
        "session_id": None,
    }

    # Show which experts are working
    expert_dims = {d["id"]: d for d in EXPERT_DIMENSIONS}
    expert_panels = []
    for eid in selected_experts:
        dim = expert_dims.get(eid, {"name": "Unknown", "description": ""})
        expert_panels.append(
            Panel(
                f"[bold]{dim['name']}[/bold]\n[dim]{dim['description']}[/dim]",
                title=f"[cyan]专家 {eid}[/cyan]",
                border_style="cyan",
                width=40,
            )
        )

    console.print(
        Panel(
            Columns(expert_panels, equal=True, expand=True),
            title=f"[bold cyan]{len(selected_experts)} 位专家正在并发分析中...[/bold cyan]",
            border_style="bright_cyan",
        )
    )

    # Run graph
    try:
        from vibe_engine.graph import build_graph

        expert_names = [expert_dims[eid]["name"] for eid in selected_experts]
        status_msg = ", ".join(expert_names)

        with console.status(
            f"[cyan]专家集群 [{status_msg}] 正在深度思考...[/cyan]",
            spinner="dots",
        ):
            graph = build_graph()
            final_state = graph.invoke(initial_state)

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断。退出。[/yellow]")
        return
    except Exception as e:
        console.print(f"\n[red]错误：{e}[/red]")
        raise

    # Display results
    results = final_state.get("expert_results", [])
    console.print(f"\n[bold green]✓ {len(results)} 位专家分析完成[/bold green]\n")

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

    # Isolation check summary
    console.print(f"\n")
    console.print(Rule("[bold]并发隔离性验证[/bold]"))
    if len(results) == len(selected_experts):
        console.print(
            f"  [green]✓[/green] 扇出数量 = {len(selected_experts)}，"
            f"回收数量 = {len(results)}，匹配成功"
        )
    else:
        console.print(
            f"  [red]✗[/red] 扇出数量 = {len(selected_experts)}，"
            f"回收数量 = {len(results)}，不匹配"
        )

    returned_ids = {r["expert_id"] for r in results}
    expected_ids = set(selected_experts)
    if returned_ids == expected_ids:
        console.print(f"  [green]✓[/green] 返回的专家 ID 集合与预期一致：{sorted(returned_ids)}")
    else:
        console.print(f"  [red]✗[/red] 专家 ID 不匹配。预期 {sorted(expected_ids)}，实际 {sorted(returned_ids)}")

    # Check uniqueness of expert analyses (basic isolation test)
    contents = [r.get("logic_chain", "") for r in results]
    if len(set(contents)) == len(contents):
        console.print(f"  [green]✓[/green] 各专家逻辑链条内容互不相同，上下文隔离正常")
    else:
        console.print(f"  [yellow]⚠[/yellow] 存在相同的逻辑链条内容，请人工检查隔离性")

    # Interactive think viewer
    if results:
        console.print(
            f"\n[dim]提示：输入专家编号可查看完整推理过程，或按 Enter 退出[/dim]"
        )
        _prompt_think_view(results)

    console.print("\n[bold green]Vibe 分析会话结束。[/bold green]")
