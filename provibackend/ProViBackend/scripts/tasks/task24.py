"""
tasks/task24.py – Task ID 24: Explore / Discover / Guideline violations in model.

Discovers a process model from the selected traces and compares it, as a model,
to the reference BPMN that holds the desired behaviour. Every idiom shows the
two models side by side and marks what only one of them has.

Public API:
    generate(log, model_path, output_dir, trace_ids=None,
             trace_count=DEFAULT_VARIANTS, noise_threshold=DEFAULT_NOISE)
        log             – PM4Py EventLog
        model_path      – path to the reference (desired) BPMN file
        output_dir      – directory where SVGs are written
        trace_ids,
        trace_count     – what the model is discovered from
        noise_threshold – how much infrequent behaviour the miner leaves out

Three idioms, all comparing like with like:
    task24_flow_chart_elaborate_bpmn  →  flow_chart_elaborate  (BPMN vs BPMN)
    task24_flow_chart_basic           →  flow_chart_basic      (strip vs strip)
    task24_table                      →  table                 (column vs column)
"""

import logging
logger = logging.getLogger(__name__)

#: Canonical idiom keys (create_all_visualizations._FILE_RENAME maps the
#: flow_chart_elaborate_bpmn file stem onto flow_chart_elaborate). This used to
#: declare the file stem itself, which is not a key the Idiom collection knows.
IDIOMS = ["flow_chart_elaborate", "flow_chart_basic", "table"]

import trace_alignment

#: Which traces the model is discovered from. The task's wording — "multiple
#: traces are taken and the model is discovered" — makes that the whole choice,
#: so there is no rule picker: either the admin names the traces or the most
#: frequent variants are taken, and `trace_count` is how many of them.
#:
#: Unlike the trace-alignment tasks this selection is NOT restricted to
#: violating traces. Discovery describes the behaviour that occurred; leaving out
#: the conformant traces would discover a model of the deviations alone and
#: overstate every difference against the guideline.
PARAM_SPEC = [
    dict(trace_alignment.TRACE_SELECTION_MODE_PARAM),
    dict(trace_alignment.TRACE_IDS_PARAM),
    {**trace_alignment.trace_count_param(3, 1, 15),
     "label": "How many of the most frequent variants to discover from",
     "hint": "The model is discovered from every trace of these variants",
     "visible_if": {"trace_selection_mode": "auto"}},
    # The miner's own filter, and the lever that decides how large the
    # difference comes out: at 0.0 every observed path enters the discovered
    # model, so one stray trace becomes a structural difference against the
    # guideline. It replaces a hard-coded minimum edge count that no admin
    # could see or set.
    {"key": "noise_threshold",
     "label": "How much infrequent behaviour to leave out of the discovered model",
     "hint": "0.0 keeps every observed path; higher values discover only the "
             "common behaviour",
     "widget": "number", "min": 0.0, "max": 0.4, "step": 0.05,
     "default": 0.2, "required": True},
]


def validate_params(log, params) -> list:
    """Discovery needs behaviour to generalise from; one trace discovers itself."""
    params = params or {}
    ids = trace_alignment.selected_trace_ids(params)
    if params.get("trace_selection_mode") == "manual" and len(ids) == 1:
        return ["Select at least two traces — a model discovered from one trace "
                "is that trace."]
    return trace_alignment.validate_selection(log, params, min_traces=1, max_traces=15)

import os
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

