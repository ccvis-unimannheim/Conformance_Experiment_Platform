"""
tasks/task23.py – Task ID 23: Explore / Compare / Guideline violations.

Compare violation patterns against one another across the whole log.
Unit of comparison = (activity, move_type); no outcome-group split
(that is task05). Reuses the alignment_pairs_to_rows classification
from shared.py and the draw_parallel_sets helper.

Public API:
    generate(alignments, output_dir)
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "table", "table_and_bar_chart", "matrix",
          "parallel_sets"]

GT_TIER = "SEMI"

PARAM_SPEC = []

ANSWER_FORMATS = [
    {"key": "free-text", "gt_shape": "reference", "decisive_default": False},
]

RUBRIC = (
    "A complete answer names at least the two most frequent violation patterns with their "
    "occurrence counts or relative frequencies, identifies which move type (Model Move, "
    "Log Move, or Mismatch Move) dominates across all violations, and notes at least one "
    "activity-level characteristic that distinguishes patterns from one another "
    "(e.g. an activity that only appears as a Model Move, or the activity with the highest "
    "total violation count). Award full marks for correctly covering frequency, move-type "
    "distribution, and at least one distinguishing activity-level insight. Award partial "
    "marks when frequency and move type are covered but no activity-level comparison is "
    "made. Deduct marks for incorrect counts, wrong move-type attribution, or unsupported "
    "claims about severity."
)

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
    "Mismatch Move": to_hex(CIVIDIS(0.15)),    # strong (dark end)
}
_MOVE_ORDER  = ["Model Move", "Log Move", "Mismatch Move"]


# ---------------------------------------------------------------------------
# Data helper
# ---------------------------------------------------------------------------

def _task23_build_pattern_df(alignments) -> pd.DataFrame:
    """Pattern aggregation; shared implementation lives in shared.build_violation_pattern_df."""
    return build_violation_pattern_df(alignments)


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

def task23_bar_chart(pat_df: pd.DataFrame, output_dir: str):
    """Bar chart: top-N violation patterns ranked by occurrence count."""
    top    = pat_df.head(TOP_N)
    colors = [_MOVE_COLORS.get(mt, _MOVE_DEFAULT) for mt in top["move_type"]]
    ymax   = max(int(top["count"].max()), 1)

    fig, ax = plt.subplots(figsize=(max(9, len(top) * 1.6), 6.5))
    bars = ax.bar(range(len(top)), top["count"], color=colors,
                  edgecolor="white", width=0.65)
    for bar, row in zip(bars, top.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.012,
                f"{int(row.count)} ({row.pct:.1f}%)\ntr={int(row.n_traces)}",
                ha="center", va="bottom", fontsize=FONT_ANNOT - 2, linespacing=1.4)

    act_labels = [p.replace(" (", "\n(") for p in top["pattern"]]
    ax.set_xticks(range(len(top)))
    ax.set_xticklabels(act_labels, fontsize=FONT_ANNOT - 1, ha="center")
    ax.set_ylabel("Occurrences", fontsize=FONT_LABEL)
    ax.set_title(f"Top-{len(top)} Violation Patterns by Frequency", fontsize=FONT_TITLE, pad=8)
    ax.set_ylim(0, ymax * 1.28)
    _move_legend(ax, set(top["move_type"]))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task23_bar_chart.svg"))


def task23_stacked_bar(pat_df: pd.DataFrame, output_dir: str):
    """Stacked bar: one bar per activity (top-N), segments = move type."""
    act_totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts   = act_totals.head(TOP_N).index.tolist()

    act_df = pat_df[pat_df["activity"].isin(top_acts)].copy()
    pivot  = (act_df.groupby(["activity", "move_type"])["count"]
              .sum().unstack(fill_value=0).reindex(top_acts, fill_value=0))
    present_types = [mt for mt in _MOVE_ORDER if mt in pivot.columns]

    x                = np.arange(len(top_acts))
    bottoms          = np.zeros(len(top_acts))
    total_violations = int(pat_df["count"].sum())
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


def task23_table(pat_df: pd.DataFrame, output_dir: str):
    """Table: Violation Pattern | Move Type | Activity | Count | #Traces | %."""
    top   = pat_df.head(TOP_N)
    total = int(pat_df["count"].sum())
    cell_text = [
        [row["pattern"], row["move_type"], row["activity"],
         str(int(row["count"])), str(int(row["n_traces"])), f"{row['pct']:.1f}%"]
        for _, row in top.iterrows()
    ]
    cell_text.append(["Total", "—", "—", str(total), "—", "100.0%"])

    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(15, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Violation Pattern", "Move Type", "Activity",
                    "Count", "#Traces", "% of All"],
        bbox=[0.01, 0.05, 0.98, 0.88],
        col_widths=[0.34, 0.16, 0.20, 0.10, 0.10, 0.10],
        font_size=9.5,
        scale_xy=(1, 1.75),
        cell_pad=0.09,
        highlight_last_row=True,
    )
    ax.set_title(f"Top-{len(top)} Violation Patterns", fontsize=FONT_TITLE, pad=8)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task23_table.svg"))


