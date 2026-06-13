"""
tasks/task33.py – Task ID 33: Present / Compare / Process conformance (attribute sub-logs).

How does the overall degree of conformance differ between traces with a certain
data attribute value? Numeric attribute → median split; categorical → one sub-log
per distinct value (top-4 + "Other"). Shows fitness distributions, ranges, and
summaries across sub-logs. No alignment data required.

Public API:
    generate(log, fitness_df, output_dir, compare_attribute="AMOUNT_REQ")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart",
    "stacked_bar",
    "scatter_plot",
    "boxplot",
    "table",
    "table_bar_chart",
    "matrix",
    "heatmap",
]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table,
    draw_value_heatmap, draw_rate_matrix, draw_grouped_box_plot,
    render_empty_state_svg, format_threshold,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

from tasks.task30 import split_by_attribute

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Greyscale-only group shades (platform style is strictly greyscale).
_GROUP_PALETTE = ["#333333", "#666666", "#999999", "#BBBBBB", "#DDDDDD"]

# Fitness bands: (label, lo, hi, fill_color, text_color)
_FITNESS_BANDS = [
    ("0.00–0.25", 0.00, 0.25, "#333333", "white"),
    ("0.25–0.50", 0.25, 0.50, "#777777", "white"),
    ("0.50–0.75", 0.50, 0.75, "#AAAAAA", "#333333"),
    ("0.75–1.00", 0.75, 1.01, "#D9D9D9", "#333333"),
]

_FIT_THRESHOLD = 0.8  # traces with fitness >= threshold counted as conformant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_trace_df(fitness_df: pd.DataFrame, assignment: list, meta: dict) -> pd.DataFrame:
    n = min(len(fitness_df), len(assignment))
    df = fitness_df.iloc[:n].copy()
    df["group"] = assignment[:n]
    if meta["type"] == "numeric":
        df["value"] = meta["numeric_values"][:n]
    return df[df["group"].notna()].reset_index(drop=True)


def _group_stats(trace_df: pd.DataFrame, groups: list) -> pd.DataFrame:
    rows = []
    for g in groups:
        sub = trace_df[trace_df["group"] == g]["fitness"]
        n = len(sub)
        rows.append({
            "group":       g,
            "n":           n,
            "pct_conform": float((sub >= _FIT_THRESHOLD).sum() / n * 100) if n else 0.0,
            "mean":        float(sub.mean())   if n else 0.0,
            "median":      float(sub.median()) if n else 0.0,
            "std":         float(sub.std())    if n else 0.0,
            "min":         float(sub.min())    if n else 0.0,
            "max":         float(sub.max())    if n else 0.0,
        })
    return pd.DataFrame(rows)


def _group_colors(groups: list) -> list:
    return [_GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i in range(len(groups))]


def _band_rates(trace_df: pd.DataFrame, groups: list) -> np.ndarray:
    """(n_bands × n_groups): % of sub-log traces per fitness band."""
    data = np.zeros((len(_FITNESS_BANDS), len(groups)), dtype=float)
    for gi, g in enumerate(groups):
        sub = trace_df[trace_df["group"] == g]["fitness"]
        n = len(sub)
        if n == 0:
            continue
        for bi, (_, lo, hi, _, _) in enumerate(_FITNESS_BANDS):
            data[bi, gi] = float(((sub >= lo) & (sub < hi)).sum() / n * 100)
    return data


def _fine_bin_rates(trace_df: pd.DataFrame, groups: list) -> np.ndarray:
    """(10 × n_groups): % per 0.1-width fitness bin."""
    data = np.zeros((10, len(groups)), dtype=float)
    for gi, g in enumerate(groups):
        sub = trace_df[trace_df["group"] == g]["fitness"]
        n = len(sub)
        if n == 0:
            continue
        for bi in range(10):
            lo, hi = bi / 10, (bi + 1) / 10
            data[bi, gi] = float(((sub >= lo) & (sub < hi)).sum() / n * 100)
    return data


# ---------------------------------------------------------------------------
# Idiom 1: bar_chart — mean fitness per sub-log with std error bars
# ---------------------------------------------------------------------------

def task33_bar_chart(trace_df, stats_df, groups, attr, output_dir):
    colors = _group_colors(groups)
    fig, ax = plt.subplots(figsize=(max(5, len(groups) * 2.0), 5.5))

    for i, (g, color) in enumerate(zip(groups, colors)):
        sub = trace_df[trace_df["group"] == g]["fitness"]
        mean = float(sub.mean()) if len(sub) else 0.0
        std  = float(sub.std())  if len(sub) else 0.0
        n    = len(sub)
        ax.bar(i, mean, color=color, edgecolor="white", linewidth=0.6, width=0.6)
        # Clip error bars so they stay within [0, 1]
        yerr_lo = min(std, mean)
        yerr_hi = min(std, 1.0 - mean)
        ax.errorbar(i, mean, yerr=[[yerr_lo], [yerr_hi]],
                    color="#555555", capsize=5, linewidth=1.2)
        # Place n= inside bar bottom to avoid overlap with rotated x-tick labels
        txt_y = max(mean / 2, 0.03)
        txt_c = "white" if mean > 0.12 else "#444444"
        ax.text(i, txt_y, f"n={n}", ha="center", va="center",
                fontsize=FONT_ANNOT - 1, color=txt_c)

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, rotation=0, ha="center", fontsize=FONT_ANNOT)
    ax.set_ylabel("Mean Fitness (± 1 std)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 1.15)
    ax.set_title(f"Mean Fitness per Sub-log ({attr})", fontsize=FONT_TITLE)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task33_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 2: stacked_bar — fitness band composition per sub-log
# ---------------------------------------------------------------------------

def task33_stacked_bar(trace_df, groups, attr, output_dir):
    band_names   = [b[0] for b in _FITNESS_BANDS]
    band_colors  = [b[3] for b in _FITNESS_BANDS]
    band_txtcols = [b[4] for b in _FITNESS_BANDS]
    rates = _band_rates(trace_df, groups)  # (n_bands × n_groups)

    fig, ax = plt.subplots(figsize=(max(5, len(groups) * 2.2), 5.5))
    bottoms = np.zeros(len(groups))
    x = np.arange(len(groups))
    for bi, (band, fill, tc) in enumerate(zip(band_names, band_colors, band_txtcols)):
        vals = rates[bi]
        # Suppress legend entry for bands with no traces in any group
        lbl = band if np.any(vals > 0) else "_nolegend_"
        bars = ax.bar(x, vals, bottom=bottoms, color=fill,
                      edgecolor="white", linewidth=0.5, label=lbl, width=0.6)
        for rect, val in zip(bars, vals):
            if val >= 6:
                ax.text(rect.get_x() + rect.get_width() / 2,
                        rect.get_y() + rect.get_height() / 2,
                        f"{val:.0f}%", ha="center", va="center",
                        fontsize=FONT_ANNOT - 1, color=tc)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels(groups, rotation=0, ha="center", fontsize=FONT_ANNOT)
    ax.set_ylabel("% of sub-log traces", fontsize=FONT_LABEL)
    ax.set_ylim(0, 105)
    ax.set_title(f"Fitness Band Composition per Sub-log ({attr})", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(title="Fitness band", frameon=False, fontsize=FONT_ANNOT - 1,
              title_fontsize=FONT_ANNOT,
              loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task33_stacked_bar.svg"))


# ---------------------------------------------------------------------------
# Idiom 3: scatter_plot — per-trace fitness by attribute
# ---------------------------------------------------------------------------

def task33_scatter_plot(trace_df, groups, meta, attr, output_dir):
    colors = dict(zip(groups, _group_colors(groups)))
    rng = np.random.default_rng(42)

    fig, ax = plt.subplots(figsize=(10, 5))
    if meta["type"] == "numeric":
        for g in groups:
            sub = trace_df[trace_df["group"] == g]
            if sub.empty:
                continue
            ax.scatter(sub["value"], sub["fitness"], c=colors[g], s=14,
                       alpha=0.55, linewidths=0, label=g)
        ax.axvline(meta["median"], color="#555555", linestyle="--", linewidth=1.0)
        ax.text(meta["median"], 1.07,
                f"median = {format_threshold(meta['median'])}",
                ha="center", va="bottom", fontsize=FONT_ANNOT, color="#555555")
        ax.set_xlabel(f"{attr} (case attribute)", fontsize=FONT_LABEL)
    else:
        for gi, g in enumerate(groups):
            sub = trace_df[trace_df["group"] == g]
            if sub.empty:
                continue
            jitter = rng.uniform(-0.18, 0.18, size=len(sub))
            ax.scatter(gi + jitter, sub["fitness"], c=colors[g], s=14,
                       alpha=0.55, linewidths=0, label=g)
            ax.hlines(sub["fitness"].mean(), gi - 0.3, gi + 0.3,
                      colors=colors[g], linewidth=2.0, zorder=5)
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels(groups, rotation=0, ha="center", fontsize=FONT_ANNOT)
        ax.set_xlabel(f"Sub-log ({attr})", fontsize=FONT_LABEL)

    ax.axhline(_FIT_THRESHOLD, color="#BBBBBB", linestyle=":", linewidth=0.8)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(f"Per-trace Fitness by {attr}", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, title="Sub-log",
              title_fontsize=FONT_ANNOT, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task33_scatter_plot.svg"))


# ---------------------------------------------------------------------------
# Idiom 4: boxplot — fitness distribution per sub-log
# ---------------------------------------------------------------------------

def task33_boxplot(trace_df, groups, attr, output_dir):
    colors = _group_colors(groups)
    data = [trace_df[trace_df["group"] == g]["fitness"].values for g in groups]

    fig, ax = plt.subplots(figsize=(max(4.5, len(groups) * 1.9), 6))
    draw_grouped_box_plot(ax, data, groups, colors, ylabel="Fitness (0.0–1.0)")
    ax.axhline(_FIT_THRESHOLD, color="#BBBBBB", linestyle="--", linewidth=0.9)
    ax.tick_params(axis="x", labelrotation=0)
    ax.set_title(f"Fitness Distribution per Sub-log ({attr})", fontsize=FONT_TITLE)

    # When IQR ≈ 0 (data nearly unimodal), boxes are invisible — overlay strip
    rng = np.random.default_rng(42)
    any_strip = False
    for gi, (arr, color) in enumerate(zip(data, colors)):
        if len(arr) < 2:
            continue
        q1, q3 = np.percentile(arr, [25, 75])
        if q3 - q1 < 0.01:
            jitter = rng.uniform(-0.22, 0.22, size=len(arr))
            ax.scatter(gi + 1 + jitter, arr, color=color, s=12,
                       alpha=0.45, linewidths=0, zorder=3)
            any_strip = True
    if any_strip:
        ax.text(0.99, 0.01, "Strip overlay: IQR ≈ 0",
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=FONT_ANNOT - 2, color="#999999")

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task33_boxplot.svg"))


# ---------------------------------------------------------------------------
# Idiom 5: table — full stats per sub-log
# ---------------------------------------------------------------------------

def task33_table(stats_df, attr, output_dir):
    cell_text = [
        [
            row["group"],
            str(int(row["n"])),
            f"{row['pct_conform']:.1f}%",
            f"{row['mean']:.4f}",
            f"{row['median']:.4f}",
            f"{row['std']:.4f}",
            f"{row['min']:.4f}",
            f"{row['max']:.4f}",
        ]
        for _, row in stats_df.iterrows()
    ]
    fig_h = max(2.6, 1.2 + len(stats_df) * 0.55)
    fig, ax = plt.subplots(figsize=(15, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Sub-log", "N", "% Conform.", "Mean", "Median", "Std Dev", "Min", "Max"],
        bbox=[0.02, 0.08, 0.96, 0.82],
        col_widths=[0.30, 0.07, 0.10, 0.09, 0.09, 0.09, 0.09, 0.09],
        font_size=10,
        scale_xy=(1, 1.4),
    )
    ax.set_title(f"Fitness Statistics per Sub-log ({attr})", fontsize=FONT_TITLE, pad=10)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task33_table.svg"))


# ---------------------------------------------------------------------------
# Idiom 6: table_bar_chart — stats table (left) + mean fitness bars (right)
# ---------------------------------------------------------------------------

def task33_table_bar_chart(trace_df, stats_df, groups, attr, output_dir):
    colors = _group_colors(groups)
    fig = plt.figure(figsize=(16, max(4.5, len(groups) * 0.9 + 2.5)),
                     layout="constrained")
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], figure=fig)
    ax_tbl = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    # Left: summary table
    ax_tbl.axis("off")
    cell_text = [
        [row["group"], str(int(row["n"])),
         f"{row['mean']:.4f}", f"{row['std']:.4f}", f"{row['pct_conform']:.1f}%"]
        for _, row in stats_df.iterrows()
    ]
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Sub-log", "N", "Mean Fitness", "Std Dev", "% Conform."],
        bbox=[0.02, 0.06, 0.96, 0.84],
        col_widths=[0.36, 0.12, 0.18, 0.16, 0.18],
        font_size=10,
        scale_xy=(1, 1.4),
    )
    ax_tbl.set_title(f"Sub-log Summary ({attr})", fontsize=FONT_TITLE, pad=10)

    # Right: horizontal bar chart
    means = [float(stats_df.loc[stats_df["group"] == g, "mean"].iloc[0])
             if (stats_df["group"] == g).any() else 0.0 for g in groups]
    stds  = [float(stats_df.loc[stats_df["group"] == g, "std"].iloc[0])
             if (stats_df["group"] == g).any() else 0.0 for g in groups]
    y = np.arange(len(groups))
    bars = ax_bar.barh(y, means, color=colors, edgecolor="white",
                       linewidth=0.6, height=0.5)
    ax_bar.errorbar(means, y, xerr=stds, fmt="none",
                    color="#555555", capsize=4, linewidth=1.0)
    for bar, val, std in zip(bars, means, stds):
        # Place label after the error bar cap so it never overlaps
        label_x = min(val + std + 0.025, 1.08)
        ax_bar.text(label_x, bar.get_y() + bar.get_height() / 2,
                    f"{val:.3f}", va="center", fontsize=FONT_ANNOT - 1, color="#444444")
    ax_bar.axvline(_FIT_THRESHOLD, color="#BBBBBB", linestyle="--", linewidth=0.9)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(groups, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Mean Fitness (± 1 std)", fontsize=FONT_LABEL)
    ax_bar.set_xlim(0, 1.15)
    ax_bar.set_title("Mean Fitness Comparison", fontsize=FONT_TITLE, pad=10)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)
    pad = max(0.8, 0.6)
    ax_bar.set_ylim(len(groups) - 1 + pad, -pad)

    save_svg(fig, os.path.join(output_dir, "task33_table_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 7: matrix — 4 fitness bands × groups (annotated %)
# ---------------------------------------------------------------------------

def task33_matrix(trace_df, groups, attr, output_dir):
    band_names = [b[0] for b in _FITNESS_BANDS]
    data = _band_rates(trace_df, groups)  # (4 × n_groups)

    fig_h = max(3.0, len(_FITNESS_BANDS) * 0.7 + 1.2)
    fig, ax = plt.subplots(figsize=(max(5, len(groups) * 2.2), fig_h))
    draw_rate_matrix(fig, ax, data, band_names, groups,
                     xlabel=f"Sub-log ({attr})", cbar_label="% of sub-log traces")
    ax.set_title("Fitness Band Distribution Matrix (%)", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task33_matrix.svg"))


# ---------------------------------------------------------------------------
# Idiom 8: heatmap — 10 fine bins × groups (continuous color scale)
# ---------------------------------------------------------------------------

def task33_heatmap(trace_df, groups, attr, output_dir):
    data = _fine_bin_rates(trace_df, groups)   # (10 × n_groups), low→high
    bin_labels = [f"{i/10:.1f}–{(i+1)/10:.1f}" for i in range(9, -1, -1)]
    data_flipped = data[::-1]                  # display high fitness at top

    fig_h = max(4.0, 10 * 0.42 + 1.2)
    fig, ax = plt.subplots(figsize=(max(5, len(groups) * 2.2), fig_h))
    draw_value_heatmap(fig, ax, data_flipped, bin_labels, groups,
                       xlabel=f"Sub-log ({attr})",
                       cbar_label="% of sub-log traces",
                       annotate=False, rotate_xticks=0)
    ax.set_title("Fitness Distribution Heatmap (fine bins)", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task33_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task33_bar_chart.svg",       "Mean Fitness per Sub-log"),
    ("task33_stacked_bar.svg",     "Fitness Band Composition per Sub-log"),
    ("task33_scatter_plot.svg",    "Per-trace Fitness by Attribute"),
    ("task33_boxplot.svg",         "Fitness Distribution per Sub-log"),
    ("task33_table.svg",           "Fitness Statistics per Sub-log"),
    ("task33_table_bar_chart.svg", "Sub-log Summary & Mean Fitness"),
    ("task33_matrix.svg",          "Fitness Band Distribution Matrix"),
    ("task33_heatmap.svg",         "Fitness Distribution Heatmap"),
]


def generate(log, fitness_df, output_dir, compare_attribute="AMOUNT_REQ"):
    """Generate all Task ID 33 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 33 visualizations ---")

    groups, assignment, meta = split_by_attribute(log, compare_attribute)
    if groups is None:
        logger.error(f"      task33: attribute '{compare_attribute}' not found.")
        for fname, title in _ALL_FNAMES_TITLES:
            render_empty_state_svg(
                os.path.join(output_dir, fname), title,
                f"Attribute '{compare_attribute}' not found in the event log.")
        return

    if meta["type"] == "numeric":
        logger.info(f"      -> numeric '{compare_attribute}', "
                    f"median split at {format_threshold(meta['median'])}")
    else:
        logger.info(f"      -> categorical '{compare_attribute}', "
                    f"{len(groups)} sub-logs")
    if meta["n_missing"]:
        logger.warning(f"      task33: {meta['n_missing']} traces without "
                       f"'{compare_attribute}' — excluded.")

    trace_df = _build_trace_df(fitness_df, assignment, meta)
    stats_df = _group_stats(trace_df, groups)
    for _, row in stats_df.iterrows():
        g_ascii = str(row["group"]).replace("≤", "<=")
        logger.info(f"         {g_ascii:<30} n={int(row['n']):>6}  "
                    f"mean={row['mean']:.4f}  median={row['median']:.4f}  "
                    f"conform={row['pct_conform']:.1f}%")

    task33_bar_chart(trace_df, stats_df, groups, compare_attribute, output_dir)
    task33_stacked_bar(trace_df, groups, compare_attribute, output_dir)
    task33_scatter_plot(trace_df, groups, meta, compare_attribute, output_dir)
    task33_boxplot(trace_df, groups, compare_attribute, output_dir)
    task33_table(stats_df, compare_attribute, output_dir)
    task33_table_bar_chart(trace_df, stats_df, groups, compare_attribute, output_dir)
    task33_matrix(trace_df, groups, compare_attribute, output_dir)
    task33_heatmap(trace_df, groups, compare_attribute, output_dir)
