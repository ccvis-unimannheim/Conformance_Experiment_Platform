"""
tasks/task01.py – Task ID 1: Confirm / Compare / Process conformance.

Compare the conformance of two sub-logs split by process outcome (Positive = outcome_activity
present in trace; Negative = absent) against the BPMN model.

Public API:
    generate(log, fitness_df, output_dir, outcome_activity="Activate Care")
        log              – PM4Py EventLog (for outcome-group classification)
        fitness_df       – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir       – directory where SVGs are written
        outcome_activity – activity name that marks a positive process outcome
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "table_and_bar_chart", "parallel_sets",
          "stacked_bar", "box_plot", "matrix"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 1)
#
# Task 1 (SEMI): compare conformance of two sub-logs split by an outcome
# condition (an activity present in the trace = Positive group, absent =
# Negative). The answer is one mean-fitness percentage per group (pct-set).
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "outcome_activity",
        "label": "Log split condition (activity present in trace marks the Positive group)",
        "widget": "activity-picker",
        "source": "log.activities",
        "default": "",
        "required": True,
    },
]

ANSWER_FORMATS = [
    {"key": "pct-set",   "gt_shape": "labelled-set", "decisive_default": True},
    {"key": "mc-single", "gt_shape": "mc",           "decisive_default": True},
]


def validate_params(log, params) -> list:
    """Reject conditions that cannot split the log into two non-empty groups
    (covers gibberish/typo'd activities — absent from every trace — and
    activities present in every trace). See ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §10."""
    act = params.get("outcome_activity")
    if not act:
        return ["An outcome activity is required."]
    total = len(log)
    present = sum(1 for trace in log if act in {str(e.get("concept:name", "")) for e in trace})
    if present == 0:
        return [f"Outcome activity '{act}' is not present in any trace of the event log."]
    if present == total:
        return [f"Outcome activity '{act}' is present in all {total} traces — it cannot split the log into two groups."]
    return []


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Per-group mean conformance, shaped for the chosen answer format
    (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §3, §8).

    - pct-set (default): one labelled row per group, value = the group's mean
      fitness as an integer percent (e.g. "96%"), flagged correct.
    - mc-single: one option per (Positive%, Negative%) pair — the correct option
      is the real pair, plus 3 near-miss distractors (see _task01_mc_single_gt).
    """
    df    = _task01_build_df(log, fitness_df, params.get("outcome_activity", "Approve Treatment"))
    stats = _task01_group_stats(df)

    if answer_format == "mc-single":
        return _task01_mc_single_gt(stats)

    options = [
        {"label": row["group"], "value": f"{round(row['mean_fitness'] * 100)}%", "correct": True}
        for _, row in stats.iterrows()
    ]
    return {"value": None, "options": options}


def _task01_mc_single_gt(stats: "pd.DataFrame") -> dict:
    """Single-choice GT whose options are (Positive%, Negative%) pairs.

    The correct option is each group's real mean fitness as an integer percent.
    Three distractors perturb the Positive and Negative percentages INDEPENDENTLY
    by a random integer in [-3, +3] pp (never both zero), clamped to [0, 100] and
    de-duplicated so no distractor coincides with the truth or another distractor.
    The RNG is seeded from the true pair, so the same dataset reproduces the same
    four options. Stays within +-3 pp; only widens if that small neighbourhood is
    too crowded (e.g. both groups near 100%) to yield 3 unique distractors."""
    import random as _rnd

    by_group = {row["group"]: round(float(row["mean_fitness"]) * 100)
                for _, row in stats.iterrows()}
    p = max(0, min(100, by_group.get("Positive", 0)))
    n = max(0, min(100, by_group.get("Negative", 0)))

    def _fmt(pp, nn):
        return f"Positive: {pp}%  ·  Negative: {nn}%", f"P={pp}%;N={nn}%"

    correct_label, correct_value = _fmt(p, n)
    options = [{"label": correct_label, "value": correct_value, "correct": True}]

    rng  = _rnd.Random(p * 101 + n)   # stable, dataset-derived seed
    seen = {(p, n)}

    def _add_distractor(span: int) -> bool:
        for _ in range(60):
            dp, dn = rng.randint(-span, span), rng.randint(-span, span)
            if dp == 0 and dn == 0:
                continue
            cp = max(0, min(100, p + dp))
            cn = max(0, min(100, n + dn))
            if (cp, cn) in seen:
                continue
            seen.add((cp, cn))
            lbl, val = _fmt(cp, cn)
            options.append({"label": lbl, "value": val, "correct": False})
            return True
        return False

    span = 3
    while len(options) < 4 and span <= 8:
        if not _add_distractor(span):
            span += 1   # neighbourhood exhausted — widen minimally

    rng.shuffle(options)
    return {"options": options}


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

from shared import (
    save_svg, make_table,
    draw_composition_stacked_bars, draw_grouped_box_plot, draw_value_heatmap,
    GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)


# ---------------------------------------------------------------------------
# Group color constants
# ---------------------------------------------------------------------------
_COLOR_POSITIVE = GREY_MED    # medium-dark grey  — Positive outcome group
_COLOR_NEGATIVE = GREY_LIGHT  # medium grey       — Negative outcome group
_GROUPS = ["Positive", "Negative"]
_GROUP_COLORS = [_COLOR_POSITIVE, _COLOR_NEGATIVE]


def _group_suffix(outcome_activity: str) -> str:
    """Title suffix that surfaces the chosen split activity and documents what the
    Positive/Negative groups mean, so each idiom's title varies with the activity
    while the on-chart group/legend labels stay 'Positive'/'Negative'."""
    return f"(Positive = '{outcome_activity}' present)"

