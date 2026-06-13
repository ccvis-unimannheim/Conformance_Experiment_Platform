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
          "parallel_sets", "scatter_plot", "box_plot", "heatmap", "calendar"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from matplotlib.colors import LinearSegmentedColormap

from shared import (
    save_svg, make_table, draw_parallel_sets, build_violation_pattern_df,
    alignment_pairs_to_rows, draw_grouped_box_plot, draw_value_heatmap,
    calendar_heatmap, render_empty_state_svg,
    GREY_MED, GREY_LIGHT, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N = 15

_MOVE_COLORS = {"Model Move": GREY_MED, "Log Move": GREY_DARK, "Mismatch Move": GREY_LIGHT}
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
    colors = [_MOVE_COLORS.get(mt, GREY_MED) for mt in top["move_type"]]
    ymax   = max(int(top["count"].max()), 1)

    fig, ax = plt.subplots(figsize=(max(9, len(top) * 1.6), 5.5))
    bars = ax.bar(range(len(top)), top["count"], color=colors,
                  edgecolor="white", width=0.65)
    for bar, val in zip(bars, top["count"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.012,
                f"{int(val)}", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)

    act_labels = [p.split(" (")[0] for p in top["pattern"]]
    ax.set_xticks(range(len(top)))
    ax.set_xticklabels(act_labels, fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Occurrences", fontsize=FONT_LABEL)
    ax.set_title(f"Top-{len(top)} Violation Patterns by Frequency", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.16)
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

    x       = np.arange(len(top_acts))
    bottoms = np.zeros(len(top_acts))

    fig, ax = plt.subplots(figsize=(max(8, len(top_acts) * 0.9), 5.5))
    for mt in present_types:
        vals = pivot[mt].values
        ax.bar(x, vals, bottom=bottoms, color=_MOVE_COLORS[mt],
               edgecolor="white", linewidth=0.5, label=mt)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels(top_acts, rotation=40, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Violation count", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Composition per Activity (top-{len(top_acts)})",
                 fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT,
              title="Move type", title_fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout()
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
    ax.set_title(f"Top-{len(top)} Violation Patterns", fontsize=FONT_TITLE, pad=4)
    fig.tight_layout()
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
    ax_tbl.set_title(f"Top-{len(top)} Violation Patterns", fontsize=FONT_TITLE, pad=4)

    ax_bar = fig.add_subplot(gs[1])
    x      = np.arange(len(top))
    colors = [_MOVE_COLORS.get(mt, GREY_MED) for mt in top["move_type"]]
    ax_bar.barh(x, top["count"], color=colors, edgecolor="white")
    ax_bar.set_yticks(x)
    ax_bar.set_yticklabels(top["pattern"], fontsize=FONT_ANNOT - 1)
    ax_bar.set_xlabel("Occurrences", fontsize=FONT_LABEL)
    ax_bar.legend(
        handles=[mpatches.Patch(color=_MOVE_COLORS[mt], label=mt)
                 for mt in _MOVE_ORDER if mt in set(top["move_type"])],
        frameon=False, fontsize=FONT_ANNOT,
        loc="upper right", bbox_to_anchor=(1.0, -0.12), ncol=3,
        columnspacing=1.4, handletextpad=0.5,
    )
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout()
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

    cmap = LinearSegmentedColormap.from_list("task23_mat", ["#F8F8F8", "#444444"])
    vmax = max(data.max(), 1.0)

    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(present_types) * 2.0), fig_h))
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(present_types)))
    ax.set_xticklabels(present_types, fontsize=FONT_ANNOT)
    ax.set_yticks(range(len(top_acts)))
    ax.set_yticklabels(top_acts, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Move Type", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Count Matrix (top-{len(top_acts)} activities)",
                 fontsize=FONT_TITLE)

    midpoint = vmax * 0.55
    for ri in range(len(top_acts)):
        for ci in range(len(present_types)):
            val = data[ri, ci]
            tc  = "white" if val > midpoint else "#222222"
            ax.text(ci, ri, f"{int(val)}", ha="center", va="center",
                    fontsize=FONT_ANNOT, color=tc)

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Count", fontsize=FONT_ANNOT)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task23_matrix.svg"))


