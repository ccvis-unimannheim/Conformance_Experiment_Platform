"""
tasks/task34.py – Where does the recorded behavior violate which guidelines?

Trace-level: shows violations for one or few traces simultaneously,
with clear attribution of which violations belong to which activities.

Which traces: trace_ids, else trace_pick_rule / trace_count (1–4, see
trace_alignment), among the traces violating violation_pattern when one is set.
(violated_activity is its superseded, activity-only form, still honoured for
experiments specified before it existed.) "The trace" below is the first one
chosen.

IDIOMS — every one of them speaks about every chosen trace, and every one
of them names the violation type:
    bar_chart                  – violations per "Activity (Move Type)", one
                                 bar per trace
    heatmap, matrix            – the same counts as "Activity (Move Type)"
                                 × traces, the heatmap as colour, the
                                 matrix as numbers
    table                      – the traces' alignments, one row per step
    flow_chart_basic           – chevron strip per trace
    flow_chart_elaborate       – BPMN coloured by the traces' violations
      (with more than one trace chosen, these last three are drawn side by side
       by task04's renderers)
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart",
    "table",
    "flow_chart_basic",
    "flow_chart_elaborate",
    "heatmap",
    "matrix",
]


import trace_alignment

PARAM_SPEC = [
    *trace_alignment.selection_params(
        rules=["worst_fitness", "first_nonconformant", "most_frequent_variants"],
        default_rule="worst_fitness",
        count_default=1, count_min=1, count_max=4,
    ),
    # Supersedes this task's own `violated_activity`, which named an activity
    # and left the move type open: "Confirm Order" meant a skipped Confirm Order
    # and an inserted one at once. The class parameter names both, and every
    # rule honours it rather than only the worst-fitness one. A
    # `violated_activity` saved by an existing experiment still narrows the
    # selection (see generate) — it just is not offered any more.
    trace_alignment.VIOLATION_PATTERN_PARAM,
]


def validate_params(log, params) -> list:
    """Task 34 presents one trace or a few; four is where the panels stop being
    readable."""
    return trace_alignment.validate_selection(log, params, min_traces=1, max_traces=4)


import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import to_hex, Normalize

from shared import (
    save_svg,
    make_table,
    CIVIDIS,
    CIVIDIS_R,
    GREY_MED, GREY_LIGHTER, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    chevron_figure_width, draw_chevron_strip,
    draw_value_heatmap, draw_grouped_rate_bars,
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    render_empty_state_svg,
    contrasting_text_color,
    classify_step,
    trace_activities, write_traces_sidecar,
)

# ── Palette (cividis, from shared.py) ───────────────────────────────────────
CAT_STRONG = to_hex(CIVIDIS(0.15))   # dark accent / text  (#243c6e)
CAT_MID    = to_hex(CIVIDIS(0.50))   # Log Move            (#7d7c78 grey)
CAT_SOFT   = to_hex(CIVIDIS(0.20))   # Model Move          (#35456c navy blue)
_C_BG      = "#f5f5f5"
_HDR_BG    = CAT_STRONG    # dark navy (#243c6e) — matches cividis palette
_CMAP      = CIVIDIS_R

# Violation type → bar / node color
_MOVE_COLORS = {
    "Synchronous":   "#e0e0e0",  # light grey — conformant (neutral, readable)
    "Model Move": CAT_SOFT,   # skipped activity
    "Log Move":   CAT_MID,    # extra activity
}

# Alignment-move palette matching task04's Flow Chart / Flow Chart+ (BPMN
# model) idioms — used only by task34_flow_chart_basic / _flow_chart_elaborate
# so the two tasks' trace-alignment visuals read consistently. Other task34
# idioms keep the cividis CAT_* palette above.
_T04_ALIGN_COLORS = {
    "Synchronous":   GREY_LIGHTER,  # yellow
    "Model Move": GREY_MED,      # grey
    "Log Move":   GREY_DARK,     # dark navy
}
_T04_ALIGN_STYLE = {
    # (edgecolor, linewidth)
    "Synchronous":   ("#666666", 2),
    "Model Move": ("#444444", 3),
    "Log Move":   ("#333333", 3),
}

# The one vocabulary every idiom names a move type with. Plain, without the
# "(skipped)" / "(extra)" glosses the legends used to add: task04 and the move
# table say "Model Move" and "Log Move", so a reader comparing two idioms of the
# same task should not have to decide whether "extra" is a third thing.
# (Internal keys stay as shared.classify_step returns them so they keep matching
# across tasks.)
_MOVE_DISPLAY = {
    "Synchronous":   "Synchronous Move",
    "Model Move": "Model Move",
    "Log Move":   "Log Move",
}

# Table row fills (cividis-sampled)
_SYNC_ROW = to_hex(CIVIDIS(0.97))
_MOM_ROW  = to_hex(CIVIDIS(0.85))
_MOL_ROW  = to_hex(CIVIDIS(0.50))
#: Every per-activity idiom carries the same title. They used to name the trace
#: and its fitness, which said something the figure beside it did not — and named
#: one trace even where several were drawn.
_VIOLATION_TITLE = "Violations per Activity"
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
    step_num = 0
    for (log_v, model_v) in (result.get("alignment") or []):
        ll = _extract_label(log_v)
        ml = _extract_label(model_v)
        if ll == ">>" and ml == ">>":
            continue
        act, mt = classify_step(ll, ml)
        if mt is None:
            mt = "Synchronous"
            act = ll
        step_num += 1
        rows.append({
            "step":       step_num,
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


_MOVE_KEYS = ("Model Move", "Log Move")


def _category(key) -> str:
    """The row name the aggregate idioms use: "Ship Order (Log Move)".

    The move type belongs in the label rather than on an axis of its own.
    The chevron, the BPMN and the move table all say which kind of violation
    a step is; without it here, three idioms of one task answered a question
    the other three could not. Folding it into the category costs no encoding
    channel - only the pairs that actually occur get a row - where a second
    axis would have doubled every bar and every column.
    """
    activity, move_type = key
    return f"{activity} ({_MOVE_DISPLAY.get(move_type, move_type)})"


def _build_canonical_payload(ctxs):
    """(keys, trace_labels, counts) over every shown trace.

    The single data source behind bar_chart, heatmap and matrix, so the three
    cannot disagree. A key is an ``(activity, move type)`` pair - the union
    over the traces, in first-seen order - and ``counts`` is
    (n_keys x n_traces).

    These used to draw the first selected trace only, however many the admin
    asked for, while the chevron, BPMN and move table showed all of them, so
    the same figure set spoke about different traces depending on which idiom
    you read.
    """
    keys, seen = [], set()
    for ctx in ctxs:
        for r in ctx["rows"]:
            a, mt = r["activity"], r["moveType"]
            if not a or a == ">>" or mt not in _MOVE_KEYS or (a, mt) in seen:
                continue
            seen.add((a, mt))
            keys.append((a, mt))

    # "Trace 1".."Trace N" over the traces actually drawn, the running number
    # trace_alignment.trace_records gives the chevron, BPMN and move table.
    # The context's own trace_label counts positions in the whole log, so
    # these idioms used to name ids the other three never mentioned.
    labels = [f"Trace {i + 1}" for i in range(len(ctxs))]
    at = {k: i for i, k in enumerate(keys)}
    counts = np.zeros((len(keys), len(ctxs)), dtype=float)
    for ti, ctx in enumerate(ctxs):
        for r in ctx["rows"]:
            row = at.get((r["activity"], r["moveType"]))
            if row is not None:
                counts[row, ti] += 1
    return keys, labels, counts


def _trace_colors(n: int) -> list:
    """One colour per shown trace, navy through cividis's yellow end."""
    return [to_hex(CIVIDIS_R(0.12 + 0.76 * i / max(n - 1, 1))) for i in range(n)]


