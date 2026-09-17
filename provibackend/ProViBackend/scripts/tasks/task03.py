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


PARAM_SPEC = [
    {
        "key": "conformant_threshold",
        "label": "Conformance threshold (traces with fitness ≥ this value are Conformant)",
        "hint": "A trace is counted as 'Conformant' when its fitness is at least this value",
        "hide_hint": True,
        "widget": "threshold",
        "default": 1.0,
        "required": False,
        "optional_hint": "(optional — leave empty to use the default of 1.0, i.e. only perfect-fitness traces count as Conformant)",
        "min": 0.01,
        "max": 1.0,
        "step": 0.01,
    },
    {
        "key": "response_attribute",
        "slot": "response",
        "label": "Attribute compared between the two groups (empty = throughput time)",
        "hint": "Each group's traces are distributed over this attribute's buckets",
        "widget": "select-one",
        "source": "log.candidate_attributes",
        "default": "",
        "required": False,
        "optional_hint": "(optional — empty compares throughput time)",
    },
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
    render_empty_state_svg,
    GREY_DARK, GREY_LIGHTER, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Number of quartile buckets for the throughput-time comparison
N_TIME_BUCKETS = 4

_COLOR_CONFORM     = GREY_DARK      # cividis dark blue
_COLOR_NON_CONFORM = GREY_LIGHTER   # cividis yellow
_GROUPS = ["Conformant", "Non-conformant"]

# Shared figure title — the single title on *every* Task 3 idiom, at one font
# size (FONT_TITLE), so no idiom exposes more/less framing than another.
# Two registers, as before: the suptitle is Title Case, the column header
# and legend title sentence case.
_SUPTITLE_FMT = "Conformant vs. Non-conformant: {}"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task03_build_trace_rows(log, fitness_df: pd.DataFrame,
                             conformant_threshold: float = 1.0,
                             response_attribute: str = "") -> list:
    """Pair each trace with its conformance label and the compared attribute.

    The attribute is whatever `response_attribute` names — throughput time by
    default, which is what every Task 3 idiom compared before it was a choice.
    Returns `(rows, value_type)`; the type comes from the registry rather than
    being guessed from the values, so a categorical attribute is not coerced.
    """
    import trace_features

    # Whichever attribute the admin picked, read as a registry feature rather
    # than derived here; throughput time — the default — used to be computed by
    # walking every trace's timestamps a second time.
    key = response_attribute or trace_features.DURATION_KEY
    values, value_type = trace_features.extract(log, key)
    values, value_type = trace_features.as_bucketable(values, value_type)

    rows = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        fitness = float(fitness_df.iloc[i]["fitness"])
        rows.append({
            "trace_index":    i,
            # "at or above the threshold counts as conformant" — the same
            # reading trace_features.split applies to an explicit cut.
            "group":          "Conformant" if fitness >= conformant_threshold else "Non-conformant",
            "fitness":        fitness,
            "num_events":     len(trace),
            # Left exactly as the registry returned it. Casting to float here
            # turned a resource id into a number and a missing value into a
            # real 0, so a categorical attribute quantile-collapsed into one
            # bucket and drew an empty chart instead of a comparison.
            "value":          values[i],
        })
    return rows, value_type


def _task03_throughput_buckets(trace_rows: list, n_buckets: int = N_TIME_BUCKETS,
                               unit: str = "h", value_type: str = "numeric"):
    """Bucket the compared attribute; return (labels, {group: counts_per_bucket})
    or None if there's not enough variance to bucket.

    Numeric attributes get quantile ranges, categorical ones their top-N values
    plus Other — `trace_features.split` picks, from the registry's value type.
    """
    import trace_features

    values = [r["value"] for r in trace_rows]
    result = trace_features.split(values, value_type, cap=n_buckets)
    if not result or len(result.labels) < 2:
        return None
    # A quartile label reads as a range, so it needs the unit the numbers are in;
    # the registry's throughput feature is in hours. A category name is already
    # a name and takes no unit.
    suffix = unit if value_type == "numeric" else ""
    labels = [f"{lab}{suffix}" for lab in result.labels]
    counts = {g: [0] * len(labels) for g in _GROUPS}
    index = {lab: i for i, lab in enumerate(result.labels)}
    for r, assigned in zip(trace_rows, result.assignment):
        if assigned is not None:
            counts[r["group"]][index[assigned]] += 1
    return labels, counts


def _task03_bucket_shares(throughput_buckets):
    """Within-group share (%) per bucket: {group: [pct_per_bucket]}. Normalising
    within each group makes the two throughput distributions directly comparable
    regardless of group size — the shared data for every Task 3 idiom."""
    labels, counts = throughput_buckets
    totals = {g: float(sum(counts[g])) for g in _GROUPS}
    return {g: [(counts[g][si] / totals[g] * 100) if totals[g] else 0.0
                for si in range(len(labels))]
            for g in _GROUPS}


def _task03_throughput_bucket_rows(throughput_buckets):
    """Rows for the throughput-time table: one row per quartile bucket, cells =
    share (%) of each group's traces in that bucket — normalised within each group
    so the two distributions compare fairly despite different group sizes, the same
    encoding every Task 3 idiom uses (information equivalence)."""
    if throughput_buckets is None:
        return [["—", "—", "—"]]
    labels, _ = throughput_buckets
    shares = _task03_bucket_shares(throughput_buckets)
    rows = []
    for si, lab in enumerate(labels):
        rows.append([lab] + [f"{shares[g][si]:.0f}%" for g in _GROUPS])
    return rows


# ---------------------------------------------------------------------------
# Idioms — every one shows the SAME throughput-time bucket comparison
# ---------------------------------------------------------------------------

def task03_bar_chart(throughput_buckets, output_dir: str,
                      attr_label: str = "Throughput time",
                      attr_title: str = "Throughput Time"):
    """Grouped bars: share (%) of each group's traces per throughput-time quartile
    bucket (normalised within group), Conformant vs. Non-conformant."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    width = 0.38

    if throughput_buckets is not None:
        labels, _ = throughput_buckets
        shares = _task03_bucket_shares(throughput_buckets)
        x = np.arange(len(labels))
        bars_c  = ax.bar(x - width / 2, shares["Conformant"],     width, color=_COLOR_CONFORM,
                         label="Conformant",     edgecolor="white")
        bars_nc = ax.bar(x + width / 2, shares["Non-conformant"], width, color=_COLOR_NON_CONFORM,
                         label="Non-conformant", edgecolor="white")
        max_h = max([b.get_height() for b in (*bars_c, *bars_nc)], default=0)
        for bars in (bars_c, bars_nc):
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + max_h * 0.01,
                            f"{h:.0f}%", ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
        ax.set_ylabel("% of group's traces", fontsize=FONT_LABEL)
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
    fig.suptitle(_SUPTITLE_FMT.format(attr_title), fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    save_svg(fig, os.path.join(output_dir, "task03_bar_chart.svg"))


def task03_table(throughput_buckets, output_dir: str,
                  attr_label: str = "Throughput time",
                  attr_title: str = "Throughput Time"):
    """One table: throughput-time quartile buckets × per-group within-group share (%)."""
    throughput_rows   = _task03_throughput_bucket_rows(throughput_buckets)
    throughput_labels = [attr_label, "Conformant (% of group)", "Non-conformant (% of group)"]

    fig_h = max(4.0, 1.4 + max(1, len(throughput_rows)) * 0.5)
    fig = plt.figure(figsize=(9, fig_h))
    ax = fig.add_subplot(111); ax.axis("off")
    make_table(
        ax, cell_text=throughput_rows, col_labels=throughput_labels,
        bbox=[0.05, 0.02, 0.90, 0.86], col_widths=auto_col_widths(throughput_labels, throughput_rows),
        font_size=10, cell_pad=0.09,
    )

    fig.suptitle(_SUPTITLE_FMT.format(attr_title), fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, os.path.join(output_dir, "task03_table.svg"))


def task03_table_and_bar_chart(throughput_buckets, output_dir: str,
                                attr_label: str = "Throughput time",
                                attr_title: str = "Throughput Time"):
    """Left: throughput-bucket table (within-group share % per group). Right: grouped
    horizontal bars of the same within-group shares — one encoding in two forms."""
    throughput_rows   = _task03_throughput_bucket_rows(throughput_buckets)
    throughput_labels = [attr_label, "Conformant (% of group)", "Non-conformant (% of group)"]

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
        labels, _ = throughput_buckets
        shares = _task03_bucket_shares(throughput_buckets)
        x = np.arange(len(labels)); w = 0.38
        ax_bar.barh(x - w / 2, shares["Conformant"],     w, color=_COLOR_CONFORM,
                    label="Conformant",     edgecolor="white")
        ax_bar.barh(x + w / 2, shares["Non-conformant"], w, color=_COLOR_NON_CONFORM,
                    label="Non-conformant", edgecolor="white")
        ax_bar.set_yticks(x)
        ax_bar.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
        ax_bar.set_xlabel("% of group's traces", fontsize=FONT_LABEL)
    else:
        ax_bar.text(0.5, 0.5, f"{attr_label}: no variance to bucket", ha="center", va="center",
                    transform=ax_bar.transAxes, fontsize=FONT_ANNOT)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    handles, lbls = ax_bar.get_legend_handles_labels()
    if handles:
        fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=2, frameon=False, fontsize=FONT_ANNOT)
    fig.suptitle(_SUPTITLE_FMT.format(attr_title), fontsize=FONT_TITLE, y=0.99)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    save_svg(fig, os.path.join(output_dir, "task03_table_and_bar_chart.svg"))


def task03_stacked_bar(throughput_buckets, output_dir: str,
                        attr_label: str = "Throughput time",
                        attr_title: str = "Throughput Time"):
    """100%-stacked bar per conformance group; segments = throughput-time quartile
    buckets, segment height = share (%) of that group's traces in the bucket. The
    within-group normalisation keeps it consistent with the bar_chart / table /
    matrix idioms and makes the two distributions comparable despite group sizes."""
    path = os.path.join(output_dir, "task03_stacked_bar.svg")
    if throughput_buckets is None:
        render_empty_state_svg(path, _SUPTITLE_FMT.format(attr_title),
                               f"{attr_label}: no variance to bucket.")
        return

    labels, _ = throughput_buckets
    shares = _task03_bucket_shares(throughput_buckets)
    data = np.array([[shares[g][si] for g in _GROUPS] for si in range(len(labels))], dtype=float)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    draw_composition_stacked_bars(ax, _GROUPS, labels, data)
    ax.set_ylabel("Share (%)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 100)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    handles, lbls = ax.get_legend_handles_labels()
    if handles:
        fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=min(len(lbls), 4), frameon=False, fontsize=FONT_ANNOT,
                   title=attr_label, title_fontsize=FONT_ANNOT)
    fig.suptitle(_SUPTITLE_FMT.format(attr_title), fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0.10, 1, 0.93])
    save_svg(fig, path)


def task03_matrix(throughput_buckets, output_dir: str,
                   attr_label: str = "Throughput time",
                   attr_title: str = "Throughput Time"):
    """Numeric grid — each column filled with its conformance-group colour, the
    same cividis dark-blue / yellow the bar_chart and stacked_bar use (uniform
    per column, so it encodes the GROUP, not the value: distinct from a
    value-encoded heatmap). Rows = throughput-time quartile buckets, columns =
    conformance group, cells = share (%) of that group's traces in the bucket."""
    path = os.path.join(output_dir, "task03_matrix.svg")
    if throughput_buckets is None:
        render_empty_state_svg(path, _SUPTITLE_FMT.format(attr_title),
                               f"{attr_label}: no variance to bucket.")
        return

    tt_labels, _ = throughput_buckets
    shares = _task03_bucket_shares(throughput_buckets)
    data = np.array([[shares[g][si] for g in _GROUPS] for si in range(len(tt_labels))], dtype=float)
    n_rows, n_cols = len(tt_labels), len(_GROUPS)
    col_fill = [_COLOR_CONFORM, _COLOR_NON_CONFORM]  # dark blue (Conformant), yellow (Non-conformant)
    col_text = [contrasting_text_color(c) for c in col_fill]

    fig_h = 0.55 * n_rows + 2.8
    fig, ax = plt.subplots(figsize=(7, fig_h))

    # Cells filled with their group's full bar_chart colour; the fill is uniform
    # within a column, so it encodes the group — never the cell value the way a
    # heatmap does. Text colour adapts to the fill so the shares stay legible.
    for ri in range(n_rows):
        for ci in range(n_cols):
            ax.add_patch(plt.Rectangle((ci, ri), 1, 1, facecolor=col_fill[ci],
                                       edgecolor="white", linewidth=1.0))
            ax.text(ci + 0.5, ri + 0.5, f"{data[ri, ci]:.0f}%",
                    ha="center", va="center", fontsize=FONT_ANNOT, color=col_text[ci])

    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.invert_yaxis()
    ax.set_xticks([c + 0.5 for c in range(n_cols)])
    ax.set_xticklabels(_GROUPS, fontsize=FONT_ANNOT)
    ax.set_yticks([r + 0.5 for r in range(n_rows)])
    ax.set_yticklabels(tt_labels, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("cell value = % of group's traces", fontsize=FONT_LABEL)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.suptitle(_SUPTITLE_FMT.format(attr_title), fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------


def generate(log, fitness_df, output_dir: str, conformant_threshold: float = 1.0,
             response_attribute: str = ""):
    """Generate all Task ID 3 SVGs into output_dir.

    `response_attribute` is what the two conformance groups are compared on;
    empty keeps throughput time, which is what the task was fixed to before.
    """
    import trace_features

    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 3 visualizations ---")

    key = response_attribute or trace_features.DURATION_KEY
    if key == trace_features.DURATION_KEY:
        attr_label, attr_title, unit = "Throughput time", "Throughput Time", "h"
    else:
        attr_label = attr_title = trace_features.label_for(key)
        unit = ""

    trace_rows, value_type = _task03_build_trace_rows(
        log, fitness_df, conformant_threshold=conformant_threshold,
        response_attribute=response_attribute)
    n_c  = sum(1 for r in trace_rows if r["group"] == "Conformant")
    n_nc = len(trace_rows) - n_c
    logger.info(f"      -> Conformant: {n_c}  |  Non-conformant: {n_nc}"
                f"  (threshold={conformant_threshold})")

    if n_c == 0:
        logger.warning("      No conformant traces — Conformant group is empty.")
    if n_nc == 0:
        logger.warning("      No non-conformant traces — Non-conformant group is empty.")

    throughput_buckets = _task03_throughput_buckets(trace_rows, unit=unit,
                                                    value_type=value_type)
    if throughput_buckets is not None:
        logger.info(f"      -> {len(throughput_buckets[0])} {attr_label} buckets.")

    task03_bar_chart(throughput_buckets, output_dir, attr_label, attr_title)
    task03_table(throughput_buckets, output_dir, attr_label, attr_title)
    task03_table_and_bar_chart(throughput_buckets, output_dir, attr_label, attr_title)
    task03_stacked_bar(throughput_buckets, output_dir, attr_label, attr_title)
    task03_matrix(throughput_buckets, output_dir, attr_label, attr_title)
