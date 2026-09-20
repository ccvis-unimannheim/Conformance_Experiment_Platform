"""
tasks/task32.py – Task ID 32: Present / Compare / Most frequent guideline violations.

What are the main violations in my process, and do they differ between sub-processes?
Detect every guideline violation, rank them by total frequency (Pareto), then break
each down across sub-logs ("sub-processes") defined by a case-level data attribute.

Distinct from task30 (which leads with the attribute split and compares RATES):
task32 leads with the whole-log FREQUENCY ranking — the "main violations" answer —
then layers the per-sub-process comparison on top. The primary metric is the raw
occurrence COUNT, not the rate.

Building blocks (sub-log split, violation extraction) are reused from task30, so a
new dataset flows through unchanged: the compare attribute is auto-detected upstream
and split_by_attribute adapts to numeric (median split) or categorical values.

Public API:
    generate(log, alignments, output_dir, compare_attribute="AMOUNT_REQ",
             split_attribute="", grouping_strategy="pattern", selection=None,
             prominence_threshold=None)
        split_attribute      – case attribute defining the sub-processes; when
                               empty, compare_attribute (auto-detected
                               upstream) is used instead
        grouping_strategy    – what a violation is counted as: "move_type",
                               "activity" or "pattern" (see violation_profile)
        selection            – which groups to show, in the units of the
                               strategy; empty = all
        prominence_threshold – minimum share (%) of all violations for one to
                               count as "main"; None keeps every violation
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "table", "matrix",
          "heatmap", "parallel_sets"]


def _param_spec():
    """The Violation-profile class's parameters, plus this task's own cut.

    task32 exposed nothing before: the sub-log attribute came from upstream
    auto-detection, so an admin could not say what "sub-process" meant for
    their study.
    """
    import violation_profile
    return [
        violation_profile.SPLIT_ATTRIBUTE_PARAM,
        violation_profile.GROUPING_STRATEGY_PARAM,
        *violation_profile.SELECTION_PARAMS,
        violation_profile.prominence_threshold_param(
            "Minimum share of all violations for a violation to count as 'main' (%)",
            "Below this, a violation is long tail and is left out of the ranking",
        ),
    ]


PARAM_SPEC = _param_spec()

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

from shared import (
    save_svg, make_table, draw_parallel_sets,
    draw_value_heatmap, draw_rate_matrix,
    draw_grouped_rate_bars, contrasting_text_color,
    render_empty_state_svg, format_threshold,
    CIVIDIS_R, PAIR_COLORS, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse the proven sub-log split + violation classification from task30.
from tasks.task30 import (
    split_by_attribute, _build_violation_df,
    _available_case_attributes,
)

TOP_N = 10
#: Width the grouped bars share, kept here so the value labels can be placed on
#: the same geometry ``draw_grouped_rate_bars`` lays out.
_BAR_WIDTH_TOTAL = 0.76
#: Navy and cividis's bright yellow first — `PAIR_COLORS`, the palette's pair for
#: two unordered groups, the same task31 uses. The old stops started in cividis's
#: olive-grey middle, which reads as a muted third category rather than as two
#: sub-processes told apart. Further stops only matter when a log splits into
#: more than two.
_GROUP_PALETTE = [*PAIR_COLORS,
                  to_hex(CIVIDIS_R(0.40)), to_hex(CIVIDIS_R(0.62))]
def _group_colors(groups: list) -> list:
    return [_GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i in range(len(groups))]


def _grid_fig_width(groups: list) -> float:
    """Figure width for matrix/heatmap: wide enough that long column (sub-process)
    labels don't collide. Scales with both group count and longest label."""
    max_label = max((len(str(g)) for g in groups), default=4)
    return max(6.5, len(groups) * 2.2, len(groups) * max_label * 0.16)


def _wrap_pattern(p: str) -> str:
    """Break "A_APPROVED (Log Move)" into two lines so the label fits a vertical
    tick horizontally instead of needing rotation."""
    return str(p).replace(" (", "\n(", 1)