# Conformance categories used in Parallel Sets (ordered light → dark)
_PSET_LABELS = ["Major deviation\n(< 0.8)", "Minor deviation\n(0.8 – <1.0)", "Conformant\n(= 1.0)"]
_PSET_COLORS = [GREY_DARK, GREY_MED, GREY_LIGHTER]
# Compact category labels reused by stacked bar / matrix
_CAT_LABELS = ["Major dev. (<0.8)", "Minor dev. (0.8–<1.0)", "Conformant (=1.0)"]


def _task01_cat_index(fitness: float) -> int:
    if fitness >= 1.0:
        return 2
    if fitness >= 0.8:
        return 1
    return 0


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

def task01_bar_chart(stats_df: pd.DataFrame, output_dir: str, outcome_activity: str):
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
    ax.set_title(f"Mean Conformance Rate by Group {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE)
    ax.set_ylim(0, 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(
        handles=[
            mpatches.Patch(color=_COLOR_POSITIVE, label="Positive"),
            mpatches.Patch(color=_COLOR_NEGATIVE, label="Negative"),
        ],
        loc="lower center", bbox_to_anchor=(0.5, -0.25),
        ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_bar_chart.svg"))


def task01_table(stats_df: pd.DataFrame, output_dir: str, outcome_activity: str):
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
    ax.set_title(f"Conformance Comparison by Group {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_table.svg"))


def task01_table_and_bar_chart(stats_df: pd.DataFrame, output_dir: str, outcome_activity: str):
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
    ax_tbl.set_title(f"Conformance Comparison by Group {_group_suffix(outcome_activity)}",
                     fontsize=FONT_TITLE, pad=10)

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

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_table_and_bar_chart.svg"))


def task01_parallel_sets(df: pd.DataFrame, output_dir: str, outcome_activity: str):
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
        ax.set_title(f"Parallel Sets: Group vs. Conformance Category {_group_suffix(outcome_activity)}",
                     fontsize=FONT_TITLE)
        save_svg(fig, os.path.join(output_dir, "task01_parallel_sets.svg"))
        return

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(f"Parallel Sets: Group vs. Conformance Category {_group_suffix(outcome_activity)}",
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
    ax.text(x_left,  1.08, "Group",                ha="center", va="bottom",
            fontsize=FONT_LABEL, fontweight="bold")
    ax.text(x_right, 1.08, "Conformance Category", ha="center", va="bottom",
            fontsize=FONT_LABEL, fontweight="bold")

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

def task01_stacked_bar(df: pd.DataFrame, output_dir: str, outcome_activity: str):
    """Per outcome group, composition by conformance category (counts)."""
    counts = np.zeros((len(_CAT_LABELS), len(_GROUPS)))
    for gi, g in enumerate(_GROUPS):
        sub = df[df["outcome_group"] == g]
        for _, row in sub.iterrows():
            counts[_task01_cat_index(float(row["fitness"])), gi] += 1

    fig, ax = plt.subplots(figsize=(6, 5.5))
    draw_composition_stacked_bars(ax, _GROUPS, _CAT_LABELS, counts,
                                  segment_colors=_PSET_COLORS)
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title(f"Conformance-Category Composition per Group {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_stacked_bar.svg"))


def task01_box_plot(df: pd.DataFrame, output_dir: str, outcome_activity: str):
    """Per-trace fitness distribution per outcome group."""
    data = [df.loc[df["outcome_group"] == g, "fitness"].values for g in _GROUPS]
    fig, ax = plt.subplots(figsize=(5.5, 6))
    draw_grouped_box_plot(ax, data, _GROUPS, _GROUP_COLORS,
                          ylabel="Conformance Rate (0.0 – 1.0)")
    ax.set_title(f"Fitness Distribution per Group {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_box_plot.svg"))


def task01_matrix(df: pd.DataFrame, output_dir: str, outcome_activity: str):
    """Outcome group × conformance category, annotated trace counts."""
    counts = np.zeros((len(_GROUPS), len(_CAT_LABELS)))
    for gi, g in enumerate(_GROUPS):
        for _, row in df[df["outcome_group"] == g].iterrows():
            counts[gi, _task01_cat_index(float(row["fitness"]))] += 1
    fig, ax = plt.subplots(figsize=(7, 3.4))
    draw_value_heatmap(fig, ax, counts, _GROUPS, _CAT_LABELS,
                       xlabel="Conformance Category", cbar_label="Traces",
                       cell_fmt="{:.0f}", annotate=True, rotate_xticks=15)
    ax.set_title(f"Group × Conformance Category, trace counts {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_matrix.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, outcome_activity: str = "Activate Care"):
    """Generate all Task ID 1 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 1 visualizations ---")

    df       = _task01_build_df(log, fitness_df, outcome_activity)
    stats_df = _task01_group_stats(df)

    n_pos = int((df["outcome_group"] == "Positive").sum())
    n_neg = int((df["outcome_group"] == "Negative").sum())
    logger.info(f"      -> Positive: {n_pos} traces  |  Negative: {n_neg} traces")

    if n_pos == 0:
        logger.warning(f"      No traces with outcome_activity='{outcome_activity}' — all Negative.")
    if n_neg == 0:
        logger.warning("      All traces are Positive — no Negative group.")

    task01_bar_chart(stats_df, output_dir, outcome_activity)
    task01_table(stats_df, output_dir, outcome_activity)
    task01_table_and_bar_chart(stats_df, output_dir, outcome_activity)
    task01_parallel_sets(df, output_dir, outcome_activity)
    task01_stacked_bar(df, output_dir, outcome_activity)
    task01_box_plot(df, output_dir, outcome_activity)
    task01_matrix(df, output_dir, outcome_activity)
