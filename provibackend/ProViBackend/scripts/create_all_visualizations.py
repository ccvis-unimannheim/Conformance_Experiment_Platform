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
import sys
import warnings
warnings.filterwarnings("ignore")

# Allow `from io_helpers import ...` and `import tasks.task06` when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_helpers import load_event_log, load_model, run_alignments, fitness_summary_dataframe
import tasks.task06 as task06
import tasks.task28 as task28
import tasks.task29 as task29
import tasks.task20 as task20
import tasks.task10 as task10
import tasks.task31 as task31


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
TASK_DIRS     = ["task06", "task28", "task29", "task20", "task10", "task31"]

# Aliases mapping task-script filename stems to canonical idiom_keys.
# E.g. task06.py writes "task06_scatter_plot.svg"; we strip "task06_" then
# rename "scatter_plot" -> "scatterplot" to match the Idiom collection.
_FILE_RENAME = {
    "scatter_plot":              "scatterplot",
    "box_plot":                  "boxplot",
    "table_and_bar_chart":       "table_bar_chart",
    "flow_chart_and_table":      "flow_chart_table",
    "flow_chart_elaborate_bpmn": "flow_chart_elaborate",
    "alignment_table":           "table",
}


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

def run_pipeline(dataset_dir: str, outcome_activity: str = "A_ACTIVATED") -> str:
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
    log         = load_event_log(log_path)
    net, im, fm = load_model(model_path)
    alignments  = run_alignments(log, net, im, fm)
    fitness_df  = fitness_summary_dataframe(alignments)

    def out(task_name: str) -> str:
        d = os.path.join(output_dir, task_name)
        os.makedirs(d, exist_ok=True)
        return d

    generators = [
        ("task06", lambda d: task06.generate(fitness_df,             d)),
        ("task28", lambda d: task28.generate(alignments, model_path, d)),
        ("task29", lambda d: task29.generate(alignments,             d)),
        ("task20", lambda d: task20.generate(log, alignments,        d)),
        ("task10", lambda d: task10.generate(fitness_df,             d)),
        ("task31", lambda d: task31.generate(log, alignments,        d,
                                             outcome_activity=outcome_activity)),
    ]

    for task_name, gen_fn in generators:
        task_dir = out(task_name)
        try:
            gen_fn(task_dir)
        except Exception as e:
            logger.warning(f"{task_name} generation failed: {e}")

        # Each task script writes "taskN_<idiom>.svg"; rename to canonical
        # "<idiom_key>.svg" form, applying _FILE_RENAME aliases.
        for f in pathlib.Path(task_dir).glob("*.svg"):
            stem = f.stem
            parts = stem.split("_", 1)
            idiom_key = parts[1] if len(parts) == 2 else stem
            idiom_key = _FILE_RENAME.get(idiom_key, idiom_key)
            target = pathlib.Path(task_dir) / f"{idiom_key}.svg"
            if f != target:
                f.rename(target)

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
        run_pipeline(args.dataset_dir, outcome_activity=args.outcome_activity)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
