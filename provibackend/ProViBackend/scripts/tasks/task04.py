"""
tasks/task04.py – Task ID 4: Describe / Compare / Conformance across individual traces.

Task 4 asks "How does the degree of conformance differ between multiple logs or
traces?", and `analysis_level` picks which half is answered. At log level the
task draws task01's sub-log comparison instead (see LEVEL_PARAM below); what
follows describes the trace level, the default.

Every idiom shows the *same* concrete traces (individual traces, NOT aggregated
variants), and every one states each trace's fitness — the "overall degree of
conformance" the task asks about. That is the payload they share:

  fitness only — how far apart the traces are
    * bar_chart        – one bar per trace in that trace's colour, fitness on the y-axis
    * matrix           – trace × Fitness grid, numbers only (colourless)

  fitness + alignment — and where the difference comes from
    * table                – a leading Fitness row, then activity × trace,
                             cell = "step · move type"
    * flow_chart_basic     – one chevron strip per trace, labelled with its
                             fitness, each activity coloured by its alignment
                             move type (needs alignments)
    * flow_chart_elaborate – the BPMN model drawn once per trace, subtitled the
                             same way (needs alignments and the model)

The second family is therefore not information-*equivalent* to the first: it
adds where the deviations are. Nothing is missing from it, which is what a
participant needs to answer the question at all. Within it the three differ in
what they can express: the chevron lays the moves out in alignment order, the
BPMN adds the model's structure but not that order, and the table carries the
order as a step number per cell. All three show a log move separately from the
model task of the same name.

The fitness labels are opt-in on the three shared renderers (``show_fitness``),
because task09, task14, task27, task28 and task34 reuse them to ask about the
deviations themselves, where a fitness number would be a payload no other idiom
of theirs carries.

Fitness is rounded to 3 decimals wherever it appears; there is no #Traces
column, no conformant/non-conformant colour coding, and no pre-computed
differences — the participant derives the conformance assessment themselves (the
alignment idioms mark individual moves, not whole traces).

Public API:
    generate(log, fitness_df, output_dir, trace_ids=None, alignments=None,
             model_path=None, analysis_level="trace",
             trace_pick_rule="violation_gap", trace_count=SAMPLE_N,
             outcome_activity="")
        log              – PM4Py EventLog
        fitness_df       – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir       – directory where SVGs are written
        analysis_level   – "trace" (the idioms above) or "log", which draws
                           task01's sub-log comparison instead and returns
        trace_ids        – optional list of case-id strings to show; empty =
                           chosen by trace_pick_rule, trace_count of them (see
                           trace_alignment.PICK_RULES)
        alignments       – raw alignment results; needed for the rule-based
                           trace choice and the flow-chart idioms
        model_path       – reference BPMN, for the model-based idioms
        outcome_activity – log level only: the activity that splits the log;
                           empty = inferred by shared.infer_outcome_activity
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_basic", "flow_chart_elaborate",
          "bar_chart", "table", "matrix"]


import trace_alignment

#: Task 4 is asked at two levels ("At the log level ... At the trace level ..."),
#: and they are different pipelines, not two views of one: at log level the log
#: is split into sub-logs and their conformance compared — task01's question and
#: task01's figures — while at trace level the traces' alignments are compared.
#: The level therefore routes generation, and each level's parameters are hidden
#: at the other.
LEVEL_PARAM = {
    "key": "analysis_level",
    "slot": "level",
    "label": "Level the conformance is compared at",
    "hint": "Whether the figures compare sub-logs or individual traces",
    "widget": "select-one",
    "options": [
        {"value": "trace", "label": "Trace level — the alignment of individual traces"},
        {"value": "log",   "label": "Log level — sub-logs split by a condition"},
    ],
    "default": "trace",
    # A fixed-option select whose default silently decides what is drawn.
    # Required so /specify marks it and refuses an empty one: the choice is
    # always in force, and without the asterisk an admin cannot tell it was
    # made for them. Contrast the parameters that stay optional, where an
    # empty value has a stated meaning their own label gives.
    "required": True,
}

PARAM_SPEC = [
    LEVEL_PARAM,
    {
        "key": "outcome_activity",
        "slot": "split",
        "label": "Log split condition (activity present in trace marks the Positive group)",
        "hint": "The 'Positive' group is made up of traces that contain this activity",
        "widget": "activity-picker",
        "source": "log.activities",
        "default": "",
        # Required where it applies: validate_params refuses to generate the log
        # level without it, so "(optional)" was the UI contradicting the backend.
        "required": True,
        "visible_if": {"analysis_level": "log"},
    },
    *trace_alignment.selection_params(
        rules=["violation_gap", "worst_fitness", "most_frequent_variants"],
        default_rule="violation_gap",
        count_default=2, count_min=2, count_max=4,
        only_when={"analysis_level": "trace"},
    ),
    {**trace_alignment.VIOLATION_PATTERN_PARAM,
     "visible_if": {**trace_alignment.VIOLATION_PATTERN_PARAM["visible_if"],
                    "analysis_level": "trace"}},
]


def validate_params(log, params) -> list:
    """Each level validates only its own half.

    At log level the split condition has to actually split: an activity every
    trace contains (or none does) puts every trace in one group and the
    comparison has nothing to compare.
    """
    params = params or {}
    if params.get("analysis_level", "trace") == "log":
        activity = (params.get("outcome_activity") or "").strip()
        if not activity:
            return ["Pick the activity whose presence marks the Positive group."]
        present = sum(
            1 for trace in log
            if any(str(e.get("concept:name", "")) == activity for e in trace)
        )
        if present == 0:
            return [f"No trace contains '{activity}' — every trace would be Negative."]
        if present == len(log):
            return [f"Every trace contains '{activity}' — no trace would be Negative."]
        return []

    return trace_alignment.validate_selection(log, params, min_traces=2, max_traces=4)


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
    contrasting_text_color, categorical_colors,
    GREY_MED, GREY_LIGHTER, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    trace_activities, write_traces_sidecar,
)

# Default number of traces to sample when the admin doesn't pick specific ones.
SAMPLE_N = 2

# The bar chart gives each compared trace one colour, from `categorical_colors`
# — cividis's blue and yellow ends, the pair task01 and task03 draw their bars
# with, extended to the 3-4 traces this task also allows. It encodes WHICH
# trace, never how conformant it is: the task asks the participant to read
# conformance off the fitness values, so no idiom here colours a trace by
# conformance.

# Consistent figure title across every idiom.
TITLE = "Trace Conformance Fitness"

# Activity-name font in the chevron flow chart. The chevron width has a fixed
# margin on top of its per-character allowance, so realistic activity names stay
# inside the arrow at 13pt; the shared auto-shrink still catches any outlier.
# Bump here to retune.
_CHEVRON_FONT = 17


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


def _task04_select_compare_traces(log, alignments, fitness_df, trace_ids=None, n=2,
                                  rule="violation_gap", pattern=""):
    """Pick the traces to compare, as a list of dicts
    {label, case_id, fitness, rows, violations}.

    Admin-selected ``trace_ids`` are used in order when given; otherwise the
    class's rule picks them. The rule used to live here and had two faults the
    shared one fixes: it could pick a trace with fitness 1.0 — nothing to
    compare against the other trace's deviations — and at three traces or more
    it could return the same activity sequence twice.
    """
    n_traces = min(len(log), len(alignments), len(fitness_df))
    if n_traces == 0:
        return []

    def _info(i, label):
        rows, viol = _task04_trace_violations(alignments, i)
        return {"label": label, "case_id": str(log[i].attributes.get("concept:name", i)),
                "trace_index": i,
                "fitness": round(float(fitness_df.iloc[i]["fitness"]), 3),
                "rows": rows, "violations": viol}

    if trace_ids:
        by_id = _task04_case_index(log)
        chosen = [by_id[str(t)] for t in trace_ids if str(t) in by_id][:max(n, len(trace_ids))]
    else:
        chosen = trace_alignment.pick_indices(log, alignments, fitness_df, n, rule,
                                              pattern=pattern)

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


def _task04_violation_activities(rows):
    """Model activities the trace violates by skipping them (move on model)."""
    return {str(r["model_move"]) for r in rows if r["moveType"] == "Model Move"}


def _task04_move_steps(rows):
    """[(activity, move type, step)] for one trace, in alignment order.

    Positional, not keyed by activity name. An activity can take part in more
    than one move of the same trace: in the order-to-cash log a trace executes
    an extra "Ship Order" (log move) and later skips the modelled "Ship Order"
    (model move). The name-keyed map this replaces let the second overwrite the
    first, so the log move — the deviation the task asks about, and the one the
    chevron draws in navy — never reached the table at all.

    ``step`` is the position in the alignment, which is the order the chevron
    lays its arrows out in; a model move therefore has a step although the log
    never executed it.
    """
    out = []
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous Move":
            a = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
        elif mt == "Model Move":
            a = str(r["model_move"])
        elif mt == "Log Move":
            a = str(r["log_move"])
        else:
            continue
        out.append((a, mt, len(out) + 1))
    return out


#: Row-label suffix for a log move — an activity the model does not expect at
#: that point. It gets a row of its own even when an activity of that name is
#: also a model task (the screenshot case: "Check Credit" as a model task and
#: "Check Credit" inserted a second time), which is what the BPMN idiom draws as
#: an external badge rather than colouring the model node.
#:
#: It says "(Log Move)" rather than "(inserted)" because that is what every other
#: figure in this class calls it. "Inserted" was a second word for one thing, and
#: a reader had to work out that it meant the same as the "Log Move" in the cell
#: beside it.
_INSERTED_SUFFIX = " (Log Move)"


def _task04_row_cells(steps, show_order: bool = True):
    """row label -> "step · move type" for one trace, or just the move type.

    Log moves take their own row label so they cannot collide with the model
    task of the same name. An activity that appears twice in the *same* role
    (a modelled loop) still keeps only its first occurrence — rare, and one row
    per activity is what makes this a table rather than a second chevron.
    """
    cells = {}
    for a, mt, step in steps:
        key = f"{a}{_INSERTED_SUFFIX}" if mt == "Log Move" else a
        cells.setdefault(key, f"{step} · {mt}" if show_order else mt)
    return cells


def _task04_model_task_names(model_path):
    """Ordered task names of the guideline model (for the not-in-trace chevrons)."""
    if not model_path:
        return []
    try:
        els = parse_bpmn_model(model_path).get("elements", {})
    except Exception:
        return []
    vals = els.values() if isinstance(els, dict) else els
    return [e.get("name", "") for e in vals if e.get("kind") == "task" and e.get("name")]


def _trace_caption(trace, show_fitness: bool) -> str:
    """"Trace 1", or "Trace 1 — Fitness 0.571" when the caller asks for it.

    Falls back to the bare label when the record carries no fitness, so a caller
    that builds its own records cannot break on the key.
    """
    label = str(trace["label"])
    if not show_fitness or trace.get("fitness") is None:
        return label
    return f"{label} — Fitness {float(trace['fitness']):.3f}"


def task04_flow_chart_basic(selected, output_dir: str, model_path=None, *,
                            filename="task04_flow_chart_basic.svg", title=None,
                            show_fitness=False):
    """Chevron flow chart: one horizontal chevron strip per selected trace, stacked
    so the two traces sit side by side (top vs bottom). Each activity chevron is
    coloured by its alignment move type — Synchronous Move, Model Move or Log Move;
    only the activities that trace actually touches are shown.

    ``filename`` lets the other trace-alignment tasks (task09, task14, task27,
    task28, task34) draw this same figure into their own output directory —
    the figure is the class's, not task04's, and one renderer keeps them from
    drifting into five encodings of one thing. ``title`` is opt-in (None keeps
    every existing caller's current, title-less layout unchanged).

    ``show_fitness`` puts each trace's fitness in its strip label. Opt-in,
    because it answers task04's question — the overall degree of conformance —
    and the other tasks in this class ask about the deviations themselves, where
    a fitness number would be an extra payload no other idiom of theirs carries.
    """
    path = os.path.join(output_dir, filename)
    if not selected:
        fig, ax = plt.subplots(figsize=(7, 3)); ax.axis("off")
        ax.text(0.5, 0.5, "No trace data available.", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
        save_svg(fig, path)
        return

    nodes_per_trace = [chevron_nodes_from_alignment_rows(t["rows"]) for t in selected]

    fig_w = max((chevron_figure_width(n) for n in nodes_per_trace if n), default=9.0)
    n_rows = len(selected)
    fig_h = 1.9 * n_rows + 1.6

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(n_rows, 1, hspace=0.9)
    for r, (trace, nodes) in enumerate(zip(selected, nodes_per_trace)):
        ax = fig.add_subplot(gs[r])
        if nodes:
            draw_chevron_strip(ax, nodes, fontsize=_CHEVRON_FONT)
        else:
            ax.axis("off")
            ax.text(0.5, 0.5, "(empty trace)", ha="center", va="center",
                    transform=ax.transAxes, fontsize=FONT_ANNOT)
        ax.set_title(_trace_caption(trace, show_fitness), fontsize=FONT_LABEL,
                     loc="left", pad=6)

    handles = [mpatches.Patch(facecolor=c, edgecolor="#4a4a4a", label=lbl)
               for lbl, c in _MOVE_LEGEND]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
               ncol=len(_MOVE_LEGEND), frameon=False, fontsize=FONT_ANNOT - 1)
    if title:
        fig.suptitle(title, fontsize=FONT_TITLE, y=0.99)
        fig.tight_layout(rect=[0, 0.08, 1, 0.93])
    else:
        fig.tight_layout(rect=[0, 0.08, 1, 1.0])
    save_svg(fig, path)


def _task04_bpmn_node_style(rows):
    """node_style_fn colouring model tasks by this trace's alignment: synchronous
    move -> yellow (conformant), model move -> grey (skipped); everything else
    white. Log moves are NOT painted onto model nodes — a log move is an activity
    the model does not expect at that point, so it is drawn as an external badge
    (see _task04_log_move_badges), never highlighted inside the model."""
    conform, skipped = _task04_bpmn_move_sets(rows)

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


def _task04_bpmn_move_sets(rows):
    """conform (Synchronous) and skipped (Model Move) activity-name sets for one
    trace — the two sets that decide a model node's colour."""
    conform, skipped = set(), set()
    for r in rows:
        if r["moveType"] == "Synchronous Move":
            lbl = str(r["log_move"]) if str(r["log_move"]) not in _MISSING else str(r["model_move"])
            conform.add(lbl)
        elif r["moveType"] == "Model Move":
            skipped.add(str(r["model_move"]))
    return conform, skipped


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


def task04_flow_chart_elaborate(selected, model_path, output_dir, *,
                                filename="task04_flow_chart_elaborate.svg",
                                title="Trace-Level Conformance on the Process Model",
                                show_fitness=False):
    """BPMN idiom, information-equivalent to the chevron: the guideline model is
    drawn once per trace (stacked), each model task coloured by that trace's
    alignment — Synchronous Move (yellow) or Model Move / skipped (grey). Log Move
    (inserted) activities aren't part of the model, so they are drawn as external
    navy dashed badges floating above their sequence position (never highlighted on
    a model node). Together the panels + badges encode the three move types the
    chevron shows.

    ``show_fitness`` puts each trace's fitness in its panel subtitle; opt-in for
    the reason given on task04_flow_chart_basic."""
    path = os.path.join(output_dir, filename)
    if not selected or not model_path:
        render_empty_state_svg(path, title, "No traces or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path, node_scale=1.6)
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
        "subtitle": _trace_caption(t, show_fitness),
        # Every log move is drawn as an external badge — never highlighted inside
        # the model, since a log move is not part of the model.
        "badges": _task04_log_move_badges(t["rows"]),
    } for t in selected]

    compose_bpmn_panels(
        panels, path,
        title=title,
        legend_items=[
            (GREY_LIGHTER, "#666666", 2, "Synchronous Move"),
            (GREY_MED,     "#444444", 3, "Model Move"),
            (GREY_DARK,    "#8ba0cf", 3, "Log Move", "6 4"),
        ],
        node_font_size=20,
    )


