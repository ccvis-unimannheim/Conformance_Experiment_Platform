"""
tasks/task09.py – Task 9: Identify Guideline Violations
Goal: Describe · Means: Identify · Characteristics: Guideline violations

Question: How exactly does the process execution differ from the guidelines?
          Which activities are responsible, and what violation type occurs?

Visualizations (all SVG, white-grey-black palette):
  bar_chart       – violation type frequency
  stacked_bar     – per-activity stacked bar by violation type
  scatter_plot    – Move-on-Model vs Move-on-Log count per activity
  table           – per-activity violation breakdown
  table_bar_chart – table + stacked bar (side by side)
  matrix          – activity × violation-type count heatmap
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart", "stacked_bar", "scatter_plot",
    "table", "table_bar_chart", "matrix",
    "flow_chart_basic", "flow_chart_and_table",
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
import matplotlib.cm as cm

from shared import save_svg, GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER, CIVIDIS, CIVIDIS_R, FONT_TITLE, FONT_LABEL, FONT_ANNOT, classify_step as _classify_step

# ── Cividis palette ───────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK
_C_MED    = GREY_MED
_C_LIGHT  = GREY_LIGHT
_C_XLIGHT = GREY_LIGHTER
_HDR_BG   = GREY_DARK
_CMAP_SEQ = CIVIDIS

# Violation type → grey shade (light=skipped, mid=extra, dark=mismatch)
_VTYPES = ["Move on Model", "Move on Log", "Mismatch Move"]
_VTYPE_COLOR = {
    "Move on Model": _C_LIGHT,
    "Move on Log":   _C_MED,
    "Mismatch Move": _C_DARK,
}

_TOP_N = 12   # max activities displayed


# ── Data extraction ───────────────────────────────────────────────────────────

def _extract_data(alignments):
    """
    Returns:
        activity_type  : Counter[(activity, vtype)] → count
        activity_totals: Counter[activity] → total violations
        type_totals    : Counter[vtype] → total violations
        n_violations   : int
    """
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
    type_totals = Counter()
    for (act, vtype), cnt in activity_type.items():
        activity_totals[act] += cnt
        type_totals[vtype] += cnt

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
    _save_empty(output_dir, f"task09_{name}.svg",
                "No guideline violations found in this log.")


# ── Idiom 1: Bar Chart ────────────────────────────────────────────────────────

def task09_bar_chart(type_totals, n_violations, output_dir):
    if not type_totals:
        _no_violations(output_dir, "bar_chart")
        return

    types  = [t for t in _VTYPES if type_totals[t] > 0]
    counts = [type_totals[t] for t in types]
    colors = [_VTYPE_COLOR[t] for t in types]
    pcts   = [c / n_violations * 100 for c in counts]

    fig, ax = plt.subplots(figsize=(10, max(3, len(types) * 1.4 + 1.5)))
    ax.set_facecolor("#fafbfc")

    bars = ax.barh(range(len(types)), counts, color=colors,
                   edgecolor="white", linewidth=0.8, height=0.55)

    for i, (bar, cnt, pct) in enumerate(zip(bars, counts, pcts)):
        ax.text(bar.get_width() + max(counts) * 0.015, i,
                f"{cnt:,}  ({pct:.1f}%)",
                va="center", fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_yticks(range(len(types)))
    ax.set_yticklabels(types, fontsize=FONT_ANNOT)
    ax.set_xlabel("Number of violations", fontsize=FONT_LABEL)
    ax.set_title("Guideline Violations by Type", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(counts) * 1.3)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task09_bar_chart.svg"))


# ── Idiom 2: Stacked Bar ──────────────────────────────────────────────────────

def task09_stacked_bar(activity_type, activity_totals, output_dir):
    if not activity_totals:
        _no_violations(output_dir, "stacked_bar")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)
    short_labels = [_short_label(a, 30) for a in top_acts]

    fig, ax = plt.subplots(figsize=(13, max(4, len(top_acts) * 0.6 + 2)))
    ax.set_facecolor("#fafbfc")

    lefts = np.zeros(len(top_acts))
    for vtype in _VTYPES:
        vals = np.array([activity_type.get((a, vtype), 0) for a in top_acts], dtype=float)
        ax.barh(range(len(top_acts)), vals, left=lefts,
                color=_VTYPE_COLOR[vtype], label=vtype,
                edgecolor="white", linewidth=0.5, height=0.65)
        lefts += vals

    ax.set_yticks(range(len(top_acts)))
    ax.set_yticklabels(short_labels, fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Number of violations", fontsize=FONT_LABEL)
    ax.set_title(f"Violations per Activity by Type  (top {len(top_acts)})",
                 fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task09_stacked_bar.svg"))


# ── Idiom 3: Scatter Plot ─────────────────────────────────────────────────────

def task09_scatter_plot(activity_type, activity_totals, output_dir):
    """X = Move-on-Model count (skipped), Y = Move-on-Log count (extra).
    Each point = one activity. Size = total violations. Color = dominant type.
    Position reveals whether an activity is predominantly skipped or inserted.
    """
    if not activity_totals:
        _no_violations(output_dir, "scatter_plot")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)

    mom = np.array([activity_type.get((a, "Move on Model"), 0) for a in top_acts], dtype=float)
    mol = np.array([activity_type.get((a, "Move on Log"),   0) for a in top_acts], dtype=float)
    mm  = np.array([activity_type.get((a, "Mismatch Move"), 0) for a in top_acts], dtype=float)
    totals = mom + mol + mm

    max_total = max(totals) if totals.max() > 0 else 1
    sizes = (totals / max_total * 600 + 80).tolist()

    def _dominant_color(i):
        vals  = [mom[i], mol[i], mm[i]]
        types = ["Move on Model", "Move on Log", "Mismatch Move"]
        return _VTYPE_COLOR[types[int(np.argmax(vals))]]

    colors = [_dominant_color(i) for i in range(len(top_acts))]

    fig, ax = plt.subplots(figsize=(11, 8))
    ax.set_facecolor("#fafbfc")

    ax.scatter(mom, mol, s=sizes, c=colors, alpha=0.85,
               edgecolors="white", linewidths=0.8, zorder=3)

    # Diagonal: equal MoM = MoL
    lim = max(mom.max(), mol.max()) * 1.18 + 1
    ax.plot([0, lim], [0, lim], color=_C_XLIGHT, linewidth=1.0,
            linestyle="--", zorder=1)
    ax.text(lim * 0.97, lim * 0.97, "MoM = MoL",
            ha="right", va="bottom", fontsize=FONT_ANNOT - 1, color=_C_LIGHT)

    # Labels: use adjustText for automatic overlap prevention.
    # Falls back to centroid-offset placement if adjustText is not installed.
    top_idx = np.argsort(-totals)[:8]

    texts = []
    for i in top_idx:
        t = ax.text(
            mom[i], mol[i], _short_label(top_acts[i], 22),
            fontsize=max(FONT_ANNOT - 1, 6), color=_C_DARK,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.88),
        )
        texts.append(t)

    try:
        from adjustText import adjust_text
        adjust_text(
            texts,
            x=mom, y=mol,
            arrowprops=dict(arrowstyle="-", color="#bbbbbb", lw=0.6),
            expand=(1.6, 1.8),
            force_text=(0.4, 0.6),
            force_points=(0.2, 0.3),
        )
    except ImportError:
        # Fallback: centroid-based offset with perpendicular collision nudge
        cx, cy = mom.mean(), mol.mean()
        label_info = []
        for i, t in zip(top_idx, texts):
            dx, dy = mom[i] - cx, mol[i] - cy
            mag = max(np.hypot(dx, dy), 1e-6)
            label_info.append((np.arctan2(dy, dx), i, dx / mag, dy / mag, t))
        label_info.sort()
        used = []
        for angle, i, nx, ny, t in label_info:
            ox, oy = nx * 36, ny * 36
            for px, py in used:
                if np.hypot(ox - px, oy - py) < 48:
                    ox += -ny * 24
                    oy +=  nx * 24
                    break
            used.append((ox, oy))
            t.set_position((mom[i] + ox * 0.01, mol[i] + oy * 0.01))

    ax.set_xlabel("Move on Model count  (activity skipped in log)", fontsize=FONT_LABEL)
    ax.set_ylabel("Move on Log count  (activity inserted in log)", fontsize=FONT_LABEL)
    ax.set_title(
        "Violation Profile per Activity\n"
        "(size = total violations · color = dominant violation type)",
        fontsize=FONT_TITLE,
    )
    ax.set_xlim(-0.5, lim)
    ax.set_ylim(-0.5, lim)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)

    legend_handles = [mpatches.Patch(color=_VTYPE_COLOR[t], label=t) for t in _VTYPES]
    # Upper-right: no data points in that region — legend safe here
    ax.legend(handles=legend_handles, fontsize=FONT_ANNOT,
              frameon=True, framealpha=0.9, loc="upper right")

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task09_scatter_plot.svg"))


# ── Idiom 4: Table ────────────────────────────────────────────────────────────

def task09_table(activity_type, activity_totals, type_totals, n_violations, output_dir):
    if not activity_totals:
        _no_violations(output_dir, "table")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)

    rows = []
    for a in top_acts:
        mom   = activity_type.get((a, "Move on Model"), 0)
        mol   = activity_type.get((a, "Move on Log"),   0)
        mm    = activity_type.get((a, "Mismatch Move"), 0)
        total = mom + mol + mm
        pct   = total / n_violations * 100 if n_violations > 0 else 0
        rows.append([_short_label(a, 32), mom, mol, mm, total, f"{pct:.1f}%"])

    col_headers = ["Activity", "Move on Model", "Move on Log", "Mismatch Move", "Total", "% of All"]
    col_widths  = [0.34, 0.14, 0.12, 0.15, 0.10, 0.10]

    n_rows  = len(rows)
    fig_h   = max(3.5, n_rows * 0.48 + 2.0)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis("off")

    t = 0.94
    b = 0.06
    l = 0.02
    table_w = 0.96
    row_h = (t - b) / (n_rows + 1)

    x = l
    for hdr, cw in zip(col_headers, col_widths):
        ax.add_patch(plt.Rectangle((x, t - row_h), cw * table_w, row_h,
                                   fc=_HDR_BG, ec="white", linewidth=0.5,
                                   transform=ax.transAxes, clip_on=False))
        ax.text(x + cw * table_w * 0.5, t - row_h * 0.5, hdr,
                ha="center", va="center", fontsize=FONT_ANNOT,
                color="white", fontweight="bold", transform=ax.transAxes)
        x += cw * table_w

    for i, row in enumerate(rows):
        y_top = t - (i + 2) * row_h
        x = l
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(zip(row, col_widths)):
            ax.add_patch(plt.Rectangle((x, y_top), cw * table_w, row_h,
                                       fc=bg, ec="#eeeeee", linewidth=0.4,
                                       transform=ax.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * table_w * 0.5
            ax.text(px, y_top + row_h * 0.5, str(val),
                    ha=ha, va="center", fontsize=FONT_ANNOT,
                    color=_C_DARK, transform=ax.transAxes)
            x += cw * table_w

    ax.set_title(f"Guideline Violations per Activity  (top {n_rows})",
                 fontsize=FONT_TITLE, pad=14)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task09_table.svg"))


# ── Idiom 7: Table & Bar Chart ────────────────────────────────────────────────

def task09_table_bar_chart(activity_type, activity_totals, n_violations, output_dir):
    if not activity_totals:
        _no_violations(output_dir, "table_bar_chart")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)
    n = len(top_acts)

    mom_vals = [activity_type.get((a, "Move on Model"), 0) for a in top_acts]
    mol_vals = [activity_type.get((a, "Move on Log"),   0) for a in top_acts]
    mm_vals  = [activity_type.get((a, "Mismatch Move"), 0) for a in top_acts]
    totals   = [activity_totals[a] for a in top_acts]

    fig, (ax_tbl, ax_bar) = plt.subplots(
        1, 2, figsize=(16, max(4, n * 0.58 + 2.5)),
        gridspec_kw={"width_ratios": [2, 3]},
    )

    # ── Left: table ──────────────────────────────────────────────────────────
    ax_tbl.axis("off")
    col_headers = ["Activity", "MoM", "MoL", "MM", "Total"]
    col_widths  = [0.50, 0.13, 0.13, 0.13, 0.11]
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

    for i, (act, mom, mol, mm, total) in enumerate(
            zip(top_acts, mom_vals, mol_vals, mm_vals, totals)):
        y_top = t - (i + 2) * row_h
        x = 0.015
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(
                zip([_short_label(act, 24), mom, mol, mm, total], col_widths)):
            ax_tbl.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg, ec="#eeeeee", linewidth=0.4,
                                           transform=ax_tbl.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            ax_tbl.text(px, y_top + row_h * 0.5, str(val),
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, transform=ax_tbl.transAxes)
            x += cw * tw

    # ── Right: stacked bar ────────────────────────────────────────────────────
    ax_bar.set_facecolor("#fafbfc")
    lefts = np.zeros(n)
    for vtype, vals in [
        ("Move on Model", mom_vals),
        ("Move on Log",   mol_vals),
        ("Mismatch Move", mm_vals),
    ]:
        v = np.array(vals, dtype=float)
        ax_bar.barh(range(n), v, left=lefts,
                    color=_VTYPE_COLOR[vtype], label=vtype,
                    edgecolor="white", linewidth=0.5, height=0.65)
        lefts += v

    ax_bar.set_yticks(range(n))
    ax_bar.set_yticklabels([_short_label(a, 24) for a in top_acts], fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Violation count", fontsize=FONT_LABEL)
    ax_bar.set_title("Violations by Type", fontsize=FONT_TITLE)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax_bar.set_axisbelow(True)
    ax_bar.legend(loc="lower right", fontsize=FONT_ANNOT, frameon=True, framealpha=0.9)

    fig.suptitle(f"Violation Breakdown per Activity  (top {n})",
                 fontsize=FONT_TITLE + 1, y=1.01)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task09_table_bar_chart.svg"))


# ── Idiom 8: Matrix ───────────────────────────────────────────────────────────

def task09_matrix(activity_type, activity_totals, output_dir):
    """Activity × violation-type matrix. Cell = count. PowerNorm for contrast."""
    if not activity_totals:
        _no_violations(output_dir, "matrix")
        return

    top_acts = _top_activities(activity_totals, _TOP_N)
    short_labels = [_short_label(a, 30) for a in top_acts]

    mat = np.array([
        [activity_type.get((a, vt), 0) for vt in _VTYPES]
        for a in top_acts
    ], dtype=float)

    fig_h = max(4, len(top_acts) * 0.6 + 2)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    ax.set_facecolor("#fafbfc")

    vmax = mat.max() if mat.max() > 0 else 1
    im = ax.imshow(mat, cmap=_CMAP_SEQ, aspect="auto",
                   norm=mcolors.PowerNorm(gamma=0.5, vmin=0, vmax=vmax))

    ax.set_xticks(range(len(_VTYPES)))
    ax.set_xticklabels(_VTYPES, fontsize=FONT_ANNOT, rotation=15, ha="right")
    ax.set_yticks(range(len(top_acts)))
    ax.set_yticklabels(short_labels, fontsize=FONT_ANNOT)

    for i in range(len(top_acts)):
        for j in range(len(_VTYPES)):
            val = int(mat[i, j])
            if val > 0:
                brightness = im.norm(val)
                txt_color = "white" if brightness > 0.55 else _C_DARK
                ax.text(j, i, str(val), ha="center", va="center",
                        fontsize=max(FONT_ANNOT - 1, 6), color=txt_color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cbar.set_label("Violation count", fontsize=FONT_ANNOT)
    cbar.outline.set_visible(False)

    ax.set_title("Activity × Violation Type Matrix", fontsize=FONT_TITLE)
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task09_matrix.svg"))


# ── Flow helpers ──────────────────────────────────────────────────────────────

def _infer_activity_order(alignments):
    """Infer activity sequence from expected (model) side of alignments."""
    pos_sum, pos_cnt = {}, {}
    for aln in alignments:
        seq = []
        for step in aln.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            exp = (str(step[1]) if step[1] else "").strip()
            if exp and exp != ">>":
                seq.append(exp)
        n = max(len(seq), 1)
        for i, act in enumerate(seq):
            pos_sum[act] = pos_sum.get(act, 0) + i / n
            pos_cnt[act] = pos_cnt.get(act, 0) + 1
    if not pos_sum:
        return []
    avg = {a: pos_sum[a] / pos_cnt[a] for a in pos_sum}
    return sorted(avg, key=avg.get)


def _violation_shade(rate):
    """Grey hex: 0→#eeeeee (light), 1→#333333 (dark)."""
    v = round(238 - max(0.0, min(1.0, rate)) * (238 - 51))
    return f"#{v:02x}{v:02x}{v:02x}"


