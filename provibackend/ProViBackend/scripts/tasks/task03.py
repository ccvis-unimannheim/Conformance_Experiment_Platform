"""
tasks/task03.py – Task ID 3: Describe / Compare / Conformant vs. non-conformant traces.

Every idiom contrasts the SAME attribute — the per-activity presence profile
(% of a group's traces that contain each activity) — between the Conformant
(fitness == 1.0) and Non-conformant (fitness < 1.0) trace groups. Only the
visual encoding differs, so the idioms are comparable on their own quality:
    * bar_chart, table, table_and_bar_chart, matrix – presence rate per activity
    * heatmap        – presence rate per activity (all activities, continuous)
    * scatter_plot   – one point per activity: x = Conformant %, y = Non-conformant %
    * parallel_sets  – group → activity flow (traces exhibiting each activity)
    * box_plot       – distribution of per-activity presence rates per group
    * stacked_bar    – per-group composition of activity presence (share of total)

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table", "table_and_bar_chart", "parallel_sets",
          "stacked_bar", "box_plot", "matrix", "heatmap"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 3 (SEMI): split traces into Conformant / Non-conformant at a threshold
# chosen by the admin, then compare activity presence rates between the groups.
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "conformant_threshold",
        "label": "Conformance threshold (traces with fitness ≥ this value are Conformant)",
        "widget": "threshold",
        "default": 1.0,
        "required": False,
    },
]

ANSWER_FORMATS = [
    {"key": "mc-multi",  "gt_shape": "mc",        "decisive_default": True},
    {"key": "free-text", "gt_shape": "reference",  "decisive_default": False},
]

RUBRIC = (
    "A complete answer identifies at least two specific activities that clearly distinguish "
    "conformant from non-conformant traces and states the direction of the difference "
    "(e.g. 'Activity X appears in 90% of conformant traces but only 40% of non-conformant "
    "traces'). Award full marks for correctly naming the top differentiating activities with "
    "approximate presence rates for both groups. Award partial marks for correctly identifying "
    "the direction without specific rates. Deduct marks for incorrect directions."
)


def validate_params(log, params) -> list:
    """Ensure conformant_threshold is a number in (0, 1]."""
    raw = params.get("conformant_threshold", 1.0)
    try:
        thr = float(raw)
    except (TypeError, ValueError):
        return [f"conformant_threshold must be a number between 0 and 1, got: {raw!r}"]
    if not (0.0 < thr <= 1.0):
        return [f"conformant_threshold must be in (0, 1], got {thr}."]
    return []

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets,
    draw_composition_stacked_bars, draw_grouped_box_plot, draw_value_heatmap,
    render_empty_state_svg,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Top-N most differentiating activities to show in charts/tables
TOP_N = 10

_COLOR_CONFORM     = GREY_MED    # medium-dark grey
_COLOR_NON_CONFORM = GREY_LIGHT  # medium grey
_GROUPS = ["Conformant", "Non-conformant"]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task03_build_trace_rows(log, fitness_df: pd.DataFrame,
                             conformant_threshold: float = 1.0) -> list:
    """Pair each trace with its conformance label and the set of activities it contains.

    Activity presence is the single attribute every Task 3 idiom compares between
    the Conformant and Non-conformant groups, so trace_rows only needs the group
    label and the activity set per trace.
    """
    rows = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        fitness = float(fitness_df.iloc[i]["fitness"])
        group   = "Conformant" if fitness >= conformant_threshold else "Non-conformant"

        activities = {str(event.get("concept:name", "")) for event in trace}
        activities.discard("")

        rows.append({
            "trace_index": i,
            "group":       group,
            "activities":  activities,
        })
    return rows


def _task03_activity_presence_df(trace_rows: list, top_n: int = TOP_N) -> pd.DataFrame:
    """Compute per-activity presence rate (% of group traces containing activity)."""
    all_acts = set()
    for r in trace_rows:
        all_acts.update(r["activities"])

    groups = ["Conformant", "Non-conformant"]
    group_rows = {g: [r for r in trace_rows if r["group"] == g] for g in groups}

    records = []
    for act in all_acts:
        row = {"activity": act}
        for g in groups:
            n = len(group_rows[g])
            row[g] = (sum(1 for r in group_rows[g] if act in r["activities"]) / n * 100) if n else 0.0
        row["difference"] = abs(row["Conformant"] - row["Non-conformant"])
        records.append(row)

    df = pd.DataFrame(records).sort_values("difference", ascending=False).reset_index(drop=True)
    return df.head(top_n)


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task03_bar_chart(presence_df: pd.DataFrame, output_dir: str):
    """Grouped bar: presence rate per activity for Conformant vs Non-conformant."""
    acts   = presence_df["activity"].tolist()
    x      = np.arange(len(acts))
    width  = 0.38

    fig, ax = plt.subplots(figsize=(max(8, len(acts) * 1.1), 5.5))
    bars_c  = ax.bar(x - width / 2, presence_df["Conformant"],     width, color=_COLOR_CONFORM,
                     label="Conformant",     edgecolor="white")
    bars_nc = ax.bar(x + width / 2, presence_df["Non-conformant"], width, color=_COLOR_NON_CONFORM,
                     label="Non-conformant", edgecolor="white")

    for bars in (bars_c, bars_nc):
        for bar in bars:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                        f"{h:.0f}%", ha="center", va="bottom", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels(acts, fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Presence rate (% of traces)", fontsize=FONT_LABEL)
    ax.set_title(f"Top-{len(acts)} Differentiating Activities by Conformance Group",
                 fontsize=FONT_TITLE)
    ax.set_ylim(0, min(115, presence_df[["Conformant", "Non-conformant"]].values.max() * 1.18))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_bar_chart.svg"))


def task03_scatter_plot(trace_rows: list, output_dir: str):
    """Scatter of activity presence: one point per activity, x = presence rate in
    Conformant traces, y = presence rate in Non-conformant traces.

    The y = x diagonal marks 'equally present in both groups'; points far from it
    are the activities whose presence differs most between the groups. The top-N
    differentiators are labelled.
    """
    full = _task03_activity_presence_df(trace_rows, top_n=10**9)
    if full.empty:
        render_empty_state_svg(os.path.join(output_dir, "task03_scatter_plot.svg"),
                               "Activity Presence: Conformant vs. Non-conformant",
                               "No activities found.")
        return

    fig, ax = plt.subplots(figsize=(7.5, 7))
    ax.plot([0, 100], [0, 100], color="#999999", linestyle="--", linewidth=1.0, zorder=1)
    ax.text(99, 99, "equal presence", rotation=45, rotation_mode="anchor",
            ha="right", va="bottom", fontsize=FONT_ANNOT - 1, color="#888888")

    ax.scatter(full["Conformant"], full["Non-conformant"],
               c=GREY_MED, s=36, alpha=0.7, linewidths=0, zorder=3)

    # Label the strongest differentiators; use adjustText to avoid overlaps.
    top = full.head(TOP_N)
    texts = [
        ax.text(row["Conformant"], row["Non-conformant"], row["activity"],
                fontsize=FONT_ANNOT - 2, color="#333333")
        for _, row in top.iterrows()
    ]
    try:
        from adjustText import adjust_text
        adjust_text(
            texts, ax=ax,
            arrowprops=dict(arrowstyle="-", color="#aaaaaa", lw=0.6),
            expand=(2.0, 2.5),
            force_text=(1.0, 1.5),
            force_points=(1.2, 1.8),
            lim=500,
        )
    except Exception:
        pass  # fall back to raw placement if adjustText fails

    ax.set_xlim(-5, 115)
    ax.set_ylim(-5, 115)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Presence rate in Conformant traces (%)", fontsize=FONT_LABEL)
    ax.set_ylabel("Presence rate in Non-conformant traces (%)", fontsize=FONT_LABEL)
    ax.set_title("Activity Presence: Conformant vs. Non-conformant", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_scatter_plot.svg"))


def task03_table(presence_df: pd.DataFrame, output_dir: str):
    """Table: Activity | % Conformant | % Non-conformant | Difference (sorted by |diff|)."""
    cell_text = [
        [
            row["activity"],
            f"{row['Conformant']:.1f}%",
            f"{row['Non-conformant']:.1f}%",
            f"{row['difference']:.1f}pp",
        ]
        for _, row in presence_df.iterrows()
    ]
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Activity", "Conformant (%)", "Non-conformant (%)", "Difference (pp)"],
        bbox=[0.02, 0.05, 0.96, 0.80],
        col_widths=[0.46, 0.18, 0.22, 0.14],
        font_size=10,
        scale_xy=(1, 1.75),
        cell_pad=0.10,
    )
    ax.set_title(f"Top-{len(cell_text)} Differentiating Activities", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_table.svg"))


def task03_table_and_bar_chart(presence_df: pd.DataFrame, output_dir: str):
    """Table (left) + grouped bar chart (right) in one figure."""
    fig = plt.figure(figsize=(15, max(4.5, 1.2 + len(presence_df) * 0.45)))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], wspace=0.35)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text = [
        [row["activity"], f"{row['Conformant']:.1f}%",
         f"{row['Non-conformant']:.1f}%", f"{row['difference']:.1f}pp"]
        for _, row in presence_df.iterrows()
    ]
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Activity", "Conform. (%)", "Non-conf. (%)", "Diff. (pp)"],
        bbox=[0.01, 0.05, 0.98, 0.82],
        col_widths=[0.46, 0.18, 0.22, 0.14],
        font_size=9.5,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )
    ax_tbl.set_title(f"Top-{len(presence_df)} Differentiating Activities",
                     fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    acts  = presence_df["activity"].tolist()
    x     = np.arange(len(acts))
    w     = 0.38
    ax_bar.barh(x - w / 2, presence_df["Conformant"],     w,
                color=_COLOR_CONFORM,     label="Conformant",     edgecolor="white")
    ax_bar.barh(x + w / 2, presence_df["Non-conformant"], w,
                color=_COLOR_NON_CONFORM, label="Non-conformant", edgecolor="white")
    ax_bar.set_yticks(x)
    ax_bar.set_yticklabels(acts, fontsize=FONT_ANNOT - 1)
    ax_bar.set_xlabel("Presence rate (%)", fontsize=FONT_LABEL)
    ax_bar.legend(frameon=False, fontsize=FONT_ANNOT,
                  loc="lower right", bbox_to_anchor=(1.0, -0.18), ncol=2)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_table_and_bar_chart.svg"))


def task03_parallel_sets(trace_rows: list, presence_df: pd.DataFrame, output_dir: str):
    """Parallel Sets: Conformance Group × Activity (top-N differentiators + Other).

    Ribbon width = number of traces in the group that contain the activity, so the
    two group bars contrast which activities each group's traces exhibit. Both axes
    are labelled with count + share of all flow, so the numbers match the ribbons.
    """
    groups   = _GROUPS
    acts     = presence_df["activity"].tolist() if not presence_df.empty else []
    if not acts:
        render_empty_state_svg(os.path.join(output_dir, "task03_parallel_sets.svg"),
                               "Parallel Sets: Conformance Group vs. Activity",
                               "No activities found.")
        return

    top_set  = set(acts)
    cats     = acts + ["Other"]
    matrix   = np.zeros((len(groups), len(cats)), dtype=int)
    for gi, g in enumerate(groups):
        grp = [r for r in trace_rows if r["group"] == g]
        for ci, a in enumerate(acts):
            matrix[gi, ci] = sum(1 for r in grp if a in r["activities"])
        # 'Other' = traces in the group that contain at least one non-top activity.
        matrix[gi, -1] = sum(1 for r in grp if (r["activities"] - top_set))

    if matrix.sum() == 0:
        render_empty_state_svg(os.path.join(output_dir, "task03_parallel_sets.svg"),
                               "Parallel Sets: Conformance Group vs. Activity",
                               "No activity presence to display.")
        return

    total   = int(matrix.sum())
    grp_tot = matrix.sum(axis=1)
    cat_tot = matrix.sum(axis=0)

    def _pct(x: float) -> float:
        return (x / total * 100.0) if total else 0.0

    left_labels  = [f"{g}\n{int(grp_tot[gi])} ({_pct(grp_tot[gi]):.0f}%)"
                    for gi, g in enumerate(groups)]
    right_labels = [f"{c}  —  {int(cat_tot[ci])} ({_pct(cat_tot[ci]):.0f}%)"
                    for ci, c in enumerate(cats)]

    n_cats = len(cats)
    grey_scale = ["#CCCCCC", "#AAAAAA", "#999999", "#888888", "#777777",
                  "#666666", "#555555", "#444444", "#333333", "#222222", "#BBBBBB"]
    right_colors = [grey_scale[i % len(grey_scale)] for i in range(n_cats)]

    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    ax.axis("off")
    ax.set_xlim(-0.16, 1.28)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Conformance Group vs. Activity",
                 fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_labels,
        matrix=matrix,
        left_colors=[_COLOR_CONFORM, _COLOR_NON_CONFORM],
        right_colors=right_colors,
        left_title="Conformance Group",
        right_title="Activity",
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_parallel_sets.svg"))


def task03_stacked_bar(trace_rows: list, output_dir: str):
    """100%-stacked activity-presence composition per conformance group.

    Per group, each segment is one activity's share of the group's TOTAL activity
    presence (presence_rate_activity / Σ presence_rates). Each bar sums to 100%, so
    comparing the two bars reveals how the activity mix differs between Conformant
    and Non-conformant traces. Shows the top-N differentiating activities + 'Other'.
    """
    full = _task03_activity_presence_df(trace_rows, top_n=10**9)
    if full.empty:
        render_empty_state_svg(os.path.join(output_dir, "task03_stacked_bar.svg"),
                               "Activity-Presence Composition per Group", "No activities found.")
        return

    top = full.head(TOP_N)
    seg_labels = top["activity"].tolist() + (["Other"] if len(full) > len(top) else [])

    # rates[segment, group] = activity's share (%) of the group's total presence mass.
    rates = np.zeros((len(seg_labels), len(_GROUPS)))
    for gi, g in enumerate(_GROUPS):
        tot = float(full[g].sum())
        if tot <= 0:
            continue
        for si, (_, row) in enumerate(top.iterrows()):
            rates[si, gi] = row[g] / tot * 100
        if len(seg_labels) > len(top):
            rates[-1, gi] = float(full[g].sum() - top[g].sum()) / tot * 100

    fig, ax = plt.subplots(figsize=(6, 5.5))
    draw_composition_stacked_bars(ax, _GROUPS, seg_labels, rates)
    ax.set_ylabel("% of group's total activity presence", fontsize=FONT_LABEL)
    ax.set_ylim(0, 100)
    ax.set_title("Activity-Presence Composition per Conformance Group", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_stacked_bar.svg"))


def task03_box_plot(trace_rows: list, output_dir: str):
    """Distribution of per-activity presence rates per conformance group.

    One box per group over the presence rates of ALL activities (the same numbers
    the matrix/heatmap show, summarised as a distribution): it contrasts how the
    two groups' activity-presence profiles are spread. Individual activities are
    overlaid as a jittered strip so the distribution stays readable.
    """
    full = _task03_activity_presence_df(trace_rows, top_n=10**9)
    if full.empty:
        render_empty_state_svg(os.path.join(output_dir, "task03_box_plot.svg"),
                               "Activity Presence Rate per Group", "No activities found.")
        return

    data = [full[g].to_numpy(dtype=float) for g in _GROUPS]
    fig, ax = plt.subplots(figsize=(6, 6))
    draw_grouped_box_plot(ax, data, _GROUPS, [_COLOR_CONFORM, _COLOR_NON_CONFORM],
                          ylabel="Activity presence rate (%)", ylim=(0, 100))

    # Overlay one point per activity so the distribution is visible per group.
    rng = np.random.default_rng(42)
    for xi, arr in enumerate(data, start=1):
        if arr.size == 0:
            continue
        jitter = rng.uniform(-0.09, 0.09, arr.size)
        ax.scatter(np.full(arr.size, xi) + jitter, arr,
                   s=14, color="#333333", alpha=0.30, linewidths=0, zorder=4)

    ax.set_title("Activity Presence Rate Distribution per Conformance Group",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_box_plot.svg"))


def task03_matrix(presence_df: pd.DataFrame, output_dir: str):
    """Top-N differentiating activities × group, annotated presence rates."""
    acts = presence_df["activity"].tolist()
    data = presence_df[["Conformant", "Non-conformant"]].values
    fig_h = max(3.0, 0.55 * len(acts) + 1.4)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    draw_value_heatmap(fig, ax, data, acts, _GROUPS, xlabel="Conformance Group",
                       cbar_label="Presence rate (%)", cell_fmt="{:.0f}%", annotate=True)
    ax.set_title("Activity Presence by Group (top differentiators)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_matrix.svg"))


def task03_heatmap(trace_rows: list, output_dir: str):
    """ALL activities × group, presence rate, continuous colour (unannotated)."""
    full = _task03_activity_presence_df(trace_rows, top_n=10**9)
    full = full.sort_values("difference", ascending=False)
    acts = full["activity"].tolist()
    if not acts:
        render_empty_state_svg(os.path.join(output_dir, "task03_heatmap.svg"),
                               "Activity Presence Heatmap", "No activities found.")
        return
    data = full[["Conformant", "Non-conformant"]].values
    fig_h = max(3.5, 0.34 * len(acts) + 1.4)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    draw_value_heatmap(fig, ax, data, acts, _GROUPS, xlabel="Conformance Group",
                       cbar_label="Presence rate (%)", annotate=False)
    ax.set_title("Activity Presence Rate by Group (all activities)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task03_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Top-3 most-differentiating activities as mc-multi options.

    For each activity: one correct statement (dominant group) + one incorrect
    (groups swapped), shuffled deterministically → 6 options, 3 correct.
    """
    threshold = float(params.get("conformant_threshold", 1.0))
    trace_rows = _task03_build_trace_rows(log, fitness_df, conformant_threshold=threshold)
    presence_df = _task03_activity_presence_df(trace_rows, top_n=TOP_N)

    if answer_format == "mc-multi":
        options = []
        for _, row in presence_df.head(3).iterrows():
            act = row["activity"]
            dominant = "Conformant" if row["Conformant"] >= row["Non-conformant"] else "Non-conformant"
            other    = "Non-conformant" if dominant == "Conformant" else "Conformant"
            options.append({
                "label":   f"'{act}' has higher presence in {dominant} traces",
                "value":   f"{act}::{dominant}",
                "correct": True,
            })
            options.append({
                "label":   f"'{act}' has higher presence in {other} traces",
                "value":   f"{act}::{other}",
                "correct": False,
            })
        import random as _rnd
        _rnd.Random(round(threshold * 100)).shuffle(options)
        return {"options": options}

    return {"options": []}