def task23_table_and_bar_chart(pat_df: pd.DataFrame, output_dir: str):
    """Table (left) + horizontal bar chart (right) for top-N patterns."""
    top = pat_df.head(TOP_N)

    fig = plt.figure(figsize=(16, max(4.5, 1.2 + len(top) * 0.45)))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.6, 1.0], wspace=0.35)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text = [
        [row["pattern"], row["move_type"],
         str(int(row["count"])), str(int(row["n_traces"])), f"{row['pct']:.1f}%"]
        for _, row in top.iterrows()
    ]
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Violation Pattern", "Move Type", "Count", "#Traces", "%"],
        bbox=[0.01, 0.05, 0.98, 0.88],
        col_widths=[0.44, 0.22, 0.13, 0.11, 0.10],
        font_size=9,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )
    fig.suptitle(f"Top-{len(top)} Violation Patterns", fontsize=FONT_TITLE, y=1.02)

    ax_bar = fig.add_subplot(gs[1])
    x      = np.arange(len(top))
    colors = [_MOVE_COLORS.get(mt, _MOVE_DEFAULT) for mt in top["move_type"]]
    ax_bar.barh(x, top["count"], color=colors, edgecolor="white")
    ax_bar.set_yticks(x)
    ax_bar.set_yticklabels(top["pattern"], fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()   # rank 1 at top, matching table row order
    ax_bar.set_xlabel("Occurrences", fontsize=FONT_LABEL)
    ax_bar.legend(
        handles=[mpatches.Patch(color=_MOVE_COLORS[mt], label=mt)
                 for mt in _MOVE_ORDER if mt in set(top["move_type"])],
        loc="lower center", bbox_to_anchor=(0.5, -0.25),
        ncol=len([mt for mt in _MOVE_ORDER if mt in set(top["move_type"])]),
        frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
        columnspacing=1.4, handletextpad=0.5,
    )
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task23_table_and_bar_chart.svg"))


def task23_matrix(pat_df: pd.DataFrame, output_dir: str):
    """Matrix heatmap: rows = activity (top-N), columns = move type, cell = count."""
    act_totals    = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts      = act_totals.head(TOP_N).index.tolist()
    present_types = [mt for mt in _MOVE_ORDER if mt in pat_df["move_type"].values]

    data = np.zeros((len(top_acts), len(present_types)))
    for ai, act in enumerate(top_acts):
        for ci, mt in enumerate(present_types):
            mask = (pat_df["activity"] == act) & (pat_df["move_type"] == mt)
            data[ai, ci] = float(pat_df.loc[mask, "count"].sum())

    if data.max() == 0:
        data[0, 0] = 0  # keep imshow happy with a valid range

    cmap = "cividis_r"   # 0 = yellow (light), high = dark
    vmax = max(data.max(), 1.0)

    total_violations = float(pat_df["count"].sum())
    fig_h = max(3.5, 0.75 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(present_types) * 2.5), fig_h))
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(present_types)))
    ax.set_xticklabels(present_types, fontsize=FONT_ANNOT)
    ax.set_yticks(range(len(top_acts)))
    ax.set_yticklabels(top_acts, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Move Type", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Count Matrix (top-{len(top_acts)} activities)",
                 fontsize=FONT_TITLE, pad=8)

    norm = Normalize(vmin=0, vmax=vmax)
    for ri in range(len(top_acts)):
        for ci in range(len(present_types)):
            val = data[ri, ci]
            tc  = contrasting_text_color(to_hex(CIVIDIS_R(norm(val))))
            pct = 100 * val / total_violations if total_violations > 0 else 0
            ax.text(ci, ri, f"{int(val)}\n({pct:.1f}%)", ha="center", va="center",
                    fontsize=FONT_ANNOT - 1, color=tc, linespacing=1.3)

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Count", fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task23_matrix.svg"))