def _grid_size(row_labels, col_labels):
    """(height, width) for the heatmap and the matrix, which share a grid.

    The width follows the longest row label: carrying the move type makes
    them half as long again, and a fixed margin cropped them.
    """
    longest = max((len(r) for r in row_labels), default=10)
    return (max(3.4, len(row_labels) * 0.5 + 2.0),
            max(5.2, len(col_labels) * 1.5 + 1.6 + longest * 0.105))


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
    make_table(
        ax,
        cell_text=_cell_text(rows),
        col_labels=_COL_LABELS,
        bbox=bbox,
        col_widths=_COL_WIDTHS,
        font_size=font_size,
        scale_xy=(1, 1.8),
        zebra=True,
    )


def _wrap_category(key, width: int = 14) -> str:
    """A tick label for one ``(activity, move type)`` key, over several lines.

    The move type always gets a line of its own, so the eye can run along the
    axis and compare it without reading the whole name first.
    """
    activity, move_type = key
    return (_wrap_activity(activity, width)
            + f"\n({_MOVE_DISPLAY.get(move_type, move_type)})")


def _wrap_activity(name: str, width: int = 14) -> str:
    """Break a long activity name so upright bars keep their tick labels apart."""
    words, lines, cur = str(name).split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def _chevron_nodes(rows, colors=None):
    colors = colors or _MOVE_COLORS
    nodes = []
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous":
            nodes.append({"label": r["log_move"],   "color": colors["Synchronous"]})
        elif mt == "Model Move":
            nodes.append({"label": r["model_move"], "color": colors["Model Move"]})
        elif mt == "Log Move":
            nodes.append({"label": r["log_move"],   "color": colors["Log Move"]})
    return nodes


