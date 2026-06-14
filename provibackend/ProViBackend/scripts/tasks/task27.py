"""
tasks/task27.py – Task ID 27: Explore / Identify / Conformant and non-conformant traces.

Identify WHICH variants/traces are conformant and which are not, and how they
differ. Unit = control-flow variant (shared.build_variant_df, reused from
task04); Conformant = fitness == 1.0. Encodings are status-centric
(frequency × status), unlike task04 (degree-centric) and task03 (behavioural
group comparison). Reuses the centrally computed alignments — nothing re-run.

Public API:
    generate(log, fitness_df, alignments, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        alignments – raw alignment results from io_helpers.run_alignments
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table", "table_bar_chart",
          "parallel_sets", "matrix", "flow_chart_table",
          "stacked_bar", "box_plot", "heatmap", "gantt_chart", "calendar",
          "flow_chart_elaborate_table"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from matplotlib.colors import ListedColormap

from shared import (
    save_svg, make_table, draw_parallel_sets, alignment_pairs_to_rows,
    build_variant_df, variant_table_data,
    chevron_figure_width, chevron_nodes_from_alignment_rows, draw_chevron_strip,
    draw_composition_stacked_bars, draw_grouped_box_plot, draw_value_heatmap,
    draw_gantt_strips, calendar_heatmap, render_empty_state_svg,
    parse_bpmn_model, compose_bpmn_panels, contrasting_text_color,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N = 15
# Number of conformant / non-conformant variants shown as chevron strips
STRIPS_PER_STATUS = 3

# Two-colour status palette, consistent with task03/task04
_COLOR_CONFORM     = GREY_MED
_COLOR_NON_CONFORM = GREY_LIGHT
_STATUS_COLORS = {"Conformant": _COLOR_CONFORM, "Non-conformant": _COLOR_NON_CONFORM}


def _status(fitness: float) -> str:
    return "Conformant" if fitness >= 1.0 else "Non-conformant"


def _status_legend_handles():
    return [
        mpatches.Patch(color=_COLOR_CONFORM,     label="Conformant (fitness = 1.0)"),
        mpatches.Patch(color=_COLOR_NON_CONFORM, label="Non-conformant (fitness < 1.0)"),
    ]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task27_bar_chart(vdf: pd.DataFrame, output_dir: str):
    """Bar chart: top-N variants by frequency; height = #traces, colour = status."""
    top = vdf.head(TOP_N)
    colors = [_STATUS_COLORS[_status(f)] for f in top["fitness"]]
    ymax = max(int(top["count"].max()), 1)

    fig, ax = plt.subplots(figsize=(max(7, len(top) * 0.75), 5))
    bars = ax.bar(top["label"], top["count"], color=colors, edgecolor="white", width=0.65)
    for bar, val in zip(bars, top["count"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.012,
                f"{int(val)}", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)

    ax.legend(handles=_status_legend_handles(), frameon=False, fontsize=FONT_ANNOT,
              loc="lower right", bbox_to_anchor=(1.0, -0.18), ncol=2)
    ax.set_xlabel(f"Variant (ranked by frequency, top {len(top)} of {len(vdf)})",
                  fontsize=FONT_LABEL)
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Variant Frequency by Conformance Status", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_bar_chart.svg"))


def task27_scatter_plot(fitness_df: pd.DataFrame, output_dir: str):
    """Scatter: one dot per trace, x = chronological index, y = fitness, colour = status."""
    fig, ax = plt.subplots(figsize=(10, 4))
    for status, color in _STATUS_COLORS.items():
        mask = fitness_df["fitness"].apply(_status) == status
        sub = fitness_df[mask]
        if sub.empty:
            continue
        ax.scatter(sub["trace_index"], sub["fitness"], c=color, s=15,
                   alpha=0.6, linewidths=0, label=status)
    ax.set_xlabel("Traces in Log ordered by time", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Conformance Status per Trace", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_scatter_plot.svg"))