def task04_bar_chart(tdf: pd.DataFrame, output_dir: str):
    """One bar per trace in that trace's colour; fitness value labelled above it."""
    fig, ax = plt.subplots(figsize=(max(7, len(tdf) * 0.75), 5))
    x = np.arange(len(tdf))
    bars = ax.bar(x, tdf["fitness"], color=categorical_colors(len(tdf)),
                  edgecolor="white", width=0.65)
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


def task04_table(selected, model_path, output_dir, *,
                 filename="task04_table.svg",
                 title="Move Type by Activity Across Traces",
                 show_fitness=False, show_order=True):
    """Activity × trace move-type table: one row per activity (model tasks plus
    any inserted ones), one column per compared trace, cell = the step at which
    that trace made the move, and the move (Synchronous Move / Model Move / Log
    Move). Only activities at least one trace touches are listed; a "—" marks an
    activity one trace touches and another does not.

    The tabular twin of the chevron / BPMN views, read as plain text (only the
    header row is coloured). The step carries what the rows cannot: the rows sit
    in model order, so without it a trace that runs two activities out of order
    reads exactly like one that runs them in order — the chevron shows that, and
    this table used to lose it.

    ``show_fitness`` puts a leading "Fitness (0-1)" row above the activities;
    opt-in for the reason given on task04_flow_chart_basic.

    ``show_order=False`` drops the step number, leaving the move type alone in
    the cell. task28 asks for it: the chevron and the BPMN beside it already
    carry the order, and a table that carries it too says more than they do in
    the one channel they cannot match. The cost is the order-blindness described
    above, accepted there because two other idioms cover it."""
    path = os.path.join(output_dir, filename)
    activities = _task04_model_task_names(model_path)
    if not activities or not selected:
        fig, ax = plt.subplots(figsize=(6.5, 3.0))
        ax.axis("off")
        make_table(ax, cell_text=[["—", "—"]], col_labels=["Activity", "Move type"],
                   bbox=[0.05, 0.05, 0.9, 0.92])
        ax.set_title(title, fontsize=FONT_TITLE, pad=3)
        fig.tight_layout(pad=1.2)
        save_svg(fig, path)
        return

    cells_per_trace = [_task04_row_cells(_task04_move_steps(t["rows"]), show_order)
                       for t in selected]
    # Log moves become extra rows, in the order the traces make them.
    inserted = []
    for cells in cells_per_trace:
        for key in cells:
            if key.endswith(_INSERTED_SUFFIX) and key not in inserted:
                inserted.append(key)
    # keep only activities at least one trace actually touches (drop never-touched)
    present = set().union(*(set(c) for c in cells_per_trace)) if cells_per_trace else set()
    rows = [a for a in (list(activities) + inserted) if a in present]
    labels = [t["label"] for t in selected]

    cell_text = []
    # Fitness leads the table: it is what the task asks for (the overall degree
    # of conformance), and the move rows below are where that degree comes from.
    # A column header would carry it too, but at three or four traces the header
    # widths are what set the figure width.
    if show_fitness and any(t.get("fitness") is not None for t in selected):
        cell_text.append(["Fitness (0-1)"] +
                         [("—" if t.get("fitness") is None
                           else f"{float(t['fitness']):.3f}") for t in selected])
    for a in rows:
        text_row = [a]
        for cells in cells_per_trace:
            text_row.append(cells.get(a, "—"))
        cell_text.append(text_row)

    col_labels = (["Activity"] + [f"{lbl} (step · move)" for lbl in labels]
                  if show_order else ["Activity"] + list(labels))
    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig_w = max(6.5, 3.2 + 2.7 * len(labels))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    make_table(
        ax, cell_text=cell_text, col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.9],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=9.5, scale_xy=(1, 1.7), cell_pad=0.1,
    )
    ax.set_title(title, fontsize=FONT_TITLE, pad=3)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task04_matrix(tdf: pd.DataFrame, output_dir: str):
    """Trace × Fitness grid: white cells ruled into a grid, each fitness carried
    by the printed number alone.

    Colourless, as in tasks 01, 03 and 27-32. With a colour scale the matrix
    would be a heatmap that also prints its numbers — one variable encoded
    twice."""
    labels = tdf["label"].tolist()
    data = tdf["fitness"].values.astype(float).reshape(-1, 1)

    fig_h = max(3.0, 0.5 * len(labels) + 1.4)
    fig, ax = plt.subplots(figsize=(3.6, fig_h))
    draw_value_heatmap(
        fig, ax, data, labels, ["Fitness"],
        cbar_label="Fitness", cell_fmt="{:.3f}", annotate=True,
        colorless=True,
    )
    ax.set_title(TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task04_matrix.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, trace_ids=None, alignments=None, model_path=None,
             analysis_level="trace", trace_pick_rule="violation_gap", trace_count=SAMPLE_N,
             violation_pattern="", outcome_activity=""):
    """Generate all Task ID 4 SVGs into output_dir.

    ``analysis_level`` routes the whole task: "log" answers the question's
    log-level half, which is task01's pipeline (sub-logs split by
    ``outcome_activity``, their conformance compared), and returns. "trace" — the
    default — compares the alignments of individual traces below.

    ``trace_ids`` is the admin-configured list of case-id strings (from
    PARAM_SPEC "trace_ids"). When empty/None the traces are chosen by
    ``trace_pick_rule`` (see trace_alignment.PICK_RULES), ``trace_count`` of
    them. Every idiom renders the same traces so the views are directly
    comparable.

    ``alignments`` (optional) enables the trace-level flow-chart idioms, which
    compare the alignment (conformance) patterns of the traces side by side.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 4 visualizations ---")

    if analysis_level == "log":
        import tasks.task01 as task01
        from shared import infer_outcome_activity
        activity = outcome_activity or infer_outcome_activity(log)
        logger.info(f"      -> Log level: comparing sub-logs split on '{activity}'.")
        task01.generate(log, fitness_df, output_dir, outcome_activity=activity)
        return

    # Single trace selection shared by EVERY idiom: the admin-selected traces, or
    # (default) the two traces with the largest violation-count gap. This needs
    # alignments; without them we fall back to the first SAMPLE_N in log order.
    selected = _task04_select_compare_traces(
        log, alignments, fitness_df, trace_ids=trace_ids,
        n=trace_count, rule=trace_pick_rule, pattern=violation_pattern,
    ) if alignments else []
    if selected:
        tdf = pd.DataFrame([{"case_id": t["case_id"], "fitness": t["fitness"], "label": t["label"]}
                            for t in selected])
    else:
        tdf = _task04_build_trace_df(log, fitness_df, trace_ids=trace_ids,
                                     sample_n=trace_count)
    if tdf.empty:
        logger.warning("      Skipped Task 4: no trace data available.")
        return

    source = "admin-selected" if trace_ids else trace_pick_rule
    logger.info(f"      -> Comparing {len(tdf)} traces ({source}).")

    case_index = _task04_case_index(log)
    write_traces_sidecar(output_dir, [
        {
            "label":      str(row["label"]),
            "activities": trace_activities(log[case_index[str(row["case_id"])]]),
        }
        for _, row in tdf.iterrows() if str(row["case_id"]) in case_index
    ])

    task04_bar_chart(tdf, output_dir)
    task04_matrix(tdf, output_dir)

    # Trace-level pattern comparison — chevron, BPMN and the move-type table of
    # the same traces (all need the alignments / model).
    if selected:
        # show_fitness: task04 asks for the overall degree of conformance, so
        # the alignment idioms state it too and every idiom of this task can
        # answer the question. The other tasks that reuse these renderers ask
        # about the deviations themselves and leave it off.
        task04_flow_chart_basic(selected, output_dir, model_path=model_path,
                                show_fitness=True)
        task04_flow_chart_elaborate(selected, model_path, output_dir,
                                    show_fitness=True)
        task04_table(selected, model_path, output_dir, show_fitness=True)