def _log_move_badges(rows, task_names):
    """Badges for Log Move steps: {'label': activity, 'anchor': nearest real
    model task in the trace's own step order}.

    Log Move activities aren't model tasks, so they have no BPMN node of their
    own — the badge is drawn hanging off the closest real task instead (the
    preceding one in the trace; the next one if the log move is the very first
    step). Steps with no real task anywhere in the trace are dropped (nothing
    to anchor to).
    """
    badges = []
    for i, r in enumerate(rows):
        if r["moveType"] != "Log Move":
            continue
        label = r["log_move"]
        if not label or label in (">>", "(skip)"):
            continue
        anchor = None
        for j in range(i - 1, -1, -1):
            a = rows[j]["activity"]
            if a and a != ">>" and a in task_names:
                anchor = a
                break
        if anchor is None:
            for j in range(i + 1, len(rows)):
                a = rows[j]["activity"]
                if a and a != ">>" and a in task_names:
                    anchor = a
                    break
        if anchor is not None:
            badges.append({"label": label, "anchor": anchor})
    return badges


# ── Idiom 1: bar_chart — most violated activities (log-level) ────────────────

def task34_bar_chart(ctxs, output_dir):
    """Grouped bars: violations per "Activity (Move Type)", one bar
    per shown trace.

    Upright, activities along the x axis. It used to lie on its side, which put
    the activities on the y axis and read against every other bar chart in the
    platform.
    """
    keys, labels, totals = _build_canonical_payload(ctxs)
    if not keys or not totals.any():
        _no_violations(output_dir, "bar_chart")
        return

    colors = _trace_colors(len(labels))
    fig_w = max(9.0, len(keys) * 1.35 + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, 5.4))
    ax.set_facecolor("#fafbfc")

    x = draw_grouped_rate_bars(ax, len(keys), labels, totals, colors)

    vmax = float(totals.max())
    bw = 0.76 / max(len(labels), 1)
    offsets = (np.arange(len(labels)) - (len(labels) - 1) / 2.0) * bw
    for ti in range(len(labels)):
        for ai in range(len(keys)):
            val = totals[ai, ti]
            if val > 0:
                ax.text(x[ai] + offsets[ti], val + vmax * 0.02, f"{int(val)}",
                        ha="center", va="bottom", fontsize=FONT_ANNOT - 1,
                        color=CAT_STRONG)

    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_category(k) for k in keys], fontsize=FONT_ANNOT)
    ax.set_ylabel("Number of Violations", fontsize=FONT_LABEL)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_ylim(0, max(vmax * 1.18, 1.0))
    ax.set_title(_VIOLATION_TITLE, fontsize=FONT_TITLE, pad=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    if len(labels) > 1:
        ax.legend(frameon=False, fontsize=FONT_ANNOT, ncol=min(len(labels), 4))

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_bar_chart.svg"))


# ── Idiom 3: table — alignment table for worst-fitness trace ──────────────────

def task34_table(ctx, output_dir):
    """Two-column table: Activity | Type — one row per alignment step, in trace order.

    Lists each step's activity together with its move type (Model Move / Log
    Move / Synchronous Move) instead of a single aggregate violation count,
    so the reader can see what actually happened at each step.
    """
    rows = ctx["rows"]
    if not rows:
        _no_violations(output_dir, "table")
        return

    cell_text = []
    for r in rows:
        mt = r["moveType"]
        act = r["model_move"] if mt == "Model Move" else r["log_move"]
        cell_text.append([act, _MOVE_DISPLAY.get(mt, mt)])

    fig_h = max(3.5, 1.2 + len(cell_text) * 0.42)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Activity", "Type"],
        bbox=[0.05, 0.05, 0.90, 0.82],
        col_widths=[0.60, 0.40],
        font_size=11,
        scale_xy=(1, 1.7),
    )
    ax.set_title("Activity Violations", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_table.svg"))


# ── Idiom 4: flow_chart_table — chevron + alignment table ─────────────────────

# ── Idiom 5: flow_chart_elaborate_table — BPMN + alignment table ──────────────

# ── Idiom 6: heatmap — top-20 traces × activities ─────────────────────────────

def task34_heatmap(ctxs, output_dir):
    """"Activity (Move Type)" x traces, the count as colour.

    The matrix is the same grid with the numbers instead.
    """
    keys, labels, totals = _build_canonical_payload(ctxs)
    if not keys or not totals.any():
        _no_violations(output_dir, "heatmap")
        return

    rows = [_category(k) for k in keys]
    fig_h, fig_w = _grid_size(rows, labels)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_value_heatmap(fig, ax, totals, rows, labels,
                       xlabel="Trace",
                       cbar_label="Number of Violations",
                       annotate=False, vmax=max(float(totals.max()), 1.0))
    ax.set_title(_VIOLATION_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_heatmap.svg"))


# ── Idiom 7: table_bar_chart — trace summary table + log-level bar chart ──────

# ── Idiom 8: flow_chart_basic — standalone chevron ───────────────────────────

def task34_flow_chart_basic(ctx, output_dir):
    """Chevron strip only — worst trace alignment without the detail table."""
    rows  = ctx["rows"]
    nodes = _chevron_nodes(rows, colors=_T04_ALIGN_COLORS)
    fig_w = max(14.0, chevron_figure_width(nodes))
    fig, ax = plt.subplots(figsize=(fig_w, 3.2))
    draw_chevron_strip(ax, nodes, fontsize=17, uniform_width=True)
    ax.set_title("Trace Alignment", fontsize=FONT_TITLE, pad=8)
    # Only list the move types actually present in this trace — a static
    # 3-entry legend implied all three always occur, which isn't true.
    present_types = {r["moveType"] for r in rows}
    legend_handles = [
        mpatches.Patch(facecolor=_T04_ALIGN_COLORS[mt], edgecolor=_T04_ALIGN_STYLE[mt][0],
                       linewidth=_T04_ALIGN_STYLE[mt][1], label=_MOVE_DISPLAY[mt])
        for mt in ("Synchronous", "Model Move", "Log Move")
        if mt in present_types
    ]
    # Anchored to the axes (not the figure) so the gap below the chevrons is
    # predictable regardless of figure width; tight_layout's rect reserves the
    # room instead of squeezing the legend up against the chevron bottoms.
    ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.18),
              ncol=len(legend_handles), fontsize=FONT_LABEL + 2, frameon=True, fancybox=False,
              edgecolor="#cccccc", handleheight=1.8, handlelength=2.4, markerscale=1.4)
    fig.tight_layout(rect=[0, 0.10, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task34_flow_chart_basic.svg"))


# ── Idiom 9: flow_chart_elaborate — standalone BPMN ──────────────────────────

def task34_flow_chart_elaborate(ctx, model_path, output_dir):
    """BPMN diagram with per-node violation coloring — no alignment table."""
    out_path = os.path.join(output_dir, "task34_flow_chart_elaborate.svg")
    if not model_path:
        render_empty_state_svg(out_path, "BPMN Violation Overview",
                               "No process model provided.")
        return
    parsed = parse_bpmn_model(model_path, node_scale=1.6)
    if not parsed.get("elements"):
        render_empty_state_svg(out_path, "BPMN Violation Overview",
                               "Could not parse BPMN model.")
        return

    rows = ctx["rows"]
    task_names = {e["name"] for e in parsed["elements"].values() if e.get("kind") == "task"}

    priority  = {"Model Move": 2, "Log Move": 1, "Synchronous": 0}
    act_status = {}
    for r in rows:
        act, mt = r["activity"], r["moveType"]
        if act and act != ">>":
            # First sighting always records the activity (even Synchronous,
            # priority 0) so it's distinguishable from "not in trace" at all —
            # a later, higher-priority move type for the same activity still
            # overrides it.
            if act not in act_status or priority[mt] > priority[act_status[act]]:
                act_status[act] = mt

    def node_style_fn(eid, elem):
        name = elem.get("name", "")
        kind = elem.get("kind", "task")
        if kind != "task":
            return ("#F5F5F5", "#CCCCCC", 1.0, CAT_STRONG)
        mt = act_status.get(name)
        if mt in _T04_ALIGN_COLORS:
            color = _T04_ALIGN_COLORS[mt]
            edge, lw = _T04_ALIGN_STYLE[mt]
            return (color, edge, lw, contrasting_text_color(color))
        return ("#FAFAFA", "#CCCCCC", 1.0, "#444444")

    # Log Move activities aren't model tasks, so they can't be shown by
    # colouring a node — draw them as dashed badges floating above their
    # nearest real task instead (shared.bpmn_diagram_body's `badges` support).
    badges = _log_move_badges(rows, task_names)

    # Only list legend entries that actually occur — a static list implied
    # all of them always occur, which isn't true.
    present_status = set(act_status.values())

    legend_items = [
        (_T04_ALIGN_COLORS[mt], *_T04_ALIGN_STYLE[mt], _MOVE_DISPLAY[mt])
        for mt in ("Synchronous", "Model Move")
        if mt in present_status
    ]
    if badges:
        legend_items.append((GREY_DARK, "#8ba0cf", 2.0, _MOVE_DISPLAY["Log Move"], "6 4"))
    compose_bpmn_panels(
        panels=[{"parsed": parsed, "node_style_fn": node_style_fn, "subtitle": "", "badges": badges}],
        out_path=out_path,
        title="BPMN Alignment — Violation Overview",
        legend_items=legend_items,
        h_scale=1.0,
        node_font_size=20.0,
        legend_font_size=13.0,
        title_font_size=16.0,
        title_center=True,
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

def task34_matrix(ctxs, output_dir):
    """"Activity (Move Type)" x traces, the count as a number on a
    white cell.

    The heatmap is the same grid in colour.
    """
    keys, labels, totals = _build_canonical_payload(ctxs)
    if not keys or not totals.any():
        _no_violations(output_dir, "matrix")
        return

    rows = [_category(k) for k in keys]
    fig_h, fig_w = _grid_size(rows, labels)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_value_heatmap(fig, ax, totals, rows, labels,
                       xlabel="Trace", cell_fmt="{:.0f}",
                       annotate=True, colorless=True)
    ax.set_title(_VIOLATION_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task34_matrix.svg"))


# ── Idiom 11: parallel_sets — violation type × activity ──────────────────────

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_ctx(ctxs, params):
    """Return the representative context based on admin params.

    If `violated_activity` is set, picks the worst-fitness context where that
    activity has a violation.  Falls back to ctxs[0] (overall worst) if the
    activity is not found or no param is set.
    """
    activity = (params.get("violated_activity") or "").strip()
    if activity:
        for ctx in ctxs:
            if any(r["activity"] == activity and _is_violation(r)
                   for r in ctx["rows"]):
                return ctx
    return ctxs[0]


def _select_ctxs(ctxs, log, alignments, *, trace_ids=None, rule="worst_fitness",
                 count=1, pattern="", violated_activity=None):
    """The contexts to show, in display order.

    Selection is the class's (trace_alignment.pick_indices): one context per
    distinct activity sequence, and only traces that actually violate — task34
    presents violations, so a conformant trace answers nothing. Its own
    ``violated_activity`` narrows that further to the traces violating one
    activity.
    """
    if not ctxs:
        return []
    by_index = {c["trace_index"]: c for c in ctxs}

    if trace_ids:
        index_of = trace_alignment.case_index(log)
        chosen = [by_index[index_of[str(t)]] for t in trace_ids
                  if str(t) in index_of and index_of[str(t)] in by_index]
        if chosen:
            return chosen[:max(count, len(trace_ids))]
        # Every named trace is fully conformant (so has no context): fall through
        # to the rule rather than rendering nothing at all.

    if violated_activity and not pattern and rule == "worst_fitness":
        narrowed = [c for c in ctxs
                    if any(r["activity"] == violated_activity and _is_violation(r)
                           for r in c["rows"])]
        if narrowed:
            seen, pool = set(), []
            for ctx in narrowed:
                key = trace_alignment.sequence_of(log, ctx["trace_index"])
                if key not in seen:
                    seen.add(key)
                    pool.append(ctx)
            return pool[:count]

    import pandas as pd
    n_traces = min(len(log), len(alignments))
    fitness_df = pd.DataFrame(
        [{"fitness": float(a.get("fitness", 1.0))} for a in alignments[:n_traces]])
    indices = trace_alignment.pick_indices(log, alignments, fitness_df, count, rule,
                                           pattern=pattern)
    return [by_index[i] for i in indices if i in by_index]


def _multi_trace_alignment_figures(log, alignments, shown, model_path, output_dir):
    """Chevron, BPMN and move table for more than one trace.

    Drawn by task04's renderers rather than by stacked copies of task34's
    single-trace ones: comparing traces is task04's figure, and two tasks
    drawing the same comparison two ways is what the trace-alignment class
    exists to prevent. Only the output filename differs.
    """
    import tasks.task04 as task04

    records = trace_alignment.trace_records(
        log, alignments, [ctx["trace_index"] for ctx in shown])
    task04.task04_flow_chart_basic(
        records, output_dir, model_path=model_path,
        filename="task34_flow_chart_basic.svg")
    task04.task04_flow_chart_elaborate(
        records, model_path, output_dir,
        filename="task34_flow_chart_elaborate.svg")
    task04.task04_table(
        records, model_path, output_dir,
        filename="task34_table.svg",
        title="Violations by Activity Across Traces")


# ── Public API ────────────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None, violated_activity=None,
             trace_ids=None, trace_pick_rule="worst_fitness", trace_count=1,
             violation_pattern=""):
    """Generate all Task 34 SVGs into output_dir.

    The task presents "one trace or few traces simultaneously". With one trace —
    the default — every idiom draws that trace, as it always has. With more, the
    three trace-alignment idioms (chevron, BPMN, move table) draw all of them
    side by side through task04's renderers, and the per-activity summaries
    (bar chart, heatmap, matrix) give each trace its own bar or column. Every
    idiom therefore speaks about the same traces, and names the same move
    types.

    violation_pattern : str
        "activity|move type" defining the guideline (trace_alignment). Every
        rule then picks among the traces that violate it.

    violated_activity : str | None
        The superseded activity-only form, kept so an experiment specified
        before `violation_pattern` existed still shows its trace. Ignored when a
        pattern is given.
    """
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

    shown = _select_ctxs(ctxs, log, alignments, trace_ids=trace_ids,
                         rule=trace_pick_rule, count=trace_count,
                         pattern=violation_pattern,
                         violated_activity=violated_activity)
    worst = shown[0] if shown else _pick_ctx(ctxs, {"violated_activity": violated_activity})

    logger.info(
        f"      Representative: {worst['trace_label']} "
        f"(fitness={worst['fitness']:.4f}, violations={worst['n_violations']})"
    )
    if len(shown) > 1:
        logger.info(f"      -> {len(shown)} traces shown side by side.")

    write_traces_sidecar(output_dir, [{
        "label":      f"Trace {position + 1}",
        "activities": trace_activities(log[ctx["trace_index"]]),
    } for position, ctx in enumerate(shown or [worst])])

    drawn = shown or [worst]
    task34_bar_chart(drawn,                         output_dir)
    if len(shown) > 1:
        _multi_trace_alignment_figures(log, alignments, shown, model_path, output_dir)
    else:
        task34_table(worst,                         output_dir)
        task34_flow_chart_basic(worst,              output_dir)
        task34_flow_chart_elaborate(worst,          model_path, output_dir)
    task34_heatmap(drawn,                           output_dir)
    task34_matrix(drawn,                            output_dir)
