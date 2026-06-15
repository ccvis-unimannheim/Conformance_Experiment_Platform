"""
tasks/task04.py – Task ID 4: Describe / Compare / Process conformance across variants.

Group traces into control-flow variants (distinct activity sequences) and compare
their conformance fitness. Top-N variants by frequency.

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table",
          "line_graph", "table_bar_chart",
          "matrix", "heatmap"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 4)
#
# Task 4 (SEMI): compare conformance of the top-N trace variants (ranked by
# frequency). The admin specifies how many variants to include; the answer
# is either one mean-fitness percentage per variant (pct-set) or the variants
# ordered from most to least conformant (rank).
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "top_n",
        "label": "Number of top variants to compare (ranked by frequency)",
        "widget": "number",
        "default": 10,
        "required": True,
    },
]

ANSWER_FORMATS = [
    {"key": "pct-set", "gt_shape": "labelled-set", "decisive_default": True},
    {"key": "rank",    "gt_shape": "rank",          "decisive_default": True},
]


def validate_params(log, params) -> list:
    """Reject invalid top_n values (must be a positive integer)."""
    raw = params.get("top_n")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return ["'top_n' must be a positive integer."]
    if n < 1:
        return ["'top_n' must be at least 1."]
    return []


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Fitness per top-N variant as pct-set (labelled-set) or rank (ordered by fitness desc)."""
    top_n = int(params.get("top_n", 10))
    vdf = _task04_build_variant_df(log, fitness_df)
    if vdf.empty:
        return {"value": None, "options": []}
    top = vdf.head(top_n)
    if answer_format == "rank":
        ranked = top.sort_values(["fitness", "count"], ascending=[False, False]).reset_index(drop=True)
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
            for _, row in top.iterrows()
        ],
    }


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from shared import (
    save_svg, make_table, build_variant_df, variant_table_data,
    draw_value_heatmap,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N = 15

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task04_build_variant_df(log, fitness_df: pd.DataFrame) -> pd.DataFrame:
    """Variant aggregation; shared implementation lives in shared.build_variant_df."""
    return build_variant_df(log, fitness_df, warn_prefix="task04")


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task04_bar_chart(vdf: pd.DataFrame, output_dir: str, total_variants: int = 0):
    """Bar chart: top-N variants × fitness; bars coloured by conformant / non-conformant.

    ``vdf`` is already sliced to the admin-configured top_n; ``total_variants``
    is the full count (for the x-axis label).
    """
    top = vdf
    colors = [GREY_MED if f >= 1.0 else GREY_LIGHT for f in top["fitness"]]

    fig, ax = plt.subplots(figsize=(max(7, len(top) * 0.75), 5))
    bars = ax.bar(top["label"], top["fitness"], color=colors, edgecolor="white", width=0.65)

    for bar, val in zip(bars, top["fitness"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.012,
            f"{val:.3f}",
            ha="center", va="bottom", fontsize=FONT_ANNOT - 1,
        )

    import matplotlib.patches as mpatches
    ax.legend(
        handles=[
            mpatches.Patch(color=GREY_MED,   label="Conformant (fitness = 1.0)"),
            mpatches.Patch(color=GREY_LIGHT, label="Non-conformant (fitness < 1.0)"),
        ],
        loc="lower center", bbox_to_anchor=(0.5, -0.25),
        ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
    )
    n_total = total_variants or len(top)
    ax.set_xlabel(f"Variant (ranked by frequency, top {len(top)} of {n_total})",
                  fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Conformance Fitness by Process Variant", fontsize=FONT_TITLE)
    ax.set_ylim(0, 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_bar_chart.svg"))


def task04_table(vdf: pd.DataFrame, output_dir: str, total_variants: int = 0):
    """Table: Rank | #Traces | Fitness for top-N variants.

    ``vdf`` is already sliced to the admin-configured top_n.
    """
    n = len(vdf)
    cell_text, col_labels, col_widths = variant_table_data(
        vdf, n, include_length=False, include_coverage=False, rank_header="Variant",
    )
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.92],
        col_widths=col_widths,
        font_size=10.5,
        scale_xy=(1, 1.75),
        cell_pad=0.11,
    )
    n_total = total_variants or n
    ax.set_title(
        f"Top-{len(cell_text)} Process Variants by Frequency (of {n_total} total)",
        fontsize=FONT_TITLE, pad=3,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_table.svg"))


def task04_scatter_plot(vdf: pd.DataFrame, output_dir: str):
    """Scatter: all variants; x = trace count (log scale if wide), y = fitness."""
    counts  = vdf["count"].values.astype(float)
    fitness = vdf["fitness"].values
    colors  = [GREY_MED if f >= 1.0 else GREY_LIGHT for f in fitness]

    use_log = counts.max() / max(counts.min(), 1) > 20

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(counts, fitness, c=colors, s=40, alpha=0.75, edgecolors="white", linewidths=0.5)

    # Label top-5 most frequent variants; alternate y-offset when x-positions are close
    prev_log_x   = None
    prev_y_off   = 3
    for _, row in vdf.head(5).iterrows():
        log_x = np.log10(max(row["count"], 1))
        if prev_log_x is not None and abs(log_x - prev_log_x) < 0.15:
            y_off = -13 if prev_y_off >= 0 else 6
        else:
            y_off = 3
        prev_log_x = log_x
        prev_y_off = y_off
        ax.annotate(
            row["label"],
            (row["count"], row["fitness"]),
            textcoords="offset points", xytext=(5, y_off),
            fontsize=FONT_ANNOT - 1, color="#333333",
        )

    if use_log:
        ax.set_xscale("log")
        ax.set_xlabel("Variant size (#traces, log scale)", fontsize=FONT_LABEL)
    else:
        ax.set_xlabel("Variant size (#traces)", fontsize=FONT_LABEL)

    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Variant Frequency vs. Conformance Fitness", fontsize=FONT_TITLE)

    import matplotlib.patches as mpatches
    ax.legend(
        handles=[
            mpatches.Patch(color=GREY_MED,   label="Conformant"),
            mpatches.Patch(color=GREY_LIGHT, label="Non-conformant"),
        ],
        frameon=False, fontsize=FONT_ANNOT,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_scatter_plot.svg"))


# ---------------------------------------------------------------------------
def task04_line_graph(vdf: pd.DataFrame, output_dir: str):
    """Fitness profile across frequency-ranked variants (x = rank, y = fitness)."""
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(vdf["rank"], vdf["fitness"], color=GREY_MED, linewidth=1.8, marker="o", markersize=4)
    ax.fill_between(vdf["rank"], vdf["fitness"], alpha=0.15, color=GREY_MED)
    ax.set_xlabel("Variant rank (by frequency)", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Fitness Profile Across Frequency-Ranked Variants", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_line_graph.svg"))



def task04_table_bar_chart(vdf: pd.DataFrame, output_dir: str, total_variants: int = 0):
    """Variant table (left) + adjacent fitness bar per variant (right).

    ``vdf`` is already sliced to the admin-configured top_n.
    """
    from matplotlib import gridspec
    top = vdf
    n = len(top)
    cell_text, col_labels, col_widths = variant_table_data(
        vdf, n, include_length=False, include_coverage=False, rank_header="Variant")

    fig = plt.figure(figsize=(15, max(4.5, 1.2 + len(top) * 0.45)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.30)
    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    make_table(ax_tbl, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.01, 0.05, 0.98, 0.88], col_widths=col_widths,
               font_size=9.5, scale_xy=(1, 1.7), cell_pad=0.09)
    ax_tbl.set_title(f"Top-{len(top)} Variants by Frequency", fontsize=FONT_TITLE, pad=4)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(top))
    colors = [GREY_MED if f >= 1.0 else GREY_LIGHT for f in top["fitness"]]
    ax_bar.barh(y, top["fitness"], color=colors, edgecolor="white")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(top["label"], fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, 1.05)
    ax_bar.set_xlabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_table_bar_chart.svg"))


def _variant_metric_grid(vdf: pd.DataFrame):
    """(raw, norm, metric_labels, row_labels) for variant × Fitness."""
    metrics = ["Fitness"]
    raw = vdf["fitness"].values.astype(float).reshape(-1, 1)
    col = raw[:, 0]
    lo, hi = col.min(), col.max()
    norm = np.zeros_like(raw)
    norm[:, 0] = (col - lo) / (hi - lo) if hi - lo > 1e-12 else 0.5
    return raw, norm, metrics, vdf["label"].tolist()


def task04_matrix(vdf: pd.DataFrame, output_dir: str):
    """Top-N variants × normalized metrics; colour = normalized, annotate raw values.

    ``vdf`` is already sliced to the admin-configured top_n.
    """
    top = vdf
    raw, norm, metrics, labels = _variant_metric_grid(top)
    cmap = LinearSegmentedColormap.from_list("task04_mat", ["#F8F8F8", "#444444"])
    fmts = ["{:.3f}"]

    fig_h = max(3.5, 0.5 * len(labels) + 1.4)
    fig, ax = plt.subplots(figsize=(3.5, fig_h))
    im = ax.imshow(norm, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metrics, fontsize=FONT_ANNOT)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
    for ri in range(len(labels)):
        for ci in range(len(metrics)):
            tc = "white" if norm[ri, ci] > 0.55 else "#222222"
            ax.text(ci, ri, fmts[ci].format(raw[ri, ci]), ha="center", va="center",
                    fontsize=FONT_ANNOT - 1, color=tc)
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Normalized fitness", fontsize=FONT_ANNOT)
    ax.set_title(f"Variant Fitness Matrix (top-{len(labels)})", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_matrix.svg"))


def task04_heatmap(vdf: pd.DataFrame, output_dir: str):
    """All variants × normalized metrics, continuous, unannotated."""
    raw, norm, metrics, labels = _variant_metric_grid(vdf)
    fig_h = max(3.5, 0.26 * len(labels) + 1.4)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    draw_value_heatmap(fig, ax, norm, labels, metrics,
                       cbar_label="Normalized (per metric)", annotate=False)
    ax.set_title(f"Variant Metrics Heatmap (top-{len(labels)} variants)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, top_n: int = TOP_N):
    """Generate all Task ID 4 SVGs into output_dir.

    ``top_n`` is the admin-configured number of variants (from PARAM_SPEC
    "top_n"). All idioms are sliced to top_n variants ranked by frequency.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 4 visualizations ---")

    vdf = _task04_build_variant_df(log, fitness_df)
    if vdf.empty:
        logger.warning("      Skipped Task 4: no trace data available.")
        return

    n_total = len(vdf)
    top_n   = min(top_n, n_total)
    top_vdf = vdf.head(top_n)

    logger.info(f"      -> {n_total} unique variants; showing top-{top_n}.")
    if n_total == 1:
        logger.warning("      Only one variant found — charts will show a single entry.")

    # Comparison idioms: sliced to top_n (match what GT was computed for)
    task04_bar_chart(top_vdf, output_dir, total_variants=n_total)
    task04_table(top_vdf, output_dir, total_variants=n_total)
    task04_table_bar_chart(top_vdf, output_dir, total_variants=n_total)
    task04_matrix(top_vdf, output_dir)

    task04_scatter_plot(top_vdf, output_dir)
    task04_line_graph(top_vdf, output_dir)
    task04_heatmap(top_vdf, output_dir)
