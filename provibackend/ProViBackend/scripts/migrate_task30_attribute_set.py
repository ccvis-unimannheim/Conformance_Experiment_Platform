#!/usr/bin/env python3
"""Move task30's stored attribute choice to the key its picker now uses.

task30 used to split by a single attribute, so /specify stored the choice under
`compare_attribute` (or `compare_event_condition` / `compare_log_attribute` for
the other levels). It now offers the same multi-select picker as the rest of the
family — one predictor side for all eight tasks — which reads `attribute_set`,
`event_conditions` and `log_attributes`.

Left alone, an experiment configured before the change would arrive with those
keys empty, fall into "empty = every attribute that can be grouped", and draw a
different attribute than the admin chose, without saying so.

    docker compose exec provibackend python ProViBackend/scripts/migrate_task30_attribute_set.py
    docker compose exec provibackend python ProViBackend/scripts/migrate_task30_attribute_set.py --apply

Only task30's own instances are touched: `compare_attribute` is still task32's
key and the pipeline's fallback, so it is copied, not moved. Idempotent.
"""
import argparse
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ProViBackend.app.main import _SEED_NAMESPACE           # noqa: E402
from ProViBackend.utils.database import connection as dbc   # noqa: E402

TASK30_ID = str(uuid.uuid5(_SEED_NAMESPACE, "task30"))

# single-value key -> the multi-select key that replaced it
MOVES = {
    "compare_attribute": "attribute_set",
    "compare_event_condition": "event_conditions",
    "compare_log_attribute": "log_attributes",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args()

    db = dbc.connect_to_database()
    planned = []

    for exp in db["Experiment"].find({"task_instances.task_id": TASK30_ID}):
        for inst in exp.get("task_instances") or []:
            if inst.get("task_id") != TASK30_ID:
                continue
            params = inst.get("parameters") or {}
            for old_key, new_key in MOVES.items():
                value = params.get(old_key)
                if not value or params.get(new_key):
                    continue
                planned.append((exp.get("_id"), exp.get("name") or "?",
                                old_key, new_key, value))

    print(f"{len(planned)} task30 instance parameter(s) to carry over:")
    for _id, name, old_key, new_key, value in planned:
        print(f"  {name} ({_id}): {old_key}={value!r} -> {new_key}=[{value!r}]")
    if not planned:
        print("  none — every task30 instance already uses the family's keys")
        return 0

    if not args.apply:
        print("\nNothing written. Re-run with --apply.")
        return 0

    written = 0
    for _id, _name, old_key, new_key, value in planned:
        result = db["Experiment"].update_one(
            {"_id": _id, "task_instances.task_id": TASK30_ID},
            {"$set": {f"task_instances.$.parameters.{new_key}": [value]}},
        )
        written += result.modified_count
    print(f"\nCarried over {written} parameter(s). The old keys are left in place: "
          f"`compare_attribute` is still task32's and the pipeline's own.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
