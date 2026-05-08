"""
tasks/task3.py – Task 3: Violation type summaries across all traces.

Public API:
    generate(alignments, output_dir)
"""

import logging

logger = logging.getLogger(__name__)

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import save_svg, make_table, alignment_pairs_to_rows, BLUE, ORANGE, RED


# ---------------------------------------------------------------------------
# Task 3 – Violation type summaries across all traces
# ---------------------------------------------------------------------------

# Task 3 helpers
TASK3_TYPE_LABELS = {
    "Model Move": "Model Move\n(Missing in Log)",
    "Log Move": "Log Move\n(Unexpected in Log)",
    "Mismatch Move": "Mismatch Move\n(Log/Model differ)",
}


def task3_violation_summary_dataframe(alignments):
    """Count violation move types across all trace alignments."""
    rows = []
    for trace_idx, result in enumerate(alignments):
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            move_type = step["moveType"]
            if move_type == "Synchronous Move":
                continue
            rows.append({
                "trace_index": trace_idx,
                "move_type": move_type,
                "violation_type": TASK3_TYPE_LABELS.get(move_type, move_type),
                "activity": step["model_move"] if move_type == "Model Move" else step["log_move"],
            })

    if rows:
        raw = pd.DataFrame(rows)
        summary = (
            raw.groupby(["move_type", "violation_type"], as_index=False)
            .agg(count=("move_type", "size"), traces=("trace_index", "nunique"))
        )
    else:
        summary = pd.DataFrame(columns=["move_type", "violation_type", "count", "traces"])

    order = ["Model Move", "Log Move", "Mismatch Move"]
    summary["order"] = summary["move_type"].apply(lambda x: order.index(x) if x in order else len(order))
    summary = summary.sort_values(["order", "violation_type"]).drop(columns=["order"]).reset_index(drop=True)
    total = int(summary["count"].sum()) if not summary.empty else 0
    summary["percentage"] = (summary["count"] / total * 100) if total else 0.0
    logger.info(f"      -> Violation moves: {total}")
    return summary


# Task 3 visualizations
def task3_bar_chart(df: pd.DataFrame, output_dir: str):
    """Bar chart: occurrence count by violation type."""
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    colors = [BLUE if mt == "Model Move" else RED if mt == "Log Move" else ORANGE for mt in df["move_type"]]
    bars = ax.bar(df["violation_type"], df["count"], color=colors, edgecolor="white", width=0.55, alpha=0.88)
    ymax = max(df["count"].max(), 1)
    for bar, val in zip(bars, df["count"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.015,
            f"{int(val)}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )
    ax.set_xlabel("Violation Type", fontsize=11)
    ax.set_ylabel("Number of Violations", fontsize=11)
    ax.set_title("Violation Type Counts", fontsize=13, fontweight="bold")
    ax.set_ylim(0, ymax * 1.16)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelrotation=15)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_bar_chart.svg"))


def task3_heatmap(df: pd.DataFrame, output_dir: str):
    """Heatmap: one count cell per violation type."""
    labels = df["violation_type"].tolist()
    values = df["count"].to_numpy(dtype=float).reshape(-1, 1)

    fig_h = max(3.2, 1.1 + len(labels) * 0.85)
    fig, ax = plt.subplots(figsize=(6.5, fig_h))
    im = ax.imshow(values, cmap="YlGnBu", aspect="auto")
    ax.set_xticks([0])
    ax.set_xticklabels(["Count"], fontsize=11)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_ylabel("Violation Type", fontsize=11)
    ax.set_title("Violation Type Heatmap", fontsize=13, fontweight="bold")
    max_val = max(df["count"].max(), 1)
    min_val = df["count"].min() if not df.empty else 0
    midpoint = min_val + (max_val - min_val) * 0.50
    for i, val in enumerate(df["count"]):
        color = "white" if val > midpoint else "#222222"
        ax.text(0, i, f"{int(val)}", ha="center", va="center", fontsize=12, fontweight="bold", color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.08, pad=0.04)
    cbar.set_label("Number of Violations", fontsize=10)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_heatmap.svg"))


def task3_pie_chart(df: pd.DataFrame, output_dir: str):
    """Pie chart: proportion of violation move types."""
    colors = [BLUE if mt == "Model Move" else RED if mt == "Log Move" else ORANGE for mt in df["move_type"]]
    labels = [label.replace("\n", " ") for label in df["violation_type"]]

    fig, ax = plt.subplots(figsize=(7, 5.5))
    wedges, texts, autotexts = ax.pie(
        df["count"],
        colors=colors,
        startangle=110,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 1 else "",
        pctdistance=0.72,
        wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops=dict(fontsize=9, color="#222222"),
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.10), ncol=1, frameon=False, fontsize=9)
    ax.set_title("Violation Types", fontsize=13, fontweight="bold")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_pie_chart.svg"))


