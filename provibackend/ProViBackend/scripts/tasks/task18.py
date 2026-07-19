"""
tasks/task18.py – Task ID 18: Explain / Derive / Reasons for guideline violations
(event-/activity-level responsibility).

Goal **Explain** / Means **Derive** / Characteristics *Reasons for guideline
violations*:
    "Which events are responsible for guideline violations in one or more traces?
     Reasons are not known previously, but deduced by the analyst."

The event/activity-centric member of the Reasons family. Distinct from its
siblings: ID 13 (attribute-centric, `task13.py`), ID 20 (decision tree,
`task20.py`), ID 21 (exploratory composite, `task21.py`). Here the unit is the
**activity / move**: which activities are *responsible* for the violations,
deduced from the alignment data. The **flow idioms are the centerpiece** (the
"which events" question maps naturally onto the process); the statistical idioms
support them.

Design (settled):
  * Unit = (activity, move-type). Reuses task29's violation classification
    primitive (`shared.alignment_pairs_to_rows`). Per (activity, move-type) we
    compute its **responsibility share** = contribution to all violations (count
    and % of total) plus the number of distinct traces it affects. Alignments are
    never re-run.
  * Attribute context (the "deduced" part): for each responsible activity, one
    dominant attribute context of the traces in which it is violated, reusing
    task13's per-trace attribute evidence frame (e.g. "model-move on A_FINALIZED
    occurs mostly in high-AMOUNT_REQ cases"). Lightweight: one dominant attribute
    per responsible activity. Omitted gracefully when no attributes are present.
  * Top-N responsible activities by responsibility share (TOP_N).

Scope = the 7 "High" idioms. Stems → canonical slug after the pipeline rename:
    task18_flow_chart_elaborate_bpmn_table.svg → flow_chart_elaborate_table  (LEAD: model + responsibility)
    task18_flow_chart_and_table.svg            → flow_chart_table            (chevron + responsibility table)
    task18_bar_chart.svg                       → bar_chart
    task18_scatter_plot.svg                    → scatterplot
    task18_table.svg                           → table
    task18_table_and_bar_chart.svg             → table_bar_chart
    task18_parallel_sets.svg                   → parallel_sets

Public API:
    generate(log, alignments, model_path, output_dir, candidate_attributes=None)
    task18_responsibility(log, alignments, candidate_attributes)  # reused by task21
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_elaborate_table", "flow_chart_table", "bar_chart",
          "scatter_plot", "table", "table_bar_chart", "parallel_sets"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets, render_empty_state_svg,
    alignment_pairs_to_rows, chevron_nodes_from_alignment_rows, draw_chevron_strip,
    chevron_figure_width, parse_bpmn_model, compose_bpmn_panels,
    contrasting_text_color, place_scatter_labels,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse: violation label + per-trace features.
from tasks.task20 import task20_trace_feature_dataframe
# Reuse: candidate-attribute evidence frame + default candidate set (attribute context).
from tasks.task13 import _build_evidence_frame, discover_candidate_attributes
# Reuse: representative-trace picker for the chevron flow idiom.
from tasks.task28 import build_task28_context


TOP_N = 12   # responsible activities kept where an idiom would otherwise crowd

# Move-type palette (matches task29).
_MOVE_COLORS = {"Model Move": GREY_MED, "Log Move": GREY_DARK, "Mismatch Move": GREY_LIGHT}

_EMPTY_STEMS = [
    ("task18_flow_chart_elaborate_bpmn_table.svg", "Responsible Activities on the Model"),
    ("task18_flow_chart_and_table.svg",            "Violation Flow & Responsible Activities"),
    ("task18_bar_chart.svg",                       "Responsibility Share by Activity"),
    ("task18_scatter_plot.svg",                    "Activity Occurrence vs. Violation Involvement"),
    ("task18_table.svg",                           "Responsible Activities"),
    ("task18_table_and_bar_chart.svg",             "Responsible Activities"),
    ("task18_parallel_sets.svg",                   "Activity vs. Move-type"),
]


# ---------------------------------------------------------------------------
# Responsibility aggregation (reuses task29's (activity, move-type) classification)
# ---------------------------------------------------------------------------

def _violation_activity_rows(alignments):
    """Flat list of {trace_index, activity, move_type} for every violation move."""
    rows = []
    for i, result in enumerate(alignments):
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            mt = step["moveType"]
            if mt == "Synchronous Move":
                continue
            activity = step["model_move"] if mt == "Model Move" else step["log_move"]
            if not activity or str(activity) in {"-", "None", "(skip)"}:
                continue
            rows.append({"trace_index": i, "activity": str(activity), "move_type": mt})
    return rows


def _activity_log_stats(log):
    """Per activity: total event occurrences + #traces containing it."""
    occ, contain = {}, {}
    for trace in log:
        seen = set()
        for ev in trace:
            a = ev.get("concept:name")
            if a is None:
                continue
            a = str(a)
            occ[a] = occ.get(a, 0) + 1
            seen.add(a)
        for a in seen:
            contain[a] = contain.get(a, 0) + 1
    return occ, contain


