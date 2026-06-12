"""
tasks/task29.py – Task 3: Violation type summaries across all traces.

Public API:
    generate(alignments, output_dir)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "heatmap", "pie_chart", "flow_chart_table", "table", "table_bar_chart",
          "stacked_bar", "matrix", "sunburst", "tree_map", "parallel_sets"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon
from matplotlib import gridspec

from shared import (
    save_svg, make_table, alignment_pairs_to_rows,
    BLUE, ORANGE, GREEN, RED, FONT_TITLE, FONT_LABEL, FONT_ANNOT, contrasting_text_color,
    build_violation_pattern_df, draw_value_heatmap, draw_parallel_sets, render_empty_state_svg,
)

# ---------------------------------------------------------------------------
# Canonical violation type order and color mapping
# ---------------------------------------------------------------------------
_VTYPES = ["Model Move", "Log Move", "Mismatch Move"]
_VTYPE_COLOR = {
    "Model Move":    BLUE,
    "Log Move":      RED,
    "Mismatch Move": ORANGE,
}
_TOP_N = 12   # top-N activities for per-activity idioms (consistent with task09/11/17)


def _lighten(hex_color: str, amount: float = 0.5) -> str:
    """Blend hex_color toward white by `amount` (0=no change, 1=white)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _squarify_layout(sizes, x, y, w, h):
    """Squarified treemap layout (no external dependency).

    sizes must be sorted descending and scaled so sum(sizes) == w * h.
    Returns one (x, y, w, h) rect per size, in input order.
    """
    rects = []
    sizes = list(sizes)
    while sizes:
        if len(sizes) == 1:
            rects.append((x, y, w, h))
            break
        short = min(w, h)

        def worst_ratio(row):
            row_total = sum(row)
            thickness = row_total / short
            worst = 1.0
            for r in row:
                cell_len = r / thickness
                worst = max(worst, thickness / cell_len, cell_len / thickness)
            return worst

        row = [sizes[0]]
        rest = sizes[1:]
        current = worst_ratio(row)
        while rest:
            cand = worst_ratio(row + [rest[0]])
            if cand <= current:
                row.append(rest.pop(0))
                current = cand
            else:
                break

        thickness = sum(row) / short
        if w >= h:
            cy = y
            for r in row:
                cell_h = r / thickness
                rects.append((x, cy, thickness, cell_h))
                cy += cell_h
            x += thickness
            w -= thickness
        else:
            cx = x
            for r in row:
                cell_w = r / thickness
                rects.append((cx, y, cell_w, thickness))
                cx += cell_w
            y += thickness
            h -= thickness
        sizes = rest
    return rects


def _task29_activity_type_pivot(alignments, top_n=_TOP_N):
    """Aggregate violations per (activity, move_type) from raw alignments.

    Returns (pivot, top_acts):
      pivot    – dict {(activity, move_type): count}
      top_acts – list of top_n activities sorted by total violation count desc
    """
    pat_df = build_violation_pattern_df(alignments)
    if pat_df.empty:
        return {}, []
    pivot = {(r["activity"], r["move_type"]): int(r["count"])
             for _, r in pat_df.iterrows()}
    act_totals = pat_df.groupby("activity")["count"].sum()
    top_acts = act_totals.nlargest(top_n).index.tolist()
    return pivot, top_acts


# ---------------------------------------------------------------------------
# Chevron helpers (same visual style as task28)
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


def _draw_chevrons(ax, nodes, fontsize=10):
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
            color=contrasting_text_color(node["color"]), clip_on=False,
        )
    ax.set_xlim(-0.45, span + 0.45)
    ax.set_ylim(-0.08, h + 0.08)
    return span


# ---------------------------------------------------------------------------
# Task 3 – Violation type summaries across all traces
# ---------------------------------------------------------------------------

# Task 3 helpers
TASK29_TYPE_LABELS = {
    "Model Move": "Model Move\n(Missing in Log)",
    "Log Move": "Log Move\n(Unexpected in Log)",
    "Mismatch Move": "Mismatch Move\n(Log/Model differ)",
}


def task29_violation_summary_dataframe(alignments):
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
                "violation_type": TASK29_TYPE_LABELS.get(move_type, move_type),
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
def task29_bar_chart(df: pd.DataFrame, output_dir: str):
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
            fontsize=FONT_ANNOT,
        )
    ax.set_xlabel("Violation Type", fontsize=FONT_LABEL)
    ax.set_ylabel("Number of Violations", fontsize=FONT_LABEL)
    ax.set_title("Violations by Type", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.16)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelrotation=15)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task29_bar_chart.svg"))


