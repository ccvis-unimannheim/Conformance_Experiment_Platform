"""
tasks/task02.py – Task ID 2: Confirm / Present / Process conformance.

Single idiom: Tile Metric — overall (sub-)log fitness as a simple percentage.
The tile is visually identical to task06's tile; rendering logic lives in shared.py.

The question this task poses is whether behaviour predominantly follows the
model; `predominant_threshold` draws the reference line the reader judges that
against. How participants answer is chosen per experiment on /answer-format.

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


PARAM_SPEC = [
    {
        "key": "predominant_threshold",
        "label": "Predominant-conformance threshold (fitness 0–1 above which behaviour predominantly follows the model)",
        "hint": "Behaviour counts as predominantly conforming when a trace's fitness is above this value",
        "widget": "threshold",
        "default": DEFAULT_PREDOMINANT_THRESHOLD,
        "required": False,
    },
]


def validate_params(log, params) -> list:
    """Reject an out-of-range predominant threshold. The threshold is optional
    (defaults to 0.8); only a supplied value is checked."""
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


import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

from shared import (
    render_fitness_tile_metric, save_svg, make_table,
    GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)


def task02_bar_chart(df, output_dir: str, predominant_threshold):
    """Single bar: overall mean fitness on a fixed 0–1 axis (the 'number' as a bar).

    A dashed reference line marks the predominant threshold neutrally when set;
    whether the bar clears it is left for the participant to judge.
    """
    avg = float(df["fitness"].mean())

    fig, ax = plt.subplots(figsize=(4.5, 5))
    bar = ax.bar(["Overall"], [avg], color=GREY_DARK, edgecolor="white", width=0.3)[0]
    ax.text(bar.get_x() + bar.get_width() / 2, avg + 0.018, f"{avg:.3f}",
            ha="center", va="bottom", fontsize=FONT_ANNOT)

    # Neutral threshold reference line (only when threshold is set). It crosses
    # the dark bar, so a white outline keeps it visible there, and it is named
    # in a legend below the axes: a label beside the line landed on the bar,
    # dark text on navy.
    if predominant_threshold is not None:
        ax.axhline(predominant_threshold, color="#444444", linestyle="--", linewidth=1.4,
                   path_effects=[pe.Stroke(linewidth=3.2, foreground="white"), pe.Normal()],
                   label=f"Fitness Threshold = {predominant_threshold:.2f}")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False,
                  fontsize=FONT_ANNOT)

    # Headroom above the bar so the value label never collides with the title;
    # ticks stay 0–1 to keep the "fixed 0–1 axis" reading.
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylabel("Mean Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Overall Process Conformance", fontsize=FONT_TITLE, pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task02_bar_chart.svg"))


def task02_table(df, output_dir: str, predominant_threshold):
    """One row: Mean Fitness | Fitness Threshold (when set).

    Exactly what the tile and the bar chart state, so the idioms differ only in
    encoding. Trace counts and % conformant used to be here too; the latter cut
    at fitness 1.0 beside a 0.8 threshold, a second, conflicting standard.
    """
    overall = float(df["fitness"].mean()) if len(df) else 0.0
    cell_text = [[f"{overall:.3f}"]]
    col_labels = ["Mean Fitness"]
    if predominant_threshold is not None:
        cell_text[0].append(f"{predominant_threshold:.2f}")
        col_labels.append("Fitness Threshold")
    col_widths = [1.0 / len(col_labels)] * len(col_labels)

    fig, ax = plt.subplots(figsize=(6, 2.8))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.08, 0.20, 0.84, 0.55],
        col_widths=col_widths,
        font_size=11,
        scale_xy=(1, 1.9),
        cell_pad=0.12,
    )
    ax.set_title("Overall Conformance Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task02_table.svg"))


def generate(df, output_dir: str,
             predominant_threshold=DEFAULT_PREDOMINANT_THRESHOLD):
    """Generate all Task ID 2 SVGs into output_dir.

    predominant_threshold : float or None
        Fitness level (0–1) regarded as the threshold for "predominantly"
        following the desired executions. When None (left empty by admin),
        threshold annotations are omitted from all idioms.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 2 visualizations ---")
    if predominant_threshold is not None:
        logger.info(f"      Predominant threshold: {predominant_threshold:.2f}")
    else:
        logger.info("      Predominant threshold: not set (no annotation)")

    if df is None or df.empty:
        logger.warning("      Skipped Task 2: empty fitness DataFrame.")
        render_fitness_tile_metric(
            0.0, os.path.join(output_dir, "task02_tile_metric.svg"),
            metric_label="Mean Fitness", threshold_label="Fitness Threshold",
            as_fraction=True)
        return

    mean_fitness = float(df["fitness"].mean())
    logger.info(f"      -> Mean fitness: {mean_fitness:.3f}")
    render_fitness_tile_metric(
        mean_fitness, os.path.join(output_dir, "task02_tile_metric.svg"),
        threshold_pct=predominant_threshold,
        metric_label="Mean Fitness", threshold_label="Fitness Threshold",
        as_fraction=True)
    task02_bar_chart(df, output_dir, predominant_threshold)
    task02_table(df, output_dir, predominant_threshold)
