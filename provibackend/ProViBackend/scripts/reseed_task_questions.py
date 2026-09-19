#!/usr/bin/env python3
"""Report — and optionally repair — Task questions that the startup seed skips.

`main.py._seed_collection` upserts `seed_data.CANONICAL_TASKS` on every startup,
but skips any document flagged `_admin_edited`: once an admin has edited a
question through `PATCH /admin/tasks/{id}` (the Edit dialog on /task), the code
no longer owns it, so a restart cannot silently discard their wording. The cost
is that a later change to seed_data.py never reaches those documents either —
the deploy succeeds, the container restarts, and the page still shows the old
question.

This script says which documents are in that state and what they would become,
and with --apply writes the canonical wording and clears the flag.

    docker compose exec provibackend python ProViBackend/scripts/reseed_task_questions.py
    docker compose exec provibackend python ProViBackend/scripts/reseed_task_questions.py --apply

Running experiments are unaffected either way: a task_instance keeps the label
snapshotted when it was configured (participant.py reads `ti["label"]` first),
so this changes the question bank, not an experiment already in the field.
"""
import argparse
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ProViBackend.app.main import _SEED_NAMESPACE           # noqa: E402
from ProViBackend.app.seed_data import CANONICAL_TASKS      # noqa: E402
from ProViBackend.utils.database import connection as dbc   # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="write the canonical labels and clear _admin_edited")
    args = parser.parse_args()

    db = dbc.connect_to_database()
    pinned, stale, ok, missing = [], [], 0, []

    for item in CANONICAL_TASKS:
        _id = str(uuid.uuid5(_SEED_NAMESPACE, item["task_key"]))
        doc = db["Task"].find_one({"_id": _id})
        if doc is None:
            missing.append(item["task_key"])
            continue
        differs = doc.get("label") != item["label"]
        if doc.get("_admin_edited"):
            pinned.append((item["task_key"], doc.get("label", ""), item["label"], differs))
        elif differs:
            stale.append((item["task_key"], doc.get("label", ""), item["label"]))
        else:
            ok += 1

    print(f"{len(CANONICAL_TASKS)} canonical tasks: {ok} already match, "
          f"{len(pinned)} admin-edited, {len(stale)} differ without the flag, "
          f"{len(missing)} not in the database")

    if stale:
        print("\nDiffer but NOT flagged — a restart alone fixes these:")
        for key, old, new in stale:
            print(f"  {key}\n    is:     {old}\n    should: {new}")

    if pinned:
        print("\nAdmin-edited, so the seed skips them:")
        for key, old, new, differs in pinned:
            mark = "" if differs else "   (same wording anyway)"
            print(f"  {key}{mark}\n    is:     {old}\n    would:  {new}")

    if missing:
        print("\nNot in the database at all (the seed will insert them on the next "
              f"restart): {', '.join(missing)}")

    if not args.apply:
        if pinned or stale:
            print("\nNothing written. Re-run with --apply to write the canonical "
                  "wording and clear the flag.")
        return 0

    written = 0
    for item in CANONICAL_TASKS:
        _id = str(uuid.uuid5(_SEED_NAMESPACE, item["task_key"]))
        result = db["Task"].update_one(
            {"_id": _id},
            {"$set": {k: v for k, v in item.items()},
             "$unset": {"_admin_edited": ""}},
        )
        written += result.modified_count
    print(f"\nWrote {written} document(s). The flag is cleared, so future "
          f"seed_data.py changes reach them on restart until an admin edits "
          f"them again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
