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

IDIOMS = ["bar_chart", "table",
          "line_graph", "table_bar_chart",
          "matrix", "heatmap"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 4)
#
# Task 4 (SEMI): compare conformance of individual traces. The admin optionally
# picks exactly which traces to show; otherwise the first 10 traces in log order
# are used. The answer is either one fitness percentage per trace (pct-set) or
# the traces ordered from most to least conformant (rank).
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "trace_ids",
        "label": "Specific traces to show (optional; default = first 10 traces in log order)",
        # Internal to reading the chart — the participant sees the traces directly.
        "hide_hint": True,
        "widget": "select-many",
        "source": "log.trace_ids",
        "default": [],
        "required": False,
    },
]

ANSWER_FORMATS = [
    {"key": "pct-set", "gt_shape": "labelled-set", "decisive_default": True},
    {"key": "rank",    "gt_shape": "rank",          "decisive_default": True},
]


def validate_params(log, params) -> list:
    """trace_ids is optional; the generic /specify validation already checks that
    each selected id exists in the dataset, so nothing task-specific is required."""
    return []


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Fitness per sampled trace as pct-set (labelled-set) or rank (fitness desc)."""
    trace_ids = params.get("trace_ids") or None
    tdf = _task04_build_trace_df(log, fitness_df, trace_ids=trace_ids)
    if tdf.empty:
        return {"value": None, "options": []}
    if answer_format == "rank":
        ranked = tdf.sort_values(["fitness", "label"], ascending=[False, True]).reset_index(drop=True)
        return {
            "options": [
                {"label": row["label"], "value": row["label"]}
                for _, row in ranked.iterrows()
            ]
        }
    return {
        "value": None,
        "options": [
            {"label": row["label"], "value": f"{round(row['fitness'] * 100)}%", "correct": True}
            for _, row in tdf.iterrows()
        ],
    }


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, auto_col_widths, draw_value_heatmap,
    GREY_MED, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Default number of traces to sample when the admin doesn't pick specific ones.
SAMPLE_N = 10

# Single uniform bar/line colour — no conformant / non-conformant distinction.
_TRACE_COLOR = GREY_MED

# Consistent figure title across every idiom.
TITLE = "Trace Conformance Fitness"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task04_build_trace_df(log, fitness_df: pd.DataFrame, trace_ids=None,
                           sample_n: int = SAMPLE_N) -> pd.DataFrame:
    """One row per concrete trace: case-id ``label`` + ``fitness`` (rounded 3 dp).

    ``trace_ids``: optional list of case-id strings. When given, exactly those
    traces are shown in that order (ids not present in the log are skipped).
    Otherwise the first ``sample_n`` traces in log order are used.
    """
    records = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        case_id = str(trace.attributes.get("concept:name", i))
        records.append({
            "trace_index": i,
            "label":       case_id,
            "fitness":     round(float(fitness_df.iloc[i]["fitness"]), 3),
        })

    cols = ["trace_index", "label", "fitness"]
    if not records:
        return pd.DataFrame(columns=cols)

    if trace_ids:
        by_id = {}
        for r in records:
            by_id.setdefault(r["label"], r)  # first trace wins if case ids repeat
        chosen = [by_id[str(tid)] for tid in trace_ids if str(tid) in by_id]
        df = pd.DataFrame(chosen, columns=cols)
    else:
        df = pd.DataFrame(records[:sample_n], columns=cols)

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

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


def task04_table(tdf: pd.DataFrame, output_dir: str):
    """Trace | Fitness, one row per sampled trace."""
    cell_text = [[row["label"], f"{row['fitness']:.3f}"] for _, row in tdf.iterrows()] \
        or [["—", "—"]]
    col_labels = ["Trace", "Fitness"]

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(6.5, fig_h))
    ax.axis("off")
    make_table(
        ax, cell_text=cell_text, col_labels=col_labels,
        bbox=[0.05, 0.05, 0.9, 0.92],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=10.5, scale_xy=(1, 1.75), cell_pad=0.11,
    )
    ax.set_title(TITLE, fontsize=FONT_TITLE, pad=3)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_table.svg"))


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


def task04_heatmap(tdf: pd.DataFrame, output_dir: str):
    """Trace × Fitness grid: continuous colour intensity, no numeric annotation."""
    labels = tdf["label"].tolist()
    data = tdf["fitness"].values.astype(float).reshape(-1, 1)

    fig_h = max(3.0, 0.3 * len(labels) + 1.4)
    fig, ax = plt.subplots(figsize=(4.5, fig_h))
    draw_value_heatmap(
        fig, ax, data, labels, ["Fitness"],
        cbar_label="Fitness", annotate=False,
    )
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, trace_ids=None):
    """Generate all Task ID 4 SVGs into output_dir.

    ``trace_ids`` is the admin-configured list of case-id strings (from
    PARAM_SPEC "trace_ids"). When empty/None the first ``SAMPLE_N`` traces in log
    order are shown. Every idiom renders the same traces so the views are
    directly comparable (and match what the ground truth was computed for).
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 4 visualizations ---")

    tdf = _task04_build_trace_df(log, fitness_df, trace_ids=trace_ids)
    if tdf.empty:
        logger.warning("      Skipped Task 4: no trace data available.")
        return

    source = "admin-selected" if trace_ids else f"first {len(tdf)} in log order"
    logger.info(f"      -> Showing {len(tdf)} traces ({source}).")

    task04_bar_chart(tdf, output_dir)
    task04_table(tdf, output_dir)
    task04_table_bar_chart(tdf, output_dir)
    task04_matrix(tdf, output_dir)
    task04_line_graph(tdf, output_dir)
    task04_heatmap(tdf, output_dir)
