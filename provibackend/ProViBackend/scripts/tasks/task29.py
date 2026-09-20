"""
tasks/task29.py – Task 3: Violation type summaries across all traces.

Public API:
    generate(alignments, output_dir, grouping_strategy="move_type", selection=None)
        grouping_strategy – what a violation is counted as: "move_type",
                            "activity" or "pattern" (see violation_profile)
        selection         – which groups to show, in the units of the strategy;
                            empty = all
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "heatmap", "pie_chart", "table", "stacked_bar",
          "matrix", "sunburst", "parallel_sets"]


def _param_spec():
    """The Violation-profile class's shared parameters (see violation_profile)."""
    import violation_profile
    return [violation_profile.GROUPING_STRATEGY_PARAM, *violation_profile.SELECTION_PARAMS]


PARAM_SPEC = _param_spec()

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from shared import (
    save_svg, make_table, render_empty_state_svg,
    build_violation_pattern_df, draw_value_heatmap, draw_parallel_sets,
    GREY_LIGHT, PAIR_COLORS, CIVIDIS_R,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    contrasting_text_color,
)
from tasks.task26 import _lighten


# Move-type vocabulary + colours for the activity-level idioms (stacked_bar,
# matrix, parallel_sets, tree_map, sunburst) — matches the move-type strings
# produced by alignment_pairs_to_rows / build_violation_pattern_df.
_VTYPES = ["Model Move", "Log Move"]
#: The platform's two-category pair — cividis navy and cividis bright yellow,
#: as task31 and task32 use it. It was GREY_MED over GREY_DARK: two neighbours
#: in cividis's dark half, which read as one emphasis level rather than two
#: categories, and left the bright secondary unused.
_VTYPE_COLOR = dict(zip(_VTYPES, PAIR_COLORS))

# Top-N activities (by total violation count) shown in stacked_bar/matrix/parallel_sets
_PIVOT_TOP_N = 15


def _task29_activity_type_pivot(alignments, top_n: int = _PIVOT_TOP_N):
    """(pivot, top_acts) for the activity-level idioms.

    pivot    – {(activity, move_type): count}
    top_acts – top-N activities by total violation count, descending
    """
    pat_df = build_violation_pattern_df(alignments)
    if pat_df.empty:
        return {}, []

    pivot = {(row["activity"], row["move_type"]): int(row["count"]) for _, row in pat_df.iterrows()}
    totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts = totals.head(top_n).index.tolist()
    return pivot, top_acts


# ---------------------------------------------------------------------------
# Chevron helpers (same visual style as task28)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Task 3 – Violation type summaries across all traces
# ---------------------------------------------------------------------------

# Task 3 helpers
#: Plain, without the "(Missing in Log)" / "(Unexpected in Log)" glosses these
#: labels used to carry. task04, task34 and the move tables say "Model Move" and
#: "Log Move"; a reader comparing two idioms of one task should not have to
#: decide whether "Unexpected in Log" is a third kind of move. Kept as a map so
#: the call site stays the same and a future rename has one place.
TASK29_TYPE_LABELS = {
    "Model Move": "Model Move",
    "Log Move": "Log Move",
}