def task23_parallel_sets(pat_df: pd.DataFrame, output_dir: str):
    """Parallel Sets: move type (left) × activity top-N + Other (right)."""
    move_types = [mt for mt in _MOVE_ORDER if mt in pat_df["move_type"].values]
    act_totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts   = act_totals.head(TOP_N_PS).index.tolist()
    has_other  = len(act_totals) > TOP_N_PS
    right_cats = top_acts + (["Other"] if has_other else [])

    matrix = np.zeros((len(move_types), len(right_cats)), dtype=int)
    for mi, mt in enumerate(move_types):
        sub = pat_df[pat_df["move_type"] == mt]
        for ci, act in enumerate(top_acts):
            matrix[mi, ci] = int(sub[sub["activity"] == act]["count"].sum())
        if has_other:
            matrix[mi, -1] = int(sub[~sub["activity"].isin(top_acts)]["count"].sum())

    move_totals      = pat_df.groupby("move_type")["count"].sum()
    total_violations = int(pat_df["count"].sum())
    left_labels  = [
        f"{mt}\n(n={int(move_totals.get(mt, 0))}, {100 * move_totals.get(mt, 0) / total_violations:.0f}%)"
        for mt in move_types
    ]
    left_colors  = [_MOVE_COLORS[mt] for mt in move_types]

    other_count    = int(pat_df[~pat_df["activity"].isin(top_acts)]["count"].sum()) if has_other else 0
    right_labels_n = (
        [f"{act}\n(n={int(act_totals.get(act, 0))}, {100 * act_totals.get(act, 0) / total_violations:.0f}%)"
         for act in top_acts]
        + ([f"Other\n(n={other_count}, {100 * other_count / total_violations:.0f}%)"] if has_other else [])
    )

    n_cats = len(right_cats)
    right_colors = [to_hex(CIVIDIS(0.15 + 0.70 * (i / max(n_cats - 1, 1)))) for i in range(n_cats)]

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
        right_colors=right_colors,
        left_title="Move Type",
        right_title="Activity",
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task23_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(alignments, output_dir: str, log=None):
    """Generate all Task ID 23 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 23 visualizations ---")

    pat_df = _task23_build_pattern_df(alignments)

    if pat_df.empty:
        logger.warning("      task23: no violation moves found — emitting zero-state SVGs.")
        for fname, title in [
            ("task23_bar_chart.svg",          "Top-N Violation Patterns"),
            ("task23_stacked_bar.svg",         "Violation Composition per Activity"),
            ("task23_table.svg",               "Violation Patterns"),
            ("task23_table_and_bar_chart.svg", "Violation Patterns"),
            ("task23_matrix.svg",              "Violation Count Matrix"),
            ("task23_parallel_sets.svg",       "Move Type vs. Activity"),
        ]:
            _empty_svg(output_dir, fname, title)
        return

    logger.info(f"      -> {len(pat_df)} unique patterns; "
                f"{int(pat_df['count'].sum())} total violations.")

    task23_bar_chart(pat_df, output_dir)
    task23_stacked_bar(pat_df, output_dir)
    task23_table(pat_df, output_dir)
    task23_table_and_bar_chart(pat_df, output_dir)
    task23_matrix(pat_df, output_dir)
    task23_parallel_sets(pat_df, output_dir)


# ---------------------------------------------------------------------------
# Ground truth (free-text answer type)
# ---------------------------------------------------------------------------

def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Auto-generate a reference narrative + rubric for admin review.

    Returns empty dict when answer_format != 'free-text'.
    Return keys: reference (str narrative), rubric (dict).
    Rubric keys: top_patterns (list), dominant_move_type (str),
                 top3_activities (list[str]), top3_patterns (list[str]).
    """
    if answer_format != "free-text":
        return {}

    pat_df = _task23_build_pattern_df(alignments)
    if pat_df.empty:
        return {
            "reference": "No guideline violations were found in this log.",
            "rubric": {
                "top_patterns": [],
                "dominant_move_type": None,
                "top3_activities": [],
                "top3_patterns": [],
            },
        }

    top = pat_df.head(TOP_N).copy()

    # --- Rubric fields ---
    top_patterns_list = [
        {
            "pattern":   r["pattern"],
            "move_type": r["move_type"],
            "activity":  r["activity"],
            "count":     int(r["count"]),
            "n_traces":  int(r["n_traces"]),
            "pct":       round(float(r["pct"]), 1),
        }
        for r in top[["pattern", "move_type", "activity", "count", "n_traces", "pct"]].to_dict("records")
    ]

    mt_totals = pat_df.groupby("move_type")["count"].sum()
    dominant_mt = mt_totals.idxmax()
    dominant_mt_pct = int(round(100 * mt_totals[dominant_mt] / mt_totals.sum(), 0))

    act_totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top3_acts  = act_totals.head(3).index.tolist()
    top3_pats  = top["pattern"].head(3).tolist()

    act_pattern_counts   = pat_df.groupby("activity")["pattern"].nunique()
    most_affected_act    = act_pattern_counts.idxmax()
    activity_pat_count   = int(act_pattern_counts[most_affected_act])

    max_traces_idx     = top["n_traces"].idxmax()
    max_traces_pattern = top.loc[max_traces_idx, "pattern"]
    max_traces         = int(top.loc[max_traces_idx, "n_traces"])

    total_patterns = len(pat_df)
    t1 = top.iloc[0]

    # --- Narrative sentences ---
    s1 = (f"The most frequent guideline violation is '{t1['pattern']}' with "
          f"{int(t1['count'])} occurrences, affecting {int(t1['n_traces'])} traces "
          f"({t1['pct']:.1f}%).")

    runners_up = [
        f"'{r['pattern']}' ({int(r['count'])} occurrences, {r['pct']:.1f}%)"
        for r in (top.iloc[i] for i in (1, 2) if len(top) > i)
    ]
    s2 = f"This is followed by {' and '.join(runners_up)}." if runners_up else ""

    s3 = (f"Across all {total_patterns} violation patterns, {dominant_mt} violations are "
          f"most prevalent, accounting for {dominant_mt_pct}% of total violation occurrences.")

    s4 = (f"The activity '{most_affected_act}' appears in {activity_pat_count} distinct "
          f"violation pattern{'s' if activity_pat_count != 1 else ''}, suggesting it is the "
          f"most problematic step in the process.")

    s5 = (f"Violations involving '{max_traces_pattern}' have the widest impact, appearing "
          f"in {max_traces} distinct traces, indicating a systemic non-conformance.")

    text = " ".join(s for s in [s1, s2, s3, s4, s5] if s)

    return {
        "reference": text,
        "rubric": {
            "top_patterns":       top_patterns_list,
            "dominant_move_type": dominant_mt,
            "top3_activities":    top3_acts,
            "top3_patterns":      top3_pats,
        },
    }