# ---------------------------------------------------------------------------
# Frequency aggregation (Pareto: total count first, sub-process breakdown next)
# ---------------------------------------------------------------------------

def _aggregate_frequency(viol_df: pd.DataFrame, groups: list,
                         top_n: int = TOP_N) -> pd.DataFrame:
    """Top-N violation patterns by TOTAL occurrence count, descending.

    Columns: pattern, total, cum_pct, n_all_patterns, and one "<group>__count"
    per sub-log. cum_pct is the running share of ALL violations (over every
    pattern, not just the top-N) so the Pareto curve stays honest.

    n_all_patterns is how many distinct patterns the log holds before the cut.
    It rides along on every row so it survives the prominence filter, and lets a
    figure say "top 5 of 23" — or say nothing, when the cut removed nothing.
    Under the move_type strategy there are only ever two patterns, and a title
    reading "Top 2" claimed a ranking where the figure shows the whole set.
    """
    cols = (["pattern", "total", "cum_pct", "n_all_patterns"]
            + [f"{g}__count" for g in groups])
    if viol_df.empty:
        return pd.DataFrame(columns=cols)

    totals = viol_df.groupby("pattern").size().sort_values(ascending=False)
    grand_total = int(totals.sum())
    top_patterns = totals.head(top_n).index.tolist()

    # count = occurrences (not distinct traces) per (pattern, group)
    by_pg = viol_df.groupby(["pattern", "group"]).size()

    rows, running = [], 0
    for pat in top_patterns:
        running += int(totals[pat])
        row = {
            "pattern": pat,
            "total": int(totals[pat]),
            "cum_pct": running / grand_total * 100 if grand_total else 0.0,
            "n_all_patterns": int(len(totals)),
        }
        for g in groups:
            row[f"{g}__count"] = int(by_pg.get((pat, g), 0))
        rows.append(row)
    return pd.DataFrame(rows)


def _counts(agg_df: pd.DataFrame, groups: list) -> np.ndarray:
    """(n_patterns × n_groups) raw-count matrix."""
    if agg_df.empty:
        return np.zeros((0, len(groups)))
    return agg_df[[f"{g}__count" for g in groups]].values.astype(float)


# ---------------------------------------------------------------------------
# Idiom 1: bar_chart — Pareto of total violation frequency (whole-log ranking)
# ---------------------------------------------------------------------------

def _rotate_bar_labels(ax, bar_width_data, n_cats, longest_label, font_size,
                       margin: float = 1.25) -> bool:
    """Does a value label have to stand on end to fit inside its bar?

    Horizontal reads better and is what the bars usually have room for — ten
    patterns across four sub-processes is the crowded case, two across three is
    not. So measure instead of assuming: the bar's width in inches against the
    label's, at 0.6 em per digit, with a margin so the text never touches the
    bar's edges.
    """
    x_lo, x_hi = ax.get_xlim()
    span = (x_hi - x_lo) or max(n_cats, 1)
    axes_inches = ax.get_window_extent().width / ax.figure.dpi
    bar_inches = bar_width_data / span * axes_inches
    label_inches = longest_label * font_size * 0.6 / 72.0
    return bar_inches < label_inches * margin


