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


if __name__ == "__main__":
    main()
