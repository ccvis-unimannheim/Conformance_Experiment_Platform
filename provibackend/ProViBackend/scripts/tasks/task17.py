"""
tasks/task17.py – Task ID 17: Explain / Annotate / Severity of guideline violations.

How often is a guideline violated? This task presents the FREQUENCY of each
guideline violation (and where it occurs on the model), so the analyst can judge —
with their own pre-existing domain knowledge — how severe a frequent violation is
and whether a rule might be too strict.

Design note (why frequency only): severity, "is the rule too strict?", and textual
rationale are value judgments that depend on the dataset and business context, not
on the log. Baking them into the SVG would couple the visualization to one context.
Instead task17 shows the neutral facts — how often, what KIND of deviation
(skipped / inserted / mismatch — a label produced by the conformance algorithm,
not a judgment), and where on the model — and leaves the interpretation to the
reader (or to admin-authored explanation text added on the visualization page).

Reuses task26's squarified-treemap / lighten helpers and shared renderers, so any
dataset flows through unchanged: nothing here is keyed to specific activity names.

Public API:
    generate(log, alignments, output_dir, model_path=None)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "flow_chart_table", "flow_chart_elaborate",
          "flow_chart_elaborate_table", "table", "table_bar_chart", "matrix",
          "heatmap", "pie_chart", "sunburst", "tree_map", "parallel_sets"]

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
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    draw_value_heatmap, chevron_figure_width, draw_chevron_strip,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse task26's layout helpers only (no severity coupling).
from tasks.task26 import _lighten, _squarify_layout

TOP_N = 12

# Move types are the conformance algorithm's neutral classification of a deviation:
#   Model Move    – activity required by the guideline but skipped in the log
#   Log Move      – unexpected extra activity present in the log
#   Mismatch Move – recorded step differs from the prescribed one
# Greyscale palette (house style), no value ordering implied.
MOVE_TYPES = ["Model Move", "Log Move", "Mismatch Move"]
MOVE_TYPE_COLORS = {
    "Model Move":    "#555555",
    "Log Move":      "#999999",
    "Mismatch Move": "#CCCCCC",
}
_MOVE_RANK = {m: i for i, m in enumerate(MOVE_TYPES)}
_BAR_COLOR = "#9A9A9A"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _build_df(alignments) -> pd.DataFrame:
    """Per-pattern violation frame (pattern, activity, move_type, count, pct),
    sorted by frequency descending. No severity/assessment — frequency only."""
    df = build_violation_pattern_df(alignments)
    if df.empty:
        return df
    df = df.copy()
    df["move_rank"] = df["move_type"].map(_MOVE_RANK).fillna(len(MOVE_TYPES))
    return df.sort_values("count", ascending=False).reset_index(drop=True)


def _present_move_types(df: pd.DataFrame) -> list:
    """Move types that actually occur, in canonical order (avoids empty columns)."""
    present = set(df["move_type"])
    return [m for m in MOVE_TYPES if m in present] or list(present)


def _move_color(mt: str) -> str:
    return MOVE_TYPE_COLORS.get(mt, "#777777")


def _activity_movetype_pivot(df: pd.DataFrame, top_n: int = TOP_N):
    """(pivot, top_acts, move_types): activity × move-type counts, top-N activities."""
    move_types = _present_move_types(df)
    act_totals = df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts = act_totals.head(top_n).index.tolist()
    sub = df[df["activity"].isin(top_acts)]
    pivot = (sub.groupby(["activity", "move_type"])["count"].sum()
             .unstack(fill_value=0)
             .reindex(index=top_acts, columns=move_types, fill_value=0))
    return pivot, top_acts, move_types


def _activity_freq(df: pd.DataFrame) -> dict:
    """activity -> total violation count."""
    return {a: int(c) for a, c in df.groupby("activity")["count"].sum().items()}


def _freq_shade(count: float, max_count: float) -> str:
    """Light grey (rare) → dark grey (frequent)."""
    frac = (count / max_count) if max_count > 0 else 0.0
    frac = max(0.0, min(1.0, frac))
    lo, hi = 0xF0, 0x44
    v = int(round(lo + (hi - lo) * frac))
    return f"#{v:02X}{v:02X}{v:02X}"


def _wrap_pat(p: str) -> str:
    return str(p).replace(" (", "\n(", 1)


# ---------------------------------------------------------------------------
# Idiom 1: bar_chart — violation frequency per pattern (coloured by move type)
# ---------------------------------------------------------------------------

def task17_bar_chart(df, output_dir):
    top = df.head(TOP_N)
    patterns = top["pattern"].tolist()
    counts = top["count"].to_numpy(dtype=float)
    colors = [_move_color(m) for m in top["move_type"]]
    move_types = _present_move_types(df)
    x = np.arange(len(patterns))

    fig, ax = plt.subplots(figsize=(max(8, len(patterns) * 1.25), 6))
    ax.bar(x, counts, color=colors, edgecolor="white", linewidth=0.6, width=0.72)
    for xi, c in zip(x, counts):
        ax.text(xi, c, f"{int(c)}", ha="center", va="bottom",
                fontsize=FONT_ANNOT - 1, color="#444444")
    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_pat(p) for p in patterns], rotation=0,
                       ha="center", fontsize=FONT_ANNOT - 2)
    ax.set_ylabel("Violation frequency (count)", fontsize=FONT_LABEL)
    ax.set_ylim(0, counts.max() * 1.16 if len(counts) else 1)
    ax.set_title("How Often is Each Guideline Violated?", fontsize=FONT_TITLE)
    ax.legend(handles=[mpatches.Patch(color=_move_color(m), label=m) for m in move_types],
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=len(move_types), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 2: stacked_bar — frequency per activity, segmented by deviation type
# ---------------------------------------------------------------------------

def task17_stacked_bar(df, output_dir):
    pivot, top_acts, move_types = _activity_movetype_pivot(df)
    x = np.arange(len(top_acts))
    bottoms = np.zeros(len(top_acts))

    fig, ax = plt.subplots(figsize=(max(8, len(top_acts) * 0.95), 5.5))
    for m in move_types:
        vals = pivot[m].values
        ax.bar(x, vals, bottom=bottoms, color=_move_color(m),
               edgecolor="white", linewidth=0.5, label=m)
        bottoms += vals
    ax.set_xticks(x)
    ax.set_xticklabels(top_acts, rotation=0, fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Violation frequency (count)", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Frequency per Activity, by Deviation Type (top-{len(top_acts)})",
                 fontsize=FONT_TITLE)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_stacked_bar.svg"))


# ---------------------------------------------------------------------------
# Idiom 6: table — frequency per violation pattern
# ---------------------------------------------------------------------------

def task17_table(df, output_dir):
    top = df.head(TOP_N)
    cell_text = [
        [row["pattern"], row["activity"], row["move_type"],
         str(int(row["count"])), f"{row['pct']:.1f}%"]
        for _, row in top.iterrows()
    ]
    fig_h = max(3.0, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    make_table(
        ax, cell_text=cell_text,
        col_labels=["Violation Pattern", "Activity", "Deviation Type",
                    "Count", "% of All"],
        bbox=[0.02, 0.06, 0.96, 0.84],
        col_widths=[0.30, 0.26, 0.20, 0.12, 0.12],
        font_size=9.5, scale_xy=(1, 1.4))
    ax.set_title("Violation Frequency per Pattern", fontsize=FONT_TITLE, pad=10)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_table.svg"))


# ---------------------------------------------------------------------------
# Idiom 7: table_bar_chart — frequency table (left) + ranked bars (right)
# ---------------------------------------------------------------------------

def task17_table_bar_chart(df, output_dir):
    top = df.head(TOP_N)
    patterns = top["pattern"].tolist()
    counts = top["count"].to_numpy(dtype=float)
    colors = [_move_color(m) for m in top["move_type"]]

    fig_h = max(4.8, 1.3 + len(top) * 0.5)
    fig = plt.figure(figsize=(16, fig_h))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], wspace=0.45)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text = [[row["pattern"], row["move_type"], str(int(row["count"])), f"{row['pct']:.1f}%"]
                 for _, row in top.iterrows()]
    n_rows = len(cell_text) + 1
    tbl_frac = min(0.86, 0.55 * n_rows / fig_h)
    tbl_y0 = max(0.04, 0.86 - tbl_frac)
    make_table(
        ax_tbl, cell_text=cell_text,
        col_labels=["Violation Pattern", "Deviation Type", "Count", "% of All"],
        bbox=[0.01, tbl_y0, 0.98, tbl_frac],
        col_widths=[0.46, 0.26, 0.14, 0.14],
        font_size=9, scale_xy=(1, 1.4))
    ax_tbl.set_title(f"Top-{len(top)} Violations by Frequency", fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(patterns))
    ax_bar.barh(y, counts, color=colors, edgecolor="white", linewidth=0.6, height=0.62)
    for yi, c in zip(y, counts):
        ax_bar.text(c, yi, f" {int(c)}", va="center", ha="left",
                    fontsize=FONT_ANNOT - 1, color="#444444")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels([_wrap_pat(p) for p in patterns], fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Violation frequency (count)", fontsize=FONT_LABEL)
    ax_bar.set_xlim(0, counts.max() * 1.15 if len(counts) else 1)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax_bar.set_axisbelow(True)
    ax_bar.set_title("Frequency", fontsize=FONT_TITLE, pad=10)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_table_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 8 & 9: matrix / heatmap — activity × deviation-type counts
# ---------------------------------------------------------------------------

def task17_matrix(df, output_dir):
    pivot, top_acts, move_types = _activity_movetype_pivot(df)
    data = pivot.values.astype(float)
    cmap = LinearSegmentedColormap.from_list("task17_mat", ["#F8F8F8", "#444444"])
    vmax = max(data.max(), 1.0)

    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(move_types) * 2.0), fig_h))
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(move_types)))
    ax.set_xticklabels(move_types, fontsize=FONT_ANNOT)
    ax.set_yticks(range(len(top_acts)))
    ax.set_yticklabels(top_acts, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Deviation Type", fontsize=FONT_LABEL)
    ax.set_title(f"Violation Frequency: Activity × Deviation Type (top-{len(top_acts)})",
                 fontsize=FONT_TITLE)
    midpoint = vmax * 0.55
    for ri in range(len(top_acts)):
        for ci in range(len(move_types)):
            val = data[ri, ci]
            tc = "white" if val > midpoint else "#222222"
            ax.text(ci, ri, f"{int(val)}", ha="center", va="center",
                    fontsize=FONT_ANNOT, color=tc)
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Count", fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_matrix.svg"))


def task17_heatmap(df, output_dir):
    pivot, top_acts, move_types = _activity_movetype_pivot(df)
    data = pivot.values.astype(float)
    fig_h = max(3.5, 0.55 * len(top_acts) + 1.5)
    fig, ax = plt.subplots(figsize=(max(5, len(move_types) * 2.0), fig_h))
    draw_value_heatmap(fig, ax, data, top_acts, move_types,
                       xlabel="Deviation Type", cbar_label="Count", annotate=False)
    ax.set_title(f"Violation Frequency Heatmap (top-{len(top_acts)} activities)",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_heatmap.svg"))


# ---------------------------------------------------------------------------
# Idiom 10: pie_chart — share of total violations per deviation type
# ---------------------------------------------------------------------------

def task17_pie_chart(df, output_dir):
    move_types = _present_move_types(df)
    totals = pd.Series({m: int(df.loc[df["move_type"] == m, "count"].sum())
                        for m in move_types})
    total = int(totals.sum())

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = [_move_color(m) for m in move_types]
    _w, _t, autotexts = ax.pie(
        [totals[m] for m in move_types], colors=colors, startangle=90,
        counterclock=False,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 1 else "",
        pctdistance=0.68,
        wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops=dict(fontsize=FONT_ANNOT))
    for color, at in zip(colors, autotexts):
        at.set_color(contrasting_text_color(color))
    ax.legend(handles=[mpatches.Patch(
        color=_move_color(m),
        label=f"{m} ({int(totals[m])}, {totals[m]/total*100:.1f}%)" if total else f"{m} (0)")
        for m in move_types],
        loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2,
        frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.set_title("Share of Violations per Deviation Type", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_pie_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 11: sunburst — deviation type → activity (ring areas = frequency)
# ---------------------------------------------------------------------------

def task17_sunburst(df, output_dir):
    d = df.sort_values(["move_rank", "count"], ascending=[True, False])
    ring1 = d.groupby("move_type", sort=False)["count"].sum()
    ring2 = d.groupby(["move_type", "activity"], sort=False)["count"].sum()
    total = float(ring1.sum())

    fig, ax = plt.subplots(figsize=(8.5, 7))
    common = dict(startangle=90, counterclock=False)
    c1 = [_move_color(m) for m in ring1.index]
    ax.pie(ring1.values, radius=0.62, colors=c1,
           wedgeprops=dict(width=0.34, edgecolor="white", linewidth=1.5), **common)
    c2 = [_lighten(_move_color(m), 0.45 if i % 2 == 0 else 0.30)
          for i, (m, _a) in enumerate(ring2.index)]
    ax.pie(ring2.values, radius=1.02, colors=c2,
           wedgeprops=dict(width=0.40, edgecolor="white", linewidth=1.5), **common)

    def _annotate(values, labels, r, fontsize, colors, min_frac=0.05):
        angle = 90.0
        for i, (val, label) in enumerate(zip(values, labels)):
            frac = val / total if total else 0
            mid = angle - frac * 360.0 / 2.0
            angle -= frac * 360.0
            if frac < min_frac:
                continue
            theta = np.deg2rad(mid)
            ax.text(r * np.cos(theta), r * np.sin(theta), label, ha="center",
                    va="center", fontsize=fontsize, color=contrasting_text_color(colors[i]))

    _annotate(ring1.values, [m.replace(" Move", "") for m in ring1.index],
              0.45, FONT_ANNOT, c1)
    _annotate(ring2.values, [a for _m, a in ring2.index], 0.82, FONT_ANNOT - 2, c2, min_frac=0.05)

    ax.legend(handles=[mpatches.Patch(color=_move_color(m), label=m)
                       for m in _present_move_types(df)],
              title="Deviation type (inner ring)", title_fontsize=FONT_ANNOT,
              loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=3,
              frameon=False, fontsize=FONT_ANNOT)
    ax.set_title("Violation Sunburst (deviation type → activity)", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_sunburst.svg"))


# ---------------------------------------------------------------------------
# Idiom 12: tree_map — area = frequency, colour = deviation type
# ---------------------------------------------------------------------------

def task17_tree_map(df, output_dir):
    by_count = df.sort_values("count", ascending=False)
    top = by_count.head(TOP_N)
    items = [{"label": row["pattern"], "count": int(row["count"]),
              "color": _move_color(row["move_type"])}
             for _, row in top.iterrows()]
    rest = by_count.iloc[TOP_N:]
    if not rest.empty:
        items.append({"label": "Other", "count": int(rest["count"].sum()), "color": "#EEEEEE"})
    items.sort(key=lambda it: it["count"], reverse=True)

    W, H = 100.0, 62.0
    total = sum(it["count"] for it in items)
    sizes = [it["count"] / total * W * H for it in items]
    rects = _squarify_layout(sizes, 0.0, 0.0, W, H)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
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
    ax.legend(handles=[mpatches.Patch(color=_move_color(m), label=m)
                       for m in _present_move_types(df)] +
                      ([mpatches.Patch(color="#EEEEEE", label="Other (mixed)")]
                       if not rest.empty else []),
              title="Deviation type", title_fontsize=FONT_ANNOT,
              loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=4,
              frameon=False, fontsize=FONT_ANNOT)
    ax.set_title(f"Violation Tree Map (area = frequency, top-{len(top)} + Other)",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_tree_map.svg"))


# ---------------------------------------------------------------------------
# Idiom 13: parallel_sets — deviation type → activity
# ---------------------------------------------------------------------------

def task17_parallel_sets(df, output_dir):
    move_types = _present_move_types(df)
    act_totals = df.groupby("activity")["count"].sum().sort_values(ascending=False)
    top_acts = act_totals.head(TOP_N).index.tolist()
    has_other = len(act_totals) > TOP_N
    right_cats = top_acts + (["Other"] if has_other else [])

    matrix = np.zeros((len(move_types), len(right_cats)), dtype=int)
    for mi, m in enumerate(move_types):
        sub = df[df["move_type"] == m]
        for ci, act in enumerate(top_acts):
            matrix[mi, ci] = int(sub[sub["activity"] == act]["count"].sum())
        if has_other:
            matrix[mi, -1] = int(sub[~sub["activity"].isin(top_acts)]["count"].sum())

    mt_tot = {m: int(df.loc[df["move_type"] == m, "count"].sum()) for m in move_types}
    left_labels = [f"{m}\n(n={mt_tot[m]})" for m in move_types]
    greys = ["#CCCCCC", "#BBBBBB", "#AAAAAA", "#999999", "#888888", "#777777",
             "#666666", "#555555", "#444444", "#333333", "#DDDDDD"]
    right_colors = [greys[i % len(greys)] for i in range(len(right_cats))]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axis("off"); ax.set_xlim(-0.05, 1.05); ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Deviation Type vs. Activity", fontsize=FONT_TITLE, pad=12)
    draw_parallel_sets(ax, left_labels=left_labels, right_labels=right_cats,
                       matrix=matrix, left_colors=[_move_color(m) for m in move_types],
                       right_colors=right_colors, left_title="Deviation type",
                       right_title="Activity")
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task17_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Model idioms: nodes shaded by violation frequency
# ---------------------------------------------------------------------------

_BPMN_LEGEND = [
    ("#F0F0F0", "#777777", 1.0, "No / few violations"),
    ("#9A9A9A", "#777777", 1.0, "Some violations"),
    ("#444444", "#777777", 1.0, "Most violations"),
]


def _node_style_fn(act_freq, max_count):
    def style(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task" and name in act_freq:
            fill = _freq_shade(act_freq[name], max_count)
            tc = "white" if int(fill[1:3], 16) < 0x99 else "#222222"
            return fill, "#777777", 1.5, tc
        return "white", "#888888", 2, "#333333"
    return style


def task17_flow_chart_elaborate(df, model_path, output_dir):
    out = os.path.join(output_dir, "task17_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Violations on the Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"      task17: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Violations on the Model", "Could not parse the BPMN model.")
        return
    act_freq = _activity_freq(df)
    max_count = max(act_freq.values(), default=1)
    render_bpmn_annotated(
        parsed, out,
        title="Guideline Violations on the Model — by Frequency",
        summary="Activity shade: darker = violated more often",
        node_style_fn=_node_style_fn(act_freq, max_count),
        legend_items=_BPMN_LEGEND)


def task17_flow_chart_elaborate_table(df, model_path, output_dir):
    out = os.path.join(output_dir, "task17_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Violations on the Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"      task17: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Violations on the Model", "Could not parse the BPMN model.")
        return
    act_freq = _activity_freq(df)
    max_count = max(act_freq.values(), default=1)

    top = df.head(TOP_N)
    table_cols = ["Violation Pattern", "Activity", "Deviation Type", "Count"]
    table_rows = [[row["pattern"], row["activity"], row["move_type"], str(int(row["count"]))]
                  for _, row in top.iterrows()] or [["No violations found.", "", "", ""]]
    panels = [{"parsed": parsed, "node_style_fn": _node_style_fn(act_freq, max_count),
               "subtitle": "Activity shade = violation frequency · table lists the patterns"}]
    compose_bpmn_panels(panels, out,
                        title="Violations on the Model — with Frequency Table",
                        legend_items=_BPMN_LEGEND,
                        table_rows=table_rows, table_cols=table_cols)


def task17_flow_chart_table(log, df, output_dir):
    """Chevron of a representative variant shaded by violation frequency + table."""
    out = os.path.join(output_dir, "task17_flow_chart_table.svg")
    act_freq = _activity_freq(df)
    violated = set(act_freq)

    counts = {}
    for tr in log:
        key = tuple(str(e.get("concept:name", "")) for e in tr)
        if key:
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        render_empty_state_svg(out, "Violation Frequency along the Process",
                               "No activity sequence found.")
        return
    ranked = sorted(counts, key=counts.get, reverse=True)
    variant = next((list(k) for k in ranked if violated & set(k)), list(ranked[0]))
    seq = [a for i, a in enumerate(variant) if i == 0 or a != variant[i - 1]]
    max_count = max(act_freq.values(), default=1)
    nodes = [{"label": a, "color": _freq_shade(act_freq.get(a, 0), max_count)} for a in seq]

    top = df.head(TOP_N)
    fig_w = max(11.0, chevron_figure_width(nodes))
    n_tbl = len(top) + 1
    fig = plt.figure(figsize=(fig_w, max(5.5, 2.4 + n_tbl * 0.42)))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.0, max(1.0, n_tbl * 0.5)], hspace=0.32)
    ax_flow = fig.add_subplot(gs[0])
    draw_chevron_strip(ax_flow, nodes, fontsize=10)
    ax_flow.set_title("Violation Frequency along a Representative Variant  (darker = more frequent)",
                      fontsize=FONT_TITLE)
    ax_tbl = fig.add_subplot(gs[1])
    ax_tbl.axis("off")
    cell_text = [[row["pattern"], row["activity"], row["move_type"], str(int(row["count"]))]
                 for _, row in top.iterrows()]
    make_table(ax_tbl, cell_text=cell_text,
               col_labels=["Violation Pattern", "Activity", "Deviation Type", "Count"],
               bbox=[0.04, 0.04, 0.92, 0.86], col_widths=[0.34, 0.30, 0.22, 0.14],
               font_size=9.5, scale_xy=(1, 1.4))
    ax_tbl.set_title("Violation Frequency per Pattern", fontsize=FONT_TITLE, pad=8)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task17_bar_chart.svg",                  "How Often is Each Guideline Violated?"),
    ("task17_stacked_bar.svg",                "Violation Frequency per Activity"),
    ("task17_flow_chart_table.svg",           "Violation Frequency along the Process"),
    ("task17_flow_chart_elaborate.svg",       "Violations on the Model"),
    ("task17_flow_chart_elaborate_table.svg", "Violations on the Model + Table"),
    ("task17_table.svg",                      "Violation Frequency per Pattern"),
    ("task17_table_bar_chart.svg",            "Violations by Frequency"),
    ("task17_matrix.svg",                     "Activity × Deviation Type"),
    ("task17_heatmap.svg",                    "Violation Frequency Heatmap"),
    ("task17_pie_chart.svg",                  "Share of Violations per Deviation Type"),
    ("task17_sunburst.svg",                   "Violation Sunburst"),
    ("task17_tree_map.svg",                   "Violation Tree Map"),
    ("task17_parallel_sets.svg",              "Deviation Type vs. Activity"),
]


def generate(log, alignments, output_dir: str, model_path: str = None):
    """Generate all Task ID 17 SVGs into output_dir (frequency only)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 17 visualizations ---")

    df = _build_df(alignments)
    if df.empty:
        logger.warning("      task17: no violation moves found — emitting zero-state SVGs.")
        for fname, title in _ALL_FNAMES_TITLES:
            render_empty_state_svg(os.path.join(output_dir, fname), title, "No violations found.")
        return

    logger.info(f"      -> {len(df)} violation patterns (frequency only):")
    for _, row in df.head(TOP_N).iterrows():
        pat = str(row["pattern"]).encode("ascii", "replace").decode()
        logger.info(f"         {pat:<48} count={int(row['count']):>6}")

    task17_bar_chart(df, output_dir)
    task17_stacked_bar(df, output_dir)
    task17_table(df, output_dir)
    task17_table_bar_chart(df, output_dir)
    task17_matrix(df, output_dir)
    task17_heatmap(df, output_dir)
    task17_pie_chart(df, output_dir)
    task17_sunburst(df, output_dir)
    task17_tree_map(df, output_dir)
    task17_parallel_sets(df, output_dir)
    task17_flow_chart_table(log, df, output_dir)
    task17_flow_chart_elaborate(df, model_path, output_dir)
    task17_flow_chart_elaborate_table(df, model_path, output_dir)