def task32_bar_chart(agg_df, groups, attr, output_dir):
    """Grouped bars: per violation pattern (ranked by total), its occurrence COUNT
    in each sub-process (sub-log defined by the compare attribute, e.g. AMOUNT_REQ).

    Consistent with task30/task13, the bar chart breaks the metric down across the
    sub-process split rather than collapsing to a single whole-log total — so the
    compare attribute (AMOUNT_REQ) is actually visible. Each bar carries its own
    count; the per-cluster total is not drawn, because only this idiom and the
    table ever had one.
    """
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task32_bar_chart.svg"),
                               "Main Violations (Pareto)", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    counts = _counts(agg_df, groups)        # (n_patterns × n_groups)
    colors = _group_colors(groups)

    fig, ax = plt.subplots(figsize=(max(10, len(patterns) * 1.6), 5.8))
    x = draw_grouped_rate_bars(ax, len(patterns), groups, counts, colors,
                               width_total=_BAR_WIDTH_TOTAL)

    # The count in each bar, on the same geometry draw_grouped_rate_bars uses.
    # A bar too short to hold its label gets it just above instead.
    ymax = counts.max() if counts.size else 1.0
    bw = _BAR_WIDTH_TOTAL / max(len(groups), 1)
    offsets = (np.arange(len(groups)) - (len(groups) - 1) / 2.0) * bw
    label_size = FONT_ANNOT - 2
    longest = max((len(f"{int(v)}") for v in counts.flat if v > 0), default=1)
    rotate = _rotate_bar_labels(ax, bw, len(patterns), longest, label_size)
    for gi, color in enumerate(colors):
        for ci in range(len(patterns)):
            val = counts[ci, gi]
            if val <= 0:
                continue
            if val >= ymax * 0.12:
                ax.text(x[ci] + offsets[gi], val / 2, f"{int(val)}",
                        ha="center", va="center", fontsize=label_size,
                        color=contrasting_text_color(color),
                        rotation=90 if rotate else 0)
            else:
                ax.text(x[ci] + offsets[gi], val + ymax * 0.015, f"{int(val)}",
                        ha="center", va="bottom", fontsize=label_size,
                        color=GREY_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_pattern(p) for p in patterns],
                       rotation=0, ha="center", fontsize=FONT_ANNOT - 2)
    ax.set_ylabel("Occurrences", fontsize=FONT_LABEL)
    ax.set_ylim(0, max(ymax * 1.08, 1.0))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=FONT_ANNOT - 1, title=f"Sub-process ({attr})",
              title_fontsize=FONT_ANNOT)

    # Name a cut only where there is one. "top N" also counts violations, not
    # sub-processes: with two violations on the x axis and three bars in each
    # cluster, "top 2" read as if it meant the bars.
    n_all = int(agg_df["n_all_patterns"].iloc[0]) if "n_all_patterns" in agg_df \
        else len(patterns)
    scope = (f"Top {len(patterns)} of {n_all} Violations"
             if len(patterns) < n_all else "Violations")
    ax.set_title(f"{scope} — Frequency by Sub-process ({attr})",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 2: stacked_bar — per violation, contribution of each sub-process
# ---------------------------------------------------------------------------

def task32_stacked_bar(agg_df, groups, attr, output_dir):
    """One bar per violation (total height = total count); segments = sub-process."""
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task32_stacked_bar.svg"),
                               "Violation Frequency by Sub-process",
                               "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    counts = _counts(agg_df, groups)       # (n_patterns × n_groups)
    colors = _group_colors(groups)
    x = np.arange(len(patterns))

    fig, ax = plt.subplots(figsize=(max(10, len(patterns) * 1.5), 5.8))
    bottoms = np.zeros(len(patterns))
    for gi, (g, color) in enumerate(zip(groups, colors)):
        vals = counts[:, gi]
        lbl = g if np.any(vals > 0) else "_nolegend_"
        ax.bar(x, vals, bottom=bottoms, color=color, edgecolor="white",
               linewidth=0.5, label=lbl, width=0.7)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_pattern(p) for p in patterns],
                       rotation=0, ha="center", fontsize=FONT_ANNOT - 2)
    ax.set_ylabel("Total occurrences", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Frequency split by Sub-process ({attr})",
                 fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_stacked_bar.svg"))


# ---------------------------------------------------------------------------
# Table data shared by Idioms 4 & 5
# ---------------------------------------------------------------------------

def _freq_table_data(agg_df, groups):
    """(cell_text, col_labels, col_widths): pattern | count per sub-process.

    No Total and no Cum % column. The cumulative share is a Pareto reading no
    other idiom of this task supports, and the row total is a number only this
    table and the bar chart's cluster label ever carried — the rows are already
    ranked by it, which is what the ranking is for.
    """
    col_labels = ["Violation Pattern"] + groups
    w_pat = 0.40
    w_grp = (1.0 - w_pat) / max(len(groups), 1)
    col_widths = [w_pat] + [w_grp] * len(groups)
    cell_text = [
        [row["pattern"]] + [str(int(row[f"{g}__count"])) for g in groups]
        for _, row in agg_df.iterrows()
    ]
    return cell_text, col_labels, col_widths


# ---------------------------------------------------------------------------
# Idiom 3: table — frequency table, ranked
# ---------------------------------------------------------------------------

def task32_table(agg_df, attr, output_dir):
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task32_table.svg"),
                               "Main Violations by Sub-process", "No violations found.")
        return
    cell_text, col_labels, col_widths = _freq_table_data(agg_df, list(
        c[:-len("__count")] for c in agg_df.columns if c.endswith("__count")))

    fig_h = max(2.6, 1.3 + len(agg_df) * 0.46)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.02, 0.06, 0.96, 0.84],
        col_widths=col_widths,
        font_size=9,
        scale_xy=(1, 1.4),
    )
    ax.set_title(f"Main Violations — Frequency by Sub-process ({attr})",
                 fontsize=FONT_TITLE, pad=10)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_table.svg"))


