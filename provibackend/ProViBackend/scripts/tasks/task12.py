"""
tasks/task12.py – Task 12: Summarize Process Conformance
Goal: Describe · Means: Summarize · Characteristics: Process conformance

Question: In what percentage of traces do violations occur?

Visualizations (all SVG, white-grey-black palette):
  tile_metric     – KPI tiles: % conformant · % deviating
  pie_chart       – 2-slice: conformant vs deviating
  bar_chart       – 2 horizontal bars with counts + %
  stacked_bar     – single 100% bar subdivided into 5 violation-profile categories
  table           – detailed breakdown: conformant + deviating sub-categories
  table_bar_chart – compact table (left) + horizontal bars (right)
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "tile_metric", "pie_chart", "bar_chart",
    "stacked_bar", "table", "table_bar_chart",
]

import os
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from shared import save_svg, FONT_TITLE, FONT_LABEL, FONT_ANNOT, classify_step as _classify_step

# ── Palette ───────────────────────────────────────────────────────────────────
_C_DARK   = "#222222"
_C_MED    = "#666666"
_C_LIGHT  = "#aaaaaa"
_C_XLIGHT = "#dddddd"
_HDR_BG   = "#333333"

# 5-category colors (conformant + 4 deviating subcategories)
_CAT_COLORS = {
    "conformant": "#eeeeee",
    "mom_only":   "#cccccc",   # Move on Model only  (skipped)
    "mol_only":   "#888888",   # Move on Log only    (extra)
    "mm_only":    "#555555",   # Mismatch Move only
    "mixed":      "#222222",   # multiple violation types
}
_CAT_LABELS = {
    "conformant": "Conformant",
    "mom_only":   "Deviating — Skipped only (MoM)",
    "mol_only":   "Deviating — Extra only (MoL)",
    "mm_only":    "Deviating — Mismatch only (MM)",
    "mixed":      "Deviating — Mixed types",
}
_CAT_ORDER = ["conformant", "mom_only", "mol_only", "mm_only", "mixed"]


# ── Data extraction ───────────────────────────────────────────────────────────

def _extract_data(alignments):
    """
    Classify each trace into one of 5 categories:
      conformant / mom_only / mol_only / mm_only / mixed

    Returns dict with n_total, n_conformant, n_deviating,
    pct_conformant, pct_deviating, categories (Counter).
    """
    n_total    = len(alignments)
    categories = Counter()

    for aln in alignments:
        vtypes = set()
        for step in aln.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            _, vtype = _classify_step(step[0], step[1])
            if vtype is not None:
                vtypes.add(vtype)

        if not vtypes:
            categories["conformant"] += 1
        elif len(vtypes) == 1:
            vt = next(iter(vtypes))
            if vt == "Move on Model":
                categories["mom_only"] += 1
            elif vt == "Move on Log":
                categories["mol_only"] += 1
            else:
                categories["mm_only"] += 1
        else:
            categories["mixed"] += 1

    n_conformant = categories["conformant"]
    n_deviating  = n_total - n_conformant
    pct_c = n_conformant / n_total * 100 if n_total > 0 else 0.0
    pct_d = n_deviating  / n_total * 100 if n_total > 0 else 0.0

    return {
        "n_total":        n_total,
        "n_conformant":   n_conformant,
        "n_deviating":    n_deviating,
        "pct_conformant": pct_c,
        "pct_deviating":  pct_d,
        "categories":     categories,
    }


def _save_empty(output_dir, filename, message="No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


def _no_data(output_dir, name):
    _save_empty(output_dir, f"task12_{name}.svg", "No alignment data available.")


# ── Idiom 1: Tile Metric ──────────────────────────────────────────────────────

def task12_tile_metric(stats, output_dir):
    """Two large KPI tiles: % conformant and % deviating."""
    if stats["n_total"] == 0:
        _no_data(output_dir, "tile_metric")
        return

    pct_c = stats["pct_conformant"]
    pct_d = stats["pct_deviating"]
    n_c   = stats["n_conformant"]
    n_d   = stats["n_deviating"]
    n_t   = stats["n_total"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))

    tile_data = [
        (axes[0], f"{pct_c:.1f}%", "Conformant Traces",
         f"{n_c:,} of {n_t:,} traces", "#f5f5f5", _C_DARK),
        (axes[1], f"{pct_d:.1f}%", "Deviating Traces",
         f"{n_d:,} of {n_t:,} traces", _C_DARK, "white"),
    ]

    for ax, big, label, sub, bg, fg in tile_data:
        ax.set_facecolor(bg)
        for spine in ax.spines.values():
            spine.set_edgecolor(_C_LIGHT)
            spine.set_linewidth(1.2)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.5, 0.58, big, ha="center", va="center",
                fontsize=38, fontweight="bold", color=fg,
                transform=ax.transAxes)
        ax.text(0.5, 0.30, label, ha="center", va="center",
                fontsize=FONT_LABEL + 1, color=fg,
                transform=ax.transAxes)
        ax.text(0.5, 0.14, sub, ha="center", va="center",
                fontsize=FONT_ANNOT, color=fg if bg == _C_DARK else _C_MED,
                transform=ax.transAxes)

    fig.suptitle("Process Conformance Summary", fontsize=FONT_TITLE + 1, y=1.02)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_tile_metric.svg"))


# ── Idiom 2: Pie Chart ────────────────────────────────────────────────────────

def task12_pie_chart(stats, output_dir):
    """2-slice pie: conformant (light) vs deviating (dark).
    Small slices (< 5%) get outside labels with a leader line."""
    if stats["n_total"] == 0:
        _no_data(output_dir, "pie_chart")
        return

    n_c, n_d, n_t = stats["n_conformant"], stats["n_deviating"], stats["n_total"]
    pct_c, pct_d  = stats["pct_conformant"], stats["pct_deviating"]

    slice_data = [
        (n_c, pct_c, _CAT_COLORS["conformant"], "Conformant"),
        (n_d, pct_d, "#333333",                 "Deviating"),
    ]

    def _autopct(pct):
        cnt = int(round(pct / 100 * n_t))
        return f"{pct:.1f}%\n({cnt:,})"

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, _texts, autotexts = ax.pie(
        [n_c, n_d],
        labels=None,
        colors=[d[2] for d in slice_data],
        autopct=_autopct,
        startangle=90,
        pctdistance=0.68,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
        textprops=dict(fontsize=FONT_ANNOT),
    )
    for atext, (_, _, clr, _) in zip(autotexts, slice_data):
        r_in = int(clr[1:3], 16)
        atext.set_color("white" if r_in < 150 else _C_DARK)

    ax.legend(
        wedges,
        [f"Conformant  ({n_c:,} traces, {pct_c:.1f}%)",
         f"Deviating  ({n_d:,} traces, {pct_d:.1f}%)"],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.06),
        fontsize=FONT_ANNOT,
        frameon=True, framealpha=0.9,
        ncol=2,
    )
    ax.set_title("Conformant vs Deviating Traces", fontsize=FONT_TITLE, pad=16)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_pie_chart.svg"))


# ── Idiom 3: Bar Chart ────────────────────────────────────────────────────────

def task12_bar_chart(stats, output_dir):
    """2 horizontal bars: conformant / deviating, with counts + %."""
    if stats["n_total"] == 0:
        _no_data(output_dir, "bar_chart")
        return

    n_c, n_d, n_t = stats["n_conformant"], stats["n_deviating"], stats["n_total"]
    pct_c, pct_d  = stats["pct_conformant"], stats["pct_deviating"]

    labels = ["Conformant", "Deviating"]
    counts = [n_c, n_d]
    pcts   = [pct_c, pct_d]
    colors = [_CAT_COLORS["conformant"], _C_DARK]

    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.set_facecolor("#fafbfc")

    for i, (cnt, pct, clr) in enumerate(zip(counts, pcts, colors)):
        ax.barh(i, cnt, color=clr, edgecolor="white", linewidth=0.8, height=0.55)
        txt_color = "white" if int(clr[1:3], 16) < 150 else _C_DARK
        # Count inside bar (if bar is wide enough), else outside
        if cnt / n_t > 0.12:
            ax.text(cnt * 0.5, i, f"{cnt:,}  ({pct:.1f}%)",
                    ha="center", va="center",
                    fontsize=FONT_ANNOT + 1, color=txt_color, fontweight="bold")
        else:
            ax.text(cnt + n_t * 0.01, i, f"{cnt:,}  ({pct:.1f}%)",
                    ha="left", va="center",
                    fontsize=FONT_ANNOT + 1, color=_C_DARK)

    ax.set_yticks([0, 1])
    ax.set_yticklabels(labels, fontsize=FONT_LABEL)
    ax.set_xlabel("Number of traces", fontsize=FONT_LABEL)
    ax.set_title(
        f"Conformant vs Deviating Traces  ·  {n_t:,} total",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlim(0, n_t * 1.22)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_bar_chart.svg"))


# ── Idiom 4: Stacked Bar ─────────────────────────────────────────────────────

def task12_stacked_bar(stats, output_dir):
    """Two-row stacked bar:
    Row 1 (top):    All traces    — Conformant | Deviating          (100% of n_total)
    Row 2 (bottom): Deviating     — MoM | MoL | MM | Mixed          (100% of n_deviating)
    """
    if stats["n_total"] == 0:
        _no_data(output_dir, "stacked_bar")
        return

    n_t  = stats["n_total"]
    n_d  = stats["n_deviating"]
    cats = stats["categories"]

    n_c = cats.get("conformant", 0)

    # Row 1: conformant vs deviating (% of all)
    row1 = [
        (n_c / n_t * 100,  n_c, _CAT_COLORS["conformant"], "Conformant"),
        (n_d / n_t * 100,  n_d, _C_DARK,                   "Deviating"),
    ]

    # Row 2: deviating subcategories (% of deviating)
    sub_cats = ["mom_only", "mol_only", "mm_only", "mixed"]
    row2 = []
    for c in sub_cats:
        cnt  = cats.get(c, 0)
        frac = cnt / n_d * 100 if n_d > 0 else 0.0
        row2.append((frac, cnt, _CAT_COLORS[c], _CAT_LABELS[c]))

    fig, ax = plt.subplots(figsize=(13, 4.2))
    ax.set_facecolor("#fafbfc")

    bar_h = 0.45

    def _draw_row(y, segments):
        left = 0.0
        for frac, cnt, clr, _ in segments:
            ax.barh(y, frac, left=left, color=clr,
                    edgecolor="white", linewidth=1.2, height=bar_h)
            if frac > 5:
                txt_color = "white" if int(clr[1:3], 16) < 150 else _C_DARK
                ax.text(left + frac / 2, y, f"{frac:.1f}%\n({cnt:,})",
                        ha="center", va="center",
                        fontsize=FONT_ANNOT, color=txt_color, linespacing=1.4)
            left += frac

    _draw_row(1.0, row1)
    _draw_row(0.0, row2)

    # Legend: all 5 categories
    patches = [
        mpatches.Patch(color=_CAT_COLORS[c], label=f"{_CAT_LABELS[c]}  ({cats.get(c, 0):,})")
        for c in _CAT_ORDER
    ]

    ax.set_xlim(0, 100)
    ax.set_xlabel("Proportion (%)", fontsize=FONT_LABEL)
    ax.set_yticks([1.0, 0.0])
    ax.set_yticklabels(
        [f"All traces\n({n_t:,})", f"Deviating only\n({n_d:,})"],
        fontsize=FONT_LABEL,
    )
    ax.set_title(
        f"Trace Conformance Profile  ·  {n_t:,} total traces",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(
        handles=patches,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.20),
        ncol=3,
        fontsize=FONT_ANNOT,
        frameon=True, framealpha=0.9,
    )

    fig.tight_layout(rect=[0, 0.10, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task12_stacked_bar.svg"))


# ── Idiom 5: Table ────────────────────────────────────────────────────────────

def task12_table(stats, output_dir):
    """Breakdown table: conformant row + 4 deviating subcategory rows + totals."""
    if stats["n_total"] == 0:
        _no_data(output_dir, "table")
        return

    n_t  = stats["n_total"]
    cats = stats["categories"]
    n_d  = stats["n_deviating"]

    rows = []
    # Conformant row
    n_c  = cats.get("conformant", 0)
    rows.append(["Conformant", f"{n_c:,}", f"{n_c / n_t * 100:.1f}%", "—"])

    # Deviating subtotal
    rows.append(["Deviating  (subtotal)", f"{n_d:,}", f"{n_d / n_t * 100:.1f}%", "100%"])

    # Subcategories (indented labels)
    sub_defs = [
        ("mom_only", "  └ Skipped only (MoM)"),
        ("mol_only", "  └ Extra only (MoL)"),
        ("mm_only",  "  └ Mismatch only (MM)"),
        ("mixed",    "  └ Mixed violation types"),
    ]
    for key, label in sub_defs:
        cnt = cats.get(key, 0)
        pct_total = cnt / n_t * 100 if n_t > 0 else 0
        pct_dev   = cnt / n_d * 100 if n_d > 0 else 0
        rows.append([label, f"{cnt:,}", f"{pct_total:.1f}%", f"{pct_dev:.1f}%"])

    # Total
    rows.append(["Total", f"{n_t:,}", "100%", "—"])

    col_headers = ["Category", "Traces", "% of All Traces", "% of Deviating"]
    col_widths  = [0.46, 0.16, 0.21, 0.17]

    n_rows = len(rows)
    fig_h  = max(3.5, n_rows * 0.55 + 2.0)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.axis("off")

    t  = 0.94
    b  = 0.06
    l  = 0.02
    tw = 0.96
    row_h = (t - b) / (n_rows + 1)

    # Header
    x = l
    for hdr, cw in zip(col_headers, col_widths):
        ax.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                   fc=_HDR_BG, ec="white", linewidth=0.5,
                                   transform=ax.transAxes, clip_on=False))
        ax.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                ha="center", va="center", fontsize=FONT_ANNOT,
                color="white", transform=ax.transAxes)
        x += cw * tw

    # Rows
    special_rows = {0, 1, n_rows - 1}  # conformant, deviating-subtotal, total
    for i, row in enumerate(rows):
        y_top = t - (i + 2) * row_h
        x = l
        if i in special_rows:
            bg = "#e8e8e8"
        else:
            bg = "#f5f5f5" if i % 2 == 0 else "white"

        for j, (val, cw) in enumerate(zip(row, col_widths)):
            ax.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                       fc=bg, ec="#eeeeee", linewidth=0.4,
                                       transform=ax.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            ax.text(px, y_top + row_h * 0.5, str(val),
                    ha=ha, va="center", fontsize=FONT_ANNOT,
                    color=_C_DARK,
                    transform=ax.transAxes)
            x += cw * tw

    ax.set_title(
        f"Process Conformance Breakdown  ·  {n_t:,} total traces",
        fontsize=FONT_TITLE, pad=14,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_table.svg"))


# ── Idiom 6: Table & Bar Chart ────────────────────────────────────────────────

def task12_table_bar_chart(stats, output_dir):
    """Left: compact conformance table. Right: horizontal bars per category."""
    if stats["n_total"] == 0:
        _no_data(output_dir, "table_bar_chart")
        return

    n_t  = stats["n_total"]
    cats = stats["categories"]

    cat_labels  = [_CAT_LABELS[c] for c in _CAT_ORDER]
    cat_counts  = [cats.get(c, 0) for c in _CAT_ORDER]
    cat_pcts    = [cnt / n_t * 100 for cnt in cat_counts]
    cat_colors  = [_CAT_COLORS[c] for c in _CAT_ORDER]

    n = len(_CAT_ORDER)
    fig, (ax_tbl, ax_bar) = plt.subplots(
        1, 2, figsize=(16, max(3.8, n * 0.72 + 2.2)),
        gridspec_kw={"width_ratios": [3, 4]},
    )

    # ── Left: table ──────────────────────────────────────────────────────────
    ax_tbl.axis("off")
    col_headers = ["Category", "Traces", "% of All"]
    col_widths  = [0.58, 0.22, 0.20]
    t = 0.94
    row_h = (t - 0.04) / (n + 1)
    tw = 0.97
    x = 0.015

    for hdr, cw in zip(col_headers, col_widths):
        ax_tbl.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                       fc=_HDR_BG, ec="white", linewidth=0.5,
                                       transform=ax_tbl.transAxes, clip_on=False))
        ax_tbl.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                    ha="center", va="center", fontsize=FONT_ANNOT,
                    color="white", fontweight="bold", transform=ax_tbl.transAxes)
        x += cw * tw

    for i, (lbl, cnt, pct) in enumerate(zip(cat_labels, cat_counts, cat_pcts)):
        y_top = t - (i + 2) * row_h
        x = 0.015
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(zip([lbl, f"{cnt:,}", f"{pct:.1f}%"], col_widths)):
            ax_tbl.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg, ec="#eeeeee", linewidth=0.4,
                                           transform=ax_tbl.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            ax_tbl.text(px, y_top + row_h * 0.5, str(val),
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, transform=ax_tbl.transAxes)
            x += cw * tw

    # ── Right: horizontal bars ────────────────────────────────────────────────
    ax_bar.set_facecolor("#fafbfc")
    for i, (cnt, clr) in enumerate(zip(cat_counts, cat_colors)):
        ax_bar.barh(i, cnt, color=clr, edgecolor="white", linewidth=0.6, height=0.6)
        ax_bar.text(cnt + n_t * 0.01, i, f"{cnt:,}",
                    va="center", fontsize=FONT_ANNOT, color=_C_DARK)

    ax_bar.set_yticks(range(n))
    ax_bar.set_yticklabels(cat_labels, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Number of traces", fontsize=FONT_LABEL)
    ax_bar.set_title("Trace count per category", fontsize=FONT_TITLE)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax_bar.set_axisbelow(True)
    ax_bar.set_xlim(0, n_t * 1.25)

    fig.suptitle(
        f"Process Conformance Breakdown  ·  {n_t:,} total traces",
        fontsize=FONT_TITLE + 1, y=1.01,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_table_bar_chart.svg"))


# ── Public entry point ────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, **kwargs):
    """Generate all Task 12 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 12 visualizations (Summarize process conformance) ---")

    if not alignments:
        logger.warning("      Skipped Task 12: no alignments provided.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task12_{name}.svg", "No alignment data available.")
        return

    stats = _extract_data(alignments)

    task12_tile_metric(stats, output_dir)
    task12_pie_chart(stats, output_dir)
    task12_bar_chart(stats, output_dir)
    task12_stacked_bar(stats, output_dir)
    task12_table(stats, output_dir)
    task12_table_bar_chart(stats, output_dir)
