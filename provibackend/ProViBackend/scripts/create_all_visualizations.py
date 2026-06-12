#!/usr/bin/env python3
"""
create_all_visualizations.py – CC Visualization Pipeline entry point.

Designed for the dataset-folder convention used on the server:

    data/{dataset_id}/
        input/
            EventLog.xes               (or EventLog.csv)
            Guideline.bpmn
        output/
            task06/  task06_bar_chart.svg, task06_table.svg, ...
            task28/  ...
            ...

Two ways to run:

1) CLI (local testing / manual server runs):

       python create_all_visualizations.py \
           --dataset-dir data/abc123 \
           [--outcome-activity A_ACTIVATED]

   The script auto-detects EventLog.xes / EventLog.csv inside <dataset-dir>/input/
   alongside Guideline.bpmn, and writes SVGs to <dataset-dir>/output/.

2) Programmatic (called by the FastAPI BackgroundTask):

       from create_all_visualizations import run_pipeline
       run_pipeline(dataset_dir="data/abc123",
                    outcome_activity="A_ACTIVATED")

Both paths share the same `run_pipeline()` function, so behaviour stays
identical whether run from CLI or from the backend.
"""

import logging

logger = logging.getLogger(__name__)

import argparse
import os
import re
import sys
import warnings
warnings.filterwarnings("ignore")

# Allow `from io_helpers import ...` and `import tasks.task06` when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_helpers import load_event_log, load_model, run_alignments, fitness_summary_dataframe
import tasks.task01 as task01
import tasks.task02 as task02
import tasks.task03 as task03
import tasks.task04 as task04
import tasks.task05 as task05
import tasks.task06 as task06
import tasks.task07 as task07
import tasks.task08 as task08
import tasks.task09 as task09
import tasks.task10 as task10
import tasks.task11 as task11
import tasks.task12 as task12
import tasks.task13 as task13
import tasks.task17 as task17
import tasks.task18 as task18
import tasks.task19 as task19
import tasks.task20 as task20
import tasks.task21 as task21
import tasks.task22 as task22
import tasks.task23 as task23
import tasks.task24 as task24
import tasks.task25 as task25
import tasks.task26 as task26
import tasks.task27 as task27
import tasks.task28 as task28
import tasks.task29 as task29
import tasks.task30 as task30
import tasks.task31 as task31
import tasks.task32 as task32
import tasks.task33 as task33
import tasks.task34 as task34
import tasks.task35 as task35
import tasks.task36 as task36
import tasks.task37 as task37


# ---------------------------------------------------------------------------
# Filename conventions inside a dataset directory
#
# Server-side dataset layout (root: data/<pair_id>/):
#     input/
#         <any filename>.xes  (or .csv)  ← event log
#         <any filename>.bpmn            ← process model
#     output/
#         task06/  task28/  task29/  task20/  task10/  task31/
# ---------------------------------------------------------------------------

INPUT_SUBDIR  = "input"
OUTPUT_SUBDIR = "output"
LOG_EXTENSIONS   = {".xes", ".csv"}
MODEL_EXTENSIONS = {".bpmn"}
TASK_DIRS     = ["task01", "task02", "task03", "task04", "task05", "task06", "task07", "task08", "task09", "task10", "task11", "task12", "task13", "task17", "task18", "task19", "task20", "task21", "task22", "task23", "task24", "task25", "task26", "task27", "task28", "task29", "task30", "task31", "task32", "task33", "task34", "task35", "task36", "task37"]

# Aliases mapping task-script filename stems to canonical idiom_keys.
# E.g. task06.py writes "task06_scatter_plot.svg"; we strip "task06_" then
# rename "scatter_plot" -> "scatterplot" to match the Idiom collection.
_FILE_RENAME = {
    "scatter_plot":                   "scatterplot",
    "box_plot":                       "boxplot",
    "table_and_bar_chart":            "table_bar_chart",
    "flow_chart_and_table":           "flow_chart_table",
    "flow_chart_elaborate_bpmn":      "flow_chart_elaborate",
    "flow_chart_elaborate_bpmn_table":"flow_chart_elaborate_table",
    "alignment_table":                "table",
}

