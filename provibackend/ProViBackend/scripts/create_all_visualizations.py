#!/usr/bin/env python3
"""
create_all_visualizations.py – CC Visualization Pipeline entry point.

Designed for the dataset-folder convention used on the server:

    data/{dataset_id}/
        input/
            EventLog.xes               (or EventLog.csv)
            Guideline.bpmn
        output/
            task1/  task1_bar_chart.svg, task1_table.svg, ...
            task2/  ...
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

# Allow `from io_helpers import ...` and `import tasks.task1` when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_helpers import load_event_log, load_model, run_alignments, fitness_summary_dataframe
import tasks.task1 as task1
import tasks.task2 as task2
import tasks.task3 as task3
import tasks.task4 as task4
import tasks.task5 as task5
import tasks.task6 as task6


# ---------------------------------------------------------------------------
# Filename conventions inside a dataset directory
#
# Server-side dataset layout (root: data/<dataset_id>/):
#     input/
#         EventLog.xes  (or EventLog.csv)
#         Guideline.bpmn
#     output/
#         task1/  task2/  ...  task6/
# ---------------------------------------------------------------------------

INPUT_SUBDIR    = "input"
OUTPUT_SUBDIR   = "output"
LOG_FILENAMES   = ["EventLog.xes", "EventLog.csv"]
MODEL_FILENAME  = "Guideline.bpmn"
TASK_DIRS       = ["task1", "task2", "task3", "task4", "task5", "task6"]


def _resolve_dataset_paths(dataset_dir: str):
    """Locate EventLog and Guideline inside <dataset_dir>/input/; create output dir."""
    if not os.path.isdir(dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    input_dir = os.path.join(dataset_dir, INPUT_SUBDIR)
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(
            f"Input directory not found: {input_dir} "
            f"(expected '{INPUT_SUBDIR}/' subfolder inside the dataset directory)"
        )

    log_path = None
    for candidate in LOG_FILENAMES:
        path = os.path.join(input_dir, candidate)
        if os.path.isfile(path):
            log_path = path
            break
    if log_path is None:
        raise FileNotFoundError(
            f"No event log found in {input_dir}. "
            f"Expected one of: {', '.join(LOG_FILENAMES)}"
        )

    model_path = os.path.join(input_dir, MODEL_FILENAME)
    if not os.path.isfile(model_path):
        raise FileNotFoundError(
            f"Process model not found: {model_path} (expected '{MODEL_FILENAME}')"
        )

    output_dir = os.path.join(dataset_dir, OUTPUT_SUBDIR)
    os.makedirs(output_dir, exist_ok=True)

    return log_path, model_path, output_dir


# ---------------------------------------------------------------------------
# Public entry point – called by both the CLI and the FastAPI backend
# ---------------------------------------------------------------------------

def run_pipeline(dataset_dir: str, output_dir: str = None,
                 outcome_activity: str = "A_ACTIVATED") -> str:
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
    log_path, model_path, default_output_dir = _resolve_dataset_paths(dataset_dir)
    output_dir = output_dir or default_output_dir
    os.makedirs(output_dir, exist_ok=True)

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
        return os.path.join(output_dir, task_name)

    task1.generate(fitness_df,             out("task1"))
    task2.generate(alignments, model_path, out("task2"))
    task3.generate(alignments,             out("task3"))
    task4.generate(log, alignments,        out("task4"))
    task5.generate(fitness_df,             out("task5"))
    task6.generate(log, alignments,        out("task6"),
                   outcome_activity=outcome_activity)

    logger.info("\nDone! SVGs written to:")
    for t in TASK_DIRS:
        logger.info(f"  {out(t)}/")
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