from shared import (
    parse_bpmn_model, compose_bpmn_panels, save_svg, make_table,
    auto_col_widths, render_empty_state_svg,
    draw_chevron_strip, chevron_figure_width,
    GREY_DARK, GREY_MED, GREY_LIGHTER,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

#: Default number of most-frequent variants the model is discovered from.
DEFAULT_VARIANTS = 3

#: Default miner noise filter. Not 0.0: on a real log every rare path would
#: otherwise enter the discovered model and the comparison would be against the
#: log's noise rather than against its process.
DEFAULT_NOISE = 0.2

#: One title over all three idioms, in the words of the task.
_TASK24_TITLE = "Where the Discovered Model Differs from the Desired Model"

_DESIRED_LABEL = "Desired model (guideline)"
_DISCOVERED_LABEL = "Discovered model (from the selected traces)"


def _discovered_caption(described: str) -> str:
    """The discovered panel's caption, naming what it was discovered from."""
    return f"Discovered model (from {described})" if described else _DISCOVERED_LABEL

#: The three categories every idiom encodes, in one palette.
#: "In both" is white because that is what the BPMN renderer already means by an
#: unremarkable node; the two differences take the platform's pair, cividis navy
#: and cividis bright yellow.
_BOTH = "In both models"
_DESIRED_ONLY = "Only in the desired model"
_DISCOVERED_ONLY = "Only in the discovered model"

#: Spelled as hex, not "white": contrasting_text_color parses the fill to pick
#: the chevron's label colour and only understands hex.
_CATEGORY_FILL = {
    _BOTH: "#ffffff",
    _DESIRED_ONLY: GREY_DARK,
    _DISCOVERED_ONLY: GREY_LIGHTER,
}

_LEGEND_ITEMS = [
    (_CATEGORY_FILL[_BOTH], GREY_MED, 2, _BOTH),
    (GREY_DARK, GREY_DARK, 2, _DESIRED_ONLY),
    (GREY_LIGHTER, GREY_MED, 2, _DISCOVERED_ONLY),
]


def _select_sublog(log, trace_ids=None, n_variants: int = DEFAULT_VARIANTS):
    """(sub-log, description) — the traces the model is discovered from.

    With ``trace_ids`` the named traces, in the order given. Otherwise **every
    trace of** the ``n_variants`` most frequent variants, not one representative
    each: the discovered model is a description of behaviour, and edge
    frequencies that counted each variant once would make a variant seen 212
    times look like one seen 3 times.
    """
    if trace_ids:
        index_of = trace_alignment.case_index(log)
        chosen = [log[index_of[str(t)]] for t in trace_ids if str(t) in index_of]
        return chosen, f"{len(chosen)} selected trace(s)"

    wanted = []
    for i in trace_alignment.variant_order(log, len(log))[:max(1, n_variants)]:
        wanted.append(trace_alignment.sequence_of(log, i))
    wanted_set = set(wanted)
    sub = [trace for trace in log
           if tuple(str(e.get("concept:name", "")) for e in trace) in wanted_set]
    return sub, f"{len(sub)} trace(s) of the {len(wanted)} most frequent variant(s)"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _discover_model(sublog, noise_threshold: float):
    """Discover a BPMN from ``sublog`` and return it parsed like the guideline.

    pm4py's inductive miner produces a sound process tree, converts it to BPMN
    and lays it out; written to a temporary file it is an ordinary BPMN with
    diagram interchange, so ``parse_bpmn_model`` reads it into exactly the
    structure the guideline model arrives in. Both sides of the comparison are
    then the same kind of object, which is what lets one renderer draw them
    both.

    The directly-follows graph the miner builds on the way stays inside pm4py:
    it is a step towards the model, not something this platform draws.
    """
    import pm4py
    from pm4py.objects.log.obj import EventLog

    # _select_sublog hands back a plain list of traces; the miner wants a log.
    sub = sublog if isinstance(sublog, EventLog) else EventLog(list(sublog))
    bpmn = pm4py.discover_bpmn_inductive(sub, noise_threshold=noise_threshold)
    handle, path = tempfile.mkstemp(suffix=".bpmn")
    os.close(handle)
    try:
        pm4py.write_bpmn(bpmn, path, auto_layout=True)
        return parse_bpmn_model(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _named_tasks(parsed) -> dict:
    """{element id: name} for the tasks that carry a name.

    The miner emits silent (tau) steps for structure. They have no name, stand
    for nothing a participant could look for in the other model, and would
    otherwise show up as empty boxes in the difference.
    """
    return {eid: e["name"] for eid, e in parsed["elements"].items()
            if e["kind"] == "task" and e.get("name")}


#: No edge-level difference is drawn. Collapsing gateways to get comparable
#: task-to-task edges turns each model into a reachability closure, and two
#: models built by different means (a hand-drawn guideline, a miner's process
#: tree) differ in dozens of closure pairs while describing the same behaviour
#: — on the sample guideline, sixteen "differences" with no reader-visible
#: meaning. Each panel draws its own flows; the comparison lives in the nodes.

def _linearise(parsed) -> list:
    """The model's named activities in reading order.

    Breadth-first from the start event over the sequence flows, so an activity
    that can only happen after another comes after it; ties broken by the
    layout's x coordinate, which both the guideline's own diagram and pm4py's
    auto-layout lay out left to right.

    A graph pressed into a line loses concurrency and loops: two models that
    differ only in whether A and B are parallel or sequential produce the same
    list. That is the chevron's and the table's known cost, and the reason the
    BPMN idiom is in this set.
    """
    elements = parsed["elements"]
    shapes = parsed["shapes"]
    adj = {}
    for sf in parsed["sequence_flows"].values():
        adj.setdefault(sf["source"], []).append(sf["target"])

    starts = [eid for eid, e in elements.items() if e["kind"] == "startEvent"]
    # Longest path from the start, not shortest. With an exclusive choice the
    # shortest path reaches everything after the choice through whichever
    # branch is briefest, which put "Close Case" ahead of the activities of the
    # long branch on the sample guideline. The longest path puts an activity
    # after everything that can precede it, which is what a step number means
    # to a reader. Relaxation is capped at one pass per element so a loop in
    # the model cannot spin.
    depth = {eid: 0 for eid in starts}
    flows = list(parsed["sequence_flows"].values())
    for _ in range(len(elements) + 1):
        changed = False
        for sf in flows:
            src, tgt = sf["source"], sf["target"]
            if src in depth and depth.get(tgt, -1) < depth[src] + 1:
                depth[tgt] = depth[src] + 1
                changed = True
        if not changed:
            break

    def sort_key(item):
        eid, _name = item
        box = shapes.get(eid) or {}
        return (depth.get(eid, len(elements)), box.get("x", 0.0), box.get("y", 0.0))

    return [name for _eid, name in sorted(_named_tasks(parsed).items(), key=sort_key)]


def _model_diff(desired, discovered) -> dict:
    """The one payload all three idioms draw.

    ``activities``  {name: category}, in the desired model's reading order with
                    the discovered model's own activities appended.
    ``order``       {name: (position in desired, position in discovered)},
                    1-based, None where the model does not hold the activity.

    Symmetric, because both sides went through the same parser and the same
    linearisation. The comparison it replaced was not: a smoothed set of model
    edges stood against raw directly-follows pairs counted off the log, so any
    rare path in the log became a structural difference against the guideline.
    """
    desired_order = _linearise(desired)
    discovered_order = _linearise(discovered)
    desired_set, discovered_set = set(desired_order), set(discovered_order)

    names = list(desired_order) + [n for n in discovered_order if n not in desired_set]
    activities = {}
    for name in names:
        if name in desired_set and name in discovered_set:
            activities[name] = _BOTH
        elif name in desired_set:
            activities[name] = _DESIRED_ONLY
        else:
            activities[name] = _DISCOVERED_ONLY

    order = {
        name: (desired_order.index(name) + 1 if name in desired_set else None,
               discovered_order.index(name) + 1 if name in discovered_set else None)
        for name in names
    }

    return {
        "desired": desired, "discovered": discovered,
        "desired_order": desired_order, "discovered_order": discovered_order,
        "activities": activities, "order": order,
    }


def _difference_summary(diff: dict) -> str:
    """One line naming what the three idioms show, in their own terms.

    Activities on one side only, and activities both models hold at a different
    step — which is what a reader compares when they put the two strips, the
    two panels or the two columns side by side.
    """
    activities = diff["activities"]
    only_desired = sum(1 for v in activities.values() if v == _DESIRED_ONLY)
    only_discovered = sum(1 for v in activities.values() if v == _DISCOVERED_ONLY)
    moved = sum(1 for a, b in diff["order"].values()
                if a is not None and b is not None and a != b)
    if not (only_desired or only_discovered or moved):
        return "No differences between the discovered and the desired model."
    parts = []
    if only_desired:
        parts.append(f"{only_desired} activity(ies) only in the desired model")
    if only_discovered:
        parts.append(f"{only_discovered} activity(ies) only in the discovered model")
    if moved:
        parts.append(f"{moved} activity(ies) at a different step")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Idioms
# ---------------------------------------------------------------------------

def _node_style_fn(diff: dict, side: str):
    """A BPMN node_style_fn painting this model's tasks by the shared category."""
    activities = diff["activities"]
    own = _DESIRED_ONLY if side == "desired" else _DISCOVERED_ONLY

    def style(eid, elem):
        name = elem.get("name") or ""
        if elem.get("kind") != "task" or not name:
            return ("white", GREY_MED, 2, GREY_DARK)
        category = activities.get(name, own)
        fill = _CATEGORY_FILL[category]
        text = "white" if category == _DESIRED_ONLY else GREY_DARK
        return (fill, GREY_MED if category != _DESIRED_ONLY else GREY_DARK, 2, text)

    return style


def task24_flow_chart_elaborate_bpmn(diff: dict, output_dir: str, subtitle: str = ""):
    """Both models as BPMN, one above the other, in one colour vocabulary.

    It used to be the guideline alone, annotated with what a directly-follows
    graph had found: one model and a legend answering a question about two.
    Now a BPMN is compared with a BPMN, which is the only way a participant can
    see *where* the shapes differ rather than be told how many differ.
    """
    path = os.path.join(output_dir, "task24_flow_chart_elaborate_bpmn.svg")
    compose_bpmn_panels(
        [
            {"parsed": diff["desired"], "subtitle": _DESIRED_LABEL,
             "node_style_fn": _node_style_fn(diff, "desired")},
            {"parsed": diff["discovered"], "subtitle": _discovered_caption(subtitle),
             "node_style_fn": _node_style_fn(diff, "discovered")},
        ],
        path,
        title=_TASK24_TITLE,
        legend_items=_LEGEND_ITEMS,
    )


def task24_flow_chart_basic(diff: dict, output_dir: str, subtitle: str = ""):
    """Both models as a chevron strip, one above the other.

    Each strip is that model's activities in reading order, each chevron
    coloured by the same three categories the BPMN uses. Strip against strip:
    a gap in the upper row is an activity the discovery did not find, a
    coloured chevron in the lower row one the guideline does not hold.
    """
    path = os.path.join(output_dir, "task24_flow_chart_basic.svg")
    rows = [(_DESIRED_LABEL, diff["desired_order"]),
            (_DISCOVERED_LABEL, diff["discovered_order"])]
    if not any(names for _lbl, names in rows):
        render_empty_state_svg(path, _TASK24_TITLE, "No activities in either model.")
        return

    nodes_per_row = [
        [{"label": name, "color": _CATEGORY_FILL[diff["activities"][name]]}
         for name in names]
        for _lbl, names in rows
    ]
    fig_w = max((chevron_figure_width(n) for n in nodes_per_row if n), default=9.0)
    fig = plt.figure(figsize=(fig_w, 1.9 * len(rows) + 1.8))
    gs = gridspec.GridSpec(len(rows), 1, hspace=0.9)
    for r, ((label, _names), nodes) in enumerate(zip(rows, nodes_per_row)):
        ax = fig.add_subplot(gs[r])
        if nodes:
            draw_chevron_strip(ax, nodes, fontsize=9.5)
        else:
            ax.axis("off")
            ax.text(0.5, 0.5, "(no activities)", ha="center", va="center",
                    transform=ax.transAxes, fontsize=FONT_ANNOT)
        ax.set_title(label, fontsize=FONT_LABEL, loc="left", pad=6)

    handles = [mpatches.Patch(facecolor=_CATEGORY_FILL[c], edgecolor="#4a4a4a", label=c)
               for c in (_BOTH, _DESIRED_ONLY, _DISCOVERED_ONLY)]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
               ncol=3, frameon=False, fontsize=FONT_ANNOT - 1)
    fig.suptitle(_TASK24_TITLE, fontsize=FONT_TITLE, y=0.98)
    # Set explicitly rather than through tight_layout: the chevron axes carry
    # hand-placed polygons in data coordinates, which tight_layout cannot
    # measure — it warns and then guesses.
    fig.subplots_adjust(left=0.04, right=0.98, top=0.84, bottom=0.14)
    save_svg(fig, path)


def task24_table(diff: dict, output_dir: str, subtitle: str = ""):
    """The two models as two columns: each activity's step in each of them.

    Column against column, which is the table's version of strip against strip.
    A cell holds the position the activity has in that model, so the table says
    both what is missing — an em dash — and what moved, which a pair of
    presence ticks could not.
    """
    path = os.path.join(output_dir, "task24_table.svg")
    order = diff["order"]
    if not order:
        render_empty_state_svg(path, _TASK24_TITLE, "No activities in either model.")
        return

    def cell(position):
        return f"Step {position}" if position else "—"

    names = list(diff["desired_order"])
    names += [n for n in diff["discovered_order"] if n not in set(names)]
    cell_text = [[name, cell(order[name][0]), cell(order[name][1])] for name in names]
    col_labels = ["Activity", _DESIRED_LABEL, _DISCOVERED_LABEL]

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig_w = max(8.0, 5.0 + 0.09 * max((len(n) for n in names), default=10))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.88],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=10.5,
        scale_xy=(1, 1.7),
        zebra=True,
    )
    ax.set_title(_TASK24_TITLE, fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, model_path: str, output_dir: str, trace_ids=None,
             trace_count: int = DEFAULT_VARIANTS,
             noise_threshold: float = DEFAULT_NOISE):
    """Generate all Task ID 24 SVGs into output_dir.

    ``trace_ids`` / ``trace_count`` choose what the model is discovered from —
    the named traces, or every trace of the ``trace_count`` most frequent
    variants. The three idioms then put the discovered model beside the
    guideline, comparing like with like: BPMN with BPMN, chevron strip with
    chevron strip, table column with table column.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 24 visualizations ---")

    if not log:
        logger.warning("      task24: empty log — skipping.")
        return
    if not model_path:
        logger.warning("      task24: no reference model — nothing to compare against.")
        return

    sublog, described = _select_sublog(log, trace_ids=trace_ids, n_variants=trace_count)
    if not sublog:
        logger.warning("      task24: no traces selected — discovering from the whole log.")
        sublog, described = list(log), f"{len(log)} trace(s), whole log"
    logger.info(f"      -> Discovering from {described} (noise {noise_threshold}).")

    try:
        desired = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task24: the reference model could not be parsed: {e}")
        return
    if not desired["elements"]:
        logger.warning("      task24: no elements found in the reference BPMN — skipping.")
        return

    try:
        discovered = _discover_model(sublog, noise_threshold)
    except Exception as e:
        logger.warning(f"      task24: discovery failed: {e}")
        return

    diff = _model_diff(desired, discovered)
    logger.info(f"      -> {len(diff['desired_order'])} desired activity(ies), "
                f"{len(diff['discovered_order'])} discovered.")
    logger.info(f"      -> {_difference_summary(diff)}")

    task24_flow_chart_elaborate_bpmn(diff, output_dir, subtitle=described)
    task24_flow_chart_basic(diff, output_dir, subtitle=described)
    task24_table(diff, output_dir, subtitle=described)
