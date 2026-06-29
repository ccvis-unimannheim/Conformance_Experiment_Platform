"""
tasks/task14.py – Task 14: Violation classification and annotation for a representative trace.

Goal: Explain · Means: Annotate · Characteristics: Guideline violations
"What kind of violation occurs in a given trace? This requires a classification of
violations, and a textual description of them."

Public API:
    generate(alignments, model_path, output_dir)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "table", "bar_chart",
    "flow_chart_table",
    # "flow_chart_elaborate",  # commented out
    "flow_chart_elaborate_table",
    "table_bar_chart", "parallel_sets",
]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 14)
#
# Task 14 (SEMI/MANUAL split): the classification half (mc-multi) is auto-
# computable from the representative trace's alignment moves; the description
# half (free-text) is graded against the static RUBRIC below.
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = []

ANSWER_FORMATS = [
    {"key": "mc-multi",  "gt_shape": "mc",        "decisive_default": True},
    {"key": "free-text", "gt_shape": "reference",  "decisive_default": False},
]

RUBRIC = (
    "A strong answer names each violation type present in the shown trace and "
    "explains what it means in process terms — e.g. a Model Move indicates a "
    "required step was absent from the recorded execution; a Log Move indicates "
    "an unexpected step was executed that the model does not prescribe. "
    "Full credit requires correctly identifying all present violation types and "
    "giving a meaningful process-level description for each. "
    "Partial credit for identifying some types or for correct naming without "
    "explanation. No credit for types not present in the trace."
)


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """For mc-multi: which violation types appear in the representative trace.

    Returns options for both move types (Model Move, Log Move), each flagged
    correct=True iff that type occurs at least once in the representative
    (worst-fitness) trace. A mismatch step (both labels present) counts as both a
    Model and a Log move. Free-text falls through to the static RUBRIC.
    """
    if answer_format == "free-text":
        return {}
    ctx = _build_context(alignments)
    if ctx is None:
        return {"options": [
            {"label": mt, "value": mt, "correct": False} for mt in _MOVE_TYPES
        ]}
    counts = _type_counts(ctx)
    options = [
        {"label": mt, "value": mt, "correct": counts.get(mt, 0) > 0}
        for mt in _MOVE_TYPES
    ]
    return {"options": options}


import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from matplotlib.patches import FancyBboxPatch

from shared import (
    save_svg, make_table,
    alignment_pairs_to_rows,
    GREY_MED, GREY_LIGHTER, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    contrasting_text_color,
    draw_chevron_strip, chevron_nodes_from_alignment_rows, chevron_figure_width,
    draw_parallel_sets,
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    render_empty_state_svg,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Alignment violation vocabulary for Task 14: the two fundamental move types.
# A PM4Py "mismatch" pair (both labels present but different) is treated as BOTH
# a Model and a Log move — Task 14 has no separate "Mismatch Move" category.
_MOVE_TYPES = ["Model Move", "Log Move"]
# Conformant + violation types, in display order (Synchronous first as the
# baseline). Used so every idiom shows synchronous moves alongside violations.
_ALL_TYPES = ["Synchronous Move"] + _MOVE_TYPES

_TYPE_COLOR = {
    "Model Move":      GREY_MED,
    "Log Move":        GREY_DARK,
    "Synchronous Move": GREY_LIGHTER,
}

# SVG dash pattern marking that an activity is BOTH a Model and a Log move on the
# Flow+ (BPMN) idiom — lets such a "both" node read at a glance.
_BOTH_DASH = "6 4"

# Domain-agnostic descriptions for each violation type
_TYPE_DESC = {
    "Model Move":    "Required step absent in recorded trace",
    "Log Move":      "Unexpected step recorded; not prescribed by model",
}

_MISSING_TOKENS = {"-", "None", "(skip)", ""}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _pick_representative_trace(alignments):
    """Return index of the trace with the highest alignment cost, else 0."""
    best_idx, best_cost = 0, -1.0
    for i, result in enumerate(alignments):
        try:
            c = float(result.get("cost") or 0)
        except (TypeError, ValueError):
            c = 0.0
        if c > best_cost:
            best_cost, best_idx = c, i
    return best_idx


def _build_context(alignments):
    """Extract representative trace context. Returns None if no usable alignment."""
    if not alignments:
        return None
    idx = _pick_representative_trace(alignments)
    result = alignments[idx]
    rows = alignment_pairs_to_rows(result.get("alignment", []))
    if not rows:
        return None
    return {
        "trace_index": idx,
        "trace_label": f"Trace {idx + 1}",
        "fitness": float(result.get("fitness", 0.0)),
        "rows": rows,
        "violations": [r for r in rows if r["moveType"] != "Synchronous Move"],
    }


def _row_move_types(row):
    """Canonical move type(s) a row contributes. A PM4Py mismatch step (both
    labels present but different) counts as BOTH a Model and a Log move, since
    Task 14 has no separate 'Mismatch' category."""
    mt = row["moveType"]
    if mt == "Mismatch Move":
        return ["Model Move", "Log Move"]
    return [mt]


def _display_move_type(row):
    """Move-type label shown in tables — a mismatch step reads as 'Model & Log Move'."""
    return "Model & Log Move" if row["moveType"] == "Mismatch Move" else row["moveType"]


def _type_counts(ctx):
    """Return {move_type: count} for violation steps in this trace."""
    counts = {mt: 0 for mt in _MOVE_TYPES}
    for r in ctx["violations"]:
        for mt in _row_move_types(r):
            if mt in counts:
                counts[mt] += 1
    return counts


def _type_counts_all(ctx):
    """Return {move_type: count} over ALL steps, incl. Synchronous Move.

    Used by the idioms that show synchronous (conformant) moves next to the
    violation types for consistency across Task 14.
    """
    counts = {mt: 0 for mt in _ALL_TYPES}
    for r in ctx["rows"]:
        for mt in _row_move_types(r):
            if mt in counts:
                counts[mt] += 1
    return counts


def _all_step_rows(ctx):
    """cell_text for every trace step (synchronous + violations), in order."""
    return [
        [str(r["step"]), _activity_for_row(r), _display_move_type(r)]
        for r in ctx["rows"]
    ]


def _build_act_types_map(rows):
    """Map activity name -> set of move types it exhibits across the trace.

    Keeps every move type per activity — including Synchronous Move — so the
    Flow+ idiom can mark an activity that is *both* conformant and a violation
    (rather than a single last-deviation-wins label).
    """
    act_types = {}
    for r in rows:
        act = _activity_for_row(r)
        if act and act not in _MISSING_TOKENS:
            act_types.setdefault(act, set()).update(_row_move_types(r))
    return act_types


def _activity_for_row(row):
    """Return the activity label for a violation row (domain-agnostic anchor)."""
    mt = row["moveType"]
    if mt == "Model Move":
        return str(row["model_move"])
    if mt == "Log Move":
        return str(row["log_move"])
    # Mismatch: prefer log_move as the executed label
    lm = str(row["log_move"])
    return lm if lm not in _MISSING_TOKENS else str(row["model_move"])


# ---------------------------------------------------------------------------
# Idiom 1: table
# ---------------------------------------------------------------------------

def task14_table(ctx, output_dir):
    """Move classification table: every trace step (synchronous + violations)."""
    out = os.path.join(output_dir, "task14_table.svg")
    cell_text = _all_step_rows(ctx)
    if not cell_text:
        render_empty_state_svg(out, "Move Classification", "No trace steps.")
        return

    fig_h = max(3.2, 1.5 + len(cell_text) * 0.42)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Step", "Activity", "Move Type"],
        bbox=[0.02, 0.05, 0.96, 0.78],
        col_widths=[0.12, 0.48, 0.40],
        font_size=9.5,
        scale_xy=(1, 1.7),
    )
    ax.set_title(
        f"Move Classification — {ctx['trace_label']}  (fitness {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE, pad=10,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 2: bar_chart
# ---------------------------------------------------------------------------

def task14_bar_chart(ctx, output_dir):
    """Bar chart: count of each move type (synchronous + violations) in the trace."""
    out = os.path.join(output_dir, "task14_bar_chart.svg")
    counts = _type_counts_all(ctx)
    present = [(mt, counts[mt]) for mt in _ALL_TYPES if counts[mt] > 0]
    if not present:
        render_empty_state_svg(out, "Move Type Distribution", "No trace steps.")
        return

    labels, vals = zip(*present)
    colors = [_TYPE_COLOR[mt] for mt in labels]
    ymax = max(vals)

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    bars = ax.bar(labels, vals, color=colors, edgecolor="white", width=0.55, alpha=0.90)
    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.015,
            str(v), ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Occurrences in Trace", fontsize=FONT_LABEL)
    ax.set_title(
        f"Move Type Distribution — {ctx['trace_label']}",
        fontsize=FONT_TITLE,
    )
    ax.set_ylim(0, ymax * 1.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelrotation=0)

    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 4: flow_chart_table
# ---------------------------------------------------------------------------

def task14_flow_chart_and_table(ctx, output_dir):
    """Chevron flow strip (top) + violation classification table (bottom)."""
    out = os.path.join(output_dir, "task14_flow_chart_and_table.svg")
    rows = ctx["rows"]
    nodes = chevron_nodes_from_alignment_rows(rows)

    if not nodes:
        render_empty_state_svg(out, "Trace Flow & Move Classification", "No trace steps.")
        return

    cell_text = _all_step_rows(ctx) or [["—", "No trace steps", "—"]]

    n_rows = len(cell_text) + 1
    fig_w = max(18.0, chevron_figure_width(nodes))
    tbl_h = max(2.2, 0.36 * n_rows)
    chev_h = 2.2
    fig_h = tbl_h + chev_h + 1.2

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(2, 1, height_ratios=[chev_h, tbl_h], hspace=0.35)
    ax_chev = fig.add_subplot(gs[0])
    ax_tbl  = fig.add_subplot(gs[1])

    draw_chevron_strip(ax_chev, nodes, fontsize=10)
    ax_chev.set_title("Trace Alignment Flow", fontsize=FONT_TITLE, pad=7)

    ax_tbl.axis("off")
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Step", "Activity", "Move Type"],
        bbox=[0.0, 0.0, 1.0, 1.0],
        col_widths=[0.10, 0.50, 0.40],
        font_size=9,
        scale_xy=(1, 1.5),
    )
    ax_tbl.set_title("Move Classification", fontsize=FONT_TITLE, pad=7)

    legend_handles = [
        mpatches.Patch(facecolor=GREY_LIGHTER, label="Synchronous (Conformant)"),
        mpatches.Patch(facecolor=GREY_MED,     label="Model Move"),
        mpatches.Patch(facecolor=GREY_DARK,    label="Log Move"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center", bbox_to_anchor=(0.5, 0.01),
        ncol=2, fontsize=FONT_ANNOT, frameon=True, fancybox=False, edgecolor="#cccccc",
    )
    fig.suptitle(
        f"Move Classification — {ctx['trace_label']}  (fitness {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE, y=0.99,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Flow+ (BPMN) shared styling
#
# Fill colour encodes the (worst) move type at an activity; a DASHED node
# outline marks that the activity is BOTH a Model and a Log move somewhere in the
# trace. That makes those "both" activities readable at a glance, which the
# solid-fill-only encoding (worst-wins) could not show. Synchronous (conformant)
# activities are drawn with a plain solid outline — no dash.
# ---------------------------------------------------------------------------

_BPMN_FILL = {
    "Model Move":    "#999999",
    "Log Move":      "#555555",
}
_BPMN_CONFORM_FILL = "#E8E8E8"   # in trace, only synchronous (conformant) moves
_BPMN_ABSENT_FILL  = "#F4F4F4"   # activity not present in this trace

_BPMN_SUMMARY = ("Node colour = move type at this activity; a dashed outline "
                 "marks an activity that is both a Model and a Log move.")


def _bpmn_fill_for_types(types):
    """Fill for an activity's set of move types: worst violation wins
    (Model > Log); else conformant grey if only synchronous; else None when the
    activity does not appear in the trace at all."""
    for mt in _MOVE_TYPES:
        if mt in types:
            return _BPMN_FILL[mt]
    if "Synchronous Move" in types:
        return _BPMN_CONFORM_FILL
    return None


def _make_bpmn_node_style_fn(ctx):
    """Build a node_style_fn returning the optional 5th element (dash pattern)."""
    act_types = _build_act_types_map(ctx["rows"])

    def node_style_fn(eid, elem):
        if elem.get("kind") != "task":
            return "white", "#888888", 2, "#333333"
        types = act_types.get(elem.get("name", ""), set())
        fill = _bpmn_fill_for_types(types)
        # Dash marks a "both" activity (a Model move AND a Log move in the trace).
        dash = _BOTH_DASH if {"Model Move", "Log Move"} <= types else None
        if fill is None:
            return _BPMN_ABSENT_FILL, "#bbbbbb", 1.2, "#333333", None
        return fill, "#333333", 2.5, contrasting_text_color(fill), dash

    return node_style_fn


def _bpmn_legend():
    return [
        (_BPMN_ABSENT_FILL,  "#bbbbbb", 1.0, "Not in this trace"),
        (_BPMN_CONFORM_FILL, "#333333", 1.5, "Synchronous (conformant)"),
        (_BPMN_FILL["Model Move"], "#333333", 1.0, "Model Move"),
        (_BPMN_FILL["Log Move"],   "#333333", 1.0, "Log Move"),
        (_BPMN_FILL["Model Move"], "#333333", 2.5, "Both Model & Log Move", _BOTH_DASH),
    ]


# ---------------------------------------------------------------------------
# Idiom 5: flow_chart_elaborate (BPMN annotated by move type)
# ---------------------------------------------------------------------------

def task14_flow_chart_elaborate(ctx, model_path, output_dir):
    """BPMN diagram with activity nodes coloured by move type; dashed = synchronous."""
    out = os.path.join(output_dir, "task14_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Move Classification on Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task14: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Move Classification on Model", "Could not parse BPMN model.")
        return

    render_bpmn_annotated(
        parsed, out,
        title=f"Move Classification on Model — {ctx['trace_label']}  "
              f"(fitness {ctx['fitness']:.4f})",
        summary=_BPMN_SUMMARY,
        node_style_fn=_make_bpmn_node_style_fn(ctx),
        legend_items=_bpmn_legend(),
    )


# ---------------------------------------------------------------------------
# Idiom 6: flow_chart_elaborate_table
# ---------------------------------------------------------------------------

def task14_flow_chart_elaborate_table(ctx, model_path, output_dir):
    """BPMN diagram (top) + move classification table (bottom)."""
    out = os.path.join(output_dir, "task14_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Move Classification on Model + Table",
                               "No BPMN model available.")
        return
    if not ctx["rows"]:
        render_empty_state_svg(out, "Move Classification on Model + Table",
                               "No trace steps.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task14: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Move Classification on Model + Table",
                               "Could not parse BPMN model.")
        return

    table_cols = ["Step", "Activity", "Move Type"]
    table_rows = _all_step_rows(ctx)
    panels = [{
        "parsed": parsed,
        "node_style_fn": _make_bpmn_node_style_fn(ctx),
        "subtitle": (f"{ctx['trace_label']} · fitness {ctx['fitness']:.4f} · "
                     "node colour = move type · dashed = both Model & Log"),
    }]
    compose_bpmn_panels(
        panels, out,
        title="Move Classification on Model — with Annotation Table",
        legend_items=_bpmn_legend(),
        table_rows=table_rows,
        table_cols=table_cols,
    )


# ---------------------------------------------------------------------------
# Idiom 9: table_bar_chart
# ---------------------------------------------------------------------------

def task14_table_bar_chart(ctx, output_dir):
    """Composite: move classification table (left) + move type bar chart (right)."""
    out = os.path.join(output_dir, "task14_table_bar_chart.svg")

    cell_text = _all_step_rows(ctx) or [["—", "No trace steps", "—"]]

    counts = _type_counts_all(ctx)
    present = [(mt, counts[mt]) for mt in _ALL_TYPES if counts[mt] > 0]

    fig_h = max(4.5, 1.4 + len(cell_text) * 0.42)
    fig = plt.figure(figsize=(16, fig_h))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.45)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    n_rows = len(cell_text) + 1
    tbl_frac = min(0.85, 0.50 * n_rows / fig_h)
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Step", "Activity", "Move Type"],
        bbox=[0.01, max(0.05, 0.85 - tbl_frac), 0.98, tbl_frac],
        col_widths=[0.12, 0.45, 0.43],
        font_size=9,
        scale_xy=(1, 1.4),
    )
    ax_bar = fig.add_subplot(gs[1])
    if present:
        labels, vals = zip(*present)
        colors = [_TYPE_COLOR[mt] for mt in labels]
        ymax = max(vals)
        bars = ax_bar.bar(labels, vals, color=colors, edgecolor="white", width=0.55, alpha=0.90)
        for bar, v in zip(bars, vals):
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + ymax * 0.015,
                str(v), ha="center", va="bottom", fontsize=FONT_ANNOT,
            )
        ax_bar.set_ylim(0, ymax * 1.18)
        ax_bar.set_ylabel("Occurrences", fontsize=FONT_LABEL)
        ax_bar.tick_params(axis="x", labelrotation=20)
    else:
        ax_bar.axis("off")
        ax_bar.text(0.5, 0.5, "No trace steps", ha="center", va="center",
                    fontsize=FONT_ANNOT, color="#888888", transform=ax_bar.transAxes)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax_bar.set_axisbelow(True)

    fig.suptitle(
        f"Move Classification Summary — {ctx['trace_label']}  "
        f"(fitness {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE, y=0.99,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 10: parallel_sets
# ---------------------------------------------------------------------------

def task14_parallel_sets(ctx, output_dir):
    """Parallel Sets: left = step status (Conformant / Violation), right = violation types."""
    out = os.path.join(output_dir, "task14_parallel_sets.svg")
    rows = ctx["rows"]
    if not rows:
        render_empty_state_svg(out, "Step Flow to Violation Types", "No trace steps.")
        return

    counts = _type_counts(ctx)
    active_types = [mt for mt in _MOVE_TYPES if counts[mt] > 0]
    if not active_types:
        render_empty_state_svg(out, "Step Flow to Violation Types", "No violations in this trace.")
        return

    n_sync = sum(1 for r in rows if r["moveType"] == "Synchronous Move")

    # Left: Conformant / Violation; Right: None(Conformant) + active violation types
    left_labels = ["Conformant", "Violation"]
    right_labels = ["None (Conformant)"] + active_types

    matrix = np.zeros((2, len(right_labels)), dtype=float)
    matrix[0, 0] = float(n_sync)
    for ci, mt in enumerate(active_types):
        matrix[1, ci + 1] = float(counts[mt])

    left_colors  = [GREY_LIGHTER, "#777777"]
    right_colors = ["#CCCCCC"] + [_TYPE_COLOR[mt] for mt in active_types]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.20)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_labels,
        matrix=matrix,
        left_colors=left_colors,
        right_colors=right_colors,
        left_title="Step Status",
        right_title="Classification",
    )
    ax.set_title(
        f"Step Flow to Violation Types — {ctx['trace_label']}  "
        f"(fitness {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE, pad=12,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(alignments, model_path: str, output_dir: str):
    """Generate all Task 14 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 14 visualizations ---")

    ctx = _build_context(alignments)
    if ctx is None:
        logger.warning("      task14: no usable alignment — emitting zero-state SVGs.")
        _msg = "No alignment data available."
        for idiom in IDIOMS:
            render_empty_state_svg(
                os.path.join(output_dir, f"task14_{idiom}.svg"),
                "Violation Classification", _msg,
            )
        return

    logger.info(
        f"      Using {ctx['trace_label']} (index {ctx['trace_index']}, "
        f"fitness={ctx['fitness']:.4f}, violations={len(ctx['violations'])})"
    )

    task14_table(ctx, output_dir)
    task14_bar_chart(ctx, output_dir)
    task14_flow_chart_and_table(ctx, output_dir)
    # task14_flow_chart_elaborate(ctx, model_path, output_dir)  # commented out
    task14_flow_chart_elaborate_table(ctx, model_path, output_dir)
    task14_table_bar_chart(ctx, output_dir)
    task14_parallel_sets(ctx, output_dir)