def task3_table(df: pd.DataFrame, output_dir: str):
    """Table: violation type, count and percentage."""
    total = int(df["count"].sum())
    cell_text = [
        [row["violation_type"].replace("\n", " "), f"{int(row['count'])}", f"{row['percentage']:.2f}%"]
        for _, row in df.iterrows()
    ]
    cell_text.append(["Total", f"{total}", "100.00%" if total else "0.00%"])
    col_labels = ["Violation Type", "Count", "Percentage"]

    fig_h = max(2.6, 1.2 + len(cell_text) * 0.55)
    fig, ax = plt.subplots(figsize=(8, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.05, 0.05, 0.90, 0.78],
        font_size=10,
        scale_xy=(1, 1.7),
        highlight_last_row=True,
    )
    ax.set_title("Violation Type Summary", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_table.svg"))


def task3_table_and_bar_chart(df: pd.DataFrame, output_dir: str):
    """Composite: compact summary table and horizontal bar chart."""
    total = int(df["count"].sum())
    fig = plt.figure(figsize=(13.5, 4.8))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.05, 1.70], wspace=0.62)
    ax_table = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    ax_table.axis("off")
    cell_text = [
        [row["violation_type"], f"{int(row['count'])}", f"{row['percentage']:.2f}%"]
        for _, row in df.iterrows()
    ]
    cell_text.append(["Total", f"{total}", "100.00%" if total else "0.00%"])
    make_table(
        ax_table,
        cell_text=cell_text,
        col_labels=["Violation", "Count", "%"],
        bbox=[0.02, 0.22, 0.92, 0.58],
        col_widths=[0.56, 0.22, 0.22],
        font_size=8.5,
        scale_xy=(1, 1.0),
        highlight_last_row=True,
    )
    ax_table.set_title("Table", fontsize=13, fontweight="bold", pad=10)

    plot_df = df.sort_values("count", ascending=True)
    colors = [BLUE if mt == "Model Move" else RED if mt == "Log Move" else ORANGE for mt in plot_df["move_type"]]
    ax_bar.barh(plot_df["violation_type"], plot_df["count"], color=colors, alpha=0.9)
    xmax = max(plot_df["count"].max(), 1)
    for y, val in enumerate(plot_df["count"]):
        ax_bar.text(val + xmax * 0.015, y, f"{int(val)}", va="center", fontsize=10, fontweight="bold")
    ax_bar.set_xlabel("Number of Violations", fontsize=10)
    ax_bar.set_title("Bar Chart", fontsize=13, fontweight="bold", pad=10)
    ax_bar.tick_params(axis="y", pad=8)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)
    fig.suptitle("Task 3 Violation Type Summary", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_svg(fig, os.path.join(output_dir, "task3_table_and_bar_chart.svg"))




# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(alignments, output_dir: str):
    """Generate all Task 3 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 3 visualizations ---")
    df = task3_violation_summary_dataframe(alignments)
    if df.empty:
        logger.warning("      Skipped Task 3: no violation moves found.")
        return
    task3_bar_chart(df, output_dir)
    task3_heatmap(df, output_dir)
    task3_pie_chart(df, output_dir)
    task3_table(df, output_dir)
    task3_table_and_bar_chart(df, output_dir)
