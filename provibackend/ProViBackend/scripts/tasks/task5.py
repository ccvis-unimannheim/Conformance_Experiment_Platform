"""
tasks/task5.py – Task 5: Which percentage of traces fall into which conformance category?

Visualizations: Bar Chart, Pie Chart, Scatter Plot, Heatmap, Table.

Public API:
    generate(df, output_dir)
        df          – fitness summary DataFrame from io_helpers.fitness_summary_dataframe
        output_dir  – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "pie_chart", "scatterplot", "heatmap", "table"]

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.colors import LinearSegmentedColormap

from shared import save_svg, make_table

# ---------------------------------------------------------------------------
# Range definitions
# ---------------------------------------------------------------------------

DEFAULT_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]   # 1.01 so fitness == 1.0 lands in last bin
DEFAULT_LABELS = ["0.0 – 0.2", "0.2 – 0.4", "0.4 – 0.6", "0.6 – 0.8", "0.8 – 1.0"]
HIGH_FITNESS_BINS = [0.80, 0.85, 0.90, 0.95, 1.0]
HIGH_FITNESS_LABELS = ["0.80 – 0.85", "0.85 – 0.90", "0.90 – 0.95", "0.95 – <1.00", "1.00"]

# Light-blue → dark-blue palette (extended for adaptive ranges)
RANGE_COLORS = ["#C6DBEF", "#9ECAE1", "#6BAED6", "#3182BD", "#08519C", "#08306B"]


def _task5_color_list(n: int):
    """Return a stable blue palette with enough colors for adaptive bins."""
    if n <= len(RANGE_COLORS):
        return RANGE_COLORS[:n]
    cmap = LinearSegmentedColormap.from_list("task5_blues", ["#C6DBEF", "#08306B"])
    return [cmap(i / max(n - 1, 1)) for i in range(n)]


def _build_high_fitness_range_df(fitness: pd.Series) -> pd.DataFrame:
    """Use narrow high-end bins plus an exact-1.0 bucket for concentrated logs."""
    nonperfect = fitness[fitness < 1.0]
    rows = []
    for lo, hi, label in zip(HIGH_FITNESS_BINS[:-1], HIGH_FITNESS_BINS[1:], HIGH_FITNESS_LABELS[:-1]):
        rows.append({
            "range": label,
            "count": int(((nonperfect >= lo) & (nonperfect < hi)).sum()),
        })
    rows.append({"range": HIGH_FITNESS_LABELS[-1], "count": int((fitness >= 1.0).sum())})
    total = len(fitness)
    result = pd.DataFrame(rows)
    result["percentage"] = result["count"] / total * 100 if total else 0.0
    return result


def _build_quantile_range_df(fitness: pd.Series, max_bins: int = 5) -> pd.DataFrame:
    """Use quantile bins when the distribution is not well served by fixed ranges."""
    quantiles = np.linspace(0, 1, max_bins + 1)
    edges = np.unique(np.quantile(fitness, quantiles))
    if len(edges) <= 2:
        return pd.DataFrame()
    edges[0] = max(0.0, edges[0])
    edges[-1] = min(1.0, edges[-1])
    labels = []
    counts = []
    for idx, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        if idx == len(edges) - 2:
            mask = (fitness >= lo) & (fitness <= hi)
        else:
            mask = (fitness >= lo) & (fitness < hi)
        labels.append(f"{lo:.2f} – {hi:.2f}")
        counts.append(int(mask.sum()))
    total = len(fitness)
    return pd.DataFrame({
        "range": labels,
        "count": counts,
        "percentage": [count / total * 100 if total else 0.0 for count in counts],
    })


def _build_range_df(df) -> pd.DataFrame:
    """Count and percentage of traces per adaptive conformance range."""
    fitness = df["fitness"].astype(float)
    if fitness.empty:
        return pd.DataFrame(columns=["range", "count", "percentage"])

    if fitness.min() >= 0.8:
        return _build_high_fitness_range_df(fitness)

    default_buckets = pd.cut(
        fitness,
        bins=DEFAULT_BINS,
        labels=DEFAULT_LABELS,
        right=False,
        include_lowest=True,
    )
    default_counts = default_buckets.value_counts().reindex(DEFAULT_LABELS, fill_value=0)
    active_default_bins = int((default_counts > 0).sum())
    if active_default_bins >= 3:
        total = len(fitness)
        return pd.DataFrame({
            "range": DEFAULT_LABELS,
            "count": default_counts.values,
            "percentage": default_counts.values / total * 100 if total else [0.0] * len(DEFAULT_LABELS),
        })

    quantile_df = _build_quantile_range_df(fitness)
    if not quantile_df.empty:
        return quantile_df

    buckets = pd.cut(
        fitness,
        bins=DEFAULT_BINS,
        labels=DEFAULT_LABELS,
        right=False,
        include_lowest=True,
    )
    counts = buckets.value_counts().reindex(DEFAULT_LABELS, fill_value=0)
    total  = len(df)
    result = pd.DataFrame({
        "range":      DEFAULT_LABELS,
        "count":      counts.values,
        "percentage": counts.values / total * 100 if total else [0.0] * len(DEFAULT_LABELS),
    })
    return result


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task5_bar_chart(range_df: pd.DataFrame, output_dir: str):
    """Bar chart: percentage of traces per conformance range."""
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        range_df["range"],
        range_df["percentage"],
        color=_task5_color_list(len(range_df)),
        edgecolor="white",
        width=0.6,
    )
    for bar, pct in zip(bars, range_df["percentage"]):
        if pct > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{pct:.1f}%",
                ha="center", va="bottom", fontsize=10, fontweight="bold",
            )
    ax.set_xlabel("Conformance Rate divided into Ranges", fontsize=11)
    ax.set_ylabel("Percentage of Traces (%)", fontsize=11)
    ax.set_title("Distribution of Traces across Conformance Ranges", fontsize=13, fontweight="bold")
    ax.set_ylim(0, max(range_df["percentage"].max() * 1.15, 5))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task5_bar_chart.svg"))


def task5_pie_chart(range_df: pd.DataFrame, output_dir: str):
    """Pie chart: proportion of traces per conformance range."""
    # Only include ranges with at least one trace
    active = range_df[range_df["count"] > 0]
    if active.empty:
        active = range_df

    fig, ax = plt.subplots(figsize=(7, 5.5))
    wedges, texts, autotexts = ax.pie(
        active["count"],
        labels=active["range"],
        colors=[_task5_color_list(len(range_df))[i] for i in active.index],
        startangle=90,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 1 else "",
        pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops=dict(fontsize=9),
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax.set_title("Conformance Range Distribution", fontsize=13, fontweight="bold")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task5_pie_chart.svg"))


def task5_scatter_plot(range_df: pd.DataFrame, output_dir: str):
    """
    Bubble scatter plot: x = conformance range, y = percentage of traces,
    marker area proportional to trace count; count shown inside each bubble.
    """
    n = len(range_df)
    x = np.arange(n, dtype=float)
    counts = range_df["count"].values.astype(float)
    pcts   = range_df["percentage"].values.astype(float)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.text(0.5, 0.93, "Scatter Plot", ha="center", fontsize=13, fontweight="bold")
    fig.text(
        0.5, 0.885,
        "Bubble size proportional to trace count per conformance range",
        ha="center", fontsize=9, color="#555555",
    )

    max_c = float(counts.max()) if len(counts) else 0.0
    if max_c <= 0:
        max_c = 1.0
    # Matplotlib scatter `s` is marker area in points^2
    s_min, s_max = 120.0, 3200.0
    areas = (counts / max_c) * (s_max - s_min) + s_min
    mask = counts > 0

    if mask.any():
        ax.scatter(
            x[mask],
            pcts[mask],
            s=areas[mask],
            c="#E74C3C",
            alpha=0.72,
            edgecolors="#B03A2E",
            linewidths=0.8,
            zorder=3,
        )
        for xi, pct, c in zip(x[mask], pcts[mask], counts[mask]):
            fs = max(8, min(13, 10 + 2.0 * (c / max_c)))
            txt = ax.text(
                xi, pct, f"{int(c):,}",
                ha="center", va="center",
                fontsize=fs, fontweight="bold", color="#1A1A1A",
                zorder=4,
            )
            txt.set_path_effects(
                [pe.withStroke(linewidth=2.8, foreground="white")]
            )

    ax.set_xticks(x)
    ax.set_xticklabels(range_df["range"], rotation=45, ha="right", fontsize=9)
    ax.set_xlabel("Conformance Rate divided into ranges", fontsize=11)
    ax.set_ylabel("Percentage of Traces (%)", fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, which="major", axis="both", linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(rect=[0, 0, 1, 0.82])
    save_svg(fig, os.path.join(output_dir, "task5_scatter_plot.svg"))


def task5_heatmap(range_df: pd.DataFrame, output_dir: str):
    """
    Horizontal heatmap: one cell per range, color encodes percentage,
    light blue (low) → dark blue (high).
    """
    pcts   = range_df["percentage"].values.reshape(1, -1)
    cmap   = LinearSegmentedColormap.from_list("lb_db", ["#C6DBEF", "#08519C"])
    vmax   = max(pcts.max(), 1.0)

    fig, ax = plt.subplots(figsize=(10, 2.4))
    im = ax.imshow(pcts, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")

    ax.set_xticks(np.arange(len(range_df)))
    ax.set_xticklabels(range_df["range"], fontsize=10)
    ax.set_yticks([])
    ax.set_xlabel("Conformance Rate Range", fontsize=11)
    ax.set_title("Percentage of Traces per Conformance Range", fontsize=13, fontweight="bold")

    # Value labels inside each cell
    midpoint = vmax * 0.55
    for col_idx, pct in enumerate(range_df["percentage"]):
        text_color = "white" if pct > midpoint else "#222222"
        ax.text(col_idx, 0, f"{pct:.1f}%",
                ha="center", va="center",
                fontsize=12, fontweight="bold", color=text_color)

    cbar = fig.colorbar(im, ax=ax, orientation="vertical", fraction=0.04, pad=0.02)
    cbar.set_label("Percentage (%)", fontsize=9)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task5_heatmap.svg"))


def task5_table(range_df: pd.DataFrame, output_dir: str):
    """Table: Conformance Range | Count (Cases) | Percentage."""
    total = int(range_df["count"].sum())
    cell_text = [
        [row["range"], str(int(row["count"])), f"{row['percentage']:.2f}%"]
        for _, row in range_df.iterrows()
    ]
    cell_text.append(["Total", str(total), "100.00%" if total else "0.00%"])

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.52)
    fig, ax = plt.subplots(figsize=(7, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Conformance Range", "Count (Cases)", "Percentage"],
        bbox=[0.05, 0.05, 0.90, 0.78],
        col_widths=[0.45, 0.28, 0.27],
        font_size=11,
        scale_xy=(1, 1.7),
        highlight_last_row=True,
    )
    ax.set_title("Conformance Range Summary", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task5_table.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(df, output_dir: str):
    """Generate all Task 5 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 5 visualizations ---")
    range_df = _build_range_df(df)
    logger.info(f"      -> Range counts: {dict(zip(range_df['range'], range_df['count']))}")
    task5_bar_chart(range_df, output_dir)
    task5_pie_chart(range_df, output_dir)
    task5_scatter_plot(range_df, output_dir)
    task5_heatmap(range_df, output_dir)
    task5_table(range_df, output_dir)
