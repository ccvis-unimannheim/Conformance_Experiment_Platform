"""
tasks/task07.py – Task 7: Process conformance over time.

Visualizations: Line Graph, Horizon Chart, Gantt Chart.

Public API:
    generate(log, fitness_df, output_dir)
        log              – PM4Py event log (used for trace timestamps)
        fitness_df       – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir       – directory where SVGs are written
        time_granularity – ("year" | "month" | "day") controls the time-axis 
                aggregation of the line graph and horizon chart (default: month).
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["line_graph", "horizon_chart"]

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

from shared import (
    save_svg, build_fitness_time_series, bin_fitness_time_series,
    render_conformance_line_graph, render_conformance_horizon_chart,
    apply_time_axis,
    DEFAULT_TIME_GRANULARITY, TIME_GRANULARITY_FREQ,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Maximum traces shown in the Gantt chart (readability + cognitive load)
_GANTT_MAX_TRACES = 20


# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 7)
#
# Task 7 (SEMI): derive process conformance over time. The admin picks the
# time-bin granularity; the answer is one mean-fitness percentage per ordered
# time bin (pct-set -> labelled-set GT shape). The same granularity drives the
# line/horizon charts and this ground truth, so each GT row matches what the
# participant reads off the visual.
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "time_granularity",
        "label": "Time-bin granularity",
        "widget": "select-one",
        # Static fallback list; when a dataset_id is known the param-spec endpoint
        # overwrites `options` via `source` with only the granularities that yield
        # >=2 bins for that dataset (admin.py _dataset_time_granularities).
        "options": ["day", "month", "year"],
        "source": "log.time_granularities",
        "default": DEFAULT_TIME_GRANULARITY,
        "required": True,
    },
]

ANSWER_FORMATS = [
    {"key": "pct-set", "gt_shape": "labelled-set", "decisive_default": True},
]

# Per-granularity label format for GT rows / bin axis.
_BIN_LABEL_FMT = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}


def validate_params(log, params) -> list:
    """Reject configs that cannot yield a meaningful over-time series: no usable
    start timestamps, or fewer than two bins at the chosen granularity (mirrors
    the renderers' own <2-bin guard). See ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §10."""
    granularity = str(params.get("time_granularity", DEFAULT_TIME_GRANULARITY)).lower()
    if granularity not in TIME_GRANULARITY_FREQ:
        return [f"Unknown time granularity '{granularity}' — choose one of {sorted(TIME_GRANULARITY_FREQ)}."]

    starts = []
    for trace in log:
        ts = trace[0].get("time:timestamp") if len(trace) else None
        if ts is not None:
            starts.append(pd.Timestamp(ts))
    if not starts:
        return ["The event log has no usable start timestamps — conformance over time cannot be computed."]

    freq = TIME_GRANULARITY_FREQ[granularity]
    n_bins = pd.Series(starts).dt.to_period(freq).nunique()
    if n_bins < 2:
        return [f"The log spans only {n_bins} {granularity} bin — at least 2 are needed to "
                f"show conformance over time. Choose a finer granularity."]
    return []


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Mean conformance (fitness) per time bin, as an ordered pct-set labelled set.

    Reuses the same binning the line/horizon charts render (shared
    bin_fitness_time_series) so each row matches the visual: label = bin start,
    value = that bin's mean fitness as an integer percent (e.g. "96%"), flagged
    correct. Returns the raw fields admin.py _build_gt_block assembles (§3, §8)."""
    granularity = str(params.get("time_granularity", DEFAULT_TIME_GRANULARITY)).lower()
    df = build_fitness_time_series(log, fitness_df)
    if df.empty:
        return {"options": []}
    binned = bin_fitness_time_series(df, granularity).sort_values("time_bin")
    label_fmt = _BIN_LABEL_FMT.get(granularity, _BIN_LABEL_FMT[DEFAULT_TIME_GRANULARITY])
    options = [
        {
            "label": pd.Timestamp(row["time_bin"]).strftime(label_fmt),
            "value": f"{round(row['avg_fitness'] * 100)}%",
            "correct": True,
        }
        for _, row in binned.iterrows()
    ]
    return {"options": options}


# ---------------------------------------------------------------------------
# Core: build time-series DataFrame (log timestamps + fitness per trace)
# ---------------------------------------------------------------------------

def _build_time_series_df(log, fitness_df) -> pd.DataFrame:
    """Per-trace fitness + start/end timestamps; shared impl in shared.build_fitness_time_series."""
    return build_fitness_time_series(log, fitness_df)


def _save_empty(output_dir: str, filename: str, message: str = "No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


# ---------------------------------------------------------------------------
# Idiom 1: Line Graph
# ---------------------------------------------------------------------------

def task07_line_graph(df: pd.DataFrame, output_dir: str,
                      time_granularity: str = DEFAULT_TIME_GRANULARITY):
    """Mean conformance per time bin (shared renderer, granularity-aware)."""
    render_conformance_line_graph(
        df, os.path.join(output_dir, "task07_line_graph.svg"),
        time_granularity=time_granularity, value_labels=True)


# ---------------------------------------------------------------------------
# Idiom 2: Horizon Chart
# ---------------------------------------------------------------------------

def task07_horizon_chart(df: pd.DataFrame, output_dir: str,
                         time_granularity: str = DEFAULT_TIME_GRANULARITY):
    """Conformance relative to the overall mean as a filled area (shared renderer)."""
    render_conformance_horizon_chart(
        df, os.path.join(output_dir, "task07_horizon_chart.svg"),
        time_granularity=time_granularity)


# ---------------------------------------------------------------------------
# Idiom 3: Gantt Chart
# ---------------------------------------------------------------------------

def task07_gantt_chart(df: pd.DataFrame, output_dir: str,
                       time_granularity: str = DEFAULT_TIME_GRANULARITY):
    """Gantt chart: one row per trace, bar spanning start→end time.

    Bar shade encodes fitness via a white→black greyscale colormap scaled to
    the actual data range.
    X-axis tick labels follow the chosen granularity (day/month/year); outlier
    traces clipped at 95th-pct end time. Capped at _GANTT_MAX_TRACES rows for
    readability.
    """
    if df is None or df.empty:
        _save_empty(output_dir, "task07_gantt_chart.svg", "No timestamp data available")
        return

    gantt_df = df.dropna(subset=["end_time"]).copy()
    if gantt_df.empty:
        _save_empty(output_dir, "task07_gantt_chart.svg",
                    "No traces with both start and end timestamps")
        return

    total_with_end = len(gantt_df)

    # Sort by start_time so vertical position encodes time order directly
    gantt_df = gantt_df.sort_values("start_time").reset_index(drop=True)

    # Uniform time-span sampling: evenly spaced indices across full date range
    # so the selected 20 cases represent the whole period, not just early cases
    if len(gantt_df) > _GANTT_MAX_TRACES:
        indices  = np.linspace(0, len(gantt_df) - 1, _GANTT_MAX_TRACES, dtype=int)
        gantt_df = gantt_df.iloc[indices].reset_index(drop=True)

    n = len(gantt_df)

    starts    = np.array(mdates.date2num(gantt_df["start_time"]))
    ends      = np.array(mdates.date2num(gantt_df["end_time"]))
    durations = ends - starts

    # Dynamic min width: 1% of total visible span, at least 1 day
    total_span = ends.max() - starts.min()
    min_width  = max(total_span * 0.01, 1.0)
    durations  = np.where(durations < min_width, min_width, durations)

    fitness_vals = gantt_df["fitness"].values

    # White (low conformance) → Black (high conformance)
    # Norm anchored to actual data range for maximum contrast
    f_min = max(0.0, float(fitness_vals.min()) - 0.05)
    f_max = min(1.0, float(fitness_vals.max()) + 0.05)
    norm  = mcolors.Normalize(vmin=f_min, vmax=f_max)
    cmap  = plt.cm.Greys

    fig_height = max(4, 0.38 * n + 1.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    ax.set_facecolor("#fafbfc")

    for i, (start, dur, fit) in enumerate(zip(starts, durations, fitness_vals)):
        color = cmap(norm(fit))
        ax.barh(i, dur, left=start, height=0.62,
                color=color, edgecolor="white", linewidth=0.8, alpha=0.95)

    # Clip x-axis at 95th-pct of end times to prevent outlier compression
    x_clip = float(np.percentile(ends, 95))
    x_pad  = (x_clip - float(starts.min())) * 0.02
    ax.set_xlim(float(starts.min()) - x_pad, x_clip + x_pad)

    # Y-axis: sequential 1-N labels in time order; invert so earliest is at top
    y_labels = [f"Case {i + 1}" for i in range(n)]
    ax.set_yticks(range(n))
    ax.set_yticklabels(y_labels, fontsize=FONT_ANNOT)
    ax.tick_params(axis="y", length=0)
    ax.invert_yaxis()

    # X-axis: tick labels follow the chosen granularity (day/month/year)
    ax.xaxis_date()
    apply_time_axis(ax, time_granularity)
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)

    ax.xaxis.grid(True, linestyle="--", alpha=0.25, color="#bbbbbb")
    ax.set_axisbelow(True)

    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    ax.set_title(
        "Trace Timeline by Conformance (sorted by start time)"
        + (f" — {_GANTT_MAX_TRACES} of {total_with_end} cases shown"
           if total_with_end > _GANTT_MAX_TRACES else ""),
        fontsize=FONT_TITLE, pad=12,
    )
    ax.spines[["top", "right", "left"]].set_visible(False)

    # Colorbar
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="vertical", fraction=0.02, pad=0.015)
    cbar.set_label("Conformance Rate", fontsize=FONT_ANNOT)
    mid = (f_min + f_max) / 2
    cbar.set_ticks([f_min, mid, f_max])
    cbar.set_ticklabels([f"{f_min:.0%}", f"{mid:.0%}", f"{f_max:.0%}"])
    cbar.outline.set_visible(False)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task07_gantt_chart.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str,
             time_granularity: str = DEFAULT_TIME_GRANULARITY):
    """Generate all Task 7 SVGs (line graph, horizon chart, gantt chart) into output_dir.

    time_granularity ("year" | "month" | "day") controls the time-axis aggregation
    of the line graph and horizon chart (default: month).
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 7 visualizations (Process conformance over time) ---")
    logger.info(f"      Time granularity: {time_granularity}")

    df = _build_time_series_df(log, fitness_df)

    if df.empty:
        logger.warning("      Skipped Task 7: no usable timestamp data in event log.")
        _save_empty(output_dir, "task07_line_graph.svg",    "No timestamp data available")
        _save_empty(output_dir, "task07_horizon_chart.svg", "No timestamp data available")
        return

    task07_line_graph(df, output_dir, time_granularity)
    task07_horizon_chart(df, output_dir, time_granularity)
