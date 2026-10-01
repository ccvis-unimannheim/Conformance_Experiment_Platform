#!/usr/bin/env python3
"""Drop the ground-truth data left behind by the answer-format refactor.

Automatic grading is gone: task instances now carry `answer_format` +
`number_kind` + `answer_options`, all authored by the admin, and answers are
recorded rather than scored. This removes the fields and the collection that
served the old model. Nothing is converted — the stored option sets were built
around correctness flags, and every stored answer_format key (yes-no, pct,
count, decimal, pct-set, count-set) has been retired.

After running this, every experiment's answer format must be re-chosen on
/admin/experiments/answer-format before it can be published.

    Experiment.task_instances[].ground_truth            removed
    Experiment.task_instances[].ground_truth_by_format  removed
    Experiment.task_instances[].answer_format           removed (keys retired)
    Answer.is_correct                                   removed
    Answer.ground_truth_id                              removed
    PreliminaryAnswers.ground_truth_id                  removed
    GroundTruth collection                              dropped

Usage:
    python scripts/drop_ground_truth_data.py --dry-run
    python scripts/drop_ground_truth_data.py --yes
"""
import argparse
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

import ProViBackend.utils.database.connection as dbc

TI_FIELDS = ["ground_truth", "ground_truth_by_format", "answer_format"]
ANSWER_FIELDS = ["is_correct", "ground_truth_id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be removed and exit")
    ap.add_argument("--yes", action="store_true",
                    help="apply the changes (required unless --dry-run)")
    args = ap.parse_args()
    if not args.dry_run and not args.yes:
        ap.error("pass --dry-run to preview, or --yes to apply")

    db = dbc.connect_to_database()

    ti_hits = [d for d in db["Experiment"].find({})
               if any(f in ti for ti in d.get("task_instances", []) for f in TI_FIELDS)]
    answers = db["Answer"].count_documents(
        {"$or": [{f: {"$exists": True}} for f in ANSWER_FIELDS]})
    prelim = db["PreliminaryAnswers"].count_documents({"ground_truth_id": {"$exists": True}})
    has_gt = "GroundTruth" in db.list_collection_names()
    gt_docs = db["GroundTruth"].estimated_document_count() if has_gt else 0

    print(f"Experiment documents with ground-truth fields : {len(ti_hits)}")
    print(f"Answer documents with grading fields          : {answers}")
    print(f"PreliminaryAnswers with ground_truth_id       : {prelim}")
    print(f"GroundTruth collection documents              : {gt_docs}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    # task_instances is an array, so each experiment is rewritten explicitly
    # rather than with an all-positional $[] update: it keeps the script
    # independent of the server's MongoDB version and easy to test.
    for doc in ti_hits:
        instances = [{k: v for k, v in ti.items() if k not in TI_FIELDS}
                     for ti in doc.get("task_instances", [])]
        db["Experiment"].update_one({"_id": doc["_id"]},
                                    {"$set": {"task_instances": instances}})

    r2 = db["Answer"].update_many({}, {"$unset": {f: "" for f in ANSWER_FIELDS}})
    r3 = db["PreliminaryAnswers"].update_many({}, {"$unset": {"ground_truth_id": ""}})
    if has_gt:
        db["GroundTruth"].drop()

    print(f"\nExperiment         : {len(ti_hits)} rewritten")
    print(f"Answer             : {r2.modified_count} modified")
    print(f"PreliminaryAnswers : {r3.modified_count} modified")
    print(f"GroundTruth        : {'dropped' if has_gt else 'not present'}")
    print("\nRe-choose each experiment's answer format on /admin/experiments/answer-format.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
