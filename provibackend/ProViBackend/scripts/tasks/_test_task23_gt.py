"""Run with: python _test_task23_gt.py  (from scripts/tasks/ directory)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Minimal synthetic alignments:
# [observed, expected] where ">>" = skip token
# Log Move:     [activity, ">>"]   → activity = log_move
# Model Move:   [">>", activity]   → activity = model_move
# Mismatch:     [actA, actB]       → activity = log_move (actA)
ALIGNMENTS = [
    {"alignment": [["A_APPROVED", ">>"], ["A_APPROVED", ">>"], [">>", "A_DECLINED"]]},
    {"alignment": [["A_APPROVED", ">>"], [">>", "A_DECLINED"]]},
    {"alignment": [["A_APPROVED", ">>"], [">>", "A_DECLINED"]]},
    {"alignment": [[">>", "A_DECLINED"], [">>", "A_ACTIVATED"]]},
    {"alignment": [["A_APPROVED", "A_ACTIVATED"]]},
]

from task23 import compute_ground_truth

# --- Test 1: correct return shape ---
result = compute_ground_truth(None, ALIGNMENTS, None, None, {}, "free_text")
assert isinstance(result, dict),             "result must be dict"
assert "text" in result,                     "result must have 'text' key"
assert "rubric" in result,                   "result must have 'rubric' key"
assert isinstance(result["text"], str),      "'text' must be string"
assert len(result["text"]) > 0,             "'text' must be non-empty"

rubric = result["rubric"]
assert "top_patterns"       in rubric,       "rubric must have 'top_patterns'"
assert "dominant_move_type" in rubric,       "rubric must have 'dominant_move_type'"
assert "top3_activities"    in rubric,       "rubric must have 'top3_activities'"
assert "top3_patterns"      in rubric,       "rubric must have 'top3_patterns'"
assert isinstance(rubric["top_patterns"], list), "'top_patterns' must be list"

for p in rubric["top_patterns"]:
    for key in ("pattern", "move_type", "activity", "count", "n_traces", "pct"):
        assert key in p, f"top_patterns entry missing key '{key}'"
    assert isinstance(p["count"],    int),   "'count' must be int"
    assert isinstance(p["n_traces"], int),   "'n_traces' must be int"
    assert isinstance(p["pct"],      float), "'pct' must be float"

assert rubric["dominant_move_type"] in {"Model Move", "Log Move", "Mismatch Move"}, \
    f"unexpected dominant_move_type: {rubric['dominant_move_type']}"

# --- Test 2: wrong answer_format returns empty dict ---
empty = compute_ground_truth(None, ALIGNMENTS, None, None, {}, "matrix")
assert empty == {}, f"expected empty dict for wrong format, got: {empty}"

# --- Test 3: empty alignments returns gracefully ---
graceful = compute_ground_truth(None, [], None, None, {}, "free_text")
assert isinstance(graceful, dict), "empty alignments must return dict"
assert "text" in graceful,         "empty alignments must still return 'text'"
assert "rubric" in graceful,       "empty alignments must still return 'rubric'"

print("All tests passed.")
