"""
tasks/task07.py – Task 7: Process conformance over time.

Visualizations: Line Graph, Horizon Chart, Gantt Chart.

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py event log (used for trace timestamps)
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["line_graph", "horizon_chart", "gantt_chart"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from shared import save_svg, BLUE, ORANGE, GREEN, RED, TEAL, FONT_TITLE, FONT_LABEL, FONT_ANNOT

# Maximum traces shown in the Gantt chart (performance + readability)
_GANTT_MAX_TRACES = 50


# ---------------------------------------------------------------------------
# Core: build time-series DataFrame (log timestamps + fitness per trace)
# ---------------------------------------------------------------------------

def _build_time_series_df(log, fitness_df) -> pd.DataFrame:
    """Merge per-trace fitness values with trace start/end timestamps from the log.

    Returns a DataFrame with columns:
        trace_index, fitness, is_fit, start_time (Timestamp), end_time (Timestamp)

    Rows where start_time is NaT (no timestamp in the log) are dropped.
    """
    rows = []
    for _, row in fitness_df.iterrows():
        idx = int(row["trace_index"])
        try:
            trace = log[idx]
        except (IndexError, Exception):
            continue
        ts_start = trace[0].get("time:timestamp") if trace else None
        ts_end   = trace[-1].get("time:timestamp") if trace else None
        rows.append({
            "trace_index": idx,
            "fitness":     float(row["fitness"]),
            "is_fit":      bool(row["is_fit"]),
            "start_time":  pd.Timestamp(ts_start) if ts_start is not None else pd.NaT,
            "end_time":    pd.Timestamp(ts_end)   if ts_end   is not None else pd.NaT,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["start_time"]).sort_values("start_time").reset_index(drop=True)
    return df


def _auto_bin_freq(df: pd.DataFrame) -> str:
    """Choose time-bin frequency from the actual span of the data."""
    span_days = (df["start_time"].max() - df["start_time"].min()).days
    if span_days < 30:
        return "D"    # daily
    elif span_days < 365:
        return "W"    # weekly
    else:
        return "ME"   # monthly


def _bin_time_series(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-trace fitness into time bins; return binned DataFrame."""
    freq = _auto_bin_freq(df)
    df2 = df.copy()
    df2["time_bin"] = df2["start_time"].dt.to_period(freq).dt.to_timestamp()
    binned = (
        df2.groupby("time_bin")["fitness"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "avg_fitness", "count": "n_traces"})
        .reset_index()
    )
    return binned


def _save_empty(output_dir: str, filename: str, message: str = "No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# Idiom 1: Line Graph
# ---------------------------------------------------------------------------

def task07_line_graph(df: pd.DataFrame, output_dir: str):
    if df is None or df.empty:
        _save_empty(output_dir, "task07_line_graph.svg", "No timestamp data available")
        return

    binned = _bin_time_series(df)
    if len(binned) < 2:
        _save_empty(output_dir, "task07_line_graph.svg",
                    "Insufficient time range for trend line (fewer than 2 time bins)")
        return

    fig, ax = plt.subplots(figsize=(12, 5))

    x = binned["time_bin"]
    y = binned["avg_fitness"]

    ax.fill_between(x, y, alpha=0.18, color=BLUE)
    ax.plot(x, y, color=BLUE, linewidth=1.8, marker="o", markersize=4)

    # Overall mean reference line
    overall_mean = df["fitness"].mean()
    ax.axhline(overall_mean, color=ORANGE, linewidth=1.2,
               linestyle="--", label=f"Overall mean: {overall_mean:.2f}")

    ax.set_ylim(-0.05, 1.1)
    ax.set_ylabel("Average Conformance Rate", fontsize=FONT_LABEL)
    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    ax.set_title("Process Conformance Over Time", fontsize=FONT_TITLE)
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=FONT_ANNOT)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task07_line_graph.svg"))


# ---------------------------------------------------------------------------
# Idiom 2: Horizon Chart
# ---------------------------------------------------------------------------

def task07_horizon_chart(df: pd.DataFrame, output_dir: str):
    """Horizon chart: continuous area chart showing conformance relative to overall mean.

    Area above mean → dark grey (higher conformance).
    Area below mean → light grey (lower conformance).
    Y-axis shows actual conformance rate; mean line is the visual baseline.
    """
    if df is None or df.empty:
        _save_empty(output_dir, "task07_horizon_chart.svg", "No timestamp data available")
        return

    binned = _bin_time_series(df)
    if len(binned) < 2:
        _save_empty(output_dir, "task07_horizon_chart.svg",
                    "Insufficient time range for horizon chart (fewer than 2 time bins)")
        return

    mean_val = df["fitness"].mean()
    x = binned["time_bin"]
    y = binned["avg_fitness"]

    fig, ax = plt.subplots(figsize=(14, 5))

    # Continuous filled areas relative to mean baseline
    ax.fill_between(x, mean_val, y,
                    where=(y >= mean_val), interpolate=True,
                    color=RED, alpha=0.75, label="Above mean (higher conformance)")
    ax.fill_between(x, mean_val, y,
                    where=(y <= mean_val), interpolate=True,
                    color=GREEN, alpha=0.75, label="Below mean (lower conformance)")

    # Thin line connecting data points for readability
    ax.plot(x, y, color="#444444", linewidth=0.9, alpha=0.5)

    # Mean reference line
    ax.axhline(mean_val, color="#555555", linewidth=1.2, linestyle="--")

    # Mean annotation — placed outside plot area to avoid overlapping data
    ax.annotate(
        f"Mean: {mean_val:.0%}",
        xy=(1.01, mean_val),
        xycoords=("axes fraction", "data"),
        fontsize=FONT_ANNOT, color="#555555", va="center",
    )

    # Y-axis: show actual conformance range with small padding
    y_pad = max((y.max() - y.min()) * 0.15, 0.01)
    ax.set_ylim(max(0.0, y.min() - y_pad), min(1.0, y.max() + y_pad))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))

    ax.set_ylabel("Conformance Rate", fontsize=FONT_LABEL)
    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    ax.set_title("Process Conformance Over Time", fontsize=FONT_TITLE)
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, loc="lower left")

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task07_horizon_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 3: Gantt Chart
# ---------------------------------------------------------------------------

