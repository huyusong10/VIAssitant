"""Configuration constants for the Vibe Investment Engine."""

import os
from typing import TypedDict

# --- Model Configuration ---
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# Model tiers per architecture constraint:
#   Planner → fast routing decisions → Chat model
#   Expert / Talent → deep reasoning → Reasoner model
MODEL_CHAT = "deepseek-chat"
MODEL_REASONER = "deepseek-reasoner"

# --- Phase Configuration ---
class PhaseConfig(TypedDict):
    max_rounds: int
    expert_count_min: int
    expert_count_max: int
    talent_role: str


PHASE_CONFIGS: dict[str, PhaseConfig] = {
    "discovery": {
        "max_rounds": 5,
        "expert_count_min": 3,
        "expert_count_max": 6,
        "talent_role": "strategist",
    },
    "targeting": {
        "max_rounds": 2,
        "expert_count_min": 2,
        "expert_count_max": 4,
        "talent_role": "stock_picker",
    },
    "validation": {
        "max_rounds": 1,
        "expert_count_min": 1,
        "expert_count_max": 3,
        "talent_role": "auditor",
    },
}

PHASE_ORDER = ["discovery", "targeting", "validation"]

# --- Expert Dimensions ---
EXPERT_DIMENSIONS = [
    {"id": 1, "name": "宏观冲浪者", "description": "从宏观经济周期、利率环境、地缘政治格局中寻找结构性机会"},
    {"id": 2, "name": "技术布道者", "description": "专注技术奇点与颠覆式创新，评估技术可行性与成熟度曲线"},
    {"id": 3, "name": "成长股狂热者", "description": "追踪高速成长赛道，关注收入增速、市场空间与竞争壁垒"},
    {"id": 4, "name": "资金博弈操盘手", "description": "解读主力资金流向、筹码分布、市场情绪与交易结构"},
    {"id": 5, "name": "深度价值卫道士", "description": "基于内在价值评估，挖掘被市场低估的资产，严守安全边际"},
    {"id": 6, "name": "黑天鹅预言家", "description": "专注识别尾部风险、系统性脆弱点与小概率高冲击事件"},
    {"id": 7, "name": "合规审查官", "description": "从监管合规、法律风险、政策敏感性角度审视投资标的"},
    {"id": 8, "name": "商业模式解构师", "description": "拆解商业模式的护城河、定价权、飞轮效应与可持续性"},
    {"id": 9, "name": "行为金融学家", "description": "分析市场参与者的认知偏差、情绪周期与非理性行为"},
    {"id": 10, "name": "第二层思维者", "description": "超越共识，思考'多数人认为X，但真实情况是Y'的反向逻辑"},
]
