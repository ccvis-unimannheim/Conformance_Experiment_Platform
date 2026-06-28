"""
tasks/task34.py – Where does the recorded behavior violate which guidelines?

Trace-level: shows violations for one or few traces simultaneously,
with clear attribution of which violations belong to which activities.

IDIOMS:
    bar_chart                  – top-N activities by total violation count (log-level, colored by dominant type)
    stacked_bar                – violations per activity (representative trace, stacked MoM/MoL)
    table                      – alignment table for worst-fitness trace
    flow_chart_table           – chevron + alignment table
    flow_chart_elaborate_table – BPMN with per-node violation coloring + alignment table
    heatmap                    – top-20 traces × activities violation heatmap
    table_bar_chart            – top-10 trace summary table + log-level violations bar chart
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart",
    "stacked_bar",
    "table",
    "flow_chart_basic",
    "flow_chart_table",
    "flow_chart_elaborate",
    "flow_chart_elaborate_table",
    "heatmap",
    "matrix",
    "parallel_sets",
    "table_bar_chart",
]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6)
#
# Task 34 (AUTO): representative trace is deterministically the worst-fitness
# trace (highest violation count, then lowest fitness). No admin parameter
# needed — GT is fully computable from the alignment output.
# ---------------------------------------------------------------------------
GT_TIER = "AUTO"

PARAM_SPEC = []

ANSWER_FORMATS = [
    {"key": "mc-multi", "gt_shape": "mc", "decisive_default": True},
]

RUBRIC = (
    "A complete answer correctly identifies the activities where violations occur "
    "in the representative (worst-fitness) trace and the type of each violation "
    "(Move on Model = skipped activity, Move on Log = extra/inserted activity, "
    "Mismatch Move = wrong activity executed). Award full marks for correctly "
    "naming the top violated activities with their violation types. Award partial "
    "marks for correctly identifying the activities without the types, or for "
    "identifying most but not all violated activities. Deduct marks for "
    "incorrectly including activities that have no violations in the trace."
)

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg,
    GREY_MED, GREY_LIGHTER, GREY_DARK, GREY_LIGHT,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    chevron_figure_width, draw_chevron_strip,
    draw_value_heatmap,
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    render_empty_state_svg,
    contrasting_text_color,
    draw_parallel_sets,
    classify_step,
)

def _chevron_nodes(rows):
    """Map task34 alignment rows to chevron nodes with correct move-type colors.
    task34 uses 'Synchronous'/'Move on Model'/'Move on Log'/'Mismatch Move'
    (different from the shared helper which expects 'Synchronous Move'/'Model Move').
    """
    nodes = []
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous":
            nodes.append({"label": r["log_move"],   "color": GREY_LIGHTER})
        elif mt == "Move on Model":
            nodes.append({"label": r["model_move"], "color": GREY_MED})
        elif mt == "Mismatch Move":
            nodes.append({"label": f"{r['log_move']} / {r['model_move']}", "color": GREY_LIGHT})
        else:  # Move on Log
            nodes.append({"label": r["log_move"],   "color": GREY_DARK})
    return nodes


# ── Color constants (aligned with task08/09/35) ───────────────────────────────
_C_DARK  = "#222222"
_C_MED   = "#666666"
_C_LIGHT = "#aaaaaa"
_C_BG    = "#f5f5f5"
_HDR_BG  = "#333333"
_CMAP    = "Greys"

# Violation type → dot / bar color
_MOVE_COLORS = {
    "Synchronous":   "#CCCCCC",   # GREY_LIGHTER  — conformant
    "Move on Model": _C_LIGHT,    # aaaaaa — skipped activity
    "Move on Log":   _C_MED,      # 666666 — extra activity
    "Mismatch Move": _C_DARK,     # 222222 — mismatch
}

# Table row colors (task28 style)
_SYNC_ROW = "#F2F2F2"
_MOM_ROW  = "#E0E0E0"
_MOL_ROW  = "#C8C8C8"
_MIS_ROW  = "#D8D8D8"
_COL_LABELS = ["Step", "Log Move", "Model Move", "Status"]
_COL_WIDTHS = [0.065, 0.375, 0.375, 0.185]


# ── Data helpers ──────────────────────────────────────────────────────────────

def _extract_label(val):
    if val is None:
        return ">>"
    if isinstance(val, (list, tuple)):
        for v in reversed(val):
            if isinstance(v, str) and v != ">>":
                return v
        return ">>"
    s = str(val)
    return ">>" if s in ("None", "") else s


def _parse_alignment(result):
    """Return list of step-dicts from one pm4py alignment result."""
    rows = []
    for i, (log_v, model_v) in enumerate(result.get("alignment") or []):
        ll = _extract_label(log_v)
        ml = _extract_label(model_v)
        if ll == ">>" and ml == ">>":
            continue
        act, mt = classify_step(ll, ml)
        if mt is None:
            mt = "Synchronous"
            act = ll
        rows.append({
            "step":       i + 1,
            "log_move":   ll,
            "model_move": ml,
            "status":     mt,
            "moveType":   mt,
            "activity":   act,
        })
    return rows


def _is_violation(row):
    return row["moveType"] != "Synchronous"


def _build_contexts(alignments, max_traces=30):
    """Top-K traces sorted by violation count descending."""
    ctxs = []
    for i, result in enumerate(alignments):
        rows = _parse_alignment(result)
        if not rows:
            continue
        n_viol = sum(1 for r in rows if _is_violation(r))
        ctxs.append({
            "trace_index":  i,
            "trace_label":  f"Trace {i + 1}",
            "fitness":      float(result.get("fitness", 1.0)),
            "cost":         result.get("cost"),
            "rows":         rows,
            "n_violations": n_viol,
        })
    ctxs.sort(key=lambda c: (-c["n_violations"], c["fitness"]))
    return ctxs[:max_traces]


def _trace_activity_violations(rows):
    """Per-activity {mom, mol, mismatch} counts for one trace."""
    counts = {}
    for r in rows:
        mt = r["moveType"]
        a  = r["activity"]
        if a == ">>" or mt == "Synchronous":
            continue
        counts.setdefault(a, {"mom": 0, "mol": 0, "mismatch": 0})
        if   mt == "Move on Model": counts[a]["mom"]      += 1
        elif mt == "Move on Log":   counts[a]["mol"]      += 1
        else:                       counts[a]["mismatch"] += 1
    return counts


def _log_activity_violations(alignments):
    """Aggregate per-activity violation counts across all traces."""
    totals = {}
    for result in alignments:
        for r in _parse_alignment(result):
            mt = r["moveType"]
            a  = r["activity"]
            if a == ">>" or mt == "Synchronous":
                continue
            totals.setdefault(a, {"mom": 0, "mol": 0, "mismatch": 0})
            if   mt == "Move on Model": totals[a]["mom"]      += 1
            elif mt == "Move on Log":   totals[a]["mol"]      += 1
            else:                       totals[a]["mismatch"] += 1
    return totals


def _no_violations(output_dir, idiom_key):
    render_empty_state_svg(
        os.path.join(output_dir, f"task34_{idiom_key}.svg"),
        "No Violations Found",
        "All traces are fully conformant — no violation data to display.",
    )


# ── Table drawing helpers ─────────────────────────────────────────────────────

def _cell_text(rows):
    return [[str(r["step"]), r["log_move"], r["model_move"], r["status"]] for r in rows]


def _draw_alignment_table(ax, rows, bbox, font_size=10.5):
    tbl = ax.table(
        cellText=_cell_text(rows),
        colLabels=_COL_LABELS,
        colWidths=_COL_WIDTHS,
        cellLoc="center",
        bbox=bbox,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(font_size)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#333333")
        cell.set_linewidth(0.8)
        if r == 0:
            cell.set_facecolor(_HDR_BG)
            cell.set_text_props(color="white")
        else:
            cell.set_facecolor("#F5F5F5" if r % 2 == 0 else "#FFFFFF")
            cell.set_text_props(color=_C_DARK)


def _add_trace_heading(fig, ctx, *, x=0.055, y=0.86):
    fig.text(x, y, ctx["trace_label"], ha="left", va="top",
             fontsize=FONT_TITLE, color="#111111")
    meta = (f"Fitness: {ctx['fitness']:.4f}   |   "
            f"Violations: {ctx['n_violations']}")
    fig.text(x, y - 0.065, meta, ha="left", va="top",
             fontsize=FONT_ANNOT, color="#6C6C6C")


def _move_legend():
    return [
        mpatches.Patch(color=_MOVE_COLORS["Synchronous"],   label="Synchronous (conform)"),
        mpatches.Patch(color=_MOVE_COLORS["Move on Model"], label="Move on Model (skipped)"),
        mpatches.Patch(color=_MOVE_COLORS["Move on Log"],   label="Move on Log (extra)"),
        mpatches.Patch(color=_MOVE_COLORS["Mismatch Move"], label="Mismatch Move"),
    ]


# ── Idiom 1: bar_chart — most violated activities (log-level) ────────────────

def task34_bar_chart(ctx, output_dir):
    """Horizontal bar: activities with violations in the worst-fitness trace.
    Bar color = dominant violation type. Trace-level answer to WHERE violations occur.
    """
    act_counts = _trace_activity_violations(ctx["rows"])
    if not act_counts:
        _no_violations(output_dir, "bar_chart")
        return

    totals = {a: sum(v.values()) for a, v in act_counts.items()}
    if not any(totals.values()):
        _no_violations(output_dir, "bar_chart")
        return

    acts   = sorted(totals, key=lambda a: totals[a], reverse=True)[:15]
    counts = [totals[a] for a in acts]
    total_viol = sum(counts)
    pcts   = [c / total_viol * 100 if total_viol else 0 for c in counts]

    def _dom_color(a):
        v = act_counts[a]
        dom = max(v, key=v.get)
        return {"mom": _C_LIGHT, "mol": _C_MED, "mismatch": _C_DARK}[dom]

    colors = [_dom_color(a) for a in acts]

    fig_h = max(3.5, len(acts) * 0.55 + 1.8)
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.set_facecolor("#fafbfc")

    bars = ax.barh(range(len(acts)), counts, color=colors,
                   edgecolor="white", linewidth=0.8, height=0.55)

    for i, (bar, cnt, pct) in enumerate(zip(bars, counts, pcts)):
        ax.text(bar.get_width() + max(counts) * 0.015, i,
                f"{cnt:,}  ({pct:.1f}%)",
                va="center", fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_yticks(range(len(acts)))
    ax.set_yticklabels(acts, fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Number of violations", fontsize=FONT_LABEL)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_xlim(0, max(counts) * 1.35)
    ax.set_title(
        f"Violated Activities — {ctx['trace_label']}  (fitness = {ctx['fitness']:.4f})\n"
        "color = dominant violation type   ·   label = count (% of trace violations)",
        fontsize=FONT_TITLE, pad=8,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)

    legend_handles = [
        mpatches.Patch(color=_C_LIGHT, label="Move on Model (dominant)"),
        mpatches.Patch(color=_C_MED,   label="Move on Log (dominant)"),
        mpatches.Patch(color=_C_DARK,  label="Mismatch Move (dominant)"),
    ]
    ax.legend(handles=legend_handles,
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_bar_chart.svg"))


# ── Idiom 2: stacked_bar — per-activity violations in representative trace ─────

def task34_stacked_bar(ctx, output_dir):
    """Stacked horizontal bar: which activities caused violations in the worst trace."""
    act_counts = _trace_activity_violations(ctx["rows"])
    if not act_counts:
        _no_violations(output_dir, "stacked_bar")
        return

    acts     = sorted(act_counts, key=lambda a: sum(act_counts[a].values()), reverse=True)
    mom_vals = [act_counts[a]["mom"]      for a in acts]
    mol_vals = [act_counts[a]["mol"]      for a in acts]
    mis_vals = [act_counts[a]["mismatch"] for a in acts]

    # Each row ~0.55 in; min 2.0, max 14.0
    fig_h = min(max(2.0, len(acts) * 0.55 + 1.8), 14.0)
    bar_h = min(0.7, (fig_h - 1.8) / max(len(acts), 1))
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.set_facecolor("#fafbfc")

    y    = range(len(acts))
    ax.barh(y, mom_vals, color=_C_LIGHT, label="Move on Model (skipped)",
            edgecolor="white", height=bar_h)
    left = mom_vals
    ax.barh(y, mol_vals, left=left, color=_C_MED, label="Move on Log (extra)",
            edgecolor="white", height=bar_h)
    left = [a + b for a, b in zip(mom_vals, mol_vals)]
    ax.barh(y, mis_vals, left=left, color=_C_DARK, label="Mismatch Move",
            edgecolor="white", height=bar_h)

    totals = [a + b + c for a, b, c in zip(mom_vals, mol_vals, mis_vals)]
    max_total = max(totals) if totals else 1
    for i, tot in enumerate(totals):
        if tot > 0:
            ax.text(tot + max_total * 0.015, i, str(tot), va="center",
                    fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_yticks(list(y))
    ax.set_yticklabels(acts, fontsize=FONT_ANNOT)
    ax.set_ylim(len(acts) - 0.5, -0.5)   # inverted, tight
    ax.set_xlabel("Violation count", fontsize=FONT_LABEL)
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_xlim(0, max_total * 1.12)
    ax.set_title(
        f"Violations per Activity — {ctx['trace_label']}  "
        f"(fitness = {ctx['fitness']:.4f})",
        fontsize=FONT_TITLE, pad=8,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45, zorder=0)
    ax.set_axisbelow(True)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="center left", bbox_to_anchor=(1.02, 0.5),
              ncol=1, fontsize=FONT_ANNOT, frameon=True, framealpha=0.9)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_stacked_bar.svg"))


# ── Idiom 3: table — alignment table for worst-fitness trace ──────────────────

def task34_table(ctx, output_dir):
    """Alignment detail table: step-by-step view of violations in the worst trace."""
    rows  = ctx["rows"]
    fig_h = max(4.7, 4.7 + len(rows) * 0.31)
    fig, ax = plt.subplots(figsize=(15.8, fig_h))
    ax.axis("off")
    _add_trace_heading(fig, ctx, x=0.06, y=0.86)
    _draw_alignment_table(ax, rows, bbox=[0.045, 0.08, 0.91, 0.58])
    fig.subplots_adjust(left=0.025, right=0.985, top=0.94, bottom=0.05)
    save_svg(fig, os.path.join(output_dir, "task34_table.svg"))


# ── Idiom 4: flow_chart_table — chevron + alignment table ─────────────────────

def task34_flow_chart_table(ctx, output_dir):
    """Composite: table (top) + chevron strip (bottom) for the worst trace."""
    rows  = ctx["rows"]
    nodes = _chevron_nodes(rows)

    fig_w = max(16.0, chevron_figure_width(nodes))
    fig_h = max(7.0, 4.0 + len(rows) * 0.22 + 2.0)
    fig   = plt.figure(figsize=(fig_w, fig_h))
    gs    = gridspec.GridSpec(
        2, 1,
        height_ratios=[max(2.0, 0.22 * len(rows) + 1.65), 1.0],
        hspace=0.16,
    )
    ax_top = fig.add_subplot(gs[0])
    ax_bot = fig.add_subplot(gs[1])

    ax_top.axis("off")
    tbl_frac = min(0.88, 10.0 / fig_w)
    tbl_x0   = (1.0 - tbl_frac) / 2
    _add_trace_heading(fig, ctx, x=tbl_x0, y=0.92)
    _draw_alignment_table(ax_top, rows,
                          bbox=[tbl_x0, 0.04, tbl_frac, 0.66], font_size=9.4)

    draw_chevron_strip(ax_bot, nodes, fontsize=11)
    ax_bot.set_title("Trace Alignment", fontsize=FONT_TITLE, pad=7)

    legend_handles = [
        mpatches.Patch(facecolor=GREY_LIGHTER, edgecolor="black", linewidth=0.75,
                       label="Synchronous (conform)"),
        mpatches.Patch(facecolor=GREY_MED,  edgecolor="black", linewidth=0.75,
                       label="Move on Model (skipped)"),
        mpatches.Patch(facecolor=GREY_DARK,   edgecolor="black", linewidth=0.75,
                       label="Move on Log (extra)"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               bbox_to_anchor=(0.5, 0.025), ncol=3,
               fontsize=FONT_ANNOT, frameon=True, fancybox=False, edgecolor="#cccccc")
    fig.subplots_adjust(left=0.04, right=0.98, top=0.97, bottom=0.11, hspace=0.16)
    save_svg(fig, os.path.join(output_dir, "task34_flow_chart_table.svg"))


# ── Idiom 5: flow_chart_elaborate_table — BPMN + alignment table ──────────────

def task34_flow_chart_elaborate_table(ctx, model_path, output_dir):
    """BPMN diagram with per-node violation coloring (worst trace) + alignment table."""
    out_path = os.path.join(output_dir, "task34_flow_chart_elaborate_table.svg")

    if not model_path:
        render_empty_state_svg(out_path, "BPMN + Alignment Table",
                               "No process model provided.")
        return

    parsed = parse_bpmn_model(model_path)
    if not parsed.get("elements"):
        render_empty_state_svg(out_path, "BPMN + Alignment Table",
                               "Could not parse BPMN model.")
        return

    # Build activity → worst violation type mapping for this trace
    priority  = {"Move on Log": 3, "Move on Model": 2, "Mismatch Move": 1, "Synchronous": 0}
    act_status = {}
    for r in ctx["rows"]:
        act, mt = r["activity"], r["moveType"]
        if act and act != ">>":
            if priority[mt] > priority.get(act_status.get(act, "Synchronous"), 0):
                act_status[act] = mt

    def node_style_fn(eid, elem):
        name = elem.get("name", "")
        kind = elem.get("kind", "task")
        if kind != "task":
            return ("#F5F5F5", "#CCCCCC", 1.0, _C_DARK)
        mt = act_status.get(name)
        if mt == "Move on Model":  return (_C_LIGHT, "#888888", 1.5, _C_DARK)
        if mt == "Move on Log":    return (_C_MED,   "#555555", 1.5, "white")
        if mt == "Mismatch Move":  return (_C_DARK,  "#111111", 1.5, "white")
        if mt == "Synchronous":    return ("#F5F5F5", "#AAAAAA", 1.0, _C_DARK)
        return ("#FAFAFA", "#CCCCCC", 1.0, "#AAAAAA")   # not in this trace

    legend_items = [
        ("#F5F5F5", "#AAAAAA", 1.0, "Synchronous (conform)"),
        (_C_LIGHT,  "#888888", 1.5, "Move on Model (skipped)"),
        (_C_MED,    "#555555", 1.5, "Move on Log (extra)"),
        (_C_DARK,   "#111111", 1.5, "Mismatch Move"),
        ("#FAFAFA", "#CCCCCC", 1.0, "Not in trace"),
    ]
    summary = (f"{ctx['trace_label']}   |   "
               f"Fitness: {ctx['fitness']:.4f}   |   "
               f"Violations: {ctx['n_violations']}")

    compose_bpmn_panels(
        panels=[{"parsed": parsed, "node_style_fn": node_style_fn, "subtitle": summary}],
        out_path=out_path,
        title="BPMN Alignment — Violation Attribution",
        legend_items=legend_items,
        table_rows=_cell_text(ctx["rows"]),
        table_cols=_COL_LABELS,
    )


# ── Idiom 6: heatmap — top-20 traces × activities ─────────────────────────────

def task34_heatmap(ctxs, output_dir):
    """Heatmap: rows=worst traces, cols=activities, cell=violation count.
    Reveals which activities cause violations across which traces."""
    if not ctxs:
        _no_violations(output_dir, "heatmap")
        return

    show = ctxs[:20]

    # Activities that appear as violations
    act_set = {r["activity"]
               for ctx in show
               for r in ctx["rows"]
               if _is_violation(r) and r["activity"] != ">>"}
    if not act_set:
        _no_violations(output_dir, "heatmap")
        return

    act_total = {a: sum(1 for ctx in show for r in ctx["rows"]
                        if r["activity"] == a and _is_violation(r))
                 for a in act_set}
    acts = sorted(act_set, key=lambda a: act_total[a], reverse=True)

    matrix = np.zeros((len(show), len(acts)), dtype=float)
    act_idx = {a: i for i, a in enumerate(acts)}
    for ti, ctx in enumerate(show):
        for r in ctx["rows"]:
            a = r["activity"]
            if a in act_idx and _is_violation(r):
                matrix[ti, act_idx[a]] += 1

    trace_labels = [f"Trace {c['trace_index']+1} (f={c['fitness']:.2f})"
                    for c in show]

    fig_w = max(10.0, len(acts) * 0.7 + 3.5)
    fig_h = max(4.5,  len(show) * 0.38 + 2.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    draw_value_heatmap(fig, ax, matrix,
                       row_labels=trace_labels,
                       col_labels=acts,
                       rotate_xticks=45)
    ax.set_title(
        f"Violation Count per Activity — Top {len(show)} Most Violated Traces",
        fontsize=FONT_TITLE, pad=9,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_heatmap.svg"))


# ── Idiom 7: table_bar_chart — trace summary table + log-level bar chart ──────

def task34_table_bar_chart(ctxs, log_act_v, output_dir):
    """Left panel: top-10 worst traces (table).
    Right panel: violated activities in the worst trace (bar chart, colored by dominant type)."""
    if not ctxs:
        _no_violations(output_dir, "table_bar_chart")
        return

    show     = ctxs[:10]
    worst    = ctxs[0]
    act_v    = _trace_activity_violations(worst["rows"])
    if not act_v:
        _no_violations(output_dir, "table_bar_chart")
        return

    totals   = {a: sum(v.values()) for a, v in act_v.items()}
    top_acts = sorted(totals, key=lambda a: totals[a], reverse=True)[:15]
    counts   = [totals[a] for a in top_acts]

    def _dom_color(a):
        v = act_v[a]
        dom = max(v, key=v.get)
        return {"mom": _C_LIGHT, "mol": _C_MED, "mismatch": _C_DARK}[dom]

    colors = [_dom_color(a) for a in top_acts]

    fig_h = max(5.0, max(len(show), len(top_acts)) * 0.38 + 3.0)
    fig   = plt.figure(figsize=(20, fig_h), layout="constrained")
    gs    = gridspec.GridSpec(1, 2, width_ratios=[1, 1.6], figure=fig)
    ax_tbl = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    # ── Left: trace summary table ──
    ax_tbl.axis("off")
    tbl_data = [
        [c["trace_label"], f"{c['fitness']:.4f}", str(c["n_violations"])]
        for c in show
    ]
    tbl = ax_tbl.table(
        cellText=tbl_data,
        colLabels=["Trace", "Fitness", "Violations"],
        colWidths=[0.38, 0.32, 0.30],
        cellLoc="center",
        bbox=[0.02, 0.04, 0.96, 0.86],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(FONT_ANNOT)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#e0e0e0")
        if r == 0:
            cell.set_facecolor(_HDR_BG)
            cell.set_text_props(color="white")
        else:
            cell.set_facecolor("#f5f5f5" if r % 2 == 0 else "white")
            cell.set_text_props(color=_C_DARK)
    ax_tbl.set_title(f"Top {len(show)} Most Violated Traces",
                     fontsize=FONT_TITLE, pad=8)

    # ── Right: bar chart (one bar per activity, colored by dominant type) ──
    ax_bar.set_facecolor("#fafbfc")
    y     = range(len(top_acts))
    bar_h = 0.45
    bars  = ax_bar.barh(y, counts, color=colors, edgecolor="white",
                        linewidth=0.8, height=bar_h)

    for i, (bar, cnt) in enumerate(zip(bars, counts)):
        ax_bar.text(bar.get_width() + max(counts) * 0.015, i,
                    f"{cnt:,}", va="center", fontsize=FONT_ANNOT, color=_C_DARK)

    ax_bar.set_yticks(list(y))
    ax_bar.set_yticklabels(top_acts, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    pad = max(0.8, bar_h)
    ax_bar.set_ylim(len(top_acts) - 1 + pad, -pad)
    ax_bar.set_xlabel("Violation count", fontsize=FONT_LABEL)
    ax_bar.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax_bar.set_xlim(0, max(counts) * 1.2)
    ax_bar.set_title(
        f"Violated Activities — {worst['trace_label']}  (fitness = {worst['fitness']:.4f})",
        fontsize=FONT_TITLE, pad=8,
    )
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.3, zorder=0)
    ax_bar.set_axisbelow(True)

    legend_handles = [
        mpatches.Patch(color=_C_LIGHT, label="Move on Model (dominant)"),
        mpatches.Patch(color=_C_MED,   label="Move on Log (dominant)"),
        mpatches.Patch(color=_C_DARK,  label="Mismatch Move (dominant)"),
    ]
    ax_bar.legend(handles=legend_handles, loc="lower right", fontsize=FONT_ANNOT,
                  frameon=True, fancybox=False, edgecolor="#cccccc")

    save_svg(fig, os.path.join(output_dir, "task34_table_bar_chart.svg"))


# ── Idiom 8: flow_chart_basic — standalone chevron ───────────────────────────

def task34_flow_chart_basic(ctx, output_dir):
    """Chevron strip only — worst trace alignment without the detail table."""
    rows  = ctx["rows"]
    nodes = _chevron_nodes(rows)
    fig_w = max(14.0, chevron_figure_width(nodes))
    fig, ax = plt.subplots(figsize=(fig_w, 3.8))
    draw_chevron_strip(ax, nodes, fontsize=11)
    ax.set_title(
        f"Trace Alignment — {ctx['trace_label']}  "
        f"(fitness = {ctx['fitness']:.4f}, violations = {ctx['n_violations']})",
        fontsize=FONT_TITLE, pad=8,
    )
    legend_handles = [
        mpatches.Patch(facecolor=GREY_LIGHTER, edgecolor="black", linewidth=0.75,
                       label="Synchronous (conform)"),
        mpatches.Patch(facecolor=GREY_MED,  edgecolor="black", linewidth=0.75,
                       label="Move on Model (skipped)"),
        mpatches.Patch(facecolor=GREY_DARK,   edgecolor="black", linewidth=0.75,
                       label="Move on Log (extra)"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               bbox_to_anchor=(0.5, 0.01), ncol=3,
               fontsize=FONT_ANNOT, frameon=True, fancybox=False, edgecolor="#cccccc")
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_flow_chart_basic.svg"))


# ── Idiom 9: flow_chart_elaborate — standalone BPMN ──────────────────────────

def task34_flow_chart_elaborate(ctx, model_path, output_dir):
    """BPMN diagram with per-node violation coloring — no alignment table."""
    out_path = os.path.join(output_dir, "task34_flow_chart_elaborate.svg")
    if not model_path:
        render_empty_state_svg(out_path, "BPMN Violation Overview",
                               "No process model provided.")
        return
    parsed = parse_bpmn_model(model_path)
    if not parsed.get("elements"):
        render_empty_state_svg(out_path, "BPMN Violation Overview",
                               "Could not parse BPMN model.")
        return

    priority  = {"Move on Log": 3, "Move on Model": 2, "Mismatch Move": 1, "Synchronous": 0}
    act_status = {}
    for r in ctx["rows"]:
        act, mt = r["activity"], r["moveType"]
        if act and act != ">>":
            if priority[mt] > priority.get(act_status.get(act, "Synchronous"), 0):
                act_status[act] = mt

    def node_style_fn(eid, elem):
        name = elem.get("name", "")
        kind = elem.get("kind", "task")
        if kind != "task":
            return ("#F5F5F5", "#CCCCCC", 1.0, _C_DARK)
        mt = act_status.get(name)
        if mt == "Move on Model":  return (_C_LIGHT, "#888888", 1.5, _C_DARK)
        if mt == "Move on Log":    return (_C_MED,   "#555555", 1.5, "white")
        if mt == "Mismatch Move":  return (_C_DARK,  "#111111", 1.5, "white")
        if mt == "Synchronous":    return ("#F5F5F5", "#AAAAAA", 1.0, _C_DARK)
        return ("#FAFAFA", "#CCCCCC", 1.0, "#AAAAAA")

    legend_items = [
        ("#F5F5F5", "#AAAAAA", 1.0, "Synchronous (conform)"),
        (_C_LIGHT,  "#888888", 1.5, "Move on Model (skipped)"),
        (_C_MED,    "#555555", 1.5, "Move on Log (extra)"),
        (_C_DARK,   "#111111", 1.5, "Mismatch Move"),
        ("#FAFAFA", "#CCCCCC", 1.0, "Not in trace"),
    ]
    summary = (f"{ctx['trace_label']}   |   Fitness: {ctx['fitness']:.4f}"
               f"   |   Violations: {ctx['n_violations']}")
    compose_bpmn_panels(
        panels=[{"parsed": parsed, "node_style_fn": node_style_fn, "subtitle": summary}],
        out_path=out_path,
        title="BPMN Alignment — Violation Overview",
        legend_items=legend_items,
    )


# ── Co-occurrence helper (used by matrix) ────────────────────────────────────

def _build_activity_cooccurrence(alignments):
    """Return (act_freqs, cooccur) where cooccur[(a,b)] = traces both violated."""
    act_freqs = {}
    cooccur   = {}
    for result in alignments:
        rows    = _parse_alignment(result)
        act_set = {r["activity"] for r in rows
                   if _is_violation(r) and r["activity"] != ">>"}
        for a in act_set:
            act_freqs[a] = act_freqs.get(a, 0) + 1
        acts = sorted(act_set)
        for i, a in enumerate(acts):
            for b in acts[i + 1:]:
                key = (a, b)
                cooccur[key] = cooccur.get(key, 0) + 1
    return act_freqs, cooccur


# ── Idiom 10: matrix — activity co-occurrence matrix ─────────────────────────

def task34_matrix(act_freqs, cooccur, output_dir):
    """Square matrix: rows/cols = violated activities, cell = traces both violated."""
    if len(act_freqs) < 2:
        _no_violations(output_dir, "matrix")
        return

    acts = sorted(act_freqs, key=lambda a: act_freqs[a], reverse=True)[:12]
    n    = len(acts)
    idx  = {a: i for i, a in enumerate(acts)}
    mat  = np.zeros((n, n), dtype=float)
    for i, a in enumerate(acts):
        mat[i, i] = float(act_freqs[a])
    for (a, b), cnt in cooccur.items():
        if a in idx and b in idx:
            mat[idx[a], idx[b]] = float(cnt)
            mat[idx[b], idx[a]] = float(cnt)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.9), max(6, n * 0.8)))
    ax.imshow(mat, cmap=_CMAP, aspect="auto", vmin=0)
    ax.set_xticks(range(n))
    ax.set_xticklabels(acts, rotation=40, ha="right", fontsize=FONT_ANNOT)
    ax.set_yticks(range(n))
    ax.set_yticklabels(acts, fontsize=FONT_ANNOT)

    thresh = mat.max() / 2.0
    for i in range(n):
        for j in range(n):
            val   = int(mat[i, j])
            color = "white" if mat[i, j] > thresh else _C_DARK
            ax.text(j, i, str(val), ha="center", va="center",
                    fontsize=max(FONT_ANNOT - 1, 6), color=color, fontweight="bold")

    ax.set_title(
        "Activity Co-occurrence Matrix\n"
        "(diagonal = individual violation frequency  ·  off-diagonal = traces both violated)",
        fontsize=FONT_TITLE,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_matrix.svg"))


# ── Idiom 11: parallel_sets — violation type × activity ──────────────────────

def task34_parallel_sets(log_act_v, output_dir):
    """Parallel sets: left = violation type, right = violated activity.
    Ribbon width = count of (type, activity) pairs across all traces."""
    if not log_act_v:
        _no_violations(output_dir, "parallel_sets")
        return

    vtypes = ["Move on Model", "Move on Log", "Mismatch Move"]
    vkeys  = ["mom", "mol", "mismatch"]
    top_acts = sorted(log_act_v, key=lambda a: sum(log_act_v[a].values()),
                      reverse=True)[:10]
    if not top_acts:
        _no_violations(output_dir, "parallel_sets")
        return

    matrix = np.array([[log_act_v[a].get(k, 0) for a in top_acts]
                        for k in vkeys], dtype=float)
    if matrix.sum() == 0:
        _no_violations(output_dir, "parallel_sets")
        return

    vtype_colors = [_C_LIGHT, _C_MED, _C_DARK]
    act_greys    = [plt.cm.Greys(0.15 + 0.65 * i / max(len(top_acts) - 1, 1))
                    for i in range(len(top_acts))]
    act_colors   = [f"#{int(c[0]*255):02x}{int(c[1]*255):02x}{int(c[2]*255):02x}"
                    for c in act_greys]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_facecolor("#fafbfc")
    draw_parallel_sets(
        ax,
        left_labels=vtypes,
        right_labels=top_acts,
        matrix=matrix,
        left_colors=vtype_colors,
        right_colors=act_colors,
        left_title="Violation Type",
        right_title="Activity",
    )
    ax.set_title(
        "Violation Type × Activity  (ribbon width = violation count)",
        fontsize=FONT_TITLE, pad=8,
    )
    ax.axis("off")
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_parallel_sets.svg"))


# ── Ground truth ─────────────────────────────────────────────────────────────

def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """mc-multi: which activities have violations in the worst-fitness trace.

    Correct options  = activities with at least one violation in the
                       representative trace (worst by violation count, then
                       fitness), labelled with their dominant violation type.
    Incorrect options = activities that appear synchronously (no violations)
                       in the same trace, used as distractors.
    """
    import random as _rnd

    if answer_format != "mc-multi":
        return {"options": []}
    if not alignments:
        return {"options": []}

    ctxs = _build_contexts(alignments, max_traces=30)
    if not ctxs:
        return {"options": []}

    rows = ctxs[0]["rows"]
    act_counts = _trace_activity_violations(rows)
    if not act_counts:
        return {"options": []}

    conformant_acts = sorted(
        {r["activity"] for r in rows
         if not _is_violation(r) and r["activity"] != ">>"}
        - set(act_counts.keys())
    )

    _DOM_LABEL = {
        "mom":      "Move on Model — skipped activity",
        "mol":      "Move on Log — extra activity",
        "mismatch": "Mismatch Move — wrong activity",
    }

    options = []

    # Correct: all violated activities, most-violated first (cap at 10)
    for act in sorted(act_counts, key=lambda a: sum(act_counts[a].values()), reverse=True)[:10]:
        dom_key = max(act_counts[act], key=act_counts[act].get)
        options.append({
            "label":   f"'{act}' — {_DOM_LABEL[dom_key]}",
            "value":   f"violated::{act}",
            "correct": True,
        })

    # Incorrect: conformant activities from the same trace (cap at 5)
    for act in conformant_acts[:5]:
        options.append({
            "label":   f"'{act}' — no violation",
            "value":   f"conformant::{act}",
            "correct": False,
        })

    _rnd.Random(42).shuffle(options)
    return {"options": options}


# ── Public API ────────────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None):
    """Generate all Task 34 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 34 visualizations ---")

    if not alignments:
        logger.warning("      Skipped Task 34: no alignments.")
        for k in IDIOMS:
            _no_violations(output_dir, k)
        return

    ctxs = _build_contexts(alignments, max_traces=30)
    if not ctxs:
        logger.warning("      Skipped Task 34: no alignment steps found.")
        for k in IDIOMS:
            _no_violations(output_dir, k)
        return

    worst    = ctxs[0]
    log_act  = _log_activity_violations(alignments)
    act_freq, cooccur = _build_activity_cooccurrence(alignments)

    logger.info(
        f"      Representative: {worst['trace_label']} "
        f"(fitness={worst['fitness']:.4f}, violations={worst['n_violations']})"
    )

    task34_bar_chart(worst,                         output_dir)
    task34_stacked_bar(worst,                       output_dir)
    task34_table(worst,                             output_dir)
    task34_flow_chart_basic(worst,                  output_dir)
    task34_flow_chart_table(worst,                  output_dir)
    task34_flow_chart_elaborate(worst,              model_path, output_dir)
    task34_flow_chart_elaborate_table(worst,        model_path, output_dir)
    task34_heatmap(ctxs[:20],                       output_dir)
    task34_matrix(act_freq, cooccur,                output_dir)
    task34_parallel_sets(log_act,                   output_dir)
    task34_table_bar_chart(ctxs, log_act,           output_dir)