# Per-task idiom keys that must NOT go through _FILE_RENAME.
# task08 uses scatter_plot (SVG) which is distinct from scatterplot (echarts).
_TASK_RENAME_SKIP: dict[str, set[str]] = {
    "task08": {"scatter_plot"},
    "task19": {"scatter_plot"},
    "task22": {"scatter_plot"},
    "task33": {"scatter_plot"},
    "task37": {"scatter_plot"},
}


def _auto_detect_compare_attribute(log, preferred: str) -> str:
    """Pick the best case attribute for sub-log splitting.

    Priority:
      1. preferred — if it exists in the log, use it.
      2. Numeric case attribute with highest std (median split).
      3. Categorical case attribute with 2–10 distinct values.
      4. preferred as fallback (split_by_attribute will emit an empty-state SVG).
    """
    import numpy as np

    _SKIP = {"concept:name", "variant", "variant-index", "creator", "library"}

    attr_values: dict = {}
    for trace in log:
        attrs = getattr(trace, "attributes", {}) or {}
        for k, v in attrs.items():
            if k in _SKIP or k.startswith(":"):
                continue
            attr_values.setdefault(k, []).append(v)

    if not attr_values:
        return preferred
    if preferred in attr_values:
        return preferred

    # Numeric candidates — need 80 %+ parseable values and non-zero std
    numeric_candidates = []
    for k, vals in attr_values.items():
        nums = []
        for v in vals:
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                pass
        if len(nums) >= len(vals) * 0.8 and len(nums) > 1:
            std = float(np.std(nums))
            if std > 0:
                numeric_candidates.append((k, std))
    if numeric_candidates:
        numeric_candidates.sort(key=lambda x: -x[1])
        return numeric_candidates[0][0]

    # Categorical candidates — 2–10 distinct values
    categorical_candidates = []
    for k, vals in attr_values.items():
        distinct = len({str(v) for v in vals if v is not None})
        if 2 <= distinct <= 10:
            categorical_candidates.append((k, distinct))
    if categorical_candidates:
        categorical_candidates.sort(key=lambda x: x[1])
        return categorical_candidates[0][0]

    return preferred


