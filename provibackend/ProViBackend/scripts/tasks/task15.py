"""
tasks/task15.py – Task 15: Overall process conformance annotation.

Goal: Explain · Means: Annotate · Characteristics: Reasons for process conformance
"How can the overall process conformance be explained? Requires prior knowledge
of potential explanations."

All idioms show log-level aggregate conformance (fitness distribution,
per-activity violation counts) so the analyst can match observed patterns
to their prior knowledge. No sublog splitting — the focus is the overall picture.

Public API:
    generate(log, fitness_df, alignments, output_dir, model_path=None)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "table", "bar_chart", "scatter_plot",
    "flow_chart_elaborate", "flow_chart_elaborate_table",
    "table_bar_chart", "parallel_sets",
]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets,
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    alignment_pairs_to_rows,
    render_empty_state_svg,
    GREY_MED, GREY_DARK, GREY_LIGHT, GREY_LIGHTER,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIT_THRESHOLD = 0.8

_MOVE_TYPES = ["Model Move", "Log Move", "Mismatch Move"]
_MOVE_COLOR = {"Model Move": GREY_MED, "Log Move": GREY_DARK, "Mismatch Move": GREY_LIGHT}

_FITNESS_BANDS = [
    ("0.00–0.25", 0.00, 0.25, "#333333", "white"),
    ("0.25–0.50", 0.25, 0.50, "#777777", "white"),
    ("0.50–0.75", 0.50, 0.75, "#AAAAAA", "#333333"),
    ("0.75–1.00", 0.75, 1.01, "#D9D9D9", "#333333"),
]

_MISSING = {"-", "None", "(skip)", ""}


# ---------------------------------------------------------------------------
# Overall stats helper
# ---------------------------------------------------------------------------

def _overall_stats(fitness_df: pd.DataFrame, viol_df: pd.DataFrame) -> dict:
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    n = len(fits)
    mean_fit = float(fits.mean()) if n else 0.0
    pct_conf = float((fits >= _FIT_THRESHOLD).sum() / n * 100) if n else 0.0
    total_viol = int(viol_df["count"].sum()) if not viol_df.empty else 0
    return {"n": n, "mean": mean_fit, "pct_conform": pct_conf, "total_viol": total_viol}


def _stats_line(s: dict) -> str:
    return (f"n = {s['n']}   mean fitness = {s['mean']:.3f}   "
            f"conformant = {s['pct_conform']:.1f}%   "
            f"total violations = {s['total_viol']}")


def _add_stats_footer(fig, s: dict):
    """Add overall stats as a small grey line at the bottom of a matplotlib figure."""
    fig.text(0.5, 0.01, _stats_line(s), ha="center", va="bottom",
             fontsize=FONT_ANNOT - 1.5, color="#888888",
             transform=fig.transFigure)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _build_violation_df(alignments) -> pd.DataFrame:
    """Return DataFrame: activity, move_type, count — aggregated across all traces."""
    rows = []
    for result in alignments:
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            mt = step["moveType"]
            if mt == "Synchronous Move":
                continue
            activity = (step["model_move"] if mt == "Model Move" else step["log_move"])
            if not activity or str(activity) in _MISSING:
                continue
            rows.append({"activity": str(activity), "move_type": mt})
    if not rows:
        return pd.DataFrame(columns=["activity", "move_type", "count"])
    df = pd.DataFrame(rows)
    agg = (df.groupby(["activity", "move_type"])
             .size()
             .reset_index(name="count")
             .sort_values("count", ascending=False))
    return agg


def _activity_total_violations(viol_df: pd.DataFrame) -> dict:
    """activity -> total violation count across all move types."""
    if viol_df.empty:
        return {}
    return dict(viol_df.groupby("activity")["count"].sum())


def _fitness_band_counts(fitness_df: pd.DataFrame) -> list:
    """Return list of (label, count) for each fitness band."""
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    result = []
    for label, lo, hi, _, _ in _FITNESS_BANDS:
        n = int(((fits >= lo) & (fits < hi)).sum())
        result.append((label, n))
    return result


def _violation_shade(rate: float) -> str:
    rate = max(0.0, min(1.0, rate))
    lo, hi = 0xF0, 0x44
    v = int(round(lo + (hi - lo) * rate))
    return f"#{v:02X}{v:02X}{v:02X}"


# ---------------------------------------------------------------------------
# Idiom 1: table — per-activity violation counts by move type
# ---------------------------------------------------------------------------

def task15_table(viol_df, s, output_dir):
    out_path = os.path.join(output_dir, "task15_table.svg")
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

    col_labels = ["Activity"] + cols_present + ["Total"]
    n_mt = len(cols_present)
    base_w = 0.40
    mt_w = round((0.56 / max(n_mt + 1, 1)), 2)
    col_widths = [base_w] + [mt_w] * n_mt + [mt_w]

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.48)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.02, 0.06, 0.96, 0.84],
        col_widths=col_widths,
        font_size=9.5,
        scale_xy=(1, 1.35),
    )
    ax.set_title("Violations by Activity (log-level aggregate)", fontsize=FONT_TITLE, pad=10)
    _add_stats_footer(fig, s)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 2: bar_chart — total violations per activity (top N)
# ---------------------------------------------------------------------------

def task15_bar_chart(viol_df, s, output_dir):
    out_path = os.path.join(output_dir, "task15_bar_chart.svg")
    if viol_df.empty:
        render_empty_state_svg(out_path, "Violations by Activity", "No violations found.")
        return

    act_totals = _activity_total_violations(viol_df)
    top_acts = sorted(act_totals, key=lambda a: -act_totals[a])[:15]

    pivot = viol_df[viol_df["activity"].isin(top_acts)].pivot_table(
        index="activity", columns="move_type", values="count",
        aggfunc="sum", fill_value=0,
    )
    pivot = pivot.reindex(top_acts).fillna(0)
    cols_present = [mt for mt in _MOVE_TYPES if mt in pivot.columns]

    fig_h = max(5, len(top_acts) * 0.45 + 2)
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
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    _add_stats_footer(fig, s)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 3: scatter_plot — per-trace fitness (sorted by fitness)
# ---------------------------------------------------------------------------

def task15_scatter_plot(fitness_df, s, output_dir):
    out_path = os.path.join(output_dir, "task15_scatter_plot.svg")
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    if len(fits) == 0:
        render_empty_state_svg(out_path, "Per-trace Fitness", "No data.")
        return

    sorted_fits = np.sort(fits)
    n = len(sorted_fits)
    x = np.arange(n)

    colors = np.where(sorted_fits >= _FIT_THRESHOLD, GREY_LIGHTER, GREY_DARK)

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.scatter(x, sorted_fits, c=colors, s=6, alpha=0.55, linewidths=0)
    ax.axhline(_FIT_THRESHOLD, color="#555555", linestyle="--",
               linewidth=1.0, zorder=5)
    ax.text(n * 0.01, _FIT_THRESHOLD + 0.02,
            f"threshold = {_FIT_THRESHOLD:.1f}", fontsize=FONT_ANNOT - 1,
            color="#555555")

    n_conf = int((sorted_fits >= _FIT_THRESHOLD).sum())
    ax.text(0.99, 0.96,
            f"mean = {sorted_fits.mean():.3f}   conformant = {n_conf/n*100:.1f}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=FONT_ANNOT, color="#444444")

    ax.set_xlabel("Trace (sorted by fitness)", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Per-trace Fitness Distribution", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    _add_stats_footer(fig, s)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 4: flow_chart_elaborate — BPMN annotated with violation frequency
# ---------------------------------------------------------------------------

def task15_flow_chart_elaborate(act_totals, s, model_path, output_dir):
    out_path = os.path.join(output_dir, "task15_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out_path, "Violations on Process Model",
                               "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task15: BPMN parse failed: {e}")
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
# Idiom 5: flow_chart_elaborate_table — BPMN + top-activity table
# ---------------------------------------------------------------------------

def task15_flow_chart_elaborate_table(act_totals, viol_df, s, model_path, output_dir):
    out_path = os.path.join(output_dir, "task15_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out_path, "Violations on Process Model & Summary",
                               "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task15: BPMN parse failed: {e}")
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
    table_cols = ["Activity", "Total Violations"]
    table_rows = [[a, str(act_totals[a])] for a in top_acts]

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
# Idiom 7: table_bar_chart — violation summary table + fitness band bar
# ---------------------------------------------------------------------------

def task15_table_bar_chart(viol_df, fitness_df, s, output_dir):
    out_path = os.path.join(output_dir, "task15_table_bar_chart.svg")

    band_data = _fitness_band_counts(fitness_df)
    n_total = len(fitness_df)

    fig = plt.figure(figsize=(16, 6), layout="constrained")
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], figure=fig)
    ax_tbl = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    # Left: violation type summary table
    ax_tbl.axis("off")
    mt_summary = []
    for mt in _MOVE_TYPES:
        sub = viol_df[viol_df["move_type"] == mt]
        total = int(sub["count"].sum())
        n_acts = int(sub["activity"].nunique())
        pct = total / viol_df["count"].sum() * 100 if viol_df["count"].sum() > 0 else 0.0
        mt_summary.append([mt, str(total), str(n_acts), f"{pct:.1f}%"])
    if not mt_summary:
        mt_summary = [["—", "0", "0", "0%"]]

    make_table(
        ax_tbl,
        cell_text=mt_summary,
        col_labels=["Move Type", "Total Violations", "Activities Affected", "Share"],
        bbox=[0.02, 0.20, 0.96, 0.65],
        col_widths=[0.40, 0.24, 0.24, 0.12],
        font_size=10,
        scale_xy=(1, 1.5),
    )
    ax_tbl.set_title("Violation Type Summary", fontsize=FONT_TITLE, pad=10)

    # Right: fitness band bar chart
    band_labels = [b[0] for b in band_data]
    band_counts = [b[1] for b in band_data]
    band_colors = [_FITNESS_BANDS[i][3] for i in range(len(band_data))]
    y = np.arange(len(band_labels))
    bars = ax_bar.barh(y, band_counts, color=band_colors,
                       edgecolor="white", linewidth=0.5, height=0.55)
    for bar, cnt in zip(bars, band_counts):
        if cnt > 0:
            pct = cnt / n_total * 100
            ax_bar.text(bar.get_width() + n_total * 0.005,
                        bar.get_y() + bar.get_height() / 2,
                        f"{cnt}  ({pct:.1f}%)", va="center",
                        fontsize=FONT_ANNOT - 1, color="#444444")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(band_labels, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Number of Traces", fontsize=FONT_LABEL)
    ax_bar.set_title("Fitness Band Distribution", fontsize=FONT_TITLE, pad=10)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)

    _add_stats_footer(fig, s)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 8: parallel_sets — fitness band → move type proportion
# ---------------------------------------------------------------------------

def task15_parallel_sets(viol_df, fitness_df, alignments, s, output_dir):
    out_path = os.path.join(output_dir, "task15_parallel_sets.svg")

    # Left axis: fitness bands (trace-level)
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    band_labels = [b[0] for b in _FITNESS_BANDS]
    band_colors  = [b[3] for b in _FITNESS_BANDS]
    band_counts_arr = np.array([
        int(((fits >= lo) & (fits < hi)).sum())
        for _, lo, hi, _, _ in _FITNESS_BANDS
    ])
    keep_bands = [i for i, c in enumerate(band_counts_arr) if c > 0]
    if not keep_bands:
        render_empty_state_svg(out_path, "Fitness Band vs. Move Type", "No data.")
        return

    # Right axis: violation move types
    # Build matrix (n_bands × n_mts): violations per band (approx by assigning
    # each trace's violations proportionally to its fitness band)
    present_mts = [mt for mt in _MOVE_TYPES if mt in viol_df["move_type"].values]
    if not present_mts:
        render_empty_state_svg(out_path, "Fitness Band vs. Move Type", "No violations.")
        return

    # Per-trace violation counts by move type
    trace_viol: list[dict] = []
    for result in alignments:
        row: dict = {mt: 0 for mt in _MOVE_TYPES}
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            mt = step["moveType"]
            if mt in row:
                row[mt] += 1
        trace_viol.append(row)

    n_traces = min(len(fits), len(trace_viol))
    matrix = np.zeros((len(keep_bands), len(present_mts)), dtype=float)
    for ti in range(n_traces):
        fit = fits[ti]
        for bi_idx, bi in enumerate(keep_bands):
            lo = _FITNESS_BANDS[bi][1]
            hi = _FITNESS_BANDS[bi][2]
            if lo <= fit < hi:
                for mi, mt in enumerate(present_mts):
                    matrix[bi_idx, mi] += trace_viol[ti].get(mt, 0)
                break

    keep_mts = [i for i in range(len(present_mts)) if matrix[:, i].sum() > 0]
    if not keep_mts:
        render_empty_state_svg(out_path, "Fitness Band vs. Move Type", "No violations.")
        return
    matrix = matrix[:, keep_mts]
    right_labels = [present_mts[i] for i in keep_mts]
    right_colors  = [_MOVE_COLOR.get(present_mts[i], "#AAAAAA") for i in keep_mts]

    left_labels = [
        f"{band_labels[bi]}\n(n={band_counts_arr[bi]})"
        for bi in keep_bands
    ]
    left_colors = [band_colors[bi] for bi in keep_bands]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Fitness Band vs. Violation Move Type", fontsize=FONT_TITLE, pad=12)
    _add_stats_footer(fig, s)
    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_labels,
        matrix=matrix.astype(int),
        left_colors=left_colors,
        right_colors=right_colors,
        left_title="Fitness Band",
        right_title="Move Type",
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task15_table.svg",                      "Violations by Activity"),
    ("task15_bar_chart.svg",                  "Top Activities by Violation Count"),
    ("task15_scatter_plot.svg",               "Per-trace Fitness Distribution"),
    ("task15_flow_chart_elaborate.svg",       "Violations on the Process Model"),
    ("task15_flow_chart_elaborate_table.svg", "Violations on the Process Model & Summary"),
    ("task15_tree.svg",                       "Violation Hierarchy"),
    ("task15_table_bar_chart.svg",            "Violation Type Summary & Fitness Bands"),
    ("task15_parallel_sets.svg",              "Fitness Band vs. Violation Move Type"),
]


def generate(log, fitness_df, alignments, output_dir: str,
             model_path: str = None, compare_attribute: str = "AMOUNT_REQ"):
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 15 visualizations ---")

    viol_df = _build_violation_df(alignments)
    act_totals = _activity_total_violations(viol_df)
    s = _overall_stats(fitness_df, viol_df)
    logger.info(f"      -> {_stats_line(s)}")

    task15_table(viol_df, s, output_dir)
    task15_bar_chart(viol_df, s, output_dir)
    task15_scatter_plot(fitness_df, s, output_dir)
    task15_flow_chart_elaborate(act_totals, s, model_path, output_dir)
    task15_flow_chart_elaborate_table(act_totals, viol_df, s, model_path, output_dir)
    task15_table_bar_chart(viol_df, fitness_df, s, output_dir)
    task15_parallel_sets(viol_df, fitness_df, alignments, s, output_dir)
