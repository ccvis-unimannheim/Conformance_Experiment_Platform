#!/usr/bin/env python3
"""
create_all_visualizations.py – CC Visualization Pipeline entry point.

Designed for the dataset-folder convention used on the server:

    data/{dataset_id}/
        input/
            EventLog.xes               (or EventLog.csv)
            Guideline.bpmn
        output/
            {experiment_id}/           (per-experiment runs; without an id the
                task06/  bar_chart.svg, table.svg, ...     task folders sit
                task28/  ...                               directly in output/)
                ...

Each task writes "taskNN_<idiom>.svg"; _postprocess_task_dir then renames the
files to their canonical "<idiom_key>.svg".

Two entry points:

1) Backend: generate_for_task_instances(dataset_dir, experiment_id, instances)
   renders only an experiment's tasks, each with its admin-chosen parameters.
   This is what POST /admin/experiments/{id}/generate and the previews run.

2) CLI (local testing / manual server runs) — run_pipeline() renders every
   task with one shared set of defaults:

       python create_all_visualizations.py \
           --dataset-dir data/abc123 \
           [--outcome-activity "Activate Care"]

   The script auto-detects EventLog.xes / EventLog.csv inside <dataset-dir>/input/
   alongside Guideline.bpmn.

Both go through make_task_generators, which is the single place that maps
parameters onto each task's generate() call.
"""

import logging

logger = logging.getLogger(__name__)

import argparse
import os
import re
import sys
import pickle
import hashlib
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
import trace_alignment
import trace_features
import violation_profile
import tasks.task12 as task12
import tasks.task13 as task13
import tasks.task14 as task14
import tasks.task15 as task15
import tasks.task16 as task16
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
#         <any filename>.xes  (or .csv)  ← event log   (uploads are saved as EventLog.*)
#         <any filename>.bpmn            ← process model (uploads: Guideline.bpmn)
#     output/[{experiment_id}/]taskNN/   ← one folder per task in TASK_DIRS
# ---------------------------------------------------------------------------

INPUT_SUBDIR  = "input"
OUTPUT_SUBDIR = "output"
LOG_EXTENSIONS   = {".xes", ".csv"}
MODEL_EXTENSIONS = {".bpmn"}
TASK_DIRS     = ["task01", "task02", "task03", "task04", "task05", "task06", "task07", "task08", "task09", "task10", "task11", "task12", "task13", "task14", "task15", "task16", "task17", "task18", "task19", "task20", "task21", "task22", "task23", "task24", "task25", "task26", "task27", "task28", "task29", "task30", "task31", "task32", "task33", "task34", "task35", "task36", "task37"]
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
# The Idiom collection holds two different scatter idioms: "scatterplot"
# (Scatterplot / Dotted Chart, trace level) and "scatter_plot" (plain Scatter
# Plot, log level). _FILE_RENAME maps the file stem scatter_plot to the former;
# these tasks draw the latter, so their files keep the name scatter_plot.
_TASK_RENAME_SKIP: dict[str, set[str]] = {
    "task13": {"scatter_plot"},
    "task14": {"scatter_plot"},
    "task15": {"scatter_plot"},
    "task16": {"scatter_plot"},
    "task18": {"scatter_plot"},
    "task19": {"scatter_plot"},
    "task21": {"scatter_plot"},
    "task22": {"scatter_plot"},
    "task33": {"scatter_plot"},
    "task37": {"scatter_plot"},
}


