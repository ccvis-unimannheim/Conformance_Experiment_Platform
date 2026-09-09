"""
tasks/task07.py – Task 7: Process conformance over time.

Visualizations: Line Graph, Horizon Chart.

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
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import (
    save_svg, build_fitness_time_series, bin_fitness_time_series,
    render_conformance_line_graph, render_conformance_horizon_chart,
    DEFAULT_TIME_GRANULARITY, TIME_GRANULARITY_FREQ,
)


PARAM_SPEC = [
    {
        "key": "time_granularity",
        "label": "Time-bin granularity",
        "hint": "The timeline is grouped into these time bins",
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


# Per-granularity label format for GT rows / bin axis.
_BIN_LABEL_FMT = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}


def validate_params(log, params) -> list:
    """Reject configs that cannot yield a meaningful over-time series: no usable
    start timestamps, or fewer than two bins at the chosen granularity (mirrors
    the renderers' own <2-bin guard)."""
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
        time_granularity=time_granularity, value_labels=True)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str,
             time_granularity: str = DEFAULT_TIME_GRANULARITY):
    """Generate all Task 7 SVGs (line graph, horizon chart) into output_dir.

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
