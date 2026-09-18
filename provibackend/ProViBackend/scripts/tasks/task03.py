"""
tasks/task03.py – Task ID 3: Describe / Compare / Conformant vs. non-conformant
throughput time.

Every idiom contrasts the SAME factors between the Conformant
(fitness ≥ threshold) and Non-conformant (fitness < threshold) trace groups —
each selected attribute's distribution over quartile buckets, one panel per
attribute (throughput time when none is selected):
    * bar_chart            – grouped bars, # traces per bucket
    * table                – bucket table (share % per group)
    * table_and_bar_chart  – bucket table + grouped-bar panel (# traces)
    * stacked_bar          – 100%-stacked bars per group over the buckets
    * matrix               – annotated grid, buckets × group, share (%)

Public API:
    generate(log, fitness_df, output_dir, conformant_threshold=1.0,
             response_attribute=None)
        log                  – PM4Py EventLog
        fitness_df           – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir           – directory where SVGs are written
        conformant_threshold – traces with fitness ≥ this value are Conformant
        response_attribute   – attributes compared between the two groups, one
                               panel each; empty compares throughput time
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
        "label": "Attributes compared between the two groups (empty = throughput time)",
        "hint": "Each group's traces are distributed over each attribute's buckets, one panel per attribute",
        "widget": "select-many",
        "source": "log.candidate_attributes",
        "default": [],
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
_SUPTITLE_BASE = "Conformant vs. Non-conformant"


def _first_legend(axes):
    """Legend handles from the first panel that drew any.

    Every panel draws the same two series, but one that could not be bucketed
    draws none — so reading only the first axes would lose the legend whenever
    the leading attribute happened to be the unbucketable one.
    """
    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            return handles, labels
    return [], []


def _suptitle(panels) -> str:
    """One attribute keeps its name in the figure title — that is what the frozen
    screenshots show. Several, and the title is generic and each panel is named."""
    return _SUPTITLE_FMT.format(panels[0][1]) if len(panels) == 1 else _SUPTITLE_BASE


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task03_build_trace_rows(log, fitness_df: pd.DataFrame,
                             conformant_threshold: float = 1.0,
                             response_attribute: str = "") -> tuple:
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


def _task03_panels(log, fitness_df: pd.DataFrame, conformant_threshold: float,
                   attributes: list, n_buckets: int = N_TIME_BUCKETS) -> list:
    """One panel per compared attribute: ``[(label, title, buckets), ...]``.

    ``buckets`` is the ``(labels, {group: counts})`` pair every idiom draws, or
    None when the attribute has too little variance to bucket — kept in the list
    either way, so one dud attribute leaves the others drawn rather than
    blanking the figure.

    An empty ``attributes`` means throughput time, the single comparison Task 3
    made before the attribute was a choice.
    """
    import trace_features

    keys = list(attributes) or [trace_features.DURATION_KEY]
    panels = []
    for key in keys:
        if key == trace_features.DURATION_KEY:
            label, title, unit = "Throughput time", "Throughput Time", "h"
            attr = ""
        else:
            label = title = trace_features.label_for(key)
            unit, attr = "", key
        try:
            rows, value_type = _task03_build_trace_rows(
                log, fitness_df, conformant_threshold=conformant_threshold,
                response_attribute=attr)
        except (KeyError, ValueError) as e:
            logger.warning(f"      task03: skipping '{key}' — {e}")
            continue
        buckets = _task03_throughput_buckets(rows, n_buckets=n_buckets, unit=unit,
                                             value_type=value_type)
        panels.append((label, title, buckets))
    return panels


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

def task03_bar_chart(panels, output_dir: str):
    """Grouped bars per attribute: share (%) of each group's traces per bucket
    (normalised within group), Conformant vs. Non-conformant. One sub-panel per
    compared attribute."""
    ncols = max(1, len(panels))
    # ncols == 1 gives exactly the single-axes figure the frozen screenshots
    # show; a 1x1 grid and a bare subplot render identically.
    fig, axes = plt.subplots(1, ncols, figsize=(9.0 if ncols == 1 else ncols * 5.0, 5.5),
                             squeeze=False)
    width = 0.38

    for ax, (attr_label, attr_title, buckets) in zip(axes[0], panels):
        if buckets is not None:
            labels, _ = buckets
            shares = _task03_bucket_shares(buckets)
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
            if max_h > 0:
                ax.set_ylim(0, max_h * 1.22)
        else:
            ax.text(0.5, 0.5, f"{attr_label}: no variance to bucket", ha="center", va="center",
                    transform=ax.transAxes, fontsize=FONT_ANNOT)
        # With one attribute the figure title already names it; naming the axes
        # too would add a second heading the frozen screenshots do not have.
        if ncols > 1:
            ax.set_title(attr_title, fontsize=FONT_LABEL)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)

    axes[0][0].set_ylabel("% of group's traces", fontsize=FONT_LABEL)
    handles, lbls = _first_legend(axes[0])
    if handles:
        fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=2, frameon=False, fontsize=FONT_ANNOT)
    fig.suptitle(_suptitle(panels), fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    save_svg(fig, os.path.join(output_dir, "task03_bar_chart.svg"))


def task03_table(panels, output_dir: str):
    """One table per attribute: buckets x per-group within-group share (%),
    stacked down the figure."""
    nrows = max(1, len(panels))
    rows_per = [_task03_throughput_bucket_rows(b) for (_, _, b) in panels]
    heights = [max(4.0, 1.4 + max(1, len(r)) * 0.5) for r in rows_per] or [4.0]
    fig, axes = plt.subplots(nrows, 1, figsize=(9, sum(heights)), squeeze=False)

    for ax, (attr_label, attr_title, _), rows in zip(axes[:, 0], panels, rows_per):
        ax.axis("off")
        col_labels = [attr_label, "Conformant (% of group)", "Non-conformant (% of group)"]
        make_table(
            ax, cell_text=rows, col_labels=col_labels,
            bbox=[0.05, 0.02, 0.90, 0.86], col_widths=auto_col_widths(col_labels, rows),
            font_size=10, cell_pad=0.09,
        )
        if nrows > 1:
            ax.set_title(attr_title, fontsize=FONT_LABEL)

    fig.suptitle(_suptitle(panels), fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, os.path.join(output_dir, "task03_table.svg"))


def task03_table_and_bar_chart(panels, output_dir: str):
    """Left: bucket table (within-group share % per group). Right: grouped
    horizontal bars of the same shares — one encoding in two forms, one row per
    compared attribute."""
    nrows = max(1, len(panels))
    rows_per = [_task03_throughput_bucket_rows(b) for (_, _, b) in panels]
    heights = [max(5.0, 1.6 + max(1, len(r)) * 0.5) for r in rows_per] or [5.0]

    fig = plt.figure(figsize=(15, sum(heights)))
    gs_kw = {"width_ratios": [1.1, 1.0], "wspace": 0.28}
    if nrows > 1:
        gs_kw["hspace"] = 0.45
    gs = gridspec.GridSpec(nrows, 2, **gs_kw)

    bar_axes = []
    for i, ((attr_label, attr_title, buckets), rows) in enumerate(zip(panels, rows_per)):
        col_labels = [attr_label, "Conformant (% of group)", "Non-conformant (% of group)"]
        ax_t = fig.add_subplot(gs[i, 0]); ax_t.axis("off")
        make_table(
            ax_t, cell_text=rows, col_labels=col_labels,
            bbox=[0.02, 0.05, 0.96, 0.82], col_widths=auto_col_widths(col_labels, rows),
            font_size=9.5, cell_pad=0.08,
        )

        ax_bar = fig.add_subplot(gs[i, 1])
        bar_axes.append(ax_bar)
        if buckets is not None:
            labels, _ = buckets
            shares = _task03_bucket_shares(buckets)
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
        if nrows > 1:
            ax_bar.set_title(attr_title, fontsize=FONT_LABEL)
        ax_bar.spines[["top", "right"]].set_visible(False)
        ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
        ax_bar.set_axisbelow(True)

    handles, lbls = _first_legend(bar_axes)
    if handles:
        fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=2, frameon=False, fontsize=FONT_ANNOT)
    fig.suptitle(_suptitle(panels), fontsize=FONT_TITLE, y=0.99)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    save_svg(fig, os.path.join(output_dir, "task03_table_and_bar_chart.svg"))


def task03_stacked_bar(panels, output_dir: str):
    """100%-stacked bar per conformance group; segments = the attribute's
    buckets, segment height = share (%) of that group's traces in the bucket.
    The within-group normalisation keeps it consistent with the bar_chart /
    table / matrix idioms and makes the two distributions comparable despite
    group sizes."""
    path = os.path.join(output_dir, "task03_stacked_bar.svg")
    if not panels or all(b is None for (_, _, b) in panels):
        label = panels[0][0] if panels else "Throughput time"
        render_empty_state_svg(path, _suptitle(panels) if panels else _SUPTITLE_BASE,
                               f"{label}: no variance to bucket.")
        return

    ncols = len(panels)
    fig, axes = plt.subplots(1, ncols, figsize=(8.0 if ncols == 1 else ncols * 4.8, 5.5),
                             squeeze=False)
    for ax, (attr_label, attr_title, buckets) in zip(axes[0], panels):
        if buckets is None:
            ax.text(0.5, 0.5, f"{attr_label}: no variance to bucket", ha="center",
                    va="center", transform=ax.transAxes, fontsize=FONT_ANNOT)
            ax.axis("off")
            continue
        labels, _ = buckets
        shares = _task03_bucket_shares(buckets)
        data = np.array([[shares[g][si] for g in _GROUPS] for si in range(len(labels))],
                        dtype=float)
        draw_composition_stacked_bars(ax, _GROUPS, labels, data)
        ax.set_ylim(0, 100)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        if ncols > 1:
            ax.set_title(attr_title, fontsize=FONT_LABEL)
            # Each attribute has its own bucket names, so one shared figure
            # legend would label every panel with the first panel's buckets.
            ax.legend(loc="upper right", frameon=False, fontsize=FONT_ANNOT - 2,
                      title=attr_label, title_fontsize=FONT_ANNOT - 2)
    axes[0][0].set_ylabel("Share (%)", fontsize=FONT_LABEL)

    if ncols == 1:
        handles, lbls = axes[0][0].get_legend_handles_labels()
        if handles:
            fig.legend(handles, lbls, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                       ncol=min(len(lbls), 4), frameon=False, fontsize=FONT_ANNOT,
                       title=panels[0][0], title_fontsize=FONT_ANNOT)
    fig.suptitle(_suptitle(panels), fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0.10, 1, 0.93])
    save_svg(fig, path)


def task03_matrix(panels, output_dir: str):
    """Numeric grid per attribute — each column filled with its conformance-group
    colour, the same cividis dark-blue / yellow the bar_chart and stacked_bar use
    (uniform per column, so it encodes the GROUP, not the value: distinct from a
    value-encoded heatmap). Rows = buckets, columns = conformance group, cells =
    share (%) of that group's traces in the bucket."""
    path = os.path.join(output_dir, "task03_matrix.svg")
    if not panels or all(b is None for (_, _, b) in panels):
        label = panels[0][0] if panels else "Throughput time"
        render_empty_state_svg(path, _suptitle(panels) if panels else _SUPTITLE_BASE,
                               f"{label}: no variance to bucket.")
        return

    ncols = len(panels)
    n_group_cols = len(_GROUPS)
    max_rows = max(len(b[0]) for (_, _, b) in panels if b is not None)
    fig_h = 0.55 * max_rows + 2.8
    fig, axes = plt.subplots(1, ncols, figsize=(7.0 if ncols == 1 else ncols * 4.5, fig_h),
                             squeeze=False)
    col_fill = [_COLOR_CONFORM, _COLOR_NON_CONFORM]  # dark blue (Conformant), yellow (Non-conformant)
    col_text = [contrasting_text_color(c) for c in col_fill]

    for ax, (attr_label, attr_title, buckets) in zip(axes[0], panels):
        if buckets is None:
            ax.text(0.5, 0.5, f"{attr_label}: no variance to bucket", ha="center",
                    va="center", transform=ax.transAxes, fontsize=FONT_ANNOT)
            ax.axis("off")
            continue
        tt_labels, _ = buckets
        shares = _task03_bucket_shares(buckets)
        data = np.array([[shares[g][si] for g in _GROUPS] for si in range(len(tt_labels))],
                        dtype=float)
        n_rows = len(tt_labels)

        # Cells filled with their group's full bar_chart colour; the fill is
        # uniform within a column, so it encodes the group — never the cell value
        # the way a heatmap does. Text colour adapts so the shares stay legible.
        for ri in range(n_rows):
            for ci in range(n_group_cols):
                ax.add_patch(plt.Rectangle((ci, ri), 1, 1, facecolor=col_fill[ci],
                                           edgecolor="white", linewidth=1.0))
                ax.text(ci + 0.5, ri + 0.5, f"{data[ri, ci]:.0f}%",
                        ha="center", va="center", fontsize=FONT_ANNOT, color=col_text[ci])

        ax.set_xlim(0, n_group_cols)
        ax.set_ylim(0, n_rows)
        ax.invert_yaxis()
        ax.set_xticks([c + 0.5 for c in range(n_group_cols)])
        ax.set_xticklabels(_GROUPS, fontsize=FONT_ANNOT)
        ax.set_yticks([r + 0.5 for r in range(n_rows)])
        ax.set_yticklabels(tt_labels, fontsize=FONT_ANNOT - 1)
        ax.set_xlabel("cell value = % of group's traces", fontsize=FONT_LABEL)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if ncols > 1:
            ax.set_title(attr_title, fontsize=FONT_LABEL)

    fig.suptitle(_suptitle(panels), fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, conformant_threshold: float = 1.0,
             response_attribute=None):
    """Generate all Task ID 3 SVGs into output_dir.

    `response_attribute` is the list of attributes the two conformance groups are
    compared on — one panel each. Empty keeps throughput time, the single
    comparison the task was fixed to before. A bare string is accepted too, which
    is what the parameter held while it was single-select.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 3 visualizations ---")

    if isinstance(response_attribute, str):
        response_attribute = [response_attribute] if response_attribute else []
    attributes = list(response_attribute or [])

    panels = _task03_panels(log, fitness_df, conformant_threshold, attributes)

    # Conformance grouping is the same for every panel, so report it once.
    rows, _ = _task03_build_trace_rows(log, fitness_df,
                                       conformant_threshold=conformant_threshold)
    n_c  = sum(1 for r in rows if r["group"] == "Conformant")
    n_nc = len(rows) - n_c
    logger.info(f"      -> Conformant: {n_c}  |  Non-conformant: {n_nc}"
                f"  (threshold {conformant_threshold:g})")
    if n_c == 0:
        logger.warning("      No conformant traces — Conformant group is empty.")
    if n_nc == 0:
        logger.warning("      No non-conformant traces — Non-conformant group is empty.")

    for label, _title, buckets in panels:
        if buckets is None:
            logger.warning(f"      -> {label}: too little variance to bucket.")
        else:
            logger.info(f"      -> {len(buckets[0])} {label} buckets.")

    task03_bar_chart(panels, output_dir)
    task03_table(panels, output_dir)
    task03_table_and_bar_chart(panels, output_dir)
    task03_stacked_bar(panels, output_dir)
    task03_matrix(panels, output_dir)
