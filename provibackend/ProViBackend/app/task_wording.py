"""What one experiment calls each of its tasks.

The `Task` collection is the shared question bank: `seed_data.py` owns it, the
startup seed rewrites it, and every experiment shows its wording by default. An
admin who rewords a question on /task or /overview is answering for *their*
experiment, so that text is stored on the experiment document
(`task_overrides`, task_id -> {label, description, answer_type}) and read back
through here.

It lives on the experiment rather than on its `task_instances` because the
rewording happens while the tasks are still being chosen — a task has no
instance until the wizard step is saved — and because an override should
survive deselecting the task and picking it again.
"""
WORDING_FIELDS = ("label", "description", "answer_type")


def effective_wording(exp: dict | None, task_id: str, task: dict | None,
                      instance: dict | None = None) -> dict:
    """The wording this experiment asks `task_id` with.

    `instance` is the copy of the bank that experiments used to freeze onto
    their task_instances. It still outranks the bank, so an experiment that has
    already run keeps the text its participants saw, until
    `scripts/reseed_task_questions.py --apply` clears it.
    """
    override = ((exp or {}).get("task_overrides") or {}).get(task_id) or {}
    return {
        # A field the admin cleared is present and empty, and stays empty: they
        # deleted that description on purpose. A field they never touched is
        # absent, and reads through.
        field: (override[field] if field in override
                else ((instance or {}).get(field)
                      or (task or {}).get(field)
                      or ""))
        for field in WORDING_FIELDS
    }