def _dominant_context(affected_traces, evidence_df, attr_meta):
    """One short dominant-attribute phrase for the traces a responsibility row hits.

    Numeric attribute → "high/low <attr>" by mean vs. overall mean (signal = |z|);
    categorical → "<attr>=<mode>" (signal = modal fraction). The attribute with the
    strongest signal wins. Returns "—" when no attributes are available."""
    if not attr_meta or not affected_traces:
        return "—"
    sub = evidence_df[evidence_df["trace_index"].isin(affected_traces)]
    if sub.empty:
        return "—"
    best = None
    for m in attr_meta:
        col = m["col"]
        if m["type"] == "numeric":
            allv = pd.to_numeric(evidence_df[col], errors="coerce")
            subv = pd.to_numeric(sub[col], errors="coerce")
            std = allv.std(skipna=True)
            if not std or np.isnan(std) or subv.notna().sum() == 0:
                continue
            signal = abs((subv.mean() - allv.mean()) / (std + 1e-9))
            phrase = f"{'high' if subv.mean() > allv.mean() else 'low'} {m['label']}"
        else:
            subv = sub[col].dropna().astype(str)
            if subv.empty:
                continue
            mode = subv.mode().iloc[0]
            signal = float((subv == mode).mean())
            phrase = f"{m['label']}={mode}"
        if best is None or signal > best[0]:
            best = (signal, phrase)
    return best[1] if best else "—"


def task18_responsibility(log, alignments, candidate_attributes=None):
    """Build the responsibility table + supporting context.

    Returns a dict:
        records   – list of per-(activity, move-type) dicts ranked by share:
                    {activity, move_type, n_violations, pct, n_traces, traces(set), context}
        total     – total number of violation moves
        occ       – {activity: #event occurrences in log}
        contain   – {activity: #traces containing the activity}
        has_attrs – whether an attribute context column is available
    Reused by task21 (exploratory composite) for the event candidates.
    """
    rows = _violation_activity_rows(alignments)
    occ, contain = _activity_log_stats(log)

    # Attribute evidence frame (reused from task13) for the dominant context.
    attr_meta, evidence_df = [], None
    feat = task20_trace_feature_dataframe(log, alignments)
    if feat is not None and not feat.empty:
        if candidate_attributes is None:
            candidate_attributes = discover_candidate_attributes(log, feat)
        evidence_df, attr_meta = _build_evidence_frame(log, feat, candidate_attributes)

    if not rows:
        return {"records": [], "total": 0, "occ": occ, "contain": contain,
                "has_attrs": bool(attr_meta)}

    df = pd.DataFrame(rows)
    total = len(df)
    grouped = df.groupby(["activity", "move_type"])
    trace_sets = grouped["trace_index"].apply(set)

    records = []
    for (activity, move_type), affected in trace_sets.items():
        n_viol = len(df[(df["activity"] == activity) & (df["move_type"] == move_type)])
        records.append({
            "activity": activity,
            "move_type": move_type,
            "n_violations": int(n_viol),
            "pct": n_viol / total * 100 if total else 0.0,
            "n_traces": len(affected),
            "traces": affected,
            "context": _dominant_context(affected, evidence_df, attr_meta) if attr_meta else "—",
        })
    records.sort(key=lambda r: r["n_violations"], reverse=True)
    return {"records": records, "total": total, "occ": occ, "contain": contain,
            "has_attrs": bool(attr_meta)}


