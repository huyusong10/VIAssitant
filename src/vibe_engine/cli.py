"""CLI entry point for the Vibe Investment Engine.

Supports the full S5 three-phase pipeline with real-time status display:
- Phase transitions (discovery -> targeting -> validation)
- Per-round expert fan-out status (S6.2: Real-time status display)
- Talent convergence summaries (S6.3: Formatted summary output)
- Planner decisions and Vibe mutation
- Final report output
- Interactive think viewer (S6.4: On-demand think viewing)
- Manual interruption support (S6.5: Ctrl+C handling)
"""

import argparse
import time
from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.markdown import Markdown
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.layout import Layout
from rich.align import Align

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


class StreamProcessor:
    """Handles graph stream events and updates the CLI UI state."""

    def __init__(self, start_phase: str):
        self.phase = start_phase
        self.round_num = 1
        self.pending_experts: set[int] = set()
        self.completed_experts: list[int] = []
        self.current_action = "Initializing..."
        self.history: list[Any] = []  # List of renderables (Panels, Rules) to keep above status
        self.expert_results = [] # Accumulate for final display
        
        # Load expert names for display
        from vibe_engine.config import EXPERT_DIMENSIONS
        self.expert_map = {d["id"]: d["name"] for d in EXPERT_DIMENSIONS}

    def process_chunk(self, chunk: dict) -> None:
        """Process a stream chunk and update UI state."""
        for node, updates in chunk.items():
            if node == "planner":
                self._handle_planner(updates)
            elif node == "fan_out":
                self._handle_fan_out(updates)
            elif node == "expert":
                self._handle_expert(updates)
            elif node == "talent":
                self._handle_talent(updates)
            elif node == "reporter":
                self._handle_reporter(updates)

    def _handle_planner(self, updates: dict):
        # Update phase/round if changed
        if "phase" in updates:
            self.phase = updates["phase"]
        if "round" in updates:
            self.round_num = updates["round"]

        # Planner Decision
        if "current_planner_decision" in updates:
            dec = updates["current_planner_decision"]
            if dec:
                self.history.append(self._render_planner_decision(dec))
        
        # Routing Action
        if "routing_action" in updates:
            action = updates["routing_action"]
            if action == "dispatch":
                selected = updates.get("selected_experts", [])
                if selected:
                    # We anticipate these experts will start soon
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
        # Fan out clears current results, so we're starting a fresh batch really

    def _handle_expert(self, updates: dict):
        results = updates.get("current_round_results", [])
        for r in results:
            eid = r.get("expert_id")
            if eid in self.pending_experts:
                self.pending_experts.remove(eid)
            if eid not in self.completed_experts:
                self.completed_experts.append(eid)
            
            # Store for final accumulation manually since we stream updates
            self.expert_results.append(r)
            
            # Add a mini log
            ename = self.expert_map.get(eid, "?")
            self.history.append(Text(f"✓ Expert {eid} ({ename}) finished analysis", style="dim green"))

    def _handle_talent(self, updates: dict):
        summaries = updates.get("talent_summaries", [])
        if summaries:
            latest = summaries[-1]
            self.history.append(self._render_talent_summary(latest))

    def _handle_reporter(self, updates: dict):
        # Report is handled in final accumulation, but we can log completion
        pass

    def get_renderable(self) -> Any:
        """Return the current dynamic status panel."""
        phase_name = PHASE_NAMES.get(self.phase, self.phase)
        
        status_text = Text()
        status_text.append(f"Phase: {phase_name} | Round: {self.round_num}\n", style="bold magenta")
        
        if self.pending_experts:
            status_text.append("\nThinking Experts:\n", style="bold yellow")
            for eid in sorted(self.pending_experts):
                ename = self.expert_map.get(eid, "?")
                status_text.append(f" • [{eid}] {ename}...\n", style="yellow")
        else:
            status_text.append(f"\n{self.current_action}\n", style="cyan")

        return Panel(
            Align.left(status_text),
            title="[bold green]System Status[/bold green]",
            border_style="green",
            padding=(1, 2)
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
            title=f"[bold yellow]Talent 收敛 · {phase_name} 第 {round_num} 轮[/bold yellow]",
            border_style="yellow",
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
            title="[bold blue]Planner 裁决[/bold blue]",
            border_style="blue",
        )


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


