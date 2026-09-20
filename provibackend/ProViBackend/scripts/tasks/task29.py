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
    save_svg, make_table, render_empty_state_svg, GREY_DARK,
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


def _row_activity(violation_type: str, grouping_strategy: str) -> str:
    """The non-move-type half of a group label.

    Under "activity" the summary writes "Check Credit\n(Model Move)"; under
    "pattern" it writes the pattern, which parses into the same two halves.
    """
    if grouping_strategy == "pattern":
        import violation_profile
        parsed = violation_profile.parse_pattern(violation_type)
        return parsed[0] if parsed else violation_type
    return violation_type.split("\n(")[0]


#: The row label when the strategy has no second dimension.
_ALL_ROWS = "All Violations"


def _strategy_grid(df, grouping_strategy: str):
    """(row_labels, col_labels, counts) {EMD} the grid behind heatmap, matrix
    and stacked bar.

    Columns are always the two move types, in their fixed order: that is the
    axis these three share, and it is what the admin sees on the x axis.
    Rows are the other half of the group {EMD} the activity under the "activity" and
    "pattern" strategies, and a single row under "move_type", where there is no
    other half and the grid is one row of two cells.

    These three used to take ``alignments`` straight and build activity
    {X} move type through ``_task29_activity_type_pivot``, capped at the top 15
    activities, whatever the admin had chosen. So with the strategy on "By move
    type" the bar chart, table and pie chart showed two categories while the
    matrix beside them showed fifteen activities, and `selection` reached
    neither. Reading the same summary frame as the other idioms is what makes
    the eight agree, and what makes the parameters arrive.
    """
    cols = list(_VTYPES)
    if df.empty:
        return [], cols, np.zeros((0, len(cols)), dtype=float)

    if grouping_strategy == "move_type":
        rows = [_ALL_ROWS]
    else:
        rows, seen = [], set()
        for vt in df["violation_type"]:
            act = _row_activity(str(vt), grouping_strategy)
            if act not in seen:
                seen.add(act)
                rows.append(act)

    at = {r: i for i, r in enumerate(rows)}
    counts = np.zeros((len(rows), len(cols)), dtype=float)
    for _, r in df.iterrows():
        row = 0 if grouping_strategy == "move_type" else at.get(
            _row_activity(str(r["violation_type"]), grouping_strategy))
        if row is None or r["move_type"] not in cols:
            continue
        counts[row, cols.index(r["move_type"])] += float(r["count"])
    return rows, cols, counts


def _rotate_tick_labels(ax, n_cats: int, labels, font_size: float,
                        margin: float = 1.15) -> bool:
    """Do the category names have to stand on end to fit side by side?

    Measured rather than assumed: the width one category gets against the widest
    label's longest line, at 0.6 em per character. Two move types across a
    9-inch axis have room to spare; fifteen activities do not.
    """
    axes_inches = ax.get_window_extent().width / ax.figure.dpi
    slot_inches = axes_inches / max(n_cats, 1)
    longest = max((len(line) for lab in labels
                   for line in str(lab).split("\n")), default=1)
    return slot_inches < longest * font_size * 0.6 / 72.0 * margin


# Task 3 visualizations
def task29_bar_chart(df: pd.DataFrame, output_dir: str):
    """Bar chart: occurrence count by violation type."""
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    colors = [_VTYPE_COLOR.get(mt, GREY_LIGHT) for mt in df["move_type"]]
    # No alpha. The bars carried 0.88, which washed the navy and the yellow
    # toward each other and toward the background — every other bar chart in
    # the platform draws its categories solid.
    bars = ax.bar(df["violation_type"], df["count"], color=colors,
                  edgecolor="white", width=0.55)
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
    if _rotate_tick_labels(ax, len(df), df["violation_type"], FONT_ANNOT):
        ax.tick_params(axis="x", labelrotation=90)
        for lab in ax.get_xticklabels():
            lab.set_ha("center")
            lab.set_va("top")
    else:
        ax.tick_params(axis="x", labelrotation=0)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task29_bar_chart.svg"))