def _auto_detect_compare_attribute(log, preferred: str | None = None) -> str | None:
    """Pick the best case attribute for sub-log splitting, or None.

    Priority:
      1. preferred — if it exists in the log, use it.
      2. Numeric case attribute with highest std (median split).
      3. Categorical case attribute with 2–10 distinct values.

    Returns None when nothing suitable is found. It used to fall back to
    `preferred` — a BPIC12 column name — so a different dataset was split on a
    column it does not have, silently producing an empty panel that looked like
    a finding. A missing attribute is now the caller's problem to report.
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
    if preferred and preferred in attr_values:
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

    logger.warning("No case attribute suitable for sub-log splitting was found "
                   "in this log; tasks that need one will render their empty state.")
    return None


def _resolve_dataset_paths(dataset_dir: str, experiment_id: str | None = None):
    """Locate log and model files inside <dataset_dir>/input/ by extension; create output dir.

    When `experiment_id` is given, SVGs are written to a per-experiment
    subdirectory (`output/{experiment_id}/...`, see
    see docs/ADMIN_EXPERIMENT_SETUP.md) so multiple experiments sharing the
    same dataset can hold independently-generated idioms. Without it (CLI /
    legacy use), the original `output/...` layout is used.
    """
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

    if experiment_id:
        output_dir = os.path.join(dataset_dir, OUTPUT_SUBDIR, experiment_id)
    else:
        output_dir = os.path.join(dataset_dir, OUTPUT_SUBDIR)
    os.makedirs(output_dir, exist_ok=True)

    return log_path, model_path, output_dir


# ---------------------------------------------------------------------------
# Alignment cache
#
# PM4Py optimal alignments are NON-DETERMINISTIC: a trace with several optimal
# alignments may be diagnosed differently across runs, so the same deviation can
# be classified as a Move-on-Model in one run and a Move-on-Log (or not at all)
# in another. The /specify violation picker and the generation step
# run alignments at different times, so without a shared result they would report
# inconsistent violation frequencies (e.g. 6.6% on /specify vs 3% in the ground
# truth). We therefore compute alignments ONCE per dataset and cache them on disk
# (keyed by the log+model file signature), so every consumer sees identical data.
# ---------------------------------------------------------------------------

def _alignments_cache_path(dataset_dir: str) -> str:
    return os.path.join(dataset_dir, "cache", "alignments.pkl")


def _input_signature(log_path: str, model_path: str) -> str:
    """Stable signature of the dataset's log + model files (size + mtime).

    Re-uploading a log/model changes the signature and invalidates the cache.
    """
    h = hashlib.md5()
    for p in (log_path, model_path):
        try:
            st = os.stat(p)
            h.update(f"{os.path.basename(p)}:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:
            h.update(p.encode())
    return h.hexdigest()


def get_or_compute_alignments(dataset_dir: str, log=None, net=None, im=None, fm=None):
    """Return this dataset's alignments, loading the on-disk cache when valid.

    Computing alignments is both expensive and non-deterministic, so the result
    is cached per dataset and reused by the /specify violation enumeration, the
    visualization render — guaranteeing they
    all agree. Pass already-loaded `log`/`net`/`im`/`fm` to avoid reloading when
    the caller has them (cache miss only).
    """
    log_path, model_path, _ = _resolve_dataset_paths(dataset_dir, None)
    sig = _input_signature(log_path, model_path)
    cache_path = _alignments_cache_path(dataset_dir)

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                blob = pickle.load(f)
            if isinstance(blob, dict) and blob.get("sig") == sig:
                return blob["alignments"]
        except Exception:
            logger.exception("Failed to read alignments cache at %s; recomputing", cache_path)

    if log is None:
        log = load_event_log(log_path)
    if net is None or im is None or fm is None:
        net, im, fm = load_model(model_path)
    alignments = run_alignments(log, net, im, fm)

    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump({"sig": sig, "alignments": alignments}, f)
    except Exception:
        logger.exception("Failed to write alignments cache at %s", cache_path)

    return alignments


# ---------------------------------------------------------------------------
# Per-task generator dispatch
#
# One callable per task_key, each reading its hyperparameters from a `params`
# dict (falling back to the pipeline defaults). Centralising the per-task
# generate() signatures here lets both the full CLI pipeline and the
# per-experiment backend job (generate_for_task_instances) thread each
# task_instance's parameters into generation (see docs/ADMIN_EXPERIMENT_SETUP.md).
# ---------------------------------------------------------------------------

def make_task_generators(log, alignments, fitness_df, model_path, compare_attribute,
                         params: dict | None = None) -> dict:
    """Return {task_key: fn(output_dir)} with each task's params applied."""
    p = params or {}

    def outcome_activity():
        v = p.get("outcome_activity", "")
        if v:
            return v
        from shared import infer_outcome_activity as _infer
        return _infer(log)
    def predominant_threshold():
        raw = p.get("predominant_threshold")
        return None if (raw is None or raw == "") else float(raw)
    def cmp_attr():                return p.get("compare_attribute", compare_attribute)
    def time_granularity():        return p.get("time_granularity", "month")
    def conformance_bins():        return p.get("conformance_bins", None)
    def violated_activity():       return p.get("violated_activity", None)
    def trace_ids():
        """The trace-alignment class's explicit selection, or None for its rule."""
        return trace_alignment.selected_trace_ids(p) or None
    def violation_pattern():      return p.get("violation_pattern") or ""
    def attribute_keys():
        """The attribute picker's three classes resolved to feature keys."""
        return trace_features.selected_keys(p, log) or None
    def perspective_kwargs(default_rule, default_count):
        """The trace-alignment + perspective block task09 and task28 share."""
        return dict(
            perspective=trace_alignment.perspective(p),
            violation_pattern=violation_pattern(),
            trace_ids=trace_ids(),
            trace_pick_rule=trace_alignment.pick_rule(p, default_rule),
            trace_count=trace_alignment.trace_count(p, default_count),
            data_attribute=(p.get("data_attribute") or ""),
            conformant_values=(p.get("conformant_values") or ()),
            conformant_resources=(p.get("conformant_resources") or ()),
            scoped_activity=(p.get("scoped_activity") or ""),
        )
    def conformant_threshold():
        raw = p.get("conformant_threshold")
        return 1.0 if (raw is None or raw == "") else float(raw)
    def target_patterns_task19():       return p.get("target_patterns", None)

    return {
        "task01": lambda d: task01.generate(log, fitness_df, d, outcome_activity=outcome_activity()),
        "task02": lambda d: task02.generate(fitness_df, d, predominant_threshold=predominant_threshold()),
        "task03": lambda d: task03.generate(log, fitness_df, d,
                                            conformant_threshold=conformant_threshold(),
                                            response_attribute=(p.get("response_attribute") or [])),
        "task04": lambda d: task04.generate(
            log, fitness_df, d,
            trace_ids=trace_ids(), alignments=alignments, model_path=model_path,
            analysis_level=(p.get("analysis_level") or "trace"),
            trace_pick_rule=trace_alignment.pick_rule(p, "violation_gap"),
            trace_count=trace_alignment.trace_count(p, task04.SAMPLE_N),
            violation_pattern=violation_pattern(),
            outcome_activity=(p.get("outcome_activity") or "")),
        "task05": lambda d: task05.generate(
            log, alignments, d,
            split_attribute=(p.get("split_attribute") or cmp_attr() or ""),
            grouping_strategy=(p.get("grouping_strategy") or "pattern"),
            selection=(p.get(violation_profile.STRATEGY_SELECTION_KEY.get(
                p.get("grouping_strategy") or "pattern", "")) or None)),
        "task06": lambda d: task06.generate(fitness_df, d, log=log, alignments=alignments, model_path=model_path),
        "task07": lambda d: task07.generate(log, fitness_df, d, time_granularity=time_granularity()),
        "task08": lambda d: task08.generate(
            log, alignments, d,
            violation_patterns=(p.get("violation_patterns") or None)),
        "task09": lambda d: task09.generate(log, alignments, d, model_path=model_path,
                                            **perspective_kwargs("violation_gap", 2)),
        "task10": lambda d: task10.generate(fitness_df, d, log=log, conformance_bins=conformance_bins()),
        "task11": lambda d: task11.generate(log, alignments, d, model_path=model_path,
                                            activities=(p.get("activities") or None)),
        "task12": lambda d: task12.generate(log, alignments, d,
                                            violation_patterns=(p.get("violation_patterns") or None)),
        "task13": lambda d: task13.generate(log, alignments, model_path, d,
                                            candidate_attributes=attribute_keys()),
        "task14": lambda d: task14.generate(
            alignments, model_path, d, log=log, trace_ids=trace_ids(),
            trace_pick_rule=trace_alignment.pick_rule(p, "worst_fitness"),
            violation_pattern=violation_pattern()),
        "task15": lambda d: task15.generate(log, fitness_df, alignments, d, model_path=model_path,
                                            attribute_set=attribute_keys(),
                                            split_strategy=(p.get("split_strategy") or None),
                                            group_cap=(int(p["group_cap"]) if p.get("group_cap") else None)),
        "task16": lambda d: task16.generate(log, fitness_df, alignments, d, model_path=model_path,
                                            attribute_set=attribute_keys(),
                                            split_strategy=(p.get("split_strategy") or None),
                                            group_cap=(int(p["group_cap"]) if p.get("group_cap") else None)),
        "task17": lambda d: task17.generate(log, alignments, d, model_path=model_path),
        "task18": lambda d: task18.generate(log, alignments, model_path, d,
                                            candidate_attributes=attribute_keys()),
        "task19": lambda d: task19.generate(log, alignments, model_path, d, outcome_activity=outcome_activity(),
                                            target_patterns=target_patterns_task19()),
        "task20": lambda d: task20.generate(log, alignments, d, model_path=model_path,
                                            attribute_set=attribute_keys()),
        "task21": lambda d: task21.generate(log, alignments, model_path, d,
                                            candidate_attributes=attribute_keys()),
        "task22": lambda d: task22.generate(log, fitness_df, alignments, d, model_path=model_path,
                                            attribute_set=attribute_keys(),
                                            split_strategy=(p.get("split_strategy") or None),
                                            group_cap=(int(p["group_cap"]) if p.get("group_cap") else None)),
        "task23": lambda d: task23.generate(alignments, d, log=log,
                                            activities=(p.get("activities") or None)),
        "task24": lambda d: task24.generate(
            log, model_path, d, trace_ids=trace_ids(),
            trace_count=trace_alignment.trace_count(p, task24.DEFAULT_VARIANTS)),
        "task25": lambda d: task25.generate(log, alignments, d),
        "task26": lambda d: task26.generate(alignments, d, model_path=model_path),
        "task27": lambda d: task27.generate(
            log, fitness_df, alignments, d, model_path=model_path,
            conformant_threshold=conformant_threshold(),
            trace_ids=trace_ids(),
            trace_count=trace_alignment.trace_count(p, 1),
            nonconformant_pick_rule=(p.get("nonconformant_pick_rule") or "most_frequent")),
        "task28": lambda d: task28.generate(alignments, model_path, d, log=log,
                                            **perspective_kwargs("first_nonconformant", 1)),
        "task29": lambda d: task29.generate(
            alignments, d,
            grouping_strategy=(p.get("grouping_strategy") or "move_type"),
            selection=(p.get(violation_profile.STRATEGY_SELECTION_KEY.get(
                p.get("grouping_strategy") or "move_type", "")) or None)),
        "task30": lambda d: task30.generate(log, fitness_df, alignments, d,
                                            attribute_set=attribute_keys(),
                                            split_strategy=(p.get("split_strategy") or None),
                                            group_cap=(int(p["group_cap"]) if p.get("group_cap") else None),
                                            pattern_top_n=(int(p["pattern_top_n"]) if p.get("pattern_top_n") else None)),
        # Not outcome_activity(): that falls back to the "contains" heuristic,
        # and this task asks which activity a trace *ends* on. Passing None
        # lets it reach for the terminal-activity heuristic instead.
        "task31": lambda d: task31.generate(log, alignments, d,
                                            outcome_activity=(p.get("outcome_activity") or None)),
        "task32": lambda d: task32.generate(
            log, alignments, d, compare_attribute=cmp_attr(),
            split_attribute=(p.get("split_attribute") or ""),
            grouping_strategy=(p.get("grouping_strategy") or "pattern"),
            selection=(p.get(violation_profile.STRATEGY_SELECTION_KEY.get(
                p.get("grouping_strategy") or "pattern", "")) or None),
            prominence_threshold=p.get("prominence_threshold")),
        "task33": lambda d: task33.generate(log, fitness_df, d, alignments=alignments,
                                            attribute_set=attribute_keys(),
                                            split_strategy=(p.get("split_strategy") or None),
                                            group_cap=(int(p["group_cap"]) if p.get("group_cap") else None)),
        "task34": lambda d: task34.generate(
            log, alignments, d, model_path=model_path,
            violated_activity=violated_activity(),
            trace_ids=trace_ids(),
            trace_pick_rule=trace_alignment.pick_rule(p, "worst_fitness"),
            trace_count=trace_alignment.trace_count(p, 1),
            violation_pattern=violation_pattern()),
        "task35": lambda d: task35.generate(log, alignments, d, model_path=model_path,
                                            move_types=(p.get("move_types") or None)),
        "task36": lambda d: task36.generate(log, alignments, d,
            grouping_strategy=(p.get("grouping_strategy") or "pattern"),
            selection=(p.get(violation_profile.STRATEGY_SELECTION_KEY.get(
                p.get("grouping_strategy") or "pattern", "")) or None),
            prominence_threshold=p.get("prominence_threshold")),
        "task37": lambda d: task37.generate(log, alignments, d, model_path=model_path,
                                            conformance_bins=conformance_bins()),
    }


