"""Slash command system for the Vibe CLI REPL (C2 complete).

Provides a CommandRegistry for registering and dispatching slash commands,
plus built-in command implementations.

C2 command set:
  C2.1  CommandRegistry with alias support
  C2.2  Core: /help, /status, /stop, /clear
  C2.3  Analysis: /think, /experts, /summary, /mode
  C2.4  Export: /export md, /export json
  C2.5  Config: /config show, /config set
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
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
    request_stop: Callable[[], None] | None = None


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

    def get_completions(self) -> list[tuple[str, str]]:
        """Return (name, help_text) tuples for all commands — used by autocomplete."""
        result = []
        for cmd in self._commands.values():
            usage_str = f" {cmd.usage}" if cmd.usage else ""
            result.append((f"/{cmd.name}{usage_str}", cmd.help_text))
        return result


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
    table.add_column("命令", style="cyan", min_width=20)
    table.add_column("说明")
    for cmd in registry.get_all_commands():
        usage_str = f" {cmd.usage}" if cmd.usage else ""
        table.add_row(f"/{cmd.name}{usage_str}", cmd.help_text)
    ctx.console.print(table)
    ctx.console.print(
        "\n[italic]提示：直接输入文本即作为 Vibe 启动分析 · "
        "输入 / 即可看到命令提示[/italic]\n"
    )


def cmd_exit(ctx: CommandContext, args: list[str]):
    """Exit the REPL."""
    if ctx.request_exit:
        ctx.request_exit()


def cmd_clear(ctx: CommandContext, args: list[str]):
    """Clear the terminal screen."""
    ctx.console.clear()


def cmd_stop(ctx: CommandContext, args: list[str]):
    """Stop the currently running analysis."""
    if not ctx.is_analyzing:
        ctx.console.print("当前没有正在运行的分析。")
        return
    if ctx.request_stop:
        ctx.request_stop()
        ctx.console.print("[yellow]正在停止分析...[/yellow]")
    else:
        ctx.console.print("[yellow]使用 Ctrl+C 中断当前分析。[/yellow]")


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
# C2.4 — Export commands
# ---------------------------------------------------------------------------


def _slugify(text: str, max_len: int = 30) -> str:
    """Convert text to a safe filename slug."""
    # Keep CJK characters, alphanumerics, and hyphens
    slug = re.sub(r'[^\w\u4e00-\u9fff-]', '_', text)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug[:max_len] if slug else "analysis"


def cmd_export(ctx: CommandContext, args: list[str]):
    """Export analysis results to a file (md or json)."""
    if ctx.last_state is None:
        ctx.console.print("尚无分析结果。请先输入 Vibe 进行分析。")
        return

    fmt = args[0].strip().lower() if args else ""
    if fmt not in ("md", "json"):
        ctx.console.print(
            "[bold]用法：[/bold] /export md  或  /export json\n"
            "  [cyan]md[/cyan]   — 导出 Markdown 报告\n"
            "  [cyan]json[/cyan] — 导出完整分析数据 (JSON)"
        )
        return

    state = ctx.last_state
    vibe = state.get("vibe_original", "analysis")
    slug = _slugify(vibe)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(".", "output")
    os.makedirs(output_dir, exist_ok=True)

    if fmt == "md":
        _export_markdown(ctx, state, output_dir, date_str, slug)
    else:
        _export_json(ctx, state, output_dir, date_str, slug)


def _export_markdown(ctx: CommandContext, state: dict, output_dir: str,
                     date_str: str, slug: str):
    """Export final report and expert summaries as Markdown."""
    from vibe_engine.cli_display import PHASE_NAMES

    filepath = os.path.join(output_dir, f"{date_str}_{slug}.md")
    parts = []

    # Header
    vibe_orig = state.get("vibe_original", "")
    parts.append(f"# Vibe 投资分析报告\n")
    parts.append(f"> **Vibe**: {vibe_orig}\n")
    parts.append(f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Vibe evolution
    vibe_history = state.get("vibe_history", [])
    if len(vibe_history) > 1:
        parts.append("\n## Vibe 演变轨迹\n")
        for i, v in enumerate(vibe_history):
            label = "原始" if i == 0 else f"变异 {i}"
            parts.append(f"- **{label}**: {v}\n")

    # Final report
    final_report = state.get("final_report")
    if final_report:
        parts.append("\n## 最终报告\n")
        parts.append(final_report + "\n")

    # Expert summaries
    expert_results = state.get("expert_results", [])
    if expert_results:
        parts.append("\n## 专家分析摘要\n")
        for r in expert_results:
            eid = r.get("expert_id", "?")
            ename = r.get("expert_name", "?")
            phase_name = PHASE_NAMES.get(r.get("phase", ""), "?")
            parts.append(f"\n### 专家 {eid} · {ename} ({phase_name} R{r.get('round_num', '?')})\n")
            parts.append(f"**结论**: {r.get('conclusion', '（无）')}\n\n")
            parts.append(f"**风险**: {r.get('risk_points', '（无）')}\n\n")
            targets = r.get("targets", [])
            if targets:
                parts.append(f"**标的**: {', '.join(targets)}\n\n")

    content = "\n".join(parts)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    abs_path = os.path.abspath(filepath)
    ctx.console.print(f"[green]✓ Markdown 报告已导出[/green]")
    ctx.console.print(f"  [cyan]{abs_path}[/cyan]")
    ctx.console.print(f"  ({len(content):,} 字)")


def _export_json(ctx: CommandContext, state: dict, output_dir: str,
                 date_str: str, slug: str):
    """Export the full analysis state as JSON (excluding think_content by default)."""
    filepath = os.path.join(output_dir, f"{date_str}_{slug}.json")

    # Build export dict — strip think_content to keep file size manageable
    export = {}
    export["vibe_original"] = state.get("vibe_original", "")
    export["vibe_history"] = state.get("vibe_history", [])
    export["phase"] = state.get("phase", "")
    export["round"] = state.get("round", 0)
    export["abort_reason"] = state.get("abort_reason")
    export["final_report"] = state.get("final_report")
    export["exported_at"] = datetime.now().isoformat()

    # Expert results without think_content
    export["expert_results"] = []
    for r in state.get("expert_results", []):
        item = {k: v for k, v in r.items() if k != "think_content"}
        item["think_content_length"] = len(r.get("think_content") or "")
        export["expert_results"].append(item)

    # Talent summaries without think_content
    export["talent_summaries"] = []
    for ts in state.get("talent_summaries", []):
        item = {k: v for k, v in ts.items() if k != "think_content"}
        item["think_content_length"] = len(ts.get("think_content") or "")
        export["talent_summaries"].append(item)

    export["planner_decisions"] = state.get("planner_decisions", [])

    content = json.dumps(export, ensure_ascii=False, indent=2)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    abs_path = os.path.abspath(filepath)
    ctx.console.print(f"[green]✓ JSON 数据已导出[/green]")
    ctx.console.print(f"  [cyan]{abs_path}[/cyan]")
    ctx.console.print(f"  ({len(content):,} 字)")
    ctx.console.print(
        "  [italic]注意：think_content 已省略以减小体积，"
        "完整推理过程请在 REPL 中使用 /think 查看[/italic]"
    )


# ---------------------------------------------------------------------------
# C2.5 — Config commands
# ---------------------------------------------------------------------------


def cmd_config(ctx: CommandContext, args: list[str]):
    """View or modify runtime configuration.

    Usage:
      /config           — show current configuration
      /config show      — same as above
      /config set <key> <value>  — modify a config value
    """
    from vibe_engine.config import PHASE_CONFIGS, MODEL_CHAT, MODEL_REASONER

    sub = args[0].strip().lower() if args else "show"

    if sub == "show":
        _config_show(ctx)
    elif sub == "set":
        if len(args) < 3:
            ctx.console.print(
                "[bold]用法：[/bold] /config set <key> <value>\n"
                "  可修改的 key：\n"
                "  [cyan]discovery.max_rounds[/cyan]   价值发现最大轮数\n"
                "  [cyan]targeting.max_rounds[/cyan]   标的锁定最大轮数\n"
                "  [cyan]validation.max_rounds[/cyan]  逻辑验证最大轮数\n"
                "  [cyan]discovery.expert_count_min[/cyan]  发现阶段最少专家数\n"
                "  [cyan]discovery.expert_count_max[/cyan]  发现阶段最多专家数\n"
                "  [cyan]targeting.expert_count_min[/cyan]  锁定阶段最少专家数\n"
                "  [cyan]targeting.expert_count_max[/cyan]  锁定阶段最多专家数\n"
                "  [cyan]validation.expert_count_min[/cyan] 验证阶段最少专家数\n"
                "  [cyan]validation.expert_count_max[/cyan] 验证阶段最多专家数"
            )
            return
        key = args[1].strip()
        value = args[2].strip()
        _config_set(ctx, key, value)
    else:
        ctx.console.print(
            "[bold]用法：[/bold] /config [show|set]\n"
            "  [cyan]/config show[/cyan]         查看当前配置\n"
            "  [cyan]/config set <k> <v>[/cyan]  修改配置项"
        )


def _config_show(ctx: CommandContext):
    """Display current runtime configuration."""
    from vibe_engine.config import PHASE_CONFIGS, MODEL_CHAT, MODEL_REASONER
    from vibe_engine.cli_display import PHASE_NAMES

    table = Table(
        title="[bold]运行时配置[/bold]",
        show_header=True, header_style="bold cyan",
        border_style="cyan", padding=(0, 2),
    )
    table.add_column("配置项", style="cyan", min_width=24)
    table.add_column("值", min_width=12)

    # Models
    table.add_row("model.chat", MODEL_CHAT)
    table.add_row("model.reasoner", MODEL_REASONER)
    table.add_row("", "")  # separator

    # Phase configs
    for phase in ["discovery", "targeting", "validation"]:
        pc = PHASE_CONFIGS.get(phase, {})
        phase_name = PHASE_NAMES.get(phase, phase)
        table.add_row(f"[bold]{phase}[/bold] ({phase_name})", "")
        table.add_row(f"  {phase}.max_rounds", str(pc.get("max_rounds", "?")))
        table.add_row(f"  {phase}.expert_count_min", str(pc.get("expert_count_min", "?")))
        table.add_row(f"  {phase}.expert_count_max", str(pc.get("expert_count_max", "?")))
        table.add_row(f"  {phase}.talent_role", str(pc.get("talent_role", "?")))

    # Current mode
    table.add_row("", "")
    table.add_row("current_mode", ctx.mode)

    ctx.console.print()
    ctx.console.print(table)
    ctx.console.print(
        "\n[italic]使用 /config set <key> <value> 修改配置 "
        "（下次分析生效）[/italic]\n"
    )


def _config_set(ctx: CommandContext, key: str, value: str):
    """Modify a runtime configuration value."""
    from vibe_engine.config import PHASE_CONFIGS

    # Parse key: expect "phase.field" format
    parts = key.split(".", 1)
    if len(parts) != 2:
        ctx.console.print(f"[red]无效的配置键：{key}[/red]")
        ctx.console.print("格式：<phase>.<field>  例如：discovery.max_rounds")
        return

    phase, field_name = parts
    if phase not in PHASE_CONFIGS:
        ctx.console.print(f"[red]未知阶段：{phase}[/red]  可选：discovery, targeting, validation")
        return

    allowed_fields = {"max_rounds", "expert_count_min", "expert_count_max"}
    if field_name not in allowed_fields:
        ctx.console.print(f"[red]不可修改的字段：{field_name}[/red]")
        ctx.console.print(f"可修改字段：{', '.join(sorted(allowed_fields))}")
        return

    try:
        int_value = int(value)
    except ValueError:
        ctx.console.print(f"[red]值必须是整数：{value}[/red]")
        return

    # Validate ranges
    if field_name == "max_rounds" and not (1 <= int_value <= 10):
        ctx.console.print("[red]max_rounds 范围：1-10[/red]")
        return
    if field_name.startswith("expert_count") and not (1 <= int_value <= 10):
        ctx.console.print("[red]expert_count 范围：1-10[/red]")
        return

    old_value = PHASE_CONFIGS[phase].get(field_name)
    PHASE_CONFIGS[phase][field_name] = int_value
    ctx.console.print(
        f"[green]✓ {key}: {old_value} → {int_value}[/green]"
        f"  （下次分析生效）"
    )


# ---------------------------------------------------------------------------
# Registry singleton
# ---------------------------------------------------------------------------

_registry = CommandRegistry()


def _register_builtins():
    """Register all built-in commands."""
    # C2.2 Core commands
    _registry.register("help", cmd_help, "显示帮助信息", aliases=["h", "?"], usage="[命令名]")
    _registry.register("exit", cmd_exit, "退出 REPL", aliases=["quit", "q"])
    _registry.register("clear", cmd_clear, "清除屏幕", aliases=["cls"])
    _registry.register("stop", cmd_stop, "停止当前分析")
    _registry.register("status", cmd_status, "查看最近一次分析的状态")

    # C2.3 Analysis interaction commands
    _registry.register(
        "think", cmd_think, "查看专家/Talent 推理过程", usage="<编号|talent>"
    )
    _registry.register("experts", cmd_experts, "列出所有 10 个专家维度")
    _registry.register("summary", cmd_summary, "查看分析摘要（Talent + Planner）")
    _registry.register("mode", cmd_mode, "查看或切换分析模式", usage="[模式名]")

    # C2.4 Export commands
    _registry.register("export", cmd_export, "导出结果（md/json）", usage="<md|json>")

    # C2.5 Config commands
    _registry.register("config", cmd_config, "查看/修改运行时配置", usage="[show|set]")


_register_builtins()


def get_registry() -> CommandRegistry:
    """Return the global command registry."""
    return _registry
