"""
tasks/task04.py – Task ID 4: Describe / Compare / Conformance across individual traces.

Task 4 asks "How does the degree of conformance differ between multiple logs or
traces?". Every idiom shows the *same* concrete traces (individual traces, NOT
aggregated variants) with their conformance fitness, just encoded differently, so
no idiom exposes more information than another (information equivalence):

    * bar_chart        – one uniform-coloured bar per trace, fitness on the y-axis
    * table            – Trace | Fitness, one row per trace
    * line_graph       – fitness profile across the sampled traces
    * table_bar_chart  – Trace | Fitness table + adjacent per-trace fitness bars
    * matrix           – trace × Fitness grid, colour + numeric annotation
    * heatmap          – trace × Fitness grid, continuous colour (no annotation)

Fitness is rounded to 3 decimals in every idiom; there is no #Traces column, no
conformant/non-conformant colour coding, and no pre-computed differences — the
participant derives the conformance assessment from the fitness values.

Public API:
    generate(log, fitness_df, output_dir, trace_ids=None)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
        trace_ids  – optional list of case-id strings to show (default: first 10)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_basic", "flow_chart_elaborate",
          "bar_chart", "table",
          "line_graph", "table_bar_chart",
          "matrix", "heatmap"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 4)
#
# Task 4 (MANUAL): compare the trace-level conformance PATTERNS of two traces. By
# default the two traces with the largest violation-count gap are shown; the admin
# can override the selection (and pick more than two). The participant answers in
# free text, comparing where each trace conforms to or deviates from the guideline;
# grading is against the static RUBRIC.
# ---------------------------------------------------------------------------
GT_TIER = "MANUAL"

PARAM_SPEC = [
    {
        "key": "trace_ids",
        "label": "Specific traces to compare (optional; default = the two traces with the largest violation gap)",
        # Internal to reading the chart — the participant sees the traces directly.
        "hide_hint": True,
        "widget": "select-many",
        "source": "log.trace_ids",
        # Admin convenience: a checkbox that auto-selects one trace from each of
        # the first N distinct variants. Handled in the specify-page select-many UI.
        "variant_autoselect": True,
        "autoselect_count": 2,
        "default": [],
        "required": False,
        "optional_hint": "(optional — leave empty to compare the two traces with the largest violation gap)",
    },
]

ANSWER_FORMATS = [
    {"key": "free-text", "gt_shape": "reference", "decisive_default": True},
]

RUBRIC = (
    "A complete answer compares the two traces' conformance patterns. For each "
    "trace it identifies where the execution conforms to the guideline and where "
    "it deviates — an activity skipped relative to the model (move on model) or an "
    "extra activity inserted (move on log) — and contrasts the two, e.g. 'Trace 1 "
    "is fully conformant, whereas Trace 2 skips Approve Treatment and inserts an "
    "extra step'. Award full marks for correctly naming the key deviation(s) in "
    "each trace and stating which trace is more conformant; partial marks for "
    "identifying the more-conformant trace without the specific deviations; deduct "
    "marks for misidentifying which trace conforms more."
)


def validate_params(log, params) -> list:
    """trace_ids is optional; the generic /specify validation already checks that
    each selected id exists in the dataset, so nothing task-specific is required."""
    return []


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, auto_col_widths, draw_value_heatmap,
    alignment_pairs_to_rows, chevron_nodes_from_alignment_rows,
    draw_chevron_strip, chevron_figure_width,
    parse_bpmn_model, compose_bpmn_panels, render_empty_state_svg,
    contrasting_text_color,
    GREY_MED, GREY_LIGHTER, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Default number of traces to sample when the admin doesn't pick specific ones.
SAMPLE_N = 2

# Single uniform bar/line colour — no conformant / non-conformant distinction.
_TRACE_COLOR = GREY_MED

# Consistent figure title across every idiom.
TITLE = "Trace Conformance Fitness"

# Activity-name font in the chevron flow chart. The chevron width has a fixed
# margin on top of its per-character allowance, so realistic activity names stay
# inside the arrow at 13pt; the shared auto-shrink still catches any outlier.
# Bump here to retune.
_CHEVRON_FONT = 13


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task04_build_trace_df(log, fitness_df: pd.DataFrame, trace_ids=None,
                           sample_n: int = SAMPLE_N) -> pd.DataFrame:
    """One row per concrete trace: a running ``label`` ("Trace 1".."Trace N"),
    the raw ``case_id``, and ``fitness`` (rounded 3 dp).

    ``trace_ids``: optional list of case-id strings. When given, exactly those
    traces are shown in that order (ids not present in the log are skipped).
    Otherwise the first ``sample_n`` traces in log order are used.

    Participants see the running ``label`` rather than the raw case id (which is
    noise to hunt for in the chart); the admin maps "Trace N → id" in the picker.
    The ``case_id`` column is kept for reference / debugging.
    """
    records = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        case_id = str(trace.attributes.get("concept:name", i))
        records.append({
            "trace_index": i,
            "case_id":     case_id,
            "fitness":     round(float(fitness_df.iloc[i]["fitness"]), 3),
        })

    cols = ["trace_index", "case_id", "fitness"]
    if not records:
        return pd.DataFrame(columns=cols + ["label"])

    if trace_ids:
        by_id = {}
        for r in records:
            by_id.setdefault(r["case_id"], r)  # first trace wins if case ids repeat
        chosen = [by_id[str(tid)] for tid in trace_ids if str(tid) in by_id]
        df = pd.DataFrame(chosen, columns=cols)
    else:
        df = pd.DataFrame(records[:sample_n], columns=cols)

    df = df.reset_index(drop=True)
    df["label"] = [f"Trace {i + 1}" for i in range(len(df))]
    return df


# Move-type palette (mirrors shared.chevron_nodes_from_alignment_rows) used for
# the chevron / flow-chart legend.
_MOVE_LEGEND = [
    ("Synchronous Move", GREY_LIGHTER),
    ("Model Move",       GREY_MED),
    ("Log Move",         GREY_DARK),
]


def _task04_case_index(log):
    """case_id (str) -> first trace index in the log."""
    idx = {}
    for i, trace in enumerate(log):
        cid = str(trace.attributes.get("concept:name", i))
        idx.setdefault(cid, i)
    return idx


def _task04_trace_violations(alignments, i):
    """(alignment rows, #violations) for trace index i. Violations = non-sync moves."""
    rows = alignment_pairs_to_rows(alignments[i].get("alignment", [])) if i < len(alignments) else []
    viol = sum(1 for r in rows if r["moveType"] != "Synchronous Move")
    return rows, viol


def _task04_select_compare_traces(log, alignments, fitness_df, trace_ids=None, n=2):
    """Pick the traces to compare, as a list of dicts
    {label, case_id, fitness, rows, violations}.

    Admin-selected ``trace_ids`` are used in order when given. Otherwise two
    "complete" traces (those covering the most distinct activities, so the chevron
    strips are substantial rather than trivially short) are chosen such that their
    fitness differs as much as possible — one clearly more conformant than the
    other — making the comparison meaningful.
    """
    n_traces = min(len(log), len(alignments), len(fitness_df))
    if n_traces == 0:
        return []

    def _info(i, label):
        rows, viol = _task04_trace_violations(alignments, i)
        return {"label": label, "case_id": str(log[i].attributes.get("concept:name", i)),
                "fitness": round(float(fitness_df.iloc[i]["fitness"]), 3),
                "rows": rows, "violations": viol}

    if trace_ids:
        by_id = _task04_case_index(log)
        chosen = [by_id[str(t)] for t in trace_ids if str(t) in by_id][:max(n, len(trace_ids))]
    else:
        # Activity coverage (distinct activities) and fitness per trace.
        coverage = [len({str(e.get("concept:name", "")) for e in log[i]}) for i in range(n_traces)]
        fitness  = [float(fitness_df.iloc[i]["fitness"]) for i in range(n_traces)]
        by_coverage = sorted(range(n_traces), key=lambda i: coverage[i], reverse=True)

        # Grow the pool from the most-complete traces until it spans a fitness gap,
        # then take the highest- and lowest-fitness trace in that pool. This keeps
        # both chosen traces long/complete while maximising the conformance contrast.
        chosen = by_coverage[:2]
        for k in range(2, n_traces + 1):
            pool = by_coverage[:k]
            hi = max(pool, key=lambda i: fitness[i])
            lo = min(pool, key=lambda i: fitness[i])
            if hi != lo and fitness[hi] - fitness[lo] > 1e-9:
                chosen = sorted({lo, hi}, key=lambda i: fitness[i], reverse=True)
                break

    return [_info(idx, f"Trace {k + 1}") for k, idx in enumerate(chosen)]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def _task04_involved_activities(rows):
    """Model activities the trace touches — synchronously executed or skipped
    (move on model). Log moves are inserted activities, not model tasks."""
    s = set()
    for r in rows:
        if r["moveType"] == "Synchronous Move":
            s.add(str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"]))
        elif r["moveType"] == "Model Move":
            s.add(str(r["model_move"]))
    return s


def _task04_model_structure(model_path):
    """Pragmatic nested decomposition of the guideline model:
    {backbone: [name,...], parallel: [[name,...],...], alt_exit: [name,...]}.
    backbone = main sequential activities; parallel = an AND-block's lanes;
    alt_exit = the shared XOR-escape activities (not block-structured, so shown as
    a stacked choice group). None when there is no model."""
    if not model_path:
        return None
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception:
        return None
    els = parsed.get("elements", {})
    if not els:
        return None
    kind = {n: e.get("kind") for n, e in els.items()}
    name = {n: e.get("name", "") for n, e in els.items()}
    out = {}
    for f in parsed.get("sequence_flows", {}).values():
        out.setdefault(f["source"], []).append(f["target"])
    tasks = [n for n in els if kind[n] == "task"]
    start = next((n for n in els if kind[n] == "startEvent"), None)
    if not tasks or start is None:
        return None

    def succ_tasks(nid):
        res, reach_end, seen, st = set(), False, set(), list(out.get(nid, []))
        while st:
            t = st.pop()
            if t in seen:
                continue
            seen.add(t)
            k = kind.get(t)
            if k == "task":
                res.add(t)
            elif k == "endEvent":
                reach_end = True
            else:
                st += out.get(t, [])
        return res, reach_end

    par_tasks, par_lanes = set(), []
    for n in els:
        if kind[n] == "parallelGateway" and len(out.get(n, [])) > 1:
            lanes = []
            for tgt in out[n]:
                lane, cur = [], tgt
                while cur is not None and kind.get(cur) == "task":
                    lane.append(name[cur]); par_tasks.add(cur)
                    nx = out.get(cur, []); cur = nx[0] if nx else None
                if lane:
                    lanes.append(lane)
            if lanes:
                par_lanes = lanes
                break

    alt = []
    for t in tasks:
        if t in par_tasks:
            continue
        st, re = succ_tasks(t)
        if re and not st:
            alt.append(t)

    dist = {t: 10 ** 9 for t in tasks}
    cur, dd = succ_tasks(start)[0], 0
    while cur and dd < 100:
        nxt = set()
        for t in cur:
            if dd < dist[t]:
                dist[t] = dd
            nxt |= succ_tasks(t)[0]
        cur = [t for t in nxt if dd + 1 < dist[t]]
        dd += 1
    backbone = sorted((t for t in tasks if t not in par_tasks and t not in alt),
                      key=lambda t: dist[t])
    return {"backbone": [name[t] for t in backbone],
            "parallel": par_lanes,
            "alt_exit": [name[t] for t in alt]}


def _task04_wrap(label, max_chars=15):
    """Wrap a label to at most two balanced lines for a chevron."""
    s = str(label)
    if len(s) <= max_chars or " " not in s:
        return [s]
    words, mid = s.split(" "), len(s) / 2.0
    acc, split_i, best = 0, 1, 1e9
    for i, w in enumerate(words[:-1]):
        acc += len(w) + 1
        if abs(acc - mid) < best:
            best, split_i = abs(acc - mid), i + 1
    return [" ".join(words[:split_i]), " ".join(words[split_i:])]


def _task04_color_map(rows):
    """activity name -> chevron colour for one trace: synchronous move (yellow),
    model move / skipped (grey); anything absent from the trace stays white."""
    cmap = {}
    for r in rows:
        if r["moveType"] == "Synchronous Move":
            a = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
            cmap[a] = GREY_LIGHTER
        elif r["moveType"] == "Model Move":
            cmap[str(r["model_move"])] = GREY_MED
    return cmap


# Nested-chevron layout constants (data units).
_NC_H, _NC_DEPTH, _NC_GAP, _NC_LANE_GAP = 1.0, 0.5, 0.5, 0.35


def _task04_chev_width(label):
    longest = max((len(l) for l in _task04_wrap(label)), default=1)
    return max(3.6, _NC_DEPTH * 2 + 1.5 + longest * 0.30)


def _task04_draw_chevron(ax, x, ytop, w, label, color, fontsize):
    from matplotlib.patches import Polygon as _Poly
    y = ytop - _NC_H; mid = y + _NC_H / 2.0
    verts = [(x, y), (x + _NC_DEPTH, mid), (x, y + _NC_H),
             (x + w - _NC_DEPTH, y + _NC_H), (x + w, mid), (x + w - _NC_DEPTH, y)]
    ax.add_patch(_Poly(verts, closed=True, facecolor=color, edgecolor="#4a4a4a",
                       linewidth=1.2, joinstyle="miter"))
    lines = _task04_wrap(label)
    tc = contrasting_text_color(color)
    for i, line in enumerate(lines):
        ax.text(x + w / 2.0, mid + (len(lines) - 1) * 0.17 - i * 0.34, line,
                ha="center", va="center", fontsize=fontsize, color=tc)


def _task04_nested_width(structure):
    x = sum(_task04_chev_width(nm) + _NC_GAP for nm in structure["backbone"])
    if structure["parallel"]:
        x += max(_task04_chev_width(l[0]) for l in structure["parallel"]) + _NC_GAP
    if structure["alt_exit"]:
        x += 1.1 + max(_task04_chev_width(a) for a in structure["alt_exit"])
    return x


def _task04_draw_nested(ax, structure, color_fn, fontsize, badges=None):
    """Draw the model structure as nested chevrons on ax, coloured by color_fn.
    ``badges`` (log moves) are drawn as blue dashed boxes above their anchor."""
    from matplotlib.patches import FancyBboxPatch as _Box
    ax.axis("off"); ax.set_aspect("equal")
    pos = {}  # activity name -> (centre_x, top_y) of its chevron
    x = 0.0
    for nm in structure["backbone"]:
        w = _task04_chev_width(nm)
        _task04_draw_chevron(ax, x, _NC_H / 2.0, w, nm, color_fn(nm), fontsize)
        pos[nm] = (x + w / 2.0, _NC_H / 2.0)
        x += w + _NC_GAP
    if structure["parallel"]:
        lanes = structure["parallel"]; n = len(lanes)
        gw = max(_task04_chev_width(l[0]) for l in lanes)
        total_h = n * _NC_H + (n - 1) * _NC_LANE_GAP
        ax.add_patch(_Box((x - 0.16, -total_h / 2.0 - 0.32), gw + 0.32, total_h + 0.64,
                          boxstyle="round,pad=0.02,rounding_size=0.14",
                          facecolor="#eef0f2", edgecolor="#c8ccd0", linewidth=1.0))
        ytop0 = total_h / 2.0
        for i, lane in enumerate(lanes):
            ytop = ytop0 - i * (_NC_H + _NC_LANE_GAP)
            _task04_draw_chevron(ax, x, ytop, gw, lane[0], color_fn(lane[0]), fontsize)
            pos[lane[0]] = (x + gw / 2.0, ytop)
        x += gw + _NC_GAP
    if structure["alt_exit"]:
        x += 0.45
        ax.plot([x, x], [-2.0, 2.0], linestyle=(0, (4, 3)), color="#999999", linewidth=1.2)
        x += 0.55
        alt = structure["alt_exit"]; n = len(alt)
        gw = max(_task04_chev_width(a) for a in alt)
        total_h = n * _NC_H + (n - 1) * _NC_LANE_GAP
        ytop0 = total_h / 2.0
        ax.text(x + gw / 2.0, ytop0 + 0.5, "Alternative exit", ha="center", va="bottom",
                fontsize=max(8, fontsize - 3), style="italic", color="#666666")
        for i, a in enumerate(alt):
            ytop = ytop0 - i * (_NC_H + _NC_LANE_GAP)
            _task04_draw_chevron(ax, x, ytop, gw, a, color_fn(a), fontsize)
            pos[a] = (x + gw / 2.0, ytop)
        x += gw

    top_y = 0.5
    if badges:
        seen = {}
        for b in badges:
            p = pos.get(b.get("anchor"))
            if not p:
                continue
            acx, atop = p
            lbl = str(b.get("label", ""))
            k = seen.get(b["anchor"], 0); seen[b["anchor"]] = k + 1
            bw = max(2.4, _task04_chev_width(lbl) - 1.2); bh = 0.6
            by = atop + 0.45 + k * (bh + 0.3)          # stack upward if repeated
            ax.plot([acx, acx], [atop, by], linestyle=(0, (3, 2)),
                    color=GREY_DARK, linewidth=1.3)
            ax.add_patch(_Box((acx - bw / 2.0, by), bw, bh,
                              boxstyle="round,pad=0.02,rounding_size=0.08",
                              facecolor="white", edgecolor=GREY_DARK, linewidth=1.6,
                              linestyle="--"))
            ax.text(acx, by + bh / 2.0, lbl, ha="center", va="center",
                    fontsize=max(8, fontsize - 3), color=GREY_DARK)
            top_y = max(top_y, by + bh)
    ax.set_xlim(-0.4, x + 0.4)
    ax.set_ylim(-2.5, max(2.5, top_y + 0.3))


def task04_flow_chart_basic(selected, output_dir: str, model_path=None):
    """Nested chevron flow chart: the guideline model is drawn as nested chevrons
    (sequential backbone, an AND-block as stacked lanes, and the XOR escape as a
    stacked 'alternative exit' group), once per selected trace. Each activity is
    coloured by that trace's alignment — synchronous move (yellow), model move /
    skipped (grey), or white when the trace never touches it — so the chevron
    carries the same structure and activity set as the BPMN idiom."""
    path = os.path.join(output_dir, "task04_flow_chart_basic.svg")
    if not selected:
        fig, ax = plt.subplots(figsize=(7, 3)); ax.axis("off")
        ax.text(0.5, 0.5, "No trace data available.", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
        save_svg(fig, path)
        return

    structure = _task04_model_structure(model_path)
    if not structure or not structure["backbone"]:
        # No model → fall back to a flat chevron strip of each trace.
        nodes_per_trace = [chevron_nodes_from_alignment_rows(t["rows"]) for t in selected]
        fig_w = max((chevron_figure_width(n) for n in nodes_per_trace if n), default=9.0)
        fig = plt.figure(figsize=(fig_w, 1.9 * len(selected) + 1.4))
        gs = gridspec.GridSpec(len(selected), 1, hspace=0.9)
        for r, (trace, nodes) in enumerate(zip(selected, nodes_per_trace)):
            ax = fig.add_subplot(gs[r])
            draw_chevron_strip(ax, nodes, fontsize=_CHEVRON_FONT)
            ax.set_title(trace["label"], fontsize=FONT_LABEL, loc="left", pad=6)
        handles = [mpatches.Patch(facecolor=c, edgecolor="#4a4a4a", label=lbl)
                   for lbl, c in _MOVE_LEGEND]
        fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=len(_MOVE_LEGEND), frameon=False, fontsize=FONT_ANNOT - 1)
        fig.tight_layout(rect=[0, 0.08, 1, 1.0])
        save_svg(fig, path)
        return

    scale = 0.42
    x_extent = _task04_nested_width(structure)
    n_rows = len(selected)
    fig_w = max(9.0, x_extent * scale + 1.0)
    fig_h = n_rows * (5.0 * scale + 0.9) + 1.0

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(n_rows, 1, hspace=0.55)
    for r, trace in enumerate(selected):
        ax = fig.add_subplot(gs[r])
        cmap = _task04_color_map(trace["rows"])
        _task04_draw_nested(ax, structure, lambda nm, _c=cmap: _c.get(nm, "#ffffff"),
                            fontsize=min(_CHEVRON_FONT, 12),
                            badges=_task04_log_move_badges(trace["rows"]))
        ax.set_title(trace["label"], fontsize=FONT_LABEL, loc="left", pad=4)

    legend = list(_MOVE_LEGEND) + [("Not in this trace", "#ffffff")]
    handles = [mpatches.Patch(facecolor=c, edgecolor="#4a4a4a", label=lbl)
               for lbl, c in legend]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
               ncol=len(legend), frameon=False, fontsize=FONT_ANNOT - 1)
    fig.tight_layout(rect=[0, 0.05, 1, 1.0])
    save_svg(fig, path)


def _task04_bpmn_node_style(rows):
    """node_style_fn colouring model tasks by this trace's alignment: synchronous
    move -> yellow (conformant), model move -> grey (skipped); everything else
    white. Log moves (inserted activities) are not model tasks — the table lists
    them instead. Uses the same colours as the chevron for information equivalence."""
    conform, skipped = set(), set()
    for r in rows:
        if r["moveType"] == "Synchronous Move":
            lbl = str(r["log_move"]) if str(r["log_move"]) not in ("-", "None", "(skip)", "") \
                else str(r["model_move"])
            conform.add(lbl)
        elif r["moveType"] == "Model Move":
            skipped.add(str(r["model_move"]))

    def _style(eid, elem):
        if elem.get("kind") == "task":
            name = elem.get("name", "")
            if name in skipped:
                return (GREY_MED, "#444444", 3, contrasting_text_color(GREY_MED))
            if name in conform:
                return (GREY_LIGHTER, "#666666", 2, contrasting_text_color(GREY_LIGHTER))
        return ("white", "#888888", 2, "#333333")
    return _style


_MISSING = ("-", "None", "(skip)", "")


def _task04_log_move_badges(rows):
    """Log moves (inserted activities) as external badges, each anchored to the
    model activity at the sequence position where the insertion occurred — the
    most recent synchronous / model move before it (or the next one if it comes
    first). Returns [{"label", "anchor"}]."""
    badges, last = [], None
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous Move":
            last = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
        elif mt == "Model Move":
            last = str(r["model_move"])
        elif mt == "Log Move":
            badges.append({"label": str(r["log_move"]), "anchor": last})

    if any(b["anchor"] is None for b in badges):
        first = None
        for r in rows:
            if r["moveType"] == "Synchronous Move":
                first = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
                break
            if r["moveType"] == "Model Move":
                first = str(r["model_move"]); break
        for b in badges:
            b["anchor"] = b["anchor"] or first
    return [b for b in badges if b["anchor"]]


def task04_flow_chart_elaborate(selected, model_path, output_dir):
    """BPMN idiom, information-equivalent to the chevron: the guideline model is
    drawn once per trace (stacked), each model task coloured by that trace's
    alignment — Synchronous Move (yellow) or Model Move / skipped (grey). Log Move
    (inserted) activities aren't model tasks, so they are listed in the table
    beneath, whose dark-blue header matches the Log Move legend colour. Together
    the panels + table encode the same three move types the chevron shows."""
    path = os.path.join(output_dir, "task04_flow_chart_elaborate.svg")
    title = "Trace-Level Conformance on the Process Model"
    if not selected or not model_path:
        render_empty_state_svg(path, title, "No traces or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task04: BPMN parse failed: {e}")
        render_empty_state_svg(path, title, "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, title, "No BPMN geometry to render.")
        return

    panels = [{
        "parsed": parsed,
        "node_style_fn": _task04_bpmn_node_style(t["rows"]),
        "subtitle": t["label"],
        "badges": _task04_log_move_badges(t["rows"]),
    } for t in selected]

    compose_bpmn_panels(
        panels, path,
        title=title,
        legend_items=[
            (GREY_LIGHTER, "#666666", 2, "Synchronous Move"),
            (GREY_MED,     "#444444", 3, "Model Move"),
            (GREY_DARK,    "#333333", 3, "Log Move"),
        ],
        node_font_size=14,
    )


def task04_bar_chart(tdf: pd.DataFrame, output_dir: str):
    """One uniform-coloured bar per trace; fitness value labelled above each bar."""
    fig, ax = plt.subplots(figsize=(max(7, len(tdf) * 0.75), 5))
    x = np.arange(len(tdf))
    bars = ax.bar(x, tdf["fitness"], color=_TRACE_COLOR, edgecolor="white", width=0.65)
    for bar, val in zip(bars, tdf["fitness"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.012,
                f"{val:.3f}", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)

    ax.set_xticks(x)
    ax.set_xticklabels(tdf["label"], rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Trace", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0-1)", fontsize=FONT_LABEL)
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    ax.set_ylim(0, 1.12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_bar_chart.svg"))


def task04_table(tdf: pd.DataFrame, output_dir: str):
    """Trace | Fitness, one row per sampled trace."""
    cell_text = [[row["label"], f"{row['fitness']:.3f}"] for _, row in tdf.iterrows()] \
        or [["—", "—"]]
    col_labels = ["Trace", "Fitness"]

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(6.5, fig_h))
    ax.axis("off")
    make_table(
        ax, cell_text=cell_text, col_labels=col_labels,
        bbox=[0.05, 0.05, 0.9, 0.92],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=10.5, scale_xy=(1, 1.75), cell_pad=0.11,
    )
    ax.set_title(TITLE, fontsize=FONT_TITLE, pad=3)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_table.svg"))


def task04_line_graph(tdf: pd.DataFrame, output_dir: str):
    """Fitness profile across the sampled traces (x = trace, y = fitness)."""
    fig, ax = plt.subplots(figsize=(max(7, len(tdf) * 0.7), 5))
    x = np.arange(len(tdf))
    ax.plot(x, tdf["fitness"], color=_TRACE_COLOR, linewidth=1.8, marker="o", markersize=5)
    ax.fill_between(x, tdf["fitness"], alpha=0.15, color=_TRACE_COLOR)
    for xi, val in zip(x, tdf["fitness"]):
        ax.text(xi, val + 0.02, f"{val:.3f}", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)

    ax.set_xticks(x)
    ax.set_xticklabels(tdf["label"], rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Trace", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0-1)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 1.12)
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_line_graph.svg"))


def task04_table_bar_chart(tdf: pd.DataFrame, output_dir: str):
    """Trace | Fitness table (left) + adjacent uniform-coloured fitness bars (right)."""
    cell_text = [[row["label"], f"{row['fitness']:.3f}"] for _, row in tdf.iterrows()] \
        or [["—", "—"]]
    col_labels = ["Trace", "Fitness"]

    fig = plt.figure(figsize=(13, max(4.5, 1.2 + len(tdf) * 0.45)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.2, 1.0], wspace=0.28)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    make_table(
        ax_tbl, cell_text=cell_text, col_labels=col_labels,
        bbox=[0.02, 0.05, 0.96, 0.88],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=9.5, scale_xy=(1, 1.7), cell_pad=0.09,
    )
    ax_tbl.set_title(TITLE, fontsize=FONT_TITLE, pad=4)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(tdf))
    bars = ax_bar.barh(y, tdf["fitness"], color=_TRACE_COLOR, edgecolor="white")
    for bar, val in zip(bars, tdf["fitness"]):
        ax_bar.text(min(val + 0.02, 1.02), bar.get_y() + bar.get_height() / 2,
                    f"{val:.3f}", va="center", ha="left", fontsize=FONT_ANNOT - 1)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(tdf["label"], fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, 1.18)
    ax_bar.set_xlabel("Fitness (0-1)", fontsize=FONT_LABEL)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_table_bar_chart.svg"))


def task04_matrix(tdf: pd.DataFrame, output_dir: str):
    """Trace × Fitness grid: colour scales 0→light to 1→dark, with numeric labels."""
    labels = tdf["label"].tolist()
    data = tdf["fitness"].values.astype(float).reshape(-1, 1)

    fig_h = max(3.0, 0.5 * len(labels) + 1.4)
    fig, ax = plt.subplots(figsize=(3.6, fig_h))
    draw_value_heatmap(
        fig, ax, data, labels, ["Fitness"],
        cbar_label="Fitness", cell_fmt="{:.3f}", annotate=True,
    )
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_matrix.svg"))


def task04_heatmap(tdf: pd.DataFrame, output_dir: str):
    """Trace × Fitness grid: continuous colour intensity, no numeric annotation."""
    labels = tdf["label"].tolist()
    data = tdf["fitness"].values.astype(float).reshape(-1, 1)

    fig_h = max(3.0, 0.3 * len(labels) + 1.4)
    fig, ax = plt.subplots(figsize=(4.5, fig_h))
    draw_value_heatmap(
        fig, ax, data, labels, ["Fitness"],
        cbar_label="Fitness", annotate=False,
    )
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, trace_ids=None, alignments=None, model_path=None):
    """Generate all Task ID 4 SVGs into output_dir.

    ``trace_ids`` is the admin-configured list of case-id strings (from
    PARAM_SPEC "trace_ids"). When empty/None the first ``SAMPLE_N`` traces in log
    order are shown. Every idiom renders the same traces so the views are
    directly comparable (and match what the ground truth was computed for).

    ``alignments`` (optional) enables the trace-level flow-chart idioms, which
    compare the alignment (conformance) patterns of two traces side by side.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 4 visualizations ---")

    # Single trace selection shared by EVERY idiom: the admin-selected traces, or
    # (default) the two traces with the largest violation-count gap. This needs
    # alignments; without them we fall back to the first SAMPLE_N in log order.
    selected = _task04_select_compare_traces(log, alignments, fitness_df, trace_ids=trace_ids) \
        if alignments else []
    if selected:
        tdf = pd.DataFrame([{"case_id": t["case_id"], "fitness": t["fitness"], "label": t["label"]}
                            for t in selected])
    else:
        tdf = _task04_build_trace_df(log, fitness_df, trace_ids=trace_ids)
    if tdf.empty:
        logger.warning("      Skipped Task 4: no trace data available.")
        return

    source = "admin-selected" if trace_ids else "largest violation gap"
    logger.info(f"      -> Comparing {len(tdf)} traces ({source}).")

    task04_bar_chart(tdf, output_dir)
    task04_table(tdf, output_dir)
    task04_table_bar_chart(tdf, output_dir)
    task04_matrix(tdf, output_dir)
    task04_line_graph(tdf, output_dir)
    task04_heatmap(tdf, output_dir)

    # Trace-level pattern comparison — chevron + BPMN idioms of the same traces.
    if selected:
        task04_flow_chart_basic(selected, output_dir, model_path=model_path)
        task04_flow_chart_elaborate(selected, model_path, output_dir)
