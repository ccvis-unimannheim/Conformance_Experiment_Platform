"""
tasks/task10.py – Task ID 10: Describe / Present / Conformance distribution
(which percentage of traces fall into which conformance category).

Validated idiom mapping (11 idioms = 6 High + 5 Medium):
    HIGH:   stacked_bar, line_graph, horizon_chart, boxplot, heatmap, calendar
    MEDIUM: bar_chart, scatter_plot, table, table_bar_chart, pie_chart

The conformance category bucket definitions are the single source of truth in
shared.py (CONFORMANCE_BINS / CONFORMANCE_LABELS / CONFORMANCE_CATEGORY_NAMES),
reused here and by task01 / task25 / task27 / task33.

Public API:
    generate(df, output_dir, log=None)
        df  – fitness summary DataFrame (trace_index, fitness, is_fit)
        log – PM4Py log; needed for the time-based idioms (line/horizon/heatmap/calendar)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["stacked_bar", "line_graph", "horizon_chart", "boxplot", "heatmap", "calendar",
          "bar_chart", "scatter_plot", "table", "table_bar_chart", "pie_chart"]

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from matplotlib.colors import LinearSegmentedColormap

from shared import (
    save_svg, make_table, render_empty_state_svg, build_fitness_time_series,
    calendar_heatmap, draw_value_heatmap,
    conformance_category_series, conformance_category_counts,
    CONFORMANCE_BINS, CONFORMANCE_LABELS, CONFORMANCE_CATEGORY_NAMES,
    BLUE, ORANGE, GREEN, RED, TEAL,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT, contrasting_text_color,
)
# Reuse: task07's line + horizon renderers for the time-based idioms.
import tasks.task07 as task07

# ---------------------------------------------------------------------------
# Range definitions (buckets extracted to shared.py — single source of truth)
# ---------------------------------------------------------------------------

DEFAULT_BINS = CONFORMANCE_BINS
DEFAULT_LABELS = CONFORMANCE_LABELS
HIGH_FITNESS_BINS = [0.80, 0.85, 0.90, 0.95, 1.0]
HIGH_FITNESS_LABELS = ["0.80 – 0.85", "0.85 – 0.90", "0.90 – 0.95", "0.95 – <1.00", "1.00"]

# Light → dark greyscale palette (extended for adaptive ranges)
RANGE_COLORS = ["#F0F0F0", "#D4D4D4", "#B8B8B8", "#9C9C9C", "#777777", "#555555"]


def _task10_color_list(n: int):
    """Return a stable greyscale palette with enough colors for adaptive bins."""
    if n <= len(RANGE_COLORS):
        return RANGE_COLORS[:n]
    cmap = LinearSegmentedColormap.from_list("task10_greys", ["#F0F0F0", "#555555"])
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

def task10_bar_chart(range_df: pd.DataFrame, output_dir: str):
    """Bar chart: percentage of traces per conformance range."""
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        range_df["range"],
        range_df["percentage"],
        color=_task10_color_list(len(range_df)),
        edgecolor="white",
        width=0.6,
    )
    for bar, pct in zip(bars, range_df["percentage"]):
        if pct > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{pct:.1f}%",
                ha="center", va="bottom", fontsize=FONT_ANNOT,
            )
    ax.set_xlabel("Conformance Rate divided into Ranges", fontsize=FONT_LABEL)
    ax.set_ylabel("Percentage of Traces (%)", fontsize=FONT_LABEL)
    ax.set_title("Traces per Conformance Range", fontsize=FONT_TITLE)
    ax.set_ylim(0, max(range_df["percentage"].max() * 1.15, 5))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task10_bar_chart.svg"))


def task10_pie_chart(range_df: pd.DataFrame, output_dir: str):
    """Pie chart: proportion of traces per conformance range."""
    # Only include ranges with at least one trace
    active = range_df[range_df["count"] > 0]
    if active.empty:
        active = range_df

    active_colors = [_task10_color_list(len(range_df))[i] for i in active.index]
    fig, ax = plt.subplots(figsize=(7, 5.5))
    wedges, texts, autotexts = ax.pie(
        active["count"],
        labels=active["range"],
        colors=active_colors,
        startangle=90,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 1 else "",
        pctdistance=0.75,
        wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops=dict(fontsize=FONT_ANNOT),
    )
    for color, autotext in zip(active_colors, autotexts):
        autotext.set_color(contrasting_text_color(color))
    ax.set_title("Conformance Range Proportions", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task10_pie_chart.svg"))


def task10_table(range_df: pd.DataFrame, output_dir: str):
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
    ax.set_title("Conformance Range Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task10_table.svg"))


# ---------------------------------------------------------------------------
# Added valid idioms (validated mapping)
# ---------------------------------------------------------------------------

def task10_stacked_bar(range_df: pd.DataFrame, output_dir: str):
    """HIGH: one bar for the whole log, segments = conformance categories."""
    path = os.path.join(output_dir, "task10_stacked_bar.svg")
    colors = _task10_color_list(len(range_df))
    fig, ax = plt.subplots(figsize=(10, 3.0))
    left = 0.0
    for (_, row), color in zip(range_df.iterrows(), colors):
        pct = float(row["percentage"])
        if pct <= 0:
            continue
        ax.barh(0, pct, left=left, color=color, edgecolor="white", height=0.55)
        if pct >= 5:
            tc = contrasting_text_color(color) if isinstance(color, str) else "#222222"
            ax.text(left + pct / 2, 0, f"{pct:.1f}%", ha="center", va="center",
                    fontsize=FONT_ANNOT - 1, color=tc)
        left += pct
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel("Percentage of traces (%)", fontsize=FONT_LABEL)
    ax.set_title("Conformance Distribution (whole log)", fontsize=FONT_TITLE)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(handles=[mpatches.Patch(color=c, label=l)
                       for c, l in zip(colors, range_df["range"])],
              loc="upper center", bbox_to_anchor=(0.5, -0.30),
              ncol=min(len(range_df), 5), frameon=False, fontsize=FONT_ANNOT - 1)
    fig.tight_layout()
    save_svg(fig, path)


def task10_line_graph(time_df: pd.DataFrame, output_dir: str):
    """HIGH: mean conformance per time bin (reuses task07's line renderer)."""
    path = os.path.join(output_dir, "task10_line_graph.svg")
    if time_df is None or time_df.empty:
        render_empty_state_svg(path, "Conformance Distribution Over Time",
                               "No timestamp data available.")
        return
    task07.task07_line_graph(time_df, output_dir)
    src = os.path.join(output_dir, "task07_line_graph.svg")
    if os.path.exists(src):
        os.replace(src, path)


def task10_horizon_chart(time_df: pd.DataFrame, output_dir: str):
    """HIGH: the monthly conformance series as horizon strips (reuses task07)."""
    path = os.path.join(output_dir, "task10_horizon_chart.svg")
    if time_df is None or time_df.empty:
        render_empty_state_svg(path, "Conformance Distribution Over Time",
                               "No timestamp data available.")
        return
    task07.task07_horizon_chart(time_df, output_dir)
    src = os.path.join(output_dir, "task07_horizon_chart.svg")
    if os.path.exists(src):
        os.replace(src, path)


def task10_box_plot(fitness_df: pd.DataFrame, output_dir: str):
    """HIGH: per-trace fitness distribution (one box for the whole log)."""
    path = os.path.join(output_dir, "task10_box_plot.svg")
    vals = fitness_df["fitness"].astype(float).values
    fig, ax = plt.subplots(figsize=(4, 6))
    ax.boxplot(
        vals, vert=True, patch_artist=True, widths=0.4,
        boxprops=dict(facecolor=TEAL, color=TEAL, alpha=0.85),
        medianprops=dict(color="white", linewidth=2),
        whiskerprops=dict(color=TEAL, linewidth=1.5),
        capprops=dict(color=TEAL, linewidth=1.5),
        flierprops=dict(marker="D", markerfacecolor=TEAL, markersize=5,
                        linestyle="none", markeredgecolor=TEAL),
    )
    ax.set_xticks([1])
    ax.set_xticklabels(["Log"])
    ax.set_ylabel("Conformance Rate (0.0 – 1.0)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Per-trace Conformance Distribution", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, path)


def task10_heatmap(time_df: pd.DataFrame, output_dir: str):
    """HIGH: month × conformance category, trace count (continuous heatmap)."""
    path = os.path.join(output_dir, "task10_heatmap.svg")
    if time_df is None or time_df.empty:
        render_empty_state_svg(path, "Conformance Category over Months",
                               "No timestamp data available.")
        return
    tdf = time_df.copy()
    tdf["month"] = tdf["start_time"].dt.to_period("M").dt.to_timestamp()
    tdf["cat"] = conformance_category_series(tdf["fitness"]).values
    months = sorted(tdf["month"].unique())
    month_labels = [pd.Timestamp(m).strftime("%b '%y") for m in months]
    data = np.zeros((len(CONFORMANCE_CATEGORY_NAMES), len(months)))
    for ci in range(len(CONFORMANCE_CATEGORY_NAMES)):
        for mj, m in enumerate(months):
            data[ci, mj] = int(((tdf["cat"] == ci) & (tdf["month"] == m)).sum())
    fig, ax = plt.subplots(figsize=(max(8, len(months) * 0.7 + 3), 4.6))
    draw_value_heatmap(fig, ax, data,
                       [f"{n}\n({r})" for n, r in zip(CONFORMANCE_CATEGORY_NAMES, CONFORMANCE_LABELS)],
                       month_labels, xlabel="Month", cbar_label="# Traces",
                       cell_fmt="{:.0f}", rotate_xticks=30)
    ax.set_title("Conformance Category Distribution over Months", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, path)


def task10_calendar(time_df: pd.DataFrame, output_dir: str):
    """HIGH: daily mean conformance (shared calendar heatmap)."""
    path = os.path.join(output_dir, "task10_calendar.svg")
    if time_df is None or time_df.empty:
        render_empty_state_svg(path, "Daily Mean Conformance", "No timestamp data available.")
        return
    daily = (time_df.assign(date=time_df["start_time"].dt.normalize())
             .groupby("date")["fitness"].mean())
    calendar_heatmap(dict(daily.items()), path,
                     title="Daily Mean Conformance Rate", cbar_label="Mean fitness",
                     vmin=0.0, vmax=1.0)


def task10_scatter_plot(fitness_df: pd.DataFrame, output_dir: str):
    """MED: per-trace fitness, x = trace index, y = fitness, colour = category."""
    path = os.path.join(output_dir, "task10_scatter_plot.svg")
    cats = conformance_category_series(fitness_df["fitness"]).values
    colors = _task10_color_list(len(CONFORMANCE_LABELS))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for i, label in enumerate(CONFORMANCE_LABELS):
        m = cats == i
        if m.any():
            ax.scatter(fitness_df["trace_index"].values[m], fitness_df["fitness"].values[m],
                       s=14, alpha=0.6, linewidths=0, color=colors[i], label=label)
    ax.set_xlabel("Trace index", fontsize=FONT_LABEL)
    ax.set_ylabel("Conformance Rate", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Per-trace Conformance by Category", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT - 1, title="Category",
              title_fontsize=FONT_ANNOT - 1, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, path)


def task10_table_bar_chart(range_df: pd.DataFrame, output_dir: str):
    """MED: the category table + an adjacent category-count bar."""
    path = os.path.join(output_dir, "task10_table_and_bar_chart.svg")
    fig = plt.figure(figsize=(13, max(3.0, 1.4 + len(range_df) * 0.5)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], wspace=0.35)

    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    cell_text = [[r["range"], str(int(r["count"])), f"{r['percentage']:.1f}%"]
                 for _, r in range_df.iterrows()]
    make_table(ax_t, cell_text=cell_text,
               col_labels=["Conformance Range", "#Traces", "% of total"],
               bbox=[0.04, 0.05, 0.92, 0.82], col_widths=[0.5, 0.25, 0.25],
               font_size=10, cell_pad=0.08)
    ax_t.set_title("Conformance Categories", fontsize=FONT_TITLE, pad=8)

    ax_b = fig.add_subplot(gs[1])
    colors = _task10_color_list(len(range_df))
    y = np.arange(len(range_df))
    ax_b.barh(y, range_df["count"].values, color=colors, edgecolor="white")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels(range_df["range"], fontsize=FONT_ANNOT - 1)
    ax_b.invert_yaxis()
    ax_b.set_xlabel("# Traces", fontsize=FONT_LABEL)
    ax_b.spines[["top", "right"]].set_visible(False)
    ax_b.set_title("Traces per category", fontsize=FONT_TITLE, pad=8)
    fig.tight_layout()
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(df, output_dir: str, log=None):
    """Generate all Task ID 10 SVGs into output_dir.

    The category idioms use the fitness summary df; the time-based idioms
    (line/horizon/heatmap/calendar) need the log for timestamps (absent → empty
    state). Legacy extras are still rendered (see `# LEGACY` notes above)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 10 visualizations ---")
    range_df = _build_range_df(df)
    logger.info(f"      -> Range counts: {dict(zip(range_df['range'], range_df['count']))}")
    time_df = build_fitness_time_series(log, df) if log is not None else pd.DataFrame()

    # Validated mapping idioms
    task10_stacked_bar(range_df, output_dir)
    task10_line_graph(time_df, output_dir)
    task10_horizon_chart(time_df, output_dir)
    task10_box_plot(df, output_dir)
    task10_heatmap(time_df, output_dir)
    task10_calendar(time_df, output_dir)
    task10_bar_chart(range_df, output_dir)
    task10_scatter_plot(df, output_dir)
    task10_table(range_df, output_dir)
    task10_table_bar_chart(range_df, output_dir)
    task10_pie_chart(range_df, output_dir)
