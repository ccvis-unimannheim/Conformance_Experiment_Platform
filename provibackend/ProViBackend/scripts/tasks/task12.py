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


def _param_spec():
    """Which violations the study counts (empty = all).

    Fixed to the pattern unit: the question names concrete violations —
    "Log Move on Ship Order" — not a move type or an activity.
    """
    import violation_profile
    return [violation_profile.selection_param_for("pattern")]


PARAM_SPEC = _param_spec()


import os
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import save_svg, make_table, GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER, CIVIDIS, FONT_TITLE, FONT_LABEL, FONT_ANNOT, classify_step as _classify_step

def _wrap(text, width=22):
    """Break a long violation label so a tile does not overflow its box."""
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        cur = f"{cur} {w}".strip()
        if len(cur) > width:
            lines.append(cur); cur = ""
    if cur:
        lines.append(cur)
    return "\n".join(lines) or str(text)


# ── Cividis palette ───────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK
_C_MED    = GREY_MED
_C_LIGHT  = GREY_LIGHT
_C_XLIGHT = GREY_LIGHTER
_HDR_BG   = GREY_DARK

# 5-category colors (conformant + 4 deviating subcategories)
_CAT_COLORS = {
    "conformant": GREY_LIGHTER,  # yellow-green (best)
    "mom_only":   GREY_MED,      # olive-grey   (skipped mandatory step)
    "mol_only":   GREY_DARK,     # dark navy    (extra unexpected step)
    "mm_only":    GREY_LIGHT,    # light olive  (mismatch)
    "mixed":      GREY_DARK,     # dark navy    (multiple violation types)
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

def _extract_data(alignments, violation_patterns=None):
    """Trace coverage per violation, plus the log's overall conformance.

    Returns n_total / n_conformant / n_deviating / pct_conformant /
    pct_deviating, and ``violations``: one row per violation with

        label       "Ship Order (Model Move)"
        traces      distinct traces containing it
        pct_traces  those traces as a share of the whole log
        pct_count   its share of all violation occurrences
        move_type   for colour

    **The two percentages have different denominators, and the difference
    matters here.** ``pct_traces`` answers the task's question — in what
    percentage of traces does this violation occur — but the column does not
    sum to 100: one trace can carry several violations and is counted under
    each. On the order_to_cash log it sums to 38.2% while 28.4% of traces
    deviate at all. So part-of-whole idioms (the pie, the 100% stacked bar)
    cannot draw it without lying about the whole, and use ``pct_count``, which
    does sum to 100, saying so in their titles.

    ``violation_patterns`` narrows what counts as a violation: with a selection
    a trace carrying only unselected deviations counts as conformant. Empty
    counts every violation.
    """
    import violation_profile

    n_total = len(alignments)
    profile = violation_profile.profile(alignments, "pattern",
                                        selection=violation_patterns,
                                        n_traces=n_total)
    violations = [
        {
            "label": str(r["group"]),
            "traces": int(r["traces"]),
            "pct_traces": float(r["pct_traces"]),
            "pct_count": float(r["pct_count"]),
            "move_type": (violation_profile.parse_pattern(r["group"]) or ("", ""))[1],
        }
        for _, r in profile.iterrows()
    ]

    # Distinct traces carrying at least one of the selected violations — not the
    # sum of the rows above, which double-counts a trace deviating more than
    # once.
    rows = violation_profile.labelled_rows(alignments, "pattern", violation_patterns)
    deviating = {int(i) for i in rows["trace_index"]} if not rows.empty else set()
    n_deviating = len(deviating)
    n_conformant = n_total - n_deviating

    return {
        "n_total":        n_total,
        "n_conformant":   n_conformant,
        "n_deviating":    n_deviating,
        "pct_conformant": n_conformant / n_total * 100 if n_total else 0.0,
        "pct_deviating":  n_deviating / n_total * 100 if n_total else 0.0,
        "violations":     violations,
    }


#: Colour per move type, so one violation keeps its colour across all six idioms.
_MOVE_COLORS = {
    "Model Move": GREY_DARK,
    "Log Move": GREY_MED,
    "Mismatch Move": GREY_LIGHT,
}


def _violation_colors(violations):
    return [_MOVE_COLORS.get(v["move_type"], GREY_LIGHTER) for v in violations]


def _top(violations, n=12):
    """The n most widespread violations; the rest would be unreadable rows."""
    return violations[:n]


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
    """KPI tiles: the log's deviating share, then the most widespread violations."""
    vio = _top(stats["violations"], 5)
    tiles = [("Traces with any violation", f"{stats['pct_deviating']:.1f}%",
              f"{stats['n_deviating']} of {stats['n_total']}", GREY_DARK)]
    for v in vio:
        tiles.append((v["label"], f"{v['pct_traces']:.1f}%",
                      f"{v['traces']} traces", _MOVE_COLORS.get(v["move_type"], GREY_LIGHTER)))

    n = len(tiles)
    fig, axes = plt.subplots(1, n, figsize=(max(8.0, n * 2.4), 3.4), squeeze=False)
    for ax, (label, big, small, color) in zip(axes[0], tiles):
        ax.axis("off")
        ax.add_patch(plt.Rectangle((0.02, 0.06), 0.96, 0.88, facecolor=color,
                                   edgecolor="white", linewidth=1.5,
                                   transform=ax.transAxes))
        txt = "white" if color in (GREY_DARK, GREY_MED) else "#222222"
        ax.text(0.5, 0.63, big, ha="center", va="center", transform=ax.transAxes,
                fontsize=19, fontweight="bold", color=txt)
        ax.text(0.5, 0.40, small, ha="center", va="center", transform=ax.transAxes,
                fontsize=FONT_ANNOT - 1, color=txt)
        ax.text(0.5, 0.22, _wrap(label), ha="center", va="center", transform=ax.transAxes,
                fontsize=FONT_ANNOT - 1, color=txt)
    fig.suptitle("Traces Containing Each Violation", fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    save_svg(fig, os.path.join(output_dir, "task12_tile_metric.svg"))


def task12_pie_chart(stats, output_dir):
    """Share of all violation *occurrences* per violation.

    Deliberately not the share of traces: a pie must partition a whole, and the
    per-violation trace shares overlap (one trace can carry several), so they
    sum past the share of traces that deviate at all. The title names the
    denominator so the two are not read as the same number.
    """
    vio = _top(stats["violations"], 10)
    if not vio:
        _save_empty(output_dir, "task12_pie_chart.svg", "No violations in this log.")
        return
    rest = 100.0 - sum(v["pct_count"] for v in vio)
    labels = [v["label"] for v in vio]
    sizes = [v["pct_count"] for v in vio]
    colors = _violation_colors(vio)
    if rest > 0.05:
        labels.append("Other violations"); sizes.append(rest); colors.append(GREY_LIGHTER)

    fig, ax = plt.subplots(figsize=(8.5, 6))
    wedges, _ = ax.pie(sizes, colors=colors, startangle=90, counterclock=False,
                       wedgeprops={"edgecolor": "white", "linewidth": 1.2})
    ax.axis("equal")
    ax.legend(wedges, [f"{l}  ({s:.1f}%)" for l, s in zip(labels, sizes)],
              loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False,
              fontsize=FONT_ANNOT - 1)
    ax.set_title("Share of All Violation Occurrences", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_pie_chart.svg"))


def task12_bar_chart(stats, output_dir):
    """One bar per violation: the percentage of traces that contain it."""
    vio = _top(stats["violations"])
    if not vio:
        _save_empty(output_dir, "task12_bar_chart.svg", "No violations in this log.")
        return
    labels = [v["label"] for v in vio]
    pct = [v["pct_traces"] for v in vio]
    y = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(9, max(3.5, len(labels) * 0.44 + 1.8)))
    ax.barh(y, pct, color=_violation_colors(vio), edgecolor="white")
    for yi, (p_, v) in enumerate(zip(pct, vio)):
        ax.text(p_ + max(pct) * 0.012, yi, f"{p_:.1f}%  ({v['traces']})",
                va="center", fontsize=FONT_ANNOT - 1, color="#333333")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
    ax.invert_yaxis()
    ax.set_xlim(0, max(pct) * 1.22)
    ax.set_xlabel("% of all traces containing this violation", fontsize=FONT_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5); ax.set_axisbelow(True)
    ax.set_title(f"Traces Containing Each Violation  "
                 f"({stats['pct_deviating']:.1f}% deviate at all)", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_bar_chart.svg"))


def task12_stacked_bar(stats, output_dir):
    """One 100% bar of all violation occurrences, segmented by violation.

    Occurrences, not traces, for the same reason as the pie: the trace shares
    overlap and would not fill the bar.
    """
    vio = _top(stats["violations"], 10)
    if not vio:
        _save_empty(output_dir, "task12_stacked_bar.svg", "No violations in this log.")
        return
    rest = 100.0 - sum(v["pct_count"] for v in vio)
    segs = [(v["label"], v["pct_count"], c) for v, c in zip(vio, _violation_colors(vio))]
    if rest > 0.05:
        segs.append(("Other violations", rest, GREY_LIGHTER))

    fig, ax = plt.subplots(figsize=(10, 3.2))
    left = 0.0
    for label, width, color in segs:
        ax.barh(0, width, left=left, height=0.55, color=color,
                edgecolor="white", linewidth=1.2, label=label)
        if width >= 4:
            ax.text(left + width / 2, 0, f"{width:.0f}%", ha="center", va="center",
                    fontsize=FONT_ANNOT - 1,
                    color="white" if color in (GREY_DARK, GREY_MED) else "#222222")
        left += width
    ax.set_xlim(0, 100); ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([]); ax.set_xlabel("% of all violation occurrences", fontsize=FONT_LABEL)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.35), ncol=3,
              frameon=False, fontsize=FONT_ANNOT - 2)
    ax.set_title("Composition of All Violation Occurrences", fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task12_stacked_bar.svg"))


def _violation_rows(stats):
    rows = [[v["label"], str(v["traces"]), f"{v['pct_traces']:.1f}%", f"{v['pct_count']:.1f}%"]
            for v in _top(stats["violations"])]
    if not rows:
        rows = [["(no violations)", "—", "—", "—"]]
    rows.append(["Any violation", str(stats["n_deviating"]),
                 f"{stats['pct_deviating']:.1f}%", "100.0%"])
    return rows


_TABLE_COLS = ["Violation", "Traces", "% of traces", "% of occurrences"]


def task12_table(stats, output_dir):
    """One row per violation: traces containing it, as a share of the log and of
    all violation occurrences."""
    rows = _violation_rows(stats)
    fig_h = max(3.4, 1.5 + len(rows) * 0.42)
    fig = plt.figure(figsize=(9.5, fig_h))
    ax = fig.add_subplot(111); ax.axis("off")
    make_table(ax, cell_text=rows, col_labels=_TABLE_COLS,
               bbox=[0.03, 0.02, 0.94, 0.86], font_size=9.5, cell_pad=0.09)
    fig.suptitle("Traces Containing Each Violation", fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, os.path.join(output_dir, "task12_table.svg"))


def task12_table_bar_chart(stats, output_dir):
    """Left: the same table. Right: the trace share as bars."""
    rows = _violation_rows(stats)
    vio = _top(stats["violations"])
    fig_h = max(3.8, 1.6 + len(rows) * 0.42)
    fig = plt.figure(figsize=(15, fig_h))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.25, 1.0], wspace=0.22)

    ax_t = fig.add_subplot(gs[0]); ax_t.axis("off")
    make_table(ax_t, cell_text=rows, col_labels=_TABLE_COLS,
               bbox=[0.02, 0.03, 0.96, 0.84], font_size=9, cell_pad=0.08)

    ax_b = fig.add_subplot(gs[1])
    if vio:
        y = np.arange(len(vio))
        pct = [v["pct_traces"] for v in vio]
        ax_b.barh(y, pct, color=_violation_colors(vio), edgecolor="white")
        ax_b.set_yticks(y)
        ax_b.set_yticklabels([v["label"] for v in vio], fontsize=FONT_ANNOT - 2)
        ax_b.invert_yaxis()
        ax_b.set_xlabel("% of all traces", fontsize=FONT_LABEL)
    else:
        ax_b.text(0.5, 0.5, "No violations", ha="center", va="center",
                  transform=ax_b.transAxes, fontsize=FONT_ANNOT)
    ax_b.spines[["top", "right"]].set_visible(False)
    ax_b.xaxis.grid(True, linestyle="--", alpha=0.5); ax_b.set_axisbelow(True)

    fig.suptitle("Traces Containing Each Violation", fontsize=FONT_TITLE, y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save_svg(fig, os.path.join(output_dir, "task12_table_bar_chart.svg"))


def generate(log, alignments, output_dir, violation_patterns=None, **kwargs):
    """Generate all Task 12 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 12 visualizations (Summarize process conformance) ---")

    if not alignments:
        logger.warning("      Skipped Task 12: no alignments provided.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task12_{name}.svg", "No alignment data available.")
        return

    stats = _extract_data(alignments, violation_patterns)

    task12_tile_metric(stats, output_dir)
    task12_pie_chart(stats, output_dir)
    task12_bar_chart(stats, output_dir)
    task12_stacked_bar(stats, output_dir)
    task12_table(stats, output_dir)
    task12_table_bar_chart(stats, output_dir)