def _postprocess_task_dir(task_name: str, task_dir: str):
    """Rename each task script's "taskNN_<idiom>.svg" to canonical "<idiom_key>.svg".

    Only a real "taskNN_" prefix is stripped — already-canonical files (from a
    previous run on the same output dir) pass through unchanged, otherwise
    "bar_chart.svg" would degrade to "chart.svg" on re-runs.
    """
    import pathlib
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
            # replace() overwrites existing targets on all platforms (os.rename
            # fails on Windows when re-running on a non-empty output directory).
            f.replace(target)


def get_log_activities(dataset_dir: str) -> list[str]:
    """Sorted distinct activity names in the dataset's event log.

    Powers the /specify "list all options" combobox for activity-picker params
    (see docs/ADMIN_EXPERIMENT_SETUP.md). For CSV logs this reads only the
    activity column (fast); XES logs fall back to the full pm4py loader.
    """
    input_dir = os.path.join(dataset_dir, INPUT_SUBDIR)
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    log_path = None
    for fname in os.listdir(input_dir):
        if os.path.splitext(fname)[1].lower() in LOG_EXTENSIONS:
            log_path = os.path.join(input_dir, fname)
            break
    if log_path is None:
        raise FileNotFoundError(f"No event log found in {input_dir}")

    ext = os.path.splitext(log_path)[1].lower()
    if ext == ".csv":
        import pandas as pd
        df = pd.read_csv(log_path)
        for col in ["concept:name", "activity", "Activity", "ActivityName", "task"]:
            if col in df.columns:
                return sorted({str(v) for v in df[col].dropna().unique()})
        return []

    log = load_event_log(log_path)
    activities = {str(ev.get("concept:name", "")) for trace in log for ev in trace}
    activities.discard("")
    return sorted(activities)


