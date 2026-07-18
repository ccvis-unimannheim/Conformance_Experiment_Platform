"""
tasks/task03.py – Task ID 3: Describe / Compare / Conformant vs. non-conformant
throughput time.

Every idiom contrasts the SAME single factor between the Conformant
(fitness ≥ threshold) and Non-conformant (fitness < threshold) trace groups —
the throughput-time distribution over quartile buckets:
    * bar_chart            – grouped bars, # traces per throughput bucket
    * table                – throughput-bucket table (share % per group)
    * table_and_bar_chart  – throughput table + grouped-bar panel (# traces)
    * stacked_bar          – 100%-stacked bars per group over throughput buckets
    * matrix               – annotated grid, buckets × group, share (%)

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "table_and_bar_chart", "stacked_bar", "matrix"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 3 (SEMI): split traces into Conformant / Non-conformant at a threshold
# chosen by the admin, then compare the throughput-time distribution between the
# groups. The auto GT is a single-choice pick of which group is slower on average.
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "conformant_threshold",
        "label": "Conformance threshold (traces with fitness ≥ this value are Conformant)",
        "hint": "A trace is counted as 'Conformant' when its fitness is at least this value",
        "widget": "threshold",
        "default": 1.0,
        "required": False,
        "optional_hint": "(optional — leave empty to use the default of 1.0, i.e. only perfect-fitness traces count as Conformant)",
        "min": 0.01,
        "max": 1.0,
        "step": 0.01,
    },
]

ANSWER_FORMATS = [
    {"key": "mc-single", "gt_shape": "mc",        "decisive_default": True},
    {"key": "free-text", "gt_shape": "reference",  "decisive_default": False},
]

RUBRIC = (
    "A complete answer states which group — Conformant or Non-conformant — has the "
    "longer average throughput time, and ideally by roughly how much (e.g. 'Non-conformant "
    "traces take about twice as long on average'). Award full marks for the correct "
    "direction with an approximate magnitude, partial marks for the correct direction "
    "without a magnitude, and deduct marks for the wrong direction."
)


def validate_params(log, params) -> list:
    """Ensure conformant_threshold is a number in (0, 1]. Empty = use default 1.0."""
    raw = params.get("conformant_threshold", 1.0)
    if raw is None or raw == "":
        return []
    try:
        thr = float(raw)
    except (TypeError, ValueError):
        return [f"conformant_threshold must be a number between 0 and 1, got: {raw!r}"]
    if not (0.0 < thr <= 1.0):
        return [f"conformant_threshold must be in (0, 1], got {thr}."]
    return []

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, auto_col_widths,
    draw_composition_stacked_bars, contrasting_text_color,
    render_empty_state_svg, format_threshold,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Number of quartile buckets for the throughput-time comparison
N_TIME_BUCKETS = 4

_COLOR_CONFORM     = GREY_MED    # medium-dark grey
_COLOR_NON_CONFORM = GREY_LIGHT  # medium grey
_GROUPS = ["Conformant", "Non-conformant"]

# Shared figure title — the single title on *every* Task 3 idiom, at one font
# size (FONT_TITLE), so no idiom exposes more/less framing than another.
FIG_SUPTITLE = "Conformant vs. Non-conformant: Throughput Time"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task03_build_trace_rows(log, fitness_df: pd.DataFrame,
                             conformant_threshold: float = 1.0) -> list:
    """Pair each trace with its conformance label and its throughput time (hours).

    Throughput time is the single attribute every Task 3 idiom compares between
    the Conformant and Non-conformant groups.
    """
    rows = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        fitness = float(fitness_df.iloc[i]["fitness"])
        group   = "Conformant" if fitness >= conformant_threshold else "Non-conformant"

        timestamps = []
        for event in trace:
            ts = event.get("time:timestamp")
            if ts is not None and not pd.isna(ts):
                timestamps.append(pd.Timestamp(ts))
        duration_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0 \
            if len(timestamps) >= 2 else 0.0

        rows.append({
            "trace_index":    i,
            "group":          group,
            "fitness":        fitness,
            "num_events":     len(trace),
            "duration_hours": duration_hours,
        })
    return rows


def _task03_throughput_stats_df(trace_rows: list) -> pd.DataFrame:
    """Per-group throughput-time (h) distribution: Group | Mean | Median | Std | Min | Max."""
    records = []
    for g in _GROUPS:
        vals = np.array([r["duration_hours"] for r in trace_rows if r["group"] == g], dtype=float)
        if vals.size:
            records.append({"Group": g, "Mean": float(vals.mean()), "Median": float(np.median(vals)),
                             "Std": float(vals.std(ddof=0)), "Min": float(vals.min()), "Max": float(vals.max())})
        else:
            records.append({"Group": g, "Mean": 0.0, "Median": 0.0, "Std": 0.0, "Min": 0.0, "Max": 0.0})
    return pd.DataFrame(records)


def _task03_throughput_buckets(trace_rows: list, n_buckets: int = N_TIME_BUCKETS):
    """Quartile-bucket the throughput times; return (labels, {group: counts_per_bucket})
    or None if there's not enough variance to bucket."""
    durations = np.array([r["duration_hours"] for r in trace_rows], dtype=float)
    if durations.size < 2 or np.unique(durations).size < 2:
        return None
    edges = np.unique(np.quantile(durations, np.linspace(0, 1, n_buckets + 1)))
    if len(edges) < 2:
        return None
    labels = [f"{format_threshold(edges[i])}–{format_threshold(edges[i + 1])}h"
              for i in range(len(edges) - 1)]
    counts = {g: [0] * len(labels) for g in _GROUPS}
    for r in trace_rows:
        b = int(np.clip(np.digitize([r["duration_hours"]], edges[1:-1])[0], 0, len(labels) - 1))
        counts[r["group"]][b] += 1
    return labels, counts


