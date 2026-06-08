"""
tasks/task05.py – Task ID 5: Describe / Compare / Violation patterns.

Compare violation patterns between Positive (outcome_activity present) and
Negative (absent) outcome groups. Violation classification reused from task29.

Public API:
    generate(log, alignments, output_dir, outcome_activity="A_ACTIVATED")
        log              – PM4Py EventLog
        alignments       – raw alignment results from io_helpers.run_alignments
        output_dir       – directory where SVGs are written
        outcome_activity – activity name that marks a positive process outcome
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "table", "table_and_bar_chart", "matrix", "parallel_sets"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from matplotlib.colors import LinearSegmentedColormap

from shared import (
    save_svg, make_table, draw_parallel_sets, alignment_pairs_to_rows,
    BLUE, ORANGE, FONT_TITLE, FONT_LABEL, FONT_ANNOT, contrasting_text_color,
)

TOP_N = 10

_COLOR_POSITIVE = BLUE
_COLOR_NEGATIVE = ORANGE
_GROUP_COLORS   = {"Positive": _COLOR_POSITIVE, "Negative": _COLOR_NEGATIVE}

_OUTCOME_ACTIVITY = "A_ACTIVATED"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task05_outcome_group(trace, outcome_activity: str) -> str:
    activities = {str(event.get("concept:name", "")) for event in trace}
    return "Positive" if outcome_activity in activities else "Negative"


def _task05_build_violation_df(log, alignments, outcome_activity: str) -> pd.DataFrame:
    """Build per-trace violation rows with outcome group label."""
    rows = []
    for i, (trace, result) in enumerate(zip(log, alignments)):
        group = _task05_outcome_group(trace, outcome_activity)
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            if step["moveType"] == "Synchronous Move":
                continue
            activity = step["model_move"] if step["moveType"] == "Model Move" else step["log_move"]
            pattern  = f"{activity} ({step['moveType']})"
            rows.append({"trace_index": i, "group": group, "pattern": pattern})
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["trace_index", "group", "pattern"])


def _task05_aggregate(viol_df: pd.DataFrame, n_traces: dict, top_n: int = TOP_N) -> pd.DataFrame:
    """Per-pattern counts + rates per group, sorted by total count."""
    groups = ["Positive", "Negative"]

    if viol_df.empty:
        return pd.DataFrame(columns=["pattern", "Positive_count", "Positive_rate",
                                      "Negative_count", "Negative_rate", "total"])

    pattern_counts = (
        viol_df.groupby(["pattern", "group"])["trace_index"]
        .nunique()   # traces exhibiting this violation
        .reset_index()
        .rename(columns={"trace_index": "n_traces_with"})
    )

    # Pivot to wide
    wide = pattern_counts.pivot(index="pattern", columns="group",
                                values="n_traces_with").fillna(0).reset_index()
    for g in groups:
        if g not in wide.columns:
            wide[g] = 0
    wide["total"] = wide[["Positive", "Negative"]].sum(axis=1)

    for g in groups:
        ng = n_traces.get(g, 1)
        wide[f"{g}_count"] = wide[g].astype(int)
        wide[f"{g}_rate"]  = wide[g] / ng * 100 if ng else 0.0
    wide = wide.sort_values("total", ascending=False).head(top_n).reset_index(drop=True)
    return wide[["pattern", "Positive_count", "Positive_rate",
                  "Negative_count", "Negative_rate", "total"]]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task05_bar_chart(agg_df: pd.DataFrame, output_dir: str):
    """Grouped bars: violation rate per top-N pattern for Positive vs Negative."""
    patterns = agg_df["pattern"].tolist()
    x     = np.arange(len(patterns))
    width = 0.38

    fig, ax = plt.subplots(figsize=(max(9, len(patterns) * 1.1), 5.5))
    ax.bar(x - width / 2, agg_df["Positive_rate"], width,
           color=_COLOR_POSITIVE, label="Positive outcome", edgecolor="white")
    ax.bar(x + width / 2, agg_df["Negative_rate"], width,
           color=_COLOR_NEGATIVE, label="Negative outcome", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(patterns, rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("% of group traces exhibiting violation", fontsize=FONT_LABEL)
    ax.set_title(f"Top-{len(patterns)} Violation Patterns by Outcome Group", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task05_bar_chart.svg"))


def task05_stacked_bar(agg_df: pd.DataFrame, n_traces: dict, output_dir: str):
    """Stacked bar: one bar per outcome group, segments = top-N patterns + Other."""
    groups  = ["Positive", "Negative"]
    colors  = [f"#{h}" for h in ["555555", "777777", "999999", "BBBBBB", "CCCCCC",
                                   "AAAAAA", "888888", "666666", "444444", "333333"]]

    # Build stacks: each pattern contributes its count (violations, not traces)
    patterns = agg_df["pattern"].tolist()

    fig, ax = plt.subplots(figsize=(5, 5.5))
    bottoms = {g: 0.0 for g in groups}
    for i, row in agg_df.iterrows():
        for g, col in zip(groups, [_COLOR_POSITIVE, _COLOR_NEGATIVE]):
            h = float(row[f"{g}_rate"])
            if h > 0:
                ax.bar(g, h, bottom=bottoms[g],
                       color=colors[i % len(colors)], edgecolor="white", linewidth=0.5,
                       label=row["pattern"] if g == "Positive" else "_nolegend_")
            bottoms[g] += h

    ax.set_ylabel("Cumulative violation rate (%)", fontsize=FONT_LABEL)
    ax.set_title("Violation Pattern Composition per Outcome Group", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, fontsize=FONT_ANNOT - 1,
        title="Violation pattern", title_fontsize=FONT_ANNOT,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task05_stacked_bar.svg"))


def task05_table(agg_df: pd.DataFrame, output_dir: str):
    """Table: Pattern | Positive (count / rate) | Negative (count / rate) | Total."""
    cell_text = [
        [
            row["pattern"],
            f"{int(row['Positive_count'])} ({row['Positive_rate']:.1f}%)",
            f"{int(row['Negative_count'])} ({row['Negative_rate']:.1f}%)",
            str(int(row["total"])),
        ]
        for _, row in agg_df.iterrows()
    ]
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Violation Pattern", "Positive (n / rate)", "Negative (n / rate)", "Total"],
        bbox=[0.01, 0.05, 0.98, 0.80],
        col_widths=[0.50, 0.18, 0.18, 0.10],
        font_size=9.5,
        scale_xy=(1, 1.75),
        cell_pad=0.09,
    )
    ax.set_title(f"Top-{len(cell_text)} Violation Patterns by Outcome Group",
                 fontsize=FONT_TITLE, pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task05_table.svg"))


def task05_table_and_bar_chart(agg_df: pd.DataFrame, output_dir: str):
    """Table (left) + grouped bar chart (right) in one figure."""
    fig = plt.figure(figsize=(16, max(4.5, 1.2 + len(agg_df) * 0.45)))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.35)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text = [
        [row["pattern"],
         f"{int(row['Positive_count'])} ({row['Positive_rate']:.1f}%)",
         f"{int(row['Negative_count'])} ({row['Negative_rate']:.1f}%)",
         str(int(row["total"]))]
        for _, row in agg_df.iterrows()
    ]
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Violation Pattern", "Positive", "Negative", "Total"],
        bbox=[0.01, 0.05, 0.98, 0.82],
        col_widths=[0.52, 0.18, 0.18, 0.10],
        font_size=9,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )
    ax_tbl.set_title(f"Top-{len(agg_df)} Violation Patterns", fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    patterns = agg_df["pattern"].tolist()
    x = np.arange(len(patterns))
    w = 0.38
    ax_bar.barh(x - w / 2, agg_df["Positive_rate"], w,
                color=_COLOR_POSITIVE, label="Positive", edgecolor="white")
    ax_bar.barh(x + w / 2, agg_df["Negative_rate"], w,
                color=_COLOR_NEGATIVE, label="Negative", edgecolor="white")
    ax_bar.set_yticks(x)
    ax_bar.set_yticklabels(patterns, fontsize=FONT_ANNOT - 1)
    ax_bar.set_xlabel("Rate (%)", fontsize=FONT_LABEL)
    ax_bar.legend(frameon=False, fontsize=FONT_ANNOT)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task05_table_and_bar_chart.svg"))


def task05_matrix(agg_df: pd.DataFrame, output_dir: str):
    """Heatmap matrix: rows = violation pattern (top-N), cols = outcome group, cell = rate."""
    if agg_df.empty:
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.axis("off")
        ax.text(0.5, 0.5, "No violations found.", ha="center", va="center", fontsize=11)
        ax.set_title("Violation Rate Matrix", fontsize=FONT_TITLE)
        save_svg(fig, os.path.join(output_dir, "task05_matrix.svg"))
        return

    patterns = agg_df["pattern"].tolist()
    groups   = ["Positive", "Negative"]
    data     = agg_df[["Positive_rate", "Negative_rate"]].values  # shape (N, 2)

    cmap = LinearSegmentedColormap.from_list("task05_mat", ["#F8F8F8", "#444444"])
    vmax = max(data.max(), 1.0)

    fig_h = max(3.0, 0.55 * len(patterns) + 1.2)
    fig, ax = plt.subplots(figsize=(5, fig_h))
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")

    ax.set_xticks([0, 1])
    ax.set_xticklabels(groups, fontsize=FONT_ANNOT)
    ax.set_yticks(np.arange(len(patterns)))
    ax.set_yticklabels(patterns, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Outcome Group", fontsize=FONT_LABEL)
    ax.set_title("Violation Rate Matrix (%)", fontsize=FONT_TITLE)

    midpoint = vmax * 0.55
    for ri, row in enumerate(data):
        for ci, val in enumerate(row):
            text_color = "white" if val > midpoint else "#222222"
            ax.text(ci, ri, f"{val:.1f}%",
                    ha="center", va="center", fontsize=FONT_ANNOT, color=text_color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Rate (%)", fontsize=FONT_ANNOT)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task05_matrix.svg"))


def task05_parallel_sets(agg_df: pd.DataFrame, viol_df: pd.DataFrame,
                          n_traces: dict, output_dir: str):
    """Parallel Sets: Outcome Group × Violation Pattern (top-N + Other)."""
    groups   = ["Positive", "Negative"]
    patterns = agg_df["pattern"].tolist() if not agg_df.empty else []

    # Build count matrix: [n_groups × n_patterns+1(Other)]
    cats = patterns + (["Other"] if not viol_df.empty else [])
    matrix = np.zeros((len(groups), len(cats)), dtype=int)

    if not viol_df.empty:
        top_set = set(patterns)
        for gi, g in enumerate(groups):
            sub = viol_df[viol_df["group"] == g]
            for ci, pat in enumerate(patterns):
                matrix[gi, ci] = int((sub["pattern"] == pat).sum())
            other_count = int((~sub["pattern"].isin(top_set)).sum())
            if len(cats) > len(patterns):
                matrix[gi, -1] = other_count

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Outcome Group vs. Violation Pattern",
                 fontsize=FONT_TITLE, pad=12)

    n_cats = len(cats)
    grey_scale = ["#CCCCCC", "#AAAAAA", "#999999", "#888888", "#777777",
                  "#666666", "#555555", "#444444", "#333333", "#222222", "#BBBBBB"]
    right_colors = [grey_scale[i % len(grey_scale)] for i in range(n_cats)]

    draw_parallel_sets(
        ax,
        left_labels=[f"Positive\n(n={n_traces.get('Positive', 0)})",
                     f"Negative\n(n={n_traces.get('Negative', 0)})"],
        right_labels=cats,
        matrix=matrix,
        left_colors=[_COLOR_POSITIVE, _COLOR_NEGATIVE],
        right_colors=right_colors,
        left_title="Outcome Group",
        right_title="Violation Pattern",
    )

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task05_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str, outcome_activity: str = "A_ACTIVATED"):
    """Generate all Task ID 5 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 5 visualizations ---")

    # Outcome group counts
    n_traces = {"Positive": 0, "Negative": 0}
    for trace in log:
        n_traces[_task05_outcome_group(trace, outcome_activity)] += 1
    logger.info(f"      -> Positive: {n_traces['Positive']}  |  Negative: {n_traces['Negative']}")

    if n_traces["Positive"] == 0:
        logger.warning(f"      No traces with outcome_activity='{outcome_activity}' — all Negative.")
    if n_traces["Negative"] == 0:
        logger.warning("      All traces are Positive — no Negative group.")

    viol_df = _task05_build_violation_df(log, alignments, outcome_activity)
    logger.info(f"      -> {len(viol_df)} violation rows extracted.")

    agg_df = _task05_aggregate(viol_df, n_traces)
    logger.info(f"      -> Top-{len(agg_df)} violation patterns aggregated.")

    task05_bar_chart(agg_df, output_dir)
    task05_stacked_bar(agg_df, n_traces, output_dir)
    task05_table(agg_df, output_dir)
    task05_table_and_bar_chart(agg_df, output_dir)
    task05_matrix(agg_df, output_dir)
    task05_parallel_sets(agg_df, viol_df, n_traces, output_dir)
