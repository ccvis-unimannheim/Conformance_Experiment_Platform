"""
tasks/task02.py – Task ID 2: Confirm / Present / Process conformance.

Single idiom: Tile Metric — overall (sub-)log fitness as a simple percentage.
The tile is visually identical to task06's tile; rendering logic lives in shared.py.

Public API:
    generate(df, output_dir)
        df         – fitness summary DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["tile_metric", "bar_chart", "table"]

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import (
    render_fitness_tile_metric, save_svg, make_table,
    BLUE, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)


def task02_bar_chart(df, output_dir: str):
    """Single bar: overall mean fitness on a fixed 0–1 axis (the 'number' as a bar)."""
    avg = float(df["fitness"].mean())
    fig, ax = plt.subplots(figsize=(4.5, 5))
    bar = ax.bar(["Overall"], [avg], color=BLUE, edgecolor="white", width=0.5)[0]
    ax.text(bar.get_x() + bar.get_width() / 2, avg + 0.018, f"{avg:.3f}",
            ha="center", va="bottom", fontsize=FONT_ANNOT)
    # Headroom above the bar so the value label never collides with the title;
    # ticks stay 0–1 to keep the "fixed 0–1 axis" reading.
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylabel("Overall Conformance Rate (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Overall Process Conformance", fontsize=FONT_TITLE, pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task02_bar_chart.svg"))


def task02_table(df, output_dir: str):
    """One row: #Traces | #Conformant | % Conformant | Overall Fitness."""
    n = len(df)
    n_conform = int(df["is_fit"].sum())
    pct = (n_conform / n * 100) if n else 0.0
    overall = float(df["fitness"].mean()) if n else 0.0
    cell_text = [[str(n), str(n_conform), f"{pct:.1f}%", f"{overall:.4f}"]]

    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["#Traces", "#Conformant", "% Conformant", "Overall Fitness"],
        bbox=[0.04, 0.20, 0.92, 0.55],
        col_widths=[0.24, 0.26, 0.26, 0.24],
        font_size=11,
        scale_xy=(1, 1.9),
        cell_pad=0.12,
    )
    ax.set_title("Overall Conformance Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task02_table.svg"))


def generate(df, output_dir: str):
    """Generate all Task ID 2 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 2 visualizations ---")

    if df is None or df.empty:
        logger.warning("      Skipped Task ID 2: empty fitness DataFrame.")
        render_fitness_tile_metric(0.0, os.path.join(output_dir, "task02_tile_metric.svg"))
        return

    avg = float(df["fitness"].mean()) * 100
    logger.info(f"      -> Overall conformance rate: {avg:.2f}%")
    render_fitness_tile_metric(avg, os.path.join(output_dir, "task02_tile_metric.svg"))
    task02_bar_chart(df, output_dir)
    task02_table(df, output_dir)