def task27_table(vdf: pd.DataFrame, output_dir: str):
    """Table: Rank | #Traces | Coverage % | Fitness | Status for top-N variants."""
    cell_text, col_labels, col_widths = variant_table_data(
        vdf, TOP_N, include_status=True, rank_header="Rank",
    )
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.92],
        col_widths=col_widths,
        font_size=10.5,
        scale_xy=(1, 1.75),
        cell_pad=0.11,
    )
    ax.set_title(
        f"Conformance Status of the Top-{len(cell_text)} Variants (of {len(vdf)} total)",
        fontsize=FONT_TITLE, pad=3,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_table.svg"))


def task27_table_and_bar_chart(vdf: pd.DataFrame, output_dir: str):
    """Composite: status table (left) + status-coloured frequency bars (right)."""
    top = vdf.head(TOP_N)
    cell_text, col_labels, col_widths = variant_table_data(
        vdf, TOP_N, include_status=True, rank_header="Rank",
    )

    fig = plt.figure(figsize=(15, max(4.5, 1.2 + len(top) * 0.45)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.30)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.01, 0.05, 0.98, 0.88],
        col_widths=col_widths,
        font_size=9.5,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )
    ax_tbl.set_title(f"Top-{len(top)} Variants by Frequency", fontsize=FONT_TITLE, pad=4)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(top))
    colors = [_STATUS_COLORS[_status(f)] for f in top["fitness"]]
    ax_bar.barh(y, top["count"], color=colors, edgecolor="white")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(top["label"], fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    xmax = max(int(top["count"].max()), 1)
    for yi, val in zip(y, top["count"]):
        ax_bar.text(val + xmax * 0.015, yi, f"{int(val)}", va="center",
                    fontsize=FONT_ANNOT - 1)
    ax_bar.set_xlabel("Number of Traces", fontsize=FONT_LABEL)
    ax_bar.legend(handles=_status_legend_handles(), frameon=False,
                  fontsize=FONT_ANNOT - 1,
                  loc="lower right", bbox_to_anchor=(1.0, -0.20), ncol=1)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_table_and_bar_chart.svg"))


def _frequency_bucket(count: int, q33: float, q67: float) -> str:
    if count > q67:
        return "Frequent"
    if count > q33:
        return "Mid"
    return "Rare"


def task27_parallel_sets(vdf: pd.DataFrame, output_dir: str):
    """Parallel Sets: variant-frequency bucket × conformance status; ribbon = #traces.

    (Deliberately different dimensions from task03's parallel sets.)
    """
    counts = vdf["count"].values.astype(float)
    q33, q67 = np.percentile(counts, [33, 67])

    buckets  = ["Frequent", "Mid", "Rare"]
    statuses = ["Conformant", "Non-conformant"]
    matrix = np.zeros((len(buckets), len(statuses)), dtype=int)
    for _, row in vdf.iterrows():
        bi = buckets.index(_frequency_bucket(int(row["count"]), q33, q67))
        si = statuses.index(_status(row["fitness"]))
        matrix[bi, si] += int(row["count"])   # ribbon width = #traces

    bucket_totals = matrix.sum(axis=1)
    left_labels = [f"{b}\n(n={int(t)})" for b, t in zip(buckets, bucket_totals)]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Variant-Frequency Bucket vs. Conformance Status",
                 fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=statuses,
        matrix=matrix,
        left_colors=["#555555", "#999999", "#CCCCCC"],
        right_colors=[_COLOR_CONFORM, _COLOR_NON_CONFORM],
        left_title="Variant Frequency",
        right_title="Status",
    )

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Matrix: variant × activity relation (the "how do they differ" view)
# ---------------------------------------------------------------------------

# Cell categories (code order = drawing precedence; higher code wins per cell)
_REL_ABSENT, _REL_CONFORM, _REL_UNEXPECTED, _REL_SKIPPED = 0, 1, 2, 3
_REL_COLORS = ["#FFFFFF", GREY_LIGHTER, GREY_DARK, GREY_MED]
_REL_LABELS = ["Absent", "Contained (conform)", "Unexpected (log move)",
               "Skipped (model move)"]