def _activity_share_map(records):
    """activity -> responsibility share in [0,1], max-normalized over activities
    (summed across move-types). Drives the elaborate-model colour intensity."""
    by_activity = {}
    for r in records:
        by_activity[r["activity"]] = by_activity.get(r["activity"], 0) + r["n_violations"]
    if not by_activity:
        return {}
    top = max(by_activity.values())
    return {a: (n / top if top else 0.0) for a, n in by_activity.items()}


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def _responsibility_table_data(records, has_attrs, top_n=TOP_N):
    """(cell_text, col_labels, col_widths) for the responsibility table. The
    dominant-attribute-context column is omitted when no attributes are present."""
    recs = records[:top_n]
    if has_attrs:
        col_labels = ["Activity", "Move type", "#Viol.", "% of all", "#Traces", "Dominant attribute context"]
        col_widths = [0.24, 0.15, 0.09, 0.10, 0.09, 0.33]
        cell_text = [[r["activity"], r["move_type"], str(r["n_violations"]),
                      f"{r['pct']:.1f}%", str(r["n_traces"]), r["context"]] for r in recs]
    else:
        col_labels = ["Activity", "Move type", "#Viol.", "% of all", "#Traces"]
        col_widths = [0.32, 0.20, 0.14, 0.16, 0.18]
        cell_text = [[r["activity"], r["move_type"], str(r["n_violations"]),
                      f"{r['pct']:.1f}%", str(r["n_traces"])] for r in recs]
    return cell_text, col_labels, col_widths


def _responsibility_node_style(share_map):
    """node_style_fn colouring each task by responsibility share (white → dark grey)."""
    def _style(eid, elem):
        if elem.get("kind") == "task":
            name = elem.get("name", "")
            s = share_map.get(name, 0.0)
            if s > 0:
                shade = int(round(225 - 160 * min(s, 1.0)))   # 225 (light) .. 65 (dark)
                fill = f"#{shade:02x}{shade:02x}{shade:02x}"
                return (fill, "#333333", 3, contrasting_text_color(fill))
        return ("white", "#888888", 2, "#333333")
    return _style


# ---------------------------------------------------------------------------
# Idiom renderers
# ---------------------------------------------------------------------------

def task18_flow_chart_elaborate_bpmn_table(resp, model_path, output_dir):
    """LEAD idiom: desired model with responsible activities highlighted
    (intensity = responsibility share) + top-responsibility table.
    Stem → canonical slug 'flow_chart_elaborate_table'."""
    path = os.path.join(output_dir, "task18_flow_chart_elaborate_bpmn_table.svg")
    records = resp["records"]
    if not records or not model_path:
        render_empty_state_svg(path, "Responsible Activities on the Model",
                               "No violations or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task18: BPMN parse failed: {e}")
        render_empty_state_svg(path, "Responsible Activities on the Model",
                               "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, "Responsible Activities on the Model",
                               "No BPMN geometry to render.")
        return

    share_map = _activity_share_map(records)
    cell_text, col_labels, _ = _responsibility_table_data(records, resp["has_attrs"])
    panels = [{
        "parsed": parsed,
        "node_style_fn": _responsibility_node_style(share_map),
        "subtitle": "Responsible activities (darker = higher responsibility share)",
    }]
    compose_bpmn_panels(
        panels,
        path,
        title="Which Activities Are Responsible for the Violations",
        legend_items=[
            ("#414141", "#333333", 3, "High responsibility"),
            ("#c8c8c8", "#333333", 3, "Lower responsibility"),
            ("white",   "#888888", 2, "Not responsible"),
        ],
        table_rows=cell_text,
        table_cols=col_labels,
    )


