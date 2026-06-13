"""
Experiment schema bridge: legacy flat ``task_configs`` <-> grouped ``task_instances``.

Background (see ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §3): the canonical shape is now
``task_instances`` — one entry per task, holding that task's idiom list plus the
shared parameters / answer_format / ground_truth. The old ``task_configs`` (one
row per task×idiom) is kept *mirrored* during the transition so the participant,
assignment, sync and stats code paths keep working unchanged. These helpers
convert between the two shapes and run a one-shot, idempotent backfill on startup.
"""

import logging

logger = logging.getLogger(__name__)


def task_instances_to_configs(task_instances: list[dict]) -> list[dict]:
    """Flatten grouped ``task_instances`` into the legacy ``task_configs`` shape.

    Produces one ``{task_id, idiom_id, dataset_id, question_ids}`` row per idiom,
    preserving task and idiom order. A task with no idioms yet still yields one
    row (with an empty idiom_id) so it is not silently dropped.
    """
    configs: list[dict] = []
    for inst in task_instances or []:
        task_id = inst.get("task_id", "")
        dataset_id = inst.get("dataset_id", "")
        question_ids = inst.get("question_ids", []) or []
        idiom_ids = inst.get("idiom_ids", []) or []
        if idiom_ids:
            for idiom_id in idiom_ids:
                configs.append({
                    "task_id": task_id,
                    "idiom_id": idiom_id,
                    "dataset_id": dataset_id,
                    "question_ids": question_ids,
                })
        else:
            configs.append({
                "task_id": task_id,
                "idiom_id": "",
                "dataset_id": dataset_id,
                "question_ids": question_ids,
            })
    return configs


def task_configs_to_instances(task_configs: list[dict]) -> list[dict]:
    """Group legacy ``task_configs`` into ``task_instances``.

    Rows are grouped by ``task_id`` (preserving first-seen order), collecting
    distinct ``idiom_id`` values into ``idiom_ids``. Params / answer_format /
    ground_truth are left at their defaults — they are authored later in the
    /specify and /answer-format-groundtruth steps. ``answer_format`` is left
    ``None`` (the legacy per-task ``Task.answer_type`` is not a col-D format key,
    so we do not guess a mapping here).
    """
    order: list[str] = []
    by_task: dict[str, dict] = {}
    for tc in task_configs or []:
        task_id = tc.get("task_id", "")
        if task_id not in by_task:
            by_task[task_id] = {
                "task_id": task_id,
                "dataset_id": tc.get("dataset_id", ""),
                "idiom_ids": [],
                "parameters": {},
                "answer_format": None,
                "generation_status": "pending",
                "generation_error": None,
                "ground_truth": None,
                "question_ids": tc.get("question_ids", []) or [],
            }
            order.append(task_id)
        inst = by_task[task_id]
        idiom_id = tc.get("idiom_id", "")
        if idiom_id and idiom_id not in inst["idiom_ids"]:
            inst["idiom_ids"].append(idiom_id)
        # Backfill a dataset_id if the first row for this task lacked one.
        if not inst["dataset_id"] and tc.get("dataset_id"):
            inst["dataset_id"] = tc["dataset_id"]
    return [by_task[t] for t in order]


def migrate_experiments_to_task_instances() -> int:
    """Backfill ``task_instances`` for any experiment that lacks them.

    Idempotent: experiments that already have a ``task_instances`` field are
    skipped, so this is safe to run on every startup. Returns the number of
    experiments migrated.
    """
    import ProViBackend.utils.database.connection as dbc

    db = dbc.connect_to_database()
    migrated = 0
    for exp in db["Experiment"].find({"task_instances": {"$exists": False}}):
        instances = task_configs_to_instances(exp.get("task_configs", []))
        db["Experiment"].update_one(
            {"_id": exp["_id"]},
            {"$set": {"task_instances": instances}},
        )
        migrated += 1
    if migrated:
        logger.info("Backfilled task_instances on %d experiment(s).", migrated)
    return migrated