def _prompt_think_view(all_results: list[dict]) -> None:
    """Interactive loop to let user inspect expert/talent think content."""
    if not all_results:
        return

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

        # Show all results from this expert (may span multiple rounds)
        for m in matched:
            phase_label = PHASE_NAMES.get(m.get('phase', ''), m.get('phase', '?'))
            console.print(f"\n[bold]{phase_label} Round {m.get('round_num')}[/bold]")
            _display_expert_result(m, show_think=True)


def _display_final_results(state: dict) -> None:
    """Display the complete results after graph execution."""
    expert_results = state.get("expert_results", [])
    final_report = state.get("final_report")
    abort_reason = state.get("abort_reason")
    vibe_history = state.get("vibe_history", [])

    # We skip Talent/Planner here since they were shown in stream, 
    # unless we want to recap. Let's stick to Report + Recap Table.

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

    phase_labels = " → ".join(PHASE_NAMES.get(p, p) for p in target_phases)
    console.print(f"[bold]模式：[/bold] {args.mode} ({phase_labels})")
    console.print(f"[bold]Vibe：[/bold] {vibe}\n")

    # Build initial state
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

    # Run graph with streaming
    from vibe_engine.graph import build_graph
    graph = build_graph()
    
    processor = StreamProcessor(start_phase)
    final_state = initial_state # Fallback if interrupted immediately

    # Accumulated state for final display (reconstruct from stream or use last yield)
    # Actually graph.stream chunks are updates. We need to merge them to get final state.
    # But since we only need expert_results and report for final display, we can track them.
    # Better: just re-merge updates into a local state dict.
    
    accumulated_state = initial_state.copy()

    try:
        with Live(processor.get_renderable(), refresh_per_second=4, console=console) as live:
            console.print(Rule(f"[bold magenta]工作流启动：{PHASE_NAMES.get(start_phase, start_phase)}[/bold magenta]"))
            
            for chunk in graph.stream(initial_state, stream_mode="updates"):
                # Update accumulated state
                for node, update in chunk.items():
                    # Handle list fields with reducers separately to avoid overwriting
                    list_fields = ["expert_results", "talent_summaries", "planner_decisions"]
                    
                    for field in list_fields:
                        if field in update:
                            if field not in accumulated_state or not isinstance(accumulated_state[field], list):
                                accumulated_state[field] = []
                            # Start with existing, extend with new
                            # But wait: accumulated_state.update() below would clobber if we don't protect it
                            # So we extract the new items, then remove from update dict before calling update()?
                            # Better: update everything else, then extend these.
                            pass

                    # 1. Update scalar/last-write-wins fields
                    scalar_update = {k: v for k, v in update.items() if k not in list_fields}
                    accumulated_state.update(scalar_update)
                    
                    # 2. Append list fields
                    for field in list_fields:
                        if field in update:
                            if field not in accumulated_state:
                                accumulated_state[field] = []
                            accumulated_state[field].extend(update[field])

                    # Special handling for "vibe_history" which is a list but planner sends the FULL list
                    if "vibe_history" in update:
                        accumulated_state["vibe_history"] = update["vibe_history"]

                # Update UI
                processor.process_chunk(chunk)
                
                # Show any history items generated by the processor
                while processor.history:
                     item = processor.history.pop(0)
                     console.print(item)
                
                live.update(processor.get_renderable())

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断。正在生成当前结果...[/yellow]")
    except Exception as e:
        console.print(f"\n[red]错误：{e}[/red]")
        raise

    # Display accumulated results
    _display_final_results(accumulated_state)

if __name__ == "__main__":
    run_cli()