# ---------------------------------------------------------------------------
# Idiom 4: matrix — violation (rows, ranked) × sub-process, annotated counts
# ---------------------------------------------------------------------------

def task32_matrix(agg_df, groups, attr, output_dir):
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task32_matrix.svg"),
                               "Violation Frequency Matrix", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    data = _counts(agg_df, groups)

    fig_h = max(3.0, 0.55 * len(patterns) + 1.2)
    fig, ax = plt.subplots(figsize=(_grid_fig_width(groups), fig_h))
    draw_rate_matrix(fig, ax, data, patterns, groups,
                     xlabel=f"Sub-process ({attr})",
                     cell_fmt="{:.0f}", colorless=True)
    ax.set_title("Violation Frequency Matrix (counts)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_matrix.svg"))


# ---------------------------------------------------------------------------
# Idiom 5: heatmap — same as matrix, continuous intensity
# ---------------------------------------------------------------------------

def task32_heatmap(agg_df, groups, attr, output_dir):
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task32_heatmap.svg"),
                               "Violation Frequency Heatmap", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    data = _counts(agg_df, groups)

    fig_h = max(3.0, 0.55 * len(patterns) + 1.2)
    fig, ax = plt.subplots(figsize=(_grid_fig_width(groups), fig_h))
    draw_value_heatmap(fig, ax, data, patterns, groups,
                       xlabel=f"Sub-process ({attr})",
                       cbar_label="Occurrences", annotate=False, rotate_xticks=0)
    ax.set_title("Violation Frequency Heatmap (counts)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_heatmap.svg"))


# ---------------------------------------------------------------------------
# Idiom 6: parallel_sets — sub-process → violation type (ribbon = count)
# ---------------------------------------------------------------------------

def task32_parallel_sets(agg_df, viol_df, groups, attr, output_dir):
    patterns = agg_df["pattern"].tolist() if not agg_df.empty else []
    if not patterns:
        render_empty_state_svg(os.path.join(output_dir, "task32_parallel_sets.svg"),
                               "Sub-process vs. Violation", "No violations found.")
        return
    cats = patterns + (["Other"] if not viol_df.empty else [])

    matrix = np.zeros((len(groups), max(len(cats), 1)), dtype=int)
    top_set = set(patterns)
    for gi, g in enumerate(groups):
        sub = viol_df[viol_df["group"] == g]
        for ci, pat in enumerate(patterns):
            matrix[gi, ci] = int((sub["pattern"] == pat).sum())
        if len(cats) > len(patterns):
            matrix[gi, -1] = int((~sub["pattern"].isin(top_set)).sum())

    group_n = {g: int((viol_df["group"] == g).sum()) for g in groups}
    left_labels = [f"{g}\n({group_n.get(g, 0)} viol.)" for g in groups]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(f"Parallel Sets: Sub-process ({attr}) vs. Violation",
                 fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=cats,
        matrix=matrix,
        left_colors=_group_colors(groups),
        left_title="Sub-process",
        right_title="Violation",
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task32_bar_chart.svg",       "Main Violations (Pareto)"),
    ("task32_stacked_bar.svg",     "Violation Frequency by Sub-process"),
    ("task32_table.svg",           "Main Violations by Sub-process"),
    ("task32_matrix.svg",          "Violation Frequency Matrix"),
    ("task32_heatmap.svg",         "Violation Frequency Heatmap"),
    ("task32_parallel_sets.svg",   "Sub-process vs. Violation"),
]