def task07_gantt_chart(df: pd.DataFrame, output_dir: str):
    """Gantt chart: one row per trace, bar spanning start→end time.

    Bar color encodes fitness via red→teal colormap scaled to actual data range.
    X-axis shows month/year labels; outlier traces clipped at 95th-pct end time.
    Capped at _GANTT_MAX_TRACES rows for readability.
    """
    if df is None or df.empty:
        _save_empty(output_dir, "task07_gantt_chart.svg", "No timestamp data available")
        return

    gantt_df = df.dropna(subset=["end_time"]).copy()
    if gantt_df.empty:
        _save_empty(output_dir, "task07_gantt_chart.svg",
                    "No traces with both start and end timestamps")
        return

    gantt_df = gantt_df.head(_GANTT_MAX_TRACES).reset_index(drop=True)
    n = len(gantt_df)

    starts    = np.array(mdates.date2num(gantt_df["start_time"]))
    ends      = np.array(mdates.date2num(gantt_df["end_time"]))
    durations = ends - starts

    # Dynamic min width: 1% of total visible span, at least 1 day
    total_span = ends.max() - starts.min()
    min_width = max(total_span * 0.01, 1.0)
    durations = np.where(durations < min_width, min_width, durations)

    fitness_vals = gantt_df["fitness"].values

    # Colormap scaled to actual fitness range → maximises colour contrast
    f_min = max(0.0, float(fitness_vals.min()) - 0.05)
    f_max = min(1.0, float(fitness_vals.max()) + 0.05)
    norm = mcolors.Normalize(vmin=f_min, vmax=f_max)
    # coral/salmon (low) → light sage → teal (high conformance)
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "conformance", ["#e07b6a", "#f5c99a", "#aed4c4", "#2d7d6f"]
    )

    fig_height = max(5, 0.30 * n + 2.0)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    ax.set_facecolor("#fafbfc")

    for i, (start, dur, fit) in enumerate(zip(starts, durations, fitness_vals)):
        color = cmap(norm(fit))
        ax.barh(i, dur, left=start, height=0.62,
                color=color, edgecolor="white", linewidth=0.5, alpha=0.93)

    # Clip x-axis at 95th-pct of end times to prevent outlier traces from
    # compressing all other bars into a tiny sliver on the left
    x_clip = float(np.percentile(ends, 95))
    x_pad  = (x_clip - float(starts.min())) * 0.02
    ax.set_xlim(float(starts.min()) - x_pad, x_clip + x_pad)

    # Y-axis
    y_labels = [f"Case {int(gantt_df.loc[i, 'trace_index']) + 1}" for i in range(n)]
    ax.set_yticks(range(n))
    ax.set_yticklabels(y_labels, fontsize=max(FONT_ANNOT - 2, 5))
    ax.tick_params(axis="y", length=0)
    ax.invert_yaxis()

    # X-axis: explicit month/year labels instead of AutoDateFormatter
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)

    # Vertical grid only — horizontal grid clutters dense row layout
    ax.xaxis.grid(True, linestyle="--", alpha=0.25, color="#bbbbbb")
    ax.set_axisbelow(True)

    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    total_with_end = len(df.dropna(subset=["end_time"]))
    ax.set_title(
        "Trace Timeline by Conformance"
        + (f" (top {_GANTT_MAX_TRACES} of {total_with_end} shown)"
           if total_with_end > _GANTT_MAX_TRACES else ""),
        fontsize=FONT_TITLE, pad=12,
    )
    ax.spines[["top", "right", "left"]].set_visible(False)

    # Colorbar with actual range tick labels
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="vertical", fraction=0.02, pad=0.015)
    cbar.set_label("Conformance Rate", fontsize=FONT_ANNOT)
    mid = (f_min + f_max) / 2
    cbar.set_ticks([f_min, mid, f_max])
    cbar.set_ticklabels([f"{f_min:.0%}", f"{mid:.0%}", f"{f_max:.0%}"])
    cbar.outline.set_visible(False)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task07_gantt_chart.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str):
    """Generate all Task 7 SVGs (line graph, horizon chart, gantt chart) into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 7 visualizations (Process conformance over time) ---")

    df = _build_time_series_df(log, fitness_df)

    if df.empty:
        logger.warning("      Skipped Task 7: no usable timestamp data in event log.")
        _save_empty(output_dir, "task07_line_graph.svg",    "No timestamp data available")
        _save_empty(output_dir, "task07_horizon_chart.svg", "No timestamp data available")
        _save_empty(output_dir, "task07_gantt_chart.svg",   "No timestamp data available")
        return

    task07_line_graph(df, output_dir)
    task07_horizon_chart(df, output_dir)
    task07_gantt_chart(df, output_dir)
