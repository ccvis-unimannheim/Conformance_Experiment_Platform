"""
tasks/task25.py – Task ID 25: Explore / Discover / Process conformance.

The analyst discovers the overall conformance degree themself from raw /
per-entity data. Core principle: NO aggregated conformance number appears in
any of this task's figures — no overall fitness, no percentage, no mean line,
no summary row. Reuses the centrally computed per-trace fitness.

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["tile_metric", "bar_chart", "scatter_plot", "table"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 25 (AUTO): no hyperparameters — the analyst discovers the overall
# conformance degree from the visualisation. GT is the same scalar fitness
# as task06 (mean per-trace fitness × 100, rounded). count-set format
# additionally exposes the raw conformant / non-conformant trace counts.
# ---------------------------------------------------------------------------
GT_TIER = "AUTO"

PARAM_SPEC = []

ANSWER_FORMATS = [
    {"key": "mc-single", "gt_shape": "mc", "decisive_default": True},
    {"key": "mc-multi",  "gt_shape": "mc", "decisive_default": True},
]


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """MC options derived from actual per-trace fitness statistics."""
    import random

    mean_fit = float(fitness_df["fitness"].mean()) if len(fitness_df) > 0 else 0.0
    pct = round(mean_fit * 100)
    total = len(fitness_df)
    conform = int(fitness_df["is_fit"].sum())
    non_conform = total - conform

    if answer_format == "mc-single":
        # 4 percentage buckets; exactly one is correct.
        buckets = [
            ("Below 25%",    0,  25),
            ("25% – 50%",   25,  50),
            ("50% – 75%",   50,  75),
            ("75% or above", 75, 100),
        ]
        options = []
        for label, lo, hi in buckets:
            correct = lo <= pct < hi or (hi == 100 and pct == 100)
            options.append({"label": label, "value": label, "correct": correct})
        return {"options": options}

    # mc-multi: statements that may each be objectively true or false.
    statements = [
        {
            "label": "More than half of all traces conform to the process model.",
            "value": "majority_conform",
            "correct": conform > non_conform,
        },
        {
            "label": "The overall conformance rate exceeds 75%.",
            "value": "above_75",
            "correct": pct > 75,
        },
        {
            "label": "Fewer than 25% of traces deviate from the model.",
            "value": "low_deviation",
            "correct": (non_conform / total * 100 < 25) if total > 0 else False,
        },
        {
            "label": "There are more non-conformant than conformant traces.",
            "value": "majority_nonconform",
            "correct": non_conform > conform,
        },
        {
            "label": "All traces fully conform to the process model.",
            "value": "all_conform",
            "correct": non_conform == 0,
        },
    ]
    random.shuffle(statements)
    return {"options": statements}


import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import (
    save_svg, make_table, render_counts_tile_metric,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task25_tile_metric(df, output_dir: str):
    """Tile Metric (discovery variant): raw counts only — no ratio, no percentage."""
    conform = int(df["is_fit"].sum())
    non_conform = len(df) - conform
    render_counts_tile_metric(
        conform, non_conform,
        os.path.join(output_dir, "task25_tile_metric.svg"),
    )


def task25_bar_chart(df, output_dir: str):
    """Exactly two bars: conformant vs non-conformant trace counts, counts as labels."""
    conform = int(df["is_fit"].sum())
    non_conform = len(df) - conform
    ymax = max(conform, non_conform, 1)

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(
        ["Conformant Traces", "Non-conformant Traces"],
        [conform, non_conform],
        color=[GREY_MED, GREY_LIGHT], edgecolor="white", width=0.5,
    )
    for bar, val in zip(bars, [conform, non_conform]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.015,
            str(val), ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Conformant vs. Non-conformant Traces", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_bar_chart.svg"))


def task25_scatter_plot(df, output_dir: str):
    """One neutral-coloured dot per trace; x = chronological index, y = fitness.

    No mean/aggregate annotation (task06's scatter scaffolding minus its
    aggregate decorations and conformance colouring).
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.scatter(df["trace_index"], df["fitness"], c=GREY_MED, s=15, alpha=0.6, linewidths=0)
    ax.set_xlabel("Traces in Log ordered by time", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Fitness per Trace", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_scatter_plot.svg"))


def task25_table(df, output_dir: str):
    """Conformance summary row: #Traces | #Conformant | % Conformant | Overall Fitness."""
    total           = len(df)
    conform         = int(df["is_fit"].sum())
    pct_conform     = (conform / total * 100) if total else 0.0
    overall_fitness = float(df["fitness"].mean()) if total else 0.0

    cell_text = [[str(total), str(conform), f"{pct_conform:.2f}%", f"{overall_fitness:.4f}"]]
    fig_h = max(3.6, 1.45 + len(cell_text) * 0.58)
    fig, ax = plt.subplots(figsize=(10.0, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["#Traces", "#Conformant", "% Conformant", "Overall Fitness"],
        bbox=[0.03, 0.04, 0.94, 0.80],
        col_widths=[0.24, 0.26, 0.26, 0.24],
        font_size=11,
        scale_xy=(1.12, 2.05),
        cell_pad=0.14,
    )
    ax.set_title("Conformance Summary", fontsize=FONT_TITLE, pad=10)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_table.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, model_path: str = None):
    """Generate all Task 25 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 25 visualizations ---")

    if fitness_df is None or fitness_df.empty:
        logger.warning("      Skipped Task 25: empty fitness DataFrame.")
        return

    task25_tile_metric(fitness_df, output_dir)
    task25_bar_chart(fitness_df, output_dir)
    task25_scatter_plot(fitness_df, output_dir)
    task25_table(fitness_df, output_dir)