def task29_violation_summary_dataframe(alignments, grouping_strategy: str = "move_type",
                                       selection=None):
    """The violation profile, in the column shape task29's idioms already read.

    Counting now comes from ``violation_profile``, shared with the other six
    tasks of this class, so a change to what counts as a violation lands in all
    of them at once. The columns are unchanged:

        move_type       the colour key — which move type this row belongs to
        violation_type  the label drawn
        count, traces   occurrences and distinct traces
        percentage      share of all violation occurrences

    ``move_type`` and ``violation_type`` mean different things per strategy,
    which is the point of the strategy: under "move_type" a row *is* a move
    type, under "activity" a row is one activity's moves of one type, and under
    "pattern" a row is one "Move on Activity" unit.

    One behavioural difference from the hand-rolled count this replaces: steps
    whose activity is a tau / hidden transition ("-", ">>", "(skip)") are no
    longer counted as violations. They name no activity, so they could never be
    attributed to one; BPIC12 has none, so its numbers are unchanged.
    """
    import violation_profile

    prof = violation_profile.profile(alignments, grouping_strategy,
                                     selection=selection, n_traces=len(alignments))
    cols = ["move_type", "violation_type", "count", "traces", "percentage"]
    if prof.empty:
        return pd.DataFrame(columns=cols)

    summary = prof.copy()
    if grouping_strategy == "move_type":
        summary["move_type"] = summary["group"]
        summary["violation_type"] = summary["group"].map(
            lambda m: TASK29_TYPE_LABELS.get(m, m))
        # The move types read in a fixed order, not by frequency: they are a
        # nominal scale the reader learns, and reordering them between datasets
        # would make two charts of the same two categories look different.
        order = ["Model Move", "Log Move"]
        summary["_order"] = summary["move_type"].apply(
            lambda x: order.index(x) if x in order else len(order))
        summary = summary.sort_values(["_order", "violation_type"]).drop(columns=["_order"])
    elif grouping_strategy == "activity":
        summary["move_type"] = summary["series"]
        summary["violation_type"] = summary["group"] + "\n(" + summary["series"] + ")"
    else:
        pairs = summary["group"].map(violation_profile.parse_pattern)
        summary["move_type"] = [p[1] if p else "" for p in pairs]
        summary["violation_type"] = summary["group"]

    summary["percentage"] = summary["pct_count"]
    summary = summary.reset_index(drop=True)
    logger.info(f"      -> Violation moves: {int(summary['count'].sum())} "
                f"in {len(summary)} {grouping_strategy} group(s)")
    return summary[cols]


# Task 3 visualizations
def task29_bar_chart(df: pd.DataFrame, output_dir: str):
    """Bar chart: occurrence count by violation type."""
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    colors = [_VTYPE_COLOR.get(mt, GREY_LIGHT) for mt in df["move_type"]]
    bars = ax.bar(df["violation_type"], df["count"], color=colors, edgecolor="white", width=0.55, alpha=0.88)
    ymax = max(df["count"].max(), 1)
    for bar, val in zip(bars, df["count"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.015,
            f"{int(val)}",
            ha="center",
            va="bottom",
            fontsize=FONT_ANNOT,
        )
    ax.set_xlabel("Violation Type", fontsize=FONT_LABEL)
    ax.set_ylabel("Number of Violations", fontsize=FONT_LABEL)
    ax.set_title("Violations by Type", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.16)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelrotation=0)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task29_bar_chart.svg"))


