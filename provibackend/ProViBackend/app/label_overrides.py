# Per-task idiom label overrides.
# Structure: { task_key: { idiom_key: display_label } }
# The global Idiom.label is used as fallback when no override exists.
TASK_IDIOM_LABEL_OVERRIDES: dict[str, dict[str, str]] = {
    "task10": {"heatmap": "Matrix"},
}


def resolve_idiom_label(task_key: str, idiom_key: str, default_label: str) -> str:
    return TASK_IDIOM_LABEL_OVERRIDES.get(task_key, {}).get(idiom_key, default_label)
