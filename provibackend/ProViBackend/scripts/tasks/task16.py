"""
tasks/task16.py – Task 16: Violation pattern annotation across the log.

Goal: Explain · Means: Annotate · Characteristics: Reasons for guideline violations
"What is the reason for guideline violations? Preexisting knowledge about
the reason is taken into account."

All idioms show log-level violation patterns (per-activity counts, type
distribution, representative trace) so the analyst can match observed
patterns to their prior knowledge. Dataset-agnostic; no domain labels.

Public API:
    generate(log, fitness_df, alignments, output_dir, model_path=None)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "table", "bar_chart", "scatter_plot",
    "flow_chart_table", "flow_chart_elaborate", "flow_chart_elaborate_table",
    "table_bar_chart", "parallel_sets",
]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets,
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    alignment_pairs_to_rows,
    draw_chevron_strip, chevron_nodes_from_alignment_rows, chevron_figure_width,
    render_empty_state_svg,
    GREY_MED, GREY_DARK, GREY_LIGHT, GREY_LIGHTER,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIT_THRESHOLD = 0.8
_MOVE_TYPES    = ["Model Move", "Log Move", "Mismatch Move"]
_MOVE_COLOR    = {"Model Move": GREY_MED, "Log Move": GREY_DARK, "Mismatch Move": GREY_LIGHT}
_MISSING       = {"-", "None", "(skip)", ""}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _build_violation_df(alignments) -> pd.DataFrame:
    rows = []
    for result in alignments:
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            mt = step["moveType"]
            if mt == "Synchronous Move":
                continue
            activity = step["model_move"] if mt == "Model Move" else step["log_move"]
            if not activity or str(activity) in _MISSING:
                continue
            rows.append({"activity": str(activity), "move_type": mt})
    if not rows:
        return pd.DataFrame(columns=["activity", "move_type", "count"])
    df = pd.DataFrame(rows)
    return (df.groupby(["activity", "move_type"])
              .size()
              .reset_index(name="count")
              .sort_values("count", ascending=False))


def _activity_total_violations(viol_df: pd.DataFrame) -> dict:
    if viol_df.empty:
        return {}
    return dict(viol_df.groupby("activity")["count"].sum())


def _per_trace_violation_counts(alignments, fitness_df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with columns: fitness, viol_count, conformant."""
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    records = []
    for i, result in enumerate(alignments):
        cnt = sum(
            1 for step in alignment_pairs_to_rows(result.get("alignment", []))
            if step["moveType"] != "Synchronous Move"
        )
        fit = float(fits[i]) if i < len(fits) else 0.0
        records.append({"fitness": fit, "viol_count": cnt,
                        "conformant": fit >= _FIT_THRESHOLD})
    return pd.DataFrame(records)


def _pick_representative_trace(alignments) -> int:
    """Return index of trace with highest alignment cost."""
    best_idx, best_cost = 0, -1.0
    for i, result in enumerate(alignments):
        try:
            c = float(result.get("cost") or 0)
        except (TypeError, ValueError):
            c = 0.0
        if c > best_cost:
            best_cost, best_idx = c, i
    return best_idx


def _activity_label(row) -> str:
    mt = row["moveType"]
    if mt == "Model Move":
        return str(row["model_move"])
    lm = str(row["log_move"])
    return lm if lm not in _MISSING else str(row["model_move"])


def _violation_shade(rate: float) -> str:
    rate = max(0.0, min(1.0, rate))
    lo, hi = 0xF0, 0x44
    v = int(round(lo + (hi - lo) * rate))
    return f"#{v:02X}{v:02X}{v:02X}"


# ---------------------------------------------------------------------------
# Overall stats (footer for all matplotlib figures)
# ---------------------------------------------------------------------------

def _overall_stats(fitness_df: pd.DataFrame, viol_df: pd.DataFrame) -> dict:
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    n = len(fits)
    return {
        "n":           n,
        "mean":        float(fits.mean()) if n else 0.0,
        "pct_conform": float((fits >= _FIT_THRESHOLD).sum() / n * 100) if n else 0.0,
        "total_viol":  int(viol_df["count"].sum()) if not viol_df.empty else 0,
    }


def _stats_line(s: dict) -> str:
    return (f"n = {s['n']}   mean fitness = {s['mean']:.3f}   "
            f"conformant = {s['pct_conform']:.1f}%   "
            f"total violations = {s['total_viol']}")


