"""
tasks/task26.py – Task ID 26: Present / Present / Severity of guideline violations.

Violation types and their severity are DEFINED BEFOREHAND (configuration, not
computation) and presented to the analyst. The (activity, move-type) violation
classification is reused from task29 (via shared.build_violation_pattern_df);
no alignments are re-run.

Public API:
    generate(alignments, output_dir)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "table", "table_bar_chart", "matrix",
          "pie_chart", "sunburst", "tree_map", "parallel_sets",
          "heatmap", "flow_chart_elaborate", "flow_chart_table"]

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
    render_empty_state_svg, contrasting_text_color,
    parse_bpmn_model, render_bpmn_annotated, draw_value_heatmap,
    GREY_DARK, GREY_LIGHT, GREY_LIGHTER, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

TOP_N = 12

# ===========================================================================
# SEVERITY CONFIGURATION — single source of truth for this task.
#
# The experiment's ground truth depends on this mapping; redefine it HERE only.
# Resolution order per violation pattern (activity, move_type):
#   1. SEVERITY_OVERRIDES[(activity, move_type)]   (exact pattern override)
#   2. DEFAULT_SEVERITY[move_type]                  (rule by move type)
#
# Move-type keys use the classification labels from shared.alignment_pairs_to_rows
# ("Model Move" = activity required by guideline but skipped in the log,
#  "Log Move"   = unexpected extra activity in the log,
#  "Mismatch Move" = log and model differ at the same step).
# Rationale of the default rule: a skipped mandatory activity is graver than
# an unexpected extra one; a mismatch is treated like an unexpected one.
# ===========================================================================

SEVERITY_LEVELS = ["High", "Medium", "Low"]          # fixed display order

SEVERITY_OVERRIDES: dict = {
    # ("A_ACTIVATED", "Log Move"): "High",          # example override
}

DEFAULT_SEVERITY = {
    "Model Move":    "High",
    "Log Move":      "Medium",
    "Mismatch Move": "Medium",
}


def resolve_severity(activity: str, move_type: str) -> str:
    """Resolve a pattern's severity: override first, then move-type default."""
    return SEVERITY_OVERRIDES.get(
        (activity, move_type),
        DEFAULT_SEVERITY.get(move_type, "Medium"),
    )


# Consistent severity colours across ALL idioms of this task
# (greyscale palette per house style: dark = grave).
SEVERITY_COLORS = {"High": GREY_DARK, "Medium": GREY_LIGHT, "Low": GREY_LIGHTER}
_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_LEVELS)}


