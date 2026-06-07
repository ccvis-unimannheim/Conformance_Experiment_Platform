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
    """Horizon chart: shows conformance deviation from the overall mean over time.

    Above-mean periods → dark grey; below-mean periods → light grey.
    The vertical axis is compressed by folding negative deviations upward,
    giving a compact time-series overview that fits many periods in one view.
    """
    if df is None or df.empty:
        _save_empty(output_dir, "task07_horizon_chart.svg", "No timestamp data available")
        return

    binned = _bin_time_series(df)
    if len(binned) < 2:
        _save_empty(output_dir, "task07_horizon_chart.svg",
                    "Insufficient time range for horizon chart (fewer than 2 time bins)")
        return

    overall_mean = df["fitness"].mean()
    binned["deviation"] = binned["avg_fitness"] - overall_mean

    x = binned["time_bin"]
    dev = binned["deviation"]
    zero = np.zeros(len(x))

    fig, ax = plt.subplots(figsize=(14, 4))

    # Below-mean: light grey fill (deviation < 0, folded positive)
    ax.fill_between(x, zero, dev.clip(upper=0) * -1,
                    where=dev < 0, step="mid",
                    color=GREEN, alpha=0.85, label="Below mean (lower conformance)")

    # Above-mean: dark grey fill
    ax.fill_between(x, zero, dev.clip(lower=0),
                    where=dev > 0, step="mid",
                    color=RED, alpha=0.85, label="Above mean (higher conformance)")

    # Baseline and mean annotation
    ax.axhline(0, color="#555555", linewidth=1.0, linestyle="-")
    ax.text(x.iloc[-1], 0.005,
            f"Mean: {overall_mean:.0%}",
            ha="right", va="bottom", fontsize=FONT_ANNOT, color="#555555")

    # Magnitude bands (guidance lines)
    max_dev = dev.abs().max()
    if max_dev > 0:
        for level in [max_dev * 0.5, max_dev]:
            ax.axhline(level, color="#cccccc", linewidth=0.6, linestyle=":")

    ax.set_ylabel("Deviation from mean", fontsize=FONT_LABEL)
    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    ax.set_title(
        f"Conformance Deviation from Overall Mean ({overall_mean:.0%}) Over Time",
        fontsize=FONT_TITLE,
    )
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, loc="upper right")

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task07_horizon_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 3: Gantt Chart
# ---------------------------------------------------------------------------

def task07_gantt_chart(df: pd.DataFrame, output_dir: str):
    """Gantt chart: one row per trace, bar spanning start→end time.

    Bar color encodes fitness (dark grey = high conformance, light = low).
    Capped at _GANTT_MAX_TRACES rows for readability.
    Zero-duration traces get a minimum visible bar width.
    """
    if df is None or df.empty:
        _save_empty(output_dir, "task07_gantt_chart.svg", "No timestamp data available")
        return

    # Drop traces without end time and cap count
    gantt_df = df.dropna(subset=["end_time"]).copy()
    if gantt_df.empty:
        _save_empty(output_dir, "task07_gantt_chart.svg",
                    "No traces with both start and end timestamps")
        return

    gantt_df = gantt_df.head(_GANTT_MAX_TRACES).reset_index(drop=True)
    n = len(gantt_df)

    # Convert timestamps to matplotlib float dates
    starts   = mdates.date2num(gantt_df["start_time"].dt.to_pydatetime())
    ends     = mdates.date2num(gantt_df["end_time"].dt.to_pydatetime())
    durations = ends - starts

    # Minimum bar width: 0.2 days in matplotlib date units (prevents zero-width bars)
    min_width = 0.2
    durations = np.where(durations < min_width, min_width, durations)

    # Fitness → greyscale color (0.0 = light grey #DDDDDD, 1.0 = dark grey #333333)
    fitness_vals = gantt_df["fitness"].values
    norm = mcolors.Normalize(vmin=0.0, vmax=1.0)
    cmap = cm.get_cmap("Greys")

    fig_height = max(4, 0.35 * n + 1.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    for i, (start, dur, fit) in enumerate(zip(starts, durations, fitness_vals)):
        color = cmap(norm(fit))
        ax.barh(i, dur, left=start, height=0.65, color=color, edgecolor="white", linewidth=0.4)

    # Y-axis: show trace indices (or "Case 1, Case 2, …")
    y_labels = [f"Case {int(gantt_df.loc[i, 'trace_index']) + 1}" for i in range(n)]
    ax.set_yticks(range(n))
    ax.set_yticklabels(y_labels, fontsize=max(FONT_ANNOT - 1, 6))
    ax.invert_yaxis()

    # X-axis: date formatting
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)

    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    ax.set_title(
        f"Trace Timeline by Conformance"
        + (f" (top {_GANTT_MAX_TRACES} shown)" if len(df.dropna(subset=["end_time"])) > _GANTT_MAX_TRACES else ""),
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)

    # Colorbar legend
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="vertical", fraction=0.025, pad=0.02)
    cbar.set_label("Conformance Rate", fontsize=FONT_ANNOT)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_ticklabels(["0%", "25%", "50%", "75%", "100%"])

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