def generate(log, alignments, output_dir: str,
             compare_attribute: str = "AMOUNT_REQ",
             split_attribute: str = "", grouping_strategy: str = "pattern",
             selection=None, prominence_threshold: float = None):
    """Generate all Task ID 32 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 32 visualizations ---")

    # split_attribute is the class's own key; compare_attribute is what upstream
    # auto-detection supplies when the admin has not chosen.
    compare_attribute = split_attribute or compare_attribute
    groups, assignment, meta = split_by_attribute(log, compare_attribute)
    if groups is None:
        available = _available_case_attributes(log)
        logger.error(
            f"      task32: attribute '{compare_attribute}' not found in any trace. "
            f"Available case attributes: {available}"
        )
        for fname, title in _ALL_FNAMES_TITLES:
            render_empty_state_svg(
                os.path.join(output_dir, fname), title,
                f"Attribute '{compare_attribute}' not found in the event log.")
        return

    if meta["type"] == "numeric":
        logger.info(f"      -> numeric attribute '{compare_attribute}', "
                    f"median split at {format_threshold(meta['median'])}")
    else:
        logger.info(f"      -> categorical attribute '{compare_attribute}', "
                    f"{len(groups)} sub-processes")
    if meta["n_missing"]:
        logger.warning(f"      task32: {meta['n_missing']} traces without "
                       f"'{compare_attribute}' value — excluded.")

    viol_df = _build_violation_df(alignments, assignment,
                                  grouping_strategy=grouping_strategy,
                                  selection=selection)
    agg_df = _aggregate_frequency(viol_df, groups)
    logger.info(f"      -> {len(viol_df)} violation rows ({grouping_strategy} units); "
                f"top-{len(agg_df)} by frequency.")

    # "Main violations" is the task's own question, so the long tail is cut here
    # rather than left for the reader to judge off a Pareto curve. The share is
    # of every violation occurrence, which is what cum_pct is built from.
    if prominence_threshold:
        total = float(viol_df.shape[0])
        if total:
            keep = agg_df["total"] / total * 100 >= float(prominence_threshold)
            dropped = int((~keep).sum())
            if keep.any():
                agg_df = agg_df[keep].reset_index(drop=True)
                logger.info(f"      -> {dropped} below the {prominence_threshold:g}% "
                            f"'main violation' cut, {len(agg_df)} kept.")
            else:
                logger.warning(
                    f"      task32: no violation reaches {prominence_threshold:g}% of all "
                    f"occurrences — the cut is ignored so the figures are not empty.")
    for _, row in agg_df.iterrows():
        pat_ascii = str(row["pattern"]).encode("ascii", "replace").decode()
        logger.info(f"         {pat_ascii:<40} total={int(row['total']):>6}  "
                    f"cum={row['cum_pct']:.0f}%")

    task32_bar_chart(agg_df, groups, compare_attribute, output_dir)
    task32_stacked_bar(agg_df, groups, compare_attribute, output_dir)
    task32_table(agg_df, compare_attribute, output_dir)
    task32_matrix(agg_df, groups, compare_attribute, output_dir)
    task32_heatmap(agg_df, groups, compare_attribute, output_dir)
    task32_parallel_sets(agg_df, viol_df, groups, compare_attribute, output_dir)