def task29_heatmap(df, output_dir: str, grouping_strategy: str = "move_type"):
    """Heatmap: the shared grid as colour, move type across.

    No numbers in the cells, which is what separates it from the matrix
    beside it (shared.draw_value_heatmap: Matrix = annotated grid,
    Heatmap = continuous colour).
    """
    rows, cols, counts = _strategy_grid(df, grouping_strategy)
    if not rows:
        render_empty_state_svg(os.path.join(output_dir, "task29_heatmap.svg"),
                               "Violation Frequency")
        return

    fig_h = max(3.2, 1.1 + len(rows) * 0.55)
    fig, ax = plt.subplots(figsize=(max(5.5, 1.6 + len(cols) * 1.8), fig_h))
    draw_value_heatmap(
        fig, ax, counts,
        row_labels=rows,
        col_labels=cols,
        xlabel="Move Type",
        cbar_label="Number of Violations",
        annotate=False,
        cmap=CIVIDIS_R,
        vmax=max(float(counts.max()), 1.0),
    )
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

def task29_stacked_bar(df, output_dir: str, grouping_strategy: str = "move_type"):
    """Upright stacked bars: one bar per row of the shared grid, split by
    move type.

    It used to lie on its side with the activities down the y axis, which
    read against every other bar chart in the platform, and it took its
    activities from the alignments whatever the admin had chosen.
    """
    out_path = os.path.join(output_dir, "task29_stacked_bar.svg")
    rows, cols, counts = _strategy_grid(df, grouping_strategy)
    if not rows:
        render_empty_state_svg(out_path, "Violation Composition by Move Type")
        return

    order = np.argsort(-counts.sum(axis=1), kind="stable")
    rows = [rows[i] for i in order]
    counts = counts[order]

    x = np.arange(len(rows))
    fig_w = max(6.0, len(rows) * 1.15 + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, 5.4))
    ax.set_facecolor("#fafbfc")

    bottoms = np.zeros(len(rows))
    for ci, vtype in enumerate(cols):
        vals = counts[:, ci]
        ax.bar(x, vals, bottom=bottoms, width=0.6, color=_VTYPE_COLOR[vtype],
               edgecolor="white", linewidth=0.5, label=vtype)
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 0:
                ax.text(xi, b + v / 2, f"{int(v)}", ha="center", va="center",
                        fontsize=FONT_ANNOT - 1,
                        color=contrasting_text_color(_VTYPE_COLOR[vtype]))
        bottoms += vals

    ymax = max(float(bottoms.max()), 1.0)
    for xi, total in enumerate(bottoms):
        if total > 0:
            ax.text(xi, total + ymax * 0.015, f"{int(total)}", ha="center",
                    va="bottom", fontsize=FONT_ANNOT, color=GREY_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels(rows, fontsize=FONT_ANNOT)
    if _rotate_tick_labels(ax, len(rows), rows, FONT_ANNOT):
        ax.tick_params(axis="x", labelrotation=90)
        for lab in ax.get_xticklabels():
            lab.set_ha("center")
            lab.set_va("top")
    ax.set_ylabel("Number of Violations", fontsize=FONT_LABEL)
    ax.set_ylim(0, ymax * 1.16)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_title("Violation Composition by Move Type", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 2: Matrix — activity × violation type annotated grid
# ---------------------------------------------------------------------------

def task29_matrix(df, output_dir: str, grouping_strategy: str = "move_type"):
    """Matrix: the shared grid as numbers on white cells.

    The heatmap is the same grid in colour.
    """
    out_path = os.path.join(output_dir, "task29_matrix.svg")
    rows, cols, counts = _strategy_grid(df, grouping_strategy)
    if not rows:
        render_empty_state_svg(out_path, "Violations by Move Type")
        return

    fig_h = max(3.2, 1.1 + len(rows) * 0.55)
    fig, ax = plt.subplots(figsize=(max(5.5, 1.6 + len(cols) * 1.8), fig_h))
    draw_value_heatmap(
        fig, ax, counts,
        row_labels=rows,
        col_labels=cols,
        xlabel="Move Type",
        cell_fmt="{:.0f}",
        annotate=True,
        rotate_xticks=0,
        colorless=True,
    )
    ax.set_title("Violations by Move Type", fontsize=FONT_TITLE, pad=10)
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
    task29_heatmap(df, output_dir, grouping_strategy)
    task29_pie_chart(df, output_dir)
    task29_table(df, output_dir)
    task29_stacked_bar(df, output_dir, grouping_strategy)
    task29_matrix(df, output_dir, grouping_strategy)
    task29_parallel_sets(alignments, output_dir)
    task29_sunburst(alignments, output_dir)
