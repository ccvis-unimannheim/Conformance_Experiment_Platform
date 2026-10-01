"""
tasks/task23.py – Task ID 23: Explore / Compare / Guideline violations.

Compare violation patterns against one another across the whole log.
Unit of comparison = (activity, move_type); the log is not split into
groups (task05 compares two sub-logs split by a case attribute). Reuses the alignment_pairs_to_rows classification
from shared.py and the draw_parallel_sets helper.

Public API:
    generate(alignments, output_dir, log=None, activities=None)
        activities – activities whose violation patterns are shown (both move
                     types of each); None/empty = all
        log        – accepted for the calling convention; unused
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "table", "matrix",
          "parallel_sets"]


def _param_spec():
    """Only the activity selection.

    The unit stays the pattern — the task asks how the violations differ from
    one another, and "Log Move on Ship Order" is the thing that differs — but
    what an admin picks is an activity, so choosing one keeps both of its move
    types on the chart rather than making them pick each half separately.
    """
    import violation_profile
    return [violation_profile.selection_param_for("activity")]


PARAM_SPEC = _param_spec()


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from matplotlib.colors import to_hex, Normalize

from shared import (
    save_svg, make_table, draw_parallel_sets, build_violation_pattern_df,
    contrasting_text_color,
    CIVIDIS, CIVIDIS_R,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N    = 10   # max items shown in most charts (patterns or activities)
TOP_N_PS = 7    # stricter cap for parallel sets (right-side two-line labels)

_MOVE_DEFAULT = to_hex(CIVIDIS(0.50))          # mid (fallback for unknown move types)
_MOVE_COLORS = {
    "Model Move":    to_hex(CIVIDIS(0.85)),    # soft  (light end)
    "Log Move":      _MOVE_DEFAULT,            # mid
}
_MOVE_ORDER  = ["Model Move", "Log Move"]


# ---------------------------------------------------------------------------
# Data helper
# ---------------------------------------------------------------------------

def _task23_build_pattern_df(alignments, activities=None) -> pd.DataFrame:
    """One row per violation pattern, in the columns task23's idioms read.

    Counting is the Violation-profile kernel's, shared with the six other tasks
    of this class; `pct` is the share of all violation occurrences, which is
    what this task's tables have always shown.
    """
    import violation_profile

    prof = violation_profile.profile(alignments, "pattern", selection=activities,
                                     select_by="activity", n_traces=len(alignments))
    cols = ["pattern", "activity", "move_type", "count", "n_traces", "pct"]
    if prof.empty:
        return pd.DataFrame(columns=cols)
    pairs = [violation_profile.parse_pattern(g) for g in prof["group"]]
    out = pd.DataFrame({
        "pattern": prof["group"],
        "activity": [p[0] if p else "" for p in pairs],
        "move_type": [p[1] if p else "" for p in pairs],
        "count": prof["count"],
        "n_traces": prof["traces"],
        "pct": prof["pct_count"],
    })
    return out.reset_index(drop=True)


def _empty_svg(output_dir: str, fname: str, title: str):
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.axis("off")
    ax.text(0.5, 0.5, "No violations found.", ha="center", va="center",
            fontsize=12, color="#888888", transform=ax.transAxes)
    ax.set_title(title, fontsize=FONT_TITLE)
    save_svg(fig, os.path.join(output_dir, fname))


def _move_legend(ax, present_types):
    ax.legend(
        handles=[mpatches.Patch(color=_MOVE_COLORS[mt], label=mt)
                 for mt in _MOVE_ORDER if mt in present_types],
        loc="lower center", bbox_to_anchor=(0.5, -0.25),
        ncol=len([mt for mt in _MOVE_ORDER if mt in present_types]),
        frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
    )


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task23_stacked_bar(pat_df: pd.DataFrame, output_dir: str):
    """Stacked bar: one bar per activity (top-N), segments = move type."""
    act_totals = pat_df.groupby("activity")["n_traces"].sum().sort_values(ascending=False)
    top_acts   = act_totals.head(TOP_N).index.tolist()

    act_df = pat_df[pat_df["activity"].isin(top_acts)].copy()
    pivot  = (act_df.groupby(["activity", "move_type"])["n_traces"]
              .sum().unstack(fill_value=0).reindex(top_acts, fill_value=0))
    present_types = [mt for mt in _MOVE_ORDER if mt in pivot.columns]

    x                = np.arange(len(top_acts))
    bottoms          = np.zeros(len(top_acts))
    total_violations = int(pat_df["n_traces"].sum())
    min_seg          = total_violations * 0.04   # skip label if segment < 4% of total

    fig, ax = plt.subplots(figsize=(max(8, len(top_acts) * 1.1), 6.0))
    for mt in present_types:
        vals = pivot[mt].values
        ax.bar(x, vals, bottom=bottoms, color=_MOVE_COLORS[mt],
               edgecolor="white", linewidth=0.5, label=mt)
        tc = contrasting_text_color(_MOVE_COLORS[mt])
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v >= min_seg:
                pct = 100 * v / total_violations
                ax.text(xi, b + v / 2, f"{int(v)}\n({pct:.1f}%)", ha="center", va="center",
                        fontsize=FONT_ANNOT - 2, color=tc, fontweight="bold", linespacing=1.3)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels(top_acts, rotation=0, fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Violation count", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Composition per Activity (top-{len(top_acts)})",
                 fontsize=FONT_TITLE, pad=8)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task23_stacked_bar.svg"))


def task23_parallel_sets(pat_df: pd.DataFrame, output_dir: str):
    """Parallel Sets: move type (left) × activity top-N + Other (right)."""
    move_types = [mt for mt in _MOVE_ORDER if mt in pat_df["move_type"].values]
    act_totals = pat_df.groupby("activity")["n_traces"].sum().sort_values(ascending=False)
    top_acts   = act_totals.head(TOP_N_PS).index.tolist()
    has_other  = len(act_totals) > TOP_N_PS
    right_cats = top_acts + (["Other"] if has_other else [])

    matrix = np.zeros((len(move_types), len(right_cats)), dtype=int)
    for mi, mt in enumerate(move_types):
        sub = pat_df[pat_df["move_type"] == mt]
        for ci, act in enumerate(top_acts):
            matrix[mi, ci] = int(sub[sub["activity"] == act]["n_traces"].sum())
        if has_other:
            matrix[mi, -1] = int(sub[~sub["activity"].isin(top_acts)]["n_traces"].sum())

    move_totals      = pat_df.groupby("move_type")["n_traces"].sum()
    total_violations = int(pat_df["n_traces"].sum())
    left_labels  = [
        f"{mt}\n(n={int(move_totals.get(mt, 0))}, {100 * move_totals.get(mt, 0) / total_violations:.0f}%)"
        for mt in move_types
    ]
    left_colors  = [_MOVE_COLORS[mt] for mt in move_types]

    other_count    = int(pat_df[~pat_df["activity"].isin(top_acts)]["n_traces"].sum()) if has_other else 0
    right_labels_n = (
        [f"{act}\n(n={int(act_totals.get(act, 0))}, {100 * act_totals.get(act, 0) / total_violations:.0f}%)"
         for act in top_acts]
        + ([f"Other\n(n={other_count}, {100 * other_count / total_violations:.0f}%)"] if has_other else [])
    )

    fig, ax = plt.subplots(figsize=(14, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.40, 1.40)   # symmetric around 0.50 (diagram center) → title auto-centers
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Move Type vs. Activity", fontsize=FONT_TITLE, pad=8)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_labels_n,
        matrix=matrix,
        left_colors=left_colors,
        left_title="Move Type",
        right_title="Activity",
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task23_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

#: task23's heading for the four idioms it shares with task11. The two tasks
#: ask different questions of the same numbers, so the wording differs; the
#: figures do not.
_TITLE_PREFIX = "Violation Patterns Compared"


def generate(alignments, output_dir: str, log=None, activities=None):
    """Generate all Task ID 23 SVGs into output_dir.

    The four idioms task11 also draws are drawn *by* task11's renderers, from
    the same per-(activity, move type) trace coverage. The two tasks were
    showing the same violations in two shapes — task23 one flat bar per pattern
    counted in occurrences, task11 two bars per activity counted in traces — so
    a reader moving between them met two encodings of one thing. task23
    follows task11.

    Its own two idioms, the composition stacked bar and the parallel sets, have
    no task11 counterpart. They keep their shape and now read trace counts too,
    so no figure in this task contradicts another.
    """
    import tasks.task11 as task11
    import violation_profile

    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 23 visualizations ---")

    coverage, n_traces = task11._extract_trace_coverage(alignments)
    if activities:
        wanted = {str(a).strip() for a in activities}
        coverage = {pair: n for pair, n in coverage.items() if pair[0] in wanted}
    selected = [pair for pair in
                violation_profile.ordered_pairs(alignments, selection=activities)
                if pair in coverage]

    if not selected:
        logger.warning("      task23: no violation moves found — emitting zero-state SVGs.")
        for fname, title in [
            ("task23_bar_chart.svg",          "Top-N Violation Patterns"),
            ("task23_stacked_bar.svg",         "Violation Composition per Activity"),
            ("task23_table.svg",               "Violation Patterns"),
            ("task23_matrix.svg",              "Violation Count Matrix"),
            ("task23_parallel_sets.svg",       "Move Type vs. Activity"),
        ]:
            _empty_svg(output_dir, fname, title)
        return

    logger.info(f"      -> {len(selected)} violation(s) over {n_traces} traces.")

    task11.task11_bar_chart(selected, coverage, n_traces, output_dir,
                            filename="task23_bar_chart.svg", title_prefix=_TITLE_PREFIX)
    task11.task11_matrix(selected, coverage, n_traces, output_dir,
                         filename="task23_matrix.svg", title_prefix=_TITLE_PREFIX)
    task11.task11_table(selected, coverage, n_traces, output_dir,
                        filename="task23_table.svg", title_prefix=_TITLE_PREFIX)

    pat_df = _task23_build_pattern_df(alignments, activities=activities)
    task23_stacked_bar(pat_df, output_dir)
    task23_parallel_sets(pat_df, output_dir)