def task23_parallel_sets(pat_df: pd.DataFrame, output_dir: str):
    """Parallel Sets: move type (left) × activity top-N + Other (right)."""
    move_types = [mt for mt in _MOVE_ORDER if mt in pat_df["move_type"].values]
    act_totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts   = act_totals.head(TOP_N).index.tolist()
    has_other  = len(act_totals) > TOP_N
    right_cats = top_acts + (["Other"] if has_other else [])

    matrix = np.zeros((len(move_types), len(right_cats)), dtype=int)
    for mi, mt in enumerate(move_types):
        sub = pat_df[pat_df["move_type"] == mt]
        for ci, act in enumerate(top_acts):
            matrix[mi, ci] = int(sub[sub["activity"] == act]["count"].sum())
        if has_other:
            matrix[mi, -1] = int(sub[~sub["activity"].isin(top_acts)]["count"].sum())

    move_totals  = pat_df.groupby("move_type")["count"].sum()
    left_labels  = [f"{mt}\n(n={int(move_totals.get(mt, 0))})" for mt in move_types]
    left_colors  = [_MOVE_COLORS[mt] for mt in move_types]

    n_cats = len(right_cats)
    greys  = ["#CCCCCC", "#BBBBBB", "#AAAAAA", "#999999", "#888888",
              "#777777", "#666666", "#555555", "#444444", "#333333", "#DDDDDD"]
    right_colors = [greys[i % len(greys)] for i in range(n_cats)]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Move Type vs. Activity", fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_cats,
        matrix=matrix,
        left_colors=left_colors,
        right_colors=right_colors,
        left_title="Move Type",
        right_title="Activity",
    )

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task23_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

def task23_scatter_plot(pat_df: pd.DataFrame, output_dir: str):
    """One dot per pattern: x = #traces affected, y = total occurrences, colour = move-type."""
    colors = [_MOVE_COLORS.get(mt, GREY_MED) for mt in pat_df["move_type"]]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(pat_df["n_traces"], pat_df["count"], c=colors, s=60, alpha=0.8,
               edgecolors="white", linewidths=0.6)
    for _, row in pat_df.head(8).iterrows():
        ax.annotate(row["activity"], (row["n_traces"], row["count"]),
                    textcoords="offset points", xytext=(5, 3),
                    fontsize=FONT_ANNOT - 1, color="#333333")
    ax.set_xlabel("# Traces affected", fontsize=FONT_LABEL)
    ax.set_ylabel("Total occurrences", fontsize=FONT_LABEL)
    ax.set_title("Violation Patterns: Reach vs. Frequency", fontsize=FONT_TITLE)
    _move_legend(ax, set(pat_df["move_type"]))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task23_scatter_plot.svg"))


def _per_trace_pattern_counts(alignments) -> dict:
    """pattern -> list of per-trace occurrence counts among affected traces."""
    from collections import Counter, defaultdict
    out = defaultdict(list)
    for result in alignments:
        c = Counter()
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            if step["moveType"] == "Synchronous Move":
                continue
            activity = (step["model_move"] if step["moveType"] == "Model Move"
                        else step["log_move"])
            if not activity or activity in {"-", "None", "(skip)"}:
                continue
            c[f"{activity} ({step['moveType']})"] += 1
        for pat, n in c.items():
            out[pat].append(n)
    return out