def get_log_time_granularities(dataset_dir: str) -> list[str]:
    """Time-bin granularities that yield >=2 bins for this dataset's timestamp span.

    Powers task07's /specify granularity dropdown: only granularities that
    actually produce a multi-point trend on THIS dataset are offered (a
    too-coarse choice would collapse to one bin and fail validation). Candidates
    and ordering (finest -> coarsest) are derived from shared.TIME_GRANULARITY_FREQ,
    so adding a granularity there flows through here automatically (extensibility).
    Bins are counted on trace START timestamps to match task07.validate_params /
    shared.bin_fitness_time_series. Falls back to the full ordered list if the
    timestamps cannot be read.
    """
    from shared import TIME_GRANULARITY_FREQ

    # Finest -> coarsest; any granularity not in this hint keeps registry order.
    _ORDER = ["day", "month", "year"]
    ordered = ([g for g in _ORDER if g in TIME_GRANULARITY_FREQ]
               + [g for g in TIME_GRANULARITY_FREQ if g not in _ORDER])

    try:
        starts = _trace_start_timestamps(dataset_dir)
        if starts is None or len(starts) == 0:
            return ordered
        usable = [g for g in ordered
                  if starts.dt.to_period(TIME_GRANULARITY_FREQ[g]).nunique() >= 2]
        return usable or ordered
    except Exception:
        logger.exception("Failed to enumerate time granularities for %s", dataset_dir)
        return ordered


def _trace_start_timestamps(dataset_dir: str):
    """Per-trace START timestamps as a tz-aware pandas Series, or None.

    Shared by get_log_time_granularities and get_log_time_bins so both bin the
    same values task07.validate_params / shared.bin_fitness_time_series do.
    """
    import pandas as pd

    input_dir = os.path.join(dataset_dir, INPUT_SUBDIR)
    log_path = None
    if os.path.isdir(input_dir):
        for fname in os.listdir(input_dir):
            if os.path.splitext(fname)[1].lower() in LOG_EXTENSIONS:
                log_path = os.path.join(input_dir, fname)
                break
    if log_path is None:
        return None

    if os.path.splitext(log_path)[1].lower() == ".csv":
        df = pd.read_csv(log_path)
        ts_col = next((c for c in ["time:timestamp", "timestamp", "Timestamp",
                                   "time", "Time", "Complete Timestamp"]
                       if c in df.columns), None)
        if ts_col is None:
            return None
        case_col = next((c for c in ["case:concept:name", "case", "Case ID",
                                     "case_id", "caseid", "CaseID"]
                         if c in df.columns), None)
        df["_ts"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
        df = df.dropna(subset=["_ts"])
        return df.groupby(case_col)["_ts"].min() if case_col else df["_ts"]

    log = load_event_log(log_path)
    raw = [trace[0].get("time:timestamp")
           for trace in log if len(trace) and trace[0].get("time:timestamp") is not None]
    return pd.to_datetime(pd.Series(raw), errors="coerce", utc=True).dropna()


# Bin label formats, mirroring task07's _BIN_LABEL_FMT.
_TIME_BIN_LABEL_FMT = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}


def get_log_time_bins(dataset_dir: str, granularity: str = None) -> list[dict]:
    """Ordered time bins this dataset's traces fall into, as option rows.

    Returns [{"value": "2023-01", "label": "2023-01"}, ...] — the label set an
    admin imports for a number-set ("read one value per period off the chart").
    Bins come from trace START timestamps at `granularity`, matching what the
    over-time idioms render.
    """
    from shared import TIME_GRANULARITY_FREQ, DEFAULT_TIME_GRANULARITY

    gran = str(granularity or DEFAULT_TIME_GRANULARITY).lower()
    if gran not in TIME_GRANULARITY_FREQ:
        gran = DEFAULT_TIME_GRANULARITY

    try:
        starts = _trace_start_timestamps(dataset_dir)
        if starts is None or len(starts) == 0:
            return []
        periods = starts.dt.to_period(TIME_GRANULARITY_FREQ[gran])
        fmt = _TIME_BIN_LABEL_FMT.get(gran, _TIME_BIN_LABEL_FMT["month"])
        labels = sorted({p.to_timestamp().strftime(fmt) for p in periods.unique()})
        return [{"value": lbl, "label": lbl} for lbl in labels]
    except Exception:
        logger.exception("Failed to enumerate time bins for %s", dataset_dir)
        return []


