"""
tasks/task03.py – Task ID 3: Describe / Compare / Conformant vs. non-conformant traces.

Compare behavioural patterns (activity presence, trace length, throughput time) between
Conformant (fitness == 1.0) and Non-conformant (fitness < 1.0) trace groups.

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table", "table_and_bar_chart", "parallel_sets",
          "stacked_bar", "box_plot", "matrix", "heatmap", "gantt_chart", "calendar"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets, build_variant_df,
    draw_composition_stacked_bars, draw_grouped_box_plot, draw_value_heatmap,
    draw_gantt_strips, calendar_heatmap, render_empty_state_svg,
    BLUE, ORANGE, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Top-N most differentiating activities to show in charts/tables
TOP_N = 10

_COLOR_CONFORM     = BLUE    # medium-dark grey
_COLOR_NON_CONFORM = ORANGE  # medium grey
_GROUP_COLORS = {"Conformant": _COLOR_CONFORM, "Non-conformant": _COLOR_NON_CONFORM}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task03_build_trace_rows(log, fitness_df: pd.DataFrame) -> list:
    """Pair each trace with its conformance label + behavioural features."""
    rows = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        fitness = float(fitness_df.iloc[i]["fitness"])
        group   = "Conformant" if fitness >= 1.0 else "Non-conformant"

        activities  = set()
        timestamps  = []
        for event in trace:
            act = str(event.get("concept:name", ""))
            if act:
                activities.add(act)
            ts = event.get("time:timestamp")
            if ts is not None:
                try:
                    timestamps.append(pd.Timestamp(ts))
                except Exception:
                    pass

        throughput_h = None
        if len(timestamps) >= 2:
            throughput_h = (max(timestamps) - min(timestamps)).total_seconds() / 3600

        rows.append({
            "trace_index": i,
            "group":       group,
            "activities":  activities,
            "n_events":    len(trace),
            "throughput_h": throughput_h,
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


def _task03_length_category(n_events: int, q33: float, q67: float) -> str:
    if n_events <= q33:
        return "Short"
    if n_events <= q67:
        return "Medium"
    return "Long"


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
    ax.set_xticklabels(acts, rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Presence rate (% of traces)", fontsize=FONT_LABEL)
    ax.set_title(f"Top-{len(acts)} Differentiating Activities by Conformance Group",
                 fontsize=FONT_TITLE)
    ax.set_ylim(0, min(115, presence_df[["Conformant", "Non-conformant"]].values.max() * 1.18))
    ax.legend(frameon=False, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task03_bar_chart.svg"))


def task03_scatter_plot(trace_rows: list, output_dir: str):
    """Scatter: x = trace length, y = throughput time; colour = conformance group.
    Falls back to strip plot on trace length only when no timestamps are available.
    """
    df = pd.DataFrame(trace_rows)
    has_time = df["throughput_h"].notna().any()

    fig, ax = plt.subplots(figsize=(9, 5))
    for group, color in _GROUP_COLORS.items():
        sub = df[df["group"] == group]
        if sub.empty:
            continue
        y = sub["throughput_h"] if has_time else sub["trace_index"]
        ax.scatter(sub["n_events"], y, c=color, s=14, alpha=0.55,
                   linewidths=0, label=group)

    ax.set_xlabel("Trace length (# events)", fontsize=FONT_LABEL)
    ax.set_ylabel("Throughput time (hours)" if has_time else "Trace index", fontsize=FONT_LABEL)
    ax.set_title("Trace Length vs. Throughput Time by Conformance Group", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
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
    fig.tight_layout()
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

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task03_table_and_bar_chart.svg"))


def task03_parallel_sets(trace_rows: list, output_dir: str):
    """Parallel Sets: Conformance Group × Trace-Length Category (Short/Medium/Long)."""
    df = pd.DataFrame(trace_rows)
    lengths = df["n_events"].values
    q33, q67 = np.percentile(lengths, [33, 67])
    df["len_cat"] = df["n_events"].apply(lambda n: _task03_length_category(n, q33, q67))

    groups  = ["Conformant", "Non-conformant"]
    cats    = ["Short", "Medium", "Long"]
    matrix  = np.zeros((len(groups), len(cats)), dtype=int)
    for gi, g in enumerate(groups):
        for ci, c in enumerate(cats):
            matrix[gi, ci] = int(((df["group"] == g) & (df["len_cat"] == c)).sum())

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Conformance Group vs. Trace-Length Category",
                 fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=[f"Conformant\n(n={int((df['group']=='Conformant').sum())})",
                     f"Non-conformant\n(n={int((df['group']=='Non-conformant').sum())})"],
        right_labels=cats,
        matrix=matrix,
        left_colors=[_COLOR_CONFORM, _COLOR_NON_CONFORM],
        right_colors=["#DDDDDD", "#AAAAAA", "#666666"],
        left_title="Conformance Group",
        right_title="Trace Length",
    )

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task03_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

_GROUPS = ["Conformant", "Non-conformant"]


def _trace_event_times(trace) -> list:
    """Sorted event timestamps (pd.Timestamp) of a PM4Py trace."""
    times = []
    for e in trace:
        ts = e.get("time:timestamp")
        if ts is not None:
            try:
                times.append(pd.Timestamp(ts))
            except Exception:
                pass
    return sorted(times)


def task03_stacked_bar(log, fitness_df, output_dir: str):
    """Per conformance group, composition of top-5 variants + 'Other' (trace counts)."""
    vdf = build_variant_df(log, fitness_df, warn_prefix="task03")
    if vdf.empty:
        render_empty_state_svg(os.path.join(output_dir, "task03_stacked_bar.svg"),
                               "Variant Composition per Group", "No variant data.")
        return
    top = vdf.head(5)
    seg_labels = top["label"].tolist() + (["Other"] if len(vdf) > 5 else [])
    counts = np.zeros((len(seg_labels), len(_GROUPS)))
    for vi, (_, row) in enumerate(top.iterrows()):
        gi = 0 if row["fitness"] >= 1.0 else 1
        counts[vi, gi] = row["count"]
    if len(vdf) > 5:
        for _, row in vdf.iloc[5:].iterrows():
            gi = 0 if row["fitness"] >= 1.0 else 1
            counts[-1, gi] += row["count"]

    greys = ["#444444", "#666666", "#888888", "#AAAAAA", "#CCCCCC", "#DDDDDD"]
    fig, ax = plt.subplots(figsize=(6, 5.5))
    draw_composition_stacked_bars(ax, _GROUPS, seg_labels, counts, segment_colors=greys)
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Top-5 Variant Composition per Conformance Group", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False,
              fontsize=FONT_ANNOT - 1, title="Variant", title_fontsize=FONT_ANNOT)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task03_stacked_bar.svg"))


def task03_box_plot(trace_rows: list, output_dir: str):
    """Throughput-time distribution per conformance group."""
    df = pd.DataFrame(trace_rows)
    has_time = df["throughput_h"].notna().any()
    if not has_time:
        render_empty_state_svg(os.path.join(output_dir, "task03_box_plot.svg"),
                               "Throughput Time per Group", "No timestamp data.")
        return
    data = [df.loc[(df["group"] == g) & df["throughput_h"].notna(), "throughput_h"].values
            for g in _GROUPS]
    fig, ax = plt.subplots(figsize=(5.5, 6))
    draw_grouped_box_plot(ax, data, _GROUPS, [_COLOR_CONFORM, _COLOR_NON_CONFORM],
                          ylabel="Throughput time (hours)", ylim=None)
    ax.set_title("Throughput Time Distribution per Conformance Group", fontsize=FONT_TITLE)
    fig.tight_layout()
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
    fig.tight_layout()
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
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task03_heatmap.svg"))


def task03_gantt_chart(log, fitness_df, output_dir: str):
    """Representative traces (≤3 per group, from the most frequent variants)."""
    vdf = build_variant_df(log, fitness_df, warn_prefix="task03")
    if vdf.empty:
        render_empty_state_svg(os.path.join(output_dir, "task03_gantt_chart.svg"),
                               "Representative Trace Timelines", "No variant data.")
        return
    rows = []
    for g, color in [("Conformant", _COLOR_CONFORM), ("Non-conformant", _COLOR_NON_CONFORM)]:
        sub = vdf[(vdf["fitness"] >= 1.0)] if g == "Conformant" else vdf[vdf["fitness"] < 1.0]
        for _, vrow in sub.head(3).iterrows():
            idx = int(vrow["rep_trace_index"])
            try:
                times = _trace_event_times(log[idx])
            except Exception:
                times = []
            if not times:
                continue
            rows.append({"label": f"{vrow['label']} · {g[:7]} (n={int(vrow['count'])})",
                         "color": color, "times": times})
    if not rows:
        render_empty_state_svg(os.path.join(output_dir, "task03_gantt_chart.svg"),
                               "Representative Trace Timelines", "No timestamped traces.")
        return
    fig, ax = plt.subplots(figsize=(13, max(3, 0.5 * len(rows) + 1.6)))
    draw_gantt_strips(ax, rows)
    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    ax.set_title("Representative Trace Timelines by Conformance Group", fontsize=FONT_TITLE)
    ax.legend(handles=[mpatches.Patch(color=_COLOR_CONFORM, label="Conformant"),
                       mpatches.Patch(color=_COLOR_NON_CONFORM, label="Non-conformant")],
              frameon=False, fontsize=FONT_ANNOT, loc="lower right")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task03_gantt_chart.svg"))


def task03_calendar(log, trace_rows: list, output_dir: str):
    """Single calendar: daily share of non-conformant case starts."""
    group_of = {r["trace_index"]: r["group"] for r in trace_rows}
    accum = {}  # date -> [total, nonconf]
    for idx, g in group_of.items():
        try:
            trace = log[idx]
        except Exception:
            continue
        if not trace:
            continue
        ts = trace[0].get("time:timestamp")
        if ts is None:
            continue
        d = pd.Timestamp(ts).normalize()
        cell = accum.setdefault(d, [0, 0])
        cell[0] += 1
        if g == "Non-conformant":
            cell[1] += 1
    if not accum:
        render_empty_state_svg(os.path.join(output_dir, "task03_calendar.svg"),
                               "Daily Non-conformance Share", "No timestamped case starts.")
        return
    daily = {d: (nc / tot if tot else 0.0) for d, (tot, nc) in accum.items()}
    calendar_heatmap(daily, os.path.join(output_dir, "task03_calendar.svg"),
                     title="Daily Share of Non-conformant Case Starts",
                     cbar_label="Share non-conformant", vmin=0.0, vmax=1.0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str):
    """Generate all Task ID 3 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 3 visualizations ---")

    trace_rows = _task03_build_trace_rows(log, fitness_df)
    n_c  = sum(1 for r in trace_rows if r["group"] == "Conformant")
    n_nc = len(trace_rows) - n_c
    logger.info(f"      -> Conformant: {n_c}  |  Non-conformant: {n_nc}")

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
    task03_parallel_sets(trace_rows, output_dir)

    task03_stacked_bar(log, fitness_df, output_dir)
    task03_box_plot(trace_rows, output_dir)
    task03_matrix(presence_df, output_dir)
    task03_heatmap(trace_rows, output_dir)
    task03_gantt_chart(log, fitness_df, output_dir)
    task03_calendar(log, trace_rows, output_dir)