def _activity_order(alignments) -> list:
    """Activities ordered by their average alignment step position (≈ model order)."""
    positions = {}
    for result in alignments:
        for row in alignment_pairs_to_rows(result.get("alignment", [])):
            for side in ("model_move", "log_move"):
                act = str(row[side])
                if act in {"-", "None", "(skip)", ""}:
                    continue
                positions.setdefault(act, []).append(row["step"])
    return sorted(positions, key=lambda a: sum(positions[a]) / len(positions[a]))


def _variant_relations(rep_rows) -> dict:
    """Map activity -> relation code for one variant's alignment rows."""
    rel = {}

    def bump(act, code):
        act = str(act)
        if act in {"-", "None", "(skip)", ""}:
            return
        rel[act] = max(rel.get(act, _REL_ABSENT), code)

    for row in rep_rows:
        mt = row["moveType"]
        if mt == "Synchronous Move":
            bump(row["log_move"], _REL_CONFORM)
        elif mt == "Model Move":
            bump(row["model_move"], _REL_SKIPPED)
        elif mt == "Log Move":
            bump(row["log_move"], _REL_UNEXPECTED)
        else:  # Mismatch: model side skipped, log side unexpected
            bump(row["model_move"], _REL_SKIPPED)
            bump(row["log_move"], _REL_UNEXPECTED)
    return rel