def get_log_violations(dataset_dir: str) -> list[dict]:
    """Distinct (activity, move_type) pairs that appear in this dataset's alignments.

    Returns a list of {"value": "activity|move_type", "label": "activity · Type  (N traces, X%)"}
    dicts, sorted by trace coverage descending.  Powers task11's /specify 'log.violations'
    source (see docs/ADMIN_EXPERIMENT_SETUP.md).

    Alignment computation is expensive; the result is cached in admin.py per dataset_id.
    """
    from collections import Counter
    from shared import classify_step as _classify_step

    alignments = get_or_compute_alignments(dataset_dir)

    trace_coverage: Counter = Counter()
    n_traces = len(alignments)
    for aln in alignments:
        seen: set = set()
        for step in aln.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            act, vtype = _classify_step(step[0], step[1])
            if act is None:
                continue
            seen.add((act, vtype))
        for pair in seen:
            trace_coverage[pair] += 1

    options = []
    for (act, vt), count in trace_coverage.most_common():
        pct = count / n_traces * 100 if n_traces > 0 else 0
        options.append({
            "value": f"{act}|{vt}",
            "label": f"{act} · {vt}  ({count:,} traces, {pct:.1f}%)",
        })
    return options


def get_log_worst_traces(dataset_dir: str) -> list[dict]:
    """Top-10 worst-fitness traces for this dataset, as dropdown options.

    Returns [{"value": "0", "label": "Rank 1 — fitness 0.234  (8 violations)"}, ...]
    sorted by violation count descending then fitness ascending (same ordering as
    task34._build_contexts).  The value is the zero-based rank index that
    task34.generate() accepts as `trace_rank`.
    Powers task34's /specify 'log.worst_traces' source.
    """
    from tasks.task34 import _parse_alignment, _is_violation

    alignments = get_or_compute_alignments(dataset_dir)

    scored = []
    for trace_idx, result in enumerate(alignments):
        rows    = _parse_alignment(result)
        n_viol  = sum(1 for r in rows if _is_violation(r))
        fitness = float(result.get("fitness", 1.0))
        scored.append((n_viol, fitness, trace_idx))

    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:10]

    options = []
    for rank, (n_viol, fitness, trace_idx) in enumerate(top):
        options.append({
            "value": str(rank),
            "label": (
                f"Rank {rank + 1} — trace #{trace_idx + 1} | "
                f"fitness {fitness:.4f}  ({n_viol} violations)"
            ),
        })
    return options


def get_log_trace_ids(dataset_dir: str) -> list[dict]:
    """Every trace in this dataset as a picker option for `trace_ids`.

    Returns [{"value": "<case_id>", "label": "<case_id> — fitness 0.812"}, ...]
    in log order; `value` is the trace's case id (concept:name), which the
    trace-alignment tasks accept in `trace_ids`. Powers the 'log.trace_ids'
    param-spec source.

    Each option used to carry the index of its control-flow variant, for a
    checkbox that auto-picked one trace per distinct variant. The checkbox is
    gone, and with it the only reader of that field.
    """
    log_path, _model_path, _ = _resolve_dataset_paths(dataset_dir, None)
    log = load_event_log(log_path)
    alignments = get_or_compute_alignments(dataset_dir, log)

    options = []
    for i, trace in enumerate(log):
        if i >= len(alignments):
            break
        case_id = str(trace.attributes.get("concept:name", i))
        fitness = float(alignments[i].get("fitness", 1.0))
        options.append({
            "value": case_id,
            "label": f"{case_id} — fitness {fitness:.3f}",
        })
    return options


#: An attribute with more distinct values than this is an identifier, not a
#: dimension: naming one of its values in a rule addresses a single case. The
#: same rule task13.discover_candidate_attributes applies to its own candidates
#: — kept in sync by the comment rather than the import, since that module pulls
#: in the whole task package.
def _is_identifier_like(n_distinct: int, n_traces: int) -> bool:
    return n_distinct > max(5, n_traces * 0.5)


#: Longest candidate list handed to a picker. The select-many widget renders one
#: checkbox per candidate behind a search box, so a long list is slow to skim
#: rather than unusable — but a list no one can reach the end of is not a choice.
MAX_PICKER_CANDIDATES = 200


def _is_numeric_column(values) -> bool:
    """Every observed value parses as a number (mirrors task13's column typing)."""
    if not values:
        return False
    for v in values:
        try:
            float(str(v))
        except (TypeError, ValueError):
            return False
    return True


def _dataset_attribute_index(dataset_dir: str):
    """(attribute -> sorted distinct values, resource values) for this dataset.

    Walks the log once for both the data and the resource perspective of task09
    / task28. Case-level and event-level attributes are collected the same way —
    which one an attribute is depends on the log, not on the admin — and the
    structural keys (the activity name, the timestamp, the case id) are left out
    because no rule is written about them.

    Identifier-like attributes are dropped: BPIC12's REG_DATE holds one distinct
    value per trace, and flattening it into "attribute = value" candidates put
    148 503 checkboxes on the page.
    """
    log_path, _model_path, _ = _resolve_dataset_paths(dataset_dir, None)
    log = load_event_log(log_path)

    skip = {"concept:name", "time:timestamp", "lifecycle:transition",
            "case:concept:name", "concept:instance", "variant", "variant-index"}
    values: dict[str, set] = {}
    resources: set = set()

    def _record(key, value):
        if value is None:
            return
        key = str(key)
        if key.startswith("case:"):
            key = key[len("case:"):]
        if key in skip or key.startswith(":"):
            return
        if key == "org:resource":
            resources.add(str(value))
            return
        values.setdefault(key, set()).add(str(value))

    for trace in log:
        for key, value in (getattr(trace, "attributes", {}) or {}).items():
            _record(key, value)
        for event in trace:
            for key, value in dict(event).items():
                _record(key, value)

    n_traces = len(log)
    kept = {}
    for key, vals in values.items():
        if _is_identifier_like(len(vals), n_traces):
            logger.info(f"      '{key}' looks like an identifier ({len(vals)} distinct "
                        f"values over {n_traces} traces) — not offered as a candidate.")
            continue
        if _is_numeric_column(vals):
            # A data rule over a numeric attribute is a range ("amount <= 10000"),
            # not a list of the 631 amounts a log happens to contain. The
            # conformant-values parameter can only express membership, so a
            # numeric attribute has nothing to offer it — see
            # docs/TRACE_ALIGNMENT_PARAMETERS.md for the gap this leaves.
            logger.info(f"      '{key}' is numeric — a conformant *set* cannot "
                        f"express a rule about it; not offered as a candidate.")
            continue
        kept[key] = sorted(vals)
    return (kept, sorted(resources))


