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

IDIOMS = ["bar_chart", "table", "matrix", "heatmap"]


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
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from shared import (
    save_svg, make_table, alignment_pairs_to_rows,
    draw_grouped_rate_bars, draw_rate_matrix,
    draw_value_heatmap, render_empty_state_svg,
    wrap_text, PAIR_COLORS, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N = 10

_COLOR_POSITIVE, _COLOR_NEGATIVE = PAIR_COLORS  # cividis blue / yellow
_GROUP_COLORS   = {"Positive": _COLOR_POSITIVE, "Negative": _COLOR_NEGATIVE}

#: Angle the sub-log names are rotated to where they sit under a two-column
#: axis. _SUBLOG_LABELS is short enough to sit flat now; the rotation stays
#: because the tick is one column wide either way, and a name that grows —
#: those two are the only ones this module fixes — would run into its
#: neighbour again.
_SUBLOG_TICK_ROTATION = 20


def _titled(title: str, caption: str) -> str:
    """The figure's title with the split spelled out under it.

    The columns and the legend name the sub-logs generically, so without this
    line nothing on the figure says which traces are in which. It goes in the
    title because that has the whole figure to wrap into, where a column header
    has only its column — the length of an attribute value is the dataset's to
    decide, and "__start_time__ = 2025-01-15 08:56:00+00:00" is not unusual.
    """
    return f"{title}\n{caption}" if caption else title


def _wrapped_headers(headers, width: int):
    """Table headers wrapped to `width`, with the tallest one's line count.

    Matplotlib tables neither clip nor grow to fit their text: an over-long
    header runs straight into the next column, and extra lines spill out of the
    header row. Callers wrap at whatever width their column affords and add the
    returned line count to the figure height, so both directions stay inside
    the cell whatever the split attribute is called.
    """
    wrapped = [wrap_text(str(h), width) for h in headers]
    return wrapped, max(w.count("\n") + 1 for w in wrapped)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

#: What the figures call the two sub-logs. The split names them after the
#: attribute and its value, which is unbounded: "region = Germany" is 16
#: characters, "__start_time__ = 2025-01-15 08:56:00+00:00" is 42, and the long
#: one overran the table's column and spilled out of the header row. It also
#: began with an underscore, which matplotlib reads as "hide this artist", so
#: the bar chart's legend came out empty.
#:
#: The split is always in two, and which half is which does not change between
#: attributes, so naming the pair generically costs the figure nothing it was
#: reliably carrying. Which attribute was split, and where, is a property of the
#: task instance — the admin sets it on /specify and it is shown there.
_SUBLOG_LABELS = ("Selected sub-log", "Remaining traces")


def _task05_groups(log, split_attribute: str = ""):
    """The two sub-logs compared, as (assignment, labels, caption).

    ``assignment`` holds the internal slot names "Positive"/"Negative" — kept so
    the aggregation and every renderer's column keys are untouched. ``labels`` is
    what the reader sees on the columns and in the legend, and ``caption`` the
    line under each title that says what those two names stand for.

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
            caption = (f"{_SUBLOG_LABELS[0]}: {label_a}"
                       f"   ·   {_SUBLOG_LABELS[1]}: {label_b}")
            return [slot.get(v) for v in raw], _SUBLOG_LABELS, caption
        logger.warning("      task05: '%s' does not split the log in two.", split_attribute)

    # No second sub-log: name it rather than leaving a blank axis label.
    return ["Positive"] * len(log), ("All traces", "(no second sub-log)"), ""


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
                     labels=("Sub-log 1", "Sub-log 2"), caption: str = ""):
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
    ax.set_title(_titled(f"Top-{len(patterns)} Violation Patterns by Sub-log", caption),
                 fontsize=FONT_TITLE)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_bar_chart.svg"))


def task05_table(agg_df: pd.DataFrame, output_dir: str,
                 labels=("Sub-log 1", "Sub-log 2"), caption: str = ""):
    """Table: Pattern | rate per sub-log.

    The rate alone, because that is what the bar chart, the matrix and the
    heatmap draw. The table used to add the trace count behind each rate and a
    Total column of counts across both sub-logs, which no other idiom carried —
    reading the four against each other meant reading past that. The rows are
    still ordered by that total, it is just no longer a column.
    """
    cell_text = [
        [
            row["pattern"],
            f"{row['Positive_rate']:.1f}%",
            f"{row['Negative_rate']:.1f}%",
        ]
        for _, row in agg_df.iterrows()
    ]
    heads, head_lines = _wrapped_headers([labels[0], labels[1]], 20)
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46) + (head_lines - 1) * 0.22
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Violation Pattern", heads[0], heads[1]],
        bbox=[0.01, 0.05, 0.98, 0.80],
        col_widths=[0.50, 0.25, 0.25],
        font_size=9.5,
        scale_xy=(1, 1.75),
        cell_pad=0.09,
    )
    ax.set_title(_titled(f"Top-{len(cell_text)} Violation Patterns by Sub-log", caption),
                 fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_table.svg"))


def task05_matrix(agg_df: pd.DataFrame, output_dir: str,
                  labels=("Sub-log 1", "Sub-log 2"), caption: str = ""):
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
    # The sub-log names come from the split attribute ("AMOUNT_REQ ≤ 10000"),
    # so two of them side by side overrun a two-column axis; rotating is what
    # the other tasks do with labels this long.
    draw_rate_matrix(fig, ax, data, patterns, groups, xlabel="Sub-log",
                     colorless=True, rotate_xticks=_SUBLOG_TICK_ROTATION)
    ax.set_title(_titled("Violation Rate Matrix (%)", caption), fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task05_matrix.svg"))


def task05_heatmap(agg_df: pd.DataFrame, output_dir: str,
                   labels=("Sub-log 1", "Sub-log 2"), caption: str = ""):
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
                       cbar_label="Rate (%)", annotate=False,
                       rotate_xticks=_SUBLOG_TICK_ROTATION)
    ax.set_title(_titled("Violation Rate Heatmap (%)", caption), fontsize=FONT_TITLE)
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

    assignment, sublog_labels, split_caption = _task05_groups(log, split_attribute)

    # n_traces keys stay the internal slot names the aggregation pivots on.
    n_traces = {"Positive": 0, "Negative": 0}
    for slot in assignment:
        if slot in n_traces:
            n_traces[slot] += 1
    logger.info(f"      -> {sublog_labels[0]}: {n_traces['Positive']}  |  "
                f"{sublog_labels[1]}: {n_traces['Negative']}")
    for slot, name in zip(("Positive", "Negative"), sublog_labels):
        if n_traces[slot] == 0:
            logger.warning(f"      task05: '{name}' holds no traces.")

    viol_df = _task05_build_violation_df(log, alignments, assignment,
                                         grouping_strategy, selection)
    logger.info(f"      -> {len(viol_df)} violation rows extracted "
                f"({grouping_strategy} units).")

    agg_df = _task05_aggregate(viol_df, n_traces)
    logger.info(f"      -> Top-{len(agg_df)} violation groups aggregated.")

    task05_bar_chart(agg_df, output_dir, sublog_labels, split_caption)
    task05_table(agg_df, output_dir, sublog_labels, split_caption)
    task05_matrix(agg_df, output_dir, sublog_labels, split_caption)
    task05_heatmap(agg_df, output_dir, sublog_labels, split_caption)
