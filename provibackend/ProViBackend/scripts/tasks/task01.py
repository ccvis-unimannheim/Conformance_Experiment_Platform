"""
tasks/task01.py – Task ID 1: Confirm / Compare / Process conformance.

Compare the conformance of two sub-logs split by process outcome (Positive = outcome_activity
present in trace; Negative = absent) against the BPMN model.

Every idiom but the box plot shows the same data, so participants who see
different idioms are given the same information: per group, the share of its
traces in each of three fitness categories, with the group's trace count in its
label. Shares rather than counts, because the groups differ in size and a
larger group would otherwise look better. The box plot cannot show this — it
draws quantiles, and with most fitness values at exactly 1.0 its boxes collapse.

Public API:
    generate(log, fitness_df, output_dir, outcome_activity="Activate Care")
        log              – PM4Py EventLog (for outcome-group classification)
        fitness_df       – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir       – directory where SVGs are written
        outcome_activity – activity name that marks a positive process outcome
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart", "table", "stacked_bar", "matrix",
    # "box_plot",             # draws quantiles, not the per-group shares; its boxes collapse at 1.0
    # "table_and_bar_chart",  # two idioms in one (task04's log level dropped it too)
    # "parallel_sets",        # shows no count of traces per conformance category
]



# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "fitness"
SPLIT_STRATEGY = "binary"
import trace_features

PARAM_SPEC = [
    {
        "key": "outcome_activity",
        "slot": "split",
        "label": "Log split condition (activity present in trace marks the Positive group)",
        "hint": "The 'Positive' group is made up of traces that contain this activity",
        "widget": "activity-picker",
        "source": "log.activities",
        "default": "",
        "required": True,
    },
    *trace_features.split_params_for('binary'),
]


def validate_params(log, params) -> list:
    """Reject conditions that cannot split the log into two non-empty groups
    (covers gibberish/typo'd activities — absent from every trace — and
    activities present in every trace)."""
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


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib import gridspec

from shared import (
    save_svg, make_table,
    draw_composition_stacked_bars, draw_grouped_box_plot, draw_grouped_rate_bars,
    draw_value_heatmap,
    CIVIDIS, PAIR_COLORS, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)
from matplotlib.colors import to_hex


# ---------------------------------------------------------------------------
# Group and category constants
# ---------------------------------------------------------------------------
_COLOR_POSITIVE, _COLOR_NEGATIVE = PAIR_COLORS  # cividis blue / yellow (box plot)
_GROUPS = ["Positive", "Negative"]
_GROUP_COLORS = [_COLOR_POSITIVE, _COLOR_NEGATIVE]


def _group_suffix(outcome_activity: str) -> str:
    """Title suffix that surfaces the chosen split activity and documents what the
    Positive/Negative groups mean, so each idiom's title varies with the activity
    while the on-chart group/legend labels stay 'Positive'/'Negative'."""
    return f"(Positive = '{outcome_activity}' present)"

# Conformance categories, low → high fitness. Yellow is low fitness (see the
# colour rule in shared.py), and both deviation categories come from cividis's
# yellow end so deviating vs conformant always reads as yellow vs blue.
# categorical_colors(3) would give Minor a slate blue next to Conformant's navy,
# and a log with no major deviations then draws all blue.
_CAT_LABELS = ["Major dev. (<0.8)", "Minor dev. (0.8–<1.0)", "Conformant (=1.0)"]
_CAT_LABELS_WRAPPED = ["Major deviation\n(< 0.8)", "Minor deviation\n(0.8 – <1.0)", "Conformant\n(= 1.0)"]
_CAT_COLORS = [to_hex(CIVIDIS(0.95)), to_hex(CIVIDIS(0.72)), to_hex(CIVIDIS(0.02))]  # yellow, ochre, navy
_SHARE_LABEL = "Share of the group's traces (%)"


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


def _task01_category_counts(df: pd.DataFrame) -> np.ndarray:
    """Trace counts per group and conformance category, shape (groups, categories).

    The one data kernel every idiom but the box plot draws from.
    """
    counts = np.zeros((len(_GROUPS), len(_CAT_LABELS)), dtype=int)
    for gi, g in enumerate(_GROUPS):
        for fitness in df.loc[df["outcome_group"] == g, "fitness"]:
            counts[gi, _task01_cat_index(float(fitness))] += 1
    return counts


def _task01_shares(counts: np.ndarray) -> np.ndarray:
    """Each group's counts as a % of that group; an empty group is all 0."""
    n = counts.sum(axis=1, keepdims=True)
    return np.divide(counts * 100.0, n, out=np.zeros(counts.shape), where=n > 0)