def get_log_log_attributes(dataset_dir: str) -> list[dict]:
    """Log-level attributes, as `log::<key>` features.

    A log attribute has one value for the whole log, so selecting one does not
    split anything — it labels the log as a single group. Most logs carry only
    export metadata here (pm4py leaves `origin`), and then the picker is empty
    and says so, which is the honest answer: this log has nothing to analyse at
    log level. Powers the 'log.log_attributes' param-spec source.
    """
    import trace_features

    log_path, _model_path, _ = _resolve_dataset_paths(dataset_dir, None)
    log = load_event_log(log_path)
    attrs = getattr(log, "attributes", {}) or {}
    return [
        {"value": f"{trace_features.LOG_PREFIX}{key}",
         "label": f"{key} = {value}"}
        for key, value in sorted(attrs.items())
        if not str(key).startswith("@@")
    ]


def get_log_event_conditions(dataset_dir: str) -> list[dict]:
    """"At activity X, attribute Y had value Z" conditions, by trace coverage.

    The event perspective of the attribute picker (task13/15/16/20/21/22). Each
    condition is a *trace-level* question — did this trace ever execute X with
    Y = Z — so it splits the traces in two and the existing panels draw it like
    any other boolean feature.

    Conditions every trace satisfies, or none does, are left out: they put every
    trace in one group, which compares nothing. On BPIC12 that alone removes the
    four most frequent ones (A_SUBMITTED is always executed by resource 112).
    Powers the 'log.event_conditions' param-spec source.
    """
    from collections import Counter
    import trace_features

    log_path, _model_path, _ = _resolve_dataset_paths(dataset_dir, None)
    log = load_event_log(log_path)

    skip = {"concept:name", "time:timestamp", "case:concept:name",
            "concept:instance", "variant", "variant-index"}
    coverage: Counter = Counter()
    for trace in log:
        seen = set()
        for event in trace:
            activity = str(event.get("concept:name", ""))
            if not activity:
                continue
            for key, value in dict(event).items():
                key = str(key)
                if key in skip or key.startswith("@@") or key.startswith(":") \
                        or key.lower().startswith("unnamed") or value is None:
                    continue
                seen.add((activity, key, str(value)))
        coverage.update(seen)

    n_traces = len(log)
    rows = []
    for (activity, key, value), n in coverage.items():
        if n >= n_traces or n == 0:
            continue
        rows.append({
            "value": f"{trace_features.AT_PREFIX}{activity}|{key}|{value}",
            "label": f"{activity} · {key} = {value}  ({n} traces, {n / n_traces * 100:.1f}%)",
            "coverage": n,
        })
    rows.sort(key=lambda r: (-r["coverage"], r["value"]))
    if len(rows) > MAX_PICKER_CANDIDATES:
        logger.info(f"      {len(rows)} event conditions found; offering the "
                    f"{MAX_PICKER_CANDIDATES} most frequent.")
        rows = rows[:MAX_PICKER_CANDIDATES]
    return [{"value": r["value"], "label": r["label"]} for r in rows]


def get_log_data_attributes(dataset_dir: str) -> list[dict]:
    """Attributes a data rule can be written about, with their cardinality.

    Powers the 'log.data_attributes' param-spec source (task09 / task28).
    """
    values, _resources = _dataset_attribute_index(dataset_dir)
    return [{"value": key, "label": f"{key} ({len(vals)} distinct values)"}
            for key, vals in sorted(values.items())]


def get_log_attribute_values(dataset_dir: str) -> list[dict]:
    """Every "attribute = value" pair in the log, as picker options.

    Flat on purpose: /specify bakes a param's options in once per dataset, so a
    value list that narrowed itself to a separately-chosen attribute would have
    nothing to narrow by at the time it is built. Powers
    'log.attribute_values'.
    """
    values, _resources = _dataset_attribute_index(dataset_dir)
    options = []
    for key, vals in sorted(values.items()):
        for value in vals:
            options.append({"value": f"{key} = {value}", "label": f"{key} = {value}"})
    return options


def get_log_resource_values(dataset_dir: str) -> list[dict]:
    """Distinct org:resource values. Powers 'log.resource_values'.

    Empty for a log that records no executor — which /specify reports as "this
    source returned nothing for this dataset", the honest answer: the resource
    perspective cannot be asked about of such a log.
    """
    _values, resources = _dataset_attribute_index(dataset_dir)
    return [{"value": r, "label": r} for r in resources]


