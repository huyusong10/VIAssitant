"""Slash command system for the Vibe CLI REPL.

Provides a CommandRegistry for registering and dispatching slash commands,
plus built-in command implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule


@dataclass
class CommandContext:
    """Shared context passed to every command handler."""

    console: Console
    last_state: dict | None = None
    mode: str = "full"
    is_analyzing: bool = False
    # Callbacks
    request_exit: Callable[[], None] | None = None
    set_mode: Callable[[str], None] | None = None


@dataclass
class Command:
    """A registered slash command."""

    name: str
    handler: Callable[[CommandContext, list[str]], None]
    help_text: str
    aliases: list[str] = field(default_factory=list)
    usage: str = ""


class CommandRegistry:
    """Registry for slash commands with alias support."""

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}

    def register(
        self,
        name: str,
        handler: Callable[[CommandContext, list[str]], None],
        help_text: str,
        aliases: list[str] | None = None,
        usage: str = "",
    ):
        cmd = Command(
            name=name, handler=handler, help_text=help_text,
            aliases=aliases or [], usage=usage,
        )
        self._commands[name] = cmd
        for alias in cmd.aliases:
            self._aliases[alias] = name

    def dispatch(self, raw_input: str, ctx: CommandContext) -> bool:
        """Parse and dispatch a slash command. Returns True if recognized."""
        parts = raw_input.strip().split(None, 1)
        if not parts:
            return False

        cmd_name = parts[0].lower().lstrip("/")
        args = (parts[1].split() if len(parts) > 1 else [])

        canonical = self._aliases.get(cmd_name, cmd_name)
        if canonical in self._commands:
            try:
                self._commands[canonical].handler(ctx, args)
            except Exception as e:
                ctx.console.print(f"[red]命令执行错误：{e}[/red]")
            return True

        ctx.console.print(
            f"[red]未知命令：/{cmd_name}[/red]  使用 /help 查看可用命令"
        )
        return False

    def get_all_commands(self) -> list[Command]:
        return list(self._commands.values())


# ---------------------------------------------------------------------------
# Built-in command implementations
# ---------------------------------------------------------------------------


def cmd_help(ctx: CommandContext, args: list[str]):
    """Show help for all commands or a specific command."""
    registry = get_registry()

    if args:
        cmd_name = args[0].lstrip("/")
        canonical = registry._aliases.get(cmd_name, cmd_name)
        if canonical in registry._commands:
            cmd = registry._commands[canonical]
            usage_str = f" {cmd.usage}" if cmd.usage else ""
            ctx.console.print(f"\n[bold cyan]/{cmd.name}{usage_str}[/bold cyan]")
            ctx.console.print(f"  {cmd.help_text}")
            if cmd.aliases:
                ctx.console.print(
                    f"  [italic]别名：{', '.join('/' + a for a in cmd.aliases)}[/italic]"
                )
            ctx.console.print()
        else:
            ctx.console.print(f"[red]未知命令：/{cmd_name}[/red]")
        return

    ctx.console.print()
    table = Table(
        title="[bold]可用命令[/bold]",
        show_header=True, header_style="bold cyan",
        border_style="cyan", padding=(0, 2),
    )
    table.add_column("命令", style="cyan", min_width=16)
    table.add_column("说明")
    for cmd in registry.get_all_commands():
        usage_str = f" {cmd.usage}" if cmd.usage else ""
        table.add_row(f"/{cmd.name}{usage_str}", cmd.help_text)
    ctx.console.print(table)
    ctx.console.print(
        "\n[italic]提示：直接输入文本即作为 Vibe 启动分析 · Ctrl+C 中断分析[/italic]\n"
    )


def cmd_exit(ctx: CommandContext, args: list[str]):
    """Exit the REPL."""
    if ctx.request_exit:
        ctx.request_exit()


def cmd_clear(ctx: CommandContext, args: list[str]):
    """Clear the terminal screen."""
    ctx.console.clear()


def cmd_status(ctx: CommandContext, args: list[str]):
    """Show the status of the last analysis."""
    from vibe_engine.cli_display import PHASE_NAMES

    if ctx.last_state is None:
        ctx.console.print("尚未进行任何分析。输入 Vibe 开始。")
        return

    state = ctx.last_state
    phase = state.get("phase", "?")
    phase_name = PHASE_NAMES.get(phase, phase)
    round_num = state.get("round", 0)
    expert_count = len(state.get("expert_results", []))
    has_report = state.get("final_report") is not None
    was_aborted = state.get("abort_reason") is not None
    vibe = state.get("vibe_original", "?")

    if has_report:
        status, status_style = "✓ 完成", "green"
    elif was_aborted:
        status, status_style = "✗ 终止", "red"
    else:
        status, status_style = "⚠ 中断", "yellow"

    ctx.console.print(Panel(
        f"[bold]Vibe：[/bold] {vibe}\n"
        f"[bold]状态：[/bold] [{status_style}]{status}[/{status_style}]\n"
        f"[bold]最后阶段：[/bold] {phase_name} · 第 {round_num} 轮\n"
        f"[bold]专家数据：[/bold] {expert_count} 条\n"
        f"[bold]模式：[/bold] {ctx.mode}",
        title="[bold cyan]分析状态[/bold cyan]", border_style="cyan",
    ))


def cmd_think(ctx: CommandContext, args: list[str]):
    """View expert or Talent thinking process."""
    from vibe_engine.cli_display import PHASE_NAMES, display_expert_result

    if ctx.last_state is None:
        ctx.console.print("尚无分析结果。请先输入 Vibe 进行分析。")
        return

    expert_results = ctx.last_state.get("expert_results", [])
    talent_summaries = ctx.last_state.get("talent_summaries", [])

    if not args:
        ctx.console.print("\n[bold]可查看的推理过程：[/bold]")
        seen = set()
        for r in expert_results:
            eid = r.get("expert_id")
            if eid not in seen:
                seen.add(eid)
                ename = r.get("expert_name", "?")
                think_len = len(r.get("think_content") or "")
                phase_label = PHASE_NAMES.get(r.get("phase", ""), "?")
                ctx.console.print(
                    f"  [cyan]{eid:>2}[/cyan] · {ename}"
                    f"  ({phase_label} R{r.get('round_num', '?')}, "
                    f"{think_len} chars)"
                )
        if talent_summaries:
            ctx.console.print(f"  [yellow]talent[/yellow] · Talent 收敛节点")
        ctx.console.print("\n[italic]用法：/think <编号> 或 /think talent[/italic]")
        return

    target = args[0].strip().lower()

    if target == "talent":
        if not talent_summaries:
            ctx.console.print("无 Talent 分析数据。")
            return
        for ts in talent_summaries:
            phase_label = PHASE_NAMES.get(ts.get("phase", ""), "?")
            ctx.console.print(
                f"\n[bold yellow]Talent 收敛 · {phase_label} "
                f"第 {ts.get('round_num', '?')} 轮[/bold yellow]"
            )
            think = ts.get("think_content", "")
            if think:
                ctx.console.print(Panel(
                    think, border_style="cyan",
                    title="reasoning trace",
                ))
            else:
                ctx.console.print("（无思考过程记录）")
        return

    # Support comma-separated IDs: /think 1,2,3
    try:
        target_ids = [int(x.strip()) for x in target.split(",")]
    except ValueError:
        ctx.console.print("[red]请输入有效的专家编号（1-10）或 'talent'。[/red]")
        return

    for target_id in target_ids:
        matched = [r for r in expert_results if r.get("expert_id") == target_id]
        if not matched:
            ctx.console.print(f"[red]未找到专家 {target_id} 的结果。[/red]")
            continue
        for m in matched:
            phase_label = PHASE_NAMES.get(m.get("phase", ""), m.get("phase", "?"))
            ctx.console.print(f"\n[bold]{phase_label} Round {m.get('round_num')}[/bold]")
            display_expert_result(ctx.console, m, show_think=True)


def cmd_experts(ctx: CommandContext, args: list[str]):
    """List all expert dimensions."""
    from vibe_engine.config import EXPERT_DIMENSIONS

    ctx.console.print()
    table = Table(
        title="[bold]专家维度列表[/bold]",
        show_header=True, header_style="bold cyan", border_style="cyan",
    )
    table.add_column("ID", style="bold cyan", justify="center", width=4)
    table.add_column("名称", min_width=16)
    table.add_column("描述")
    for d in EXPERT_DIMENSIONS:
        table.add_row(str(d["id"]), d["name"], d["description"])
    ctx.console.print(table)
    ctx.console.print()


def cmd_summary(ctx: CommandContext, args: list[str]):
    """Show analysis summary (Talent + Planner decisions)."""
    from vibe_engine.cli_display import PHASE_NAMES, display_expert_summary_table

    if ctx.last_state is None:
        ctx.console.print("尚无分析结果。请先输入 Vibe 进行分析。")
        return

    state = ctx.last_state

    for ts in state.get("talent_summaries", []):
        phase_name = PHASE_NAMES.get(ts.get("phase", "?"), ts.get("phase", "?"))
        score = ts.get("synthesis_score", "?")
        ctx.console.print(Panel(
            f"[bold]核心矛盾点：[/bold]\n{ts.get('core_contradictions', '（无）')}\n\n"
            f"[bold]涌现假设：[/bold]\n{ts.get('emergent_hypothesis', '（无）')}\n\n"
            f"[bold]综合评分：[/bold] {score}/10",
            title=f"[bold cyan]Talent · {phase_name} "
                  f"第 {ts.get('round_num', '?')} 轮[/bold cyan]",
            border_style="cyan",
        ))

    for dec in state.get("planner_decisions", []):
        action = dec.get("decision", "?")
        action_display = {
            "proceed": "[bold green]PROCEED[/bold green]",
            "iterate": "[bold yellow]ITERATE[/bold yellow]",
            "abort": "[bold red]ABORT[/bold red]",
        }.get(action, action)
        ctx.console.print(Panel(
            f"[bold]决策：[/bold] {action_display}\n"
            f"[bold]充分度评分：[/bold] {dec.get('sufficiency_score', '?')}/10\n"
            f"[bold]理由：[/bold] {dec.get('reasoning', '')}",
            title="[bold cyan]Planner 裁决[/bold cyan]", border_style="cyan",
        ))

    expert_results = state.get("expert_results", [])
    if expert_results:
        display_expert_summary_table(ctx.console, expert_results)


def cmd_mode(ctx: CommandContext, args: list[str]):
    """View or change the analysis mode."""
    from vibe_engine.cli_display import MODE_TO_PHASES, PHASE_NAMES

    valid_modes = list(MODE_TO_PHASES.keys())

    if not args:
        ctx.console.print(f"\n[bold]当前模式：[/bold] {ctx.mode}")
        ctx.console.print(f"可用模式：{', '.join(valid_modes)}")
        ctx.console.print("[italic]用法：/mode <mode> 切换模式[/italic]\n")
        return

    new_mode = args[0].strip().lower()
    if new_mode not in valid_modes:
        ctx.console.print(f"[red]无效模式：{new_mode}[/red]")
        ctx.console.print(f"可用模式：{', '.join(valid_modes)}")
        return

    if ctx.set_mode:
        ctx.set_mode(new_mode)
    phase_labels = " → ".join(PHASE_NAMES.get(p, p) for p in MODE_TO_PHASES[new_mode])
    ctx.console.print(f"[green]模式已切换为 {new_mode}[/green] ({phase_labels})")


# ---------------------------------------------------------------------------
# Registry singleton
# ---------------------------------------------------------------------------

_registry = CommandRegistry()


def _register_builtins():
    """Register all built-in commands."""
    _registry.register("help", cmd_help, "显示帮助信息", aliases=["h", "?"], usage="[命令名]")
    _registry.register("exit", cmd_exit, "退出 REPL", aliases=["quit", "q"])
    _registry.register("clear", cmd_clear, "清除屏幕", aliases=["cls"])
    _registry.register("status", cmd_status, "查看分析状态")
    _registry.register(
        "think", cmd_think, "查看专家/Talent 推理过程", usage="<编号|talent>"
    )
    _registry.register("experts", cmd_experts, "列出所有专家维度")
    _registry.register("summary", cmd_summary, "查看分析摘要（Talent + Planner）")
    _registry.register("mode", cmd_mode, "查看或切换分析模式", usage="[模式名]")


_register_builtins()


def get_registry() -> CommandRegistry:
    """Return the global command registry."""
    return _registry