def _ordered_violated_acts(activity_totals, alignments):
    order   = _infer_activity_order(alignments)
    ordered = [a for a in order if a in activity_totals]
    if len(ordered) > _TOP_N:
        top_set = set(_top_activities(activity_totals, _TOP_N))
        ordered = [a for a in ordered if a in top_set]
    return ordered


def _flow_nodes(activity_totals, ordered):
    max_v = max(activity_totals.get(a, 0) for a in ordered) if ordered else 1
    return [
        {"label": f"{_short_label(a, 16)}\n({activity_totals.get(a, 0)})",
         "color": _violation_shade(activity_totals.get(a, 0) / max_v if max_v else 0)}
        for a in ordered
    ]


def _flow_legend_handles():
    return [
        mpatches.Patch(facecolor=_violation_shade(r), edgecolor="#888888",
                       linewidth=0.8, label=lbl)
        for r, lbl in [(0.0, "No violations"), (0.5, "Moderate"), (1.0, "Most violations")]
    ]


def _import_task28_chevron():
    # Chevron primitives live in shared.py (moved there from task28)
    from shared import draw_chevron_strip, chevron_figure_width
    return draw_chevron_strip, chevron_figure_width


# ── Idiom: Flow Chart Basic ───────────────────────────────────────────────────

def task09_flow_chart_basic(activity_type, activity_totals, alignments, output_dir):
    if not activity_totals:
        _no_violations(output_dir, "flow_chart_basic")
        return

    ordered = _ordered_violated_acts(activity_totals, alignments)
    if not ordered:
        _no_violations(output_dir, "flow_chart_basic")
        return

    nodes = _flow_nodes(activity_totals, ordered)
    draw_chevrons, chevron_fig_width = _import_task28_chevron()

    fig_w = chevron_fig_width(nodes)
    fig, ax = plt.subplots(figsize=(fig_w, 4.5))
    draw_chevrons(ax, nodes, fontsize=9)
    fig.subplots_adjust(left=0.03, right=0.98, top=0.58, bottom=0.30)
    fig.text(0.03, 0.90, "Process Flow — Violation Heatmap",
             ha="left", va="top", fontsize=FONT_TITLE, color=_C_DARK)
    fig.legend(handles=_flow_legend_handles(), loc="lower center",
               bbox_to_anchor=(0.5, 0.05), ncol=3,
               fontsize=FONT_ANNOT, frameon=True, fancybox=False, edgecolor="#cccccc")
    save_svg(fig, os.path.join(output_dir, "task09_flow_chart_basic.svg"))


