"""
tasks/task01.py – Task ID 1: Confirm / Compare / Process conformance.

Compare the conformance of two sub-logs split by process outcome (Positive = outcome_activity
present in trace; Negative = absent) against the BPMN model.

Public API:
    generate(log, fitness_df, output_dir, outcome_activity="A_ACTIVATED")
        log              – PM4Py EventLog (for outcome-group classification)
        fitness_df       – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir       – directory where SVGs are written
        outcome_activity – activity name that marks a positive process outcome
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table", "table_and_bar_chart", "parallel_sets"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib import gridspec

from shared import save_svg, make_table, BLUE, ORANGE, FONT_TITLE, FONT_LABEL, FONT_ANNOT


# ---------------------------------------------------------------------------
# Group color constants
# ---------------------------------------------------------------------------
_COLOR_POSITIVE = BLUE    # medium-dark grey  — Positive outcome group
_COLOR_NEGATIVE = ORANGE  # medium grey       — Negative outcome group

# Conformance categories used in Parallel Sets (ordered light → dark)
_PSET_LABELS = ["Major deviation\n(< 0.8)", "Minor deviation\n(0.8 – <1.0)", "Conformant\n(= 1.0)"]
_PSET_COLORS = ["#CCCCCC", "#999999", "#555555"]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task01_build_df(log, fitness_df: pd.DataFrame, outcome_activity: str) -> pd.DataFrame:
    """Merge per-trace fitness with binary outcome label (Positive / Negative)."""
    outcomes = []
    for trace in log:
        activities = {str(event.get("concept:name", "")) for event in trace}
        outcomes.append("Positive" if outcome_activity in activities else "Negative")

    df = fitness_df.copy()
    n = min(len(df), len(outcomes))
    df = df.iloc[:n].copy()
    df["outcome_group"] = outcomes[:n]
    return df


def _task01_group_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Return summary stats (n_traces, n_conformant, pct_conformant, mean_fitness) per group."""
    rows = []
    for group in ["Positive", "Negative"]:
        sub = df[df["outcome_group"] == group]
        n = len(sub)
        n_conform = int(sub["is_fit"].sum()) if n > 0 else 0
        mean_fit  = float(sub["fitness"].mean()) if n > 0 else 0.0
        rows.append({
            "group":          group,
            "n_traces":       n,
            "n_conformant":   n_conform,
            "pct_conformant": (n_conform / n * 100) if n > 0 else 0.0,
            "mean_fitness":   mean_fit,
        })
    return pd.DataFrame(rows)