def _task01_group_labels(counts: np.ndarray) -> list:
    """'Positive (n=321)' — the trace count the shares are taken of."""
    return [f"{g} (n={int(n)})" for g, n in zip(_GROUPS, counts.sum(axis=1))]


def _task01_table_rows(counts: np.ndarray, shares: np.ndarray) -> list:
    """Group | #Traces | one 'count (share%)' cell per category."""
    return [
        [g, str(int(counts[gi].sum()))]
        + [f"{int(counts[gi, ci])} ({shares[gi, ci]:.1f}%)" for ci in range(len(_CAT_LABELS))]
        for gi, g in enumerate(_GROUPS)
    ]


def _task01_draw_share_bars(ax, counts: np.ndarray, shares: np.ndarray):
    """Grouped bars: per group, one bar per category, height = share of the group."""
    pos = draw_grouped_rate_bars(ax, len(_GROUPS), _CAT_LABELS, shares, _CAT_COLORS)
    ax.set_xticks(pos)
    ax.set_xticklabels(_task01_group_labels(counts), fontsize=FONT_ANNOT)
    ax.set_ylabel(_SHARE_LABEL, fontsize=FONT_LABEL)
    ax.set_ylim(0, 100)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)


def _task01_category_legend(ax, ncol: int = len(_CAT_LABELS)):
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=ncol,
              frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task01_bar_chart(counts: np.ndarray, output_dir: str, outcome_activity: str):
    """Grouped bars: per group, the share of its traces in each conformance category."""
    shares = _task01_shares(counts)
    fig, ax = plt.subplots(figsize=(6.5, 5))
    _task01_draw_share_bars(ax, counts, shares)
    ax.set_title(f"Conformance Categories per Group {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE)
    _task01_category_legend(ax)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_bar_chart.svg"))


def task01_table(counts: np.ndarray, output_dir: str, outcome_activity: str):
    """Group | #Traces | count (share%) per conformance category."""
    cell_text = _task01_table_rows(counts, _task01_shares(counts))
    fig_h = max(3.0, 1.4 + len(cell_text) * 0.56)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Group", "#Traces", *_CAT_LABELS_WRAPPED],
        bbox=[0.03, 0.06, 0.94, 0.78],
        col_widths=[0.16, 0.14, 0.23, 0.24, 0.23],
        font_size=11,
        scale_xy=(1, 1.9),
        cell_pad=0.12,
    )
    ax.set_title(f"Conformance Categories per Group {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_table.svg"))


