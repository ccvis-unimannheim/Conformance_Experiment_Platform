"""
tasks/task30.py – Task ID 30: Present / Compare / Guideline violations (attribute-based sub-logs).

Compare process conformance AND deviating behaviour between sub-logs defined by
a case-level data attribute (--compare-attribute; default AMOUNT_REQ). Numeric
attribute → median split into two sub-logs; categorical → one sub-log per value
(top-4 + "Other"). Structurally task05 with a different split axis plus a
conformance dimension; rendering reuses the shared group-comparison helpers
(draw_grouped_rate_bars, draw_composition_stacked_bars, draw_value_heatmap,
draw_parallel_sets). Violation classification reused from task29 (via
shared.alignment_pairs_to_rows); per-trace fitness reused — nothing re-run.

Sub-logs differ in size, so all charts compare RATES (% of sub-log traces
exhibiting a pattern); raw counts appear only in the Table for reference.

Public API:
    generate(log, fitness_df, alignments, output_dir, compare_attribute="AMOUNT_REQ")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "table_bar_chart",
          "parallel_sets", "stacked_bar", "matrix",
          "heatmap"]



# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "patterns"
SPLIT_STRATEGY = None  # admin chooses
import trace_features
import trace_response

PARAM_SPEC = [
    *trace_features.attribute_params(multi=False),
    *trace_features.split_params_for(),
    trace_response.PATTERN_TOP_N_PARAM,
]


RUBRIC = (
    "A complete answer identifies which sub-log has a higher conformance rate and names "
    "at least one violation pattern that is more prevalent in one sub-log than the other, "
    "with the correct direction. Award full marks for correctly identifying both the "
    "conformance direction and the top distinguishing violation patterns with approximate "
    "rates. Award partial marks for correct conformance direction only. Deduct marks for "
    "incorrect directions."
)


def validate_params(log, params) -> list:
    errors = trace_features.validate_attribute_class(params, multi=False)
    if errors:
        return errors
    attr = params.get("compare_attribute")
    if not attr or not str(attr).strip():
        return ["An attribute to split the log by is required."]
    return []


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.colors import to_hex

from shared import (
    save_svg, make_table, draw_parallel_sets, alignment_pairs_to_rows,
    draw_grouped_rate_bars, draw_composition_stacked_bars,
    draw_value_heatmap,
    render_empty_state_svg, format_threshold,
    CIVIDIS_R,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N = 10
# Categorical attributes: one sub-log per distinct value, capped at the
# MAX_CATEGORICAL_GROUPS most frequent (rest -> "Other")
MAX_CATEGORICAL_GROUPS = 4

# Sub-log palette: 5 well-separated stops across the cividis_r ramp
_GROUP_PALETTE = [to_hex(CIVIDIS_R(p)) for p in (0.15, 0.85, 0.40, 0.65, 0.28)]


# ---------------------------------------------------------------------------
# Attribute split (the part that distinguishes task30 from task05/task31)
# ---------------------------------------------------------------------------

def _trace_attribute_value(trace, attr: str):
    """Read a case attribute from a trace, tolerating both PM4Py placements:
    trace-level attributes (with or without 'case:' prefix) and replication
    on the events."""
    for key in (attr, f"case:{attr}"):
        if key in trace.attributes:
            return trace.attributes[key]
    if len(trace) > 0:
        for key in (attr, f"case:{attr}"):
            if key in trace[0]:
                return trace[0][key]
    return None


def _available_case_attributes(log) -> list:
    """Collect attribute names visible on the first trace (for error messages)."""
    if len(log) == 0:
        return []
    keys = set(log[0].attributes.keys())
    if len(log[0]) > 0:
        keys.update(k for k in log[0][0].keys() if k.startswith("case:"))
    return sorted(keys)


def _as_float(value):
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def split_by_attribute(log, attr: str, max_groups: int = MAX_CATEGORICAL_GROUPS):
    """Split cases into labelled sub-logs by a case-level data attribute.

    Returns (group_labels, assignment, meta):
        group_labels – list of sub-log labels in display order
        assignment   – list, one entry per trace: group label or None (missing value)
        meta         – {"type": "numeric"|"categorical"|"missing",
                        "median": float|None, "numeric_values": list|None,
                        "n_missing": int}
    If the attribute is missing from every trace, group_labels is None.
    """
    import trace_features

    try:
        values, value_type = trace_features.extract(log, attr)
        values, value_type = trace_features.as_bucketable(values, value_type)
    except (KeyError, ValueError) as e:
        logger.warning(f"      split_by_attribute: '{attr}' unusable — {e}")
        return None, None, {"type": "missing", "median": None,
                            "numeric_values": None, "n_missing": len(log)}

    # This call site cuts a case attribute in two at its median; task13's
    # quantile ranges are the same operation under a different strategy, which
    # is why both now go through the shared splitter.
    strategy = "binary" if value_type == "numeric" else "nominal_n"
    result = trace_features.split(values, value_type, strategy=strategy,
                                  cap=max_groups, label_prefix=attr)
    if not result:
        return None, None, result.meta

    if value_type == "numeric" and len(result.labels) == 1:
        logger.warning(f"      task30: attribute '{attr}' has a single value "
                       f"— one sub-log only.")
    return list(result.labels), result.assignment, result.meta


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _build_trace_df(fitness_df: pd.DataFrame, assignment: list, meta: dict) -> pd.DataFrame:
    """Per-trace frame: trace_index, group, fitness, is_fit (+ numeric value)."""
    n = min(len(fitness_df), len(assignment))
    df = fitness_df.iloc[:n].copy()
    df["group"] = assignment[:n]
    if meta["type"] == "numeric":
        df["value"] = meta["numeric_values"][:n]
    df = df[df["group"].notna()].reset_index(drop=True)
    return df


def _group_stats(trace_df: pd.DataFrame, groups: list) -> pd.DataFrame:
    """Per sub-log: #traces, % conformant, mean fitness.

    Delegates to the shared response helper; the column names here are this
    task's own. `is_fit` is `fitness >= 1.0`, which is the threshold passed.
    """
    import trace_response

    stats = trace_response.fitness_stats(
        trace_df["fitness"], trace_df["group"], groups,
        conformant_threshold=1.0,
    )
    return pd.DataFrame({
        "group": stats["group"],
        "n": stats["n"],
        "pct_conform": stats["pct_conformant"],
        "mean_fitness": stats["mean"],
    })


def _build_violation_df(alignments, assignment: list,
                        missing_policy: str = "drop",
                        grouping_strategy: str = None,
                        selection=None) -> pd.DataFrame:
    """Violation rows per sub-log: trace_index, group, activity, move_type, pattern.

    Extraction and grouping are now two steps (trace_response.violation_table
    and .assign_groups), so re-grouping does not re-walk the alignments and
    `activity` / `move_type` are available as columns rather than only as halves
    of the `pattern` string.

    `grouping_strategy` rewrites `pattern` to the unit that strategy counts in,
    and applies its selection, for the Violation-profile tasks that share this
    builder. Left None — task30's own use — `pattern` keeps its "activity (Move
    Type)" form and nothing is filtered.
    """
    import trace_response

    violations = trace_response.violation_table(alignments)
    if grouping_strategy:
        import violation_profile
        violations = violation_profile.select(violations, grouping_strategy, selection)
        if not violations.empty:
            violations = violations.assign(
                pattern=violation_profile.unit_labels(violations, grouping_strategy))
    return trace_response.assign_groups(violations, assignment,
                                        missing_policy=missing_policy)


def _aggregate_patterns(viol_df: pd.DataFrame, stats_df: pd.DataFrame,
                        groups: list, top_n: int = TOP_N,
                        count_level: str = "trace") -> pd.DataFrame:
    """Top-N violation patterns with a per-group breakdown.

    `count_level` decides what is counted, for both the ranking and the columns:

        "trace"       distinct traces exhibiting the pattern; the rate is then
                      the share of the sub-log's traces (never above 100%)
        "occurrence"  violating steps; the rate becomes violations per 100
                      traces and may exceed 100%

    Defaults to "trace", which matches what the rate has always meant.
    """
    if viol_df.empty:
        cols = ["pattern", "total"]
        for g in groups:
            cols += [f"{g}__count", f"{g}__rate"]
        return pd.DataFrame(columns=cols)

    group_n = dict(zip(stats_df["group"], stats_df["n"]))

    # `total` and the per-group counts must be counted the same way, or the
    # ranking and the breakdown describe different quantities and the columns do
    # not add up. They previously did not: `total` counted occurrences while the
    # per-group columns counted distinct traces. The two coincide only while no
    # trace repeats a pattern — true of BPIC12-A, not true in general (a loop
    # violating the same activity repeatedly is exactly the case that diverges).
    if count_level == "trace":
        totals = viol_df.groupby("pattern")["trace_index"].nunique()
        per_group = viol_df.groupby(["pattern", "group"])["trace_index"].nunique()
    elif count_level == "occurrence":
        totals = viol_df.groupby("pattern").size()
        per_group = viol_df.groupby(["pattern", "group"]).size()
    else:
        raise ValueError(
            f"Unknown count_level '{count_level}' — expected 'trace' or 'occurrence'."
        )

    totals = totals.sort_values(ascending=False)
    top_patterns = totals.head(top_n).index.tolist()

    rows = []
    for pat in top_patterns:
        row = {"pattern": pat, "total": int(totals[pat])}
        for g in groups:
            cnt = int(per_group.get((pat, g), 0))
            n = group_n.get(g, 0)
            row[f"{g}__count"] = cnt
            row[f"{g}__rate"] = cnt / n * 100 if n else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def _rates(agg_df: pd.DataFrame, groups: list) -> np.ndarray:
    return agg_df[[f"{g}__rate" for g in groups]].values if not agg_df.empty \
        else np.zeros((0, len(groups)))


def _group_colors(groups: list) -> list:
    return [_GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i in range(len(groups))]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task30_bar_chart(agg_df, groups, attr, output_dir):
    """Grouped bars: per violation pattern (top-N), its rate in each sub-log."""
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task30_bar_chart.svg"),
                               "Violation Rates by Sub-log", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()

    fig, ax = plt.subplots(figsize=(max(13, len(patterns) * 2.0), 6.0))
    x = draw_grouped_rate_bars(ax, len(patterns), groups, _rates(agg_df, groups),
                               _group_colors(groups))
    ax.set_xticks(x)
    ax.set_xticklabels(
        [p.replace(" (", "\n(") for p in patterns],
        fontsize=FONT_ANNOT - 1, ha="center", rotation=0,
    )
    ax.set_ylabel("% of sub-log traces exhibiting violation", fontsize=FONT_LABEL)
    ax.set_title(f"Top-{len(patterns)} Violation Patterns per Sub-log ({attr})",
                 fontsize=FONT_TITLE)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.28),
              ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2, rect=[0, 0.14, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task30_bar_chart.svg"))


def _pattern_table_data(agg_df, groups):
    """(cell_text, col_labels, col_widths) for the violation-pattern section."""
    col_labels = ["Violation Pattern"] + [f"{g}\n(n / rate)" for g in groups] + ["Total"]
    w_pat, w_tot = 0.34, 0.08
    w_grp = (1.0 - w_pat - w_tot) / max(len(groups), 1)
    col_widths = [w_pat] + [w_grp] * len(groups) + [w_tot]
    cell_text = []
    for _, row in agg_df.iterrows():
        cells = [row["pattern"]]
        for g in groups:
            cells.append(f"{int(row[f'{g}__count'])} ({row[f'{g}__rate']:.1f}%)")
        cells.append(str(int(row["total"])))
        cell_text.append(cells)
    return cell_text, col_labels, col_widths


def task30_table(agg_df, stats_df, groups, attr, output_dir):
    """Two sections: sub-log summary (conformance level) + pattern rates."""
    summary_text = [
        [row["group"], str(int(row["n"])), f"{row['pct_conform']:.1f}%",
         f"{row['mean_fitness']:.4f}"]
        for _, row in stats_df.iterrows()
    ]
    n_pat_rows = max(len(agg_df), 1)
    fig_h = max(4.5, 2.0 + len(summary_text) * 0.5 + n_pat_rows * 0.46)
    fig = plt.figure(figsize=(13, fig_h))
    gs = gridspec.GridSpec(2, 1,
                           height_ratios=[1.0 + len(summary_text) * 0.5,
                                          1.0 + n_pat_rows * 0.46],
                           hspace=0.55)

    ax_sum = fig.add_subplot(gs[0])
    ax_sum.axis("off")
    make_table(
        ax_sum,
        cell_text=summary_text,
        col_labels=["Sub-log", "#Traces", "% Conformant", "Mean Fitness"],
        bbox=[0.05, 0.05, 0.90, 0.80],
        col_widths=[0.40, 0.18, 0.21, 0.21],
        font_size=10,
        scale_xy=(1, 1.7),
        cell_pad=0.10,
    )
    ax_sum.set_title(f"Conformance per Sub-log ({attr})", fontsize=FONT_TITLE, pad=8)

    ax_pat = fig.add_subplot(gs[1])
    ax_pat.axis("off")
    if agg_df.empty:
        ax_pat.text(0.5, 0.5, "No violations found.", ha="center", va="center",
                    fontsize=11, color="#888888", transform=ax_pat.transAxes)
    else:
        cell_text, col_labels, col_widths = _pattern_table_data(agg_df, groups)
        make_table(
            ax_pat,
            cell_text=cell_text,
            col_labels=col_labels,
            bbox=[0.01, 0.05, 0.98, 0.86],
            col_widths=col_widths,
            font_size=9,
            scale_xy=(1, 1.7),
            cell_pad=0.09,
        )
    ax_pat.set_title(f"Top-{len(agg_df)} Violation Patterns per Sub-log",
                     fontsize=FONT_TITLE, pad=8)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task30_table.svg"))


def task30_table_and_bar_chart(agg_df, groups, attr, output_dir):
    """Pattern table (left) + horizontal grouped rate bars (right)."""
    if agg_df.empty:
        render_empty_state_svg(
            os.path.join(output_dir, "task30_table_and_bar_chart.svg"),
            "Violation Patterns per Sub-log", "No violations found.")
        return

    fig = plt.figure(figsize=(16, max(5.0, 1.5 + len(agg_df) * 0.50)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.35)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text, col_labels, col_widths = _pattern_table_data(agg_df, groups)
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.01, 0.05, 0.98, 0.85],
        col_widths=col_widths,
        font_size=8.5,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )

    ax_bar = fig.add_subplot(gs[1])
    patterns = agg_df["pattern"].tolist()
    x = draw_grouped_rate_bars(ax_bar, len(patterns), groups,
                               _rates(agg_df, groups), _group_colors(groups),
                               horizontal=True)
    ax_bar.set_yticks(x)
    ax_bar.set_yticklabels(patterns, fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("% of sub-log traces", fontsize=FONT_LABEL)
    ax_bar.legend(
        loc="lower center", bbox_to_anchor=(0.5, -0.28),
        ncol=len(groups), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT - 1,
    )
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    # Title centred over both subplots
    fig.suptitle(f"Top-{len(agg_df)} Violation Patterns ({attr})",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2, rect=[0, 0.12, 1, 0.95])
    save_svg(fig, os.path.join(output_dir, "task30_table_and_bar_chart.svg"))


def task30_parallel_sets(agg_df, viol_df, stats_df, groups, attr, output_dir):
    """Parallel Sets: sub-log × violation pattern (top-N + Other); ribbon = count."""
    patterns = agg_df["pattern"].tolist() if not agg_df.empty else []
    cats = patterns + (["Other"] if not viol_df.empty else [])

    matrix = np.zeros((len(groups), max(len(cats), 1)), dtype=int)
    if not viol_df.empty:
        top_set = set(patterns)
        for gi, g in enumerate(groups):
            sub = viol_df[viol_df["group"] == g]
            for ci, pat in enumerate(patterns):
                matrix[gi, ci] = int((sub["pattern"] == pat).sum())
            if len(cats) > len(patterns):
                matrix[gi, -1] = int((~sub["pattern"].isin(top_set)).sum())

    group_n = dict(zip(stats_df["group"], stats_df["n"]))
    left_labels = [f"{g}\n(n={group_n.get(g, 0)})" for g in groups]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(f"Parallel Sets: Sub-log ({attr}) vs. Violation Pattern",
                 fontsize=FONT_TITLE, pad=12)

    n_cats = max(len(cats), 1)
    cividis_cats = [to_hex(CIVIDIS_R(0.15 + 0.70 * i / max(n_cats - 1, 1)))
                    for i in range(n_cats)]
    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=cats if cats else ["(none)"],
        matrix=matrix,
        left_colors=_group_colors(groups),
        right_colors=cividis_cats,
        left_title="Sub-log",
        right_title="Violation Pattern",
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task30_parallel_sets.svg"))


def task30_stacked_bar(agg_df, groups, attr, output_dir):
    """One stacked bar per sub-log; segments = patterns (top-N) → composition."""
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task30_stacked_bar.svg"),
                               "Violation Composition per Sub-log",
                               "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()

    n_pats = len(patterns)
    cividis_segs = [to_hex(CIVIDIS_R(0.15 + 0.70 * i / max(n_pats - 1, 1)))
                    for i in range(n_pats)]
    fig, ax = plt.subplots(figsize=(max(5, len(groups) * 2.2), 5.5))
    draw_composition_stacked_bars(ax, groups, patterns, _rates(agg_df, groups),
                                  segment_colors=cividis_segs)
    ax.set_ylabel("Cumulative violation rate (%)", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Pattern Composition per Sub-log ({attr})",
                 fontsize=FONT_TITLE)
    ax.tick_params(axis="x", labelrotation=0)
    ax.set_xticklabels(
        [g.replace(" ≤ ", "\n≤ ").replace(" > ", "\n> ").replace(" = ", "\n= ")
         for g in groups],
        fontsize=FONT_ANNOT,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task30_stacked_bar.svg"))


def task30_matrix(agg_df, groups, attr, output_dir):
    """Matrix: rows = violation pattern (top-N), columns = sub-log, cell = rate."""
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task30_matrix.svg"),
                               "Violation Rate Matrix", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    data = _rates(agg_df, groups)

    fig_h = max(3.0, 0.55 * len(patterns) + 1.2)
    fig, ax = plt.subplots(figsize=(max(5, len(groups) * 2.2), fig_h))
    draw_value_heatmap(fig, ax, data, patterns, groups,
                       xlabel=f"Sub-log ({attr})", cbar_label="Rate (%)",
                       cell_fmt="{:.1f}%", annotate=True, cmap="cividis_r")
    ax.set_xticklabels(
        [g.replace(" ≤ ", "\n≤ ").replace(" > ", "\n> ").replace(" = ", "\n= ")
         for g in groups],
        fontsize=FONT_ANNOT,
    )
    ax.set_title("Violation Rate Matrix (%)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task30_matrix.svg"))


def task30_heatmap(agg_df, groups, attr, output_dir):
    """Heatmap: violation pattern × sub-log, rate, continuous (complements matrix)."""
    if agg_df.empty:
        render_empty_state_svg(os.path.join(output_dir, "task30_heatmap.svg"),
                               "Violation Rate Heatmap", "No violations found.")
        return
    patterns = agg_df["pattern"].tolist()
    data = _rates(agg_df, groups)

    fig_h = max(3.0, 0.55 * len(patterns) + 1.2)
    fig, ax = plt.subplots(figsize=(max(5, len(groups) * 2.2), fig_h))
    draw_value_heatmap(fig, ax, data, patterns, groups, xlabel=f"Sub-log ({attr})",
                       cbar_label="Rate (%)", annotate=False, rotate_xticks=20,
                       cmap="cividis_r")
    ax.set_title("Violation Rate Heatmap (%)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task30_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task30_bar_chart.svg",           "Violation Rates by Sub-log"),
    ("task30_table.svg",               "Conformance per Sub-log"),
    ("task30_table_and_bar_chart.svg", "Violation Patterns per Sub-log"),
    ("task30_parallel_sets.svg",       "Sub-log vs. Violation Pattern"),
    ("task30_stacked_bar.svg",         "Violation Composition per Sub-log"),
    ("task30_matrix.svg",              "Violation Rate Matrix"),
    ("task30_heatmap.svg",             "Violation Rate Heatmap"),
]


def generate(log, fitness_df, alignments, output_dir: str,
             compare_attribute: str = "AMOUNT_REQ"):
    """Generate all Task ID 30 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 30 visualizations ---")

    groups, assignment, meta = split_by_attribute(log, compare_attribute)
    if groups is None:
        available = _available_case_attributes(log)
        logger.error(
            f"      task30: attribute '{compare_attribute}' not found in any trace. "
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
                    f"{len(groups)} sub-logs")
    if meta["n_missing"]:
        logger.warning(f"      task30: {meta['n_missing']} traces without "
                       f"'{compare_attribute}' value — excluded from all sub-logs.")

    trace_df = _build_trace_df(fitness_df, assignment, meta)
    stats_df = _group_stats(trace_df, groups)
    for _, row in stats_df.iterrows():
        # "≤" -> "<=" so Windows cp1252 console logging cannot choke
        group_ascii = str(row["group"]).replace("≤", "<=")
        logger.info(f"         {group_ascii:<30} n={int(row['n']):>6}  "
                    f"conformant={row['pct_conform']:.1f}%  "
                    f"mean fitness={row['mean_fitness']:.4f}")

    viol_df = _build_violation_df(alignments, assignment)
    agg_df = _aggregate_patterns(viol_df, stats_df, groups)
    logger.info(f"      -> {len(viol_df)} violation rows; "
                f"top-{len(agg_df)} patterns aggregated.")
    for g in groups:
        if not viol_df.empty and (viol_df["group"] == g).sum() == 0:
            logger.warning(f"      task30: sub-log '{g}' has no violations.")

    task30_bar_chart(agg_df, groups, compare_attribute, output_dir)
    task30_table(agg_df, stats_df, groups, compare_attribute, output_dir)
    task30_table_and_bar_chart(agg_df, groups, compare_attribute, output_dir)
    task30_parallel_sets(agg_df, viol_df, stats_df, groups, compare_attribute, output_dir)
    task30_stacked_bar(agg_df, groups, compare_attribute, output_dir)
    task30_matrix(agg_df, groups, compare_attribute, output_dir)
    task30_heatmap(agg_df, groups, compare_attribute, output_dir)
