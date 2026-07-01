"""
tasks/task25.py – Task ID 25: Explore / Discover / Process conformance.

The analyst discovers the overall conformance degree (= conformance rate, i.e.
**fitness**) themself from the per-trace data. Three core principles:

  * **One vocabulary — fitness (0–1).** Every idiom speaks the same conformance-
    rate language as the GT (mean per-trace fitness). NO idiom reduces the log to
    a binary conformant-vs-non-conformant split: a trace with fitness 0.9 is
    *mostly* conformant, and a binary count would mislead the analyst toward a far
    lower conformance estimate than the true rate (the answer the GT buckets).
  * **Discovery, not description.** No single aggregated conformance number is
    handed over (no overall fitness value, no mean line, no summary row).
  * **Derivable, not binned.** Every idiom shows the EXACT per-trace fitness — never
    coarse value ranges/bins. Binning into ranges would hide where inside a range
    the traces sit (all at 0.61 vs all at 0.79 give very different rates), so the
    true rate could not be recovered. With exact per-trace values the analyst can
    compute the rate themself, and all idioms are equivalent ("fair") in letting
    them do so. Reuses the centrally computed per-trace fitness.

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["tile_metric", "bar_chart", "table"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 25 (AUTO): no hyperparameters — the analyst discovers the overall
# conformance degree from the visualisation. GT is the same conformance rate as
# task06 (mean per-trace fitness × 100, rounded): mc-single buckets the rate,
# mc-multi poses fitness-distribution statements — both stay in the fitness
# vocabulary the idioms render (no binary conformant/non-conformant counts).
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
    # Thresholds derived from the EXACT per-trace fitness (the same values the
    # idioms render), so every answer option is recoverable from the visualisation
    # — no binary conformant/non-conformant count, no coarse range that hides where
    # inside it the traces sit.
    fit = fitness_df["fitness"].to_numpy(dtype=float)
    high = int((fit >= 0.8).sum())   # fitness 0.8 or higher
    low  = int((fit < 0.4).sum())    # fitness below 0.4

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

    # mc-multi: statements in the fitness vocabulary, each objectively true/false
    # and each derivable from the per-trace fitness distribution the idioms show.
    statements = [
        {
            "label": "The overall conformance rate (mean fitness) exceeds 75%.",
            "value": "rate_above_75",
            "correct": pct > 75,
        },
        {
            "label": "Most traces have a fitness of 0.8 or higher.",
            "value": "majority_high_fitness",
            "correct": high > (total - high),
        },
        {
            "label": "Some traces have a fitness below 0.4.",
            "value": "some_low_fitness",
            "correct": low > 0,
        },
        {
            "label": "The overall conformance rate (mean fitness) is below 50%.",
            "value": "rate_below_50",
            "correct": pct < 50,
        },
        {
            "label": "Every trace has a fitness of 0.8 or higher.",
            "value": "all_high_fitness",
            "correct": total > 0 and high == total,
        },
    ]
    random.shuffle(statements)
    return {"options": statements}


import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import (
    save_svg, make_table, render_distribution_tile_metric,
    GREY_MED, FONT_TITLE, FONT_LABEL,
)


# ---------------------------------------------------------------------------
# Visualizations
#
# Every idiom shows the EXACT per-trace fitness (no value ranges/bins), so the
# analyst can recover the overall conformance rate, and no idiom prints it.
# ---------------------------------------------------------------------------

def task25_tile_metric(df, output_dir: str):
    """Tile Metric (discovery variant): the two raw ingredients of the conformance
    rate — trace count and the summed per-trace fitness — but NOT the rate itself.
    The analyst divides to recover it (caption states how). No binned ranges, no
    handed-over aggregate."""
    total = len(df)
    fit_sum = float(df["fitness"].sum())
    rows = [
        ("Number of traces", str(total)),
        ("Sum of per-trace fitness", f"{fit_sum:.2f}"),
    ]
    render_distribution_tile_metric(
        rows,
        os.path.join(output_dir, "task25_tile_metric.svg"),
        title="Conformance Ingredients",
        caption="Conformance rate = sum ÷ traces",
    )


def task25_bar_chart(df, output_dir: str):
    """One bar per trace, sorted by fitness (ascending) — exact per-trace fitness,
    no binning. The full sorted shape lets the overall rate be computed; no single
    aggregate is drawn (no mean line), no binary conformant/non-conformant split."""
    fit_sorted = np.sort(df["fitness"].to_numpy(dtype=float))
    n = len(fit_sorted)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    pos = np.arange(n)
    # Thin, edgeless bars so a large log reads as a continuous sorted-fitness curve.
    ax.bar(pos, fit_sorted, color=GREY_MED, width=1.0, linewidth=0)
    ax.set_xlabel("Traces (sorted by fitness)", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Per-Trace Fitness, Sorted", fontsize=FONT_TITLE)
    ax.set_ylim(0, 1.05)
    ax.set_xlim(-0.5, max(n - 0.5, 0.5))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_bar_chart.svg"))


def task25_table(df, output_dir: str):
    """Frequency table of the EXACT per-trace fitness values: Fitness | # Traces |
    % of Traces, one row per distinct value (descending). No ranges/bins, so the
    weighted mean — the overall conformance rate — is exactly computable; no
    handed-over aggregate row."""
    total = len(df)
    # Group by the exact fitness value (rounded to 3 dp — fitness precision is far
    # finer than the answer buckets, so this hides nothing the rate needs).
    counts = (
        df["fitness"].round(3)
        .value_counts()
        .sort_index(ascending=False)
    )
    cell_text = [
        [f"{val:.3f}", str(int(c)), f"{(c / total * 100):.1f}%" if total else "0.0%"]
        for val, c in counts.items()
    ]
    fig_h = max(3.0, 1.0 + len(cell_text) * 0.32)
    fig, ax = plt.subplots(figsize=(8.0, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Fitness (0–1)", "# Traces", "% of Traces"],
        bbox=[0.08, 0.03, 0.84, 0.86],
        col_widths=[0.40, 0.30, 0.30],
        font_size=10,
        cell_pad=0.08,
    )
    ax.set_title("Per-Trace Fitness Values", fontsize=FONT_TITLE, pad=10)
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
    task25_table(fitness_df, output_dir)