def task18_flow_chart_and_table(resp, ctx, output_dir):
    """Chevron of a representative violating trace (responsible events marked by the
    move-type palette) + the responsibility table.
    Stem 'flow_chart_and_table' → canonical slug 'flow_chart_table'."""
    path = os.path.join(output_dir, "task18_flow_chart_and_table.svg")
    records = resp["records"]
    if ctx is None or not records:
        render_empty_state_svg(path, "Violation Flow & Responsible Activities",
                               "No usable alignment / no violations.")
        return

    nodes = chevron_nodes_from_alignment_rows(ctx["rows"])
    cell_text, col_labels, col_widths = _responsibility_table_data(records, resp["has_attrs"])

    fig_w = max(14.0, chevron_figure_width(nodes))
    fig_h = max(7.0, 3.4 + min(len(records), TOP_N) * 0.5)
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.0, max(1.4, 0.5 * min(len(records), TOP_N) + 0.8)],
                           hspace=0.30)

    ax_flow = fig.add_subplot(gs[0])
    draw_chevron_strip(ax_flow, nodes, fontsize=10)
    ax_flow.set_title(
        f"Representative Violating Trace ({ctx['trace_label']}, fitness={ctx['fitness']:.3f})",
        fontsize=FONT_TITLE, pad=6)

    ax_tab = fig.add_subplot(gs[1])
    ax_tab.axis("off")
    make_table(ax_tab, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.03, 0.05, 0.94, 0.84], col_widths=col_widths,
               font_size=9, cell_pad=0.07)
    ax_tab.set_title("Responsible Activities (ranked by responsibility share)",
                     fontsize=FONT_TITLE, pad=6)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task18_bar_chart(resp, output_dir):
    """Top-N activities ranked by responsibility share (Y = % of all violations)."""
    path = os.path.join(output_dir, "task18_bar_chart.svg")
    records = resp["records"][:TOP_N]
    if not records:
        render_empty_state_svg(path, "Responsibility Share by Activity", "No violations found.")
        return
    labels = [f"{r['activity']}\n({r['move_type'].split()[0]})" for r in records]
    pct = [r["pct"] for r in records]
    colors = [_MOVE_COLORS.get(r["move_type"], GREY_MED) for r in records]

    fig, ax = plt.subplots(figsize=(max(9.0, len(records) * 1.05), 5.5))
    pos = np.arange(len(records))
    ax.bar(pos, pct, color=colors, edgecolor="white")
    for p, v in zip(pos, pct):
        ax.text(p, v + 0.4, f"{v:.1f}%", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)
    ax.set_xticks(pos)
    ax.set_xticklabels(labels, fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("% of all violations", fontsize=FONT_LABEL)
    ax.set_title("Activities Ranked by Responsibility Share", fontsize=FONT_TITLE)
    ax.legend(handles=[mpatches.Patch(color=c, label=mt) for mt, c in _MOVE_COLORS.items()],
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task18_scatter_plot(resp, output_dir):
    """One dot per activity: x = #occurrences in log, y = violation-involvement rate
    (#traces violated / #traces containing it); size & colour = responsibility share."""
    path = os.path.join(output_dir, "task18_scatter_plot.svg")
    records = resp["records"]
    occ, contain = resp["occ"], resp["contain"]
    if not records:
        render_empty_state_svg(path, "Activity Occurrence vs. Violation Involvement",
                               "No violations found.")
        return

    # Aggregate per activity across move-types.
    per_activity = {}
    for r in records:
        a = per_activity.setdefault(r["activity"], {"n_violations": 0, "traces": set()})
        a["n_violations"] += r["n_violations"]
        a["traces"] |= r["traces"]
    max_viol = max(a["n_violations"] for a in per_activity.values())

    xs, ys, sizes, shares, names = [], [], [], [], []
    for a, info in per_activity.items():
        x = occ.get(a, 0)
        cont = contain.get(a, 0)
        rate = (len(info["traces"]) / cont * 100) if cont else 0.0
        share = info["n_violations"] / max_viol if max_viol else 0.0
        xs.append(x); ys.append(rate); sizes.append(30 + share * 170)
        shares.append(share); names.append(a)

    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(xs, ys, s=sizes, c=shares, cmap="Greys", vmin=0, vmax=1,
                    edgecolors="#333333", linewidths=0.8, alpha=0.9)
    # Label the most responsible activities with cluster-aware, non-crossing callouts.
    labeled = sorted(zip(xs, ys, shares, names), key=lambda t: t[2], reverse=True)[:6]
    place_scatter_labels(ax, [(x, y, name) for x, y, _s, name in labeled])
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Responsibility share", fontsize=FONT_ANNOT)
    ax.set_xlabel("# Occurrences in log", fontsize=FONT_LABEL)
    ax.set_ylabel("Violation-involvement rate (%)", fontsize=FONT_LABEL)
    ax.set_title("Which Activities Are Disproportionately Responsible", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task18_table(resp, output_dir):
    """Activity | Move type | #Violations | % of all violations | #Traces affected |
    Dominant attribute context — ranked by responsibility share."""
    path = os.path.join(output_dir, "task18_table.svg")
    records = resp["records"]
    if not records:
        render_empty_state_svg(path, "Responsible Activities", "No violations found.")
        return
    cell_text, col_labels, col_widths = _responsibility_table_data(records, resp["has_attrs"])
    fig_h = max(3.0, 1.4 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    make_table(ax, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.05, 0.96, 0.84], col_widths=col_widths,
               font_size=9.5, cell_pad=0.08)
    ax.set_title("Responsible Activities (ranked by responsibility share)",
                 fontsize=FONT_TITLE, pad=10)
    save_svg(fig, path)


def task18_table_and_bar_chart(resp, output_dir):
    """Responsibility table (left) + adjacent responsibility-share bars (right)."""
    path = os.path.join(output_dir, "task18_table_and_bar_chart.svg")
    records = resp["records"][:TOP_N]
    if not records:
        render_empty_state_svg(path, "Responsible Activities", "No violations found.")
        return
    cell_text, col_labels, col_widths = _responsibility_table_data(records, resp["has_attrs"])

    fig = plt.figure(figsize=(17, max(3.4, 1.6 + len(records) * 0.5)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.7, 1.0], wspace=0.40)

    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    make_table(ax_t, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.05, 0.96, 0.84], col_widths=col_widths,
               font_size=9, cell_pad=0.07)
    ax_t.set_title("Responsible Activities (ranked)", fontsize=FONT_TITLE, pad=8)

    ax_b = fig.add_subplot(gs[1])
    labels = [f"{r['activity']} ({r['move_type'].split()[0]})" for r in records][::-1]
    pct = [r["pct"] for r in records][::-1]
    colors = [_MOVE_COLORS.get(r["move_type"], GREY_MED) for r in records][::-1]
    y = np.arange(len(labels))
    ax_b.barh(y, pct, color=colors, edgecolor="white")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
    ax_b.set_xlabel("% of all violations", fontsize=FONT_LABEL)
    for i, v in enumerate(pct):
        ax_b.text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=FONT_ANNOT - 1)
    ax_b.spines[["top", "right"]].set_visible(False)
    ax_b.set_title("Responsibility share", fontsize=FONT_TITLE, pad=8)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task18_parallel_sets(resp, output_dir):
    """Dimension 1 = responsible activity (top-N + 'Other'), Dimension 2 = move-type;
    ribbon width = violation count."""
    path = os.path.join(output_dir, "task18_parallel_sets.svg")
    records = resp["records"]
    if not records:
        render_empty_state_svg(path, "Activity vs. Move-type", "No violations found.")
        return

    # Per-activity totals to choose the top-N; everything else folds into "Other".
    by_activity = {}
    for r in records:
        by_activity[r["activity"]] = by_activity.get(r["activity"], 0) + r["n_violations"]
    top_activities = [a for a, _ in sorted(by_activity.items(), key=lambda t: t[1], reverse=True)[:TOP_N]]
    has_other = len(by_activity) > len(top_activities)
    left_labels = top_activities + (["Other"] if has_other else [])

    move_types = ["Model Move", "Log Move", "Mismatch Move"]
    present_moves = [mt for mt in move_types if any(r["move_type"] == mt for r in records)]
    matrix = np.zeros((len(left_labels), len(present_moves)))
    left_index = {a: i for i, a in enumerate(left_labels)}
    for r in records:
        li = left_index.get(r["activity"], left_index.get("Other"))
        if li is None:
            continue
        mj = present_moves.index(r["move_type"])
        matrix[li, mj] += r["n_violations"]

    fig, ax = plt.subplots(figsize=(10, max(6, len(left_labels) * 0.5 + 2)))
    ax.axis("off")
    left_colors = [GREY_MED if i % 2 == 0 else GREY_LIGHT for i in range(len(left_labels))]
    right_colors = [_MOVE_COLORS.get(mt, GREY_MED) for mt in present_moves]
    draw_parallel_sets(
        ax, left_labels, present_moves, matrix, left_colors,
        right_colors=right_colors,
        left_title="Responsible activity", right_title="Move type",
    )
    # Title above the column headers (which draw_parallel_sets places at y=1.08).
    fig.suptitle("Responsible Activities by Move-type (ribbon = violation count)",
                 fontsize=FONT_TITLE, y=0.99)
    fig.subplots_adjust(top=0.80)
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _emit_all_empty(output_dir, message: str):
    for fname, title in _EMPTY_STEMS:
        render_empty_state_svg(os.path.join(output_dir, fname), title, message)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, model_path, output_dir: str, candidate_attributes=None):
    """Generate all Task ID 18 SVGs into output_dir. Alignments are reused from the
    central run (never recomputed); the dominant-attribute context reuses task13's
    evidence frame."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 18 visualizations ---")

    if not log or not alignments:
        logger.warning("      task18: empty log / alignments — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No log or alignment data available.")
        return

    resp = task18_responsibility(log, alignments, candidate_attributes)
    if not resp["records"]:
        logger.warning("      task18: no guideline violations — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No guideline violations — no responsible activities.")
        return

    logger.info(f"      task18: {len(resp['records'])} (activity, move-type) responsibility "
                f"rows over {resp['total']} violation moves; attribute context "
                f"{'on' if resp['has_attrs'] else 'off'}.")

    ctx = build_task28_context(alignments)

    # Flow idioms (centerpiece) first, then the supporting statistical idioms.
    task18_flow_chart_elaborate_bpmn_table(resp, model_path, output_dir)
    task18_flow_chart_and_table(resp, ctx, output_dir)
    task18_bar_chart(resp, output_dir)
    task18_scatter_plot(resp, output_dir)
    task18_table(resp, output_dir)
    task18_table_and_bar_chart(resp, output_dir)
    task18_parallel_sets(resp, output_dir)
