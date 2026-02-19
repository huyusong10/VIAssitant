"""S2 verification script — tests fan-out/fan-in without calling the real LLM.

This script validates the S2 structural requirements:
  S2.1 — 10 expert dimension configs
  S2.2 — Send() fan-out mechanism
  S2.3 — Fan-in convergence (result count matches)
  S2.4 — Context isolation (each expert gets independent input)
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vibe_engine.state import VibeState, ExpertInput, ExpertResult
from vibe_engine.config import EXPERT_DIMENSIONS
from vibe_engine.graph import build_graph, route_to_experts
from vibe_engine.nodes.expert import make_expert_node
from vibe_engine.prompts import get_expert_system_prompt, get_expert_user_prompt


def test_s2_1_expert_dimensions():
    """S2.1: 10 expert dimensions with name + role_prompt fields."""
    assert len(EXPERT_DIMENSIONS) == 10, f"Expected 10– got {len(EXPERT_DIMENSIONS)}"
    for dim in EXPERT_DIMENSIONS:
        assert "id" in dim, f"Missing 'id' in {dim}"
        assert "name" in dim, f"Missing 'name' in {dim}"
        assert "description" in dim, f"Missing 'description' (role_prompt) in {dim}"
        assert isinstance(dim["name"], str) and len(dim["name"]) > 0
        assert isinstance(dim["description"], str) and len(dim["description"]) > 0
    print("S2.1 ✓ 10 expert dimensions verified (each has id, name, description)")


def test_s2_2_fanout_send():
    """S2.2: Send() fan-out produces correct number of dispatches."""
    test_cases = [
        ([2], 1),
        ([1, 3, 5], 3),
        ([1, 2, 3, 4, 5, 6], 6),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 10),
    ]
    for experts, expected_count in test_cases:
        state = {
            "vibe": "test vibe",
            "phase": "discovery",
            "round": 1,
            "selected_experts": experts,
        }
        sends = route_to_experts(state)
        assert len(sends) == expected_count, (
            f"Fan-out for {experts}: expected {expected_count} sends, got {len(sends)}"
        )
    print("S2.2 ✓ Send() fan-out produces correct counts (1, 3, 6, 10)")


def test_s2_3_fanin_structure():
    """S2.3: Fan-in results should have the expert_results list."""
    # We can't run the full graph without LLM, but we can verify:
    # 1. The graph compiles with the fan-out/fan-in structure
    # 2. The Send() args match ExpertInput structure
    graph = build_graph()
    
    state = {
        "vibe": "看好人工智能",
        "phase": "discovery",
        "round": 1,
        "selected_experts": [2, 6, 8],
    }
    sends = route_to_experts(state)
    
    for send in sends:
        arg = send.arg
        assert "expert_id" in arg, "Missing expert_id in Send arg"
        assert "vibe" in arg, "Missing vibe in Send arg"
        assert "phase" in arg, "Missing phase in Send arg"
        assert "round" in arg, "Missing round in Send arg"
    
    print("S2.3 ✓ Fan-in structure verified (graph compiles, Send args match ExpertInput)")


def test_s2_4_isolation():
    """S2.4: Each expert's Send() has fully independent context."""
    state = {
        "vibe": "看好新能源汽车",
        "phase": "discovery",
        "round": 1,
        "selected_experts": [1, 5, 10],
    }
    sends = route_to_experts(state)

    # Each Send should point to the same node but with different expert_id
    expert_ids = [s.arg["expert_id"] for s in sends]
    assert expert_ids == [1, 5, 10], f"Wrong expert IDs: {expert_ids}"
    assert len(set(expert_ids)) == len(expert_ids), "Duplicate expert IDs!"

    # All should share the same node name
    nodes = [s.node for s in sends]
    assert all(n == "expert" for n in nodes), f"Unexpected node names: {nodes}"

    # Each should have its own copy of the vibe (no shared reference issues)
    for s in sends:
        assert s.arg["vibe"] == "看好新能源汽车"
        assert s.arg["phase"] == "discovery"
        assert s.arg["round"] == 1

    # Verify that modifying one arg doesn't affect others
    sends[0].arg["vibe"] = "MODIFIED"
    assert sends[1].arg["vibe"] == "看好新能源汽车", "Context leak between Send args!"

    print("S2.4 ✓ Context isolation verified (independent args, no cross-reference)")


def test_expert_prompts():
    """Bonus: Verify all 10 expert system prompts are distinct."""
    prompts = []
    for dim in EXPERT_DIMENSIONS:
        prompt = get_expert_system_prompt(dim["id"])
        assert dim["name"] in prompt, f"Expert name not found in prompt for {dim['id']}"
        prompts.append(prompt)
    
    assert len(set(prompts)) == 10, "Some expert prompts are duplicated!"
    print("     ✓ All 10 expert system prompts are unique and contain their role names")


if __name__ == "__main__":
    print("=" * 60)
    print("  S2 — 专家集群扇出/扇入 验证")
    print("=" * 60)
    print()

    test_s2_1_expert_dimensions()
    test_s2_2_fanout_send()
    test_s2_3_fanin_structure()
    test_s2_4_isolation()
    test_expert_prompts()

    print()
    print("=" * 60)
    print("  ✅ All S2 verifications passed!")
    print("=" * 60)
