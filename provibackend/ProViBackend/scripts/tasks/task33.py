"""
tasks/task33.py – Task ID 33: Present / Compare / Process conformance (attribute sub-logs).

How does the overall degree of conformance differ between traces with a certain
data attribute value? Each chosen attribute is cut into sub-logs by its own type
unless a split strategy is set (see trace_features). Shows fitness distributions,
ranges, and summaries across sub-logs. Every reported number comes from fitness;
alignments are only used to discover the default attribute set.

Public API:
    generate(log, fitness_df, output_dir, alignments=None,
             attribute_set=None, split_strategy=None, group_cap=None)
        alignments     – optional; only used to discover the default attributes
        attribute_set  – attributes to compare; empty = the discovered default
                         set. The distribution idioms use only the first one.
        split_strategy – "binary" | "nominal_n" | "ordered_bins"; None picks
                         by each attribute's type
        group_cap      – most groups named before the rest become "Other"
"""

RUBRIC = (
    "A complete answer says which attribute value's traces conform better and by "
    "roughly how much, reading the per-group fitness summaries (and, where shown, "
    "their spread). Award full marks for the correct direction with an "
    "approximate magnitude, partial marks for the correct direction alone, and no "
    "marks for the wrong direction or for comparing how many traces each group "
    "holds rather than how well they conform."
)

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


# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "fitness"
SPLIT_STRATEGY = None  # admin chooses

_SPLIT_SUPTITLE = "Process Conformance by Candidate Attribute"

import trace_features

def validate_params(log, params) -> list:
    return trace_features.validate_attribute_class(params, multi=True)


PARAM_SPEC = [
    *trace_features.attribute_params(),
    *trace_features.split_params_for(),
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

from tasks.task30 import split_by_attribute, MAX_CATEGORICAL_GROUPS

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
    """Per sub-log fitness summary."""
    import trace_response

    stats = trace_response.fitness_stats(
        trace_df["fitness"], trace_df["group"], groups,
    )
    return pd.DataFrame({
        "group":       stats["group"],
        "n":           stats["n"],
        "mean":        stats["mean"],
        "median":      stats["median"],
        "std":         stats["std"],
        "min":         stats["min"],
        "max":         stats["max"],
    })


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
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
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
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
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

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task33_boxplot.svg"))


# ---------------------------------------------------------------------------
# Idiom 5: table — full stats per sub-log
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Idiom 6: table_bar_chart — stats table (left) + mean fitness bars (right)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Idiom 7: matrix — 4 fitness bands × groups (annotated %)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Idiom 8: heatmap — 10 fine bins × groups (continuous color scale)
# ---------------------------------------------------------------------------

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


def generate(log, fitness_df, output_dir, alignments=None,
             attribute_set=None, split_strategy=None, group_cap=None):
    """Render Task ID 33 into output_dir.

    The panel idioms draw mean fitness per bucket of every chosen attribute,
    through the renderers task20 also uses. The distribution idioms need a
    single grouping, so they use the first attribute selected and name it in
    their own titles.
    """
    import trace_response
    import tasks.task20 as task20

    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 33 visualizations ---")

    # Alignments are used only to discover the default attribute set; every
    # number this task reports comes from fitness.
    feat = task20.task20_trace_feature_dataframe(log, alignments) if alignments is not None else None
    attrs = list(attribute_set) if attribute_set else task20._default_attributes(log, feat)
    panels = trace_response.attribute_panels(
        log, attrs, "fitness", fitness_per_trace=fitness_df["fitness"],
        strategy=split_strategy, cap=group_cap,
    )
    logger.info(f"      -> attributes: {attrs}  ({len(panels)} panel(s))")

    fmt = dict(suptitle=_SPLIT_SUPTITLE, value_label="Mean fitness",
               value_fmt="{:.3f}", value_max=1.0)
    task20.task20_bar_chart(panels, output_dir, filename="task33_bar_chart.svg", **fmt)
    task20.task20_table(panels, output_dir, filename="task33_table.svg", **fmt)
    task20.task20_table_bar_chart(panels, output_dir,
                                  filename="task33_table_bar_chart.svg", **fmt)
    task20.task20_matrix(panels, output_dir, filename="task33_matrix.svg", **fmt)
    task20.task20_heatmap(panels, output_dir, filename="task33_heatmap.svg", **fmt)

    compare_attribute = attrs[0] if attrs else ""
    groups, assignment, meta = split_by_attribute(
        log, compare_attribute, max_groups=group_cap or MAX_CATEGORICAL_GROUPS)
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
                    f"mean={row['mean']:.4f}  median={row['median']:.4f}")

    # One grouping only: these read a distribution, not a per-bucket summary.
    task33_stacked_bar(trace_df, groups, compare_attribute, output_dir)
    task33_scatter_plot(trace_df, groups, meta, compare_attribute, output_dir)
    task33_boxplot(trace_df, groups, compare_attribute, output_dir)
