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
        df               – fitness summary DataFrame (trace_index, fitness, is_fit)
        log              – PM4Py log; needed for the time-based idioms (line/horizon/heatmap/calendar)
        conformance_bins – optional list of conformance interval boundaries
            (e.g. [0.0, 0.5, 0.9, 1.01]). Defaults to the canonical CONFORMANCE_BINS in
            shared.py — the single source of truth shared with task01/25/27/33. Range
            labels are derived automatically via make_conformance_labels.
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["stacked_bar", "line_graph", "horizon_chart", "boxplot", "heatmap", "calendar",
          "bar_chart", "scatter_plot", "table", "table_bar_chart", "pie_chart"]


PARAM_SPEC = [
    {
        "key": "conformance_bins",
        "label": "Conformance interval boundaries",
        # The interval ranges are shown directly in the chart → hint redundant.
        "hide_hint": True,
        "widget": "select-one",
        "options": [
            {
                "label": "Standard (0–20 %, 20–40 %, 40–60 %, 60–80 %, 80–100 %)",
                "value": "0.0,0.2,0.4,0.6,0.8,1.01",
            },
            {
                "label": "High-fitness focus (80–85 %, 85–90 %, 90–95 %, 95–<100 %, 100 %)",
                "value": "0.80,0.85,0.90,0.95,1.0,1.01",
            },
            {
                "label": "Study-defined categories (Perfectly conformant = 100 %, Minor 75–<100 %, Moderate 50–75 %, Major <50 %)",
                "value": "0.0,0.5,0.75,1.0,1.01",
            },
        ],
        "default": "0.0,0.2,0.4,0.6,0.8,1.01",
        "required": True,
    },
]


RUBRIC = (
    "A strong answer states the percentage of traces in each conformance category "
    "(as defined by the selected interval boundaries), covering every category that "
    "contains traces. Full credit requires an approximately correct percentage "
    "(within ±5 percentage points) for each category, or a correct ranking of which "
    "categories contain the most to fewest traces. No credit for percentages computed "
    "against the wrong boundary set, or for omitting a category that contains traces."
)


def _parse_bins(raw) -> list | None:
    """Parse comma-separated bin boundaries from a param string."""
    if not raw:
        return None
    try:
        return [float(x.strip()) for x in str(raw).split(",") if x.strip()]
    except (ValueError, TypeError):
        return None


def validate_params(log, params) -> list:
    raw = params.get("conformance_bins", "")
    if not raw:
        return ["conformance_bins is required."]
    bins = _parse_bins(raw)
    if bins is None or len(bins) < 3:
        return ["conformance_bins must be at least 3 comma-separated numbers (≥ 2 intervals)."]
    if bins != sorted(bins):
        return ["conformance_bins must be in strictly ascending order."]
    if bins[0] < 0.0 or bins[-1] > 1.01:
        return ["conformance_bins values must be between 0.0 and 1.01."]
    return []


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
    render_conformance_line_graph, render_conformance_horizon_chart,
    conformance_category_series, conformance_category_counts,
    make_conformance_labels,
    CONFORMANCE_BINS, CONFORMANCE_LABELS, CONFORMANCE_CATEGORY_NAMES,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, CIVIDIS, CIVIDIS_R,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT, contrasting_text_color,
)
from matplotlib.colors import to_hex

# ---------------------------------------------------------------------------
# Range definitions (buckets extracted to shared.py — single source of truth)
# ---------------------------------------------------------------------------

DEFAULT_BINS = CONFORMANCE_BINS
DEFAULT_LABELS = CONFORMANCE_LABELS
HIGH_FITNESS_BINS = [0.80, 0.85, 0.90, 0.95, 1.0]
# Percentage labels, matching make_conformance_labels(HIGH_FITNESS_CATEGORY_BINS)
# so the adaptive high-fitness preview reads identically to the admin-selected
# "High-fitness focus" preset.
HIGH_FITNESS_LABELS = ["80–85%", "85–90%", "90–95%", "95–100%", "100%"]

# Study-defined preset: named categories instead of generic "X–Y%" range labels
# (the "Perfectly conformant" bucket is [1.0, 1.01) — fitness == 1.00 exactly).
STUDY_DEFINED_BINS = [0.0, 0.5, 0.75, 1.0, 1.01]
STUDY_DEFINED_LABELS = ["Major deviations", "Moderate deviations", "Minor deviations", "Perfectly conformant"]

# Cividis ramp for adaptive conformance ranges (dark = low, light = high)
RANGE_COLORS = [to_hex(CIVIDIS(i / 5)) for i in range(6)]