def task29_heatmap(df: pd.DataFrame, output_dir: str):
    """Heatmap: one count cell per violation type."""
    labels = df["violation_type"].tolist()
    values = df["count"].to_numpy(dtype=float).reshape(-1, 1)

    fig_h = max(3.2, 1.1 + len(labels) * 0.85)
    fig, ax = plt.subplots(figsize=(6.5, fig_h))
    im = ax.imshow(values, cmap="Greys", aspect="auto")
    ax.set_xticks([0])
    ax.set_xticklabels(["Count"], fontsize=FONT_ANNOT)
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_ylabel("Violation Type", fontsize=FONT_LABEL)
    ax.set_title("Violation Frequency", fontsize=FONT_TITLE)
    max_val = max(df["count"].max(), 1)
    min_val = df["count"].min() if not df.empty else 0
    midpoint = min_val + (max_val - min_val) * 0.50
    for i, val in enumerate(df["count"]):
        color = "white" if val > midpoint else "#222222"
        ax.text(0, i, f"{int(val)}", ha="center", va="center", fontsize=FONT_ANNOT, color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.08, pad=0.04)
    cbar.set_label("Number of Violations", fontsize=FONT_ANNOT)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task29_heatmap.svg"))


def task29_pie_chart(df: pd.DataFrame, output_dir: str):
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
        textprops=dict(fontsize=FONT_ANNOT),
    )
    for color, autotext in zip(colors, autotexts):
        autotext.set_color(contrasting_text_color(color))
    ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.10), ncol=1, frameon=False, fontsize=FONT_ANNOT)
    ax.set_title("Violation Type Proportions", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task29_pie_chart.svg"))


def task29_table(df: pd.DataFrame, output_dir: str):
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
    ax.set_title("Violation Type Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task29_table.svg"))


def task29_table_and_bar_chart(df: pd.DataFrame, output_dir: str):
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
    ax_table.set_title("Table", fontsize=FONT_TITLE, pad=10)

    plot_df = df.sort_values("count", ascending=True)
    colors = [BLUE if mt == "Model Move" else RED if mt == "Log Move" else ORANGE for mt in plot_df["move_type"]]
    ax_bar.barh(plot_df["violation_type"], plot_df["count"], color=colors, alpha=0.9)
    xmax = max(plot_df["count"].max(), 1)
    for y, val in enumerate(plot_df["count"]):
        ax_bar.text(val + xmax * 0.015, y, f"{int(val)}", va="center", fontsize=FONT_ANNOT)
    ax_bar.set_xlabel("Number of Violations", fontsize=FONT_LABEL)
    ax_bar.set_title("Bar Chart", fontsize=FONT_TITLE, pad=10)
    ax_bar.tick_params(axis="y", pad=8)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)
    fig.suptitle("Violation Type Summary", fontsize=FONT_TITLE, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_svg(fig, os.path.join(output_dir, "task29_table_and_bar_chart.svg"))



def _task29_wrap_label(label: str, max_chars: int = 14) -> str:
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


def _task29_build_activity_violation_nodes(alignments, max_nodes: int = 16):
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
        label = _task29_wrap_label(item["activity"]) + f"\n×{item['total']}"
        nodes.append({"label": label, "color": color})

    return nodes, items, truncated


def task29_flow_chart_and_table(df: pd.DataFrame, alignments, output_dir: str):
    """Composite: violation summary table (top) + activity-level violation map (bottom).

    Table  – violation-type counts & percentages aggregated across all traces.
    Flow   – each violating activity as a chevron node, coloured by dominant
             violation type and labelled with total violation count, ordered by
             average process position so the flow reads left-to-right.
    """
    nodes, items, truncated = _task29_build_activity_violation_nodes(alignments)

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
    ax_table.set_title("Table", fontsize=FONT_TITLE, pad=10)

    # ── Chevron flow ──
    if has_flow:
        _draw_chevrons(ax_chevron, nodes, fontsize=10)
        flow_title = "Violations by Activity"
        if truncated:
            flow_title += f" (top {len(nodes)} by count)"
        ax_chevron.set_title(flow_title, fontsize=FONT_TITLE, pad=10)
    else:
        ax_chevron.axis("off")
        ax_chevron.text(0.5, 0.5, "No violations found", ha="center", va="center",
                        fontsize=FONT_ANNOT, color="#888888", transform=ax_chevron.transAxes)

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
        ncol=3, fontsize=FONT_ANNOT, frameon=True, fancybox=False, edgecolor="#cccccc",
    )

    fig.suptitle("Violation Type Summary", fontsize=FONT_TITLE, y=0.98)
    fig.tight_layout(rect=[0, 0.07, 1, 0.93])
    save_svg(fig, os.path.join(output_dir, "task29_flow_chart_and_table.svg"))



# ---------------------------------------------------------------------------
# New idiom 1: Stacked bar — violation type breakdown per activity
# ---------------------------------------------------------------------------