def _add_stats_footer(fig, s: dict):
    fig.text(0.5, 0.01, _stats_line(s), ha="center", va="bottom",
             fontsize=FONT_ANNOT - 1.5, color="#888888",
             transform=fig.transFigure)


# ---------------------------------------------------------------------------
# Idiom 1: table — per-activity × move-type count matrix
# ---------------------------------------------------------------------------

def task16_table(viol_df, s, output_dir):
    out_path = os.path.join(output_dir, "task16_table.svg")
    if viol_df.empty:
        render_empty_state_svg(out_path, "Violations by Activity", "No violations found.")
        return

    act_totals = _activity_total_violations(viol_df)
    top_acts = sorted(act_totals, key=lambda a: -act_totals[a])[:20]

    pivot = viol_df.pivot_table(
        index="activity", columns="move_type", values="count",
        aggfunc="sum", fill_value=0,
    )
    cols_present = [mt for mt in _MOVE_TYPES if mt in pivot.columns]

    cell_text = []
    for act in top_acts:
        row_data = [act]
        total = 0
        for mt in cols_present:
            v = int(pivot.loc[act, mt]) if act in pivot.index and mt in pivot.columns else 0
            row_data.append(str(v))
            total += v
        row_data.append(str(total))
        cell_text.append(row_data)

    n_mt = len(cols_present)
    mt_w = round(0.56 / max(n_mt + 1, 1), 2)
    col_widths = [0.40] + [mt_w] * n_mt + [mt_w]

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.48)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Activity"] + cols_present + ["Total"],
        bbox=[0.02, 0.08, 0.96, 0.82],
        col_widths=col_widths,
        font_size=9.5,
        scale_xy=(1, 1.35),
    )
    ax.set_title("Violations by Activity", fontsize=FONT_TITLE, pad=10)
    _add_stats_footer(fig, s)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 2: bar_chart — stacked horizontal bar by activity (top N)
# ---------------------------------------------------------------------------