def _labels_for_bins(bins):
    """Named category labels for the study-defined preset; auto "X–Y%" labels otherwise."""
    if list(bins) == STUDY_DEFINED_BINS:
        return list(STUDY_DEFINED_LABELS)
    return make_conformance_labels(bins)


def _task10_color_list(n: int):
    """Return a stable cividis palette with enough colors for adaptive bins."""
    if n <= len(RANGE_COLORS):
        return RANGE_COLORS[:n]
    return [to_hex(CIVIDIS(i / max(n - 1, 1))) for i in range(n)]


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


def _build_quantile_range_df(fitness: pd.Series, max_bins: int = 5):
    """Use quantile bins when the distribution is not well served by fixed ranges.

    Returns (range_df, edges); range_df is empty and edges is None when the
    distribution collapses to fewer than two distinct quantile edges.
    """
    quantiles = np.linspace(0, 1, max_bins + 1)
    edges = np.unique(np.quantile(fitness, quantiles))
    if len(edges) <= 2:
        return pd.DataFrame(), None
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
    range_df = pd.DataFrame({
        "range": labels,
        "count": counts,
        "percentage": [count / total * 100 if total else 0.0 for count in counts],
    })
    return range_df, edges


# Edge list equivalent to the high-fitness ranges (last bucket is exactly 1.0),
# so per-trace idioms can categorise identically via conformance_category_series.
HIGH_FITNESS_CATEGORY_BINS = [0.80, 0.85, 0.90, 0.95, 1.0, 1.01]