def _resolve_dataset_paths(dataset_dir: str):
    """Locate log and model files inside <dataset_dir>/input/ by extension; create output dir."""
    if not os.path.isdir(dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    input_dir = os.path.join(dataset_dir, INPUT_SUBDIR)
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(
            f"Input directory not found: {input_dir} "
            f"(expected '{INPUT_SUBDIR}/' subfolder inside the dataset directory)"
        )

    log_path = None
    model_path = None
    for fname in os.listdir(input_dir):
        ext = os.path.splitext(fname)[1].lower()
        full = os.path.join(input_dir, fname)
        if ext in LOG_EXTENSIONS and log_path is None:
            log_path = full
        elif ext in MODEL_EXTENSIONS and model_path is None:
            model_path = full

    if log_path is None:
        raise FileNotFoundError(
            f"No event log found in {input_dir}. "
            f"Expected a file with extension: {', '.join(sorted(LOG_EXTENSIONS))}"
        )
    if model_path is None:
        raise FileNotFoundError(
            f"No process model found in {input_dir}. "
            f"Expected a file with extension: {', '.join(sorted(MODEL_EXTENSIONS))}"
        )

    output_dir = os.path.join(dataset_dir, OUTPUT_SUBDIR)
    os.makedirs(output_dir, exist_ok=True)

    return log_path, model_path, output_dir


# ---------------------------------------------------------------------------
# Public entry point – called by both the CLI and the FastAPI backend
# ---------------------------------------------------------------------------

def run_pipeline(dataset_dir: str, outcome_activity: str = "A_ACTIVATED",
                 compare_attribute: str = "AMOUNT_REQ") -> str:
    """Run the full visualization pipeline for one dataset directory.

    Parameters
    ----------
    dataset_dir : str
        Path to the dataset folder (must contain input/EventLog.{xes|csv}
        and input/Guideline.bpmn).
    output_dir : str, optional
        Where to write task SVG subdirectories.  Defaults to
        ``<dataset_dir>/output/`` when not supplied.
    outcome_activity : str
        Activity name that marks a positive process outcome (used by Task 6).
    compare_attribute : str
        Case-level data attribute used by Task 30 to split the log into
        sub-logs (numeric → median split, categorical → value groups).

    Returns
    -------
    str
        Absolute path to the directory that received the SVGs.
    """
    import pathlib

    log_path, model_path, output_dir = _resolve_dataset_paths(dataset_dir)

    logger.error(f"Dataset directory : {os.path.abspath(dataset_dir)}")
    logger.info(f"Event log         : {log_path}")
    logger.info(f"Process model     : {model_path}")
    logger.info(f"Output directory  : {output_dir}")
    logger.info(f"Outcome activity  : {outcome_activity}")
    logger.info(f"Compare attribute : {compare_attribute}")
    log         = load_event_log(log_path)
    compare_attribute = _auto_detect_compare_attribute(log, compare_attribute)
    logger.info(f"Compare attribute (resolved): {compare_attribute}")
    net, im, fm = load_model(model_path)
    alignments  = run_alignments(log, net, im, fm)
    fitness_df  = fitness_summary_dataframe(alignments)

    def out(task_name: str) -> str:
        d = os.path.join(output_dir, task_name)
        os.makedirs(d, exist_ok=True)
        return d

    generators = [
        ("task01", lambda d: task01.generate(log, fitness_df,        d,
                                             outcome_activity=outcome_activity)),
        ("task02", lambda d: task02.generate(fitness_df,             d)),
        ("task03", lambda d: task03.generate(log, fitness_df,        d)),
        ("task04", lambda d: task04.generate(log, fitness_df,        d)),
        ("task05", lambda d: task05.generate(log, alignments,        d,
                                             outcome_activity=outcome_activity)),
        ("task06", lambda d: task06.generate(fitness_df,             d,
                                             log=log, alignments=alignments, model_path=model_path)),
        ("task07", lambda d: task07.generate(log, fitness_df,        d)),
        ("task08", lambda d: task08.generate(log, alignments,        d)),
        ("task09", lambda d: task09.generate(log, alignments,        d, model_path=model_path)),
        ("task10", lambda d: task10.generate(fitness_df,             d, log=log)),
        ("task11", lambda d: task11.generate(log, alignments,        d, model_path=model_path)),
        ("task12", lambda d: task12.generate(log, alignments,        d)),
        ("task13", lambda d: task13.generate(log, alignments, model_path, d)),
        ("task17", lambda d: task17.generate(log, alignments,        d,
                                             model_path=model_path)),
        ("task18", lambda d: task18.generate(log, alignments, model_path, d)),
        ("task19", lambda d: task19.generate(log, alignments, model_path, d,
                                             outcome_activity=outcome_activity)),
        ("task20", lambda d: task20.generate(log, alignments,        d, model_path=model_path)),
        ("task21", lambda d: task21.generate(log, alignments, model_path, d)),
        ("task22", lambda d: task22.generate(log, fitness_df, alignments, d,
                                             model_path=model_path,
                                             compare_attribute=compare_attribute)),
        ("task23", lambda d: task23.generate(alignments,             d, log=log)),
        ("task24", lambda d: task24.generate(log, model_path,        d)),
        ("task25", lambda d: task25.generate(log, fitness_df,        d, model_path=model_path)),
        ("task26", lambda d: task26.generate(alignments,             d, model_path=model_path)),
        ("task27", lambda d: task27.generate(log, fitness_df, alignments, d, model_path=model_path)),
        ("task28", lambda d: task28.generate(alignments, model_path, d)),
        ("task29", lambda d: task29.generate(alignments,             d)),
        ("task30", lambda d: task30.generate(log, fitness_df, alignments, d,
                                             compare_attribute=compare_attribute)),
        ("task31", lambda d: task31.generate(log, alignments,        d,
                                             outcome_activity=outcome_activity)),
        ("task32", lambda d: task32.generate(log, alignments,        d,
                                             compare_attribute=compare_attribute)),
        ("task33", lambda d: task33.generate(log, fitness_df,        d,
                                             compare_attribute=compare_attribute)),
        ("task34", lambda d: task34.generate(log, alignments,        d, model_path=model_path)),
        ("task35", lambda d: task35.generate(log, alignments,        d, model_path=model_path)),
        ("task36", lambda d: task36.generate(log, alignments,        d, model_path=model_path)),
        ("task37", lambda d: task37.generate(log, alignments,        d, model_path=model_path)),
    ]

    for task_name, gen_fn in generators:
        task_dir = out(task_name)
        try:
            gen_fn(task_dir)
        except Exception as e:
            logger.warning(f"{task_name} generation failed: {e}")

        # Each task script writes "taskN_<idiom>.svg"; rename to canonical
        # "<idiom_key>.svg" form, applying _FILE_RENAME aliases.
        # Only strip a real "taskNN_" prefix — already-canonical files (from a
        # previous run on the same output dir) must pass through unchanged,
        # otherwise "bar_chart.svg" would degrade to "chart.svg" on re-runs.
        skip = _TASK_RENAME_SKIP.get(task_name, set())
        for f in pathlib.Path(task_dir).glob("*.svg"):
            stem = f.stem
            parts = stem.split("_", 1)
            if len(parts) == 2 and re.fullmatch(r"task\d+", parts[0]):
                idiom_key = parts[1]
            else:
                idiom_key = stem
            if idiom_key not in skip:
                idiom_key = _FILE_RENAME.get(idiom_key, idiom_key)
            target = pathlib.Path(task_dir) / f"{idiom_key}.svg"
            if f != target:
                # replace() overwrites existing targets on all platforms
                # (os.rename would fail on Windows when re-running on a
                #  non-empty output directory)
                f.replace(target)

    logger.info("\nDone! SVGs written to:")
    for t in TASK_DIRS:
        logger.info(f"  {os.path.join(output_dir, t)}/")
    return os.path.abspath(output_dir)


# ---------------------------------------------------------------------------
# CLI wrapper
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="CC Visualization Pipeline – generates SVGs for conformance checking tasks."
    )
    parser.add_argument(
        "--dataset-dir", required=True,
        help="Path to the dataset folder containing EventLog.{xes|csv} and Model.bpmn",
    )
    parser.add_argument(
        "--outcome-activity", default="A_ACTIVATED",
        help="Activity name that marks a positive outcome (Task 6). Default: A_ACTIVATED",
    )
    parser.add_argument(
        "--compare-attribute", default="AMOUNT_REQ",
        help="Case attribute used by Task 30 to split the log into sub-logs "
             "(numeric: median split, categorical: value groups). Default: AMOUNT_REQ",
    )
    return parser.parse_args()


def _configure_cli_logging(level: int = logging.INFO):
    """Configure logging when running as a CLI script.

    The FastAPI backend will configure its own logging — this helper is only
    used when run_pipeline() is invoked from the command line. It writes to
    stdout in a format that also looks clean inside Docker logs.
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. by FastAPI / uvicorn) — don't touch
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(handler)
    root.setLevel(level)


def main():
    _configure_cli_logging()
    args = parse_args()
    try:
        run_pipeline(args.dataset_dir, outcome_activity=args.outcome_activity,
                     compare_attribute=args.compare_attribute)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
