"""Prompt template management for all agent roles."""

from pathlib import Path
from vibe_engine.config import EXPERT_DIMENSIONS

_PROMPTS_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    """Read a prompt template file from the prompts directory."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Expert prompts — templates live in expert_system.md / expert_user.md
# ---------------------------------------------------------------------------

def get_expert_system_prompt(expert_id: int) -> str:
    """Return the system prompt for the given expert dimension ID (1-10)."""
    dims = {d["id"]: d for d in EXPERT_DIMENSIONS}
    if expert_id not in dims:
        raise ValueError(f"Unknown expert_id: {expert_id}")

    # 1. Try specific expert file: experts/expert_{id}.md
    specific_path = _PROMPTS_DIR / "experts" / f"expert_{expert_id}.md"
    if specific_path.exists():
        return specific_path.read_text(encoding="utf-8")

    # 2. Fallback to generic template
    dim = dims[expert_id]
    template = _load("expert_system.md")
    return template.format(name=dim["name"], description=dim["description"])


# Phase-specific instructions injected into the expert user prompt
EXPERT_PHASE_INSTRUCTIONS = {
    "discovery": "",
    "targeting": """## 标的锁定阶段特殊要求
请在分析中**必须**提出具体的可投资标的，包括但不限于：
- 具体股票代码（如 $AAPL.US$, $600519.SH$）
- 加密货币 Token（如 $BTC, $ETH）
- 产业链关键节点公司

请在输出末尾额外添加以下格式：
### 推荐标的
（列出 1-5 个具体标的，每个标的附带一句话理由）""",
    "validation": """## 逻辑验证阶段特殊要求
请对给定的具体标的进行**严谨的数据逻辑推导**，包括：
- 财务数据验证（营收结构、利润率、增速）
- 估值合理性（PE/PS/PB 对比同行）
- 筹码/链上数据分析（如适用）
- 关键假设的敏感性分析

请在输出末尾额外添加以下格式：
### 数据推导链
（步骤化的数据推导过程，每步标注数据来源或假设依据）""",
}


def get_expert_user_prompt(vibe: str, phase: str, round_num: int) -> str:
    """Return the user message for an expert analysis call.

    Injects phase-specific instructions for targeting (concrete targets)
    and validation (data logic chain) phases.
    """
    template = _load("expert_user.md")
    phase_instruction = EXPERT_PHASE_INSTRUCTIONS.get(phase, "")
    return template.format(
        vibe=vibe, phase=phase, round=round_num,
        phase_instruction=phase_instruction,
    )


# ---------------------------------------------------------------------------
# Talent prompts  (S3)
# ---------------------------------------------------------------------------

TALENT_ROLE_PROMPTS = {
    "strategist": """\
你是一位战略家，擅长从多维视角中提炼核心矛盾与涌现新机遇。
你将收到多位专家的独立分析，你的任务是：
1. 识别专家意见中最核心的冲突与张力
2. 涌现出超越单一专家视角的新假设或投资逻辑
3. 为 Planner 提供信息充分度的参考依据
""",
    "stock_picker": """\
你是一位选股手，专注于将抽象投资逻辑落地为具体可投资标的。
你将收到多位专家的独立分析，你的任务是：
1. 评估各专家提出的具体标的是否符合初始 Vibe 的核心审美
2. 对明显偏离主线的标的进行标注和质疑
3. 聚焦最符合逻辑的 1-3 个核心标的
""",
    "auditor": """\
你是一位量化审计师，专注于逻辑闭环与数据可靠性验证。
你将收到多位专家的独立分析，你的任务是：
1. 交叉比对专家的数据逻辑链是否完整闭环
2. 指出推导过程中的致命漏洞或数据缺失
3. 给出清晰的盈亏比评估结论
""",
}

TALENT_SYSTEM_TEMPLATE = """\
{role_prompt}

## 输出格式（严格遵守）
---
### 核心矛盾点
（描述专家意见中最重要的冲突或张力）

### 涌现假设
（超越单一专家视角的新洞见或待验证假设）

### 综合评分
（对当前信息充分度的评分，0-10 分，10 分表示信息完全充分）
评分：X/10
理由：（一句话说明评分依据）
---

使用中文输出。
"""

TALENT_USER_TEMPLATE = """\
以下是本轮专家分析结果（阶段：{phase}，第 {round} 轮）：