# ── Idiom: Flow Chart & Table ─────────────────────────────────────────────────

def task09_flow_chart_and_table(activity_type, activity_totals, type_totals, n_violations, alignments, output_dir):
    if not activity_totals:
        _no_violations(output_dir, "flow_chart_and_table")
        return

    ordered  = _ordered_violated_acts(activity_totals, alignments)
    top_acts = _top_activities(activity_totals, _TOP_N)
    n_rows   = len(top_acts)
    nodes    = _flow_nodes(activity_totals, ordered) if ordered else []

    draw_chevrons, chevron_fig_width = _import_task28_chevron()

    fig_w = max(16.0, chevron_fig_width(nodes) if nodes else 16.0)
    fig_h = max(9.0, n_rows * 0.5 + 5.5)
    fig   = plt.figure(figsize=(fig_w, fig_h))
    gs    = plt.GridSpec(2, 1,
                         height_ratios=[max(2.8, n_rows * 0.5 + 1.5), 1.5],
                         hspace=0.22)
    ax_tbl  = fig.add_subplot(gs[0])
    ax_flow = fig.add_subplot(gs[1])

    # ── Table ──────────────────────────────────────────────────────────────────
    ax_tbl.axis("off")
    col_headers = ["Activity", "Move on Model", "Move on Log", "Mismatch Move", "Total", "% of All"]
    col_widths  = [0.34, 0.14, 0.12, 0.15, 0.10, 0.10]
    t = 0.96; l = 0.01; tw = 0.98
    row_h = (t - 0.02) / (n_rows + 1)
    x = l
    for hdr, cw in zip(col_headers, col_widths):
        ax_tbl.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                       fc=_HDR_BG, ec="white", linewidth=0.5,
                                       transform=ax_tbl.transAxes, clip_on=False))
        ax_tbl.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                    ha="center", va="center", fontsize=FONT_ANNOT,
                    color="white", fontweight="bold", transform=ax_tbl.transAxes)
        x += cw * tw
    for i, act in enumerate(top_acts):
        mom   = activity_type.get((act, "Move on Model"), 0)
        mol   = activity_type.get((act, "Move on Log"),   0)
        mm    = activity_type.get((act, "Mismatch Move"), 0)
        total = mom + mol + mm
        pct   = total / n_violations * 100 if n_violations > 0 else 0
        row_vals = [_short_label(act, 32), mom, mol, mm, total, f"{pct:.1f}%"]
        y_top = t - (i + 2) * row_h
        x = l
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(zip(row_vals, col_widths)):
            ax_tbl.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg, ec="#eeeeee", linewidth=0.4,
                                           transform=ax_tbl.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            ax_tbl.text(px, y_top + row_h * 0.5, str(val),
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, transform=ax_tbl.transAxes)
            x += cw * tw
    ax_tbl.set_title(f"Guideline Violations per Activity  (top {n_rows})",
                     fontsize=FONT_TITLE, pad=10)

    # ── Chevron flow ────────────────────────────────────────────────────────────
    if nodes:
        draw_chevrons(ax_flow, nodes, fontsize=9)
    else:
        ax_flow.axis("off")
        ax_flow.text(0.5, 0.5, "No activity order inferred from alignments",
                     ha="center", va="center", fontsize=FONT_ANNOT,
                     color="#888888", transform=ax_flow.transAxes)
    ax_flow.set_title("Process Flow — Violation Heatmap", fontsize=FONT_TITLE, pad=6)

    fig.legend(handles=_flow_legend_handles(), loc="lower center",
               bbox_to_anchor=(0.5, 0.01), ncol=3,
               fontsize=FONT_ANNOT, frameon=True, fancybox=False, edgecolor="#cccccc")
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task09_flow_chart_and_table.svg"))