def _resolve_ranges(df, bins=None, labels=None):
    """Resolve the conformance ranges used by *every* Task 10 idiom.

    Returns (range_df, used_bins, used_labels).

    bins=None  → adaptive mode (sample preview): may switch to HIGH_FITNESS bins
                 when fitness.min() ≥ 0.8, or fall back to quantile bins when
                 fewer than 3 default buckets are occupied.
    bins given → exact mode (admin-configured run / GT): the caller's bins are
                 used as-is with no adaptive override, so participants always see
                 the intervals the admin actually selected.
    """
    adaptive = bins is None
    bins   = list(bins)   if bins   is not None else DEFAULT_BINS
    labels = list(labels) if labels is not None else DEFAULT_LABELS

    fitness = df["fitness"].astype(float)
    if fitness.empty:
        return pd.DataFrame(columns=["range", "count", "percentage"]), bins, labels

    if adaptive and fitness.min() >= 0.8:
        return (_build_high_fitness_range_df(fitness),
                list(HIGH_FITNESS_CATEGORY_BINS), list(HIGH_FITNESS_LABELS))

    default_buckets = pd.cut(
        fitness, bins=bins, labels=labels, right=False, include_lowest=True,
    )
    default_counts = default_buckets.value_counts().reindex(labels, fill_value=0)
    active_default_bins = int((default_counts > 0).sum())
    if not adaptive or active_default_bins >= 3:
        total = len(fitness)
        result = pd.DataFrame({
            "range": labels,
            "count": default_counts.values,
            "percentage": default_counts.values / total * 100 if total else [0.0] * len(labels),
        })
        return result, bins, labels

    quantile_df, quantile_edges = _build_quantile_range_df(fitness)
    if not quantile_df.empty:
        return quantile_df, list(quantile_edges), list(quantile_df["range"])

    counts = default_buckets.value_counts().reindex(labels, fill_value=0)
    total  = len(df)
    result = pd.DataFrame({
        "range":      labels,
        "count":      counts.values,
        "percentage": counts.values / total * 100 if total else [0.0] * len(labels),
    })
    return result, bins, labels


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task10_bar_chart(range_df: pd.DataFrame, output_dir: str):
    """Bar chart: percentage of traces per conformance range.

    Each bar is coloured by its percentage value using CIVIDIS_R (yellow = low,
    dark blue = high) — the same colormap and normalization as task10_heatmap,
    so colour magnitude is consistent across all three information-equivalent idioms.
    """
    max_pct = range_df["percentage"].max()
    norm = max_pct if max_pct > 0 else 1.0
    bar_colors = [to_hex(CIVIDIS_R(float(pct) / norm)) for pct in range_df["percentage"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        range_df["range"],
        range_df["percentage"],
        color=bar_colors,
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
    ax.set_xlabel("Conformance Category", fontsize=FONT_LABEL)
    ax.set_ylabel("Percentage of Traces (%)", fontsize=FONT_LABEL)
    ax.set_title("Conformance Category Distribution", fontsize=FONT_TITLE)
    ax.set_ylim(0, max(range_df["percentage"].max() * 1.15, 5))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task10_bar_chart.svg"))


def task10_pie_chart(range_df: pd.DataFrame, output_dir: str):
    """Pie chart: proportion of traces per conformance range.

    All categories are included in the pie and legend, even ones with zero
    traces, so the legend always shows the complete set of categories in use —
    a zero-count category simply renders as a zero-width wedge but still gets
    its correct rank colour in the legend. Percentage labels sit outside the
    pie with a leader line to their wedge, since thin/small slices make inside
    labels overlap."""
    # Colour by conformance rank (low → high category), matching the bar chart
    # and heatmap's CIVIDIS_R convention: low conformance = yellow, high = blue.
    # Applied uniformly regardless of count, so a category's colour never
    # depends on how much data happens to be in it this run.
    n = len(range_df)
    colors = [to_hex(CIVIDIS_R(i / max(n - 1, 1))) for i in range(n)]

    fig, ax = plt.subplots(figsize=(9, 7))
    wedges, _texts = ax.pie(
        range_df["count"],
        labels=None,
        colors=colors,
        startangle=90,
        wedgeprops=dict(edgecolor="white", linewidth=2),
    )

    total = range_df["count"].sum()
    active = [
        (count / total * 100, (wedge.theta1 + wedge.theta2) / 2.0)
        for wedge, count in zip(wedges, range_df["count"])
        if count > 0 and total > 0
    ]
    active.sort(key=lambda t: t[1])

    # Adjacent thin wedges can land close enough in angle that their outside
    # labels still collide. Fan a closely-following label's angle away from its
    # neighbour (one left, one right of their true positions) instead of
    # pushing it further out, so both leader lines stay the same length.
    MIN_GAP_DEG = 12
    FAN_DEG = 3
    BASE_RADIUS = 1.3
    label_angle_offsets = [0.0] * len(active)
    for i in range(1, len(active)):
        if abs(active[i][1] - active[i - 1][1]) < MIN_GAP_DEG:
            label_angle_offsets[i - 1] -= FAN_DEG
            label_angle_offsets[i] += FAN_DEG

    for i, (pct, angle_deg) in enumerate(active):
        true_angle = np.deg2rad(angle_deg)
        x0, y0 = np.cos(true_angle), np.sin(true_angle)
        label_angle = np.deg2rad(angle_deg + label_angle_offsets[i])
        xl, yl = np.cos(label_angle), np.sin(label_angle)
        ax.annotate(
            f"{pct:.1f}%",
            xy=(x0, y0),
            xytext=(xl * BASE_RADIUS, yl * BASE_RADIUS),
            ha="left" if xl >= 0 else "right", va="center",
            fontsize=FONT_ANNOT,
            arrowprops=dict(arrowstyle="-", color=GREY_MED, lw=1),
        )
    ax.set_xlim(-1.7, 1.7)
    ax.set_ylim(-1.7, 1.7)

    ax.legend(
        wedges, list(range_df["range"]),
        loc="lower center", bbox_to_anchor=(0.5, -0.1),
        fontsize=FONT_ANNOT, frameon=True, framealpha=0.9,
        ncol=len(range_df),
        title="Conformance Category\n",
    )
    ax.set_title("Conformance Category Distribution", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task10_pie_chart.svg"))


def task10_table(range_df: pd.DataFrame, output_dir: str):
    """Table: Conformance Category | Percentage of Traces (no counts, no total row)."""
    cell_text = [
        [row["range"], f"{row['percentage']:.1f}%"]
        for _, row in range_df.iterrows()
    ]
    fig_h = max(3.0, 1.2 + len(cell_text) * 0.52)
    fig, ax = plt.subplots(figsize=(7, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Conformance Category", "Percentage of Traces"],
        bbox=[0.05, 0.05, 0.90, 0.78],
        col_widths=[0.60, 0.40],
        font_size=11,
        scale_xy=(1, 1.7),
    )
    ax.set_title("Conformance Category Distribution", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
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
              loc="lower center", bbox_to_anchor=(0.5, -0.30),
              ncol=min(len(range_df), 5), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task10_line_graph(time_df: pd.DataFrame, output_dir: str):
    """HIGH: mean conformance per time bin (shared conformance-time renderer)."""
    render_conformance_line_graph(
        time_df, os.path.join(output_dir, "task10_line_graph.svg"),
        title="Conformance Distribution Over Time")


def task10_horizon_chart(time_df: pd.DataFrame, output_dir: str):
    """HIGH: the conformance series as a horizon area chart (shared renderer)."""
    render_conformance_horizon_chart(
        time_df, os.path.join(output_dir, "task10_horizon_chart.svg"),
        title="Conformance Distribution Over Time")


def task10_box_plot(fitness_df: pd.DataFrame, output_dir: str):
    """HIGH: per-trace fitness distribution (one box for the whole log)."""
    path = os.path.join(output_dir, "task10_box_plot.svg")
    vals = fitness_df["fitness"].astype(float).values
    fig, ax = plt.subplots(figsize=(4, 6))
    ax.boxplot(
        vals, vert=True, patch_artist=True, widths=0.4,
        boxprops=dict(facecolor=GREY_MED, color=GREY_MED, alpha=0.85),
        medianprops=dict(color="white", linewidth=2),
        whiskerprops=dict(color=GREY_MED, linewidth=1.5),
        capprops=dict(color=GREY_MED, linewidth=1.5),
        flierprops=dict(marker="D", markerfacecolor=GREY_MED, markersize=5,
                        linestyle="none", markeredgecolor=GREY_MED),
    )
    ax.set_xticks([1])
    ax.set_xticklabels(["Log"])
    ax.set_ylabel("Conformance Rate (0.0 – 1.0)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Per-trace Conformance Distribution", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task10_heatmap(range_df: pd.DataFrame, output_dir: str):
    """Single-row heatmap: colour intensity = percentage of traces per conformance category.

    Encodes the same 5 category percentages as the bar chart and table; only the
    visual encoding mechanism differs (colour intensity instead of bar length / table cell).
    """
    path = os.path.join(output_dir, "task10_heatmap.svg")
    data = np.array([range_df["percentage"].values], dtype=float)
    col_labels = list(range_df["range"])
    row_labels = ["Percentage\nof Traces"]
    fig, ax = plt.subplots(figsize=(max(8, len(col_labels) * 1.6), 2.8))
    draw_value_heatmap(fig, ax, data, row_labels, col_labels,
                       xlabel="Conformance Category",
                       cbar_label="Percentage of Traces (%)",
                       cell_fmt="{:.1f}%", annotate=True)
    ax.set_title("Conformance Category Distribution", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
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


def task10_scatter_plot(fitness_df: pd.DataFrame, output_dir: str, bins=None, labels=None):
    """MED: per-trace fitness, x = trace index, y = fitness, colour = category."""
    path = os.path.join(output_dir, "task10_scatter_plot.svg")
    labels = list(labels) if labels is not None else CONFORMANCE_LABELS
    cats = conformance_category_series(fitness_df["fitness"], bins).values
    colors = _task10_color_list(len(labels))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for i, label in enumerate(labels):
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
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
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
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(df, output_dir: str, log=None, conformance_bins=None):
    """Generate all Task ID 10 SVGs into output_dir.

    The category idioms use the fitness summary df; the time-based idioms
    (line/horizon/heatmap/calendar) need the log for timestamps (absent → empty
    state)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 10 visualizations ---")

    if conformance_bins:
        if isinstance(conformance_bins, str):
            conformance_bins = _parse_bins(conformance_bins)
        if conformance_bins:
            bins   = list(conformance_bins)
            labels = _labels_for_bins(bins)
            logger.info(f"      -> Admin-specified conformance bins: {bins}")
            # Pass bins explicitly → _resolve_ranges() respects them exactly.
            range_df, used_bins, used_labels = _resolve_ranges(df, bins, labels)
        else:
            # Parsing failed; fall through to adaptive.
            range_df, used_bins, used_labels = _resolve_ranges(df)
    else:
        # No bins specified (sample preview) → adaptive logic selects best intervals.
        range_df, used_bins, used_labels = _resolve_ranges(df)
    canonical = (used_bins == list(CONFORMANCE_BINS))
    category_names = CONFORMANCE_CATEGORY_NAMES if canonical else None
    logger.info(f"      -> Range counts: {dict(zip(range_df['range'], range_df['count']))}")
    if not canonical:
        logger.info(f"      -> Adaptive conformance intervals in use: {used_labels}")
    time_df = build_fitness_time_series(log, df) if log is not None else pd.DataFrame()

    # Validated mapping idioms
    task10_stacked_bar(range_df, output_dir)
    task10_line_graph(time_df, output_dir)
    task10_horizon_chart(time_df, output_dir)
    task10_box_plot(df, output_dir)
    task10_heatmap(range_df, output_dir)
    task10_calendar(time_df, output_dir)
    task10_bar_chart(range_df, output_dir)
    task10_scatter_plot(df, output_dir, used_bins, used_labels)
    task10_table(range_df, output_dir)
    task10_table_bar_chart(range_df, output_dir)
    task10_pie_chart(range_df, output_dir)
