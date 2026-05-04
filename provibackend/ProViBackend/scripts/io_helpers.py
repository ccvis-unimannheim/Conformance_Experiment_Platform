"""
io_helpers.py – Data loading and alignment computation for the CC Visualization Pipeline.
"""

import os
import sys

import pm4py
import pandas as pd


def load_event_log(log_path: str):
    print(f"[1/3] Loading event log: {log_path}")
    ext = os.path.splitext(log_path)[1].lower()
    if ext == ".xes":
        log = pm4py.read_xes(log_path)
    elif ext == ".csv":
        df_csv = pd.read_csv(log_path)
        col_map = {}
        for candidate in ["case:concept:name", "case_id", "CaseID", "Case ID", "caseid"]:
            if candidate in df_csv.columns:
                col_map["case_id_key"] = candidate
                break
        for candidate in ["concept:name", "activity", "Activity", "ActivityName", "task"]:
            if candidate in df_csv.columns:
                col_map["activity_key"] = candidate
                break
        for candidate in ["time:timestamp", "timestamp", "Timestamp", "StartTimestamp", "start_time"]:
            if candidate in df_csv.columns:
                col_map["timestamp_key"] = candidate
                break
        if len(col_map) < 3:
            missing = {"case_id_key", "activity_key", "timestamp_key"} - col_map.keys()
            print(f"ERROR: Could not auto-detect columns for: {missing}", file=sys.stderr)
            print(f"       Available columns: {list(df_csv.columns)}", file=sys.stderr)
            sys.exit(1)
        log = pm4py.format_dataframe(
            df_csv,
            case_id=col_map["case_id_key"],
            activity_key=col_map["activity_key"],
            timestamp_key=col_map["timestamp_key"],
        )
        log = pm4py.convert_to_event_log(log)
    else:
        print(f"ERROR: Unsupported file format '{ext}'. Use .xes or .csv", file=sys.stderr)
        sys.exit(1)
    print(f"      -> {len(log)} traces loaded.")
    return log


def load_model(model_path: str):
    print(f"[2/3] Loading BPMN model: {model_path}")
    bpmn_graph = pm4py.read_bpmn(model_path)
    net, initial_marking, final_marking = pm4py.convert_to_petri_net(bpmn_graph)
    print(f"      -> Petri net: {len(net.places)} places, {len(net.transitions)} transitions.")
    return net, initial_marking, final_marking


def run_alignments(log, net, im, fm):
    """Run PM4Py alignment diagnostics once; raw results reused by all tasks."""
    print("[3/3] Running alignment-based conformance checking (this may take a while) ...")
    alignments = pm4py.conformance_diagnostics_alignments(log, net, im, fm)
    return alignments


def fitness_summary_dataframe(alignments):
    """Build per-trace fitness DataFrame from raw alignment results (used by Task 1 & Task 5)."""
    rows = []
    for i, result in enumerate(alignments):
        fitness = result["fitness"]
        rows.append({
            "trace_index": i,
            "fitness": fitness,
            "is_fit": fitness >= 1.0,
        })
    df = pd.DataFrame(rows)
    conform_count = int(df["is_fit"].sum())
    non_conform_count = len(df) - conform_count
    avg_fitness = df["fitness"].mean()
    print(f"      -> Conformant: {conform_count}  |  Non-conformant: {non_conform_count}  |  Avg fitness: {avg_fitness:.4f}")
    return df