# ── Idiom: Flow Chart Elaborate BPMN ─────────────────────────────────────────

def _make_bpmn_violation_svg(activity_totals, model_path, h_scale: float = 1.0):
    """Return SVG string: BPMN nodes shaded by violation rate. Returns None on parse failure."""
    ns = {
        "bpmn":  "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi":"http://www.omg.org/spec/BPMN/20100524/DI",
        "dc":    "http://www.omg.org/spec/DD/20100524/DC",
        "di":    "http://www.omg.org/spec/DD/20100524/DI",
    }

    def local(tag): return tag.split("}", 1)[-1] if "}" in tag else tag
    def esc(v):     return _html.escape("" if v is None else str(v), quote=True)

    try:
        tree = _ET.parse(model_path)
    except Exception:
        return None
    root = tree.getroot()

    elements = {}
    for e in root.findall(".//bpmn:*", ns):
        eid  = e.attrib.get("id")
        kind = local(e.tag)
        if eid and kind in {"task", "startEvent", "endEvent",
                            "exclusiveGateway", "parallelGateway"}:
            elements[eid] = {"kind": kind, "name": e.attrib.get("name", "")}

    shapes = {}
    for s in root.findall(".//bpmndi:BPMNShape", ns):
        eid = s.attrib.get("bpmnElement")
        b   = s.find("dc:Bounds", ns)
        if eid and b is not None:
            shapes[eid] = {
                "x": float(b.attrib["x"]), "y": float(b.attrib["y"]),
                "width": float(b.attrib["width"]), "height": float(b.attrib["height"]),
            }

    edges = {}
    for e in root.findall(".//bpmndi:BPMNEdge", ns):
        fid = e.attrib.get("bpmnElement")
        pts = [(float(wp.attrib["x"]), float(wp.attrib["y"]))
               for wp in e.findall("di:waypoint", ns)]
        if fid and pts:
            edges[fid] = pts

    if not shapes:
        return None

    max_v    = max(activity_totals.values()) if activity_totals else 1
    max_act  = max(activity_totals, key=activity_totals.get) if activity_totals else ""
    max_cnt  = activity_totals.get(max_act, 0)
    name_to_rate = {name: cnt / max_v for name, cnt in activity_totals.items()}

    xs, ys = [], []
    for b in shapes.values():
        xs += [b["x"], b["x"] + b["width"]]
        ys += [b["y"], b["y"] + b["height"]]
    for pts in edges.values():
        for px, py in pts:
            xs.append(px); ys.append(py)

    min_x, min_y = min(xs), min(ys)
    W = (max(xs) - min_x) * h_scale + 120
    H = max(ys) - min_y + 195   # extra bottom for legend + title

    def tx(x): return (x - min_x) * h_scale + 60
    def ty(y): return y - min_y + 95

    def wrap(label, box_w, fs=9):
        mc    = max(6, int((box_w - 10) / (fs * 0.58)))
        words, lines, cur = str(label).replace("_", " ").split(), [], ""
        for w in words:
            cand = w if not cur else f"{cur} {w}"
            if len(cand) <= mc: cur = cand
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines[:3] or [str(label)]

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H:.1f}" viewBox="0 0 {W:.1f} {H:.1f}">',
        "<defs><marker id='arr' viewBox='0 0 10 10' refX='9' refY='5' "
        "markerWidth='5' markerHeight='5' orient='auto' markerUnits='userSpaceOnUse'>"
        "<path d='M0,0 L10,5 L0,10 Z' fill='#888'/></marker></defs>",
        "<rect width='100%' height='100%' fill='white'/>",
        f"<text x='{W/2:.1f}' y='32' text-anchor='middle' "
        f"font-family='Arial,sans-serif' font-size='15' font-weight='bold' fill='{_C_DARK}'>"
        "Process Flow — Violation Heatmap</text>",
        f"<text x='{W/2:.1f}' y='52' text-anchor='middle' "
        f"font-family='Arial,sans-serif' font-size='10' fill='{_C_MED}'>"
        "Node shade: lighter = fewer violations · darker = more violations</text>",
    ]

    # Edges
    for fid, pts in edges.items():
        pstr = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in pts)
        out.append(f"<polyline points='{pstr}' fill='none' stroke='#999' "
                   f"stroke-width='1.8' marker-end='url(#arr)'/>")

    # Shapes
    for eid, b in shapes.items():
        elem = elements.get(eid, {"kind": "task", "name": ""})
        kind, name = elem["kind"], elem["name"]
        x, y, w, h = tx(b["x"]), ty(b["y"]), b["width"], b["height"]
        rate  = name_to_rate.get(name, 0.0)
        fill  = _violation_shade(rate) if kind == "task" else "#f0f0f0"
        stroke = "#777"
        v_int = int(fill[1:3], 16)
        tc    = "white" if v_int < 140 else "#1a1a1a"

        if kind == "task":
            cnt   = activity_totals.get(name, 0)
            out.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' "
                       f"rx='6' fill='{fill}' stroke='{stroke}' stroke-width='2'/>")
            lines = wrap(name, w)
            gap   = 11
            # Shift label up slightly when count badge is shown at bottom
            shift = 4 if cnt > 0 else 0
            sy    = y + h / 2 - (len(lines) - 1) * gap / 2 - shift
            for li, line in enumerate(lines):
                out.append(f"<text x='{x+w/2:.1f}' y='{sy+li*gap:.1f}' "
                           f"text-anchor='middle' dominant-baseline='middle' "
                           f"font-family='Arial,sans-serif' font-size='9' fill='{tc}'>"
                           f"{esc(line)}</text>")
            if cnt > 0:
                cnt_tc = "white" if v_int < 140 else "#333333"
                out.append(f"<text x='{x+w/2:.1f}' y='{y+h-5:.1f}' "
                           f"text-anchor='middle' dominant-baseline='middle' "
                           f"font-family='Arial,sans-serif' font-size='7.5' fill='{cnt_tc}'>"
                           f"{cnt:,}</text>")
        elif kind in {"exclusiveGateway", "parallelGateway"}:
            cx, cy = x + w / 2, y + h / 2
            out.append(f"<polygon points='{cx:.1f},{y:.1f} {x+w:.1f},{cy:.1f} "
                       f"{cx:.1f},{y+h:.1f} {x:.1f},{cy:.1f}' "
                       f"fill='#f0f0f0' stroke='{stroke}' stroke-width='2'/>")
            mk = "+" if kind == "parallelGateway" else "X"
            fs = max(13.0, min(w, h) * 0.38)
            out.append(f"<text x='{cx:.1f}' y='{cy+1:.1f}' text-anchor='middle' "
                       f"dominant-baseline='middle' font-family='Arial,sans-serif' "
                       f"font-size='{fs:.0f}' fill='{stroke}'>{mk}</text>")
        elif kind in {"startEvent", "endEvent"}:
            cx, cy = x + w / 2, y + h / 2
            r  = min(w, h) / 2
            sw = 3 if kind == "endEvent" else 2
            out.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='{r:.1f}' "
                       f"fill='white' stroke='{stroke}' stroke-width='{sw}'/>")
            lbl = "START" if kind == "startEvent" else "END"
            out.append(f"<text x='{cx:.1f}' y='{y+h+14:.1f}' text-anchor='middle' "
                       f"font-family='Arial,sans-serif' font-size='8' fill='{stroke}'>{lbl}</text>")

    # Greyscale legend — centered, with border box, absolute violation counts
    ly       = H - 58
    STEP     = 58
    SW_W     = 26
    SW_H     = 16
    LBL_FS   = 10
    cnt_label     = f"{max_cnt:,}"
    tail_text_str = f"violations  ·  darkest: {_short_label(max_act, 20)}"
    swatch_bar_w  = 4 * STEP + SW_W
    cnt_label_w   = len(cnt_label) * 6.5 + 10
    tail_text_w   = len(tail_text_str) * 5.8 + 8
    content_w     = swatch_bar_w + cnt_label_w + tail_text_w
    box_pad       = 14
    box_w         = content_w + 2 * box_pad
    off           = max(10.0, (W - box_w) / 2)   # content left edge
    out.append(f"<rect x='{off - box_pad:.1f}' y='{ly - 10:.1f}' "
               f"width='{box_w:.1f}' height='{SW_H + 22:.1f}' "
               f"rx='5' fill='#fafafa' stroke='#cccccc' stroke-width='1'/>")
    legend_steps = [(0.0, "0"), (0.25, ""), (0.5, "50%"), (0.75, ""), (1.0, cnt_label)]
    for i, (lvl, lbl) in enumerate(legend_steps):
        bx = off + i * STEP
        shade = _violation_shade(lvl)
        out.append(f"<rect x='{bx:.1f}' y='{ly:.1f}' width='{SW_W}' height='{SW_H}' "
                   f"fill='{shade}' stroke='#aaa' stroke-width='0.8'/>")
        if lbl:
            out.append(f"<text x='{bx + SW_W + 4:.1f}' y='{ly + SW_H - 2:.1f}' "
                       f"font-family='Arial,sans-serif' font-size='{LBL_FS}' fill='{_C_MED}'>"
                       f"{esc(lbl)}</text>")
    tail_x = off + 4 * STEP + SW_W + cnt_label_w
    out.append(f"<text x='{tail_x:.1f}' y='{ly + SW_H - 2:.1f}' "
               f"font-family='Arial,sans-serif' font-size='{LBL_FS}' fill='{_C_MED}'>"
               f"{esc(tail_text_str)}</text>")

    out.append("</svg>")
    return "\n".join(out)


