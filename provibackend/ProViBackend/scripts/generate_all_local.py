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
import hashlib
import logging
import os
import pathlib
import pickle
import sys
import time
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_helpers import load_event_log, load_model, run_alignments, fitness_summary_dataframe
from create_all_visualizations import make_task_generators, _postprocess_task_dir

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG   = os.path.join(SCRIPT_DIR, "..", "new_input", "BPIC12_Log_renamed.csv")
DEFAULT_MODEL = os.path.join(SCRIPT_DIR, "..", "new_input", "Model_renamed.bpmn")
DEFAULT_OUT   = "/tmp/provi_svgs"


def _cached_alignments(log_path, model_path, log, net, im, fm, cache_dir):
    """Return alignments, loading a file-signature cache to ensure determinism across re-runs.

    PM4Py optimal alignments are non-deterministic; caching the result means
    re-runs on the same input files produce identical SVGs.
    """
    sig = hashlib.sha1()
    for p in (log_path, model_path):
        try:
            st = os.stat(p)
            sig.update(f"{os.path.basename(p)}:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:
            sig.update(p.encode())
    sig = sig.hexdigest()

    cache_path = os.path.join(cache_dir, ".alignments_cache.pkl")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                blob = pickle.load(f)
            if isinstance(blob, dict) and blob.get("sig") == sig:
                print("  (loaded from cache)")
                return blob["alignments"]
        except Exception:
            pass

    alignments = run_alignments(log, net, im, fm)
    try:
        with open(cache_path, "wb") as f:
            pickle.dump({"sig": sig, "alignments": alignments}, f)
    except Exception:
        pass
    return alignments


def parse_args():
    p = argparse.ArgumentParser(description="Generate all ProVi task SVGs locally.")
    p.add_argument("--log",   default=DEFAULT_LOG,   help="Path to event log (.xes or .csv)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Path to process model (.bpmn)")
    p.add_argument("--out",   default=DEFAULT_OUT,   help="Output root directory")
    p.add_argument("--tasks", default="",            help="Comma-separated task list, e.g. task06,task28 (default: all)")
    p.add_argument("--outcome-activity",            default="Activate Care")
    p.add_argument("--compare-attribute",           default="AMOUNT_REQ")
    p.add_argument("--predominant-threshold",       type=float, default=0.8,
                   help="Threshold for predominant-activity tasks (default: 0.8)")
    p.add_argument("--high-cooccurrence-threshold", type=float, default=0.1,
                   help="Threshold for high co-occurrence tasks (default: 0.1)")
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
    alignments  = _cached_alignments(log_path, model_path, log, net, im, fm, out_root)
    fitness_df  = fitness_summary_dataframe(alignments)
    print(f"  done ({time.time()-t0:.1f}s)")
    print()

    # ── Build generators via shared make_task_generators ────────────────────
    gen_map = make_task_generators(
        log, alignments, fitness_df, model_path,
        compare_attribute=args.compare_attribute,
        params={
            "outcome_activity":             args.outcome_activity,
            "predominant_threshold":        args.predominant_threshold,
            "high_cooccurrence_threshold":  args.high_cooccurrence_threshold,
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
            _postprocess_task_dir(task_name, task_dir)
            count = len(list(pathlib.Path(task_dir).glob("*.svg")))
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