def _task03_throughput_bucket_rows(throughput_buckets):
    """Rows for the throughput-time table: one row per quartile bucket, cells =
    # traces of each group in that bucket — the same count encoding the bar_chart
    idiom uses, so the two idioms expose exactly the same information (fairness)."""
    if throughput_buckets is None:
        return [["—", "—", "—"]]
    labels, counts = throughput_buckets
    rows = []
    for si, lab in enumerate(labels):
        row = [lab]
        for g in _GROUPS:
            row.append(f"{counts[g][si]:d}")
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Idioms — every one shows the SAME throughput-time bucket comparison
# ---------------------------------------------------------------------------

def task03_bar_chart(throughput_buckets, output_dir: str):
    """Grouped bars: # traces per throughput-time quartile bucket, Conformant vs.
    Non-conformant."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    width = 0.38

    if throughput_buckets is not None:
        labels, counts = throughput_buckets
        x = np.arange(len(labels))
        bars_c  = ax.bar(x - width / 2, counts["Conformant"],     width, color=_COLOR_CONFORM,
                         label="Conformant",     edgecolor="white")
        bars_nc = ax.bar(x + width / 2, counts["Non-conformant"], width, color=_COLOR_NON_CONFORM,
                         label="Non-conformant", edgecolor="white")
        max_h = max([b.get_height() for b in (*bars_c, *bars_nc)], default=0)
        for bars in (bars_c, bars_nc):
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + max_h * 0.01,
                            f"{h:.0f}", ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
        ax.set_ylabel("# traces", fontsize=FONT_LABEL)
        if max_h > 0:
            ax.set_ylim(0, max_h * 1.22)
    else:
        ax.text(0.5, 0.5, "No throughput-time variance", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    handles, lbls = ax.get_legend_handles_labels()
    if handles:
        fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=2, frameon=False, fontsize=FONT_ANNOT)
    fig.suptitle(FIG_SUPTITLE, fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    save_svg(fig, os.path.join(output_dir, "task03_bar_chart.svg"))


def task03_table(throughput_buckets, output_dir: str):
    """One table: throughput-time quartile buckets × per-group trace counts."""
    throughput_rows   = _task03_throughput_bucket_rows(throughput_buckets)
    throughput_labels = ["Throughput time", "Conformant (# traces)", "Non-conformant (# traces)"]

    fig_h = max(4.0, 1.4 + max(1, len(throughput_rows)) * 0.5)
    fig = plt.figure(figsize=(9, fig_h))
    ax = fig.add_subplot(111); ax.axis("off")
    make_table(
        ax, cell_text=throughput_rows, col_labels=throughput_labels,
        bbox=[0.05, 0.02, 0.90, 0.86], col_widths=auto_col_widths(throughput_labels, throughput_rows),
        font_size=10, cell_pad=0.09,
    )

    fig.suptitle(FIG_SUPTITLE, fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, os.path.join(output_dir, "task03_table.svg"))


def task03_table_and_bar_chart(throughput_buckets, output_dir: str):
    """Left: throughput-bucket table (# traces per group). Right: grouped horizontal
    bars of # traces per bucket — the same throughput counts in two encodings."""
    throughput_rows   = _task03_throughput_bucket_rows(throughput_buckets)
    throughput_labels = ["Throughput time", "Conformant (# traces)", "Non-conformant (# traces)"]

    fig_h = max(5.0, 1.6 + max(1, len(throughput_rows)) * 0.5)
    fig = plt.figure(figsize=(15, fig_h))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.1, 1.0], wspace=0.28)

    ax_t = fig.add_subplot(gs[0]); ax_t.axis("off")
    make_table(
        ax_t, cell_text=throughput_rows, col_labels=throughput_labels,
        bbox=[0.02, 0.05, 0.96, 0.82], col_widths=auto_col_widths(throughput_labels, throughput_rows),
        font_size=9.5, cell_pad=0.08,
    )

    ax_bar = fig.add_subplot(gs[1])
    if throughput_buckets is not None:
        labels, counts = throughput_buckets
        x = np.arange(len(labels)); w = 0.38
        ax_bar.barh(x - w / 2, counts["Conformant"],     w, color=_COLOR_CONFORM,
                    label="Conformant",     edgecolor="white")
        ax_bar.barh(x + w / 2, counts["Non-conformant"], w, color=_COLOR_NON_CONFORM,
                    label="Non-conformant", edgecolor="white")
        ax_bar.set_yticks(x)
        ax_bar.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
        ax_bar.set_xlabel("# traces", fontsize=FONT_LABEL)
    else:
        ax_bar.text(0.5, 0.5, "No throughput-time variance", ha="center", va="center",
                    transform=ax_bar.transAxes, fontsize=FONT_ANNOT)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    handles, lbls = ax_bar.get_legend_handles_labels()
    if handles:
        fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=2, frameon=False, fontsize=FONT_ANNOT)
    fig.suptitle(FIG_SUPTITLE, fontsize=FONT_TITLE, y=0.99)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    save_svg(fig, os.path.join(output_dir, "task03_table_and_bar_chart.svg"))


