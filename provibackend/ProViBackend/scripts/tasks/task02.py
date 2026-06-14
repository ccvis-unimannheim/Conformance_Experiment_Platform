"""
tasks/task02.py – Task ID 2: Confirm / Present / Process conformance.

Single idiom: Tile Metric — overall (sub-)log fitness as a simple percentage.
The tile is visually identical to task06's tile; rendering logic lives in shared.py.

Public API:
    generate(df, output_dir, predominant_threshold=0.8)
        df                   – fitness summary DataFrame from io_helpers.fitness_summary_dataframe
        output_dir           – directory where SVGs are written
        predominant_threshold – fitness level (0–1) regarded as the threshold
                                for "predominantly" following the desired
                                executions. Shown neutrally as a reference value
                                on every idiom; no pass/fail verdict is rendered.
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["tile_metric", "bar_chart", "table"]

# Default fitness level above which behaviour counts as "predominantly"
# following the model. Overridable via generate(predominant_threshold=...).
DEFAULT_PREDOMINANT_THRESHOLD = 0.8

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 2)
#
# Task 2 (AUTO): overall (sub-)log fitness as a percentage (pct), plus an
# optional Yes/No reading of whether behaviour "predominantly" follows the model
# (mc-single, decided against an optional predominant threshold, default 0.8).
# The task runs with zero admin input; the admin may override the threshold.
# ---------------------------------------------------------------------------
GT_TIER = "AUTO"

PARAM_SPEC = [
    {
        "key": "predominant_threshold",
        "label": "Predominant-conformance threshold (fitness 0–1 above which behaviour predominantly follows the model)",
        "widget": "threshold",
        "default": DEFAULT_PREDOMINANT_THRESHOLD,
        "required": False,
    },
]

ANSWER_FORMATS = [
    {"key": "pct",       "gt_shape": "scalar", "decisive_default": True},
    {"key": "mc-single", "gt_shape": "mc",     "decisive_default": False},
]


def validate_params(log, params) -> list:
    """Reject an out-of-range predominant threshold. The threshold is optional
    (defaults to 0.8); only a supplied value is checked (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §10)."""
    raw = params.get("predominant_threshold")
    if raw is None or raw == "":
        return []
    try:
        thr = float(raw)
    except (TypeError, ValueError):
        return [f"Predominant threshold '{raw}' is not a number."]
    if not (0.0 <= thr <= 1.0):
        return ["Predominant threshold must be between 0 and 1."]
    return []


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Overall log fitness as the ground truth (design doc §2 row 2, AUTO tier).

    Returns the raw GroundTruthBlock fields the backend assembles
    (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §3, §8):
      - "pct"       -> {"value": "96%"} (overall mean fitness, integer percent).
      - "mc-single" -> Yes/No options, the side matching whether overall fitness
                       meets the predominant threshold flagged correct.
    """
    overall = (
        float(fitness_df["fitness"].mean())
        if fitness_df is not None and len(fitness_df) else 0.0
    )

    if answer_format == "mc-single":
        thr = float(params.get("predominant_threshold", DEFAULT_PREDOMINANT_THRESHOLD))
        predominant = overall >= thr
        return {
            "value": None,
            "options": [
                {"label": "Yes", "value": "yes", "correct": predominant},
                {"label": "No",  "value": "no",  "correct": not predominant},
            ],
        }

    return {"value": f"{round(overall * 100)}%"}


import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import (
    render_fitness_tile_metric, save_svg, make_table,
    GREY_MED, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)


def task02_bar_chart(df, output_dir: str, predominant_threshold: float):
    """Single bar: overall mean fitness on a fixed 0–1 axis (the 'number' as a bar).

    A dashed reference line marks the predominant threshold neutrally; whether
    the bar clears it is left for the participant to judge.
    """
    avg = float(df["fitness"].mean())

    fig, ax = plt.subplots(figsize=(4.5, 5))
    bar = ax.bar(["Overall"], [avg], color=GREY_MED, edgecolor="white", width=0.3)[0]
    ax.text(bar.get_x() + bar.get_width() / 2, avg + 0.018, f"{avg:.3f}",
            ha="center", va="bottom", fontsize=FONT_ANNOT)

    # Neutral threshold reference line + label (no pass/fail verdict).
    ax.axhline(predominant_threshold, color="#444444", linestyle="--", linewidth=1.4)
    ax.text(0.98, predominant_threshold + 0.012,
            f"Threshold = {predominant_threshold:.2f}",
            transform=ax.get_yaxis_transform(), ha="right", va="bottom",
            fontsize=FONT_ANNOT, color="#444444")

    # Headroom above the bar so the value label never collides with the title;
    # ticks stay 0–1 to keep the "fixed 0–1 axis" reading.
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylabel("Overall Conformance Rate (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Overall Process Conformance", fontsize=FONT_TITLE, pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task02_bar_chart.svg"))


def task02_table(df, output_dir: str, predominant_threshold: float):
    """One row: #Traces | #Conformant | % Conformant | Overall Fitness | Threshold."""
    n = len(df)
    n_conform = int(df["is_fit"].sum())
    pct = (n_conform / n * 100) if n else 0.0
    overall = float(df["fitness"].mean()) if n else 0.0
    cell_text = [[str(n), str(n_conform), f"{pct:.1f}%", f"{overall:.4f}",
                  f"{predominant_threshold:.2f}"]]

    fig, ax = plt.subplots(figsize=(10, 2.8))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["#Traces", "#Conformant", "% Conformant", "Overall Fitness",
                    "Threshold"],
        bbox=[0.04, 0.20, 0.92, 0.55],
        col_widths=[0.20, 0.22, 0.22, 0.20, 0.16],
        font_size=11,
        scale_xy=(1, 1.9),
        cell_pad=0.12,
    )
    ax.set_title("Overall Conformance Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task02_table.svg"))


def generate(df, output_dir: str,
             predominant_threshold: float = DEFAULT_PREDOMINANT_THRESHOLD):
    """Generate all Task ID 2 SVGs into output_dir.

    predominant_threshold : float
        Fitness level (0–1) regarded as the threshold for "predominantly"
        following the desired executions. Shown neutrally on the tile, bar chart
        and table as a reference value — no pass/fail verdict is rendered, so
        participants decide for themselves whether the behaviour predominates.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 2 visualizations ---")
    logger.info(f"      Predominant threshold: {predominant_threshold:.2f}")

    if df is None or df.empty:
        logger.warning("      Skipped Task 2: empty fitness DataFrame.")
        render_fitness_tile_metric(0.0, os.path.join(output_dir, "task02_tile_metric.svg"))
        return

    avg = float(df["fitness"].mean()) * 100
    logger.info(f"      -> Overall conformance rate: {avg:.2f}%")
    render_fitness_tile_metric(avg, os.path.join(output_dir, "task02_tile_metric.svg"),
                               threshold_pct=predominant_threshold * 100)
    task02_bar_chart(df, output_dir, predominant_threshold)
    task02_table(df, output_dir, predominant_threshold)
