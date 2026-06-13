"""
tasks/task28.py – Task 2: Location/alignment visualizations for a representative trace.

Public API:
    generate(alignments, model_path, output_dir)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_basic", "flow_chart_table", "flow_chart_elaborate", "table",
          "bar_chart", "stacked_bar", "scatter_plot", "boxplot", "matrix",
          "heatmap", "table_bar_chart", "network_diagram",
          "flow_chart_elaborate_table"]

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
from matplotlib import gridspec
from matplotlib.colors import LinearSegmentedColormap

from shared import (
    save_svg, make_table, BLUE, ORANGE, GREEN, RED,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    chevron_figure_width, chevron_nodes_from_alignment_rows, draw_chevron_strip,
    alignment_pairs_to_rows, build_violation_pattern_df,
    draw_value_heatmap, draw_rate_matrix, draw_grouped_box_plot,
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    render_empty_state_svg, contrasting_text_color,
)


# Task 2 – Location / alignment visualizations (representative trace)
# ---------------------------------------------------------------------------

# Task 2 helpers
TASK28_HEADER_COLOR = "#555555"
TASK28_SYNC_ROW_COLOR = "#F2F2F2"
TASK28_MODEL_ROW_COLOR = "#E0E0E0"
TASK28_LOG_ROW_COLOR = "#C8C8C8"
TASK28_MISMATCH_ROW_COLOR = "#D8D8D8"
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
        mpatches.Patch(facecolor=GREEN, edgecolor="black", linewidth=0.75, label="Synchronous move (Conform)"),
        mpatches.Patch(facecolor=BLUE, edgecolor="black", linewidth=0.75, label="Model move only"),
        mpatches.Patch(facecolor=RED, edgecolor="black", linewidth=0.75, label="Log move only"),
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


def task28_flow_chart_and_table(ctx: dict, output_dir: str):
    """Composite: table above, chevron row below. The table block is sized to its
    row count so rows keep a normal height instead of stretching to fill the figure."""
    rows = ctx["rows"]
    nodes = chevron_nodes_from_alignment_rows(rows)
    n_rows = len(rows) + 1  # + header

    fig_w = max(16.0, chevron_figure_width(nodes))
    tbl_block = 0.34 * n_rows           # inches reserved for the table
    chev_block = 2.2                    # inches for the chevron strip
    fig_h = tbl_block + chev_block + 1.4

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(2, 1, height_ratios=[tbl_block, chev_block], hspace=0.28)
    ax_top = fig.add_subplot(gs[0])
    ax_bot = fig.add_subplot(gs[1])

    ax_top.axis("off")
    _add_task28_table_heading(fig, ctx, x=0.055, y=0.97, compact=True)
    # bbox fills the (already row-sized) top subplot; scale_y=1.0 so rows are not inflated.
    _draw_task28_alignment_table(
        ax_top,
        rows,
        bbox=[0.055, 0.0, 0.89, 0.84],
        font_size=9.4,
        scale_y=1.0,
    )

    draw_chevron_strip(ax_bot, nodes, fontsize=11)
    ax_bot.set_title("Trace Alignment", fontsize=FONT_TITLE, pad=7)

    fig.tight_layout(rect=[0, 0.105, 1, 0.98])
    fig.legend(
        handles=_task28_move_legend_elements(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.025),
        ncol=3,
        fontsize=FONT_ANNOT,
        frameon=True,
        fancybox=False,
        edgecolor="#cccccc",
    )
    save_svg(fig, os.path.join(output_dir, "task28_flow_chart_and_table.svg"))


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
    fills = {"conform": "#E8E8E8", "skipped": "#999999",
             "extra": "#555555", "mismatch": "#777777"}

    def node_style_fn(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task" and name in status:
            fill = fills[status[name]]
            tc = "white" if int(fill[1:3], 16) < 0x99 else "#222222"
            return fill, "#333333", 2.5, tc
        if elem.get("kind") == "task":
            return "white", "#888888", 1.5, "#333333"
        return "white", "#888888", 2, "#333333"

    legend = [
        ("#E8E8E8", "#333333", 1.0, "Synchronous move"),
        ("#999999", "#333333", 1.0, "Model move"),
        ("#555555", "#333333", 1.0, "Log move"),
        ("white",   "#888888", 1.0, "Not in this trace"),
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
MOVE_TYPE_COLORS = {"Model Move": "#555555", "Log Move": "#999999", "Mismatch Move": "#CCCCCC"}
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


def _activity_freq(df):
    return {a: int(c) for a, c in df.groupby("activity")["count"].sum().items()}


def _freq_shade(count, max_count):
    frac = (count / max_count) if max_count > 0 else 0.0
    frac = max(0.0, min(1.0, frac))
    lo, hi = 0xF0, 0x44
    v = int(round(lo + (hi - lo) * frac))
    return f"#{v:02X}{v:02X}{v:02X}"


# --- Idiom: scatter_plot — per-trace dotted chart (scan for deviating traces) --

def task28_scatter_plot(tdf, output_dir):
    out = os.path.join(output_dir, "task28_scatter_plot.svg")
    if tdf.empty:
        render_empty_state_svg(out, "Scan Traces for Deviations", "No traces.")
        return
    x = tdf["trace_index"].to_numpy()
    y = tdf["n_dev"].to_numpy(dtype=float)
    clean = y == 0
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.scatter(x[clean], y[clean], c="#CCCCCC", s=8, alpha=0.45, linewidths=0,
               label="conformant")
    ax.scatter(x[~clean], y[~clean], c="#444444", s=10, alpha=0.5, linewidths=0,
               label="has deviations")
    ax.set_xlabel("Trace (log order)", fontsize=FONT_LABEL)
    ax.set_ylabel("Deviating steps per trace", fontsize=FONT_LABEL)
    ax.set_title("Scan Traces for Deviations (each point = one trace)", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, loc="upper left",
              bbox_to_anchor=(1.01, 1), borderaxespad=0, markerscale=2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, out)


# --- Idiom: boxplot — deviations-per-trace distribution (find outliers) -------

def task28_boxplot(tdf, output_dir):
    out = os.path.join(output_dir, "task28_boxplot.svg")
    if tdf.empty:
        render_empty_state_svg(out, "Deviations per Trace", "No traces.")
        return
    data = [tdf["n_dev"].to_numpy(dtype=float)]
    vmax = float(data[0].max()) if data[0].size else 1.0
    fig, ax = plt.subplots(figsize=(5.0, 6))
    draw_grouped_box_plot(ax, data, ["All traces"], ["#999999"],
                          ylabel="Deviating steps per trace", ylim=(-0.3, vmax + 1))
    ax.set_title("Deviations per Trace — spot the outliers", fontsize=FONT_TITLE)
    fig.tight_layout()
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
              title="Deviation type", frameon=False, fontsize=FONT_ANNOT - 1,
              title_fontsize=FONT_ANNOT, loc="upper left",
              bbox_to_anchor=(1.01, 1), borderaxespad=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout()
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
    ax.legend(frameon=False, fontsize=FONT_ANNOT, title="Deviation type", title_fontsize=FONT_ANNOT,
              loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout()
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
                     xlabel="Deviation Type", cbar_label="Count", cell_fmt="{:.0f}")
    ax.set_title(f"Explore: Activity × Deviation Type (top-{len(top_acts)})", fontsize=FONT_TITLE)
    fig.tight_layout()
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
    fig.tight_layout()
    save_svg(fig, out)


# --- Idiom: table_bar_chart — pattern table + frequency bars -----------------

def task28_table_bar_chart(df, output_dir):
    out = os.path.join(output_dir, "task28_table_bar_chart.svg")
    if df.empty:
        render_empty_state_svg(out, "Deviation Patterns", "No deviations found.")
        return
    top = df.head(TOP_N)
    patterns = top["pattern"].tolist()
    counts = top["count"].to_numpy(dtype=float)
    colors = [_move_color(m) for m in top["move_type"]]

    fig_h = max(4.8, 1.3 + len(top) * 0.5)
    fig = plt.figure(figsize=(16, fig_h))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], wspace=0.45)
    ax_tbl = fig.add_subplot(gs[0]); ax_tbl.axis("off")
    cell_text = [[r["pattern"], r["move_type"], str(int(r["count"])), f"{r['pct']:.1f}%"]
                 for _, r in top.iterrows()]
    n_rows = len(cell_text) + 1
    tbl_frac = min(0.86, 0.55 * n_rows / fig_h)
    make_table(ax_tbl, cell_text=cell_text,
               col_labels=["Deviation Pattern", "Deviation Type", "Count", "% of All"],
               bbox=[0.01, max(0.04, 0.86 - tbl_frac), 0.98, tbl_frac],
               col_widths=[0.46, 0.26, 0.14, 0.14], font_size=9, scale_xy=(1, 1.4))
    ax_tbl.set_title(f"Top-{len(top)} Deviation Patterns", fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(patterns))
    ax_bar.barh(y, counts, color=colors, edgecolor="white", linewidth=0.6, height=0.62)
    for yi, c in zip(y, counts):
        ax_bar.text(c, yi, f" {int(c)}", va="center", ha="left",
                    fontsize=FONT_ANNOT - 1, color="#444444")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels([_wrap_pat(p) for p in patterns], fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Observed count", fontsize=FONT_LABEL)
    ax_bar.set_xlim(0, counts.max() * 1.15)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax_bar.set_axisbelow(True)
    ax_bar.set_title("Frequency", fontsize=FONT_TITLE, pad=10)
    fig.tight_layout()
    save_svg(fig, out)


# --- Idiom: network_diagram — deviation co-occurrence (explore relations) ----

def task28_network_diagram(alignments, df, output_dir):
    out = os.path.join(output_dir, "task28_network_diagram.svg")
    if df.empty:
        render_empty_state_svg(out, "Deviation Co-occurrence", "No deviations found.")
        return
    try:
        import networkx as nx
    except ImportError:
        render_empty_state_svg(out, "Deviation Co-occurrence",
                               "networkx not installed.")
        return

    top = df.head(TOP_N)["pattern"].tolist()
    top_set = set(top)
    from collections import Counter
    cooccur = Counter()
    for res in alignments:
        steps = alignment_pairs_to_rows(res.get("alignment") or [])
        pats = sorted({f"{(s['model_move'] if s['moveType']=='Model Move' else s['log_move'])} ({s['moveType']})"
                       for s in steps if s["moveType"] != "Synchronous Move"} & top_set)
        for a in range(len(pats)):
            for b in range(a + 1, len(pats)):
                cooccur[(pats[a], pats[b])] += 1
    pairs = [(a, b, c) for (a, b), c in cooccur.items() if c > 0]
    if not pairs:
        render_empty_state_svg(out, "Deviation Co-occurrence",
                               "No deviation patterns co-occur in the same trace.")
        return

    freq = dict(zip(df["pattern"], df["count"]))
    G = nx.Graph()
    for p in top:
        G.add_node(p, freq=int(freq.get(p, 1)))
    for a, b, c in pairs:
        G.add_edge(a, b, weight=c)
    pos = nx.circular_layout(G, scale=2.0) if G.number_of_nodes() <= 8 \
        else nx.spring_layout(G, seed=42, k=3.0)

    nodes = list(G.nodes)
    fr = np.array([G.nodes[n]["freq"] for n in nodes], dtype=float)
    node_sz = (fr / fr.max() * 1500 + 350).tolist()
    edges = list(G.edges()); w = [G[u][v]["weight"] for u, v in edges]
    mw = max(w) if w else 1
    ew = [1.5 + (x / mw) * 5 for x in w]
    ec = [plt.cm.Greys(0.25 + 0.55 * x / mw) for x in w]

    def _ncolor(p):
        return _move_color("Model Move" if "Model Move" in p
                           else "Log Move" if "Log Move" in p else "Mismatch Move")

    fig, ax = plt.subplots(figsize=(13, 8.5))
    nx.draw_networkx_edges(G, pos, ax=ax, width=ew, edge_color=ec, alpha=0.85, edgelist=edges)
    nx.draw_networkx_nodes(G, pos, nodelist=nodes, ax=ax, node_size=node_sz,
                           node_color=[_ncolor(n) for n in nodes], alpha=0.92,
                           linewidths=0.8, edgecolors="white")
    for node, (xx, yy) in pos.items():
        ax.annotate(node.replace(" (", "\n("), xy=(xx, yy), xytext=(0, -20),
                    textcoords="offset points", ha="center", va="top",
                    fontsize=max(FONT_ANNOT - 1, 6), color="#222222",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#dddddd", alpha=0.92))
    ax.legend(handles=[mpatches.Patch(color=_move_color(m), label=m) for m in _present_move_types(df)],
              loc="lower right", fontsize=FONT_ANNOT, frameon=True, framealpha=0.95)
    ax.set_title("Explore: Deviation Co-occurrence Network\n"
                 "(node size = frequency · edge width = traces sharing both)", fontsize=FONT_TITLE)
    ax.axis("off")
    fig.tight_layout()
    save_svg(fig, out)




# --- Idiom: flow_chart_elaborate_table — BPMN shaded by frequency + table ----

_BPMN_LEGEND = [
    ("#F0F0F0", "#777777", 1.0, "No / few deviations"),
    ("#9A9A9A", "#777777", 1.0, "Some deviations"),
    ("#444444", "#777777", 1.0, "Most deviations"),
]


def _node_style_fn(act_freq, max_count):
    def style(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task" and name in act_freq:
            fill = _freq_shade(act_freq[name], max_count)
            tc = "white" if int(fill[1:3], 16) < 0x99 else "#222222"
            return fill, "#777777", 1.5, tc
        return "white", "#888888", 2, "#333333"
    return style


def task28_flow_chart_elaborate_table(df, model_path, output_dir):
    out = os.path.join(output_dir, "task28_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Deviations on the Model", "No BPMN model available.")
        return
    if df.empty:
        render_empty_state_svg(out, "Deviations on the Model", "No deviations found.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"      task28: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Deviations on the Model", "Could not parse the BPMN model.")
        return
    act_freq = _activity_freq(df)
    max_count = max(act_freq.values(), default=1)
    top = df.head(TOP_N)
    table_cols = ["Deviation Pattern", "Activity", "Deviation Type", "Count"]
    table_rows = [[r["pattern"], r["activity"], r["move_type"], str(int(r["count"]))]
                  for _, r in top.iterrows()] or [["No deviations.", "", "", ""]]
    panels = [{"parsed": parsed, "node_style_fn": _node_style_fn(act_freq, max_count),
               "subtitle": "Activity shade = deviation frequency · explore where the log differs"}]
    compose_bpmn_panels(panels, out,
                        title="Explore Deviations on the Model — with Pattern Table",
                        legend_items=_BPMN_LEGEND, table_rows=table_rows, table_cols=table_cols)


# ===========================================================================
# Public entry point
# ===========================================================================

_LOG_FNAMES_TITLES = [
    ("task28_bar_chart.svg",                  "Where Does the Log Deviate?"),
    ("task28_stacked_bar.svg",                "Deviations per Activity"),
    ("task28_scatter_plot.svg",               "Scan Traces for Deviations"),
    ("task28_boxplot.svg",                    "Deviations per Trace"),
    ("task28_matrix.svg",                     "Activity × Deviation Type"),
    ("task28_heatmap.svg",                    "Deviation Heatmap"),
    ("task28_table_bar_chart.svg",            "Deviation Patterns"),
    ("task28_network_diagram.svg",            "Deviation Co-occurrence"),
    ("task28_flow_chart_elaborate_table.svg", "Deviations on the Model"),
]


def generate(alignments, model_path: str, output_dir: str):
    """Generate all Task 28 SVGs into output_dir (trace-level deep-dive + log-level
    exploratory overview)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 28 visualizations ---")

    # Trace-level deep-dive (representative trace)
    ctx = build_task28_context(alignments)
    if ctx is not None:
        logger.info(f"      Using {ctx['trace_label']} (log index {ctx['trace_index']}, "
                    f"fitness={ctx['fitness']:.4f})")
        task28_alignment_table(ctx, output_dir)
        task28_flow_chart_basic(ctx, output_dir)
        task28_flow_chart_and_table(ctx, output_dir)
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
    task28_scatter_plot(tdf, output_dir)
    task28_boxplot(tdf, output_dir)
    task28_matrix(df, output_dir)
    task28_heatmap(df, output_dir)
    task28_table_bar_chart(df, output_dir)
    task28_network_diagram(alignments, df, output_dir)
    task28_flow_chart_elaborate_table(df, model_path, output_dir)