# ── T11-specific BPMN: rich node labels with embedded violation details ────────

_T11_VTYPE_SHORT = {
    "Move on Model": "MoM",
    "Move on Log":   "MoL",
    "Mismatch Move": "MM",
}


def _make_bpmn_t11_svg(selected, trace_coverage, n_traces, activity_totals,
                        model_path, h_scale=1.1, v_scale=2.0):
    """Return SVG string: BPMN nodes with embedded per-violation-type labels.

    Each violating task node shows:
      Activity Name (wrapped, top half)
      ─────────────────── (separator)
      VT: count | pct%   (one line per violation, bottom half)

    Shade uses CIVIDIS_R proportional to the activity's union trace count.
    Non-violating tasks get a neutral light fill.
    Returns None on parse failure.
    """
    ns = {
        "bpmn":   "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        "dc":     "http://www.omg.org/spec/DD/20100524/DC",
        "di":     "http://www.omg.org/spec/DD/20100524/DI",
    }

    def local(tag): return tag.split("}", 1)[-1] if "}" in tag else tag
    def esc(v):     return _html.escape("" if v is None else str(v), quote=True)

    try:
        tree = _ET.parse(model_path)
    except Exception:
        return None
    root = tree.getroot()

    elements = {}
    for e in root.findall(".//bpmn:*", ns):
        eid  = e.attrib.get("id")
        kind = local(e.tag)
        if eid and kind in {"task", "startEvent", "endEvent",
                            "exclusiveGateway", "parallelGateway"}:
            elements[eid] = {"kind": kind, "name": e.attrib.get("name", "")}

    shapes = {}
    for s in root.findall(".//bpmndi:BPMNShape", ns):
        eid = s.attrib.get("bpmnElement")
        b   = s.find("dc:Bounds", ns)
        if eid and b is not None:
            shapes[eid] = {
                "x": float(b.attrib["x"]), "y": float(b.attrib["y"]),
                "width": float(b.attrib["width"]), "height": float(b.attrib["height"]),
            }

    edges = {}
    for e in root.findall(".//bpmndi:BPMNEdge", ns):
        fid = e.attrib.get("bpmnElement")
        pts = [(float(wp.attrib["x"]), float(wp.attrib["y"]))
               for wp in e.findall("di:waypoint", ns)]
        if fid and pts:
            edges[fid] = pts

    if not shapes:
        return None

    # ── Build per-activity violation list ──────────────────────────────────────
    act_viols = {}  # act → [(short_vt, count, pct), ...]
    for act, vt in selected:
        cnt = trace_coverage.get((act, vt), 0)
        pct = cnt / n_traces * 100 if n_traces > 0 else 0
        act_viols.setdefault(act, []).append(
            (_T11_VTYPE_SHORT.get(vt, vt), cnt, pct)
        )
    for act in act_viols:
        act_viols[act].sort(key=lambda x: -x[1])

    max_v = max(activity_totals.values()) if activity_totals else 1

    def node_fill(act_name):
        if act_name not in activity_totals:
            return "#f0f1f2"
        rate = activity_totals[act_name] / max_v
        r, g, b, _ = CIVIDIS_R(rate)
        return mcolors.to_hex((r, g, b))

    def text_color(hex_fill):
        r = int(hex_fill[1:3], 16) / 255
        g = int(hex_fill[3:5], 16) / 255
        b = int(hex_fill[5:7], 16) / 255
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "white" if lum < 0.45 else "#1a1a1a"

    xs, ys = [], []
    for b in shapes.values():
        xs += [b["x"], b["x"] + b["width"]]
        ys += [b["y"], b["y"] + b["height"]]
    for pts in edges.values():
        for px, py in pts:
            xs.append(px); ys.append(py)

    min_x, min_y = min(xs), min(ys)
    W = (max(xs) - min_x) * h_scale + 120
    H = (max(ys) - min_y) * v_scale + 130

    def tx(x): return (x - min_x) * h_scale + 60
    def ty(y): return (y - min_y) * v_scale + 75

    def wrap_name(label, box_w, fs=9):
        mc = max(6, int((box_w - 12) / (fs * 0.58)))
        words, lines, cur = str(label).replace("_", " ").split(), [], ""
        for w in words:
            cand = w if not cur else f"{cur} {w}"
            if len(cand) <= mc: cur = cand
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines[:3] or [str(label)]

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H:.1f}" '
        f'viewBox="0 0 {W:.1f} {H:.1f}">',
        "<defs><marker id='arr' viewBox='0 0 10 10' refX='9' refY='5' "
        "markerWidth='5' markerHeight='5' orient='auto' markerUnits='userSpaceOnUse'>"
        "<path d='M0,0 L10,5 L0,10 Z' fill='#999'/></marker></defs>",
        "<rect width='100%' height='100%' fill='white'/>",
        f"<text x='{W/2:.1f}' y='44' text-anchor='middle' "
        f"font-family='Arial,sans-serif' font-size='15' font-weight='bold' fill='#1a1a1a'>"
        "Predefined Violation Frequency — Process View</text>",
    ]

    # Edges
    for fid, pts in edges.items():
        pstr = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in pts)
        out.append(f"<polyline points='{pstr}' fill='none' stroke='#b0b0b0' "
                   f"stroke-width='1.6' marker-end='url(#arr)'/>")

    # Shapes
    for eid, b in shapes.items():
        elem = elements.get(eid, {"kind": "task", "name": ""})
        kind, name = elem["kind"], elem["name"]
        x  = tx(b["x"])
        y  = ty(b["y"])
        w  = b["width"] * h_scale   # scale width with h_scale so waypoints align
        h  = b["height"] * v_scale
        stroke = "#aaaaaa"

        if kind == "task":
            fill = node_fill(name)
            tc   = text_color(fill)
            viols = act_viols.get(name, [])
            has_viols = bool(viols)

            out.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' "
                       f"rx='7' fill='{fill}' stroke='{stroke}' stroke-width='1.5'/>")

            name_lines = wrap_name(name, w)
            name_gap   = 11
            name_fs    = 9

            if has_viols:
                # Name occupies upper third; separator divides; violations fill lower half
                n_name = len(name_lines)
                name_block_h = n_name * name_gap
                sep_y = y + max(name_block_h + 10, h * 0.42)
                name_top = sep_y - name_block_h - 4
                for li, line in enumerate(name_lines):
                    ly = name_top + li * name_gap
                    out.append(f"<text x='{x+w/2:.1f}' y='{ly:.1f}' "
                               f"text-anchor='middle' dominant-baseline='middle' "
                               f"font-family='Arial,sans-serif' font-size='{name_fs}' "
                               f"font-weight='600' fill='{tc}'>{esc(line)}</text>")
                # Separator line — use white on dark nodes, grey on light nodes
                sep_color = "white" if tc == "white" else "#999999"
                sep_margin = w * 0.12
                out.append(f"<line x1='{x+sep_margin:.1f}' y1='{sep_y:.1f}' "
                           f"x2='{x+w-sep_margin:.1f}' y2='{sep_y:.1f}' "
                           f"stroke='{sep_color}' stroke-width='0.8' stroke-opacity='0.5'/>")
                # Violation lines
                viol_fs  = 9
                viol_gap = 12
                viol_top = sep_y + 10
                for vi, (svt, cnt, pct) in enumerate(viols):
                    vy = viol_top + vi * viol_gap
                    lbl = f"{svt}: {cnt:,} | {pct:.1f}%"
                    out.append(f"<text x='{x+w/2:.1f}' y='{vy:.1f}' "
                               f"text-anchor='middle' dominant-baseline='middle' "
                               f"font-family='Arial,sans-serif' font-size='{viol_fs}' "
                               f"fill='{tc}'>{esc(lbl)}</text>")
            else:
                # No violations: name centered
                name_mid = y + h / 2 - (len(name_lines) - 1) * name_gap / 2
                for li, line in enumerate(name_lines):
                    out.append(f"<text x='{x+w/2:.1f}' y='{name_mid+li*name_gap:.1f}' "
                               f"text-anchor='middle' dominant-baseline='middle' "
                               f"font-family='Arial,sans-serif' font-size='{name_fs}' "
                               f"fill='#555555'>{esc(line)}</text>")

        elif kind in {"exclusiveGateway", "parallelGateway"}:
            gw = b["width"]
            gh = b["height"]
            # Center at the correct vertical position; render as a square diamond
            cx = x + gw * h_scale / 2
            cy = y + gh * v_scale / 2
            gs = gh * v_scale / 2   # half-side (height and width equal → square)
            pts_g = (f"{cx:.1f},{cy-gs:.1f} {cx+gs:.1f},{cy:.1f} "
                     f"{cx:.1f},{cy+gs:.1f} {cx-gs:.1f},{cy:.1f}")
            out.append(f"<polygon points='{pts_g}' fill='#f0f0f0' "
                       f"stroke='{stroke}' stroke-width='1.5'/>")
            mk = "+" if kind == "parallelGateway" else "×"
            out.append(f"<text x='{cx:.1f}' y='{cy+1:.1f}' text-anchor='middle' "
                       f"dominant-baseline='middle' font-family='Arial,sans-serif' "
                       f"font-size='16' fill='#888'>{mk}</text>")

        elif kind in {"startEvent", "endEvent"}:
            ew = b["width"]
            eh = b["height"]
            cx, cy = x + ew * h_scale / 2, y + eh * v_scale / 2
            r  = min(ew, eh) * h_scale / 2
            sw = 3 if kind == "endEvent" else 1.5
            out.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='{r:.1f}' "
                       f"fill='white' stroke='#777' stroke-width='{sw}'/>")
            lbl = "START" if kind == "startEvent" else "END"
            out.append(f"<text x='{cx:.1f}' y='{cy + r + 13:.1f}' text-anchor='middle' "
                       f"font-family='Arial,sans-serif' font-size='8' fill='#888'>{lbl}</text>")

    out.append("</svg>")
    return "\n".join(out)


