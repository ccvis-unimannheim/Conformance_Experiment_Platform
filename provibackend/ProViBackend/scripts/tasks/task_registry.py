"""
Per-task contract registry.

Each ``taskNN`` module may declare:

    IDIOMS          list[str]        the visualizations it renders
    PARAM_SPEC      list[dict]       computational params for /specify
    validate_params callable | None  semantic validation of those params
    RUBRIC          str | None       reference text for manually coding answers

The answer shape (format, options, number kind) is NOT a task property — every
task may use every format, and the admin authors it on /answer-format (see
app/answer_formats.py). Until a task declares the attributes above, the getters
return safe fallbacks so /specify still renders a working page for it.
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

# Fallback for tasks that declare no params.
DEFAULT_PARAM_SPEC: list[dict] = []


def _module(task_key: str):
    mod = TASK_MODULES.get(task_key)
    if mod is None:
        raise KeyError(f"Unknown task_key '{task_key}'")
    return mod


def get_param_spec(task_key: str) -> list[dict]:
    """This task's computational params for /specify, or [] if it declares none."""
    return getattr(_module(task_key), "PARAM_SPEC", DEFAULT_PARAM_SPEC)


def get_rubric(task_key: str) -> Optional[str]:
    """Static grading rubric for manually coding this task's answers, or None.

    Reference text only — it feeds no automatic scoring.
    """
    return getattr(_module(task_key), "RUBRIC", None)


def get_validate_params(task_key: str) -> Optional[Callable]:
    """Optional `validate_params(log, params) -> list[str]` semantic validator.

    Returns task-specific error messages (e.g. a chosen condition that cannot
    split the log) so /generate can reject illegal input with a hard error.
    None if the task declares none.
    """
    return getattr(_module(task_key), "validate_params", None)