def task03_stacked_bar(throughput_buckets, output_dir: str):
    """Stacked bar per conformance group; segments = throughput-time quartile
    buckets, segment height = # traces of that group in that bucket (so the total
    bar height is the group size). Uses trace counts to stay consistent with the
    bar_chart / table / matrix idioms."""
    path = os.path.join(output_dir, "task03_stacked_bar.svg")
    if throughput_buckets is None:
        render_empty_state_svg(path, FIG_SUPTITLE, "No throughput-time variance.")
        return

    labels, counts = throughput_buckets
    data = np.array([[counts[g][si] for g in _GROUPS] for si in range(len(labels))], dtype=float)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    draw_composition_stacked_bars(ax, _GROUPS, labels, data)
    ax.set_ylabel("# traces", fontsize=FONT_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    handles, lbls = ax.get_legend_handles_labels()
    if handles:
        fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=min(len(lbls), 4), frameon=False, fontsize=FONT_ANNOT,
                   title="Throughput time", title_fontsize=FONT_ANNOT)
    fig.suptitle(FIG_SUPTITLE, fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0.10, 1, 0.93])
    save_svg(fig, path)


def task03_matrix(throughput_buckets, output_dir: str):
    """Numeric grid — each column filled with its conformance-group colour, the
    same grey / olive-yellow the bar_chart and stacked_bar use (uniform per
    column, so it encodes the GROUP, not the value: distinct from a value-encoded
    heatmap). Rows = throughput-time quartile buckets, columns = conformance
    group, cells = # traces of that group in that bucket."""
    path = os.path.join(output_dir, "task03_matrix.svg")
    if throughput_buckets is None:
        render_empty_state_svg(path, FIG_SUPTITLE, "No throughput-time variance.")
        return

    tt_labels, counts = throughput_buckets
    data = np.array([[counts[g][si] for g in _GROUPS] for si in range(len(tt_labels))], dtype=int)
    n_rows, n_cols = len(tt_labels), len(_GROUPS)
    col_fill = [_COLOR_CONFORM, _COLOR_NON_CONFORM]  # grey (Conformant), olive-yellow (Non-conformant)
    col_text = [contrasting_text_color(c) for c in col_fill]

    fig_h = 0.55 * n_rows + 2.8
    fig, ax = plt.subplots(figsize=(7, fig_h))

    # Cells filled with their group's full bar_chart colour; the fill is uniform
    # within a column, so it encodes the group — never the cell value the way a
    # heatmap does. Text colour adapts to the fill so the counts stay legible.
    for ri in range(n_rows):
        for ci in range(n_cols):
            ax.add_patch(plt.Rectangle((ci, ri), 1, 1, facecolor=col_fill[ci],
                                       edgecolor="white", linewidth=1.0))
            ax.text(ci + 0.5, ri + 0.5, f"{int(data[ri, ci])}",
                    ha="center", va="center", fontsize=FONT_ANNOT, color=col_text[ci])

    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.invert_yaxis()
    ax.set_xticks([c + 0.5 for c in range(n_cols)])
    ax.set_xticklabels(_GROUPS, fontsize=FONT_ANNOT)
    ax.set_yticks([r + 0.5 for r in range(n_rows)])
    ax.set_yticklabels(tt_labels, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Conformance Group   (cell value = # traces)", fontsize=FONT_LABEL)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.suptitle(FIG_SUPTITLE, fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """mc-single: which conformance group has the longer average throughput time.

    Two mirror-image options (Conformant longer / Non-conformant longer); the one
    matching the group with the larger mean throughput is flagged correct, so the
    participant must read the direction off the throughput-bucket visualization.
    When the two means are indistinguishable (≈ equal), no gradable option set is
    produced (SEMI / manual fallback).
    """
    raw = params.get("conformant_threshold", 1.0)
    threshold = 1.0 if (raw is None or raw == "") else float(raw)
    trace_rows = _task03_build_trace_rows(log, fitness_df, conformant_threshold=threshold)

    if answer_format != "mc-single":
        return {"options": []}

    throughput_df = _task03_throughput_stats_df(trace_rows)
    t_map = {row["Group"]: row["Mean"] for _, row in throughput_df.iterrows()}
    c_mean  = t_map.get("Conformant",     0.0)
    nc_mean = t_map.get("Non-conformant", 0.0)
    if not (c_mean > 0 and nc_mean > 0) or abs(c_mean - nc_mean) <= 0.01:
        return {"options": []}

    longer = "Conformant" if c_mean > nc_mean else "Non-conformant"
    return {
        "options": [
            {
                "label":   "Conformant traces have longer average throughput time",
                "value":   "throughput::Conformant::longer",
                "correct": longer == "Conformant",
            },
            {
                "label":   "Non-conformant traces have longer average throughput time",
                "value":   "throughput::Non-conformant::longer",
                "correct": longer == "Non-conformant",
            },
        ]
    }


def generate(log, fitness_df, output_dir: str, conformant_threshold: float = 1.0):
    """Generate all Task ID 3 SVGs into output_dir (throughput-time comparison)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 3 visualizations ---")

    trace_rows = _task03_build_trace_rows(log, fitness_df,
                                          conformant_threshold=conformant_threshold)
    n_c  = sum(1 for r in trace_rows if r["group"] == "Conformant")
    n_nc = len(trace_rows) - n_c
    logger.info(f"      -> Conformant: {n_c}  |  Non-conformant: {n_nc}"
                f"  (threshold={conformant_threshold})")

    if n_c == 0:
        logger.warning("      No conformant traces — Conformant group is empty.")
    if n_nc == 0:
        logger.warning("      No non-conformant traces — Non-conformant group is empty.")

    throughput_buckets = _task03_throughput_buckets(trace_rows)
    if throughput_buckets is not None:
        logger.info(f"      -> {len(throughput_buckets[0])} throughput-time buckets.")

    task03_bar_chart(throughput_buckets, output_dir)
    task03_table(throughput_buckets, output_dir)
    task03_table_and_bar_chart(throughput_buckets, output_dir)
    task03_stacked_bar(throughput_buckets, output_dir)
    task03_matrix(throughput_buckets, output_dir)