def get_log_candidate_attributes(dataset_dir: str) -> list[dict]:
    """Trace-level features the admin can split this log by.

    Returns [{"value", "label", "perspective", "value_type", "cardinality",
    "coverage"}, ...] from the trace-feature registry; _param_candidates and the
    option editor read value/label and ignore the rest. Powers the
    'log.candidate_attributes' param-spec source.

    Supersedes key-scanning (task13.discover_candidate_attributes), which listed
    raw log keys plus one hard-coded derived feature. Three consequences:

      * Control-flow and resource features become selectable at all. Activity
        presence was computed inside task20 all along, but `concept:name` is a
        structural key, so key-scanning could never offer it.
      * Cardinality no longer gates the list — a 61-value `org:resource` is
        offered with its cardinality reported, for the split strategy to handle,
        instead of being dropped.
      * No alignments are computed. The old implementation ran them only to
        reach the throughput column, which the registry derives from the log.

    Feature keys are stable: a case-level data attribute keeps its own name and
    throughput keeps `__throughput_hours__`, so `attribute_set` values saved by
    existing experiments keep resolving.
    Two filters apply here rather than in the registry, whose rule is that
    cardinality never gates availability: a feature with one distinct value puts
    every trace in one group, and one with a distinct value per trace is an
    identifier (BPIC12's REG_DATE) whose buckets are singletons plus a huge
    "Other". Neither can answer "how does this attribute relate to violations",
    which is what every caller asks. The canonical reading of each attribute is
    listed first (`Feature.primary`), so the admin meets "amount" before
    "amount (mean) / (max) / (sum)".
    """
    import trace_features

    log_path, _model_path, _ = _resolve_dataset_paths(dataset_dir, None)
    log = load_event_log(log_path)
    return [f.as_option() for f in trace_features.offerable(log)]


def get_log_default_attributes(dataset_dir: str) -> list[str]:
    """The keys an empty `attribute_set` falls back to: the canonical ones.

    The same list the picker shows first, so "leave it empty" and "take the
    obvious ones" agree.
    """
    return [row["value"] for row in get_log_candidate_attributes(dataset_dir)
            if row.get("primary")]


def get_log_violation_activities(dataset_dir: str) -> list[dict]:
    """Activities carrying at least one violation, most traces first.

    Powers the Violation-profile class's "activities" selection. Distinct from
    `log.activities`, which lists every activity in the log: offering one with
    no violations would put an empty group on the chart.
    """
    import violation_profile

    alignments = get_or_compute_alignments(dataset_dir)
    return [
        {"value": activity, "label": f"{activity}  ({traces} traces, {pct:.1f}%)"}
        for activity, traces, pct in violation_profile.activity_coverage(alignments)
    ]


def get_log_violated_activities_task34(dataset_dir: str) -> list[dict]:
    """Distinct violated activities for task34's admin dropdown.

    Returns [{"value": "Approve Treatment", "label": "TREATMENT_APPROVED (6 traces)"}, ...]
    sorted by trace count descending.  MoM / MoL violations are counted,
    matching task34's classification rules.
    Powers the 'log.violated_activities_task34' param-spec source.
    """
    from tasks.task34 import _parse_alignment, _is_violation

    alignments = get_or_compute_alignments(dataset_dir)

    from collections import Counter
    act_trace_counts: Counter = Counter()
    for result in alignments:
        rows = _parse_alignment(result)
        seen = {r["activity"] for r in rows if _is_violation(r) and r["activity"] != ">>"}
        for act in seen:
            act_trace_counts[act] += 1

    n_traces = len(alignments)
    options = []
    for act, count in act_trace_counts.most_common():
        pct = count / n_traces * 100 if n_traces > 0 else 0
        options.append({
            "value": act,
            "label": f"{act}  ({count:,} traces, {pct:.1f}%)",
        })
    return options


def generate_for_task_instances(dataset_dir: str, experiment_id: str,
                                instances: list[dict]) -> dict:
    """Render one dataset's task_instances.

    `instances` items: {"task_key": str, "parameters": dict}.
    Shared artefacts (log, Petri net, alignments, fitness_df) are computed once
    and reused across this dataset's tasks.

    Returns {task_key: {"render_error": str|None}}. This function only draws —
    the answer shape is authored by the admin on /answer-format.
    """
    log_path, model_path, output_dir = _resolve_dataset_paths(dataset_dir, experiment_id)
    log         = load_event_log(log_path)
    compare_attribute = _auto_detect_compare_attribute(log)
    net, im, fm = load_model(model_path)
    # Reuse the cached alignments shared with /specify's violation enumeration so
    # idiom frequencies match what the admin saw when selecting violations
    # (PM4Py alignments are non-deterministic — see get_or_compute_alignments).
    alignments  = get_or_compute_alignments(dataset_dir, log, net, im, fm)
    fitness_df  = fitness_summary_dataframe(alignments)

    results: dict = {}
    for inst in instances:
        tk = inst["task_key"]
        params = inst.get("parameters") or {}
        entry = {"render_error": None}

        generators = make_task_generators(log, alignments, fitness_df, model_path,
                                          compare_attribute, params)
        gen_fn = generators.get(tk)
        if gen_fn is None:
            entry["render_error"] = f"No generator registered for '{tk}'."
            results[tk] = entry
            continue

        task_dir = os.path.join(output_dir, tk)
        os.makedirs(task_dir, exist_ok=True)
        try:
            gen_fn(task_dir)
            _postprocess_task_dir(tk, task_dir)
        except Exception as e:
            logger.exception("Render failed for %s", tk)
            entry["render_error"] = str(e)

        results[tk] = entry

    return results


# ---------------------------------------------------------------------------
# Public entry point – called by both the CLI and the FastAPI backend
# ---------------------------------------------------------------------------

