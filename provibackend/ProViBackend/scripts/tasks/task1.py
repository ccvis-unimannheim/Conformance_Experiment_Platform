"""
tasks/task1.py – Task 1: Overall degree of conformance.

Visualizations: Bar Chart, Box Plot, Donut Chart, Scatter Plot, Heatmap, Table, Tile Metric.

Public API:
    generate(df, output_dir)
        df          – fitness summary DataFrame from io_helpers.fitness_summary_dataframe
        output_dir  – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "boxplot", "donut_chart", "scatterplot", "heatmap", "table", "tile_metric"]

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

from shared import save_svg, make_table, BLUE, ORANGE, TEAL, GREEN, RED, FONT_TITLE, FONT_LABEL, FONT_ANNOT


def task1_bar_chart(df, output_dir: str):
    conform     = int(df["is_fit"].sum())
    non_conform = len(df) - conform

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(
        ["Conform Traces", "Non-Conform Traces"],
        [conform, non_conform],
        color=[BLUE, ORANGE], edgecolor="white", width=0.5,
    )
    for bar, val in zip(bars, [conform, non_conform]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(conform, non_conform) * 0.015,
            str(val), ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Conform vs. Non-Conform Traces", fontsize=FONT_TITLE)
    ax.set_ylim(0, max(conform, non_conform) * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task1_bar_chart.svg"))


def task1_box_plot(df, output_dir: str):
    fig, ax = plt.subplots(figsize=(4, 6))
    ax.boxplot(
        df["fitness"].values,
        vert=True, patch_artist=True, widths=0.4,
        flierprops=dict(marker="D", markerfacecolor=TEAL, markersize=5,
                        linestyle="none", markeredgecolor=TEAL),
        medianprops=dict(color="white", linewidth=2),
        boxprops=dict(facecolor=TEAL, color=TEAL, alpha=0.85),
        whiskerprops=dict(color=TEAL, linewidth=1.5),
        capprops=dict(color=TEAL, linewidth=1.5),
    )
    ax.set_xticks([1])
    ax.set_xticklabels(["Log"])
    ax.set_ylabel("Conformance Rate (0.0 – 1.0)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Conformance Rate Distribution", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task1_box_plot.svg"))


def task1_donut_chart(df, output_dir: str):
    conform     = int(df["is_fit"].sum())
    non_conform = len(df) - conform
    total       = len(df)

    labels = [
        f"Conform\n{conform} ({conform / total * 100:.1f}%)",
        f"Non-Conform\n{non_conform} ({non_conform / total * 100:.1f}%)",
    ]
    fig, ax = plt.subplots(figsize=(6, 5))
    wedges, _ = ax.pie(
        [conform, non_conform],
        colors=[BLUE, ORANGE], startangle=90,
        wedgeprops=dict(width=0.6, edgecolor="white", linewidth=2),
    )
    ax.text(0, 0, "Conform vs.\nnon-conform\ncases", ha="center", va="center",
            fontsize=FONT_ANNOT, color="#555555")
    ax.legend(
        handles=[mpatches.Patch(color=BLUE, label=labels[0]),
                 mpatches.Patch(color=ORANGE, label=labels[1])],
        loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False, fontsize=FONT_ANNOT,
    )
    ax.set_title("Share of Conformant Traces", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task1_donut_chart.svg"))


def task1_scatter_plot(df, output_dir: str):
    colors = [GREEN if fit else RED for fit in df["is_fit"]]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.scatter(df["trace_index"], df["fitness"], c=colors, s=15, alpha=0.6, linewidths=0)
    ax.set_xlabel("Traces in Log ordered by time", fontsize=FONT_LABEL)
    ax.set_ylabel("Conformance Rate", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Conformance Rate per Trace", fontsize=FONT_TITLE)
    ax.legend(
        handles=[mpatches.Patch(color=GREEN, label="Conform: True"),
                 mpatches.Patch(color=RED,   label="Conform: False")],
        frameon=False, fontsize=FONT_ANNOT,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task1_scatter_plot.svg"))


def task1_heatmap(df, output_dir: str):
    avg  = df["fitness"].mean()
    cmap = "Greys"

    fig, ax = plt.subplots(figsize=(3.5, 3))
    im = ax.imshow(np.array([[avg]]), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    text_color = "white" if avg > 0.5 else "#222222"
    ax.text(0, 0, f"{avg:.2%}", ha="center", va="center",
            fontsize=22, color=text_color)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Average Conformance Rate", fontsize=FONT_TITLE)
    cbar = fig.colorbar(im, ax=ax, orientation="vertical", fraction=0.08, pad=0.04)
    cbar.set_label("Conformance Rate", fontsize=FONT_ANNOT)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_ticklabels(["0%", "25%", "50%", "75%", "100%"])
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task1_heatmap.svg"))


def task1_table(df, output_dir: str):
    conform     = int(df["is_fit"].sum())
    non_conform = len(df) - conform
    rate        = df["fitness"].mean() * 100

    cell_text = [[str(conform), str(non_conform), f"{rate:.2f}%"]]
    # Taller canvas + wrapped headers so cell text is not clipped (mpl table centers text; PAD is weak for center)
    fig_h = max(3.6, 1.45 + len(cell_text) * 0.58)

    fig, ax = plt.subplots(figsize=(10.0, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=[
            "Total\nConform Traces",
            "Total Non-Conform\nTraces",
            "Conformance\nRate (%)",
        ],
        bbox=[0.03, 0.04, 0.94, 0.80],
        col_widths=[0.32, 0.38, 0.30],
        font_size=11,
        scale_xy=(1.12, 2.05),
        cell_pad=0.14,
    )
    ax.set_title("Conformance Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task1_table.svg"))


def task1_tile_metric(df, output_dir: str):
    avg = df["fitness"].mean() * 100

    fig, ax = plt.subplots(figsize=(4, 3))
    ax.axis("off")
    ax.add_patch(FancyBboxPatch(
        (0.05, 0.05), 0.9, 0.9,
        boxstyle="round,pad=0.02", linewidth=2,
        edgecolor="black", facecolor="white",
        transform=ax.transAxes, clip_on=False,
    ))
    ax.text(0.5, 0.68, "Conformance Rate",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=FONT_TITLE, color="#555555")
    ax.text(0.5, 0.38, f"{avg:.2f}%",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=32, color="#333333")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task1_tile_metric.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(df, output_dir: str):
    """Generate all Task 1 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 1 visualizations ---")
    task1_bar_chart(df, output_dir)
    task1_box_plot(df, output_dir)
    task1_donut_chart(df, output_dir)
    task1_scatter_plot(df, output_dir)
    task1_heatmap(df, output_dir)
    task1_table(df, output_dir)
    task1_tile_metric(df, output_dir)