def task09_flow_chart_elaborate_bpmn(activity_type, activity_totals, model_path, output_dir):
    if model_path is None:
        _save_empty(output_dir, "task09_flow_chart_elaborate_bpmn.svg",
                    "No process model provided — Flow+ requires a BPMN file.")
        return
    if not activity_totals:
        _no_violations(output_dir, "flow_chart_elaborate_bpmn")
        return
    svg = _make_bpmn_violation_svg(activity_totals, model_path)
    if svg is None:
        _save_empty(output_dir, "task09_flow_chart_elaborate_bpmn.svg",
                    "Could not parse process model.")
        return
    path = os.path.join(output_dir, "task09_flow_chart_elaborate_bpmn.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ── Idiom: Flow Chart Elaborate BPMN & Table ──────────────────────────────────

def _svg_dims(svg_str):
    m = _re.search(r'<svg[^>]*\bwidth="([^"]+)"[^>]*\bheight="([^"]+)"', svg_str)
    if m:
        w = float(_re.sub(r"[^\d.]", "", m.group(1)))
        h = float(_re.sub(r"[^\d.]", "", m.group(2)))
        return w, h
    return None, None


def task09_flow_chart_elaborate_bpmn_table(activity_type, activity_totals, type_totals, n_violations, model_path, output_dir):
    """Composite SVG: BPMN flow+ (top) + violation table (bottom)."""
    if not activity_totals:
        _no_violations(output_dir, "flow_chart_elaborate_bpmn_table")
        return

    # ── Violation table → matplotlib SVG bytes ────────────────────────────────
    top_acts = _top_activities(activity_totals, _TOP_N)
    n_rows   = len(top_acts)
    tbl_w_in = 14.0
    tbl_h_in = max(3.5, n_rows * 0.48 + 2.0)
    tbl_fig, tbl_ax = plt.subplots(figsize=(tbl_w_in, tbl_h_in))
    tbl_ax.axis("off")
    col_headers = ["Activity", "Move on Model", "Move on Log", "Mismatch Move", "Total", "% of All"]
    col_widths  = [0.34, 0.14, 0.12, 0.15, 0.10, 0.10]
    t = 0.94; l = 0.02; tw = 0.96
    row_h = (t - 0.06) / (n_rows + 1)
    x = l
    for hdr, cw in zip(col_headers, col_widths):
        tbl_ax.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                       fc=_HDR_BG, ec="white", linewidth=0.5,
                                       transform=tbl_ax.transAxes, clip_on=False))
        tbl_ax.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                    ha="center", va="center", fontsize=FONT_ANNOT,
                    color="white", fontweight="bold", transform=tbl_ax.transAxes)
        x += cw * tw
    for i, act in enumerate(top_acts):
        mom   = activity_type.get((act, "Move on Model"), 0)
        mol   = activity_type.get((act, "Move on Log"),   0)
        mm    = activity_type.get((act, "Mismatch Move"), 0)
        total = mom + mol + mm
        pct   = total / n_violations * 100 if n_violations > 0 else 0
        row_vals = [_short_label(act, 32), mom, mol, mm, total, f"{pct:.1f}%"]
        y_top = t - (i + 2) * row_h
        x = l
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(zip(row_vals, col_widths)):
            tbl_ax.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg, ec="#eeeeee", linewidth=0.4,
                                           transform=tbl_ax.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            tbl_ax.text(px, y_top + row_h * 0.5, str(val),
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, transform=tbl_ax.transAxes)
            x += cw * tw
    tbl_ax.set_title(f"Guideline Violations per Activity  (top {n_rows})",
                     fontsize=FONT_TITLE, pad=14)
    tbl_fig.tight_layout(pad=1.2)
    buf = _io.BytesIO()
    tbl_fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(tbl_fig)
    buf.seek(0)
    tbl_svg_str = buf.read().decode("utf-8")
    tbl_w, tbl_h = _svg_dims(tbl_svg_str)
    if tbl_w is None:
        tbl_w, tbl_h = tbl_w_in * 72, tbl_h_in * 72

    # ── BPMN SVG ──────────────────────────────────────────────────────────────
    bpmn_svg = None if model_path is None else _make_bpmn_violation_svg(activity_totals, model_path)

    if bpmn_svg is None:
        # No model — just emit the table
        path = os.path.join(output_dir, "task09_flow_chart_elaborate_bpmn_table.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(tbl_svg_str)
        return

    bpmn_w, bpmn_h = _svg_dims(bpmn_svg)
    if bpmn_w is None:
        bpmn_w, bpmn_h = 800.0, 600.0

    # Scale table to match BPMN width; stack vertically
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
    path = os.path.join(output_dir, "task09_flow_chart_elaborate_bpmn_table.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(composite)


# ── Public entry point ────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None):
    """Generate all Task 9 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 9 visualizations (Identify guideline violations) ---")

    activity_type, activity_totals, type_totals, n_violations = _extract_data(alignments)

    if not activity_totals:
        logger.warning("      Skipped Task 9: no violations found in alignments.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task09_{name}.svg",
                        "No guideline violations found in this log.")
        return

    task09_bar_chart(type_totals, n_violations, output_dir)
    task09_stacked_bar(activity_type, activity_totals, output_dir)
    task09_scatter_plot(activity_type, activity_totals, output_dir)
    task09_table(activity_type, activity_totals, type_totals, n_violations, output_dir)
    task09_table_bar_chart(activity_type, activity_totals, n_violations, output_dir)
    task09_matrix(activity_type, activity_totals, output_dir)
    task09_flow_chart_basic(activity_type, activity_totals, alignments, output_dir)
    task09_flow_chart_and_table(activity_type, activity_totals, type_totals, n_violations, alignments, output_dir)
    task09_flow_chart_elaborate_bpmn(activity_type, activity_totals, model_path, output_dir)
    task09_flow_chart_elaborate_bpmn_table(activity_type, activity_totals, type_totals, n_violations, model_path, output_dir)
