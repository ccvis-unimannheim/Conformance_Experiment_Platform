"""
Per-task contract registry (see ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4).

Each ``taskNN`` module may declare its own contract attributes, authored one
task at a time (§14):

    IDIOMS                 list[str]            (already used by /task-idioms)
    GT_TIER                "AUTO" | "SEMI" | "MANUAL"
    PARAM_SPEC             list[dict]           computational params for /specify
    ANSWER_FORMATS         list[dict]           allowed col-D formats + gt_shape
    RUBRIC                 str | None           static free-text grading rubric
    compute_ground_truth   callable | None      (log, alignments, fitness_df,
                                                   model_path, params, answer_format) -> dict

Until a task declares these, the getters below return safe fallbacks so
/specify and /answer-format-groundtruth still render a working (if generic)
page for that task.
"""

from typing import Any, Callable, Optional

from ProViBackend.scripts.tasks import (
    task01, task02, task03, task04, task05,
    task06, task07, task08, task09, task10, task11, task12,
    task13, task14, task15, task16,
    task17, task18, task19, task20, task21,
    task22, task23, task24, task25, task26, task27,
    task28, task29, task30, task31,
    task32, task33, task34,
    task35, task36, task37,
)

TASK_MODULES: dict[str, Any] = {
    "task01": task01, "task02": task02, "task03": task03, "task04": task04, "task05": task05,
    "task06": task06, "task07": task07, "task08": task08, "task09": task09,
    "task10": task10, "task11": task11, "task12": task12,
    "task13": task13, "task14": task14, "task15": task15, "task16": task16,
    "task17": task17, "task18": task18, "task19": task19, "task20": task20, "task21": task21,
    "task22": task22,
    "task23": task23, "task24": task24, "task25": task25, "task26": task26, "task27": task27,
    "task28": task28, "task29": task29, "task30": task30, "task31": task31,
    "task32": task32, "task33": task33, "task34": task34,
    "task35": task35, "task36": task36, "task37": task37,
}

# Fallbacks for unauthored tasks (§4, §9, §11).
DEFAULT_PARAM_SPEC: list[dict] = []
DEFAULT_ANSWER_FORMATS: list[dict] = [
    {"key": "free-text", "gt_shape": "reference", "decisive_default": False},
]
DEFAULT_GT_TIER = "MANUAL"


def _module(task_key: str):
    mod = TASK_MODULES.get(task_key)
    if mod is None:
        raise KeyError(f"Unknown task_key '{task_key}'")
    return mod


def get_param_spec(task_key: str) -> list[dict]:
    """This task's computational params for /specify, or [] if unauthored/none."""
    return getattr(_module(task_key), "PARAM_SPEC", DEFAULT_PARAM_SPEC)


def get_answer_formats(task_key: str) -> list[dict]:
    """This task's allowed col-D answer formats, or the free-text fallback."""
    return getattr(_module(task_key), "ANSWER_FORMATS", DEFAULT_ANSWER_FORMATS)


def get_gt_tier(task_key: str) -> str:
    """AUTO | SEMI | MANUAL — defaults to MANUAL until authored (§6)."""
    return getattr(_module(task_key), "GT_TIER", DEFAULT_GT_TIER)


def get_rubric(task_key: str) -> Optional[str]:
    """Static free-text grading rubric, or None if not authored (§8)."""
    return getattr(_module(task_key), "RUBRIC", None)


def get_compute_ground_truth(task_key: str) -> Optional[Callable]:
    """Optional `compute_ground_truth(...)` for AUTO/SEMI tasks (§4, §8)."""
    return getattr(_module(task_key), "compute_ground_truth", None)
