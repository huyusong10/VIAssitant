"""CLI entry point for the Vibe Investment Engine.

Supports the full S5 three-phase pipeline with real-time status display:
- Phase transitions (discovery -> targeting -> validation)
- Per-round expert fan-out status
- Talent convergence summaries
- Planner decisions and Vibe mutation
- Final report output
- Interactive think viewer
"""

import argparse
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="vibe",
        description="Vibe Investment Multi-Agent Analysis Engine",
    )
    parser.add_argument(
        "--mode",
        default="full",
        choices=["discovery", "targeting", "validation", "1+2", "1+2+3", "full"],
        help="Workflow mode: discovery, targeting, validation, 1+2, 1+2+3, full (default: full)",
    )
    parser.add_argument(
        "--vibe",
        default=None,
        help="Investment thesis / vibe to analyze (skips interactive prompt)",
    )
    return parser.parse_args(argv)


def _display_expert_result(result: dict, show_think: bool = False) -> None:
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

    # Phase-specific content
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


def _display_talent_summary(summary: dict) -> None:
    """Display a Talent convergence summary."""
    phase = summary.get("phase", "?")
    round_num = summary.get("round_num", "?")
    score = summary.get("synthesis_score", "?")
    phase_name = PHASE_NAMES.get(phase, phase)

    console.print(
        Panel(
            f"[bold]核心矛盾点：[/bold]\n{summary.get('core_contradictions', '（无）')}\n\n"
            f"[bold]涌现假设：[/bold]\n{summary.get('emergent_hypothesis', '（无）')}\n\n"
            f"[bold]综合评分：[/bold] {score}/10",
            title=f"[bold yellow]Talent 收敛 · {phase_name} 第 {round_num} 轮[/bold yellow]",
            border_style="yellow",
        )
    )


def _display_planner_decision(decision: dict, phase: str, round_num: int) -> None:
    """Display a Planner decision."""
    action = decision.get("decision", "?")
    score = decision.get("sufficiency_score", "?")
    reasoning = decision.get("reasoning", "")
    phase_name = PHASE_NAMES.get(phase, phase)

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

    selected = decision.get("selected_experts", [])
    if selected:
        content += f"\n[bold]下一轮专家：[/bold] {selected}"

    console.print(
        Panel(
            content,
            title=f"[bold blue]Planner 裁决 · {phase_name} 第 {round_num} 轮[/bold blue]",
            border_style="blue",
        )
    )


def _prompt_think_view(all_results: list[dict]) -> None:
    """Interactive loop to let user inspect expert/talent think content."""
    if not all_results:
        return

    while True:
        console.print(
            "\n[dim]输入专家编号查看完整思考过程（如 [bold]2[/bold]），"
            "输入 [bold]/think talent[/bold] 查看 Talent 推理，"
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

        # Show all results from this expert (may span multiple rounds)
        for m in matched:
            _display_expert_result(m, show_think=True)


def run_cli(argv=None):
    """Main CLI entrypoint — runs the full S5 three-phase pipeline."""
    args = parse_args(argv)

    console.print(Panel(Text(BANNER, style="bold cyan"), border_style="cyan"))
    console.print(
        "[bold green]Vibe Investment Engine[/bold green] — "
        "[dim]多智能体发散-收敛投资分析引擎[/dim]\n"
    )

    vibe = args.vibe
    if not vibe:
        vibe = console.input("[bold yellow]请输入你的投资直觉（Vibe）：[/bold yellow] ").strip()

    if not vibe:
        console.print("[red]未提供 Vibe。退出。[/red]")
        return

    # Resolve mode to target phases
    target_phases = MODE_TO_PHASES.get(args.mode, MODE_TO_PHASES["full"])
    start_phase = target_phases[0]

    from vibe_engine.config import EXPERT_DIMENSIONS
    expert_dims = {d["id"]: d for d in EXPERT_DIMENSIONS}

    phase_labels = " → ".join(PHASE_NAMES.get(p, p) for p in target_phases)
    console.print(f"[bold]模式：[/bold] {args.mode} ({phase_labels})")
    console.print(f"[bold]Vibe：[/bold] {vibe}\n")

    # Build initial state — Planner will select experts on the first round
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

    # Run graph with streaming to show real-time progress
    try:
        from vibe_engine.graph import build_graph

        graph = build_graph()

        console.print(
            Rule(f"[bold magenta]阶段：{PHASE_NAMES.get(start_phase, start_phase)}[/bold magenta]")
        )

        console.print("[cyan]Planner 正在规划首轮专家组合...[/cyan]")

        with console.status("[cyan]分析进行中...[/cyan]", spinner="dots"):
            final_state = graph.invoke(initial_state)

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断。退出。[/yellow]")
        return
    except Exception as e:
        console.print(f"\n[red]错误：{e}[/red]")
        raise

    # Display accumulated results by phase/round
    _display_final_results(final_state, expert_dims)


def _display_final_results(state: dict, expert_dims: dict) -> None:
    """Display the complete results after graph execution."""
    talent_summaries = state.get("talent_summaries", [])
    planner_decisions = state.get("planner_decisions", [])
    expert_results = state.get("expert_results", [])
    final_report = state.get("final_report")
    abort_reason = state.get("abort_reason")
    vibe_history = state.get("vibe_history", [])

    # Display Talent summaries and Planner decisions in order
    for i, ts in enumerate(talent_summaries):
        phase = ts.get("phase", "?")
        round_num = ts.get("round_num", "?")
        phase_name = PHASE_NAMES.get(phase, phase)

        console.print(
            Rule(f"[bold magenta]{phase_name}  第 {round_num} 轮 — 结果[/bold magenta]")
        )

        # Show expert results for this phase/round
        round_experts = [
            r for r in expert_results
            if r.get("phase") == phase and r.get("round_num") == round_num
        ]
        if round_experts:
            for r in round_experts:
                _display_expert_result(r)

        _display_talent_summary(ts)

        # Planner decisions list includes the initial planning decision too,
        # so align by offset: talent #i corresponds to planner decision #(i+1)
        planner_idx = i + 1  # skip the initial planning decision
        if planner_idx < len(planner_decisions):
            _display_planner_decision(planner_decisions[planner_idx], phase, round_num)

    # Vibe evolution
    if len(vibe_history) > 1:
        console.print(Rule("[bold]Vibe 演变轨迹[/bold]"))
        for i, v in enumerate(vibe_history):
            label = "Vibe_0 (原始)" if i == 0 else f"Vibe_{i} (变异)"
            console.print(f"  [dim]{label}:[/dim] {v}")

    # Abort reason
    if abort_reason:
        console.print(
            Panel(
                abort_reason,
                title="[bold red]工作流终止[/bold red]",
                border_style="red",
            )
        )

    # Final report
    if final_report:
        console.print(Rule("[bold green]最终投资分析报告[/bold green]"))
        console.print(Markdown(final_report))

    # Expert results summary table
    if expert_results:
        console.print(Rule("[bold]专家分析摘要[/bold]"))
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("专家", style="cyan", max_width=20)
        table.add_column("阶段/轮次", style="dim", max_width=15)
        table.add_column("结论摘要", style="white", max_width=50)
        table.add_column("Think", style="dim", justify="right")
        for r in expert_results:
            phase_label = PHASE_NAMES.get(r.get('phase', ''), r.get('phase', '?'))
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

    # Interactive think viewer
    if expert_results:
        console.print(
            "\n[dim]输入专家编号可查看完整推理过程，按 Enter 退出[/dim]"
        )
        _prompt_think_view(expert_results)

    console.print("\n[bold green]Vibe 分析会话结束。[/bold green]")