def _task01_conformance_category(fitness: float) -> str:
    if fitness >= 1.0:
        return _PSET_LABELS[2]
    if fitness >= 0.8:
        return _PSET_LABELS[1]
    return _PSET_LABELS[0]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task01_bar_chart(stats_df: pd.DataFrame, output_dir: str):
    """Two bars: mean conformance rate for Positive vs Negative group."""
    groups = stats_df["group"].tolist()
    means  = stats_df["mean_fitness"].tolist()
    colors = [_COLOR_POSITIVE, _COLOR_NEGATIVE]

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(groups, means, color=colors, edgecolor="white", width=0.5)
    for bar, val in zip(bars, means):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.015,
            f"{val:.3f}",
            ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Mean Conformance Rate (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Mean Conformance Rate by Outcome Group", fontsize=FONT_TITLE)
    ax.set_ylim(0, 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(
        handles=[
            mpatches.Patch(color=_COLOR_POSITIVE, label="Positive outcome"),
            mpatches.Patch(color=_COLOR_NEGATIVE, label="Negative outcome"),
        ],
        frameon=False, fontsize=FONT_ANNOT,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task01_bar_chart.svg"))


def task01_scatter_plot(df: pd.DataFrame, output_dir: str):
    """One dot per trace; x = trace index, y = fitness; color = outcome group."""
    pos_mask = df["outcome_group"] == "Positive"
    neg_mask = ~pos_mask

    fig, ax = plt.subplots(figsize=(10, 4))
    if pos_mask.any():
        ax.scatter(
            df.loc[pos_mask, "trace_index"], df.loc[pos_mask, "fitness"],
            c=_COLOR_POSITIVE, s=15, alpha=0.6, linewidths=0,
            label="Positive outcome",
        )
    if neg_mask.any():
        ax.scatter(
            df.loc[neg_mask, "trace_index"], df.loc[neg_mask, "fitness"],
            c=_COLOR_NEGATIVE, s=15, alpha=0.6, linewidths=0,
            label="Negative outcome",
        )
    ax.set_xlabel("Traces in Log ordered by time", fontsize=FONT_LABEL)
    ax.set_ylabel("Conformance Rate", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Conformance Rate per Trace by Outcome Group", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task01_scatter_plot.svg"))


def task01_table(stats_df: pd.DataFrame, output_dir: str):
    """Group | #Traces | #Conformant | % Conformant | Mean Fitness."""
    cell_text = [
        [
            row["group"],
            str(int(row["n_traces"])),
            str(int(row["n_conformant"])),
            f"{row['pct_conformant']:.1f}%",
            f"{row['mean_fitness']:.3f}",
        ]
        for _, row in stats_df.iterrows()
    ]
    fig_h = max(3.0, 1.2 + len(cell_text) * 0.56)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Group", "#Traces", "#Conformant", "% Conformant", "Mean Fitness"],
        bbox=[0.03, 0.06, 0.94, 0.78],
        col_widths=[0.20, 0.18, 0.20, 0.22, 0.20],
        font_size=11,
        scale_xy=(1, 1.9),
        cell_pad=0.12,
    )
    ax.set_title("Conformance Comparison by Outcome Group", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task01_table.svg"))


def task01_table_and_bar_chart(stats_df: pd.DataFrame, output_dir: str):
    """Table (left) + bar chart of mean fitness (right) in one figure."""
    fig = plt.figure(figsize=(12, 4.5))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.6, 1.0], wspace=0.35)

    # Left: table
    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text = [
        [
            row["group"],
            str(int(row["n_traces"])),
            str(int(row["n_conformant"])),
            f"{row['pct_conformant']:.1f}%",
            f"{row['mean_fitness']:.3f}",
        ]
        for _, row in stats_df.iterrows()
    ]
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Group", "#Traces", "#Conform.", "% Conform.", "Mean Fit."],
        bbox=[0.02, 0.10, 0.96, 0.72],
        col_widths=[0.20, 0.18, 0.22, 0.22, 0.18],
        font_size=10,
        scale_xy=(1, 1.85),
        cell_pad=0.10,
    )
    ax_tbl.set_title("Conformance Comparison by Outcome Group", fontsize=FONT_TITLE, pad=10)

    # Right: bar chart
    ax_bar = fig.add_subplot(gs[1])
    groups = stats_df["group"].tolist()
    means  = stats_df["mean_fitness"].tolist()
    bars = ax_bar.bar(groups, means, color=[_COLOR_POSITIVE, _COLOR_NEGATIVE],
                      edgecolor="white", width=0.5)
    for bar, val in zip(bars, means):
        ax_bar.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.015,
            f"{val:.3f}",
            ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax_bar.set_ylabel("Mean Conformance Rate", fontsize=FONT_LABEL)
    ax_bar.set_ylim(0, 1.15)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task01_table_and_bar_chart.svg"))