def run_pipeline(dataset_dir: str, experiment_id: str | None = None,
                 outcome_activity: str = "Activate Care",
                 compare_attribute: str = "AMOUNT_REQ",
                 predominant_threshold: float = 0.8,
                 time_granularity: str = "month",
                 conformance_bins: list | None = None) -> str:
    """Render every task for one dataset directory with one shared set of
    defaults — the CLI path. The backend renders per experiment through
    generate_for_task_instances instead, with each task's own parameters.

    Parameters (which tasks read each one: see make_task_generators)
    ----------
    dataset_dir : str
        Path to the dataset folder (must contain an event log (.xes/.csv) and a
        .bpmn model under input/).
    experiment_id : str, optional
        When given, SVGs are written to ``<dataset_dir>/output/{experiment_id}/``
        instead of ``<dataset_dir>/output/`` (see docs/ADMIN_EXPERIMENT_SETUP.md).
    outcome_activity : str
        Activity name that marks a positive process outcome (task01, task19,
        task31, and task04 at its log level).
    compare_attribute : str
        Case-level data attribute that splits the log into sub-logs (numeric →
        median split, categorical → value groups) for task30, task32 and, when
        no split attribute is given, task05. Replaced by an auto-detected
        attribute if the log does not carry it.
    predominant_threshold : float
        Fitness level (0–1) task02 draws as the "predominantly follows the
        model" reference.
    time_granularity : str
        "year" | "month" | "day" — task07's time-axis aggregation.
    conformance_bins : list, optional
        Conformance interval boundaries for task10; None uses the canonical
        bins in shared.py.
    Returns
    -------
    str
        Absolute path to the directory that received the SVGs.
    """
    import pathlib

    log_path, model_path, output_dir = _resolve_dataset_paths(dataset_dir, experiment_id)

    logger.error(f"Dataset directory : {os.path.abspath(dataset_dir)}")
    logger.info(f"Event log         : {log_path}")
    logger.info(f"Process model     : {model_path}")
    logger.info(f"Output directory  : {output_dir}")
    logger.info(f"Outcome activity  : {outcome_activity}")
    logger.info(f"Compare attribute : {compare_attribute}")
    logger.info(f"Predominant thresh: {predominant_threshold}")
    logger.info(f"Time granularity  : {time_granularity}")
    logger.info(f"Conformance bins  : {conformance_bins if conformance_bins else 'default (shared.py)'}")
    log         = load_event_log(log_path)
    compare_attribute = _auto_detect_compare_attribute(log, compare_attribute)
    logger.info(f"Compare attribute (resolved): {compare_attribute}")
    net, im, fm = load_model(model_path)
    # Reuse the per-dataset alignment cache so the CLI pipeline, the /specify
    # violation enumeration and the backend generation all see identical
    # (deterministic) alignments — PM4Py alignments are otherwise non-deterministic.
    alignments  = get_or_compute_alignments(dataset_dir, log, net, im, fm)
    fitness_df  = fitness_summary_dataframe(alignments)

    def out(task_name: str) -> str:
        d = os.path.join(output_dir, task_name)
        os.makedirs(d, exist_ok=True)
        return d

    # Full-pipeline defaults are threaded through `params` so make_task_generators
    # is the single source of per-task generate() signatures.
    generators = make_task_generators(
        log, alignments, fitness_df, model_path, compare_attribute,
        params={
            "outcome_activity": outcome_activity,
            "predominant_threshold": predominant_threshold,
            "compare_attribute": compare_attribute,
            "time_granularity": time_granularity,
            "conformance_bins": conformance_bins,
        },
    )

    for task_name in TASK_DIRS:
        gen_fn = generators.get(task_name)
        if gen_fn is None:
            continue
        task_dir = out(task_name)
        try:
            gen_fn(task_dir)
        except Exception as e:
            logger.warning(f"{task_name} generation failed: {e}")
        _postprocess_task_dir(task_name, task_dir)

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
        help="Path to the dataset folder whose input/ holds the event log "
             "(.xes/.csv) and the .bpmn model",
    )
    parser.add_argument(
        "--experiment-id", default=None,
        help="If given, write SVGs to <dataset-dir>/output/{experiment-id}/ instead of "
             "<dataset-dir>/output/ (per-experiment generation, see "
             "docs/ADMIN_EXPERIMENT_SETUP.md).",
    )
    parser.add_argument(
        "--outcome-activity", default="Activate Care",
        help="Activity name that marks a positive outcome. Default: 'Activate Care'",
    )
    parser.add_argument(
        "--compare-attribute", default="AMOUNT_REQ",
        help="Case attribute that splits the log into sub-logs for tasks 30 and 32 "
             "(and task 5 when it has no split attribute); numeric: median split, "
             "categorical: value groups. Default: AMOUNT_REQ",
    )
    parser.add_argument(
        "--predominant-threshold", type=float, default=0.8,
        help="Fitness level (0–1) Task 2 draws as the 'predominantly follows the "
             "model' reference line. Default: 0.8",
    )
    parser.add_argument(
        "--time-granularity", choices=["year", "month", "day"], default="month",
        help="Time-axis aggregation for Task 7's line/horizon charts. Default: month",
    )
    parser.add_argument(
        "--conformance-bins", default=None,
        help="Comma-separated conformance interval boundaries for Task 10 "
             "(e.g. '0.0,0.5,0.9,1.01'). Default: shared.py canonical bins.",
    )
    return parser.parse_args()


def _parse_conformance_bins(raw):
    """Parse a comma-separated bin-edge string into an ascending list of floats."""
    if not raw:
        return None
    try:
        bins = [float(x.strip()) for x in str(raw).split(",") if x.strip() != ""]
    except ValueError as e:
        raise ValueError(f"Invalid --conformance-bins '{raw}': expected comma-separated "
                         f"numbers like '0.0,0.5,0.9,1.01' ({e})")
    if len(bins) < 2:
        raise ValueError(f"--conformance-bins needs at least 2 edges, got: {bins}")
    if any(a >= b for a, b in zip(bins, bins[1:])):
        raise ValueError(f"--conformance-bins must be strictly ascending, got: {bins}")
    return bins


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
        conformance_bins = _parse_conformance_bins(args.conformance_bins)
        run_pipeline(args.dataset_dir, experiment_id=args.experiment_id,
                     outcome_activity=args.outcome_activity,
                     compare_attribute=args.compare_attribute,
                     predominant_threshold=args.predominant_threshold,
                     time_granularity=args.time_granularity,
                     conformance_bins=conformance_bins)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
