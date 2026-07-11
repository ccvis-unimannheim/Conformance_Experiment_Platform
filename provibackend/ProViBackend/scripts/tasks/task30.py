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

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 30 (SEMI): compare violation patterns and conformance rates across
# sub-logs defined by a case-level attribute (numeric → median split;
# categorical → one sub-log per value). Admin specifies which attribute to
# use. Answer: mc-multi statements about which sub-log is more conformant /
# which violation pattern is more prevalent, or pct-set of per-sub-log
# conformance rates.
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "compare_attribute",
        "label": "Case attribute used to split traces into sub-logs (e.g. AMOUNT_REQ)",
        "hint": "Traces are split into sub-logs by this case attribute",
        "widget": "text",
        "default": "AMOUNT_REQ",
        "required": True,
    },
]

ANSWER_FORMATS = [
    {"key": "mc-multi", "gt_shape": "mc",           "decisive_default": True},
    {"key": "pct-set",  "gt_shape": "labelled-set",  "decisive_default": True},
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
    attr = params.get("compare_attribute", "AMOUNT_REQ")
    if not attr or not str(attr).strip():
        return ["'compare_attribute' must be a non-empty attribute name."]
    return []


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Ground truth for task 30.

    pct-set  – per-sub-log conformance rate (% of traces that are fit).
    mc-multi – statements distinguishing sub-logs by conformance rate and
               top violation patterns (correct / incorrect pairs, shuffled).
    """
    import random as _rnd

    attr = str(params.get("compare_attribute", "AMOUNT_REQ")).strip()
    # split_by_attribute and helpers are defined later in this module;
    # they are safe to call here because Python resolves names at call time.
    groups, assignment, meta = split_by_attribute(log, attr)
    if groups is None or len(groups) < 2:
        return {"options": []}

    trace_df = _build_trace_df(fitness_df, assignment, meta)
    stats_df = _group_stats(trace_df, groups)
    viol_df  = _build_violation_df(alignments, assignment)
    agg_df   = _aggregate_patterns(viol_df, stats_df, groups)

    # ── pct-set: one labelled entry per sub-log ───────────────────────────
    if answer_format == "pct-set":
        return {
            "value": None,
            "options": [
                {
                    "label":   row["group"],
                    "value":   f"{round(row['pct_conform'])}%",
                    "correct": True,
                }
                for _, row in stats_df.iterrows()
            ],
        }

    if answer_format != "mc-multi":
        return {"options": []}

    # ── mc-multi ──────────────────────────────────────────────────────────
    options = []
    rng = _rnd.Random(42)

    # Dim 1 — overall conformance direction (which sub-log is more conformant)
    if len(stats_df) >= 2:
        g0, g1 = stats_df.iloc[0], stats_df.iloc[1]
        if abs(g0["pct_conform"] - g1["pct_conform"]) > 0.5:
            higher = g0["group"] if g0["pct_conform"] >= g1["pct_conform"] else g1["group"]
            lower  = g1["group"] if higher == g0["group"] else g0["group"]
            options.append({
                "label":   f"The '{higher}' sub-log has a higher conformance rate",
                "value":   f"conform_higher::{higher}",
                "correct": True,
            })
            options.append({
                "label":   f"The '{lower}' sub-log has a higher conformance rate",
                "value":   f"conform_higher::{lower}",
                "correct": False,
            })

    # Dim 2 — top-2 most distinguishing violation patterns
    if not agg_df.empty and len(groups) >= 2:
        g0_key, g1_key = groups[0], groups[1]
        r0_col, r1_col = f"{g0_key}__rate", f"{g1_key}__rate"
        if r0_col in agg_df.columns and r1_col in agg_df.columns:
            scored = agg_df.copy()
            scored["_diff"] = abs(scored[r0_col] - scored[r1_col])
            for _, row in scored.nlargest(2, "_diff").iterrows():
                pat      = row["pattern"]
                dominant = g0_key if row[r0_col] >= row[r1_col] else g1_key
                other    = g1_key if dominant == g0_key else g0_key
                options.append({
                    "label":   f"'{pat}' is more prevalent in the '{dominant}' sub-log",
                    "value":   f"pattern::{pat}::{dominant}",
                    "correct": True,
                })
                options.append({
                    "label":   f"'{pat}' is more prevalent in the '{other}' sub-log",
                    "value":   f"pattern::{pat}::{other}",
                    "correct": False,
                })

    rng.shuffle(options)
    return {"options": options}


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
    raw = [_trace_attribute_value(trace, attr) for trace in log]
    present = [v for v in raw if v is not None]
    meta = {"type": "missing", "median": None, "numeric_values": None,
            "n_missing": raw.count(None)}
    if not present:
        return None, None, meta

    floats = [_as_float(v) for v in raw]
    numeric = all(f is not None for v, f in zip(raw, floats) if v is not None)

    if numeric:
        values = [f for f in floats if f is not None]
        median = float(np.median(values))
        meta.update(type="numeric", median=median, numeric_values=floats)
        low_label  = f"{attr} ≤ {format_threshold(median)}"
        high_label = f"{attr} > {format_threshold(median)}"
        if max(values) - min(values) < 1e-12:
            # Degenerate split: every case carries the same value
            single = f"{attr} = {format_threshold(median)}"
            logger.warning(f"      task30: attribute '{attr}' has a single value "
                           f"({format_threshold(median)}) — one sub-log only.")
            assignment = [single if f is not None else None for f in floats]
            return [single], assignment, meta
        assignment = [
            None if f is None else (low_label if f <= median else high_label)
            for f in floats
        ]
        return [low_label, high_label], assignment, meta

    # Categorical: top-N most frequent values, rest -> "Other"
    meta["type"] = "categorical"
    counts = pd.Series([str(v) for v in present]).value_counts()
    top_values = counts.head(max_groups).index.tolist()
    labels = [f"{attr} = {v}" for v in top_values]
    has_other = len(counts) > max_groups
    if has_other:
        labels.append("Other")
    label_of = {v: f"{attr} = {v}" for v in top_values}
    assignment = [
        None if v is None else label_of.get(str(v), "Other" if has_other else None)
        for v in raw
    ]
    return labels, assignment, meta


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
    """Per sub-log: #traces, % conformant, mean fitness."""
    rows = []
    for g in groups:
        sub = trace_df[trace_df["group"] == g]
        n = len(sub)
        rows.append({
            "group": g,
            "n": n,
            "pct_conform": (sub["is_fit"].sum() / n * 100) if n else 0.0,
            "mean_fitness": float(sub["fitness"].mean()) if n else 0.0,
        })
    return pd.DataFrame(rows)


def _build_violation_df(alignments, assignment: list) -> pd.DataFrame:
    """Violation rows {trace_index, group, pattern} — task29's (activity,
    move-type) classification per sub-log."""
    rows = []
    for i, result in enumerate(alignments):
        if i >= len(assignment) or assignment[i] is None:
            continue
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            if step["moveType"] == "Synchronous Move":
                continue
            activity = (step["model_move"] if step["moveType"] == "Model Move"
                        else step["log_move"])
            if not activity or activity in {"-", "None", "(skip)"}:
                continue
            rows.append({
                "trace_index": i,
                "group": assignment[i],
                "pattern": f"{activity} ({step['moveType']})",
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["trace_index", "group", "pattern"])


def _aggregate_patterns(viol_df: pd.DataFrame, stats_df: pd.DataFrame,
                        groups: list, top_n: int = TOP_N) -> pd.DataFrame:
    """Top-N patterns by total occurrence count with per-group trace counts and
    rates (% of sub-log traces exhibiting the pattern)."""
    if viol_df.empty:
        cols = ["pattern", "total"]
        for g in groups:
            cols += [f"{g}__count", f"{g}__rate"]
        return pd.DataFrame(columns=cols)

    group_n = dict(zip(stats_df["group"], stats_df["n"]))
    totals = viol_df.groupby("pattern").size().sort_values(ascending=False)
    top_patterns = totals.head(top_n).index.tolist()

    traces_with = (viol_df.groupby(["pattern", "group"])["trace_index"]
                   .nunique())
    rows = []
    for pat in top_patterns:
        row = {"pattern": pat, "total": int(totals[pat])}
        for g in groups:
            cnt = int(traces_with.get((pat, g), 0))
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
