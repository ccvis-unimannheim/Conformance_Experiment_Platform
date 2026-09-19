"""
tasks/task28.py – task28: where exactly the process execution differs from the
guideline.

Trace level: the alignment of the chosen traces (see trace_ids / trace_pick_rule
below), drawn by task09's trace-alignment figures in the chosen perspective
(control flow, data or resource) — the same pictures task09 shows. Log level: an
exploratory overview of the deviations across the whole log.

Public API:
    generate(alignments, model_path, output_dir, log=None,
             perspective="control-flow", trace_ids=None,
             trace_pick_rule="first_nonconformant", trace_count=1,
             data_attribute="", conformant_values=(),
             conformant_resources=(), scoped_activity="")
        perspective          – "control-flow" | "data" | "resource": what the
                               shown traces are checked against
        trace_ids            – traces to show; empty = chosen by
                               trace_pick_rule, trace_count of them (see
                               trace_alignment.PICK_RULES)
        data_attribute,
        conformant_values    – the data rule (perspective "data")
        conformant_resources,
        scoped_activity      – the resource rule (perspective "resource")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_basic", "flow_chart_elaborate", "table", "bar_chart",
          "stacked_bar", "boxplot", "matrix", "heatmap"]

import trace_alignment

#: Same question as task09 — where does the execution differ from the guideline,
#: and in which perspective — explored rather than presented, so the parameters
#: are task09's. The difference is not a parameter: task28 does not hand the
#: participant the violations, which is HIGHLIGHT_VIOLATIONS below.
PARAM_SPEC = [
    trace_alignment.PERSPECTIVE_PARAM,
    *trace_alignment.selection_params(
        rules=["first_nonconformant", "worst_fitness", "violation_gap",
               "most_frequent_variants"],
        default_rule="first_nonconformant",
        count_default=1, count_min=1, count_max=4,
    ),
    {**trace_alignment.VIOLATION_PATTERN_PARAM,
     "visible_if": {**trace_alignment.VIOLATION_PATTERN_PARAM["visible_if"],
                    "perspective": "control-flow"}},
    trace_alignment.DATA_ATTRIBUTE_PARAM,
    trace_alignment.CONFORMANT_VALUES_PARAM,
    trace_alignment.CONFORMANT_RESOURCES_PARAM,
    trace_alignment.SCOPED_ACTIVITY_PARAM,
]

#: Explore · Identify: the means to find the violations are provided, the
#: violations themselves are not pointed out. A task property, not an admin
#: choice — the wording of the task fixes it.
HIGHLIGHT_VIOLATIONS = False


def validate_params(log, params) -> list:
    return (trace_alignment.validate_selection(log, params, min_traces=1, max_traces=4)
            + trace_alignment.validate_perspective(log, params))

import html
import math
import os
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap

from shared import (
    save_svg, make_table, GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    chevron_figure_width, chevron_nodes_from_alignment_rows, draw_chevron_strip,
    alignment_pairs_to_rows, build_violation_pattern_df,
    draw_value_heatmap, draw_rate_matrix, draw_grouped_box_plot,
    parse_bpmn_model, render_bpmn_annotated,
    render_empty_state_svg, contrasting_text_color,
)


# Task 2 – Location / alignment visualizations (representative trace)
# ---------------------------------------------------------------------------

# Task 2 helpers
TASK28_HEADER_COLOR = GREY_DARK
TASK28_SYNC_ROW_COLOR = GREY_LIGHTER
TASK28_MODEL_ROW_COLOR = GREY_LIGHT
TASK28_LOG_ROW_COLOR = GREY_MED
TASK28_MISMATCH_ROW_COLOR = GREY_MED
TASK28_TABLE_EDGE_COLOR = "#FFFFFF"
TASK28_TABLE_COL_LABELS = ["Step", "Log Move", "Model Move", "Status"]
TASK28_TABLE_COL_WIDTHS = [0.065, 0.375, 0.375, 0.185]


def pick_representative_trace_index(alignments):
    """First trace with fitness < 1, else 0."""
    for i, result in enumerate(alignments):
        if float(result.get("fitness", 1.0)) < 1.0 - 1e-9:
            return i
    return 0


def build_task28_context(alignments):
    """Pick representative trace and build row list; returns None if no usable alignment."""
    if not alignments:
        return None
    idx = pick_representative_trace_index(alignments)
    result = alignments[idx]
    alignment = result.get("alignment")
    if not alignment:
        return None
    rows = alignment_pairs_to_rows(alignment)
    if not rows:
        return None
    return {
        "trace_index": idx,
        "trace_label": f"Trace {idx + 1}",
        "fitness": float(result.get("fitness", 0.0)),
        "cost": result.get("cost"),
        "rows": rows,
    }


def _task28_format_cost(cost):
    """Format PM4Py alignment cost for the table subtitle."""
    if cost is None:
        return None
    try:
        cost_num = float(cost)
    except (TypeError, ValueError):
        return str(cost)
    if abs(cost_num - round(cost_num)) < 1e-9:
        return str(int(round(cost_num)))
    return f"{cost_num:.4f}".rstrip("0").rstrip(".")


def _task28_status_color(move_type: str) -> str:
    """Map alignment move type to the reference table row color."""
    if move_type == "Model Move":
        return TASK28_MODEL_ROW_COLOR
    if move_type == "Log Move":
        return TASK28_LOG_ROW_COLOR
    if move_type == "Mismatch Move":
        return TASK28_MISMATCH_ROW_COLOR
    return TASK28_SYNC_ROW_COLOR


def _task28_table_cell_text(rows):
    """Return table cells in the reference Step | Log | Model | Status order."""
    return [
        [str(row["step"]), str(row["log_move"]), str(row["model_move"]), str(row["status"])]
        for row in rows
    ]


def _task28_alignment_table_height(row_count: int, *, compact: bool = False) -> float:
    """Figure height that keeps table rows close to the reference density."""
    base = 3.8 if compact else 4.7
    row_h = 0.27 if compact else 0.31
    return max(base, base + row_count * row_h)


def _draw_task28_alignment_table(ax, rows, *, bbox, font_size=10.5, scale_y=1.4):
    """Standard zebra table, aligned with the platform's other tables: dark header,
    alternating white/light-grey rows, no per-status colour."""
    return make_table(
        ax,
        cell_text=_task28_table_cell_text(rows),
        col_labels=TASK28_TABLE_COL_LABELS,
        bbox=bbox,
        col_widths=TASK28_TABLE_COL_WIDTHS,
        font_size=font_size,
        scale_xy=(1, scale_y),
    )


def _add_task28_table_heading(fig, ctx, *, x=0.055, y=0.86, compact=False):
    """Add the trace title and alignment summary above the table."""
    fig.text(
        x,
        y,
        ctx["trace_label"],
        ha="left",
        va="top",
        fontsize=FONT_TITLE,
        color="#111111",
    )

    cost_text = _task28_format_cost(ctx.get("cost"))
    meta_parts = [f"Fitness: {ctx['fitness']:.4f}"]
    if cost_text is not None:
        meta_parts.append(f"Cost: {cost_text}")
    fig.text(
        x,
        y - (0.055 if compact else 0.065),
        "   |   ".join(meta_parts),
        ha="left",
        va="top",
        fontsize=FONT_ANNOT,
        color="#6C6C6C",
    )


# Chevron strip primitives moved to shared.py (chevron_layout, draw_chevron_strip,
# chevron_figure_width, chevron_nodes_from_alignment_rows) so task27 can reuse them.

def _task28_move_legend_elements():
    return [
        mpatches.Patch(facecolor=GREY_LIGHTER, edgecolor="black", linewidth=0.75, label="Synchronous move (Conform)"),
        mpatches.Patch(facecolor=GREY_MED, edgecolor="black", linewidth=0.75, label="Model move only"),
        mpatches.Patch(facecolor=GREY_DARK, edgecolor="black", linewidth=0.75, label="Log move only"),
    ]


# Task 2 visualizations
def task28_alignment_table(ctx: dict, output_dir: str):
    """Alignment detail table for representative trace."""
    rows = ctx["rows"]

    fig_h = _task28_alignment_table_height(len(rows))
    fig, ax = plt.subplots(figsize=(15.8, fig_h))
    ax.axis("off")
    _add_task28_table_heading(fig, ctx, x=0.06, y=0.86)
    _draw_task28_alignment_table(
        ax,
        rows,
        bbox=[0.045, 0.08, 0.91, 0.58],
        font_size=10.5,
    )
    fig.subplots_adjust(left=0.025, right=0.985, top=0.94, bottom=0.05)
    save_svg(fig, os.path.join(output_dir, "task28_table.svg"))


def task28_flow_chart_basic(ctx: dict, output_dir: str):
    """Chevron diagram (reference layout): titled flow strip + bottom move-type legend."""
    nodes = chevron_nodes_from_alignment_rows(ctx["rows"])

    fig_w = chevron_figure_width(nodes)
    fig_h = 4.15
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_chevron_strip(ax, nodes, fontsize=10)
    fig.subplots_adjust(left=0.045, right=0.985, top=0.55, bottom=0.28)
    fig.text(
        0.045,
        0.90,
        "Trace Alignment",
        ha="left",
        va="top",
        fontsize=FONT_TITLE,
        color="black",
    )
    fig.text(
        0.045,
        0.58,
        ctx["trace_label"],
        ha="left",
        va="center",
        fontsize=FONT_TITLE,
        color="#222222",
    )
    fig.legend(
        handles=_task28_move_legend_elements(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.075),
        ncol=3,
        fontsize=FONT_ANNOT,
        frameon=True,
        fancybox=False,
        edgecolor="#cccccc",
    )
    save_svg(fig, os.path.join(output_dir, "task28_flow_chart_basic.svg"))


_MISSING_MOVE_TOKENS = {"-", "None", "(skip)", ">>", ""}

def _trace_act_status(rows):
    """activity -> alignment status for one trace. Deviations override 'conform'."""
    status = {}
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous Move":
            name = r["log_move"] if str(r["log_move"]) not in _MISSING_MOVE_TOKENS else r["model_move"]
            status.setdefault(str(name), "conform")
        elif mt == "Model Move":
            status[str(r["model_move"])] = "skipped"
        elif mt == "Log Move":
            status[str(r["log_move"])] = "extra"
        elif mt == "Mismatch Move":
            status[str(r["log_move"])] = "mismatch"
    return status


def task28_flow_chart_elaborate_bpmn(ctx: dict, model_path: str, output_dir: str):
    """Annotate the BPMN model with this trace's alignment status, using the shared
    renderer (clean arrows + a legend whose colours match the node fills)."""
    out = os.path.join(output_dir, "task28_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Trace Alignment on the Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"      task28: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Trace Alignment on the Model", "Could not parse the BPMN model.")
        return

    status = _trace_act_status(ctx["rows"])
    fills = {"conform": GREY_LIGHTER, "skipped": GREY_LIGHT,
             "extra": GREY_DARK, "mismatch": GREY_MED}

    def node_style_fn(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task" and name in status:
            fill = fills[status[name]]
            tc = contrasting_text_color(fill)
            return fill, GREY_DARK, 2.5, tc
        if elem.get("kind") == "task":
            return "white", GREY_MED, 1.5, GREY_DARK
        return "white", GREY_MED, 2, GREY_DARK

    legend = [
        (GREY_LIGHTER, GREY_DARK, 1.0, "Synchronous move"),
        (GREY_LIGHT,   GREY_DARK, 1.0, "Model move"),
        (GREY_DARK,    GREY_DARK, 1.0, "Log move"),
        ("white",      GREY_MED,  1.0, "Not in this trace"),
    ]
    render_bpmn_annotated(
        parsed, out,
        title=f"Trace Alignment on the Model — {ctx['trace_label']} "
              f"(fitness {ctx['fitness']:.4f})",
        summary="Task shade = this trace's alignment status; border colour matches the legend.",
        node_style_fn=node_style_fn, legend_items=legend)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# ===========================================================================
# LOG-LEVEL EXPLORATORY IDIOMS (Explore · Identify)
#
# task28 is "Explore · Identify · Guideline violations": deviations are NOT
# pre-summarised for the analyst (that is task29's "Present" job). These overview
# idioms present the NEUTRAL facts — how often each deviation kind occurs, where,
# and which traces carry many — so the analyst scans, spots, and then drills into
# a single trace with the chevron / table / BPMN idioms above.
#
# A "deviation" is the conformance algorithm's own classification, not a value
# judgment: Model Move (activity skipped), Log Move (extra activity), Mismatch.
# ===========================================================================

TOP_N = 12
MOVE_TYPES = ["Model Move", "Log Move", "Mismatch Move"]
MOVE_TYPE_COLORS = {"Model Move": GREY_DARK, "Log Move": GREY_MED, "Mismatch Move": GREY_LIGHT}
_MOVE_RANK = {m: i for i, m in enumerate(MOVE_TYPES)}


def _move_color(mt):
    return MOVE_TYPE_COLORS.get(mt, "#777777")


def _present_move_types(df):
    present = set(df["move_type"])
    return [m for m in MOVE_TYPES if m in present] or list(present)


def _wrap_pat(p):
    return str(p).replace(" (", "\n(", 1)


def _dev_df(alignments):
    """Log-level deviation-pattern frame (pattern, activity, move_type, count, pct)."""
    df = build_violation_pattern_df(alignments)
    if df.empty:
        return df
    df = df.copy()
    df["move_rank"] = df["move_type"].map(_MOVE_RANK).fillna(len(MOVE_TYPES))
    return df.sort_values("count", ascending=False).reset_index(drop=True)


def _trace_dev_df(alignments):
    """Per-trace frame: trace_index, fitness, n_dev (non-sync moves)."""
    rows = []
    for i, res in enumerate(alignments or []):
        steps = alignment_pairs_to_rows(res.get("alignment") or [])
        n_dev = sum(1 for s in steps if s["moveType"] != "Synchronous Move")
        rows.append({"trace_index": i, "fitness": float(res.get("fitness", 0.0)),
                     "n_dev": n_dev})
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["trace_index", "fitness", "n_dev"])


def _activity_movetype_pivot(df, top_n=TOP_N):
    move_types = _present_move_types(df)
    act_totals = df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts = act_totals.head(top_n).index.tolist()
    sub = df[df["activity"].isin(top_acts)]
    pivot = (sub.groupby(["activity", "move_type"])["count"].sum()
             .unstack(fill_value=0)
             .reindex(index=top_acts, columns=move_types, fill_value=0))
    return pivot, top_acts, move_types


# --- Idiom: boxplot — deviations-per-trace distribution (find outliers) -------

def task28_boxplot(tdf, output_dir):
    out = os.path.join(output_dir, "task28_boxplot.svg")
    if tdf.empty:
        render_empty_state_svg(out, "Deviations per Trace", "No traces.")
        return
    data = [tdf["n_dev"].to_numpy(dtype=float)]
    vmax = float(data[0].max()) if data[0].size else 1.0
    fig, ax = plt.subplots(figsize=(5.0, 6))
    draw_grouped_box_plot(ax, data, ["All traces"], [GREY_MED],
                          ylabel="Deviating steps per trace", ylim=(-0.3, vmax + 1))
    ax.set_title("Deviations per Trace — spot the outliers", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# --- Idiom: bar_chart — frequency per deviation pattern ----------------------

def task28_bar_chart(df, output_dir):
    out = os.path.join(output_dir, "task28_bar_chart.svg")
    if df.empty:
        render_empty_state_svg(out, "Where Does the Log Deviate?", "No deviations found.")
        return
    top = df.head(TOP_N)
    patterns = top["pattern"].tolist()
    counts = top["count"].to_numpy(dtype=float)
    colors = [_move_color(m) for m in top["move_type"]]
    move_types = _present_move_types(df)
    x = np.arange(len(patterns))

    fig, ax = plt.subplots(figsize=(max(8, len(patterns) * 1.25), 6))
    ax.bar(x, counts, color=colors, edgecolor="white", linewidth=0.6, width=0.72)
    for xi, c in zip(x, counts):
        ax.text(xi, c, f"{int(c)}", ha="center", va="bottom",
                fontsize=FONT_ANNOT - 1, color="#444444")
    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_pat(p) for p in patterns], rotation=0,
                       ha="center", fontsize=FONT_ANNOT - 2)
    ax.set_ylabel("Observed count", fontsize=FONT_LABEL)
    ax.set_ylim(0, counts.max() * 1.12)
    ax.set_title("Observed Deviating Steps per Pattern", fontsize=FONT_TITLE)
    ax.legend(handles=[mpatches.Patch(color=_move_color(m), label=m) for m in move_types],
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=len(move_types), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# --- Idiom: stacked_bar — per activity, segmented by deviation type ----------

def task28_stacked_bar(df, output_dir):
    out = os.path.join(output_dir, "task28_stacked_bar.svg")
    if df.empty:
        render_empty_state_svg(out, "Deviations per Activity", "No deviations found.")
        return
    pivot, top_acts, move_types = _activity_movetype_pivot(df)
    x = np.arange(len(top_acts))
    bottoms = np.zeros(len(top_acts))
    fig, ax = plt.subplots(figsize=(max(8, len(top_acts) * 0.95), 5.5))
    for m in move_types:
        vals = pivot[m].values
        ax.bar(x, vals, bottom=bottoms, color=_move_color(m),
               edgecolor="white", linewidth=0.5, label=m)
        bottoms += vals
    ax.set_xticks(x)
    ax.set_xticklabels(top_acts, rotation=0, ha="center", fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Observed count", fontsize=FONT_LABEL)
    ax.set_title(f"Deviations per Activity, by Type (top-{len(top_acts)})", fontsize=FONT_TITLE)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# --- Idiom: matrix / heatmap — activity × deviation type ---------------------

def task28_matrix(df, output_dir):
    out = os.path.join(output_dir, "task28_matrix.svg")
    if df.empty:
        render_empty_state_svg(out, "Activity × Deviation Type", "No deviations found.")
        return
    pivot, top_acts, move_types = _activity_movetype_pivot(df)
    data = pivot.values.astype(float)
    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(move_types) * 2.0), fig_h))
    draw_rate_matrix(fig, ax, data, top_acts, move_types,
                     xlabel="Deviation Type", cell_fmt="{:.0f}", colorless=True)
    ax.set_title(f"Explore: Activity × Deviation Type (top-{len(top_acts)})", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


def task28_heatmap(df, output_dir):
    out = os.path.join(output_dir, "task28_heatmap.svg")
    if df.empty:
        render_empty_state_svg(out, "Deviation Heatmap", "No deviations found.")
        return
    pivot, top_acts, move_types = _activity_movetype_pivot(df)
    data = pivot.values.astype(float)
    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(move_types) * 2.0), fig_h))
    draw_value_heatmap(fig, ax, data, top_acts, move_types,
                       xlabel="Deviation Type", cbar_label="Count", annotate=False)
    ax.set_title(f"Deviation Heatmap (top-{len(top_acts)} activities)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ===========================================================================
# Public entry point
# ===========================================================================

_LOG_FNAMES_TITLES = [
    ("task28_bar_chart.svg",                  "Where Does the Log Deviate?"),
    ("task28_stacked_bar.svg",                "Deviations per Activity"),
    ("task28_boxplot.svg",                    "Deviations per Trace"),
    ("task28_matrix.svg",                     "Activity × Deviation Type"),
    ("task28_heatmap.svg",                    "Deviation Heatmap"),
]


def generate(alignments, model_path: str, output_dir: str, log=None,
             perspective="control-flow", trace_ids=None,
             trace_pick_rule="first_nonconformant", trace_count=1,
             violation_pattern="", data_attribute="", conformant_values=(),
             conformant_resources=(), scoped_activity=""):
    """Generate all Task 28 SVGs into output_dir (trace-level deep-dive + log-level
    exploratory overview).

    The trace-level trio is task09's, in whichever perspective the admin chose —
    the two tasks ask the same question of the same traces, one presenting the
    answer and one leaving it to be explored, so they must not show two
    different pictures of it.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 28 visualizations ---")

    # Trace-level deep-dive (the chosen traces)
    ctx = build_task28_context(alignments)
    records = trace_alignment.select_records(
        log, alignments, view=perspective, trace_ids=trace_ids,
        rule=trace_pick_rule, count=trace_count, pattern=violation_pattern,
        attribute=data_attribute, conformant_values=conformant_values,
        resources=conformant_resources, scoped_activity=scoped_activity,
    ) if log is not None else []

    if records:
        import tasks.task09 as task09
        logger.info(f"      -> {len(records)} trace(s) shown, {perspective} perspective.")
        task09.alignment_figures(output_dir, model_path, view=perspective,
                                 records=records, attribute=data_attribute,
                                 prefix="task28")
    elif ctx is not None:
        logger.info(f"      Using {ctx['trace_label']} (log index {ctx['trace_index']}, "
                    f"fitness={ctx['fitness']:.4f})")
        task28_alignment_table(ctx, output_dir)
        task28_flow_chart_basic(ctx, output_dir)
        task28_flow_chart_elaborate_bpmn(ctx, model_path, output_dir)
    else:
        logger.warning("      task28: no deviating trace — trace-level idioms skipped.")

    # Log-level exploratory overview
    df = _dev_df(alignments)
    tdf = _trace_dev_df(alignments)
    if df.empty:
        logger.warning("      task28: no deviations — emitting log-level zero-state SVGs.")
        for fname, title in _LOG_FNAMES_TITLES:
            render_empty_state_svg(os.path.join(output_dir, fname), title, "No deviations found.")
        return

    logger.info(f"      -> {len(df)} deviation patterns; "
                f"{int((tdf['n_dev'] > 0).sum())}/{len(tdf)} traces deviate.")
    task28_bar_chart(df, output_dir)
    task28_stacked_bar(df, output_dir)
    task28_boxplot(tdf, output_dir)
    task28_matrix(df, output_dir)
    task28_heatmap(df, output_dir)