def task29_heatmap(df: pd.DataFrame, output_dir: str):
    """Heatmap: the count of each violation type as colour.

    No numbers in the cells, which is what separates it from the matrix
    beside it (shared.draw_value_heatmap: Matrix = annotated grid,
    Heatmap = continuous colour). It used to print the count *and* shade
    the cell, encoding one variable twice and leaving the matrix with
    nothing of its own. The ramp is cividis, not the "Greys" it had, which
    was the last greyscale figure in the task.
    """
    labels = df["violation_type"].tolist()
    values = df["count"].to_numpy(dtype=float).reshape(-1, 1)

    fig_h = max(3.2, 1.1 + len(labels) * 0.85)
    fig, ax = plt.subplots(figsize=(6.5, fig_h))
    draw_value_heatmap(
        fig, ax, values,
        row_labels=labels,
        col_labels=["Violations"],
        cbar_label="Number of Violations",
        annotate=False,
        cmap=CIVIDIS_R,
        vmax=max(float(df["count"].max()), 1.0),
    )
    ax.set_ylabel("Violation Type", fontsize=FONT_LABEL)
    ax.set_title("Violation Frequency", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task29_heatmap.svg"))


def task29_pie_chart(df: pd.DataFrame, output_dir: str):
    """Pie chart: proportion of violation move types."""
    colors = [_VTYPE_COLOR.get(mt, GREY_LIGHT) for mt in df["move_type"]]
    labels = list(df["move_type"])

    # The count in the wedge, as every other idiom of this task carries it. The
    # share stays too, but as the angle — that is the pie's encoding, not an
    # extra number. Without the count the pie was the one idiom a reader could
    # not take an absolute figure from.
    counts = list(df["count"])
    total = float(sum(counts)) or 1.0

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, _texts, autotexts = ax.pie(
        df["count"],
        colors=colors,
        startangle=90,
        autopct=lambda pct: (f"{int(round(pct / 100.0 * total))}"
                             if pct >= 1 else ""),
        pctdistance=0.68,
        wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops=dict(fontsize=FONT_ANNOT),
    )
    for color, autotext in zip(colors, autotexts):
        autotext.set_color(contrasting_text_color(color))
    ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=len(labels), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.set_title("Violation Type Proportions", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task29_pie_chart.svg"))


def task29_table(df: pd.DataFrame, output_dir: str):
    """Table: the violation types and their counts."""
    # Count only. The percentage column and the Total row were two numbers no
    # other idiom of this task carries — the bar chart, heatmap, matrix and pie
    # chart all show counts — and a table that adds a derived measure is not the
    # same information in another encoding, which is what this task varies.
    cell_text = [
        [row["violation_type"].replace("\n", " "), f"{int(row['count'])}"]
        for _, row in df.iterrows()
    ]
    col_labels = ["Violation Type", "Number of Violations"]

    fig_h = max(2.6, 1.2 + len(cell_text) * 0.55)
    fig, ax = plt.subplots(figsize=(8, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.05, 0.05, 0.90, 0.78],
        font_size=10,
        scale_xy=(1, 1.7),
    )
    ax.set_title("Violation Type Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task29_table.svg"))


# ---------------------------------------------------------------------------
# New idiom 1: Stacked bar — violation type breakdown per activity
# ---------------------------------------------------------------------------

def task29_stacked_bar(alignments, output_dir: str):
    """Horizontal stacked bar: top-N activities coloured by violation type (Model/Log)."""
    out_path = os.path.join(output_dir, "task29_stacked_bar.svg")
    pivot, top_acts = _task29_activity_type_pivot(alignments)
    if not top_acts:
        render_empty_state_svg(out_path, "Violation Type Breakdown per Activity")
        return

    # Sort activities by total violations descending (top = highest bar)
    top_acts = sorted(top_acts,
                      key=lambda a: sum(pivot.get((a, vt), 0) for vt in _VTYPES),
                      reverse=True)

    fig, ax = plt.subplots(figsize=(13, max(4.5, len(top_acts) * 0.6 + 2)))
    ax.set_facecolor("#fafbfc")

    lefts = np.zeros(len(top_acts))
    for vtype in _VTYPES:
        vals = np.array([pivot.get((a, vtype), 0) for a in top_acts], dtype=float)
        bars = ax.barh(range(len(top_acts)), vals, left=lefts,
                       color=_VTYPE_COLOR[vtype], label=vtype,
                       edgecolor="white", linewidth=0.5, height=0.65)
        # Annotate segment count when wide enough
        for i, (bar, v) in enumerate(zip(bars, vals)):
            if v > 0 and bar.get_width() > (lefts.max() + vals.max()) * 0.04:
                ax.text(lefts[i] + v / 2, i, str(int(v)),
                        ha="center", va="center",
                        fontsize=FONT_ANNOT - 1, color=contrasting_text_color(_VTYPE_COLOR[vtype]))
        lefts += vals

    # Total count annotation at bar end
    xmax = max(lefts.max(), 1)
    for i, total in enumerate(lefts):
        ax.text(total + xmax * 0.01, i, str(int(total)),
                va="center", fontsize=FONT_ANNOT, color="#333333")

    short_labels = [a if len(a) <= 30 else a[:28] + "…" for a in top_acts]
    ax.set_yticks(range(len(top_acts)))
    ax.set_yticklabels(short_labels, fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Number of violations", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Type Breakdown per Activity  (top {len(top_acts)})",
                 fontsize=FONT_TITLE)
    ax.set_xlim(0, xmax * 1.12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 2: Matrix — activity × violation type annotated grid
# ---------------------------------------------------------------------------

def task29_matrix(alignments, output_dir: str):
    """Annotated matrix: rows = top-N activities, columns = 3 violation types."""
    out_path = os.path.join(output_dir, "task29_matrix.svg")
    pivot, top_acts = _task29_activity_type_pivot(alignments)
    if not top_acts:
        render_empty_state_svg(out_path, "Activity × Violation Type Matrix")
        return

    data = np.array(
        [[pivot.get((a, vt), 0) for vt in _VTYPES] for a in top_acts],
        dtype=float,
    )
    short_labels = [a if len(a) <= 30 else a[:28] + "…" for a in top_acts]

    fig_h = max(4.0, len(top_acts) * 0.6 + 2)
    fig, ax = plt.subplots(figsize=(9, fig_h))

    draw_value_heatmap(
        fig, ax, data,
        row_labels=short_labels,
        col_labels=_VTYPES,
        xlabel="Violation Type",
        cell_fmt="{:.0f}",
        annotate=True,
        rotate_xticks=0,
        colorless=True,
    )
    ax.set_title("Activity × Violation Type Matrix", fontsize=FONT_TITLE, pad=10)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 3: Parallel Sets — violation type (left) × activity (right)
# ---------------------------------------------------------------------------

def task29_parallel_sets(alignments, output_dir: str):
    """Parallel Sets: move type (left) flows to top-N violated activities (right)."""
    out_path = os.path.join(output_dir, "task29_parallel_sets.svg")
    pivot, top_acts = _task29_activity_type_pivot(alignments)
    if not top_acts:
        render_empty_state_svg(out_path, "Parallel Sets: Violation Type × Activity")
        return

    # Build count matrix: shape (3 move_types, n_right)
    pat_df = build_violation_pattern_df(alignments)
    top_set = set(top_acts)
    right_labels = top_acts + ["Other"]
    n_right = len(right_labels)
    matrix = np.zeros((3, n_right), dtype=int)

    for vi, vtype in enumerate(_VTYPES):
        sub = pat_df[pat_df["move_type"] == vtype]
        for ai, act in enumerate(top_acts):
            row = sub[sub["activity"] == act]
            matrix[vi, ai] = int(row["count"].sum()) if not row.empty else 0
        matrix[vi, -1] = int(sub[~sub["activity"].isin(top_set)]["count"].sum())

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Violation Type × Activity", fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=_VTYPES,
        right_labels=right_labels,
        matrix=matrix,
        left_colors=[_VTYPE_COLOR[vt] for vt in _VTYPES],
        left_title="Violation Type",
        right_title="Activity",
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 4: Tree Map — violation patterns by area = count
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# New idiom 5: Sunburst — move_type (inner) → activity (outer)
# ---------------------------------------------------------------------------

def task29_sunburst(alignments, output_dir: str):
    """Sunburst: inner ring = 3 move types, outer ring = top activities per type."""
    out_path = os.path.join(output_dir, "task29_sunburst.svg")
    pat_df = build_violation_pattern_df(alignments)
    if pat_df.empty:
        render_empty_state_svg(out_path, "Violation Sunburst (Move Type → Activity)")
        return

    total = float(pat_df["count"].sum())
    if total == 0:
        render_empty_state_svg(out_path, "Violation Sunburst (Move Type → Activity)")
        return

    # Inner ring: aggregated by move_type (in canonical order)
    ring1 = pat_df.groupby("move_type")["count"].sum().reindex(_VTYPES, fill_value=0)

    # Outer ring: top-N activities per move_type, rest → "Other"
    _SB_TOP_PER_TYPE = 5
    outer_items = []  # list of (move_type, activity, count)
    for vtype in _VTYPES:
        sub = pat_df[pat_df["move_type"] == vtype].sort_values("count", ascending=False)
        top = sub.head(_SB_TOP_PER_TYPE)
        for _, row in top.iterrows():
            outer_items.append((vtype, row["activity"], int(row["count"])))
        rest_count = int(sub.iloc[_SB_TOP_PER_TYPE:]["count"].sum()) if len(sub) > _SB_TOP_PER_TYPE else 0
        if rest_count > 0:
            outer_items.append((vtype, "Other", rest_count))

    fig, ax = plt.subplots(figsize=(8.5, 7.0))
    common = dict(startangle=90, counterclock=False)

    # Inner ring
    inner_colors = [_VTYPE_COLOR[vt] for vt in _VTYPES]
    ax.pie(ring1.values, radius=0.50, colors=inner_colors,
           wedgeprops=dict(width=0.30, edgecolor="white", linewidth=1.5), **common)

    # Outer ring
    outer_values = [c for _, _, c in outer_items]
    outer_colors = [_lighten(_VTYPE_COLOR[vt], 0.45 if i % 2 == 0 else 0.35)
                    for i, (vt, _, _) in enumerate(outer_items)]
    ax.pie(outer_values, radius=0.82, colors=outer_colors,
           wedgeprops=dict(width=0.30, edgecolor="white", linewidth=1.5), **common)

    # Angle-based annotations
    def _annotate_ring(values, labels, r_mid, fontsize, colors, min_frac=0.05):
        angle = 90.0
        val_total = sum(values)
        if val_total == 0:
            return
        for i, (val, label) in enumerate(zip(values, labels)):
            frac = val / val_total
            mid_angle = angle - frac * 360.0 / 2.0
            angle -= frac * 360.0
            if frac < min_frac:
                continue
            theta = np.deg2rad(mid_angle)
            x, y = r_mid * np.cos(theta), r_mid * np.sin(theta)
            short = label if len(label) <= 14 else label[:12] + "…"
            # The count under the name. The sunburst carried neither a number
            # nor a share, so it was the only idiom here a reader could read
            # nothing off but rank.
            ax.text(x, y, f"{short}\n{int(val)}", ha="center", va="center",
                    fontsize=fontsize, color=contrasting_text_color(colors[i]),
                    linespacing=1.15)

    _annotate_ring(ring1.values, list(ring1.index), 0.35, FONT_ANNOT, inner_colors, min_frac=0.04)
    _annotate_ring(outer_values,
                   [act for _, act, _ in outer_items],
                   0.67, FONT_ANNOT - 1, outer_colors, min_frac=0.04)

    ax.legend(
        handles=[mpatches.Patch(color=_VTYPE_COLOR[vt], label=vt) for vt in _VTYPES],
        title="Move Type (inner ring)", title_fontsize=FONT_ANNOT,
        loc="lower center", bbox_to_anchor=(0.5, -0.05),
        ncol=3, frameon=False, fontsize=FONT_ANNOT,
    )
    ax.set_title("Violation Sunburst (Move Type → Activity)",
                 fontsize=FONT_TITLE, pad=10)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------

def generate(alignments, output_dir: str, grouping_strategy: str = "move_type",
             selection=None):
    """Generate all Task 29 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 29 visualizations ---")
    df = task29_violation_summary_dataframe(alignments, grouping_strategy, selection)
    if df.empty:
        logger.warning("      Skipped Task 29: no violation moves found.")
        return
    task29_bar_chart(df, output_dir)
    task29_heatmap(df, output_dir)
    task29_pie_chart(df, output_dir)
    task29_table(df, output_dir)
    task29_stacked_bar(alignments, output_dir)
    task29_matrix(alignments, output_dir)
    task29_parallel_sets(alignments, output_dir)
    task29_sunburst(alignments, output_dir)
