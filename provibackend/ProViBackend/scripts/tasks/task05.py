"""
tasks/task05.py – Task ID 5: Describe / Compare / Violation patterns.

Compare violation profiles between two sub-logs of one event log. The sub-logs
come from a case attribute (`split_attribute`), which is what this task's own
question — how often a set of violations occurs across different logs — asks
for. Counting is shared with the rest of the Violation-profile class; see
docs/VIOLATION_PROFILE_CLASS.md.

Public API:
    generate(log, alignments, output_dir, split_attribute="",
             grouping_strategy="pattern", selection=None)
        log               – PM4Py EventLog
        alignments        – raw alignment results from io_helpers.run_alignments
        output_dir        – directory where SVGs are written
        split_attribute   – case attribute whose two groups are compared
        grouping_strategy – what a violation is counted as: "move_type",
                            "activity" or "pattern" (see violation_profile)
        selection         – which groups to show, in the units of the strategy;
                            empty = all
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "table", "table_and_bar_chart", "matrix",
          "parallel_sets", "box_plot", "heatmap"]


def _shared_params():
    """The Violation-profile class's split and grouping parameters.

    `split_attribute` defines the two sub-logs compared. It replaced an
    outcome-activity picker: that split two outcome groups of one log, which
    this task's own question — "across different logs" — never described.
    """
    import violation_profile
    return [violation_profile.SPLIT_ATTRIBUTE_PARAM,
            violation_profile.GROUPING_STRATEGY_PARAM,
            *violation_profile.SELECTION_PARAMS]


PARAM_SPEC = [*_shared_params()]


def validate_params(log, params) -> list:
    """Check that an attribute is named and that it splits this log in two.

    An attribute with one value throughout, or none at all, yields a single
    group — the comparison this task exists for would then be a chart of one
    series against nothing. Naming none at all is the same problem.
    """
    attr = params.get("split_attribute")
    if not attr:
        return ["Pick the attribute that splits the log into the sub-logs to compare."]
    import violation_profile
    if violation_profile.binary_split(log, attr) is None:
        return [f"Attribute '{attr}' does not split this log into two sub-logs."]
    return []


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets, alignment_pairs_to_rows,
    draw_grouped_rate_bars, draw_composition_stacked_bars, draw_rate_matrix,
    draw_grouped_box_plot, draw_value_heatmap, render_empty_state_svg,
    PAIR_COLORS, categorical_colors, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N = 10

_COLOR_POSITIVE, _COLOR_NEGATIVE = PAIR_COLORS  # cividis blue / yellow
_GROUP_COLORS   = {"Positive": _COLOR_POSITIVE, "Negative": _COLOR_NEGATIVE}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task05_groups(log, split_attribute: str = ""):
    """The two sub-logs compared, as (assignment, short_labels, long_labels).

    ``assignment`` holds the internal slot names "Positive"/"Negative" — kept so
    the aggregation and every renderer's column keys are untouched — while the
    labels are what the reader sees.

    The outcome split this task used to make is gone with the parameter that
    configured it. It compared two outcome groups of one log, which its own
    question ("across different logs") never described; the sub-log attribute
    does describe it. Without an attribute the whole log is one group, and the
    second series is empty — the task then has nothing to compare and says so.
    """
    import violation_profile

    if split_attribute:
        split = violation_profile.binary_split(log, split_attribute)
        if split:
            raw, (label_a, label_b) = split
            slot = {label_a: "Positive", label_b: "Negative"}
            return [slot.get(v) for v in raw], (label_a, label_b), (label_a, label_b)
        logger.warning("      task05: '%s' does not split the log in two.", split_attribute)

    # No second sub-log: name it rather than leaving a blank axis label.
    return ["Positive"] * len(log), ("All traces", "(no second sub-log)"), \
           ("All traces", "(no second sub-log)")


def _task05_build_violation_df(log, alignments, assignment,
                               grouping_strategy: str = "pattern",
                               selection=None) -> pd.DataFrame:
    """Per-trace violation rows labelled with their sub-log.

    The unit in ``pattern`` is whatever the grouping strategy counts in, so the
    column name is historical: under "move_type" it holds a move type, under
    "activity" an activity with its move type. Both the unit label and the
    selection come from the shared kernel, so this task cannot spell either
    differently from the other six.
    """
    import violation_profile

    rows = violation_profile.labelled_rows(alignments, grouping_strategy, selection)
    cols = ["trace_index", "group", "pattern"]
    if rows.empty:
        return pd.DataFrame(columns=cols)

    groups = [assignment[i] if i < len(assignment) else None
              for i in rows["trace_index"]]
    out = pd.DataFrame({"trace_index": rows["trace_index"],
                        "group": groups,
                        "pattern": rows["unit"]})
    # A trace outside both sub-logs (no value for the split attribute) belongs
    # to neither denominator, so it leaves rather than skewing one of them.
    return out[out["group"].notna()].reset_index(drop=True)


def _task05_aggregate(viol_df: pd.DataFrame, n_traces: dict, top_n: int = TOP_N) -> pd.DataFrame:
    """Per-pattern counts + rates per group, sorted by total count."""
    groups = ["Positive", "Negative"]

    if viol_df.empty:
        return pd.DataFrame(columns=["pattern", "Positive_count", "Positive_rate",
                                      "Negative_count", "Negative_rate", "total"])

    pattern_counts = (
        viol_df.groupby(["pattern", "group"])["trace_index"]
        .nunique()   # traces exhibiting this violation
        .reset_index()
        .rename(columns={"trace_index": "n_traces_with"})
    )

    # Pivot to wide
    wide = pattern_counts.pivot(index="pattern", columns="group",
                                values="n_traces_with").fillna(0).reset_index()
    for g in groups:
        if g not in wide.columns:
            wide[g] = 0
    wide["total"] = wide[["Positive", "Negative"]].sum(axis=1)

    for g in groups:
        ng = n_traces.get(g, 1)
        wide[f"{g}_count"] = wide[g].astype(int)
        wide[f"{g}_rate"]  = wide[g] / ng * 100 if ng else 0.0
    wide = wide.sort_values("total", ascending=False).head(top_n).reset_index(drop=True)
    return wide[["pattern", "Positive_count", "Positive_rate",
                  "Negative_count", "Negative_rate", "total"]]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task05_bar_chart(agg_df: pd.DataFrame, output_dir: str,
                     labels=("Sub-log 1", "Sub-log 2")):
    """Grouped bars: violation rate per top-N pattern for Positive vs Negative."""
    patterns = agg_df["pattern"].tolist()

    fig, ax = plt.subplots(figsize=(max(9, len(patterns) * 1.5), 5.5))
    rates = agg_df[["Positive_rate", "Negative_rate"]].values
    x = draw_grouped_rate_bars(
        ax, len(patterns), list(labels), rates,
        [_COLOR_POSITIVE, _COLOR_NEGATIVE],
    )

    wrapped = [p.replace(" (", "\n(") for p in patterns]
    ax.set_xticks(x)
    ax.set_xticklabels(wrapped, fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("% of group traces exhibiting violation", fontsize=FONT_LABEL)
    ax.set_title(f"Top-{len(patterns)} Violation Patterns by Sub-log", fontsize=FONT_TITLE)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_bar_chart.svg"))


def task05_stacked_bar(agg_df: pd.DataFrame, n_traces: dict, output_dir: str,
                       labels=("Sub-log 1", "Sub-log 2")):
    """Stacked bar: one bar per sub-log, segments = top-N patterns + Other."""
    groups   = list(labels)
    patterns = agg_df["pattern"].tolist()

    fig, ax = plt.subplots(figsize=(5, 5.5))
    draw_composition_stacked_bars(
        ax, groups, patterns,
        agg_df[["Positive_rate", "Negative_rate"]].values,
        segment_colors=categorical_colors(len(patterns)),
    )

    ax.set_ylabel("Cumulative violation rate (%)", fontsize=FONT_LABEL)
    ax.set_title("Violation Pattern Composition per Sub-log", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_stacked_bar.svg"))


def task05_table(agg_df: pd.DataFrame, output_dir: str,
                 labels=("Sub-log 1", "Sub-log 2")):
    """Table: Pattern | Positive (count / rate) | Negative (count / rate) | Total."""
    cell_text = [
        [
            row["pattern"],
            f"{int(row['Positive_count'])} ({row['Positive_rate']:.1f}%)",
            f"{int(row['Negative_count'])} ({row['Negative_rate']:.1f}%)",
            str(int(row["total"])),
        ]
        for _, row in agg_df.iterrows()
    ]
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Violation Pattern", f"{labels[0]} (n / rate)",
                    f"{labels[1]} (n / rate)", "Total"],
        bbox=[0.01, 0.05, 0.98, 0.80],
        col_widths=[0.50, 0.18, 0.18, 0.10],
        font_size=9.5,
        scale_xy=(1, 1.75),
        cell_pad=0.09,
    )
    ax.set_title(f"Top-{len(cell_text)} Violation Patterns by Sub-log",
                 fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_table.svg"))


def task05_table_and_bar_chart(agg_df: pd.DataFrame, output_dir: str,
                               labels=("Sub-log 1", "Sub-log 2")):
    """Table (left) + grouped bar chart (right) in one figure."""
    fig = plt.figure(figsize=(16, max(4.5, 1.2 + len(agg_df) * 0.45)))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.35)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text = [
        [row["pattern"],
         f"{int(row['Positive_count'])} ({row['Positive_rate']:.1f}%)",
         f"{int(row['Negative_count'])} ({row['Negative_rate']:.1f}%)",
         str(int(row["total"]))]
        for _, row in agg_df.iterrows()
    ]
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Violation Pattern", labels[0], labels[1], "Total"],
        bbox=[0.01, 0.05, 0.98, 0.82],
        col_widths=[0.52, 0.18, 0.18, 0.10],
        font_size=9,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )
    ax_tbl.set_title(f"Top-{len(agg_df)} Violation Patterns", fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    patterns = agg_df["pattern"].tolist()
    x = draw_grouped_rate_bars(
        ax_bar, len(patterns), list(labels),
        agg_df[["Positive_rate", "Negative_rate"]].values,
        [_COLOR_POSITIVE, _COLOR_NEGATIVE], horizontal=True,
    )
    ax_bar.set_yticks(x)
    ax_bar.set_yticklabels(patterns, fontsize=FONT_ANNOT - 1)
    ax_bar.set_xlabel("Rate (%)", fontsize=FONT_LABEL)
    ax_bar.legend(frameon=False, fontsize=FONT_ANNOT)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_table_and_bar_chart.svg"))


def task05_matrix(agg_df: pd.DataFrame, output_dir: str,
                  labels=("Sub-log 1", "Sub-log 2")):
    """Rate as numbers: rows = violation pattern (top-N), cols = sub-log.

    The heatmap draws the same table as colour; this one carries the rate in the
    printed number alone, so the two idioms differ in how the value is read
    rather than only in whether digits sit on top of the shading.
    """
    if agg_df.empty:
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.axis("off")
        ax.text(0.5, 0.5, "No violations found.", ha="center", va="center", fontsize=11)
        ax.set_title("Violation Rate Matrix", fontsize=FONT_TITLE)
        save_svg(fig, os.path.join(output_dir, "task05_matrix.svg"))
        return

    patterns = agg_df["pattern"].tolist()
    groups   = list(labels)
    data     = agg_df[["Positive_rate", "Negative_rate"]].values  # shape (N, 2)

    fig_h = max(3.0, 0.55 * len(patterns) + 1.2)
    fig, ax = plt.subplots(figsize=(5, fig_h))
    draw_rate_matrix(fig, ax, data, patterns, groups, xlabel="Sub-log",
                     colorless=True)
    ax.set_title("Violation Rate Matrix (%)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_matrix.svg"))


def task05_parallel_sets(agg_df: pd.DataFrame, viol_df: pd.DataFrame,
                          n_traces: dict, output_dir: str,
                          labels=("Sub-log 1", "Sub-log 2")):
    """Parallel Sets: Sub-log × Violation Pattern (top-N + Other).

    Ribbon width ∝ number of traces in the group that exhibit the pattern
    (deduplicated per trace, consistent with the table/bar idioms). Both axes
    are labelled with the count *and* its share of all flow, so the numbers on
    the left match the ribbons leaving them and the participant can read a
    percentage directly.
    """
    groups   = list(labels)
    patterns = agg_df["pattern"].tolist() if not agg_df.empty else []

    # Count matrix [n_groups × (n_patterns + Other)] at the TRACE level:
    # matrix[g, p] = # traces in group g that exhibit pattern p.
    cats = patterns + (["Other"] if not viol_df.empty else [])
    matrix = np.zeros((len(groups), len(cats)), dtype=int)

    if not agg_df.empty:
        matrix[0, :len(patterns)] = agg_df["Positive_count"].to_numpy(dtype=int)
        matrix[1, :len(patterns)] = agg_df["Negative_count"].to_numpy(dtype=int)

    if not viol_df.empty and len(cats) > len(patterns):
        top_set = set(patterns)
        for gi, g in enumerate(groups):
            sub = viol_df[viol_df["group"] == g]
            # traces (deduped) with at least one non-top pattern
            matrix[gi, -1] = int(
                sub.loc[~sub["pattern"].isin(top_set), "trace_index"].nunique())

    if matrix.sum() == 0:
        render_empty_state_svg(os.path.join(output_dir, "task05_parallel_sets.svg"),
                               "Parallel Sets: Sub-log vs. Violation Pattern",
                               "No violations found.")
        return

    total    = int(matrix.sum())
    grp_tot  = matrix.sum(axis=1)
    cat_tot  = matrix.sum(axis=0)

    def _pct(x: float) -> float:
        return (x / total * 100.0) if total else 0.0

    # Left labels: group + flow count + % of all flow (matches the bar height).
    left_labels = [
        f"{g}\n{int(grp_tot[gi])} ({_pct(grp_tot[gi]):.0f}%)"
        for gi, g in enumerate(groups)
    ]
    # Right labels: pattern + flow count + % of all flow.
    right_labels = [
        f"{c}  —  {int(cat_tot[ci])} ({_pct(cat_tot[ci]):.0f}%)"
        for ci, c in enumerate(cats)
    ]

    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    ax.axis("off")
    ax.set_xlim(-0.16, 1.28)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Sub-log vs. Violation Pattern",
                 fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_labels,
        matrix=matrix,
        # Colour means only the pattern (navy = most frequent, as on the heatmap
        # where dark = more); the sub-logs are outlined and named.
        left_colors=["white", "white"],
        left_edgecolor="#333333",
        right_colors=categorical_colors(len(cats)),
        ribbon_colors_by="right",
        ribbon_alpha=0.55,
        left_title="Sub-log",
        right_title="Violation Pattern",
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

_GROUPS = ["Positive", "Negative"]


def task05_box_plot(log, viol_df: pd.DataFrame, assignment, output_dir: str,
                    labels=("Sub-log 1", "Sub-log 2")):
    """Violations-per-trace distribution per sub-log (zero-violation traces included).

    Individual per-trace points are overlaid as a jittered strip so the
    distribution stays readable even when most traces have zero violations (a
    plain box then collapses to a flat line). Each group is annotated with the
    share of its traces that exhibit at least one violation — the percentage the
    task is really asking for — plus the group size and mean.

    Takes the assignment rather than recomputing the split: it used to derive
    the group from the outcome activity a second time, so this one figure could
    disagree with the other seven about which trace sat where.
    """
    per_trace = viol_df.groupby("trace_index").size() if not viol_df.empty else pd.Series(dtype=int)
    data = {g: [] for g in _GROUPS}
    for i, _trace in enumerate(log):
        g = assignment[i] if i < len(assignment) else None
        if g is None:
            continue
        data[g].append(int(per_trace.get(i, 0)))
    arrays = [np.array(data[g]) for g in _GROUPS]
    if all(a.size == 0 for a in arrays):
        render_empty_state_svg(os.path.join(output_dir, "task05_box_plot.svg"),
                               "Violations per Trace", "No traces.")
        return

    fig, ax = plt.subplots(figsize=(6.5, 6))
    draw_grouped_box_plot(ax, arrays, list(labels), [_COLOR_POSITIVE, _COLOR_NEGATIVE],
                          ylabel="Violations per trace", ylim=None)

    # Overlay individual traces as a jittered strip so a mostly-zero group is
    # not reduced to a single line + outlier point.
    rng = np.random.default_rng(42)
    for xi, arr in enumerate(arrays, start=1):
        if arr.size == 0:
            continue
        jitter = rng.uniform(-0.09, 0.09, arr.size)
        ax.scatter(np.full(arr.size, xi) + jitter, arr,
                   s=12, color="#333333", alpha=0.30, linewidths=0, zorder=4)

    # Per-group annotation: % of traces with >=1 violation (the answer unit),
    # group size, and mean violations per trace.
    y_max = max((int(a.max()) if a.size else 0) for a in arrays)
    head_room = max(y_max * 0.18, 0.6)
    for xi, (g, arr) in enumerate(zip(_GROUPS, arrays), start=1):
        n = int(arr.size)
        pct = (int(np.count_nonzero(arr)) / n * 100.0) if n else 0.0
        mean = float(arr.mean()) if n else 0.0
        ax.text(xi, y_max + head_room,
                f"{pct:.1f}% with ≥1 violation\n(n={n} · mean {mean:.2f})",
                ha="center", va="bottom", fontsize=FONT_ANNOT, color="#333333")

    ax.set_ylim(-0.4, y_max + head_room * 2.4 + 0.6)
    ax.set_title("Violations per Trace by Sub-log\n"
                 "(% = traces in group with at least one violation)",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_box_plot.svg"))


def task05_heatmap(agg_df: pd.DataFrame, output_dir: str,
                   labels=("Sub-log 1", "Sub-log 2")):
    """Violation pattern × sub-log, rate, continuous colour (complements the matrix)."""
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task05_heatmap.svg"),
                               "Violation Rate Heatmap", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    data = agg_df[["Positive_rate", "Negative_rate"]].values
    fig_h = max(3.0, 0.55 * len(patterns) + 1.2)
    fig, ax = plt.subplots(figsize=(5, fig_h))
    draw_value_heatmap(fig, ax, data, patterns, list(labels), xlabel="Sub-log",
                       cbar_label="Rate (%)", annotate=False)
    ax.set_title("Violation Rate Heatmap (%)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str, split_attribute: str = "",
             grouping_strategy: str = "pattern", selection=None):
    """Generate all Task ID 5 SVGs into output_dir.

    `split_attribute` names the case attribute whose two groups are compared.
    Without one the whole log is a single group and there is nothing to compare
    against, which is logged as a warning rather than drawn as a second empty
    series.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 5 visualizations ---")
    if not split_attribute:
        logger.warning("      task05: no split attribute — the whole log is one group, "
                       "so there is nothing to compare it against.")

    assignment, short_labels, long_labels = _task05_groups(log, split_attribute)

    # n_traces keys stay the internal slot names the aggregation pivots on.
    n_traces = {"Positive": 0, "Negative": 0}
    for slot in assignment:
        if slot in n_traces:
            n_traces[slot] += 1
    logger.info(f"      -> {short_labels[0]}: {n_traces['Positive']}  |  "
                f"{short_labels[1]}: {n_traces['Negative']}")
    for slot, name in zip(("Positive", "Negative"), short_labels):
        if n_traces[slot] == 0:
            logger.warning(f"      task05: '{name}' holds no traces.")

    viol_df = _task05_build_violation_df(log, alignments, assignment,
                                         grouping_strategy, selection)
    logger.info(f"      -> {len(viol_df)} violation rows extracted "
                f"({grouping_strategy} units).")

    agg_df = _task05_aggregate(viol_df, n_traces)
    logger.info(f"      -> Top-{len(agg_df)} violation groups aggregated.")

    task05_bar_chart(agg_df, output_dir, long_labels)
    task05_stacked_bar(agg_df, n_traces, output_dir, short_labels)
    task05_table(agg_df, output_dir, short_labels)
    task05_table_and_bar_chart(agg_df, output_dir, short_labels)
    task05_matrix(agg_df, output_dir, short_labels)
    task05_parallel_sets(agg_df, viol_df, n_traces, output_dir, short_labels)
    task05_box_plot(log, viol_df, assignment, output_dir, short_labels)
    task05_heatmap(agg_df, output_dir, short_labels)