def task16_bar_chart(viol_df, s, output_dir):
    out_path = os.path.join(output_dir, "task16_bar_chart.svg")
    if viol_df.empty:
        render_empty_state_svg(out_path, "Violations by Activity", "No violations found.")
        return

    act_totals = _activity_total_violations(viol_df)
    top_acts = sorted(act_totals, key=lambda a: -act_totals[a])[:15]

    pivot = viol_df[viol_df["activity"].isin(top_acts)].pivot_table(
        index="activity", columns="move_type", values="count",
        aggfunc="sum", fill_value=0,
    ).reindex(top_acts).fillna(0)
    cols_present = [mt for mt in _MOVE_TYPES if mt in pivot.columns]

    fig_h = max(5, len(top_acts) * 0.48 + 2)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    y = np.arange(len(top_acts))
    bottoms = np.zeros(len(top_acts))
    for mt in cols_present:
        vals = pivot[mt].to_numpy(dtype=float)
        ax.barh(y, vals, left=bottoms, color=_MOVE_COLOR.get(mt, "#AAAAAA"),
                label=mt, edgecolor="white", linewidth=0.5, height=0.6)
        bottoms += vals

    ax.set_yticks(y)
    ax.set_yticklabels(top_acts, fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Violation Count", fontsize=FONT_LABEL)
    ax.set_title("Top Activities by Violation Count", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    _add_stats_footer(fig, s)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 3: scatter_plot — per-trace: fitness × violation count
# ---------------------------------------------------------------------------

def task16_scatter_plot(trace_df, s, output_dir):
    out_path = os.path.join(output_dir, "task16_scatter_plot.svg")
    if trace_df.empty:
        render_empty_state_svg(out_path, "Fitness vs. Violation Count", "No data.")
        return

    colors = np.where(trace_df["conformant"], GREY_LIGHTER, GREY_DARK)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(trace_df["fitness"], trace_df["viol_count"],
               c=colors, s=10, alpha=0.45, linewidths=0)

    legend_handles = [
        mpatches.Patch(facecolor=GREY_LIGHTER, label=f"Conformant (≥ {_FIT_THRESHOLD})"),
        mpatches.Patch(facecolor=GREY_DARK,   label=f"Non-conformant (< {_FIT_THRESHOLD})"),
    ]
    ax.legend(handles=legend_handles, frameon=False, fontsize=FONT_ANNOT,
              loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
    ax.set_xlabel("Trace Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylabel("Violation Steps per Trace", fontsize=FONT_LABEL)
    ax.set_title("Fitness vs. Violation Count per Trace", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    _add_stats_footer(fig, s)
    fig.tight_layout(rect=[0, 0.10, 1, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 4: flow_chart_table — chevron strip + annotation table (representative trace)
# ---------------------------------------------------------------------------

def task16_flow_chart_table(alignments, fitness_df, s, output_dir):
    out_path = os.path.join(output_dir, "task16_flow_chart_and_table.svg")
    if not alignments:
        render_empty_state_svg(out_path, "Trace Flow & Violations", "No alignment data.")
        return

    idx = _pick_representative_trace(alignments)
    result = alignments[idx]
    rows = alignment_pairs_to_rows(result.get("alignment", []))
    if not rows:
        render_empty_state_svg(out_path, "Trace Flow & Violations", "No alignment steps.")
        return

    fits = fitness_df["fitness"].to_numpy(dtype=float)
    trace_fit = float(fits[idx]) if idx < len(fits) else float(result.get("fitness", 0.0))
    violations = [r for r in rows if r["moveType"] != "Synchronous Move"]
    nodes = chevron_nodes_from_alignment_rows(rows)

    cell_text = [
        [str(r["step"]), _activity_label(r), r["moveType"]]
        for r in violations
    ] if violations else [["—", "No violations", "—"]]

    n_rows = len(cell_text) + 1
    fig_w   = max(18.0, chevron_figure_width(nodes))
    tbl_h   = max(2.2, 0.36 * n_rows)
    chev_h  = 2.2
    fig_h   = tbl_h + chev_h + 1.4

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
        bbox=[0.01, 0.04, 0.98, 0.82],
        col_widths=[0.10, 0.50, 0.40],
        font_size=9,
        scale_xy=(1, 1.5),
    )
    ax_tbl.set_title("Violation Steps", fontsize=FONT_TITLE, pad=7)

    legend_handles = [
        mpatches.Patch(facecolor=GREY_LIGHTER,  label="Synchronous Move"),
        mpatches.Patch(facecolor=GREY_MED,   label="Model Move"),
        mpatches.Patch(facecolor=GREY_DARK,    label="Log Move"),
        mpatches.Patch(facecolor=GREY_LIGHT, label="Mismatch Move"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               bbox_to_anchor=(0.5, 0.01), ncol=4,
               fontsize=FONT_ANNOT, frameon=True, fancybox=False,
               edgecolor="#cccccc")
    fig.suptitle(
        f"Representative Trace (Trace {idx + 1})   fitness = {trace_fit:.4f}   "
        f"violations = {len(violations)}",
        fontsize=FONT_TITLE, y=0.99,
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.97])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 5: flow_chart_elaborate — BPMN annotated with violation frequency
# ---------------------------------------------------------------------------

def task16_flow_chart_elaborate(act_totals, s, model_path, output_dir):
    out_path = os.path.join(output_dir, "task16_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out_path, "Violations on Process Model",
                               "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task16: BPMN parse failed: {e}")
        render_empty_state_svg(out_path, "Violations on Process Model",
                               "Could not parse the BPMN model.")
        return

    max_v = max(act_totals.values()) if act_totals else 0

    def node_style_fn(eid, elem):
        kind = elem.get("kind", "task")
        name = elem.get("name", "")
        if kind == "task":
            rate = (act_totals.get(name, 0) / max_v) if max_v else 0.0
            fill = _violation_shade(rate)
            tc = "white" if int(fill[1:3], 16) < 0x99 else "#222222"
            return fill, "#777777", 1.2, tc
        if kind in {"exclusiveGateway", "parallelGateway"}:
            return "#FFFFFF", "#777777", 1.2, "#333333"
        return "#EFEFEF", "#777777", 1.5, "#333333"

    legend_items = [
        ("#F0F0F0", "#777777", 1.0, "Few / no violations"),
        ("#9A9A9A", "#777777", 1.0, "Some violations"),
        ("#444444", "#777777", 1.0, "Most violations"),
    ]
    render_bpmn_annotated(
        parsed, out_path,
        title="Violations on the Process Model",
        summary=("Activity shade: lighter = fewer violations · darker = more violations"
                 f"   |   {_stats_line(s)}"),
        node_style_fn=node_style_fn,
        legend_items=legend_items,
        legend_center=True,
    )


# ---------------------------------------------------------------------------
# Idiom 6: flow_chart_elaborate_table — BPMN + top-activity table
# ---------------------------------------------------------------------------

def task16_flow_chart_elaborate_table(act_totals, viol_df, s, model_path, output_dir):
    out_path = os.path.join(output_dir, "task16_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out_path, "Violations on Process Model & Summary",
                               "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task16: BPMN parse failed: {e}")
        render_empty_state_svg(out_path, "Violations on Process Model & Summary",
                               "Could not parse the BPMN model.")
        return

    max_v = max(act_totals.values()) if act_totals else 0

    def node_style_fn(eid, elem):
        kind = elem.get("kind", "task")
        name = elem.get("name", "")
        if kind == "task":
            rate = (act_totals.get(name, 0) / max_v) if max_v else 0.0
            fill = _violation_shade(rate)
            tc = "white" if int(fill[1:3], 16) < 0x99 else "#222222"
            return fill, "#777777", 1.2, tc
        if kind in {"exclusiveGateway", "parallelGateway"}:
            return "#FFFFFF", "#777777", 1.2, "#333333"
        return "#EFEFEF", "#777777", 1.5, "#333333"

    legend_items = [
        ("#F0F0F0", "#777777", 1.0, "Few / no violations"),
        ("#9A9A9A", "#777777", 1.0, "Some violations"),
        ("#444444", "#777777", 1.0, "Most violations"),
    ]

    top_acts = sorted(act_totals, key=lambda a: -act_totals[a])[:8]

    # Build per-move-type counts for top activities
    pivot = viol_df[viol_df["activity"].isin(top_acts)].pivot_table(
        index="activity", columns="move_type", values="count",
        aggfunc="sum", fill_value=0,
    )
    cols_present = [mt for mt in _MOVE_TYPES if mt in pivot.columns]

    table_cols = ["Activity"] + cols_present + ["Total"]
    table_rows = []
    for act in top_acts:
        row_data = [act]
        total = 0
        for mt in cols_present:
            v = int(pivot.loc[act, mt]) if act in pivot.index and mt in pivot.columns else 0
            row_data.append(str(v))
            total += v
        row_data.append(str(total))
        table_rows.append(row_data)

    panels = [{
        "parsed": parsed,
        "node_style_fn": node_style_fn,
        "subtitle": "Activity shade: lighter = fewer violations · darker = more violations",
    }]
    compose_bpmn_panels(
        panels, out_path,
        title=f"Violations on the Process Model   |   {_stats_line(s)}",
        legend_items=legend_items,
        table_rows=table_rows, table_cols=table_cols,
        legend_below_panels=True, legend_center=True,
    )


# ---------------------------------------------------------------------------
# Idiom 8: table_bar_chart — activity table (left) + per-activity bar (right)
# ---------------------------------------------------------------------------

def task16_table_bar_chart(viol_df, s, output_dir):
    out_path = os.path.join(output_dir, "task16_table_bar_chart.svg")
    if viol_df.empty:
        render_empty_state_svg(out_path, "Activity Violation Summary", "No violations found.")
        return

    act_totals = _activity_total_violations(viol_df)
    top_acts = sorted(act_totals, key=lambda a: -act_totals[a])[:10]

    pivot = viol_df[viol_df["activity"].isin(top_acts)].pivot_table(
        index="activity", columns="move_type", values="count",
        aggfunc="sum", fill_value=0,
    ).reindex(top_acts).fillna(0)
    cols_present = [mt for mt in _MOVE_TYPES if mt in pivot.columns]

    fig = plt.figure(figsize=(16, 6.5), layout="constrained")
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], figure=fig)
    ax_tbl = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    # Left: table
    ax_tbl.axis("off")
    cell_text = []
    for act in top_acts:
        row_data = [act]
        for mt in cols_present:
            v = int(pivot.loc[act, mt]) if act in pivot.index and mt in pivot.columns else 0
            row_data.append(str(v))
        row_data.append(str(act_totals[act]))
        cell_text.append(row_data)

    n_mt = len(cols_present)
    mt_w = round(0.50 / max(n_mt + 1, 1), 2)
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Activity"] + cols_present + ["Total"],
        bbox=[0.01, 0.08, 0.98, 0.80],
        col_widths=[0.50] + [mt_w] * n_mt + [mt_w],
        font_size=9,
        scale_xy=(1, 1.4),
    )
    ax_tbl.set_title("Activity Violation Breakdown", fontsize=FONT_TITLE, pad=10)

    # Right: horizontal bar (total violations per activity, stacked by move type)
    y = np.arange(len(top_acts))
    bottoms = np.zeros(len(top_acts))
    for mt in cols_present:
        vals = np.array([
            int(pivot.loc[act, mt]) if act in pivot.index and mt in pivot.columns else 0
            for act in top_acts
        ], dtype=float)
        ax_bar.barh(y, vals, left=bottoms,
                    color=_MOVE_COLOR.get(mt, "#AAAAAA"),
                    label=mt, edgecolor="white", linewidth=0.4, height=0.55)
        bottoms += vals

    act_labels = [a if len(a) <= 16 else a[:14] + "…" for a in top_acts]
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(act_labels, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Violation Count", fontsize=FONT_LABEL)
    ax_bar.set_title("Violation Count by Activity", fontsize=FONT_TITLE, pad=10)
    ax_bar.legend(frameon=False, fontsize=FONT_ANNOT - 1,
                  loc="lower right", title="Move Type", title_fontsize=FONT_ANNOT - 1)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)

    _add_stats_footer(fig, s)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 9: parallel_sets — activity → move type flows
# ---------------------------------------------------------------------------

def task16_parallel_sets(viol_df, s, output_dir):
    out_path = os.path.join(output_dir, "task16_parallel_sets.svg")
    if viol_df.empty:
        render_empty_state_svg(out_path, "Activity vs. Move Type", "No violations found.")
        return

    act_totals = _activity_total_violations(viol_df)
    top_acts = sorted(act_totals, key=lambda a: -act_totals[a])[:8]
    present_mts = [mt for mt in _MOVE_TYPES if mt in viol_df["move_type"].values]

    if not top_acts or not present_mts:
        render_empty_state_svg(out_path, "Activity vs. Move Type", "No data.")
        return

    # Matrix: (n_activities × n_move_types)
    pivot = viol_df[viol_df["activity"].isin(top_acts)].pivot_table(
        index="activity", columns="move_type", values="count",
        aggfunc="sum", fill_value=0,
    ).reindex(top_acts).fillna(0)

    keep_mts = [mt for mt in present_mts if mt in pivot.columns and pivot[mt].sum() > 0]
    if not keep_mts:
        render_empty_state_svg(out_path, "Activity vs. Move Type", "No data.")
        return

    matrix = np.array([
        [int(pivot.loc[act, mt]) if act in pivot.index and mt in pivot.columns else 0
         for mt in keep_mts]
        for act in top_acts
    ], dtype=int)

    left_labels = [
        f"{a[:14] + '…' if len(a) > 14 else a}\n(n={act_totals[a]})"
        for a in top_acts
    ]
    left_colors  = ["#555555"] * len(top_acts)
    right_labels = keep_mts
    right_colors  = [_MOVE_COLOR.get(mt, "#AAAAAA") for mt in keep_mts]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Activity vs. Move Type", fontsize=FONT_TITLE, pad=12)
    _add_stats_footer(fig, s)
    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_labels,
        matrix=matrix,
        left_colors=left_colors,
        right_colors=right_colors,
        left_title="Activity (top violations)",
        right_title="Move Type",
    )
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task16_table.svg",                      "Violations by Activity"),
    ("task16_bar_chart.svg",                  "Top Activities by Violation Count"),
    ("task16_scatter_plot.svg",               "Fitness vs. Violation Count per Trace"),
    ("task16_flow_chart_and_table.svg",       "Representative Trace Flow & Violations"),
    ("task16_flow_chart_elaborate.svg",       "Violations on the Process Model"),
    ("task16_flow_chart_elaborate_table.svg", "Violations on the Process Model & Summary"),
    ("task16_tree.svg",                       "Violation Hierarchy"),
    ("task16_table_bar_chart.svg",            "Activity Violation Summary"),
    ("task16_parallel_sets.svg",              "Activity vs. Move Type"),
]


def generate(log, fitness_df, alignments, output_dir: str,
             model_path: str = None, compare_attribute: str = "AMOUNT_REQ"):
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 16 visualizations ---")

    viol_df   = _build_violation_df(alignments)
    act_totals = _activity_total_violations(viol_df)
    trace_df  = _per_trace_violation_counts(alignments, fitness_df)
    s         = _overall_stats(fitness_df, viol_df)
    logger.info(f"      -> {_stats_line(s)}")

    task16_table(viol_df, s, output_dir)
    task16_bar_chart(viol_df, s, output_dir)
    task16_scatter_plot(trace_df, s, output_dir)
    task16_flow_chart_table(alignments, fitness_df, s, output_dir)
    task16_flow_chart_elaborate(act_totals, s, model_path, output_dir)
    task16_flow_chart_elaborate_table(act_totals, viol_df, s, model_path, output_dir)
    task16_table_bar_chart(viol_df, s, output_dir)
    task16_parallel_sets(viol_df, s, output_dir)