def task23_box_plot(pat_df: pd.DataFrame, alignments, output_dir: str):
    """Per top-N pattern: distribution of per-trace occurrence counts among affected traces."""
    top = pat_df.head(TOP_N)
    per_pat = _per_trace_pattern_counts(alignments)
    labels, data, colors = [], [], []
    for _, row in top.iterrows():
        vals = per_pat.get(row["pattern"], [])
        if not vals:
            continue
        labels.append(row["pattern"])
        data.append(np.array(vals))
        colors.append(_MOVE_COLORS.get(row["move_type"], GREY_MED))
    if not data:
        render_empty_state_svg(os.path.join(output_dir, "task23_box_plot.svg"),
                               "Occurrences per Affected Trace", "No violations found.")
        return
    # Anchor the y-axis at 0 with headroom so boxes are visible even when every
    # affected trace has the same occurrence count (degenerate = flat line at 1).
    all_vals = np.concatenate(data)
    gmax = float(all_vals.max())
    degenerate = float(np.ptp(all_vals)) == 0.0
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.0), 6))
    draw_grouped_box_plot(ax, data, labels, colors,
                          ylabel="Occurrences per affected trace",
                          ylim=(0, max(2.0, gmax * 1.3)))
    ax.tick_params(axis="x", labelrotation=40)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    title = f"Per-trace Occurrence Spread (top-{len(labels)} patterns)"
    if degenerate:
        ax.text(0.5, 0.97,
                f"Every affected trace exhibits each pattern exactly {int(gmax)}× "
                f"— no spread.",
                transform=ax.transAxes, ha="center", va="top",
                fontsize=FONT_ANNOT, color="#888888")
    ax.set_title(title, fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task23_box_plot.svg"))


def task23_heatmap(pat_df: pd.DataFrame, output_dir: str):
    """Activity × move-type, counts, continuous colour (complements the matrix)."""
    act_totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts = act_totals.head(TOP_N).index.tolist()
    present_types = [mt for mt in _MOVE_ORDER if mt in pat_df["move_type"].values]
    data = np.zeros((len(top_acts), len(present_types)))
    for ai, act in enumerate(top_acts):
        for ci, mt in enumerate(present_types):
            mask = (pat_df["activity"] == act) & (pat_df["move_type"] == mt)
            data[ai, ci] = float(pat_df.loc[mask, "count"].sum())
    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(present_types) * 2.0), fig_h))
    draw_value_heatmap(fig, ax, data, top_acts, present_types, xlabel="Move Type",
                       cbar_label="Count", annotate=False)
    ax.set_title(f"Violation Count Heatmap (top-{len(top_acts)} activities)", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task23_heatmap.svg"))


def task23_calendar(alignments, log, output_dir: str):
    """Single calendar: daily total violation count."""
    if log is None:
        render_empty_state_svg(os.path.join(output_dir, "task23_calendar.svg"),
                               "Daily Violation Count", "Event log unavailable for dates.")
        return
    import pandas as _pd
    daily = {}
    for i, result in enumerate(alignments):
        try:
            trace = log[i]
        except Exception:
            continue
        if not trace:
            continue
        ts = trace[0].get("time:timestamp")
        if ts is None:
            continue
        n_viol = sum(1 for s in alignment_pairs_to_rows(result.get("alignment", []))
                     if s["moveType"] != "Synchronous Move")
        if n_viol == 0:
            continue
        d = _pd.Timestamp(ts).normalize()
        daily[d] = daily.get(d, 0) + n_viol
    if not daily:
        render_empty_state_svg(os.path.join(output_dir, "task23_calendar.svg"),
                               "Daily Violation Count", "No timestamped violations.")
        return
    calendar_heatmap(daily, os.path.join(output_dir, "task23_calendar.svg"),
                     title="Daily Total Violation Count",
                     cbar_label="Violations", vmin=0.0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(alignments, output_dir: str, log=None):
    """Generate all Task ID 23 SVGs into output_dir.

    log is optional and only used by the calendar idiom (daily violation count).
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 23 visualizations ---")

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
            ("task23_scatter_plot.svg",        "Violation Patterns: Reach vs. Frequency"),
            ("task23_box_plot.svg",            "Occurrences per Affected Trace"),
            ("task23_heatmap.svg",             "Violation Count Heatmap"),
            ("task23_calendar.svg",            "Daily Violation Count"),
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
    task23_scatter_plot(pat_df, output_dir)
    task23_box_plot(pat_df, alignments, output_dir)
    task23_heatmap(pat_df, output_dir)
    task23_calendar(alignments, log, output_dir)
