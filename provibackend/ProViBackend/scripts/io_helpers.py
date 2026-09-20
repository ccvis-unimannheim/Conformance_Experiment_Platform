"""
io_helpers.py – Data loading and alignment computation for the CC Visualization Pipeline.
"""

import os

import pm4py
import pandas as pd


class EventLogFormatError(ValueError):
    """An event log this pipeline cannot read: wrong extension, or a CSV whose
    case / activity / timestamp columns cannot be identified. The message is
    meant for the admin who uploaded the file."""


# Accepted CSV header names per role, tried in order.
CSV_COLUMN_CANDIDATES: dict[str, list[str]] = {
    "case_id_key":   ["case:concept:name", "case_id", "CaseID", "Case ID", "caseid"],
    "activity_key":  ["concept:name", "activity", "Activity", "ActivityName", "task"],
    "timestamp_key": ["time:timestamp", "timestamp", "Timestamp", "StartTimestamp", "start_time"],
}
_ROLE_NAMES = {"case_id_key": "case id", "activity_key": "activity",
               "timestamp_key": "timestamp"}


def detect_csv_columns(columns) -> dict:
    """Map each role to the CSV column that plays it.

    Raises EventLogFormatError naming every role that has no matching column,
    the names that would have been accepted, and the columns the file has.
    """
    columns = list(columns)
    col_map, problems = {}, []
    for role, candidates in CSV_COLUMN_CANDIDATES.items():
        found = next((c for c in candidates if c in columns), None)
        if found is None:
            problems.append(f"no {_ROLE_NAMES[role]} column (accepted names: "
                            f"{', '.join(candidates)})")
        else:
            col_map[role] = found
    if problems:
        raise EventLogFormatError(
            "The event log CSV cannot be read: " + "; ".join(problems)
            + f". Columns in the file: {', '.join(map(str, columns)) or '(none)'}.")
    return col_map


def load_event_log(log_path: str):
    """Load XES or CSV event log and always return a PM4Py EventLog object.

    Raises EventLogFormatError (a ValueError) for an unsupported extension or
    a CSV whose columns cannot be identified — never exits the process, since
    the backend calls this inside requests and background jobs.
    """
    print(f"[1/3] Loading event log: {log_path}")
    ext = os.path.splitext(log_path)[1].lower()
    if ext == ".xes":
        raw = pm4py.read_xes(log_path)
    elif ext == ".csv":
        df_csv = pd.read_csv(log_path)
        col_map = detect_csv_columns(df_csv.columns)
        raw = pm4py.format_dataframe(
            df_csv,
            case_id=col_map["case_id_key"],
            activity_key=col_map["activity_key"],
            timestamp_key=col_map["timestamp_key"],
        )
    else:
        raise EventLogFormatError(f"Unsupported event log format '{ext}'. Use .xes or .csv.")

    # PM4Py ≥ 2.7 returns a DataFrame from read_xes; convert to EventLog so
    # task20/task31 can iterate over traces and events directly.
    if isinstance(raw, pd.DataFrame):
        log = pm4py.convert_to_event_log(raw)
    else:
        log = raw

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
    """Build per-trace fitness DataFrame from raw alignment results — the
    `fitness_df` the central run hands to every task that needs fitness."""
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