def task01_parallel_sets(df: pd.DataFrame, output_dir: str):
    """Parallel Sets: Outcome Group (left) × Conformance Category (right).

    Ribbon width proportional to number of traces. Implemented with matplotlib
    Bezier PathPatch — no external dependencies.
    """
    df = df.copy()
    df["category"] = df["fitness"].apply(_task01_conformance_category)

    groups = ["Positive", "Negative"]
    cats   = _PSET_LABELS  # light → dark

    # Count matrix [n_groups × n_cats]
    matrix = np.zeros((len(groups), len(cats)), dtype=int)
    for gi, g in enumerate(groups):
        for ci, c in enumerate(cats):
            matrix[gi, ci] = int(((df["outcome_group"] == g) & (df["category"] == c)).sum())

    total = int(matrix.sum())
    if total == 0:
        logger.warning("task01_parallel_sets: no data to render.")
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.axis("off")
        ax.text(0.5, 0.5, "No data available.", ha="center", va="center", fontsize=12)
        ax.set_title("Parallel Sets: Outcome Group vs. Conformance Category", fontsize=FONT_TITLE)
        save_svg(fig, os.path.join(output_dir, "task01_parallel_sets.svg"))
        return

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Outcome Group vs. Conformance Category",
                 fontsize=FONT_TITLE, pad=12)

    bar_w   = 0.10
    x_left  = 0.12
    x_right = 0.88
    ctrl_x  = (x_left + x_right) / 2

    g_colors = {"Positive": _COLOR_POSITIVE, "Negative": _COLOR_NEGATIVE}

    # Normalised heights
    g_heights = matrix.sum(axis=1) / total
    c_heights = matrix.sum(axis=0) / total

    g_bottoms = np.concatenate([[0.0], np.cumsum(g_heights[:-1])])
    c_bottoms = np.concatenate([[0.0], np.cumsum(c_heights[:-1])])

    # Draw left bars (groups)
    for g, h, bot in zip(groups, g_heights, g_bottoms):
        ax.add_patch(plt.Rectangle(
            (x_left - bar_w / 2, bot), bar_w, h,
            facecolor=g_colors[g], edgecolor="white", linewidth=0.8, zorder=3,
        ))
        if h > 0.03:
            ax.text(x_left - bar_w / 2 - 0.015, bot + h / 2, g,
                    ha="right", va="center", fontsize=FONT_ANNOT, color="#333333")

    # Draw right bars (categories)
    for cat, color, h, bot in zip(cats, _PSET_COLORS, c_heights, c_bottoms):
        ax.add_patch(plt.Rectangle(
            (x_right - bar_w / 2, bot), bar_w, h,
            facecolor=color, edgecolor="white", linewidth=0.8, zorder=3,
        ))
        if h > 0.03:
            ax.text(x_right + bar_w / 2 + 0.015, bot + h / 2, cat,
                    ha="left", va="center", fontsize=FONT_ANNOT - 1, color="#333333")

    # Bezier ribbons — fill offsets track consumed height within each bar
    g_fill = g_bottoms.copy().astype(float)
    c_fill = c_bottoms.copy().astype(float)

    for gi, g in enumerate(groups):
        for ci in range(len(cats)):
            count = matrix[gi, ci]
            if count == 0:
                continue
            rh = count / total
            ylb = g_fill[gi];        ylt = ylb + rh
            yrb = c_fill[ci];        yrt = yrb + rh
            g_fill[gi] += rh
            c_fill[ci] += rh

            # Closed Bezier ribbon path
            verts = [
                (x_left,   ylb),
                (ctrl_x,   ylb), (ctrl_x,  yrb), (x_right, yrb),
                (x_right,  yrt),
                (ctrl_x,   yrt), (ctrl_x,  ylt), (x_left,  ylt),
                (x_left,   ylb),
            ]
            codes = [
                Path.MOVETO,
                Path.CURVE4, Path.CURVE4, Path.CURVE4,
                Path.LINETO,
                Path.CURVE4, Path.CURVE4, Path.CURVE4,
                Path.CLOSEPOLY,
            ]
            ax.add_patch(PathPatch(
                Path(verts, codes),
                facecolor=g_colors[g], edgecolor="none", alpha=0.35, zorder=2,
            ))

    # Column labels
    ax.text(x_left,  1.08, "Outcome Group",        ha="center", va="bottom",
            fontsize=FONT_LABEL, fontweight="bold")
    ax.text(x_right, 1.08, "Conformance Category", ha="center", va="bottom",
            fontsize=FONT_LABEL, fontweight="bold")

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task01_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, outcome_activity: str = "A_ACTIVATED"):
    """Generate all Task ID 1 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 1 visualizations ---")

    df       = _task01_build_df(log, fitness_df, outcome_activity)
    stats_df = _task01_group_stats(df)

    n_pos = int((df["outcome_group"] == "Positive").sum())
    n_neg = int((df["outcome_group"] == "Negative").sum())
    logger.info(f"      -> Positive: {n_pos} traces  |  Negative: {n_neg} traces")

    if n_pos == 0:
        logger.warning(f"      No traces with outcome_activity='{outcome_activity}' — all Negative.")
    if n_neg == 0:
        logger.warning("      All traces are Positive — no Negative group.")

    task01_bar_chart(stats_df, output_dir)
    task01_scatter_plot(df, output_dir)
    task01_table(stats_df, output_dir)
    task01_table_and_bar_chart(stats_df, output_dir)
    task01_parallel_sets(df, output_dir)