{expert_summaries}

请进行交叉比对与综合分析。
"""


def get_talent_system_prompt(talent_role: str) -> str:
    """Return the system prompt for the Talent node based on current phase role."""
    role_prompt = TALENT_ROLE_PROMPTS.get(talent_role, TALENT_ROLE_PROMPTS["strategist"])
    return TALENT_SYSTEM_TEMPLATE.format(role_prompt=role_prompt)


def get_talent_user_prompt(expert_results: list, phase: str, round_num: int) -> str:
    """Format expert results for the Talent node."""
    summaries = []
    for r in expert_results:
        summaries.append(
            f"**[专家{r['expert_id']} - {r['expert_name']}]**\n"
            f"逻辑链条：{r['logic_chain']}\n"
            f"精简结论：{r['conclusion']}\n"
            f"核心风险点：{r['risk_points']}\n"
        )
    return TALENT_USER_TEMPLATE.format(
        phase=phase,
        round=round_num,
        expert_summaries="\n---\n".join(summaries),
    )


# ---------------------------------------------------------------------------
# Planner prompts  (S4)
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """\
你是投资分析工作流的规划器（Planner），负责评估信息充分度并控制工作流的流转。

## 你的职责
1. 基于 Talent 的综合总结，判断当前信息是否足以推进
2. 若信息不足，将 Talent 的关键洞见融合到原始 Vibe 中，生成进化后的 Vibe_Next
3. 选取下一轮最需要的专家维度

## 当前上下文
- 当前阶段：{phase}
- 当前轮次：第 {round} 轮（最大 {max_rounds} 轮）

## 决策规则
- 若综合评分 ≥ 7，且逻辑基本闭环 → 决策为 "proceed"（推进到下一阶段）
- 若综合评分 < 7，且未达到最大轮数 → 决策为 "iterate"（发起新一轮发散）
- 若已达最大轮数但信息仍不充分 → 决策为 "abort"（终止并返回失败状态）

## 可选专家列表
{expert_roster}

## 输出格式（严格 JSON，不要添加其他内容）
```json
{{
  "sufficiency_score": <0-10 整数>,
  "decision": "<proceed|iterate|abort>",
  "reasoning": "<一段决策依据>",
  "vibe_next": "<融合后的新 Vibe，仅 iterate 时填写，否则为空字符串>",
  "selected_experts": [<专家ID列表，1-10之间的整数>]
}}
```

使用中文输出（JSON 字段值部分）。
"""

PLANNER_USER_TEMPLATE = """\
## 当前 Vibe
{vibe_current}

## 原始 Vibe（用户初始直觉）
{vibe_original}

## Talent 综合分析（阶段：{phase}，第 {round} 轮）

### 核心矛盾点
{core_contradictions}

### 涌现假设
{emergent_hypothesis}

### Talent 综合评分
{synthesis_score}/10

---

当前是第 {round}/{max_rounds} 轮。请根据上述信息做出决策。

若决策为 "iterate"：
1. 将 Talent 的关键洞见融入当前 Vibe，生成更聚焦的 Vibe_Next
2. 选择最能填补信息缺口的专家

若决策为 "proceed"：
1. 选择下一阶段最需要的专家

若决策为 "abort"：
1. 说明信息不足的具体原因
"""


def _build_expert_roster() -> str:
    """Build a formatted expert roster string for the Planner prompt."""
    lines = []
    for d in EXPERT_DIMENSIONS:
        lines.append(f"  {d['id']}. {d['name']}：{d['description']}")
    return "\n".join(lines)


def get_planner_system_prompt(phase: str, round_num: int, max_rounds: int) -> str:
    """Return the system prompt for the Planner node with current context."""
    return PLANNER_SYSTEM_PROMPT.format(
        phase=phase,
        round=round_num,
        max_rounds=max_rounds,
        expert_roster=_build_expert_roster(),
    )


def get_planner_user_prompt(
    talent_summary: dict | None,
    vibe_current: str,
    vibe_original: str,
    phase: str,
    round_num: int,
    max_rounds: int,
) -> str:
    """Format the Planner's user prompt with Talent synthesis and Vibe context."""
    if talent_summary is None:
        talent_summary = {
            "core_contradictions": "（无 Talent 分析结果）",
            "emergent_hypothesis": "（无 Talent 分析结果）",
            "synthesis_score": 0,
        }

    return PLANNER_USER_TEMPLATE.format(
        vibe_current=vibe_current,
        vibe_original=vibe_original,
        phase=phase,
        round=round_num,
        max_rounds=max_rounds,
        core_contradictions=talent_summary.get("core_contradictions", ""),
        emergent_hypothesis=talent_summary.get("emergent_hypothesis", ""),
        synthesis_score=talent_summary.get("synthesis_score", 0),
    )


