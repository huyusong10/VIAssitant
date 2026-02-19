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
    dim = dims[expert_id]
    template = _load("expert_system.md")
    return template.format(name=dim["name"], description=dim["description"])


def get_expert_user_prompt(vibe: str, phase: str, round_num: int) -> str:
    """Return the user message for an expert analysis call."""
    template = _load("expert_user.md")
    return template.format(vibe=vibe, phase=phase, round=round_num)


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

## 决策规则
- 若综合评分 ≥ 7，且逻辑基本闭环 → 决策为 "proceed"（推进到下一阶段）
- 若综合评分 < 7，且未达到最大轮数 → 决策为 "iterate"（发起新一轮发散）
- 若已达最大轮数但信息仍不充分 → 决策为 "abort"（终止并返回失败状态）

## 输出格式（JSON）
```json
{
  "sufficiency_score": <0-10 整数>,
  "decision": "<proceed|iterate|abort>",
  "reasoning": "<一段决策依据>",
  "vibe_next": "<融合后的新 Vibe，仅 iterate 时填写，否则为空字符串>",
  "selected_experts": [<专家ID列表，1-10之间的整数>]
}
```

使用中文输出（JSON 字段值部分）。
"""
