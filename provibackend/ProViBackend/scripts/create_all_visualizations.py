#!/usr/bin/env python3
"""
create_all_visualizations.py – CC Visualization Pipeline entry point.

Usage:
    python create_all_visualizations.py \
        --log   <path_to_log.xes_or_.csv> \
        --model <path_to_model.bpmn> \
        --output <output_directory> \
        [--outcome-activity <activity_name>]
"""

import argparse
import os
import sys
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from io_helpers import load_event_log, load_model, run_alignments, fitness_summary_dataframe
import tasks.task1 as task1
import tasks.task2 as task2
import tasks.task3 as task3
import tasks.task4 as task4
import tasks.task5 as task5
import tasks.task6 as task6


def parse_args():
    parser = argparse.ArgumentParser(
        description="CC Visualization Pipeline – generates SVGs for conformance checking tasks."
    )
    parser.add_argument("--log",    required=True, help="Path to the input event log (.xes or .csv)")
    parser.add_argument("--model",  required=True, help="Path to the process model (.bpmn)")
    parser.add_argument("--output", required=True, help="Directory where SVGs will be saved")
    parser.add_argument(
        "--outcome-activity", default="A_ACTIVATED",
        help="Activity name that constitutes a positive process outcome (Task 6). Default: A_ACTIVATED",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    for path, label in [(args.log, "Event log"), (args.model, "Model")]:
        if not os.path.isfile(path):
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            sys.exit(1)

    log         = load_event_log(args.log)
    net, im, fm = load_model(args.model)
    alignments  = run_alignments(log, net, im, fm)
    fitness_df  = fitness_summary_dataframe(alignments)

    def out(t): return os.path.join(args.output, t)

    task1.generate(fitness_df,             out("task1"))
    task2.generate(alignments, args.model, out("task2"))
    task3.generate(alignments,             out("task3"))
    task4.generate(log, alignments,        out("task4"))
    task5.generate(fitness_df,             out("task5"))
    task6.generate(log, alignments,        out("task6"),
                   outcome_activity=args.outcome_activity)

    print("\nDone! SVGs written to:")
    for t in ["task1","task2","task3","task4","task5","task6"]:
        print(f"  {out(t)}/")


_FILE_RENAME = {
    "scatter_plot":            "scatterplot",
    "box_plot":                "boxplot",
    "table_and_bar_chart":     "table_bar_chart",
    "flow_chart_and_table":    "flow_chart_table",
    "flow_chart_elaborate_bpmn": "flow_chart_elaborate",
    "alignment_table":         "table",
}


def create_all_visualizations(log_path, output_dir, model_path):
    """
    Programmatic entry point. Generates SVGs into output_dir using task_key naming:
      output_dir/T-01/bar_chart.svg, T-02/flow_chart_basic.svg, etc.
    """
    import pathlib, shutil
    log_path   = str(log_path)
    model_path = str(model_path)
    output_dir = str(output_dir)

    log         = load_event_log(log_path)
    net, im, fm = load_model(model_path)
    alignments  = run_alignments(log, net, im, fm)
    fitness_df  = fitness_summary_dataframe(alignments)

    tmp_tasks = {
        "task1": lambda d: (task1.generate(fitness_df,            d), None),
        "task2": lambda d: (task2.generate(alignments, model_path, d), None),
        "task3": lambda d: (task3.generate(alignments,            d), None),
        "task4": lambda d: (task4.generate(log, alignments,       d), None),
        "task5": lambda d: (task5.generate(fitness_df,            d), None),
        "task6": lambda d: (task6.generate(log, alignments,       d), None),
    }
    task_key_map = {
        "task1": "T-01", "task2": "T-02", "task3": "T-03",
        "task4": "T-04", "task5": "T-05", "task6": "T-06",
    }

    for tmp_name, gen_fn in tmp_tasks.items():
        tmp_dir = os.path.join(output_dir, tmp_name)
        os.makedirs(tmp_dir, exist_ok=True)
        try:
            gen_fn(tmp_dir)
        except Exception as e:
            print(f"Warning: {tmp_name} generation failed: {e}")

        target_dir = os.path.join(output_dir, task_key_map[tmp_name])
        os.makedirs(target_dir, exist_ok=True)

        for f in pathlib.Path(tmp_dir).glob("*.svg"):
            stem = f.stem                          # e.g. "task3_bar_chart"
            # strip "taskN_" prefix
            parts = stem.split("_", 1)
            idiom_key = parts[1] if len(parts) == 2 else stem
            idiom_key = _FILE_RENAME.get(idiom_key, idiom_key)
            shutil.move(str(f), os.path.join(target_dir, f"{idiom_key}.svg"))

        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