# ---------------------------------------------------------------------------
# Final Report prompts  (S5)
# ---------------------------------------------------------------------------

FINAL_REPORT_SYSTEM_PROMPT = """\
你是一位资深投资分析报告撰写专家。你的任务是基于完整的多阶段分析过程，
生成一份结构化的投资建议报告。

## 报告结构（严格遵守）

### 一、执行摘要
（2-3 句话总结核心结论：建议/否决，核心理由）

### 二、Vibe 回溯
（原始直觉 → 经过分析后的认知演变轨迹）

### 三、多维分析总结
（各阶段关键发现，按阶段分小节）

#### 价值发现阶段
（核心矛盾、涌现假设、信息缺口）

#### 标的锁定阶段
（推荐标的及筛选逻辑，若有）

#### 逻辑验证阶段
（数据验证结论，盈亏比评估，若有）

### 四、推荐标的
（最终推荐/否决的具体标的列表，附理由）

### 五、核心风险提示
（按重要性排序的 3-5 条风险）

### 六、结论与建议
（最终投资建议：买入/观望/回避，以及后续关注要点）

---
使用中文输出。
"""

FINAL_REPORT_USER_TEMPLATE = """\
## 原始 Vibe
{vibe_original}

## Vibe 演变历史
{vibe_history}

## 各阶段分析记录

{phase_records}

## 最终 Planner 决策
{final_decision}

---
请基于以上完整的分析过程，生成结构化投资建议报告。
"""


def get_final_report_system_prompt() -> str:
    """Return the system prompt for final report generation."""
    return FINAL_REPORT_SYSTEM_PROMPT


def get_final_report_user_prompt(
    vibe_original: str,
    vibe_history: list[str],
    talent_summaries: list[dict],
    planner_decisions: list[dict],
    expert_results: list[dict],
) -> str:
    """Format the final report user prompt with full analysis history."""
    # Vibe history
    vibe_hist_text = "\n".join(
        f"  - Vibe_{i}: {v}" for i, v in enumerate(vibe_history)
    )

    # Phase records — group talent summaries by phase
    phase_records = []
    for ts in talent_summaries:
        phase_records.append(
            f"### [{ts.get('phase', '?')}] 第 {ts.get('round_num', '?')} 轮 — Talent 总结\n"
            f"核心矛盾点：{ts.get('core_contradictions', '')}\n"
            f"涌现假设：{ts.get('emergent_hypothesis', '')}\n"
            f"综合评分：{ts.get('synthesis_score', '?')}/10\n"
        )

    # Add expert targets/data chains if available
    targets_seen = []
    data_chains = []
    for er in expert_results:
        if er.get("targets"):
            targets_seen.append(
                f"专家{er['expert_id']}·{er.get('expert_name','')}: {', '.join(er['targets'])}"
            )
        if er.get("data_logic_chain"):
            data_chains.append(
                f"专家{er['expert_id']}·{er.get('expert_name','')}: {er['data_logic_chain']}"
            )

    if targets_seen:
        phase_records.append("### 标的锁定结果\n" + "\n".join(targets_seen))
    if data_chains:
        phase_records.append("### 数据推导链\n" + "\n".join(data_chains))

    # Final decision
    if planner_decisions:
        last = planner_decisions[-1]
        final_decision = (
            f"充分度评分: {last.get('sufficiency_score', '?')}/10\n"
            f"决策: {last.get('decision', '?')}\n"
            f"理由: {last.get('reasoning', '')}"
        )
    else:
        final_decision = "（无 Planner 决策记录）"

    return FINAL_REPORT_USER_TEMPLATE.format(
        vibe_original=vibe_original,
        vibe_history=vibe_hist_text,
        phase_records="\n\n".join(phase_records),
        final_decision=final_decision,
    )