def generate(log, fitness_df, output_dir: str, conformant_threshold: float = 1.0):
    """Generate all Task ID 3 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 3 visualizations ---")

    trace_rows = _task03_build_trace_rows(log, fitness_df,
                                          conformant_threshold=conformant_threshold)
    n_c  = sum(1 for r in trace_rows if r["group"] == "Conformant")
    n_nc = len(trace_rows) - n_c
    logger.info(f"      -> Conformant: {n_c}  |  Non-conformant: {n_nc}"
                f"  (threshold={conformant_threshold})")

    if n_c == 0:
        logger.warning("      No conformant traces — Conformant group is empty.")
    if n_nc == 0:
        logger.warning("      No non-conformant traces — Non-conformant group is empty.")

    presence_df = _task03_activity_presence_df(trace_rows)
    logger.info(f"      -> Top-{len(presence_df)} activities extracted.")

    task03_bar_chart(presence_df, output_dir)
    task03_scatter_plot(trace_rows, output_dir)
    task03_table(presence_df, output_dir)
    task03_table_and_bar_chart(presence_df, output_dir)
    task03_parallel_sets(trace_rows, presence_df, output_dir)

    task03_stacked_bar(trace_rows, output_dir)
    task03_box_plot(trace_rows, output_dir)
    task03_matrix(presence_df, output_dir)
    task03_heatmap(trace_rows, output_dir)