def task01_table_and_bar_chart(counts: np.ndarray, output_dir: str, outcome_activity: str):
    """The table (left) and the grouped bars (right) in one figure."""
    shares = _task01_shares(counts)
    fig = plt.figure(figsize=(14, 5))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.3)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    make_table(
        ax_tbl,
        cell_text=_task01_table_rows(counts, shares),
        col_labels=["Group", "#Traces", *_CAT_LABELS_WRAPPED],
        bbox=[0.02, 0.18, 0.96, 0.64],
        col_widths=[0.16, 0.14, 0.23, 0.24, 0.23],
        font_size=10,
        scale_xy=(1, 1.85),
        cell_pad=0.10,
    )
    ax_tbl.set_title(f"Conformance Categories per Group {_group_suffix(outcome_activity)}",
                     fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    _task01_draw_share_bars(ax_bar, counts, shares)
    _task01_category_legend(ax_bar, ncol=1)  # three across overflow the narrow panel

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task01_table_and_bar_chart.svg"))


def task01_parallel_sets(counts: np.ndarray, output_dir: str, outcome_activity: str):
    """Parallel Sets: Outcome Group (left) × Conformance Category (right).

    Every non-empty group gets the same height, so a ribbon's width is the share
    of its group's traces — as in the other idioms — rather than a count, which
    would make the larger group look better. Implemented with matplotlib Bezier
    PathPatch — no external dependencies.
    """
    groups = _task01_group_labels(counts)
    cats   = _CAT_LABELS_WRAPPED

    total = int(counts.sum())
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

    # Colour carries one meaning here, the conformance category: ribbons take their
    # category's colour (yellow = deviation, navy = conformant), and the
    # groups are outlined and named instead. Group colours as well would read as
    # a second, matching scale.

    # Ribbon heights: share of the group × the group's (equal) height.
    n_groups = int((counts.sum(axis=1) > 0).sum())
    weights = _task01_shares(counts) / 100.0 / n_groups
    g_heights = weights.sum(axis=1)
    c_heights = weights.sum(axis=0)

    g_bottoms = np.concatenate([[0.0], np.cumsum(g_heights[:-1])])
    c_bottoms = np.concatenate([[0.0], np.cumsum(c_heights[:-1])])

    # Draw left bars (groups)
    for g, h, bot in zip(groups, g_heights, g_bottoms):
        ax.add_patch(plt.Rectangle(
            (x_left - bar_w / 2, bot), bar_w, h,
            facecolor="white", edgecolor="#333333", linewidth=1.0, zorder=3,
        ))
        if h > 0.03:
            ax.text(x_left - bar_w / 2 - 0.015, bot + h / 2, g,
                    ha="right", va="center", fontsize=FONT_ANNOT, color="#333333")

    # Draw right bars (categories)
    for cat, color, h, bot in zip(cats, _CAT_COLORS, c_heights, c_bottoms):
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

    for gi in range(len(groups)):
        for ci in range(len(cats)):
            rh = weights[gi, ci]
            if rh == 0:
                continue
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
            # Opaque enough that a navy ribbon does not wash out to grey.
            ax.add_patch(PathPatch(
                Path(verts, codes),
                facecolor=_CAT_COLORS[ci], edgecolor="none", alpha=0.55, zorder=2,
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

def task01_stacked_bar(counts: np.ndarray, output_dir: str, outcome_activity: str):
    """Per outcome group, composition by conformance category (100% stacked)."""
    fig, ax = plt.subplots(figsize=(6, 5.5))
    draw_composition_stacked_bars(ax, _task01_group_labels(counts), _CAT_LABELS,
                                  _task01_shares(counts).T, segment_colors=_CAT_COLORS)
    ax.set_ylabel(_SHARE_LABEL, fontsize=FONT_LABEL)
    ax.set_ylim(0, 100)
    ax.set_title(f"Conformance-Category Composition per Group {_group_suffix(outcome_activity)}",
                 fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    _task01_category_legend(ax)
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


def task01_matrix(counts: np.ndarray, output_dir: str, outcome_activity: str):
    """Outcome group × conformance category, annotated share of each group's traces.

    Colourless: each cell carries its share as a printed number alone, ruled into
    a grid. With a colour scale the matrix would be a heatmap that also prints
    its numbers — one variable encoded twice, as in tasks 27-32.
    """
    fig, ax = plt.subplots(figsize=(7, 3.4))
    draw_value_heatmap(fig, ax, _task01_shares(counts), _task01_group_labels(counts), _CAT_LABELS,
                       xlabel="Conformance Category", cbar_label=_SHARE_LABEL,
                       cell_fmt="{:.1f}%", annotate=True, rotate_xticks=15, vmax=100,
                       colorless=True)
    ax.set_title(f"Group × Conformance Category {_group_suffix(outcome_activity)}",
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

    df     = _task01_build_df(log, fitness_df, outcome_activity)
    counts = _task01_category_counts(df)

    n_pos = int((df["outcome_group"] == "Positive").sum())
    n_neg = int((df["outcome_group"] == "Negative").sum())
    logger.info(f"      -> Positive: {n_pos} traces  |  Negative: {n_neg} traces")

    if n_pos == 0:
        logger.warning(f"      No traces with outcome_activity='{outcome_activity}' — all Negative.")
    if n_neg == 0:
        logger.warning("      All traces are Positive — no Negative group.")

    task01_bar_chart(counts, output_dir, outcome_activity)
    task01_table(counts, output_dir, outcome_activity)
    # task01_table_and_bar_chart(counts, output_dir, outcome_activity)  # removed idiom
    # task01_parallel_sets(counts, output_dir, outcome_activity)  # removed idiom
    task01_stacked_bar(counts, output_dir, outcome_activity)
    # task01_box_plot(df, output_dir, outcome_activity)  # removed idiom
    task01_matrix(counts, output_dir, outcome_activity)
