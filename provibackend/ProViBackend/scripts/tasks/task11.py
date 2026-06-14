"""
tasks/task11.py – Task 11: Summarize Guideline Violations
Goal: Describe · Means: Summarize · Characteristics: Guideline violations

Question: How often did a specific guideline violation occur?

Visualizations (all SVG, white-grey-black palette):
  bar_chart                     – per-activity total violation count
  pie_chart                     – violation type proportions
  heatmap                       – activity × type count with marginals + %
  table                         – Pareto ranked table with cumulative %
  table_bar_chart               – Pareto table + gradient bar chart
  stacked_bar                   – 100% normalized type distribution per activity
  flow_chart_elaborate_bpmn     – BPMN heatmap (frequency annotation)
  flow_chart_elaborate_bpmn_table – BPMN heatmap + Pareto table
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart", "pie_chart", "heatmap",
    "table", "table_bar_chart", "stacked_bar",
    "flow_chart_elaborate_bpmn", "flow_chart_elaborate_bpmn_table",
]

import os
import html as _html
import io as _io
import base64 as _base64
import re as _re
import xml.etree.ElementTree as _ET
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors

from shared import save_svg, FONT_TITLE, FONT_LABEL, FONT_ANNOT, classify_step as _classify_step

# ── Palette ───────────────────────────────────────────────────────────────────
_C_DARK   = "#222222"
_C_MED    = "#666666"
_C_LIGHT  = "#aaaaaa"
_C_XLIGHT = "#dddddd"
_HDR_BG   = "#333333"
_CMAP_SEQ = "Greys"

_VTYPES = ["Move on Model", "Move on Log", "Mismatch Move"]
_VTYPE_COLOR = {
    "Move on Model": _C_LIGHT,
    "Move on Log":   _C_MED,
    "Mismatch Move": _C_DARK,
}
_VTYPE_SHORT = {
    "Move on Model": "MoM",
    "Move on Log":   "MoL",
    "Mismatch Move": "MM",
}

_TOP_N = 12

# Accepts full names or short codes (MoM/MoL/MM) when parsing a target spec.
_VTYPE_FROM_TOKEN = {
    "mom": "Move on Model", "move on model": "Move on Model",
    "mol": "Move on Log",   "move on log":   "Move on Log",
    "mm":  "Mismatch Move", "mismatch move": "Mismatch Move",
}


# ── Target-violation selection ────────────────────────────────────────────────

def _resolve_target(target_violation, activity_type):
    """Normalise a target-violation spec to an (activity, vtype) key that exists in
    activity_type, or None if it cannot be matched.

    Accepts a 2-tuple/list (activity, move_type) or a string "activity|move_type"
    (also "activity::move_type"); the move_type may be a full name or a short code
    (MoM / MoL / MM).
    """
    if target_violation is None:
        return None
    if isinstance(target_violation, (tuple, list)) and len(target_violation) == 2:
        act, vt = str(target_violation[0]).strip(), str(target_violation[1]).strip()
    else:
        s = str(target_violation).strip()
        if "|" in s:
            act, vt = s.rsplit("|", 1)
        elif "::" in s:
            act, vt = s.rsplit("::", 1)
        else:
            return None
        act, vt = act.strip(), vt.strip()
    vt = _VTYPE_FROM_TOKEN.get(vt.lower(), vt)
    key = (act, vt)
    return key if key in activity_type else None


def _available_pairs_str(activity_type, limit=40):
    """Human-readable list of available (activity | move_type) pairs, most frequent first."""
    pairs = sorted(activity_type.items(), key=lambda kv: -kv[1])
    shown = ", ".join(f"({a} | {vt}: {c})" for (a, vt), c in pairs[:limit])
    more = "" if len(pairs) <= limit else f"  … (+{len(pairs) - limit} more)"
    return shown + more


def _focus_caption(target, target_count, target_pct):
    """Single-line caption naming the focus violation and its frequency / %."""
    if not target:
        return ""
    act, vt = target
    return (f"Focus violation:  {_short_label(act, 30)}  ·  {vt}   →   "
            f"{target_count:,} occurrences  ({target_pct:.1f}% of all violations)")


def _add_focus_caption(fig, target, target_count, target_pct):
    """Draw the focus caption along the bottom of a figure (no-op without a target)."""
    cap = _focus_caption(target, target_count, target_pct)
    if cap:
        fig.text(0.5, 0.012, cap, ha="center", va="bottom",
                 fontsize=FONT_ANNOT, color=_C_DARK, fontweight="bold")


# ── Data extraction (identical logic to task09) ───────────────────────────────

def _extract_data(alignments):
    """Returns (activity_type Counter, activity_totals Counter, type_totals Counter, n_violations int)."""
    activity_type = Counter()
    for aln in alignments:
        for step in aln.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            act, vtype = _classify_step(step[0], step[1])
            if act is None:
                continue
            activity_type[(act, vtype)] += 1

    activity_totals = Counter()
    type_totals     = Counter()
    for (act, vtype), cnt in activity_type.items():
        activity_totals[act]   += cnt
        type_totals[vtype]     += cnt
    return activity_type, activity_totals, type_totals, sum(activity_type.values())


def _top_activities(activity_totals, n=_TOP_N):
    return [act for act, _ in activity_totals.most_common(n)]


def _short_label(label, max_len=26):
    return label if len(label) <= max_len else label[:max_len - 1] + "…"


def _save_empty(output_dir, filename, message="No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


def _no_violations(output_dir, name):
    _save_empty(output_dir, f"task11_{name}.svg",
                "No guideline violations found in this log.")


# ── Idiom 1: Bar Chart — per-activity total violation count ───────────────────

def task11_bar_chart(activity_totals, n_violations, output_dir,
                     target=None, target_count=0, target_pct=0.0):
    """Horizontal bar per activity, sorted by total violations; the target
    violation's activity is highlighted and its frequency / % captioned."""
    if not activity_totals:
        _no_violations(output_dir, "bar_chart")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)
    # Make sure the focus activity is visible even if it falls outside the top-N.
    if target and target[0] not in top_acts:
        top_acts = top_acts + [target[0]]
    counts   = [activity_totals[a] for a in top_acts]
    pcts     = [c / n_violations * 100 if n_violations > 0 else 0 for c in counts]

    # Shade each bar by its relative rank: darker = more violations
    max_c = max(counts) if counts else 1
    shades = [str(round(1 - (c / max_c) * 0.72, 3)) for c in counts]

    n      = len(top_acts)
    fig_h  = max(3.5, n * 0.55 + 2.0)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.set_facecolor("#fafbfc")

    for i, (act, cnt, pct, shade) in enumerate(zip(top_acts, counts, pcts, shades)):
        is_target = bool(target and act == target[0])
        ax.barh(i, cnt, color=shade,
                edgecolor=(_C_DARK if is_target else "white"),
                linewidth=(2.6 if is_target else 0.6), height=0.65)
        ax.text(cnt + max_c * 0.012, i,
                f"{cnt:,}  ({pct:.1f}%)" + ("  ◀ focus" if is_target else ""),
                va="center", fontsize=FONT_ANNOT,
                color=_C_DARK, fontweight=("bold" if is_target else "normal"))

    ax.set_yticks(range(n))
    ax.set_yticklabels([_short_label(a, 32) for a in top_acts], fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Number of violations", fontsize=FONT_LABEL)
    ax.set_title(
        f"Guideline Violation Frequency by Activity  (top {n})\n"
        f"{n_violations:,} total violations across all activities",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max_c * 1.32)

    _add_focus_caption(fig, target, target_count, target_pct)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task11_bar_chart.svg"))


# ── Idiom 2: Pie Chart — violation type proportions ───────────────────────────

def task11_pie_chart(type_totals, n_violations, output_dir,
                     target=None, target_count=0, target_pct=0.0):
    """2-slice pie: the focus violation vs. all other violations — directly showing
    what share of all violations the target accounts for."""
    if not n_violations:
        _no_violations(output_dir, "pie_chart")
        return
    if not target:
        # No focus selected (no violations): fall back to a type breakdown.
        types  = [t for t in _VTYPES if type_totals.get(t, 0) > 0]
        if not types:
            _no_violations(output_dir, "pie_chart")
            return
        counts = [type_totals[t] for t in types]
        colors = [_VTYPE_COLOR[t] for t in types]
        labels = types
    else:
        act, vt = target
        other = max(n_violations - target_count, 0)
        counts = [target_count, other]
        colors = [_C_DARK, _C_XLIGHT]
        labels = [f"{_short_label(act, 22)} · {_VTYPE_SHORT.get(vt, vt)}",
                  "All other violations"]

    def _autopct(pct):
        cnt = int(round(pct / 100 * n_violations))
        return f"{pct:.1f}%\n({cnt:,})"

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, _texts, autotexts = ax.pie(
        counts,
        labels=None,
        colors=colors,
        autopct=_autopct,
        startangle=140,
        pctdistance=0.72,
        explode=([0.06, 0.0] if target else None),
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for atext, clr in zip(autotexts, colors):
        atext.set_fontsize(FONT_ANNOT)
        r = int(clr[1:3], 16)
        atext.set_color("white" if r < 150 else _C_DARK)

    ax.legend(
        wedges, [f"{lbl}  ({c:,})" for lbl, c in zip(labels, counts)],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
        fontsize=FONT_ANNOT,
        frameon=True, framealpha=0.9,
        ncol=min(len(labels), 2),
    )
    title = ("Focus Violation vs. All Other Violations"
             if target else "Guideline Violations by Type")
    ax.set_title(f"{title}\n{n_violations:,} total violations",
                 fontsize=FONT_TITLE, pad=16)
    _add_focus_caption(fig, target, target_count, target_pct)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task11_pie_chart.svg"))


# ── Idiom 3: Heatmap — activity × type with marginal totals ──────────────────

def task11_heatmap(activity_type, activity_totals, type_totals, n_violations, output_dir,
                   target=None, target_count=0, target_pct=0.0):
    """Activity × violation-type heatmap (colour = count) with row/column marginal
    totals; the target (activity, move_type) cell is boxed. Cells carry no numbers,
    matching the other tasks' heatmaps."""
    if not activity_totals:
        _no_violations(output_dir, "heatmap")
        return

    top_acts    = _top_activities(activity_totals, _TOP_N)
    if target and target[0] not in top_acts:
        top_acts = top_acts + [target[0]]
    short_labels = [_short_label(a, 30) for a in top_acts]
    n           = len(top_acts)

    # Core matrix (activities × types)
    mat = np.array([
        [activity_type.get((a, vt), 0) for vt in _VTYPES]
        for a in top_acts
    ], dtype=float)

    row_totals = mat.sum(axis=1)
    col_totals = mat.sum(axis=0)

    fig_h  = max(4.5, n * 0.62 + 2.5)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    ax.set_facecolor("#fafbfc")

    vmax = mat.max() if mat.max() > 0 else 1
    im   = ax.imshow(mat, cmap=_CMAP_SEQ, aspect="auto",
                     norm=mcolors.PowerNorm(gamma=0.5, vmin=0, vmax=vmax))

    ax.set_xticks(range(len(_VTYPES)))
    ax.set_xticklabels(_VTYPES, fontsize=FONT_LABEL)
    ax.set_yticks(range(n))
    ax.set_yticklabels(short_labels, fontsize=FONT_ANNOT)

    # Cells are not annotated with numbers, for consistency with the heatmaps in
    # the other tasks — colour intensity encodes the count, marginals give totals,
    # and the focus cell is boxed below.

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cbar.set_label("Violation count", fontsize=FONT_ANNOT)
    cbar.outline.set_visible(False)

    # Right-side row totals annotation
    for i, rt in enumerate(row_totals):
        pct = rt / n_violations * 100 if n_violations > 0 else 0
        ax.text(len(_VTYPES) + 0.08, i,
                f"  {int(rt):,}  ({pct:.1f}%)",
                va="center", fontsize=FONT_ANNOT - 1, color=_C_MED)

    # Column totals at bottom
    ax.text(-0.6, n + 0.12, "Total:", fontsize=FONT_ANNOT - 1,
            color=_C_MED, va="top", transform=ax.transData)
    for j, ct in enumerate(col_totals):
        pct = ct / n_violations * 100 if n_violations > 0 else 0
        ax.text(j, n + 0.12, f"{int(ct):,}\n({pct:.1f}%)",
                ha="center", va="top",
                fontsize=FONT_ANNOT - 1, color=_C_MED)

    # The focus cell is named in the caption below; no in-cell frame (it cluttered
    # the heatmap). The focus violation's count/% is carried by the caption.

    ax.set_xlim(-0.5, len(_VTYPES) - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_title(
        f"Violation Frequency: Activity × Type  (top {n})\n"
        f"Colour = violation count  ·  row/column totals at the margins",
        fontsize=FONT_TITLE,
    )
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    _add_focus_caption(fig, target, target_count, target_pct)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task11_heatmap.svg"))


# ── Idiom 4: Table — Pareto ranked table with cumulative % ───────────────────

def task11_table(activity_totals, type_totals, n_violations, output_dir,
                 target=None, target_count=0, target_pct=0.0):
    """Ranked table: Rank | Activity | MoM | MoL | MM | Total | %Total | Cum%.
    The target violation's activity row is highlighted."""
    if not activity_totals:
        _no_violations(output_dir, "table")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)
    if target and target[0] not in top_acts:
        top_acts = top_acts + [target[0]]
    target_row_idx = top_acts.index(target[0]) if target and target[0] in top_acts else -1
    rows     = []
    cum      = 0.0
    for rank, act in enumerate(top_acts, 1):
        total = activity_totals[act]
        pct   = total / n_violations * 100 if n_violations > 0 else 0
        cum  += pct
        rows.append([str(rank), _short_label(act, 30),
                     total, f"{pct:.1f}%", f"{cum:.1f}%"])

    col_headers = ["#", "Activity", "Total Violations", "% of All", "Cumulative %"]
    col_widths  = [0.05, 0.42, 0.20, 0.15, 0.15]

    n_rows = len(rows)
    fig_h  = max(3.5, n_rows * 0.50 + 2.2)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")

    t     = 0.94
    b     = 0.06
    l     = 0.02
    tw    = 0.96
    row_h = (t - b) / (n_rows + 1)

    x = l
    for hdr, cw in zip(col_headers, col_widths):
        ax.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                   fc=_HDR_BG, ec="#333333", linewidth=0.5,
                                   transform=ax.transAxes, clip_on=False))
        ax.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                ha="center", va="center", fontsize=FONT_ANNOT,
                color="white", fontweight="bold", transform=ax.transAxes)
        x += cw * tw

    for i, row in enumerate(rows):
        y_top = t - (i + 2) * row_h
        x     = l
        is_target_row = (i == target_row_idx)
        bg    = "#cfcfcf" if is_target_row else ("#f5f5f5" if i % 2 == 0 else "white")
        # Highlight the cumulative column when it crosses 50% / 80%
        cum_val = float(row[-1].replace("%", ""))
        for j, (val, cw) in enumerate(zip(row, col_widths)):
            cell_bg = bg
            if j == 4 and not is_target_row:  # Cumulative %
                if cum_val <= 50.0:
                    cell_bg = "#e8e8e8"
                elif cum_val <= 80.0:
                    cell_bg = "#f0f0f0"
            ax.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                       fc=cell_bg,
                                       ec=(_C_DARK if is_target_row else "#cccccc"),
                                       linewidth=(1.4 if is_target_row else 0.6),
                                       transform=ax.transAxes, clip_on=False))
            ha = "left" if j == 1 else "center"
            px = x + 0.008 if j == 1 else x + cw * tw * 0.5
            ax.text(px, y_top + row_h * 0.5, str(val),
                    ha=ha, va="center", fontsize=FONT_ANNOT,
                    color=_C_DARK, fontweight=("bold" if is_target_row else "normal"),
                    transform=ax.transAxes)
            x += cw * tw

    # Footer: type totals
    footer_y = b - 0.01
    type_summary = "  ·  ".join(
        f"{_VTYPE_SHORT[vt]}: {type_totals.get(vt, 0):,}"
        for vt in _VTYPES if type_totals.get(vt, 0) > 0
    )
    ax.text(l, footer_y,
            f"Total: {n_violations:,} violations  ({type_summary})",
            ha="left", va="top", fontsize=FONT_ANNOT - 1,
            color=_C_MED, transform=ax.transAxes)

    ax.set_title(
        f"Guideline Violation Frequency — Pareto Ranking  (top {n_rows})",
        fontsize=FONT_TITLE, pad=14,
    )
    _add_focus_caption(fig, target, target_count, target_pct)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task11_table.svg"))