def _lighten(hex_color: str, factor: float) -> str:
    """Blend a hex colour towards white by *factor* (0 = unchanged, 1 = white)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task26_build_severity_df(alignments) -> pd.DataFrame:
    """Pattern DataFrame (task29 classification) extended by resolved severity."""
    pat_df = build_violation_pattern_df(alignments)
    if pat_df.empty:
        pat_df["severity"] = pd.Series(dtype=str)
        return pat_df
    pat_df = pat_df.copy()
    pat_df["severity"] = [
        resolve_severity(act, mt)
        for act, mt in zip(pat_df["activity"], pat_df["move_type"])
    ]
    pat_df["sev_rank"] = pat_df["severity"].map(_SEVERITY_RANK)
    pat_df = (pat_df.sort_values(["sev_rank", "count"], ascending=[True, False])
              .reset_index(drop=True))
    return pat_df


def _severity_counts(pat_df: pd.DataFrame) -> pd.Series:
    """Violation counts per severity class; all classes kept (zeros included)."""
    counts = pat_df.groupby("severity")["count"].sum()
    return pd.Series({s: int(counts.get(s, 0)) for s in SEVERITY_LEVELS})


def _top_patterns(pat_df: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    """Top-N patterns by count, displayed sorted by severity then count."""
    top = pat_df.sort_values("count", ascending=False).head(top_n)
    return top.sort_values(["sev_rank", "count"], ascending=[True, False])


def _activity_severity_pivot(pat_df: pd.DataFrame, top_n: int = TOP_N):
    """(pivot, top_acts): activity × severity counts for the top-N activities."""
    act_totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts = act_totals.head(top_n).index.tolist()
    sub = pat_df[pat_df["activity"].isin(top_acts)]
    pivot = (sub.groupby(["activity", "severity"])["count"].sum()
             .unstack(fill_value=0)
             .reindex(index=top_acts, columns=SEVERITY_LEVELS, fill_value=0))
    return pivot, top_acts


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task26_bar_chart(pat_df: pd.DataFrame, output_dir: str):
    """Bar chart: violation count per severity class (High / Medium / Low)."""
    sev = _severity_counts(pat_df)
    ymax = max(int(sev.max()), 1)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    bars = ax.bar(SEVERITY_LEVELS, [sev[s] for s in SEVERITY_LEVELS],
                  color=[SEVERITY_COLORS[s] for s in SEVERITY_LEVELS],
                  edgecolor="white", width=0.55)
    for bar, s in zip(bars, SEVERITY_LEVELS):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.015,
                f"{sev[s]}", ha="center", va="bottom", fontsize=FONT_ANNOT)
    ax.set_xlabel("Severity Class", fontsize=FONT_LABEL)
    ax.set_ylabel("Number of Violations", fontsize=FONT_LABEL)
    ax.set_title("Violations by Severity Class", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.16)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_bar_chart.svg"))


def task26_stacked_bar(pat_df: pd.DataFrame, output_dir: str):
    """Stacked bar: one bar per activity (top-N), segments = severity classes."""
    pivot, top_acts = _activity_severity_pivot(pat_df)
    x = np.arange(len(top_acts))
    bottoms = np.zeros(len(top_acts))

    fig, ax = plt.subplots(figsize=(max(8, len(top_acts) * 0.9), 5.5))
    for s in SEVERITY_LEVELS:
        vals = pivot[s].values
        ax.bar(x, vals, bottom=bottoms, color=SEVERITY_COLORS[s],
               edgecolor="white", linewidth=0.5, label=s)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels(top_acts, rotation=0, fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Violation count", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Severity per Activity (top-{len(top_acts)})",
                 fontsize=FONT_TITLE)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_stacked_bar.svg"))


def task26_table(pat_df: pd.DataFrame, output_dir: str):
    """Table: Pattern | Activity | Move type | Severity | Count | % of all violations."""
    top = _top_patterns(pat_df)
    cell_text = [
        [row["pattern"], row["activity"], row["move_type"], row["severity"],
         str(int(row["count"])), f"{row['pct']:.1f}%"]
        for _, row in top.iterrows()
    ]
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(15, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Violation Pattern", "Activity", "Move Type",
                    "Severity", "Count", "% of All"],
        bbox=[0.01, 0.05, 0.98, 0.88],
        col_widths=[0.30, 0.20, 0.14, 0.12, 0.12, 0.12],
        font_size=9.5,
        scale_xy=(1, 1.75),
        cell_pad=0.09,
    )
    ax.set_title(f"Violation Patterns by Severity (top-{len(top)})",
                 fontsize=FONT_TITLE, pad=4)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_table.svg"))


def task26_table_and_bar_chart(pat_df: pd.DataFrame, output_dir: str):
    """Composite: severity-sorted pattern table + adjacent severity-class bar."""
    top = _top_patterns(pat_df)
    sev = _severity_counts(pat_df)

    fig = plt.figure(figsize=(15, max(4.8, 1.2 + len(top) * 0.45)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.7, 1.0], wspace=0.35)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text = [
        [row["pattern"], row["severity"], str(int(row["count"])), f"{row['pct']:.1f}%"]
        for _, row in top.iterrows()
    ]
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Violation Pattern", "Severity", "Count", "%"],
        bbox=[0.01, 0.05, 0.98, 0.88],
        col_widths=[0.52, 0.20, 0.14, 0.14],
        font_size=9,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )
    ax_tbl.set_title(f"Top-{len(top)} Violation Patterns", fontsize=FONT_TITLE, pad=4)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(SEVERITY_LEVELS))
    ax_bar.barh(y, [sev[s] for s in SEVERITY_LEVELS],
                color=[SEVERITY_COLORS[s] for s in SEVERITY_LEVELS],
                edgecolor="white")
    xmax = max(int(sev.max()), 1)
    for yi, s in zip(y, SEVERITY_LEVELS):
        ax_bar.text(sev[s] + xmax * 0.015, yi, f"{sev[s]}",
                    va="center", fontsize=FONT_ANNOT)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(SEVERITY_LEVELS, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Number of Violations", fontsize=FONT_LABEL)
    ax_bar.set_title("Violations per Severity Class", fontsize=FONT_TITLE, pad=10)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_table_and_bar_chart.svg"))


def task26_matrix(pat_df: pd.DataFrame, output_dir: str):
    """Matrix: rows = activity (top-N), columns = severity class, cell = count."""
    pivot, top_acts = _activity_severity_pivot(pat_df)
    data = pivot.values.astype(float)

    cmap = LinearSegmentedColormap.from_list("task26_mat", ["#F8F8F8", "#444444"])
    vmax = max(data.max(), 1.0)

    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(SEVERITY_LEVELS) * 2.0), fig_h))
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(SEVERITY_LEVELS)))
    ax.set_xticklabels(SEVERITY_LEVELS, fontsize=FONT_ANNOT)
    ax.set_yticks(range(len(top_acts)))
    ax.set_yticklabels(top_acts, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Severity Class", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Severity Matrix (top-{len(top_acts)} activities)",
                 fontsize=FONT_TITLE)

    midpoint = vmax * 0.55
    for ri in range(len(top_acts)):
        for ci in range(len(SEVERITY_LEVELS)):
            val = data[ri, ci]
            tc = "white" if val > midpoint else "#222222"
            ax.text(ci, ri, f"{int(val)}", ha="center", va="center",
                    fontsize=FONT_ANNOT, color=tc)

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Count", fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_matrix.svg"))


def task26_pie_chart(pat_df: pd.DataFrame, output_dir: str):
    """Donut: share of total violations per severity class, labelled with %."""
    sev = _severity_counts(pat_df)
    total = int(sev.sum())
    present = [s for s in SEVERITY_LEVELS if sev[s] > 0]

    fig, ax = plt.subplots(figsize=(8, 6))
    if present:
        values = [sev[s] for s in present]
        colors = [SEVERITY_COLORS[s] for s in present]
        wedges, _texts, autotexts = ax.pie(
            values,
            colors=colors,
            startangle=90,
            counterclock=False,
            autopct=lambda pct: f"{pct:.1f}%" if pct >= 1 else "",
            pctdistance=0.68,
            wedgeprops=dict(edgecolor="white", linewidth=2),
            textprops=dict(fontsize=FONT_ANNOT),
        )
        for color, autotext in zip(colors, autotexts):
            autotext.set_color(contrasting_text_color(color))
    # legend keeps all classes (zero classes included) in fixed order
    ax.legend(
        handles=[mpatches.Patch(
            color=SEVERITY_COLORS[s],
            label=f"{s} ({int(sev[s])}, {sev[s] / total * 100:.1f}%)" if total
                  else f"{s} (0)")
            for s in SEVERITY_LEVELS],
        loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=3,
        frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
    )
    ax.set_title("Violation Share per Severity Class", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_pie_chart.svg"))


def task26_sunburst(pat_df: pd.DataFrame, output_dir: str):
    """Sunburst: hierarchy severity → move type → activity as nested pie rings."""
    # Hierarchical ordering: severity rank, then move type, then count desc.
    df = pat_df.sort_values(["sev_rank", "move_type", "count"],
                            ascending=[True, True, False])

    ring1 = df.groupby("severity", sort=False)["count"].sum()
    ring2 = df.groupby(["severity", "move_type"], sort=False)["count"].sum()
    ring3 = df.set_index(["severity", "move_type", "activity"])["count"]
    total = float(ring1.sum())

    fig, ax = plt.subplots(figsize=(8.5, 7))
    common = dict(startangle=90, counterclock=False)

    # Inner ring: severity
    c1 = [SEVERITY_COLORS[s] for s in ring1.index]
    ax.pie(ring1.values, radius=0.50, colors=c1,
           wedgeprops=dict(width=0.26, edgecolor="white", linewidth=1.5), **common)
    # Middle ring: move type within severity
    c2 = [_lighten(SEVERITY_COLORS[s], 0.30) for s, _mt in ring2.index]
    ax.pie(ring2.values, radius=0.76, colors=c2,
           wedgeprops=dict(width=0.26, edgecolor="white", linewidth=1.5), **common)
    # Outer ring: activity within (severity, move type)
    c3 = [_lighten(SEVERITY_COLORS[s], 0.55 if i % 2 == 0 else 0.45)
          for i, (s, _mt, _a) in enumerate(ring3.index)]
    wedges3, _ = ax.pie(ring3.values, radius=1.02, colors=c3,
                        wedgeprops=dict(width=0.26, edgecolor="white", linewidth=1.5),
                        **common)

    # Wedge labels for sufficiently large segments
    def _annotate(values, labels, r, fontsize, colors=None, min_frac=0.05):
        angle = 90.0
        for i, (val, label) in enumerate(zip(values, labels)):
            frac = val / total if total else 0
            mid = angle - frac * 360.0 / 2.0
            angle -= frac * 360.0
            if frac < min_frac:
                continue
            theta = np.deg2rad(mid)
            x, y = r * np.cos(theta), r * np.sin(theta)
            color = "#222222"
            if colors is not None:
                color = contrasting_text_color(colors[i])
            ax.text(x, y, label, ha="center", va="center",
                    fontsize=fontsize, color=color)

    _annotate(ring1.values, list(ring1.index), 0.37, FONT_ANNOT, colors=c1)
    _annotate(ring2.values, [mt.replace(" Move", "") for _s, mt in ring2.index],
              0.63, FONT_ANNOT - 1, colors=c2)
    _annotate(ring3.values, [a for _s, _mt, a in ring3.index],
              0.89, FONT_ANNOT - 2, colors=c3, min_frac=0.06)

    ax.legend(
        handles=[mpatches.Patch(color=SEVERITY_COLORS[s], label=s)
                 for s in SEVERITY_LEVELS],
        title="Severity (inner ring)", title_fontsize=FONT_ANNOT,
        loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=3,
        frameon=False, fontsize=FONT_ANNOT,
    )
    ax.set_title("Violation Severity Sunburst (severity → move type → activity)",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_sunburst.svg"))


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
        if w >= h:   # lay the row as a vertical strip on the left
            cy = y
            for r in row:
                cell_h = r / thickness
                rects.append((x, cy, thickness, cell_h))
                cy += cell_h
            x += thickness
            w -= thickness
        else:        # horizontal strip on top
            cx = x
            for r in row:
                cell_w = r / thickness
                rects.append((cx, y, cell_w, thickness))
                cx += cell_w
            y += thickness
            h -= thickness
        sizes = rest
    return rects


def task26_tree_map(pat_df: pd.DataFrame, output_dir: str):
    """Tree map: one rectangle per pattern (top-N + Other); area = count, colour = severity."""
    by_count = pat_df.sort_values("count", ascending=False)
    top = by_count.head(TOP_N)
    items = [
        {"label": row["pattern"], "count": int(row["count"]),
         "color": SEVERITY_COLORS[row["severity"]]}
        for _, row in top.iterrows()
    ]
    rest = by_count.iloc[TOP_N:]
    if not rest.empty:
        items.append({"label": "Other", "count": int(rest["count"].sum()),
                      "color": "#EEEEEE"})
    items.sort(key=lambda it: it["count"], reverse=True)

    W, H = 100.0, 62.0
    total = sum(it["count"] for it in items)
    sizes = [it["count"] / total * W * H for it in items]
    rects = _squarify_layout(sizes, 0.0, 0.0, W, H)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.invert_yaxis()
    ax.axis("off")
    for it, (rx, ry, rw, rh) in zip(items, rects):
        ax.add_patch(plt.Rectangle((rx, ry), rw, rh, facecolor=it["color"],
                                   edgecolor="white", linewidth=2))
        area_frac = (rw * rh) / (W * H)
        if area_frac > 0.015 and rw > 8 and rh > 4:
            fontsize = FONT_ANNOT if area_frac > 0.06 else FONT_ANNOT - 2
            label = it["label"]
            if len(label) > 26 and " (" in label:
                label = label.replace(" (", "\n(")
            ax.text(rx + rw / 2, ry + rh / 2, f"{label}\n{it['count']}",
                    ha="center", va="center", fontsize=fontsize,
                    color=contrasting_text_color(it["color"]))
    ax.legend(
        handles=[mpatches.Patch(color=SEVERITY_COLORS[s], label=s)
                 for s in SEVERITY_LEVELS] +
                ([mpatches.Patch(color="#EEEEEE", label="Other (mixed)")]
                 if not rest.empty else []),
        title="Severity", title_fontsize=FONT_ANNOT,
        loc="lower center", bbox_to_anchor=(0.5, -0.10), ncol=4,
        frameon=False, fontsize=FONT_ANNOT,
    )
    ax.set_title(f"Violation Patterns Tree Map (area = count, top-{len(top)} + Other)",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_tree_map.svg"))


def task26_parallel_sets(pat_df: pd.DataFrame, output_dir: str):
    """Parallel Sets: severity class (left) × activity top-N + Other (right)."""
    act_totals = pat_df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts = act_totals.head(TOP_N).index.tolist()
    has_other = len(act_totals) > TOP_N
    right_cats = top_acts + (["Other"] if has_other else [])

    matrix = np.zeros((len(SEVERITY_LEVELS), len(right_cats)), dtype=int)
    for si, s in enumerate(SEVERITY_LEVELS):
        sub = pat_df[pat_df["severity"] == s]
        for ci, act in enumerate(top_acts):
            matrix[si, ci] = int(sub[sub["activity"] == act]["count"].sum())
        if has_other:
            matrix[si, -1] = int(sub[~sub["activity"].isin(top_acts)]["count"].sum())

    sev = _severity_counts(pat_df)
    left_labels = [f"{s}\n(n={sev[s]})" for s in SEVERITY_LEVELS]
    left_colors = [SEVERITY_COLORS[s] for s in SEVERITY_LEVELS]

    greys = ["#CCCCCC", "#BBBBBB", "#AAAAAA", "#999999", "#888888",
             "#777777", "#666666", "#555555", "#444444", "#333333", "#DDDDDD"]
    right_colors = [greys[i % len(greys)] for i in range(len(right_cats))]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Severity Class vs. Activity", fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_cats,
        matrix=matrix,
        left_colors=left_colors,
        right_colors=right_colors,
        left_title="Severity",
        right_title="Activity",
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

def _task26_activity_severity(pat_df: pd.DataFrame) -> dict:
    """activity -> (highest severity label, total count) across its violations."""
    out = {}
    for act, sub in pat_df.groupby("activity"):
        best_rank = int(sub["sev_rank"].min())
        out[act] = (SEVERITY_LEVELS[best_rank], int(sub["count"].sum()))
    return out


def task26_heatmap(pat_df: pd.DataFrame, output_dir: str):
    """Activity × severity class, counts, continuous colour (complements matrix)."""
    pivot, top_acts = _activity_severity_pivot(pat_df)
    data = pivot.values.astype(float)
    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(SEVERITY_LEVELS) * 2.0), fig_h))
    draw_value_heatmap(fig, ax, data, top_acts, SEVERITY_LEVELS, xlabel="Severity Class",
                       cbar_label="Count", annotate=False)
    ax.set_title(f"Violation Severity Heatmap (top-{len(top_acts)} activities)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_heatmap.svg"))


def _task26_severity_legend():
    return [(SEVERITY_COLORS[s], "#444444", 3, f"{s} severity") for s in SEVERITY_LEVELS] \
        + [("white", "#888888", 2, "No violation")]


def task26_flow_chart_elaborate(pat_df: pd.DataFrame, model_path: str, output_dir: str):
    """Desired model with task nodes coloured by their highest violation severity."""
    parsed = parse_bpmn_model(model_path)
    act_sev = _task26_activity_severity(pat_df)

    def _node_style(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task" and name in act_sev:
            fill = SEVERITY_COLORS[act_sev[name][0]]
            return (fill, "#444444", 3, contrasting_text_color(fill))
        return ("white", "#888888", 2, "#333333")

    n_marked = sum(1 for e in parsed["elements"].values()
                   if e["kind"] == "task" and e["name"] in act_sev)
    render_bpmn_annotated(
        parsed,
        os.path.join(output_dir, "task26_flow_chart_elaborate.svg"),
        title="Guideline Violations on the Desired Model — by Severity",
        summary=f"{n_marked} task(s) carry violations; colour = highest severity "
                f"(High > Medium > Low).",
        node_style_fn=_node_style,
        legend_items=_task26_severity_legend(),
    )


def task26_flow_chart_table(pat_df: pd.DataFrame, model_path: str, output_dir: str):
    """Model-deviation severity table: one row per annotated activity."""
    parsed = parse_bpmn_model(model_path)
    model_names = {e["name"] for e in parsed["elements"].values()
                   if e["kind"] == "task" and e["name"]}
    act_sev = _task26_activity_severity(pat_df)

    rows = []
    for act, (sev, count) in act_sev.items():
        in_model = "yes" if act in model_names else "no (log only)"
        rows.append((act, sev, count, in_model, _SEVERITY_RANK[sev]))
    rows.sort(key=lambda r: (r[4], -r[2]))
    cell_text = [[r[0], r[1], str(r[2]), r[3]] for r in rows] or \
        [["(No violations)", "—", "—", "—"]]

    fig_h = max(3.0, 1.3 + len(cell_text) * 0.44)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Activity", "Highest Severity", "Violation Count", "In Model"],
        bbox=[0.02, 0.05, 0.96, 0.86],
        col_widths=[0.40, 0.22, 0.20, 0.18],
        font_size=10,
        scale_xy=(1, 1.7),
        cell_pad=0.10,
    )
    ax.set_title("Per-Activity Violation Severity (annotated on the model)",
                 fontsize=FONT_TITLE, pad=4)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task26_flow_chart_table.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(alignments, output_dir: str, model_path: str = None):
    """Generate all Task ID 26 SVGs into output_dir.

    model_path is required for the flow-chart idioms (model annotated by
    severity); when absent those two idioms are skipped.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 26 visualizations ---")

    pat_df = _task26_build_severity_df(alignments)

    if pat_df.empty:
        logger.warning("      task26: no violation moves found — emitting zero-state SVGs.")
        for fname, title in [
            ("task26_bar_chart.svg",           "Violations by Severity Class"),
            ("task26_stacked_bar.svg",         "Violation Severity per Activity"),
            ("task26_table.svg",               "Violation Patterns by Severity"),
            ("task26_table_and_bar_chart.svg", "Violation Patterns by Severity"),
            ("task26_matrix.svg",              "Violation Severity Matrix"),
            ("task26_pie_chart.svg",           "Violation Share per Severity Class"),
            ("task26_sunburst.svg",            "Violation Severity Sunburst"),
            ("task26_tree_map.svg",            "Violation Patterns Tree Map"),
            ("task26_parallel_sets.svg",       "Severity Class vs. Activity"),
            ("task26_heatmap.svg",             "Violation Severity Heatmap"),
            ("task26_flow_chart_elaborate.svg", "Violations on the Desired Model"),
            ("task26_flow_chart_table.svg",    "Per-Activity Violation Severity"),
        ]:
            render_empty_state_svg(os.path.join(output_dir, fname), title,
                                   "No violations found.")
        return

    logger.info(f"      -> {len(pat_df)} patterns; resolved severities:")
    for _, row in pat_df.iterrows():
        logger.info(f"         {row['pattern']:<55} -> {row['severity']:<6} "
                    f"(count={int(row['count'])})")
    for s in SEVERITY_LEVELS:
        if (pat_df["severity"] == s).sum() == 0:
            logger.warning(f"      task26: severity class '{s}' has no violations "
                           f"(kept in legends/axes).")

    task26_bar_chart(pat_df, output_dir)
    task26_stacked_bar(pat_df, output_dir)
    task26_table(pat_df, output_dir)
    task26_table_and_bar_chart(pat_df, output_dir)
    task26_matrix(pat_df, output_dir)
    task26_pie_chart(pat_df, output_dir)
    task26_sunburst(pat_df, output_dir)
    task26_tree_map(pat_df, output_dir)
    task26_parallel_sets(pat_df, output_dir)
    task26_heatmap(pat_df, output_dir)
    if model_path:
        try:
            task26_flow_chart_elaborate(pat_df, model_path, output_dir)
            task26_flow_chart_table(pat_df, model_path, output_dir)
        except Exception as e:
            logger.warning(f"      task26: flow-chart idioms skipped ({e}).")
    else:
        logger.warning("      task26: no model_path — flow-chart idioms skipped.")
