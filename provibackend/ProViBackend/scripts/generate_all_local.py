#!/usr/bin/env python3
"""
generate_all_local.py – Generate all task SVGs locally for review.

Usage:
    python generate_all_local.py [--log LOG] [--model MODEL] [--out OUT]

Defaults:
    --log   ../new_input/BPIC12_Log_renamed.csv
    --model ../new_input/Model_renamed.bpmn
    --out   /tmp/provi_svgs
"""

import argparse
import logging
import os
import pathlib
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_helpers import load_event_log, load_model, run_alignments, fitness_summary_dataframe
from create_all_visualizations import make_task_generators, _FILE_RENAME, _TASK_RENAME_SKIP

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG   = os.path.join(SCRIPT_DIR, "..", "new_input", "BPIC12_Log_renamed.csv")
DEFAULT_MODEL = os.path.join(SCRIPT_DIR, "..", "new_input", "Model_renamed.bpmn")
DEFAULT_OUT   = "/tmp/provi_svgs"


def parse_args():
    p = argparse.ArgumentParser(description="Generate all ProVi task SVGs locally.")
    p.add_argument("--log",   default=DEFAULT_LOG,   help="Path to event log (.xes or .csv)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Path to process model (.bpmn)")
    p.add_argument("--out",   default=DEFAULT_OUT,   help="Output root directory")
    p.add_argument("--tasks", default="",            help="Comma-separated task list, e.g. task06,task28 (default: all)")
    p.add_argument("--outcome-activity", default="Activate Care")
    p.add_argument("--compare-attribute", default="AMOUNT_REQ")
    return p.parse_args()


def main():
    args = parse_args()

    log_path   = os.path.abspath(args.log)
    model_path = os.path.abspath(args.model)
    out_root   = os.path.abspath(args.out)

    if not os.path.exists(log_path):
        print(f"ERROR: log not found: {log_path}"); sys.exit(1)
    if not os.path.exists(model_path):
        print(f"ERROR: model not found: {model_path}"); sys.exit(1)

    os.makedirs(out_root, exist_ok=True)

    print(f"Log   : {log_path}")
    print(f"Model : {model_path}")
    print(f"Out   : {out_root}")
    print()

    # ── Load & align ────────────────────────────────────────────────────────
    print("Loading event log …")
    t0  = time.time()
    log = load_event_log(log_path)
    print(f"  {len(log)} traces loaded ({time.time()-t0:.1f}s)")

    print("Running alignments …")
    t0          = time.time()
    net, im, fm = load_model(model_path)
    alignments  = run_alignments(log, net, im, fm)
    fitness_df  = fitness_summary_dataframe(alignments)
    print(f"  done ({time.time()-t0:.1f}s)")
    print()

    # ── Build generators via shared make_task_generators ────────────────────
    gen_map = make_task_generators(
        log, alignments, fitness_df, model_path,
        compare_attribute=args.compare_attribute,
        params={
            "outcome_activity":  args.outcome_activity,
            "compare_attribute": args.compare_attribute,
        },
    )

    task_list  = sorted(gen_map.items())
    filter_set = set(t.strip() for t in args.tasks.split(",") if t.strip())
    if filter_set:
        task_list = [(k, v) for k, v in task_list if k in filter_set]

    # ── Run generators ───────────────────────────────────────────────────────
    results = {}
    for task_name, gen_fn in task_list:
        task_dir = os.path.join(out_root, task_name)
        os.makedirs(task_dir, exist_ok=True)
        print(f"  [{task_name}] generating …", end=" ", flush=True)
        t0 = time.time()
        try:
            gen_fn(task_dir)
            # Rename stems to canonical idiom keys
            skip  = _TASK_RENAME_SKIP.get(task_name, set())
            count = 0
            for f in pathlib.Path(task_dir).glob("*.svg"):
                stem      = f.stem
                parts     = stem.split("_", 1)
                idiom_key = parts[1] if (len(parts) == 2 and re.fullmatch(r"task\d+", parts[0])) else stem
                if idiom_key not in skip:
                    idiom_key = _FILE_RENAME.get(idiom_key, idiom_key)
                target = pathlib.Path(task_dir) / f"{idiom_key}.svg"
                if f != target:
                    f.replace(target)
                count += 1
            print(f"✓  {count} SVGs  ({time.time()-t0:.1f}s)")
            results[task_name] = ("ok", count)
        except Exception as e:
            print(f"✗  ERROR: {e}")
            results[task_name] = ("error", str(e))

    # ── Summary ─────────────────────────────────────────────────────────────
    ok         = [k for k, v in results.items() if v[0] == "ok"]
    error      = [k for k, v in results.items() if v[0] == "error"]
    total_svgs = sum(v[1] for v in results.values() if v[0] == "ok")

    print()
    print(f"Done. {len(ok)}/{len(results)} tasks succeeded, {total_svgs} SVGs total.")
    print(f"Output: {out_root}/")
    if error:
        print("\nFailed tasks:")
        for k in error:
            print(f"  {k}: {results[k][1]}")


if __name__ == "__main__":
    main()