# ── Idiom 5: Table & Bar Chart — Pareto table + gradient horizontal bars ──────

def task11_table_bar_chart(activity_totals, type_totals, n_violations, output_dir,
                           target=None, target_count=0, target_pct=0.0):
    """Left: compact Pareto table. Right: gradient horizontal bars sorted by count.
    The target violation's activity row and bar are highlighted."""
    if not activity_totals:
        _no_violations(output_dir, "table_bar_chart")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)
    if target and target[0] not in top_acts:
        top_acts = top_acts + [target[0]]
    target_row_idx = top_acts.index(target[0]) if target and target[0] in top_acts else -1
    counts   = [activity_totals[a] for a in top_acts]
    n        = len(top_acts)
    max_c    = max(counts) if counts else 1

    cum  = 0.0
    rows = []
    for act, cnt in zip(top_acts, counts):
        pct  = cnt / n_violations * 100 if n_violations > 0 else 0
        cum += pct
        rows.append([_short_label(act, 22), f"{cnt:,}", f"{pct:.1f}%", f"{cum:.1f}%"])

    fig, (ax_tbl, ax_bar) = plt.subplots(
        1, 2, figsize=(16, max(4.0, n * 0.60 + 2.5)),
        gridspec_kw={"width_ratios": [3, 4]},
    )

    # ── Left: table ──────────────────────────────────────────────────────────
    ax_tbl.axis("off")
    col_headers = ["Activity", "Count", "% of All", "Cum%"]
    col_widths  = [0.48, 0.18, 0.18, 0.16]
    t     = 0.94
    row_h = (t - 0.04) / (n + 1)
    tw    = 0.97
    x     = 0.015

    for hdr, cw in zip(col_headers, col_widths):
        ax_tbl.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                       fc=_HDR_BG, ec="white", linewidth=0.5,
                                       transform=ax_tbl.transAxes, clip_on=False))
        ax_tbl.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                    ha="center", va="center", fontsize=FONT_ANNOT,
                    color="white", fontweight="bold", transform=ax_tbl.transAxes)
        x += cw * tw

    for i, row in enumerate(rows):
        y_top = t - (i + 2) * row_h
        x     = 0.015
        is_target_row = (i == target_row_idx)
        bg    = "#cfcfcf" if is_target_row else ("#f5f5f5" if i % 2 == 0 else "white")
        for j, (val, cw) in enumerate(zip(row, col_widths)):
            ax_tbl.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg,
                                           ec=(_C_DARK if is_target_row else "#cccccc"),
                                           linewidth=(1.4 if is_target_row else 0.6),
                                           transform=ax_tbl.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            ax_tbl.text(px, y_top + row_h * 0.5, str(val),
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, fontweight=("bold" if is_target_row else "normal"),
                        transform=ax_tbl.transAxes)
            x += cw * tw

    # ── Right: gradient bars (darker = more violations) ───────────────────────
    ax_bar.set_facecolor("#fafbfc")
    for i, (act, cnt) in enumerate(zip(top_acts, counts)):
        shade = str(round(1 - (cnt / max_c) * 0.72, 3))
        is_target_row = (i == target_row_idx)
        ax_bar.barh(i, cnt, color=shade,
                    edgecolor=(_C_DARK if is_target_row else "white"),
                    linewidth=(2.6 if is_target_row else 0.6), height=0.65)
        ax_bar.text(cnt + max_c * 0.012, i,
                    f"{cnt:,}" + ("  ◀ focus" if is_target_row else ""),
                    va="center", fontsize=FONT_ANNOT, color=_C_DARK,
                    fontweight=("bold" if is_target_row else "normal"))

    ax_bar.set_yticks(range(n))
    ax_bar.set_yticklabels([_short_label(a, 24) for a in top_acts], fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Violation count", fontsize=FONT_LABEL)
    ax_bar.set_title("Frequency  (darker = more violations)", fontsize=FONT_TITLE)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax_bar.set_axisbelow(True)
    ax_bar.set_xlim(0, max_c * 1.30)

    fig.suptitle(
        f"Violation Frequency Ranking  (top {n})  ·  {n_violations:,} total violations",
        fontsize=FONT_TITLE + 1, y=1.01,
    )
    _add_focus_caption(fig, target, target_count, target_pct)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task11_table_bar_chart.svg"))


# ── Idiom 6: Stacked Bar — 100% normalized type distribution ─────────────────

def task11_stacked_bar(activity_type, activity_totals, output_dir,
                       target=None, target_count=0, target_pct=0.0):
    """100% normalized stacked bar: type proportion within each activity.
    The target violation's segment (activity row × move_type) is outlined."""
    if not activity_totals:
        _no_violations(output_dir, "stacked_bar")
        return

    top_acts     = _top_activities(activity_totals, _TOP_N)
    if target and target[0] not in top_acts:
        top_acts = top_acts + [target[0]]
    target_row_idx = top_acts.index(target[0]) if target and target[0] in top_acts else -1
    short_labels = [_short_label(a, 30) for a in top_acts]
    n            = len(top_acts)

    # Compute proportions
    fracs = {vt: [] for vt in _VTYPES}
    for act in top_acts:
        total = activity_totals[act]
        for vt in _VTYPES:
            cnt = activity_type.get((act, vt), 0)
            fracs[vt].append(cnt / total * 100 if total > 0 else 0)

    fig_h  = max(4, n * 0.62 + 2.2)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.set_facecolor("#fafbfc")

    lefts = np.zeros(n)
    for vt in _VTYPES:
        vals = np.array(fracs[vt])
        bars = ax.barh(range(n), vals, left=lefts,
                       color=_VTYPE_COLOR[vt], label=vt,
                       edgecolor="white", linewidth=0.5, height=0.65)
        # Annotate segments > 8%; outline the focus segment
        for i, (bar, pct) in enumerate(zip(bars, vals)):
            if target and vt == target[1] and i == target_row_idx:
                bar.set_edgecolor(_C_DARK)
                bar.set_linewidth(2.6)
                bar.set_zorder(5)
            if pct > 8:
                cx = bar.get_x() + bar.get_width() / 2
                bv = int(_VTYPE_COLOR[vt][1:3], 16)
                tc = "white" if bv < 150 else _C_DARK
                # zorder above the (possibly raised) focus bar so the % stays visible
                ax.text(cx, i, f"{pct:.0f}%",
                        ha="center", va="center",
                        fontsize=max(FONT_ANNOT - 1, 6.5), color=tc, zorder=6)
        lefts += vals

    ax.set_yticks(range(n))
    ax.set_yticklabels(short_labels, fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Proportion of violations (%)", fontsize=FONT_LABEL)
    ax.set_xlim(0, 100)
    ax.set_title(
        f"Violation Type Distribution per Activity  (top {n})\n"
        "Each bar = 100%  ·  segments show proportion of each violation type",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.25),
        ncol=3,
        fontsize=FONT_ANNOT,
        frameon=True,
        framealpha=0.9,
    )

    _add_focus_caption(fig, target, target_count, target_pct)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task11_stacked_bar.svg"))


# ── BPMN helpers (imported from task09) ──────────────────────────────────────

def _import_task09_bpmn():
    try:
        from tasks.task09 import _make_bpmn_violation_svg, _violation_shade, _short_label as _sl09
    except ImportError:
        from task09 import _make_bpmn_violation_svg, _violation_shade, _short_label as _sl09
    return _make_bpmn_violation_svg, _violation_shade


def _svg_dims(svg_str):
    m = _re.search(r'<svg[^>]*\bwidth="([^"]+)"[^>]*\bheight="([^"]+)"', svg_str)
    if m:
        w = float(_re.sub(r"[^\d.]", "", m.group(1)))
        h = float(_re.sub(r"[^\d.]", "", m.group(2)))
        return w, h
    return None, None


# ── Idiom 7: Flow Chart Elaborate BPMN ───────────────────────────────────────

def task11_flow_chart_elaborate_bpmn(activity_totals, model_path, output_dir):
    if model_path is None:
        _save_empty(output_dir, "task11_flow_chart_elaborate_bpmn.svg",
                    "No process model provided — Flow+ requires a BPMN file.")
        return
    if not activity_totals:
        _no_violations(output_dir, "flow_chart_elaborate_bpmn")
        return
    try:
        _make_bpmn_violation_svg, _ = _import_task09_bpmn()
    except Exception:
        _save_empty(output_dir, "task11_flow_chart_elaborate_bpmn.svg",
                    "Could not load BPMN helpers from task09.")
        return
    svg = _make_bpmn_violation_svg(activity_totals, model_path)
    if svg is None:
        _save_empty(output_dir, "task11_flow_chart_elaborate_bpmn.svg",
                    "Could not parse process model.")
        return
    path = os.path.join(output_dir, "task11_flow_chart_elaborate_bpmn.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ── Idiom 8: Flow Chart Elaborate BPMN & Table ────────────────────────────────

def task11_flow_chart_elaborate_bpmn_table(activity_totals, type_totals, n_violations, model_path, output_dir,
                                           target=None, target_count=0, target_pct=0.0):
    """Composite SVG: BPMN heatmap (top) + Pareto table (bottom).
    The table title names the focus violation and its frequency / %."""
    if not activity_totals:
        _no_violations(output_dir, "flow_chart_elaborate_bpmn_table")
        return

    # ── Pareto table SVG ──────────────────────────────────────────────────────
    top_acts = _top_activities(activity_totals, _TOP_N)
    n_rows   = len(top_acts)
    tbl_w_in = 14.0
    tbl_h_in = max(3.5, n_rows * 0.48 + 2.0)
    tbl_fig, tbl_ax = plt.subplots(figsize=(tbl_w_in, tbl_h_in))
    tbl_ax.axis("off")

    col_headers = ["#", "Activity", "Total Violations", "% of All", "Cumulative %"]
    col_widths  = [0.05, 0.42, 0.20, 0.15, 0.15]
    t     = 0.94
    l     = 0.02
    tw    = 0.96
    row_h = (t - 0.06) / (n_rows + 1)
    x     = l

    for hdr, cw in zip(col_headers, col_widths):
        tbl_ax.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                       fc=_HDR_BG, ec="white", linewidth=0.5,
                                       transform=tbl_ax.transAxes, clip_on=False))
        tbl_ax.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                    ha="center", va="center", fontsize=FONT_ANNOT,
                    color="white", fontweight="bold", transform=tbl_ax.transAxes)
        x += cw * tw

    cum = 0.0
    for i, act in enumerate(top_acts):
        total = activity_totals[act]
        pct   = total / n_violations * 100 if n_violations > 0 else 0
        cum  += pct
        row_vals = [str(i + 1), _short_label(act, 32),
                    f"{total:,}", f"{pct:.1f}%", f"{cum:.1f}%"]
        y_top = t - (i + 2) * row_h
        x     = l
        bg    = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(zip(row_vals, col_widths)):
            tbl_ax.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg, ec="#eeeeee", linewidth=0.4,
                                           transform=tbl_ax.transAxes, clip_on=False))
            ha = "left" if j == 1 else "center"
            px = x + 0.008 if j == 1 else x + cw * tw * 0.5
            tbl_ax.text(px, y_top + row_h * 0.5, str(val),
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, transform=tbl_ax.transAxes)
            x += cw * tw

    type_summary = "  ·  ".join(
        f"{_VTYPE_SHORT[vt]}: {type_totals.get(vt, 0):,}"
        for vt in _VTYPES if type_totals.get(vt, 0) > 0
    )
    _title = f"Violation Frequency Ranking  (top {n_rows})  ·  {n_violations:,} total  ({type_summary})"
    _cap = _focus_caption(target, target_count, target_pct)
    if _cap:
        _title += "\n" + _cap
    tbl_ax.set_title(_title, fontsize=FONT_TITLE, pad=14)
    tbl_fig.tight_layout()

    buf = _io.BytesIO()
    tbl_fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(tbl_fig)
    buf.seek(0)
    tbl_svg_str = buf.read().decode("utf-8")
    tbl_w, tbl_h = _svg_dims(tbl_svg_str)
    if tbl_w is None:
        tbl_w, tbl_h = tbl_w_in * 72, tbl_h_in * 72

    # ── BPMN SVG ──────────────────────────────────────────────────────────────
    bpmn_svg = None
    if model_path is not None:
        try:
            _make_bpmn_violation_svg, _ = _import_task09_bpmn()
            bpmn_svg = _make_bpmn_violation_svg(activity_totals, model_path)
        except Exception:
            pass

    if bpmn_svg is None:
        path = os.path.join(output_dir, "task11_flow_chart_elaborate_bpmn_table.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(tbl_svg_str)
        return

    bpmn_w, bpmn_h = _svg_dims(bpmn_svg)
    if bpmn_w is None:
        bpmn_w, bpmn_h = 800.0, 600.0

    tbl_scale = bpmn_w / tbl_w
    tbl_h_scl = tbl_h * tbl_scale
    total_h   = bpmn_h + tbl_h_scl

    b64_bpmn = _base64.b64encode(bpmn_svg.encode()).decode()
    b64_tbl  = _base64.b64encode(tbl_svg_str.encode()).decode()

    composite = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        f'     width="{bpmn_w:.1f}" height="{total_h:.1f}" viewBox="0 0 {bpmn_w:.1f} {total_h:.1f}">',
        '  <rect width="100%" height="100%" fill="white"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_bpmn}"',
        f'         x="0" y="0" width="{bpmn_w:.1f}" height="{bpmn_h:.1f}"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_tbl}"',
        f'         x="0" y="{bpmn_h:.1f}" width="{bpmn_w:.1f}" height="{tbl_h_scl:.1f}"/>',
        '</svg>',
    ])
    path = os.path.join(output_dir, "task11_flow_chart_elaborate_bpmn_table.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(composite)


# ── Public entry point ────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None, target_violation=None):
    """Generate all Task 11 SVGs into output_dir.

    target_violation: the specific guideline violation to focus on, as an
    (activity, move_type) pair or "activity|move_type" string (move_type may be a
    full name or a short code MoM/MoL/MM). When omitted, the most frequent
    violation in the log is auto-selected (and logged). Every idiom then displays
    that violation's frequency / % of all violations. If the specified violation
    is absent from the log, a clear error lists the available pairs and empty-state
    SVGs are written instead of crashing.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 11 visualizations (Summarize guideline violations) ---")

    activity_type, activity_totals, type_totals, n_violations = _extract_data(alignments)

    if not activity_totals:
        logger.warning("      Skipped Task 11: no violations found in alignments.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task11_{name}.svg",
                        "No guideline violations found in this log.")
        return

    # Resolve the focus (target) violation.
    if target_violation is not None:
        target = _resolve_target(target_violation, activity_type)
        if target is None:
            logger.error(
                f"      task11: target violation '{target_violation}' not found in the log. "
                f"Available (activity | move_type) pairs: "
                f"{_available_pairs_str(activity_type)}"
            )
            for name in IDIOMS:
                _save_empty(output_dir, f"task11_{name}.svg",
                            f"Target violation '{target_violation}' not found in this log.")
            return
    else:
        target = max(activity_type.items(), key=lambda kv: kv[1])[0]
        logger.info(
            f"      task11: no target violation specified — auto-selected most frequent: "
            f"({target[0]} | {target[1]}) with {activity_type[target]} occurrence(s)."
        )

    target_count = activity_type.get(target, 0)
    target_pct = target_count / n_violations * 100 if n_violations else 0.0
    logger.info(f"      -> Focus violation: ({target[0]} | {target[1]})  "
                f"{target_count} occ.  ({target_pct:.1f}% of {n_violations} total)")

    task11_bar_chart(activity_totals, n_violations, output_dir, target, target_count, target_pct)
    task11_pie_chart(type_totals, n_violations, output_dir, target, target_count, target_pct)
    task11_heatmap(activity_type, activity_totals, type_totals, n_violations, output_dir,
                   target, target_count, target_pct)
    task11_table(activity_totals, type_totals, n_violations, output_dir,
                 target, target_count, target_pct)
    task11_table_bar_chart(activity_totals, type_totals, n_violations, output_dir,
                           target, target_count, target_pct)
    task11_stacked_bar(activity_type, activity_totals, output_dir,
                       target, target_count, target_pct)
    task11_flow_chart_elaborate_bpmn(activity_totals, model_path, output_dir)
    task11_flow_chart_elaborate_bpmn_table(activity_totals, type_totals, n_violations, model_path, output_dir,
                                           target, target_count, target_pct)
