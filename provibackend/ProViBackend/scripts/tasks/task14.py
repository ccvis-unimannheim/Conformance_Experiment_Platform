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
    "table", "bar_chart", "scatter_plot",
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
    "an unexpected step was executed that the model does not prescribe; a "
    "Mismatch Move indicates a recorded step that conflicts with the model's "
    "expectation at that position. "
    "Full credit requires correctly identifying all present violation types and "
    "giving a meaningful process-level description for each. "
    "Partial credit for identifying some types or for correct naming without "
    "explanation. No credit for types not present in the trace."
)


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """For mc-multi: which violation types appear in the representative trace.

    Returns options for all three move types, each flagged correct=True iff
    that type occurs at least once in the representative (worst-fitness) trace.
    Free-text format falls through to the static RUBRIC; no value is computed.
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
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK,
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

_MOVE_TYPES = ["Model Move", "Log Move", "Mismatch Move"]

_TYPE_COLOR = {
    "Model Move":      GREY_MED,
    "Log Move":        GREY_DARK,
    "Mismatch Move":   GREY_LIGHT,
    "Synchronous Move": GREY_LIGHTER,
}

# Domain-agnostic descriptions for each violation type
_TYPE_DESC = {
    "Model Move":    "Required step absent in recorded trace",
    "Log Move":      "Unexpected step recorded; not prescribed by model",
    "Mismatch Move": "Step recorded differs from model expectation",
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


def _type_counts(ctx):
    """Return {move_type: count} for violation steps in this trace."""
    counts = {mt: 0 for mt in _MOVE_TYPES}
    for r in ctx["violations"]:
        mt = r["moveType"]
        if mt in counts:
            counts[mt] += 1
    return counts


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


def _build_act_type_map(violations):
    """Map activity name -> violation type (last deviation per activity wins)."""
    act_type = {}
    for r in violations:
        act = _activity_for_row(r)
        if act and act not in _MISSING_TOKENS:
            act_type[act] = r["moveType"]
    return act_type


# ---------------------------------------------------------------------------
# Idiom 1: table
# ---------------------------------------------------------------------------

def task14_table(ctx, output_dir):
    """Annotation table: each violation step with step number, activity, type, description."""
    out = os.path.join(output_dir, "task14_table.svg")
    violations = ctx["violations"]
    if not violations:
        render_empty_state_svg(out, "Violation Classification", "No violations in this trace.")
        return

    cell_text = [
        [str(r["step"]), _activity_for_row(r), r["moveType"]]
        for r in violations
    ]

    fig_h = max(3.2, 1.5 + len(cell_text) * 0.42)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Step", "Activity", "Violation Type"],
        bbox=[0.02, 0.05, 0.96, 0.78],
        col_widths=[0.12, 0.48, 0.40],
        font_size=9.5,
        scale_xy=(1, 1.7),
    )
    ax.set_title(
        f"Violation Classification — {ctx['trace_label']}  (fitness {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE, pad=10,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 2: bar_chart
# ---------------------------------------------------------------------------

def task14_bar_chart(ctx, output_dir):
    """Bar chart: number of each violation type within the representative trace."""
    out = os.path.join(output_dir, "task14_bar_chart.svg")
    counts = _type_counts(ctx)
    present = [(mt, counts[mt]) for mt in _MOVE_TYPES if counts[mt] > 0]
    if not present:
        render_empty_state_svg(out, "Violation Type Distribution", "No violations in this trace.")
        return

    labels, vals = zip(*present)
    colors = [_TYPE_COLOR[mt] for mt in labels]
    ymax = max(vals)

    fig, ax = plt.subplots(figsize=(7, 5.5))
    bars = ax.bar(labels, vals, color=colors, edgecolor="white", width=0.55, alpha=0.90)
    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.015,
            str(v), ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Occurrences in Trace", fontsize=FONT_LABEL)
    ax.set_title(
        f"Violation Type Distribution — {ctx['trace_label']}",
        fontsize=FONT_TITLE,
    )
    ax.set_ylim(0, ymax * 1.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelrotation=0)

    legend_handles = [
        mpatches.Patch(facecolor=_TYPE_COLOR[mt], label=mt)
        for mt in _MOVE_TYPES if counts[mt] > 0
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower center", bbox_to_anchor=(0.5, -0.25),
        ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 3: scatter_plot
# ---------------------------------------------------------------------------

def task14_scatter_plot(ctx, output_dir):
    """Scatter: each trace step as a point. X = step position, Y-lane = move type."""
    out = os.path.join(output_dir, "task14_scatter_plot.svg")
    rows = ctx["rows"]
    if not rows:
        render_empty_state_svg(out, "Trace Step Classification", "No trace steps.")
        return

    _type_y = {
        "Synchronous Move": 0,
        "Model Move":       1,
        "Log Move":         2,
        "Mismatch Move":    3,
    }
    ytick_labels = [
        "Synchronous\n(Conformant)",
        "Model Move",
        "Log Move",
        "Mismatch Move",
    ]

    fig, ax = plt.subplots(figsize=(max(10, len(rows) * 0.32 + 3), 4.8))
    for mt, y_pos in _type_y.items():
        xs = [r["step"] for r in rows if r["moveType"] == mt]
        if not xs:
            continue
        ys = [y_pos] * len(xs)
        marker = "o" if mt == "Synchronous Move" else "D"
        size = 22 if mt == "Synchronous Move" else 50
        ax.scatter(xs, ys, c=_TYPE_COLOR[mt], s=size, marker=marker,
                   alpha=0.82, linewidths=0, zorder=3)

    ax.set_yticks([0, 1, 2, 3])
    ax.set_yticklabels(ytick_labels, fontsize=FONT_ANNOT)
    ax.set_xlabel("Step position in trace", fontsize=FONT_LABEL)
    ax.set_title(
        f"Trace Step Classification — {ctx['trace_label']}  (fitness {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE,
    )
    ax.set_ylim(-0.65, 3.65)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    legend_handles = [
        mpatches.Patch(facecolor=_TYPE_COLOR[mt], label=mt)
        for mt in ["Synchronous Move"] + _MOVE_TYPES
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper right", fontsize=FONT_ANNOT, frameon=True, framealpha=0.9,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 4: flow_chart_table
# ---------------------------------------------------------------------------

def task14_flow_chart_and_table(ctx, output_dir):
    """Chevron flow strip (top) + violation classification table (bottom)."""
    out = os.path.join(output_dir, "task14_flow_chart_and_table.svg")
    rows = ctx["rows"]
    violations = ctx["violations"]
    nodes = chevron_nodes_from_alignment_rows(rows)

    if not nodes:
        render_empty_state_svg(out, "Trace Flow & Violation Classification", "No trace steps.")
        return

    cell_text = [
        [str(r["step"]), _activity_for_row(r), r["moveType"]]
        for r in violations
    ] if violations else [["—", "No violations", "—"]]

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
        col_labels=["Step", "Activity", "Violation Type"],
        bbox=[0.0, 0.0, 1.0, 1.0],
        col_widths=[0.10, 0.50, 0.40],
        font_size=9,
        scale_xy=(1, 1.5),
    )
    ax_tbl.set_title("Violation Classification", fontsize=FONT_TITLE, pad=7)

    legend_handles = [
        mpatches.Patch(facecolor=GREY_LIGHTER,  label="Synchronous (Conformant)"),
        mpatches.Patch(facecolor=GREY_MED,   label="Model Move"),
        mpatches.Patch(facecolor=GREY_DARK,    label="Log Move"),
        mpatches.Patch(facecolor=GREY_LIGHT, label="Mismatch Move"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center", bbox_to_anchor=(0.5, 0.01),
        ncol=2, fontsize=FONT_ANNOT, frameon=True, fancybox=False, edgecolor="#cccccc",
    )
    fig.suptitle(
        f"Violation Classification — {ctx['trace_label']}  (fitness {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE, y=0.99,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 5: flow_chart_elaborate (BPMN annotated by violation type)
# ---------------------------------------------------------------------------

def task14_flow_chart_elaborate(ctx, model_path, output_dir):
    """BPMN diagram with activity nodes coloured by their violation type."""
    out = os.path.join(output_dir, "task14_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Violation Classification on Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task14: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Violation Classification on Model", "Could not parse BPMN model.")
        return

    act_type = _build_act_type_map(ctx["violations"])

    _fill = {
        "Model Move":    "#999999",
        "Log Move":      "#555555",
        "Mismatch Move": "#777777",
    }

    def node_style_fn(eid, elem):
        if elem.get("kind") != "task":
            return "white", "#888888", 2, "#333333"
        mt = act_type.get(elem.get("name", ""))
        if mt:
            fill = _fill[mt]
            tc = "white" if int(fill.lstrip("#")[0:2], 16) < 0x99 else "#222222"
            return fill, "#333333", 2.5, tc
        return "#E8E8E8", "#888888", 1.5, "#333333"

    legend = [
        ("#E8E8E8", "#888888", 1.0, "Conformant (no violation)"),
        ("#999999", "#333333", 1.0, "Model Move"),
        ("#555555", "#333333", 1.0, "Log Move"),
        ("#777777", "#333333", 1.0, "Mismatch Move"),
    ]
    render_bpmn_annotated(
        parsed, out,
        title=f"Violation Classification on Model — {ctx['trace_label']}  "
              f"(fitness {ctx['fitness']:.4f})",
        summary="Node colour = violation type at this activity in the representative trace.",
        node_style_fn=node_style_fn,
        legend_items=legend,
    )


# ---------------------------------------------------------------------------
# Idiom 6: flow_chart_elaborate_table
# ---------------------------------------------------------------------------

def task14_flow_chart_elaborate_table(ctx, model_path, output_dir):
    """BPMN diagram (top) + annotation table (bottom)."""
    out = os.path.join(output_dir, "task14_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Violation Classification on Model + Table",
                               "No BPMN model available.")
        return
    if not ctx["violations"]:
        render_empty_state_svg(out, "Violation Classification on Model + Table",
                               "No violations in this trace.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task14: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Violation Classification on Model + Table",
                               "Could not parse BPMN model.")
        return

    act_type = _build_act_type_map(ctx["violations"])
    _fill = {
        "Model Move":    "#999999",
        "Log Move":      "#555555",
        "Mismatch Move": "#777777",
    }

    def node_style_fn(eid, elem):
        if elem.get("kind") != "task":
            return "white", "#888888", 2, "#333333"
        mt = act_type.get(elem.get("name", ""))
        if mt:
            fill = _fill[mt]
            tc = "white" if int(fill.lstrip("#")[0:2], 16) < 0x99 else "#222222"
            return fill, "#333333", 2.5, tc
        return "#E8E8E8", "#888888", 1.5, "#333333"

    legend = [
        ("#E8E8E8", "#888888", 1.0, "Conformant"),
        ("#999999", "#333333", 1.0, "Model Move"),
        ("#555555", "#333333", 1.0, "Log Move"),
        ("#777777", "#333333", 1.0, "Mismatch Move"),
    ]
    table_cols = ["Step", "Activity", "Violation Type"]
    table_rows = [
        [str(r["step"]), _activity_for_row(r), r["moveType"]]
        for r in ctx["violations"]
    ]
    panels = [{
        "parsed": parsed,
        "node_style_fn": node_style_fn,
        "subtitle": (f"{ctx['trace_label']} · fitness {ctx['fitness']:.4f} · "
                     "node colour = violation type"),
    }]
    compose_bpmn_panels(
        panels, out,
        title="Violation Classification on Model — with Annotation Table",
        legend_items=legend,
        table_rows=table_rows,
        table_cols=table_cols,
    )


# ---------------------------------------------------------------------------
# Idiom 9: table_bar_chart
# ---------------------------------------------------------------------------

def task14_table_bar_chart(ctx, output_dir):
    """Composite: annotation table (left) + violation type bar chart (right)."""
    out = os.path.join(output_dir, "task14_table_bar_chart.svg")
    violations = ctx["violations"]

    cell_text = [
        [str(r["step"]), _activity_for_row(r), r["moveType"]]
        for r in violations
    ] if violations else [["—", "No violations", "—"]]

    counts = _type_counts(ctx)
    present = [(mt, counts[mt]) for mt in _MOVE_TYPES if counts[mt] > 0]

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
        col_labels=["Step", "Activity", "Violation Type"],
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
        ax_bar.tick_params(axis="x", labelrotation=0)
    else:
        ax_bar.axis("off")
        ax_bar.text(0.5, 0.5, "No violations", ha="center", va="center",
                    fontsize=FONT_ANNOT, color="#888888", transform=ax_bar.transAxes)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax_bar.set_axisbelow(True)

    fig.suptitle(
        f"Violation Classification Summary — {ctx['trace_label']}  "
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
    task14_scatter_plot(ctx, output_dir)
    task14_flow_chart_and_table(ctx, output_dir)
    # task14_flow_chart_elaborate(ctx, model_path, output_dir)  # commented out
    task14_flow_chart_elaborate_table(ctx, model_path, output_dir)
    task14_table_bar_chart(ctx, output_dir)
    task14_parallel_sets(ctx, output_dir)
