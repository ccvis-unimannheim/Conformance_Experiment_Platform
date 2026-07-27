"""
tasks/task04.py – Task ID 4: Describe / Compare / Conformance across individual traces.

Task 4 asks "How does the degree of conformance differ between multiple logs or
traces?". Every idiom shows the *same* concrete traces (individual traces, NOT
aggregated variants) with their conformance fitness, just encoded differently, so
no idiom exposes more information than another (information equivalence):

    * bar_chart        – one uniform-coloured bar per trace, fitness on the y-axis
    * table            – Trace | Fitness, one row per trace
    * line_graph       – fitness profile across the sampled traces
    * table_bar_chart  – Trace | Fitness table + adjacent per-trace fitness bars
    * matrix           – trace × Fitness grid, colour + numeric annotation
    * heatmap          – trace × Fitness grid, continuous colour (no annotation)

Fitness is rounded to 3 decimals in every idiom; there is no #Traces column, no
conformant/non-conformant colour coding, and no pre-computed differences — the
participant derives the conformance assessment from the fitness values.

Public API:
    generate(log, fitness_df, output_dir, trace_ids=None)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
        trace_ids  – optional list of case-id strings to show (default: first 10)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_basic", "flow_chart_elaborate",
          "bar_chart", "table",
          "line_graph", "table_bar_chart",
          "matrix", "heatmap"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 4)
#
# Task 4 (MANUAL): compare the trace-level conformance PATTERNS of two traces. By
# default the two traces with the largest violation-count gap are shown; the admin
# can override the selection (and pick more than two). The participant answers in
# free text, comparing where each trace conforms to or deviates from the guideline;
# grading is against the static RUBRIC.
# ---------------------------------------------------------------------------
GT_TIER = "MANUAL"

PARAM_SPEC = [
    {
        "key": "trace_ids",
        "label": "Specific traces to compare (optional; default = the two traces with the largest violation gap)",
        # Internal to reading the chart — the participant sees the traces directly.
        "hide_hint": True,
        "widget": "select-many",
        "source": "log.trace_ids",
        # Admin convenience: a checkbox that auto-selects one trace from each of
        # the first N distinct variants. Handled in the specify-page select-many UI.
        "variant_autoselect": True,
        "autoselect_count": 2,
        "default": [],
        "required": False,
        "optional_hint": "(optional — leave empty to compare the two traces with the largest violation gap)",
    },
]

ANSWER_FORMATS = [
    {"key": "free-text", "gt_shape": "reference", "decisive_default": True},
]

RUBRIC = (
    "A complete answer compares the two traces' conformance patterns. For each "
    "trace it identifies where the execution conforms to the guideline and where "
    "it deviates — an activity skipped relative to the model (move on model) or an "
    "extra activity inserted (move on log) — and contrasts the two, e.g. 'Trace 1 "
    "is fully conformant, whereas Trace 2 skips Approve Treatment and inserts an "
    "extra step'. Award full marks for correctly naming the key deviation(s) in "
    "each trace and stating which trace is more conformant; partial marks for "
    "identifying the more-conformant trace without the specific deviations; deduct "
    "marks for misidentifying which trace conforms more."
)


def validate_params(log, params) -> list:
    """trace_ids is optional; the generic /specify validation already checks that
    each selected id exists in the dataset, so nothing task-specific is required."""
    return []


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, auto_col_widths, draw_value_heatmap,
    alignment_pairs_to_rows, chevron_nodes_from_alignment_rows,
    draw_chevron_strip, chevron_figure_width,
    parse_bpmn_model, compose_bpmn_panels, render_empty_state_svg,
    contrasting_text_color,
    GREY_MED, GREY_LIGHTER, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Default number of traces to sample when the admin doesn't pick specific ones.
SAMPLE_N = 2

# Single uniform bar/line colour — no conformant / non-conformant distinction.
_TRACE_COLOR = GREY_MED

# Consistent figure title across every idiom.
TITLE = "Trace Conformance Fitness"

# Activity-name font in the chevron flow chart. The chevron width has a fixed
# margin on top of its per-character allowance, so realistic activity names stay
# inside the arrow at 13pt; the shared auto-shrink still catches any outlier.
# Bump here to retune.
_CHEVRON_FONT = 15


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task04_build_trace_df(log, fitness_df: pd.DataFrame, trace_ids=None,
                           sample_n: int = SAMPLE_N) -> pd.DataFrame:
    """One row per concrete trace: a running ``label`` ("Trace 1".."Trace N"),
    the raw ``case_id``, and ``fitness`` (rounded 3 dp).

    ``trace_ids``: optional list of case-id strings. When given, exactly those
    traces are shown in that order (ids not present in the log are skipped).
    Otherwise the first ``sample_n`` traces in log order are used.

    Participants see the running ``label`` rather than the raw case id (which is
    noise to hunt for in the chart); the admin maps "Trace N → id" in the picker.
    The ``case_id`` column is kept for reference / debugging.
    """
    records = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        case_id = str(trace.attributes.get("concept:name", i))
        records.append({
            "trace_index": i,
            "case_id":     case_id,
            "fitness":     round(float(fitness_df.iloc[i]["fitness"]), 3),
        })

    cols = ["trace_index", "case_id", "fitness"]
    if not records:
        return pd.DataFrame(columns=cols + ["label"])

    if trace_ids:
        by_id = {}
        for r in records:
            by_id.setdefault(r["case_id"], r)  # first trace wins if case ids repeat
        chosen = [by_id[str(tid)] for tid in trace_ids if str(tid) in by_id]
        df = pd.DataFrame(chosen, columns=cols)
    else:
        df = pd.DataFrame(records[:sample_n], columns=cols)

    df = df.reset_index(drop=True)
    df["label"] = [f"Trace {i + 1}" for i in range(len(df))]
    return df


# Move-type palette (mirrors shared.chevron_nodes_from_alignment_rows) used for
# the chevron / flow-chart legend.
_MOVE_LEGEND = [
    ("Synchronous Move", GREY_LIGHTER),
    ("Model Move",       GREY_MED),
    ("Log Move",         GREY_DARK),
]


def _task04_case_index(log):
    """case_id (str) -> first trace index in the log."""
    idx = {}
    for i, trace in enumerate(log):
        cid = str(trace.attributes.get("concept:name", i))
        idx.setdefault(cid, i)
    return idx


def _task04_trace_violations(alignments, i):
    """(alignment rows, #violations) for trace index i. Violations = non-sync moves."""
    rows = alignment_pairs_to_rows(alignments[i].get("alignment", [])) if i < len(alignments) else []
    viol = sum(1 for r in rows if r["moveType"] != "Synchronous Move")
    return rows, viol


def _task04_select_compare_traces(log, alignments, fitness_df, trace_ids=None, n=2):
    """Pick the traces to compare, as a list of dicts
    {label, case_id, fitness, rows, violations}.

    Admin-selected ``trace_ids`` are used in order when given. Otherwise two
    "complete" traces (those covering the most distinct activities, so the chevron
    strips are substantial rather than trivially short) are chosen such that their
    fitness differs as much as possible — one clearly more conformant than the
    other — making the comparison meaningful.
    """
    n_traces = min(len(log), len(alignments), len(fitness_df))
    if n_traces == 0:
        return []

    def _info(i, label):
        rows, viol = _task04_trace_violations(alignments, i)
        return {"label": label, "case_id": str(log[i].attributes.get("concept:name", i)),
                "fitness": round(float(fitness_df.iloc[i]["fitness"]), 3),
                "rows": rows, "violations": viol}

    if trace_ids:
        by_id = _task04_case_index(log)
        chosen = [by_id[str(t)] for t in trace_ids if str(t) in by_id][:max(n, len(trace_ids))]
    else:
        # Activity coverage (distinct activities) and fitness per trace.
        coverage = [len({str(e.get("concept:name", "")) for e in log[i]}) for i in range(n_traces)]
        fitness  = [float(fitness_df.iloc[i]["fitness"]) for i in range(n_traces)]
        by_coverage = sorted(range(n_traces), key=lambda i: coverage[i], reverse=True)

        # Grow the pool from the most-complete traces until it spans a fitness gap,
        # then take the highest- and lowest-fitness trace in that pool. This keeps
        # both chosen traces long/complete while maximising the conformance contrast.
        chosen = by_coverage[:2]
        for k in range(2, n_traces + 1):
            pool = by_coverage[:k]
            hi = max(pool, key=lambda i: fitness[i])
            lo = min(pool, key=lambda i: fitness[i])
            if hi != lo and fitness[hi] - fitness[lo] > 1e-9:
                chosen = sorted({lo, hi}, key=lambda i: fitness[i], reverse=True)
                break

    return [_info(idx, f"Trace {k + 1}") for k, idx in enumerate(chosen)]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def _task04_involved_activities(rows):
    """Model activities the trace touches — synchronously executed or skipped
    (move on model). Log moves are inserted activities, not model tasks."""
    s = set()
    for r in rows:
        if r["moveType"] == "Synchronous Move":
            s.add(str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"]))
        elif r["moveType"] == "Model Move":
            s.add(str(r["model_move"]))
    return s


def _task04_violation_activities(rows):
    """Model activities the trace violates by skipping them (move on model)."""
    return {str(r["model_move"]) for r in rows if r["moveType"] == "Model Move"}


def _task04_move_map(rows):
    """activity name -> heatmap/chevron colour for one trace, by alignment move
    type: synchronous move (yellow), model move (grey), log move (dark blue)."""
    m = {}
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous Move":
            a = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
            m[a] = GREY_LIGHTER
        elif mt == "Model Move":
            m[str(r["model_move"])] = GREY_MED
        elif mt == "Log Move":
            m[str(r["log_move"])] = GREY_DARK
    return m


def _task04_model_task_names(model_path):
    """Ordered task names of the guideline model (for the not-in-trace chevrons)."""
    if not model_path:
        return []
    try:
        els = parse_bpmn_model(model_path).get("elements", {})
    except Exception:
        return []
    vals = els.values() if isinstance(els, dict) else els
    return [e.get("name", "") for e in vals if e.get("kind") == "task" and e.get("name")]


def task04_flow_chart_basic(selected, output_dir: str, model_path=None):
    """Chevron flow chart: one horizontal chevron strip per selected trace, stacked
    so the two traces sit side by side (top vs bottom). Each activity chevron is
    coloured by its alignment move type — Synchronous Move, Model Move or Log Move;
    only the activities that trace actually touches are shown."""
    path = os.path.join(output_dir, "task04_flow_chart_basic.svg")
    if not selected:
        fig, ax = plt.subplots(figsize=(7, 3)); ax.axis("off")
        ax.text(0.5, 0.5, "No trace data available.", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
        save_svg(fig, path)
        return

    nodes_per_trace = [chevron_nodes_from_alignment_rows(t["rows"]) for t in selected]

    fig_w = max((chevron_figure_width(n) for n in nodes_per_trace if n), default=9.0)
    n_rows = len(selected)
    fig_h = 1.9 * n_rows + 1.6

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(n_rows, 1, hspace=0.9)
    for r, (trace, nodes) in enumerate(zip(selected, nodes_per_trace)):
        ax = fig.add_subplot(gs[r])
        if nodes:
            draw_chevron_strip(ax, nodes, fontsize=_CHEVRON_FONT)
        else:
            ax.axis("off")
            ax.text(0.5, 0.5, "(empty trace)", ha="center", va="center",
                    transform=ax.transAxes, fontsize=FONT_ANNOT)
        ax.set_title(trace["label"], fontsize=FONT_LABEL, loc="left", pad=6)

    handles = [mpatches.Patch(facecolor=c, edgecolor="#4a4a4a", label=lbl)
               for lbl, c in _MOVE_LEGEND]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
               ncol=len(_MOVE_LEGEND), frameon=False, fontsize=FONT_ANNOT - 1)
    fig.tight_layout(rect=[0, 0.08, 1, 1.0])
    save_svg(fig, path)


def _task04_bpmn_node_style(rows, log_move_in_model=frozenset()):
    """node_style_fn colouring model tasks by this trace's alignment: synchronous
    move -> yellow (conformant), model move -> grey (skipped), a log move that maps
    onto an otherwise-white model task -> navy dashed (deviation executed in place);
    everything else white. Uses the same colours as the chevron for information
    equivalence."""
    conform, skipped = _task04_bpmn_move_sets(rows)

    def _style(eid, elem):
        if elem.get("kind") == "task":
            name = elem.get("name", "")
            if name in skipped:
                return (GREY_MED, "#444444", 3, contrasting_text_color(GREY_MED))
            if name in conform:
                return (GREY_LIGHTER, "#666666", 2, contrasting_text_color(GREY_LIGHTER))
            if name in log_move_in_model:
                # executed, but as a log move (deviation): navy fill like the Log
                # Move legend, with a dashed border to mark it as out-of-place.
                return (GREY_DARK, "#8ba0cf", 2, contrasting_text_color(GREY_DARK), "6 4")
        return ("white", "#888888", 2, "#333333")
    return _style


_MISSING = ("-", "None", "(skip)", "")


def _task04_bpmn_move_sets(rows):
    """conform (Synchronous) and skipped (Model Move) activity-name sets for one
    trace — the two sets that decide a model node's colour."""
    conform, skipped = set(), set()
    for r in rows:
        if r["moveType"] == "Synchronous Move":
            lbl = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
            conform.add(lbl)
        elif r["moveType"] == "Model Move":
            skipped.add(str(r["model_move"]))
    return conform, skipped


def _task04_log_move_badges(rows):
    """Log moves (inserted activities) as external badges, each anchored to the
    model activity at the sequence position where the insertion occurred — the
    most recent synchronous / model move before it (or the next one if it comes
    first). Returns [{"label", "anchor"}]."""
    badges, last = [], None
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous Move":
            last = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
        elif mt == "Model Move":
            last = str(r["model_move"])
        elif mt == "Log Move":
            badges.append({"label": str(r["log_move"]), "anchor": last})

    if any(b["anchor"] is None for b in badges):
        first = None
        for r in rows:
            if r["moveType"] == "Synchronous Move":
                first = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
                break
            if r["moveType"] == "Model Move":
                first = str(r["model_move"]); break
        for b in badges:
            b["anchor"] = b["anchor"] or first
    return [b for b in badges if b["anchor"]]


def _task04_resolve_log_moves(rows, model_task_names):
    """Split a trace's log moves into (in_model, badges).

    A log move whose activity matches a model task this trace otherwise leaves
    white (neither Synchronous nor Model Move) is painted ON that model node
    (in_model set), avoiding a duplicate label. The rest keep their external
    badge. Returns (in_model:set[str], badges:list[dict])."""
    conform, skipped = _task04_bpmn_move_sets(rows)
    coloured = conform | skipped
    model_set = set(model_task_names)
    in_model, kept = set(), []
    for b in _task04_log_move_badges(rows):
        name = b["label"]
        if name in model_set and name not in coloured and name not in in_model:
            in_model.add(name)      # reuse the white model node as the log move
        else:
            kept.append(b)          # external badge fallback
    return in_model, kept


def task04_flow_chart_elaborate(selected, model_path, output_dir):
    """BPMN idiom, information-equivalent to the chevron: the guideline model is
    drawn once per trace (stacked), each model task coloured by that trace's
    alignment — Synchronous Move (yellow) or Model Move / skipped (grey). Log Move
    (inserted) activities aren't model tasks, so they are listed in the table
    beneath, whose dark-blue header matches the Log Move legend colour. Together
    the panels + table encode the same three move types the chevron shows."""
    path = os.path.join(output_dir, "task04_flow_chart_elaborate.svg")
    title = "Trace-Level Conformance on the Process Model"
    if not selected or not model_path:
        render_empty_state_svg(path, title, "No traces or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path, node_scale=1.35)
    except Exception as e:
        logger.warning(f"      task04: BPMN parse failed: {e}")
        render_empty_state_svg(path, title, "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, title, "No BPMN geometry to render.")
        return

    model_names = {e.get("name", "") for e in parsed["elements"].values()
                   if e.get("kind") == "task"}
    panels = []
    for t in selected:
        in_model, badges = _task04_resolve_log_moves(t["rows"], model_names)
        panels.append({
            "parsed": parsed,
            "node_style_fn": _task04_bpmn_node_style(t["rows"], in_model),
            "subtitle": t["label"],
            "badges": badges,
        })

    compose_bpmn_panels(
        panels, path,
        title=title,
        legend_items=[
            (GREY_LIGHTER, "#666666", 2, "Synchronous Move"),
            (GREY_MED,     "#444444", 3, "Model Move"),
            (GREY_DARK,    "#8ba0cf", 3, "Log Move", "6 4"),
        ],
        node_font_size=18,
    )


def task04_bar_chart(tdf: pd.DataFrame, output_dir: str):
    """One uniform-coloured bar per trace; fitness value labelled above each bar."""
    fig, ax = plt.subplots(figsize=(max(7, len(tdf) * 0.75), 5))
    x = np.arange(len(tdf))
    bars = ax.bar(x, tdf["fitness"], color=_TRACE_COLOR, edgecolor="white", width=0.65)
    for bar, val in zip(bars, tdf["fitness"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.012,
                f"{val:.3f}", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)

    ax.set_xticks(x)
    ax.set_xticklabels(tdf["label"], rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Trace", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0-1)", fontsize=FONT_LABEL)
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    ax.set_ylim(0, 1.12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_bar_chart.svg"))


def task04_table(selected, model_path, output_dir):
    """Activity × trace move-type table: one row per activity (model tasks plus
    any inserted ones), one column per compared trace, cell = the alignment move
    type in that trace (Synchronous Move / Model Move / Log Move). Only activities
    at least one trace touches are listed; a "—" marks the rare case an activity
    appears in one trace but not the other. The tabular twin of the chevron / BPMN
    / heatmap, read as plain text (only the header row is coloured)."""
    path = os.path.join(output_dir, "task04_table.svg")
    title = "Move Type by Activity Across Traces"
    activities = _task04_model_task_names(model_path)
    if not activities or not selected:
        fig, ax = plt.subplots(figsize=(6.5, 3.0))
        ax.axis("off")
        make_table(ax, cell_text=[["—", "—"]], col_labels=["Activity", "Move type"],
                   bbox=[0.05, 0.05, 0.9, 0.92])
        ax.set_title(title, fontsize=FONT_TITLE, pad=3)
        fig.tight_layout(pad=1.2)
        save_svg(fig, path)
        return

    move_maps = [_task04_move_map(t["rows"]) for t in selected]
    # inserted (log-move) activities become extra rows, mirroring the heatmap
    inserted = []
    for mm in move_maps:
        for a, c in mm.items():
            if c == GREY_DARK and a not in activities and a not in inserted:
                inserted.append(a)
    # keep only activities at least one trace actually touches (drop never-touched)
    present = set().union(*(set(mm) for mm in move_maps)) if move_maps else set()
    rows = [a for a in (list(activities) + inserted) if a in present]
    labels = [t["label"] for t in selected]
    label_by_color = {c: lbl for lbl, c in _MOVE_LEGEND}

    cell_text = []
    for a in rows:
        text_row = [a]
        for mm in move_maps:
            c = mm.get(a)
            text_row.append("—" if c is None else label_by_color.get(c, ""))
        cell_text.append(text_row)

    col_labels = ["Activity"] + labels
    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig_w = max(6.5, 3.2 + 2.1 * len(labels))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    make_table(
        ax, cell_text=cell_text, col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.9],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=9.5, scale_xy=(1, 1.7), cell_pad=0.1,
    )
    ax.set_title(title, fontsize=FONT_TITLE, pad=3)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task04_line_graph(tdf: pd.DataFrame, output_dir: str):
    """Fitness profile across the sampled traces (x = trace, y = fitness)."""
    fig, ax = plt.subplots(figsize=(max(7, len(tdf) * 0.7), 5))
    x = np.arange(len(tdf))
    ax.plot(x, tdf["fitness"], color=_TRACE_COLOR, linewidth=1.8, marker="o", markersize=5)
    ax.fill_between(x, tdf["fitness"], alpha=0.15, color=_TRACE_COLOR)
    for xi, val in zip(x, tdf["fitness"]):
        ax.text(xi, val + 0.02, f"{val:.3f}", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)

    ax.set_xticks(x)
    ax.set_xticklabels(tdf["label"], rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Trace", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0-1)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 1.12)
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_line_graph.svg"))


def task04_table_bar_chart(tdf: pd.DataFrame, output_dir: str):
    """Trace | Fitness table (left) + adjacent uniform-coloured fitness bars (right)."""
    cell_text = [[row["label"], f"{row['fitness']:.3f}"] for _, row in tdf.iterrows()] \
        or [["—", "—"]]
    col_labels = ["Trace", "Fitness"]

    fig = plt.figure(figsize=(13, max(4.5, 1.2 + len(tdf) * 0.45)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.2, 1.0], wspace=0.28)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    make_table(
        ax_tbl, cell_text=cell_text, col_labels=col_labels,
        bbox=[0.02, 0.05, 0.96, 0.88],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=9.5, scale_xy=(1, 1.7), cell_pad=0.09,
    )
    ax_tbl.set_title(TITLE, fontsize=FONT_TITLE, pad=4)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(tdf))
    bars = ax_bar.barh(y, tdf["fitness"], color=_TRACE_COLOR, edgecolor="white")
    for bar, val in zip(bars, tdf["fitness"]):
        ax_bar.text(min(val + 0.02, 1.02), bar.get_y() + bar.get_height() / 2,
                    f"{val:.3f}", va="center", ha="left", fontsize=FONT_ANNOT - 1)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(tdf["label"], fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, 1.18)
    ax_bar.set_xlabel("Fitness (0-1)", fontsize=FONT_LABEL)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_table_bar_chart.svg"))


def task04_matrix(tdf: pd.DataFrame, output_dir: str):
    """Trace × Fitness grid: colour scales 0→light to 1→dark, with numeric labels."""
    labels = tdf["label"].tolist()
    data = tdf["fitness"].values.astype(float).reshape(-1, 1)

    fig_h = max(3.0, 0.5 * len(labels) + 1.4)
    fig, ax = plt.subplots(figsize=(3.6, fig_h))
    draw_value_heatmap(
        fig, ax, data, labels, ["Fitness"],
        cbar_label="Fitness", cell_fmt="{:.3f}", annotate=True,
    )
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_matrix.svg"))


def task04_heatmap(selected, model_path, output_dir):
    """Activity × trace move-type heatmap: columns = the compared traces, rows =
    the activities (model tasks plus any inserted ones), cell colour = the
    alignment move type — synchronous move (yellow), model move (grey), log move
    (dark blue), or white when the trace never touches that activity. Colour only,
    using the same cividis-derived palette as the chevron / BPMN views; no fitness,
    no numbers."""
    path = os.path.join(output_dir, "task04_heatmap.svg")
    title = "Move Type by Activity Across Traces"
    activities = _task04_model_task_names(model_path)
    if not activities or not selected:
        render_empty_state_svg(path, title, "No model / traces available.")
        return

    move_maps = [_task04_move_map(t["rows"]) for t in selected]
    # inserted (log-move) activities become extra rows so the log-move colour appears
    inserted = []
    for mm in move_maps:
        for a, c in mm.items():
            if c == GREY_DARK and a not in activities and a not in inserted:
                inserted.append(a)
    rows = list(activities) + inserted
    cols = [t["label"] for t in selected]
    n_rows, n_cols = len(rows), len(cols)

    fig_h = max(3.0, 0.46 * n_rows + 1.9)
    fig_w = max(4.5, 1.9 * n_cols + 3.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    for ri, a in enumerate(rows):
        for ci, mm in enumerate(move_maps):
            ax.add_patch(mpatches.Rectangle(
                (ci, ri), 1, 1, facecolor=mm.get(a, "#ffffff"),
                edgecolor="#cfcfcf", linewidth=1.2))
    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.invert_yaxis()
    ax.set_xticks([c + 0.5 for c in range(n_cols)])
    ax.set_xticklabels(cols, fontsize=FONT_ANNOT)
    ax.set_yticks([r + 0.5 for r in range(n_rows)])
    ax.set_yticklabels(rows, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Trace", fontsize=FONT_LABEL)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=FONT_TITLE)

    any_not_involved = any(
        rows[ri] not in mm for ri in range(n_rows) for mm in move_maps)
    legend = list(_MOVE_LEGEND) + ([("Not in this trace", "#ffffff")] if any_not_involved else [])
    handles = [mpatches.Patch(facecolor=c, edgecolor="#4a4a4a", label=lbl)
               for lbl, c in legend]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
               ncol=len(legend), frameon=False, fontsize=FONT_ANNOT - 1)
    fig.tight_layout(rect=[0, 0.07, 1, 1.0])
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, trace_ids=None, alignments=None, model_path=None):
    """Generate all Task ID 4 SVGs into output_dir.

    ``trace_ids`` is the admin-configured list of case-id strings (from
    PARAM_SPEC "trace_ids"). When empty/None the first ``SAMPLE_N`` traces in log
    order are shown. Every idiom renders the same traces so the views are
    directly comparable (and match what the ground truth was computed for).

    ``alignments`` (optional) enables the trace-level flow-chart idioms, which
    compare the alignment (conformance) patterns of two traces side by side.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 4 visualizations ---")

    # Single trace selection shared by EVERY idiom: the admin-selected traces, or
    # (default) the two traces with the largest violation-count gap. This needs
    # alignments; without them we fall back to the first SAMPLE_N in log order.
    selected = _task04_select_compare_traces(log, alignments, fitness_df, trace_ids=trace_ids) \
        if alignments else []
    if selected:
        tdf = pd.DataFrame([{"case_id": t["case_id"], "fitness": t["fitness"], "label": t["label"]}
                            for t in selected])
    else:
        tdf = _task04_build_trace_df(log, fitness_df, trace_ids=trace_ids)
    if tdf.empty:
        logger.warning("      Skipped Task 4: no trace data available.")
        return

    source = "admin-selected" if trace_ids else "largest violation gap"
    logger.info(f"      -> Comparing {len(tdf)} traces ({source}).")

    task04_bar_chart(tdf, output_dir)
    task04_table_bar_chart(tdf, output_dir)
    task04_matrix(tdf, output_dir)
    task04_line_graph(tdf, output_dir)

    # Trace-level pattern comparison — chevron, BPMN, violation heatmap and the
    # move-type table of the same traces (all need the alignments / model).
    if selected:
        task04_flow_chart_basic(selected, output_dir, model_path=model_path)
        task04_flow_chart_elaborate(selected, model_path, output_dir)
        task04_heatmap(selected, model_path, output_dir)
        task04_table(selected, model_path, output_dir)
