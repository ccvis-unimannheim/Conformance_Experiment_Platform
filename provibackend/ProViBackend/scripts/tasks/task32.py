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
    generate(log, alignments, output_dir, compare_attribute="AMOUNT_REQ")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "boxplot", "table",
          "table_bar_chart", "matrix", "heatmap", "parallel_sets"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets,
    draw_value_heatmap, draw_rate_matrix, draw_grouped_box_plot,
    render_empty_state_svg, format_threshold,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse the proven sub-log split + violation classification from task30.
from tasks.task30 import (
    split_by_attribute, _build_violation_df,
    _available_case_attributes,
)

TOP_N = 10
_GROUP_PALETTE = [GREY_MED, GREY_LIGHT, "#333333", "#CCCCCC", "#888888"]
_PARETO_BAR = "#9A9A9A"      # medium grey for frequency bars


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

    Columns: pattern, total, cum_pct, and one "<group>__count" per sub-log.
    cum_pct is the running share of ALL violations (over every pattern, not just
    the top-N) so the Pareto curve stays honest.
    """
    cols = ["pattern", "total", "cum_pct"] + [f"{g}__count" for g in groups]
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


def _violations_per_trace(viol_df: pd.DataFrame, assignment: list,
                          groups: list) -> dict:
    """group -> np.array of per-trace violation counts (includes 0 for clean traces)."""
    per_trace_counts = (viol_df.groupby("trace_index").size()
                        if not viol_df.empty else pd.Series(dtype=int))
    out = {g: [] for g in groups}
    for i, g in enumerate(assignment):
        if g is None or g not in out:
            continue
        out[g].append(int(per_trace_counts.get(i, 0)))
    return {g: np.asarray(v, dtype=float) for g, v in out.items()}


# ---------------------------------------------------------------------------
# Idiom 1: bar_chart — Pareto of total violation frequency (whole-log ranking)
# ---------------------------------------------------------------------------

def task32_bar_chart(agg_df, attr, output_dir):
    """Pareto chart: bars = total count (desc), line = cumulative % of all violations."""
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task32_bar_chart.svg"),
                               "Main Violations (Pareto)", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    totals = agg_df["total"].values
    x = np.arange(len(patterns))

    fig, ax = plt.subplots(figsize=(max(10, len(patterns) * 1.5), 5.8))
    ax.bar(x, totals, color=_PARETO_BAR, edgecolor="white", linewidth=0.6, width=0.7)
    for xi, t in zip(x, totals):
        ax.text(xi, t, f"{int(t)}", ha="center", va="bottom",
                fontsize=FONT_ANNOT - 1, color="#444444")
    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_pattern(p) for p in patterns],
                       rotation=0, ha="center", fontsize=FONT_ANNOT - 2)
    ax.set_ylabel("Total occurrences", fontsize=FONT_LABEL)
    ax.set_ylim(0, totals.max() * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)

    ax.set_title(f"Main Violations — Frequency Ranking (top {len(patterns)})",
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
# Idiom 3: boxplot — violations-per-trace distribution per sub-process
# ---------------------------------------------------------------------------

def task32_boxplot(viol_df, assignment, groups, attr, output_dir):
    """How many violations does a typical trace carry, and does that differ by sub-process?"""
    per_group = _violations_per_trace(viol_df, assignment, groups)
    data = [per_group[g] for g in groups]
    colors = _group_colors(groups)

    if all(arr.size == 0 for arr in data):
        render_empty_state_svg(os.path.join(output_dir, "task32_boxplot.svg"),
                               "Violations per Trace by Sub-process",
                               "No traces in any sub-process.")
        return

    vmax = max((arr.max() for arr in data if arr.size), default=1.0)
    fig, ax = plt.subplots(figsize=(_grid_fig_width(groups), 6))
    draw_grouped_box_plot(ax, data, groups, colors,
                          ylabel="Violations per trace",
                          ylim=(-0.3, vmax + 1))
    ax.tick_params(axis="x", labelrotation=0)
    ax.set_title(f"Violations per Trace by Sub-process ({attr})", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_boxplot.svg"))


# ---------------------------------------------------------------------------
# Table data shared by Idioms 4 & 5
# ---------------------------------------------------------------------------

def _freq_table_data(agg_df, groups):
    """(cell_text, col_labels, col_widths): pattern | per-sub-process count | Total | Cum %."""
    col_labels = ["Violation Pattern"] + groups + ["Total", "Cum %"]
    w_pat, w_tot, w_cum = 0.34, 0.09, 0.09
    w_grp = (1.0 - w_pat - w_tot - w_cum) / max(len(groups), 1)
    col_widths = [w_pat] + [w_grp] * len(groups) + [w_tot, w_cum]
    cell_text = []
    for _, row in agg_df.iterrows():
        cells = [row["pattern"]]
        cells += [str(int(row[f"{g}__count"])) for g in groups]
        cells += [str(int(row["total"])), f"{row['cum_pct']:.0f}%"]
        cell_text.append(cells)
    return cell_text, col_labels, col_widths


# ---------------------------------------------------------------------------
# Idiom 4: table — frequency table, ranked, with cumulative %
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
# Idiom 5: table_bar_chart — frequency table (left) + ranked total bars (right)
# ---------------------------------------------------------------------------

def task32_table_bar_chart(agg_df, groups, attr, output_dir):
    if agg_df.empty:
        render_empty_state_svg(
            os.path.join(output_dir, "task32_table_bar_chart.svg"),
            "Main Violations by Sub-process", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    totals = agg_df["total"].values

    fig = plt.figure(figsize=(17, max(4.5, 1.3 + len(agg_df) * 0.50)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.45, 1.0], wspace=0.55)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text, col_labels, col_widths = _freq_table_data(agg_df, groups)
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.01, 0.05, 0.98, 0.84],
        col_widths=col_widths,
        font_size=8.5,
        scale_xy=(1, 1.4),
    )
    ax_tbl.set_title(f"Top-{len(agg_df)} Violations ({attr})",
                     fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(patterns))
    ax_bar.barh(y, totals, color=_PARETO_BAR, edgecolor="white",
                linewidth=0.6, height=0.62)
    for yi, t in zip(y, totals):
        ax_bar.text(t, yi, f" {int(t)}", va="center", ha="left",
                    fontsize=FONT_ANNOT - 1, color="#444444")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels([_wrap_pattern(p) for p in patterns],
                           fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Total occurrences", fontsize=FONT_LABEL)
    ax_bar.set_xlim(0, totals.max() * 1.15)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)
    ax_bar.set_title("Frequency Ranking", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_table_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 6: matrix — violation (rows, ranked) × sub-process, annotated counts
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
                     cbar_label="Occurrences", cell_fmt="{:.0f}")
    ax.set_title("Violation Frequency Matrix (counts)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task32_matrix.svg"))


# ---------------------------------------------------------------------------
# Idiom 7: heatmap — same as matrix, continuous intensity
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
# Idiom 8: parallel_sets — sub-process → violation type (ribbon = count)
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

    grey_scale = ["#CCCCCC", "#AAAAAA", "#999999", "#888888", "#777777",
                  "#666666", "#555555", "#444444", "#333333", "#222222", "#BBBBBB"]
    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=cats,
        matrix=matrix,
        left_colors=_group_colors(groups),
        right_colors=[grey_scale[i % len(grey_scale)] for i in range(len(cats))],
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
    ("task32_boxplot.svg",         "Violations per Trace by Sub-process"),
    ("task32_table.svg",           "Main Violations by Sub-process"),
    ("task32_table_bar_chart.svg", "Main Violations + Frequency Ranking"),
    ("task32_matrix.svg",          "Violation Frequency Matrix"),
    ("task32_heatmap.svg",         "Violation Frequency Heatmap"),
    ("task32_parallel_sets.svg",   "Sub-process vs. Violation"),
]


def generate(log, alignments, output_dir: str,
             compare_attribute: str = "AMOUNT_REQ"):
    """Generate all Task ID 32 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 32 visualizations ---")

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

    viol_df = _build_violation_df(alignments, assignment)
    agg_df = _aggregate_frequency(viol_df, groups)
    logger.info(f"      -> {len(viol_df)} violation rows; "
                f"top-{len(agg_df)} patterns by frequency.")
    for _, row in agg_df.iterrows():
        pat_ascii = str(row["pattern"]).encode("ascii", "replace").decode()
        logger.info(f"         {pat_ascii:<40} total={int(row['total']):>6}  "
                    f"cum={row['cum_pct']:.0f}%")

    task32_bar_chart(agg_df, compare_attribute, output_dir)
    task32_stacked_bar(agg_df, groups, compare_attribute, output_dir)
    task32_boxplot(viol_df, assignment, groups, compare_attribute, output_dir)
    task32_table(agg_df, compare_attribute, output_dir)
    task32_table_bar_chart(agg_df, groups, compare_attribute, output_dir)
    task32_matrix(agg_df, groups, compare_attribute, output_dir)
    task32_heatmap(agg_df, groups, compare_attribute, output_dir)
    task32_parallel_sets(agg_df, viol_df, groups, compare_attribute, output_dir)