def task27_matrix(vdf: pd.DataFrame, alignments, output_dir: str):
    """Matrix: rows = top-N variants, columns = activities; cell = variant's relation."""
    top = vdf.head(TOP_N)
    activities = _activity_order(alignments)
    if not activities:
        logger.warning("      task27: no activities found for the matrix.")
        return

    data = np.full((len(top), len(activities)), _REL_ABSENT, dtype=int)
    row_labels = []
    for vi, (_, row) in enumerate(top.iterrows()):
        rep_rows = alignment_pairs_to_rows(
            alignments[int(row["rep_trace_index"])].get("alignment", []))
        rel = _variant_relations(rep_rows)
        for ci, act in enumerate(activities):
            data[vi, ci] = rel.get(act, _REL_ABSENT)
        mark = "✓" if _status(row["fitness"]) == "Conformant" else "✗"
        row_labels.append(f"{row['label']} {mark} (n={int(row['count'])})")

    fig_h = max(3.8, 0.5 * len(top) + 2.2)
    fig_w = max(8.0, 0.85 * len(activities) + 3.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.imshow(data, cmap=ListedColormap(_REL_COLORS), vmin=0, vmax=3, aspect="auto")

    # cell grid for readability
    ax.set_xticks(np.arange(-0.5, len(activities)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(top)), minor=True)
    ax.grid(which="minor", color="#DDDDDD", linewidth=0.8)
    ax.tick_params(which="minor", length=0)

    ax.set_xticks(range(len(activities)))
    ax.set_xticklabels(activities, rotation=40, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(row_labels, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Activity (model order)", fontsize=FONT_LABEL)
    ax.set_title(f"Variant × Activity Relation (top-{len(top)} variants)",
                 fontsize=FONT_TITLE)
    ax.legend(
        handles=[mpatches.Patch(facecolor=c, edgecolor="#AAAAAA", label=l)
                 for c, l in zip(_REL_COLORS, _REL_LABELS)],
        loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=4,
        frameon=False, fontsize=FONT_ANNOT - 1,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_matrix.svg"))


# ---------------------------------------------------------------------------
# Flow Chart & Table: chevron strips per variant + compact variant table
# ---------------------------------------------------------------------------

def _chevron_move_legend_handles():
    return [
        mpatches.Patch(facecolor=GREY_LIGHTER,  edgecolor="black", linewidth=0.75,
                       label="Synchronous move (Conform)"),
        mpatches.Patch(facecolor=GREY_MED,   edgecolor="black", linewidth=0.75,
                       label="Model move only"),
        mpatches.Patch(facecolor=GREY_DARK,    edgecolor="black", linewidth=0.75,
                       label="Log move only"),
        mpatches.Patch(facecolor=GREY_LIGHT, edgecolor="black", linewidth=0.75,
                       label="Mismatch move"),
    ]


def task27_flow_chart_and_table(vdf: pd.DataFrame, alignments, output_dir: str):
    """Small multiples of chevron strips (top conformant + top non-conformant
    variants) with a compact variant table beneath."""
    conform_v = vdf[vdf["fitness"] >= 1.0].head(STRIPS_PER_STATUS)
    nonconf_v = vdf[vdf["fitness"] < 1.0].head(STRIPS_PER_STATUS)
    shown = pd.concat([conform_v, nonconf_v])
    if shown.empty:
        logger.warning("      task27: no variants to draw chevron strips for.")
        return

    strips = []
    for _, row in shown.iterrows():
        rep_rows = alignment_pairs_to_rows(
            alignments[int(row["rep_trace_index"])].get("alignment", []))
        nodes = chevron_nodes_from_alignment_rows(rep_rows)
        status = _status(row["fitness"])
        title = (f"{row['label']}  —  {int(row['count'])} traces "
                 f"({row['coverage']:.1f}%)  —  {status}")
        strips.append({"nodes": nodes, "title": title})

    cell_text, col_labels, col_widths = variant_table_data(
        shown.reset_index(drop=True), len(shown),
        include_status=True, rank_header="Rank",
    )

    fig_w = max(chevron_figure_width(s["nodes"]) for s in strips)
    strip_h = 1.55
    table_h = max(1.8, 0.85 + len(cell_text) * 0.42)
    fig_h = len(strips) * strip_h + table_h + 1.6

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(
        len(strips) + 1, 1,
        height_ratios=[strip_h] * len(strips) + [table_h],
        hspace=0.85,
    )

    for i, strip in enumerate(strips):
        ax = fig.add_subplot(gs[i])
        draw_chevron_strip(ax, strip["nodes"], fontsize=10)
        ax.set_title(strip["title"], fontsize=FONT_ANNOT + 1, loc="left", pad=5)

    ax_tbl = fig.add_subplot(gs[-1])
    ax_tbl.axis("off")
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.10, 0.06, 0.80, 0.86],
        col_widths=col_widths,
        font_size=9.5,
        scale_xy=(1, 1.5),
        cell_pad=0.09,
    )
    ax_tbl.set_title("Shown Variants", fontsize=FONT_TITLE, pad=6)

    fig.suptitle(
        f"Top Conformant ({len(conform_v)}) and Non-conformant ({len(nonconf_v)}) "
        f"Variants — Trace Alignment", fontsize=FONT_TITLE, y=0.995,
    )
    fig.legend(
        handles=_chevron_move_legend_handles(),
        loc="lower center", bbox_to_anchor=(0.5, 0.005),
        ncol=4, fontsize=FONT_ANNOT, frameon=True, fancybox=False,
        edgecolor="#cccccc",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.97])
    save_svg(fig, os.path.join(output_dir, "task27_flow_chart_and_table.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

def _task27_trace_df(log, fitness_df: pd.DataFrame) -> pd.DataFrame:
    """Per-trace length, fitness, status, start_time, throughput (timestamped only)."""
    rows = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        fit = float(fitness_df.iloc[i]["fitness"])
        times = []
        for e in trace:
            ts = e.get("time:timestamp")
            if ts is not None:
                try:
                    times.append(pd.Timestamp(ts))
                except Exception:
                    pass
        times.sort()
        throughput = ((times[-1] - times[0]).total_seconds() / 3600
                      if len(times) >= 2 else None)
        rows.append({
            "trace_index": i, "length": len(trace), "fitness": fit,
            "status": _status(fit),
            "start_time": times[0] if times else pd.NaT,
            "throughput_h": throughput,
        })
    return pd.DataFrame(rows)


def task27_stacked_bar(tdf: pd.DataFrame, output_dir: str):
    """Trace-length bucket × conformance-status composition (trace counts)."""
    lengths = tdf["length"].values.astype(float)
    q33, q67 = np.percentile(lengths, [33, 67])
    def bucket(n):
        return "Short" if n <= q33 else ("Medium" if n <= q67 else "Long")
    tdf = tdf.assign(bucket=[bucket(n) for n in tdf["length"]])

    buckets = ["Short", "Medium", "Long"]
    statuses = ["Conformant", "Non-conformant"]
    counts = np.zeros((len(statuses), len(buckets)))
    for si, s in enumerate(statuses):
        for bi, b in enumerate(buckets):
            counts[si, bi] = int(((tdf["status"] == s) & (tdf["bucket"] == b)).sum())

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    draw_composition_stacked_bars(ax, buckets, statuses, counts,
                                  segment_colors=[_COLOR_CONFORM, _COLOR_NON_CONFORM])
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Conformance Status by Trace-Length Bucket", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=False, fontsize=FONT_ANNOT, title="Status",
              title_fontsize=FONT_ANNOT)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_stacked_bar.svg"))


def task27_box_plot(tdf: pd.DataFrame, output_dir: str):
    """Throughput-time distribution per conformance-status group."""
    if tdf["throughput_h"].notna().sum() == 0:
        render_empty_state_svg(os.path.join(output_dir, "task27_box_plot.svg"),
                               "Throughput Time per Status", "No timestamp data.")
        return
    statuses = ["Conformant", "Non-conformant"]
    data = [tdf.loc[(tdf["status"] == s) & tdf["throughput_h"].notna(), "throughput_h"].values
            for s in statuses]
    fig, ax = plt.subplots(figsize=(5.5, 6))
    draw_grouped_box_plot(ax, data, statuses, [_COLOR_CONFORM, _COLOR_NON_CONFORM],
                          ylabel="Throughput time (hours)", ylim=None)
    ax.set_title("Throughput Time by Conformance Status", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_box_plot.svg"))


def task27_heatmap(vdf: pd.DataFrame, alignments, output_dir: str):
    """Top-N variants × activities, occurrence count within the variant (continuous)."""
    top = vdf.head(TOP_N)
    activities = _activity_order(alignments)
    if not activities:
        render_empty_state_svg(os.path.join(output_dir, "task27_heatmap.svg"),
                               "Variant × Activity Presence", "No activities found.")
        return
    data = np.zeros((len(top), len(activities)))
    labels = []
    for vi, (_, row) in enumerate(top.iterrows()):
        seq = list(row["variant"])
        for ci, act in enumerate(activities):
            data[vi, ci] = seq.count(act)
        mark = "✓" if _status(row["fitness"]) == "Conformant" else "✗"
        labels.append(f"{row['label']} {mark}")
    fig_h = max(3.8, 0.5 * len(top) + 2.0)
    fig_w = max(8.0, 0.7 * len(activities) + 3.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_value_heatmap(fig, ax, data, labels, activities, xlabel="Activity (model order)",
                       cbar_label="Occurrences in variant", annotate=False, rotate_xticks=40)
    ax.set_title(f"Activity Presence Across Variants (top-{len(top)})", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_heatmap.svg"))


def task27_gantt_chart(vdf: pd.DataFrame, log, output_dir: str):
    """Representative traces per status (≤3 + ≤3) as event-span strips."""
    rows = []
    for status, color, sub in [
        ("Conformant", _COLOR_CONFORM, vdf[vdf["fitness"] >= 1.0]),
        ("Non-conformant", _COLOR_NON_CONFORM, vdf[vdf["fitness"] < 1.0]),
    ]:
        for _, vrow in sub.head(3).iterrows():
            idx = int(vrow["rep_trace_index"])
            try:
                trace = log[idx]
            except Exception:
                continue
            times = sorted(pd.Timestamp(e.get("time:timestamp")) for e in trace
                           if e.get("time:timestamp") is not None)
            if not times:
                continue
            rows.append({"label": f"{vrow['label']} · {status[:7]} (n={int(vrow['count'])})",
                         "color": color, "times": times})
    if not rows:
        render_empty_state_svg(os.path.join(output_dir, "task27_gantt_chart.svg"),
                               "Representative Trace Timelines", "No timestamped traces.")
        return
    fig, ax = plt.subplots(figsize=(13, max(3, 0.5 * len(rows) + 1.6)))
    draw_gantt_strips(ax, rows)
    ax.set_xlabel("Time", fontsize=FONT_LABEL)
    ax.set_title("Representative Trace Timelines by Conformance Status", fontsize=FONT_TITLE)
    ax.legend(handles=_status_legend_handles(), frameon=False, fontsize=FONT_ANNOT,
              loc="lower right")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task27_gantt_chart.svg"))


def task27_calendar(tdf: pd.DataFrame, output_dir: str):
    """Single calendar: daily count of non-conformant case starts."""
    sub = tdf[(tdf["status"] == "Non-conformant") & tdf["start_time"].notna()]
    if sub.empty:
        render_empty_state_svg(os.path.join(output_dir, "task27_calendar.svg"),
                               "Daily Non-conformant Case Starts",
                               "No non-conformant timestamped traces.")
        return
    daily = sub.groupby(sub["start_time"].dt.normalize()).size()
    calendar_heatmap({d: int(v) for d, v in daily.items()},
                     os.path.join(output_dir, "task27_calendar.svg"),
                     title="Daily Count of Non-conformant Case Starts",
                     cbar_label="Non-conformant case starts", vmin=0.0)


def _task27_exemplar_style(rep_rows):
    """node_style_fn marking a single trace's deviating / conform activities."""
    skipped, mismatch, conform = set(), set(), set()
    for row in rep_rows:
        mt = row["moveType"]
        if mt == "Synchronous Move":
            conform.add(str(row["log_move"]) if str(row["log_move"]) not in {"-", "None"}
                        else str(row["model_move"]))
        elif mt == "Model Move":
            skipped.add(str(row["model_move"]))
        elif mt == "Mismatch Move":
            mismatch.add(str(row["model_move"]))

    def _style(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task":
            if name in skipped:
                return (GREY_MED, "#444444", 3, contrasting_text_color(GREY_MED))
            if name in mismatch:
                return (GREY_LIGHT, "#444444", 3, contrasting_text_color(GREY_LIGHT))
            if name in conform:
                return (GREY_LIGHTER, "#666666", 2, contrasting_text_color(GREY_LIGHTER))
        return ("white", "#888888", 2, "#333333")
    return _style


def task27_flow_chart_elaborate_table(vdf, alignments, model_path, output_dir):
    """Two elaborate BPMN panels (conformant + non-conformant exemplar) + comparison table.

    A variant exemplar = its representative trace; deviating activities are marked
    on the desired model (reuses the shared BPMN renderer / task28's geometry).
    """
    conf = vdf[vdf["fitness"] >= 1.0].head(1)
    nonc = vdf[vdf["fitness"] < 1.0].head(1)
    if conf.empty or nonc.empty:
        render_empty_state_svg(
            os.path.join(output_dir, "task27_flow_chart_elaborate_table.svg"),
            "Conformant vs. Non-conformant Exemplars",
            "Need both a conformant and a non-conformant variant.")
        return

    parsed = parse_bpmn_model(model_path)
    panels, exemplars = [], []
    for vrow, status in [(conf.iloc[0], "Conformant"), (nonc.iloc[0], "Non-conformant")]:
        rep_rows = alignment_pairs_to_rows(
            alignments[int(vrow["rep_trace_index"])].get("alignment", []))
        n_dev = sum(1 for r in rep_rows if r["moveType"] != "Synchronous Move")
        panels.append({
            "parsed": parsed,
            "node_style_fn": _task27_exemplar_style(rep_rows),
            "subtitle": f"{status} exemplar — {vrow['label']} "
                        f"(n={int(vrow['count'])}, {vrow['coverage']:.1f}%, "
                        f"fitness={vrow['fitness']:.3f})",
        })
        exemplars.append((vrow, n_dev))

    (cv, cdev), (nv, ndev) = exemplars
    table_rows = [
        ["Variant rank", cv["label"], nv["label"]],
        ["#Traces", str(int(cv["count"])), str(int(nv["count"]))],
        ["Coverage %", f"{cv['coverage']:.1f}%", f"{nv['coverage']:.1f}%"],
        ["Fitness", f"{cv['fitness']:.3f}", f"{nv['fitness']:.3f}"],
        ["#Deviations (exemplar)", str(cdev), str(ndev)],
    ]
    compose_bpmn_panels(
        panels,
        os.path.join(output_dir, "task27_flow_chart_elaborate_table.svg"),
        title="Conformant vs. Non-conformant Variant Exemplars on the Model",
        legend_items=[
            (GREY_LIGHTER,  "#666666", 2, "Conform (synchronous)"),
            (GREY_MED,   "#444444", 3, "Model move (skipped)"),
            (GREY_LIGHT, "#444444", 3, "Mismatch move"),
            ("white", "#888888", 2, "Not on this trace"),
        ],
        table_rows=table_rows,
        table_cols=["Metric", "Conformant", "Non-conformant"],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, alignments, output_dir: str, model_path: str = None):
    """Generate all Task ID 27 SVGs into output_dir.

    model_path is required for the flow_chart_elaborate_table idiom (two annotated
    BPMN exemplar panels); when absent that idiom is skipped.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 27 visualizations ---")

    if fitness_df is None or fitness_df.empty:
        logger.warning("      Skipped Task 27: empty fitness DataFrame.")
        return

    vdf = build_variant_df(log, fitness_df, warn_prefix="task27")
    if vdf.empty:
        logger.warning("      Skipped Task 27: no trace data available.")
        return

    n_conform = int((vdf["fitness"] >= 1.0).sum())
    n_nonconf = len(vdf) - n_conform
    logger.info(f"      -> {len(vdf)} variants "
                f"({n_conform} conformant, {n_nonconf} non-conformant); "
                f"showing top-{min(TOP_N, len(vdf))}.")
    if n_conform == 0:
        logger.warning("      task27: no conformant variants — "
                       "status encodings degrade to one group.")
    if n_nonconf == 0:
        logger.warning("      task27: all variants conformant — "
                       "status encodings degrade to one group.")

    task27_bar_chart(vdf, output_dir)
    task27_scatter_plot(fitness_df, output_dir)
    task27_table(vdf, output_dir)
    task27_table_and_bar_chart(vdf, output_dir)
    task27_parallel_sets(vdf, output_dir)
    task27_matrix(vdf, alignments, output_dir)
    task27_flow_chart_and_table(vdf, alignments, output_dir)

    tdf = _task27_trace_df(log, fitness_df)
    task27_stacked_bar(tdf, output_dir)
    task27_box_plot(tdf, output_dir)
    task27_heatmap(vdf, alignments, output_dir)
    task27_gantt_chart(vdf, log, output_dir)
    task27_calendar(tdf, output_dir)
    if model_path:
        try:
            task27_flow_chart_elaborate_table(vdf, alignments, model_path, output_dir)
        except Exception as e:
            logger.warning(f"      task27: flow_chart_elaborate_table skipped ({e}).")
    else:
        logger.warning("      task27: no model_path — flow_chart_elaborate_table skipped.")