def task29_stacked_bar(alignments, output_dir: str):
    """Horizontal stacked bar: top-N activities coloured by violation type (Model/Log/Mismatch)."""
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
    ax.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", fontsize=FONT_ANNOT, frameon=True, framealpha=0.9)
    fig.tight_layout()
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
        cbar_label="Violation count",
        cell_fmt="{:.0f}",
        annotate=True,
        rotate_xticks=0,
    )
    ax.set_title("Activity × Violation Type Matrix", fontsize=FONT_TITLE, pad=10)
    fig.tight_layout()
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

    grey_scale = ["#CCCCCC", "#AAAAAA", "#999999", "#888888", "#777777",
                  "#666666", "#555555", "#444444", "#333333", "#222222", "#BBBBBB", "#DDDDDD", "#EEEEEE"]
    right_colors = [grey_scale[i % len(grey_scale)] for i in range(n_right)]

    draw_parallel_sets(
        ax,
        left_labels=_VTYPES,
        right_labels=right_labels,
        matrix=matrix,
        left_colors=[_VTYPE_COLOR[vt] for vt in _VTYPES],
        right_colors=right_colors,
        left_title="Violation Type",
        right_title="Activity",
    )
    fig.tight_layout()
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 4: Tree Map — violation patterns by area = count
# ---------------------------------------------------------------------------

_TREEMAP_TOP_N = 20


def task29_tree_map(alignments, output_dir: str):
    """Tree map: one rectangle per (activity, move_type) pattern, area = count."""
    out_path = os.path.join(output_dir, "task29_tree_map.svg")
    pat_df = build_violation_pattern_df(alignments)
    if pat_df.empty:
        render_empty_state_svg(out_path, "Violation Pattern Tree Map")
        return

    by_count = pat_df.sort_values("count", ascending=False)
    top = by_count.head(_TREEMAP_TOP_N)
    items = [
        {"label": row["activity"], "move_type": row["move_type"],
         "count": int(row["count"]), "color": _VTYPE_COLOR[row["move_type"]]}
        for _, row in top.iterrows()
    ]
    rest = by_count.iloc[_TREEMAP_TOP_N:]
    if not rest.empty:
        items.append({"label": "Other", "move_type": "", "count": int(rest["count"].sum()),
                      "color": "#DDDDDD"})

    W, H = 100.0, 62.0
    total = sum(it["count"] for it in items)
    sizes = [it["count"] / total * W * H for it in items]
    rects = _squarify_layout(sizes, 0.0, 0.0, W, H)

    fig, ax = plt.subplots(figsize=(12, 7.5))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.invert_yaxis()
    ax.axis("off")
    for it, (rx, ry, rw, rh) in zip(items, rects):
        ax.add_patch(plt.Rectangle((rx, ry), rw, rh,
                                   facecolor=it["color"], edgecolor="white", linewidth=2))
        area_frac = (rw * rh) / (W * H)
        if area_frac > 0.015 and rw > 7 and rh > 3.5:
            fontsize = FONT_ANNOT if area_frac > 0.05 else FONT_ANNOT - 2
            mt_short = it["move_type"].replace(" Move", "") if it["move_type"] else ""
            label = it["label"]
            if len(label) > 22:
                label = label[:20] + "…"
            cell_text = f"{label}\n{mt_short}\n×{it['count']}" if mt_short else f"{label}\n×{it['count']}"
            ax.text(rx + rw / 2, ry + rh / 2, cell_text,
                    ha="center", va="center", fontsize=fontsize,
                    color=contrasting_text_color(it["color"]))

    legend_handles = [
        mpatches.Patch(color=_VTYPE_COLOR[vt], label=vt) for vt in _VTYPES
    ]
    if not rest.empty:
        legend_handles.append(mpatches.Patch(color="#DDDDDD", label="Other"))
    ax.legend(handles=legend_handles, loc="lower center",
              bbox_to_anchor=(0.5, -0.06), ncol=4, frameon=False, fontsize=FONT_ANNOT)
    ax.set_title(f"Violation Pattern Tree Map  (area = count, top-{len(top)})",
                 fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, out_path)


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
            ax.text(x, y, short, ha="center", va="center",
                    fontsize=fontsize, color=contrasting_text_color(colors[i]))

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
    fig.tight_layout()
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------

def generate(alignments, output_dir: str):
    """Generate all Task 3 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 3 visualizations ---")
    df = task29_violation_summary_dataframe(alignments)
    if df.empty:
        logger.warning("      Skipped Task 3: no violation moves found.")
        return
    task29_bar_chart(df, output_dir)
    task29_heatmap(df, output_dir)
    task29_pie_chart(df, output_dir)
    task29_table(df, output_dir)
    task29_table_and_bar_chart(df, output_dir)
    task29_flow_chart_and_table(df, alignments, output_dir)
    task29_stacked_bar(alignments, output_dir)
    task29_matrix(alignments, output_dir)
    task29_parallel_sets(alignments, output_dir)
    task29_tree_map(alignments, output_dir)
    task29_sunburst(alignments, output_dir)
