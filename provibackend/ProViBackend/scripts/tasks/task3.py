"""
tasks/task3.py – Task 3: Violation type summaries across all traces.

Public API:
    generate(alignments, output_dir)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "heatmap", "pie_chart", "flow_chart_table", "table", "table_bar_chart"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon
from matplotlib import gridspec

from shared import save_svg, make_table, alignment_pairs_to_rows, BLUE, ORANGE, GREEN, RED


# ---------------------------------------------------------------------------
# Chevron helpers (same visual style as task2)
# ---------------------------------------------------------------------------
_CHEVRON_HEIGHT     = 1.65
_CHEVRON_DEPTH      = 0.92
_CHEVRON_GAP        = 0.82
_CHEVRON_MIN_WIDTH  = 6.15
_CHEVRON_CHAR_WIDTH = 0.42


def _chevron_layout(nodes):
    widths = []
    for node in nodes:
        longest = max(len(line) for line in str(node["label"]).splitlines())
        content_w = _CHEVRON_DEPTH * 2.0 + 2.65 + longest * _CHEVRON_CHAR_WIDTH
        widths.append(max(_CHEVRON_MIN_WIDTH, content_w))
    x_cursor = 0.0
    layout = []
    for width in widths:
        layout.append({"x": x_cursor, "width": width})
        x_cursor += width + _CHEVRON_GAP
    span = max(0.0, x_cursor - _CHEVRON_GAP)
    return layout, span


def _chevron_font_size(label, width, base_fontsize):
    longest = max(len(line) for line in str(label).splitlines())
    available = max(width - _CHEVRON_DEPTH * 2.0 - 1.2, 1.0)
    estimated = longest * 0.34
    if estimated <= available:
        return base_fontsize
    return max(8.5, base_fontsize * available / estimated)


def _draw_chevrons(ax, nodes, fontsize=11):
    ax.set_aspect("auto")
    ax.axis("off")
    h = _CHEVRON_HEIGHT
    layout, span = _chevron_layout(nodes)
    for i, node in enumerate(nodes):
        base_x = layout[i]["x"]
        width  = layout[i]["width"]
        mid_y  = h / 2.0
        verts = [
            (base_x,                     0.0),
            (base_x + _CHEVRON_DEPTH,    mid_y),
            (base_x,                     h),
            (base_x + width - _CHEVRON_DEPTH, h),
            (base_x + width,             mid_y),
            (base_x + width - _CHEVRON_DEPTH, 0.0),
        ]
        ax.add_patch(Polygon(
            verts, closed=True,
            facecolor=node["color"], edgecolor="#4a4a4a",
            linewidth=1.25, joinstyle="miter",
        ))
        ax.text(
            base_x + width / 2.0, mid_y,
            node["label"],
            ha="center", va="center",
            fontsize=_chevron_font_size(node["label"], width, fontsize),
            fontweight="bold", color="#1f1f1f", clip_on=False,
        )
    ax.set_xlim(-0.45, span + 0.45)
    ax.set_ylim(-0.08, h + 0.08)
    return span


# ---------------------------------------------------------------------------
# Task 3 – Violation type summaries across all traces
# ---------------------------------------------------------------------------

# Task 3 helpers
TASK3_TYPE_LABELS = {
    "Model Move": "Model Move\n(Missing in Log)",
    "Log Move": "Log Move\n(Unexpected in Log)",
    "Mismatch Move": "Mismatch Move\n(Log/Model differ)",
}


def task3_violation_summary_dataframe(alignments):
    """Count violation move types across all trace alignments."""
    rows = []
    for trace_idx, result in enumerate(alignments):
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            move_type = step["moveType"]
            if move_type == "Synchronous Move":
                continue
            rows.append({
                "trace_index": trace_idx,
                "move_type": move_type,
                "violation_type": TASK3_TYPE_LABELS.get(move_type, move_type),
                "activity": step["model_move"] if move_type == "Model Move" else step["log_move"],
            })

    if rows:
        raw = pd.DataFrame(rows)
        summary = (
            raw.groupby(["move_type", "violation_type"], as_index=False)
            .agg(count=("move_type", "size"), traces=("trace_index", "nunique"))
        )
    else:
        summary = pd.DataFrame(columns=["move_type", "violation_type", "count", "traces"])

    order = ["Model Move", "Log Move", "Mismatch Move"]
    summary["order"] = summary["move_type"].apply(lambda x: order.index(x) if x in order else len(order))
    summary = summary.sort_values(["order", "violation_type"]).drop(columns=["order"]).reset_index(drop=True)
    total = int(summary["count"].sum()) if not summary.empty else 0
    summary["percentage"] = (summary["count"] / total * 100) if total else 0.0
    logger.info(f"      -> Violation moves: {total}")
    return summary


# Task 3 visualizations
def task3_bar_chart(df: pd.DataFrame, output_dir: str):
    """Bar chart: occurrence count by violation type."""
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    colors = [BLUE if mt == "Model Move" else RED if mt == "Log Move" else ORANGE for mt in df["move_type"]]
    bars = ax.bar(df["violation_type"], df["count"], color=colors, edgecolor="white", width=0.55, alpha=0.88)
    ymax = max(df["count"].max(), 1)
    for bar, val in zip(bars, df["count"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.015,
            f"{int(val)}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )
    ax.set_xlabel("Violation Type", fontsize=11)
    ax.set_ylabel("Number of Violations", fontsize=11)
    ax.set_title("Violation Type Counts", fontsize=13, fontweight="bold")
    ax.set_ylim(0, ymax * 1.16)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelrotation=15)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_bar_chart.svg"))


def task3_heatmap(df: pd.DataFrame, output_dir: str):
    """Heatmap: one count cell per violation type."""
    labels = df["violation_type"].tolist()
    values = df["count"].to_numpy(dtype=float).reshape(-1, 1)

    fig_h = max(3.2, 1.1 + len(labels) * 0.85)
    fig, ax = plt.subplots(figsize=(6.5, fig_h))
    im = ax.imshow(values, cmap="YlGnBu", aspect="auto")
    ax.set_xticks([0])
    ax.set_xticklabels(["Count"], fontsize=11)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_ylabel("Violation Type", fontsize=11)
    ax.set_title("Violation Type Heatmap", fontsize=13, fontweight="bold")
    max_val = max(df["count"].max(), 1)
    min_val = df["count"].min() if not df.empty else 0
    midpoint = min_val + (max_val - min_val) * 0.50
    for i, val in enumerate(df["count"]):
        color = "white" if val > midpoint else "#222222"
        ax.text(0, i, f"{int(val)}", ha="center", va="center", fontsize=12, fontweight="bold", color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.08, pad=0.04)
    cbar.set_label("Number of Violations", fontsize=10)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_heatmap.svg"))


def task3_pie_chart(df: pd.DataFrame, output_dir: str):
    """Pie chart: proportion of violation move types."""
    colors = [BLUE if mt == "Model Move" else RED if mt == "Log Move" else ORANGE for mt in df["move_type"]]
    labels = [label.replace("\n", " ") for label in df["violation_type"]]

    fig, ax = plt.subplots(figsize=(7, 5.5))
    wedges, texts, autotexts = ax.pie(
        df["count"],
        colors=colors,
        startangle=110,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 1 else "",
        pctdistance=0.72,
        wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops=dict(fontsize=9, color="#222222"),
    )
    for t in autotexts:
        t.set_fontweight("bold")
    ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.10), ncol=1, frameon=False, fontsize=9)
    ax.set_title("Violation Types", fontsize=13, fontweight="bold")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_pie_chart.svg"))


def task3_table(df: pd.DataFrame, output_dir: str):
    """Table: violation type, count and percentage."""
    total = int(df["count"].sum())
    cell_text = [
        [row["violation_type"].replace("\n", " "), f"{int(row['count'])}", f"{row['percentage']:.2f}%"]
        for _, row in df.iterrows()
    ]
    cell_text.append(["Total", f"{total}", "100.00%" if total else "0.00%"])
    col_labels = ["Violation Type", "Count", "Percentage"]

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
        highlight_last_row=True,
    )
    ax.set_title("Violation Type Summary", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task3_table.svg"))


def task3_table_and_bar_chart(df: pd.DataFrame, output_dir: str):
    """Composite: compact summary table and horizontal bar chart."""
    total = int(df["count"].sum())
    fig = plt.figure(figsize=(13.5, 4.8))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.05, 1.70], wspace=0.62)
    ax_table = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    ax_table.axis("off")
    cell_text = [
        [row["violation_type"], f"{int(row['count'])}", f"{row['percentage']:.2f}%"]
        for _, row in df.iterrows()
    ]
    cell_text.append(["Total", f"{total}", "100.00%" if total else "0.00%"])
    make_table(
        ax_table,
        cell_text=cell_text,
        col_labels=["Violation", "Count", "%"],
        bbox=[0.02, 0.22, 0.92, 0.58],
        col_widths=[0.56, 0.22, 0.22],
        font_size=8.5,
        scale_xy=(1, 1.0),
        highlight_last_row=True,
    )
    ax_table.set_title("Table", fontsize=13, fontweight="bold", pad=10)

    plot_df = df.sort_values("count", ascending=True)
    colors = [BLUE if mt == "Model Move" else RED if mt == "Log Move" else ORANGE for mt in plot_df["move_type"]]
    ax_bar.barh(plot_df["violation_type"], plot_df["count"], color=colors, alpha=0.9)
    xmax = max(plot_df["count"].max(), 1)
    for y, val in enumerate(plot_df["count"]):
        ax_bar.text(val + xmax * 0.015, y, f"{int(val)}", va="center", fontsize=10, fontweight="bold")
    ax_bar.set_xlabel("Number of Violations", fontsize=10)
    ax_bar.set_title("Bar Chart", fontsize=13, fontweight="bold", pad=10)
    ax_bar.tick_params(axis="y", pad=8)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)
    fig.suptitle("Task 3 Violation Type Summary", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_svg(fig, os.path.join(output_dir, "task3_table_and_bar_chart.svg"))



def _task3_wrap_label(label: str, max_chars: int = 14) -> str:
    """Wrap long activity label at underscore boundaries to fit inside chevron."""
    if len(label) <= max_chars:
        return label
    parts = label.split("_")
    lines, current = [], ""
    for part in parts:
        token = part if not current else f"_{part}"
        if len(current) + len(token) <= max_chars:
            current += token
        else:
            if current:
                lines.append(current)
            current = part
    if current:
        lines.append(current)
    return "\n".join(lines) if lines else label


def _task3_build_activity_violation_nodes(alignments, max_nodes: int = 16):
    """Aggregate violations by activity across ALL traces.

    Returns (nodes, items, truncated):
      nodes     – list of {label, color} for _draw_chevrons
      items     – list of {activity, dominant_type, total, avg_pos} sorted by process position
      truncated – True when capped at max_nodes
    """
    from collections import defaultdict

    # acc[activity] = {"counts": {move_type: int}, "positions": [step, ...]}
    acc = defaultdict(lambda: {"counts": defaultdict(int), "positions": []})

    for result in alignments:
        rows = alignment_pairs_to_rows(result.get("alignment", []))
        for row in rows:
            mt = row["moveType"]
            if mt == "Synchronous Move":
                continue
            # anchor each violation to its process activity name
            if mt == "Model Move":
                act = row["model_move"]
            elif mt == "Log Move":
                act = row["log_move"]
            else:                          # Mismatch – expected position
                act = row["model_move"]
            if not act or act == "-":
                continue
            acc[act]["counts"][mt] += 1
            acc[act]["positions"].append(row["step"])

    if not acc:
        return [], [], False

    items = []
    for act, s in acc.items():
        dominant = max(s["counts"], key=s["counts"].get)
        total    = sum(s["counts"].values())
        avg_pos  = sum(s["positions"]) / len(s["positions"])
        items.append({
            "activity":     act,
            "dominant_type": dominant,
            "total":        total,
            "avg_pos":      avg_pos,
        })

    # sort by process position first; cap to top-N by count if too many
    items.sort(key=lambda x: x["avg_pos"])
    truncated = len(items) > max_nodes
    if truncated:
        items = sorted(items, key=lambda x: x["total"], reverse=True)[:max_nodes]
        items.sort(key=lambda x: x["avg_pos"])

    nodes = []
    for item in items:
        color = (BLUE   if item["dominant_type"] == "Model Move"
                 else RED    if item["dominant_type"] == "Log Move"
                 else ORANGE)
        label = _task3_wrap_label(item["activity"]) + f"\n×{item['total']}"
        nodes.append({"label": label, "color": color})

    return nodes, items, truncated


def task3_flow_chart_and_table(df: pd.DataFrame, alignments, output_dir: str):
    """Composite: violation summary table (top) + activity-level violation map (bottom).

    Table  – violation-type counts & percentages aggregated across all traces.
    Flow   – each violating activity as a chevron node, coloured by dominant
             violation type and labelled with total violation count, ordered by
             average process position so the flow reads left-to-right.
    """
    nodes, items, truncated = _task3_build_activity_violation_nodes(alignments)

    # fall back to an empty axis message when no violations exist
    has_flow = bool(nodes)

    # ── Percentages from df for legend labels ──
    pct = {row["move_type"]: row["percentage"] for _, row in df.iterrows()}

    # ── Figure sizing ──
    total = int(df["count"].sum())
    n_data_rows = len(df)

    _layout, span = _chevron_layout(nodes) if has_flow else ({}, 0)
    fig_w    = min(max(16.0, span * 0.29 + 1.6), 40.0)
    table_h  = max(2.4, 1.1 + n_data_rows * 0.52)
    chevron_h = 1.8
    fig_h    = table_h + chevron_h + 0.9

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs  = gridspec.GridSpec(2, 1, height_ratios=[table_h, chevron_h], hspace=0.42)
    ax_table   = fig.add_subplot(gs[0])
    ax_chevron = fig.add_subplot(gs[1])

    # ── Table ──
    ax_table.axis("off")
    cell_text = [
        [row["violation_type"].replace("\n", " "),
         f"{int(row['count'])}",
         f"{row['percentage']:.2f}%"]
        for _, row in df.iterrows()
    ]
    cell_text.append(["Total", f"{total}", "100.00%" if total else "0.00%"])
    make_table(
        ax_table,
        cell_text=cell_text,
        col_labels=["Violation Type", "Count", "Percentage"],
        bbox=[0.05, 0.05, 0.90, 0.78],
        font_size=10,
        scale_xy=(1, 1.7),
        highlight_last_row=True,
    )
    ax_table.set_title("Table", fontsize=13, fontweight="bold", pad=10)

    # ── Chevron flow ──
    if has_flow:
        _draw_chevrons(ax_chevron, nodes, fontsize=10)
        flow_title = "Flow Chart"
        if truncated:
            flow_title += f" (top {len(nodes)} activities by count)"
        ax_chevron.set_title(flow_title, fontsize=13, fontweight="bold", pad=10)
    else:
        ax_chevron.axis("off")
        ax_chevron.text(0.5, 0.5, "No violations found", ha="center", va="center",
                        fontsize=12, color="#888888", transform=ax_chevron.transAxes)

    # ── Legend ──
    legend_handles = [
        mpatches.Patch(facecolor=BLUE,   edgecolor="black", linewidth=0.75,
                       label=f"Model Move ({pct.get('Model Move', 0):.1f}%)"),
        mpatches.Patch(facecolor=RED,    edgecolor="black", linewidth=0.75,
                       label=f"Log Move ({pct.get('Log Move', 0):.1f}%)"),
        mpatches.Patch(facecolor=ORANGE, edgecolor="black", linewidth=0.75,
                       label=f"Mismatch Move ({pct.get('Mismatch Move', 0):.1f}%)"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center", bbox_to_anchor=(0.5, 0.01),
        ncol=3, fontsize=9.5, frameon=True, fancybox=False, edgecolor="#cccccc",
    )

    fig.suptitle("Violation Type Summary", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0.07, 1, 0.93])
    save_svg(fig, os.path.join(output_dir, "task3_flow_chart_and_table.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(alignments, output_dir: str):
    """Generate all Task 3 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 3 visualizations ---")
    df = task3_violation_summary_dataframe(alignments)
    if df.empty:
        logger.warning("      Skipped Task 3: no violation moves found.")
        return
    task3_bar_chart(df, output_dir)
    task3_heatmap(df, output_dir)
    task3_pie_chart(df, output_dir)
    task3_table(df, output_dir)
    task3_table_and_bar_chart(df, output_dir)
    task3_flow_chart_and_table(df, alignments, output_dir)
