"""
tasks/task24.py – Task ID 24: Explore / Discover / Guideline violations in model.

Discovers a process model from the selected traces and puts it beside the
reference BPMN that holds the desired behaviour. Finding the differences is the
participant's work: nothing in these figures marks them.

Every idiom shows the same two things — the desired model as BPMN, and the
discovered model in that idiom's own encoding. The desired side is always the
BPMN because it is the only notation here that shows concurrency, and a
guideline redrawn as a chevron strip or a list of steps would claim an order
its gateways do not prescribe. What the experiment varies is how the
*discovered* model is presented.

Public API:
    generate(log, model_path, output_dir, trace_ids=None,
             trace_count=DEFAULT_VARIANTS)
        log         – PM4Py EventLog
        model_path  – path to the reference (desired) BPMN file
        output_dir  – directory where SVGs are written
        trace_ids,
        trace_count – what the model is discovered from

Three idioms:
    task24_flow_chart_elaborate_bpmn  →  flow_chart_elaborate  (BPMN + BPMN)
    task24_flow_chart_basic           →  flow_chart_basic      (BPMN + chevron)
    task24_table                      →  table                 (BPMN + step list)
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
#:
#: There is no noise filter beside it. How much behaviour enters the discovery
#: is already this selection's job: the traces chosen are whole variants, each
#: one frequent by the very rule that picked it, so a filter that drops
#: infrequent paths has nothing left to drop. Two parameters over one decision
#: would only let an admin set them against each other.
PARAM_SPEC = [
    dict(trace_alignment.TRACE_SELECTION_MODE_PARAM),
    dict(trace_alignment.TRACE_IDS_PARAM),
    {**trace_alignment.trace_count_param(3, 1, 15),
     "label": "How many of the most frequent variants to discover from",
     "hint": "The model is discovered from every trace of these variants",
     "visible_if": {"trace_selection_mode": "auto"}},
]


def validate_params(log, params) -> list:
    """Discovery needs behaviour to generalise from; one trace discovers itself."""
    params = params or {}
    ids = trace_alignment.selected_trace_ids(params)
    if params.get("trace_selection_mode") == "manual" and len(ids) == 1:
        return ["Select at least two traces — a model discovered from one trace "
                "is that trace."]
    return trace_alignment.validate_selection(log, params, min_traces=1, max_traces=15)

import io as _io
import os
import re as _re
import base64 as _base64
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import (
    parse_bpmn_model, compose_bpmn_panels, render_empty_state_svg,
    draw_chevron_strip, chevron_figure_width,
    GREY_MED, GREY_DARK, FONT_LABEL,
)

#: Default number of most-frequent variants the model is discovered from.
DEFAULT_VARIANTS = 3

#: One title over all three idioms, in the words of the task.
_TASK24_TITLE = "Where the Discovered Model Differs from the Desired Model"

_DESIRED_LABEL = "Desired model (guideline)"


def _discovered_caption(described: str) -> str:
    """The discovered side's caption, naming what it was discovered from."""
    return (f"Discovered model (from {described})" if described
            else "Discovered model (from the selected traces)")


def _plain_node_style(eid, elem):
    """Every node the same. Nothing here marks a difference.

    The figures used to carry a three-colour vocabulary and a legend reading
    "Only in the desired model" / "Only in the discovered model". That answered
    the task's question on the participant's behalf: the work left was to find
    the coloured shapes, not to compare two models. This is an Explore task,
    and the comparison is the thing being measured.
    """
    return ("#ffffff", GREY_MED, 2, GREY_DARK)


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

def _discover_model(sublog):
    """Discover a BPMN from ``sublog`` and return it parsed like the guideline.

    pm4py's inductive miner produces a sound process tree, converts it to BPMN
    and lays it out; written to a temporary file it is an ordinary BPMN with
    diagram interchange, so ``parse_bpmn_model`` reads it into exactly the
    structure the guideline model arrives in. Both sides of the comparison are
    then the same kind of object, which is what lets one renderer draw them
    both.

    The directly-follows graph the miner builds on the way stays inside pm4py:
    it is a step towards the model, not something this platform draws.

    ``noise_threshold=0.0``: every path in the sub-log enters the model. The
    sub-log is already whole variants picked for their frequency, so there is
    no infrequent behaviour left in it to filter — see PARAM_SPEC.
    """
    import pm4py
    from pm4py.objects.log.obj import EventLog

    # _select_sublog hands back a plain list of traces; the miner wants a log.
    sub = sublog if isinstance(sublog, EventLog) else EventLog(list(sublog))
    bpmn = pm4py.discover_bpmn_inductive(sub, noise_threshold=0.0)
    handle, path = tempfile.mkstemp(suffix=".bpmn")
    os.close(handle)
    try:
        pm4py.write_bpmn(bpmn, path, auto_layout=True)
        return _relayout(parse_bpmn_model(path))
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _named_tasks(parsed) -> dict:
    """{element id: name} for the tasks that carry a name.

    The miner emits silent (tau) steps for structure. They have no name, stand
    for nothing a participant could look for in the other model, and would
    otherwise show up as empty boxes.
    """
    return {eid: e["name"] for eid, e in parsed["elements"].items()
            if e["kind"] == "task" and e.get("name")}


def _depths(parsed) -> dict:
    """{element id: longest-path distance from a start event}.

    Longest path, not shortest. With an exclusive choice the shortest path
    reaches everything after the choice through whichever branch is briefest,
    which put "Close Case" ahead of the long branch's activities on the sample
    guideline. The longest path puts a node after everything that can precede
    it. Relaxation is capped at one pass per element so a loop cannot spin.
    """
    elements = parsed["elements"]
    flows = list(parsed["sequence_flows"].values())
    depth = {eid: 0 for eid, e in elements.items() if e["kind"] == "startEvent"}
    if not depth:                      # no start event: every source is one
        targets = {sf["target"] for sf in flows}
        depth = {eid: 0 for eid in elements if eid not in targets}
    for _ in range(len(elements) + 1):
        changed = False
        for sf in flows:
            src, tgt = sf["source"], sf["target"]
            if src in depth and depth.get(tgt, -1) < depth[src] + 1:
                depth[tgt] = depth[src] + 1
                changed = True
        if not changed:
            break
    return depth


#: Spacing of the re-laid-out model, in the units the guideline's own diagram
#: uses, so the two diagrams come out at comparable scale.
_LAYER_GAP_X = 58.0
#: Gap after a column of gateways and events. A miner's model is mostly
#: gateways, each a third the width of a task, and giving every one of them a
#: task-sized gap on both sides is what made the diagram wide: the arrow
#: between two diamonds needs no more room than the arrow into a task.
_NARROW_GAP_X = 30.0
_NARROW_WIDTH = 45.0
_LAYER_GAP_Y = 34.0
_BACK_EDGE_DROP = 34.0


def _relayout(parsed) -> dict:
    """Give a parsed model a compact layered layout, replacing the one it came with.

    pm4py's auto-layout spread the sample's discovered model over 5806 x 1985
    units against the guideline's 1360 x 210 — the same kind of process, four
    times as wide and ten times as tall, with long detours between neighbouring
    nodes. Under the guideline that is not a comparison a reader can make.

    Nodes keep their own size and go into columns by longest-path depth, each
    column centred vertically. Edges become short orthogonal runs from the
    source's right edge to the target's left edge; an edge that goes backwards
    (a loop) drops below the diagram and returns, which is where a reader
    expects a loop and keeps it out of the rows.
    """
    shapes, flows = parsed["shapes"], parsed["sequence_flows"]
    if not shapes:
        return parsed
    depth = _depths(parsed)

    columns = {}
    for eid in shapes:
        columns.setdefault(depth.get(eid, 0), []).append(eid)
    for ids in columns.values():
        # Keep the miner's own vertical ordering inside a column, so branches
        # it drew together stay together.
        ids.sort(key=lambda e: (shapes[e]["y"], shapes[e]["x"]))

    column_x, cursor = {}, 0.0
    for d in sorted(columns):
        column_x[d] = cursor
        col_w = max(shapes[e]["width"] for e in columns[d])
        cursor += col_w + (_NARROW_GAP_X if col_w <= _NARROW_WIDTH
                           else _LAYER_GAP_X)

    placed = {}
    for d, ids in columns.items():
        col_w = max(shapes[e]["width"] for e in ids)
        total_h = (sum(shapes[e]["height"] for e in ids)
                   + _LAYER_GAP_Y * (len(ids) - 1))
        y = -total_h / 2.0
        for eid in ids:
            box = shapes[eid]
            placed[eid] = {"x": column_x[d] + (col_w - box["width"]) / 2.0,
                           "y": y, "width": box["width"], "height": box["height"]}
            y += box["height"] + _LAYER_GAP_Y

    bottom = max(b["y"] + b["height"] for b in placed.values())
    edge_pts = {}
    for fid, sf in flows.items():
        src, tgt = placed.get(sf["source"]), placed.get(sf["target"])
        if not src or not tgt:
            continue
        sx, sy = src["x"] + src["width"], src["y"] + src["height"] / 2.0
        tx, ty = tgt["x"], tgt["y"] + tgt["height"] / 2.0
        if tx >= sx:
            if abs(sy - ty) < 1.0:
                edge_pts[fid] = [(sx, sy), (tx, ty)]
            else:
                mid = (sx + tx) / 2.0
                edge_pts[fid] = [(sx, sy), (mid, sy), (mid, ty), (tx, ty)]
        else:
            drop = bottom + _BACK_EDGE_DROP
            sxc = src["x"] + src["width"] / 2.0
            txc = tgt["x"] + tgt["width"] / 2.0
            edge_pts[fid] = [(sxc, src["y"] + src["height"]), (sxc, drop),
                             (txc, drop), (txc, tgt["y"] + tgt["height"])]

    out = dict(parsed)
    out["shapes"] = placed
    out["edge_pts"] = edge_pts
    return out


def _linearise(parsed) -> list:
    """The model's named activities in reading order.

    Sorted by longest-path depth, ties broken by the layout's y then x; both
    the guideline's own diagram and the re-laid-out discovered model run left
    to right.

    A graph pressed into a line loses concurrency and loops: two models that
    differ only in whether A and B are parallel or sequential produce the same
    list. That is exactly why the desired side of every idiom stays a BPMN.
    """
    depth = _depths(parsed)
    shapes = parsed["shapes"]

    def sort_key(item):
        eid, _name = item
        box = shapes.get(eid) or {}
        return (depth.get(eid, len(shapes)), box.get("x", 0.0), box.get("y", 0.0))

    return [name for _eid, name in sorted(_named_tasks(parsed).items(), key=sort_key)]


def _difference_summary(desired_order, discovered_order) -> str:
    """One line for the pipeline log. None of this reaches a participant."""
    only_desired = [a for a in desired_order if a not in set(discovered_order)]
    only_discovered = [a for a in discovered_order if a not in set(desired_order)]
    if not (only_desired or only_discovered):
        return "both models hold the same activities"
    parts = []
    if only_desired:
        parts.append(f"{len(only_desired)} only in the desired model "
                     f"({', '.join(only_desired)})")
    if only_discovered:
        parts.append(f"{len(only_discovered)} only in the discovered model "
                     f"({', '.join(only_discovered)})")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def _svg_dims(svg: str):
    """(width, height) from an SVG's own attributes, or (None, None)."""
    match = _re.search(r'<svg[^>]*\bwidth="([\d.]+)[^"]*"[^>]*\bheight="([\d.]+)', svg)
    return (float(match.group(1)), float(match.group(2))) if match else (None, None)


def _desired_panel_svg(desired) -> str:
    """The guideline BPMN, titled, as an SVG string."""
    handle, path = tempfile.mkstemp(suffix=".svg")
    os.close(handle)
    try:
        compose_bpmn_panels(
            [{"parsed": desired, "subtitle": _DESIRED_LABEL,
              "node_style_fn": _plain_node_style}],
            path, title=_TASK24_TITLE, legend_items=[],
            legend_below_panels=False,
        )
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _figure_to_svg(fig) -> str:
    buf = _io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read().decode("utf-8")


def _stack_svgs(top: str, bottom: str, out_path: str):
    """Write one SVG with ``bottom`` scaled to ``top``'s width and placed below.

    Both halves go in as embedded images rather than merged markup: each came
    from a different renderer with its own coordinate system, and the only
    thing that has to line up is the width.
    """
    tw, th = _svg_dims(top)
    bw, bh = _svg_dims(bottom)
    if not tw or not bw:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(top)
        return
    bh_scaled = bh * (tw / bw)
    total_h = th + bh_scaled
    b64_top = _base64.b64encode(top.encode()).decode()
    b64_bottom = _base64.b64encode(bottom.encode()).decode()
    composite = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        f'     width="{tw:.1f}" height="{total_h:.1f}" viewBox="0 0 {tw:.1f} {total_h:.1f}">',
        '  <rect width="100%" height="100%" fill="white"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_top}"',
        f'         x="0" y="0" width="{tw:.1f}" height="{th:.1f}"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_bottom}"',
        f'         x="0" y="{th:.1f}" width="{tw:.1f}" height="{bh_scaled:.1f}"/>',
        '</svg>',
    ])
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(composite)


# ---------------------------------------------------------------------------
# Idioms
# ---------------------------------------------------------------------------

def task24_flow_chart_elaborate_bpmn(desired, discovered, output_dir: str,
                                     described: str = ""):
    """Both models as BPMN, one above the other, in one neutral style.

    It used to be the guideline alone, annotated with what a directly-follows
    graph had found: one model and a legend answering a question about two.
    """
    compose_bpmn_panels(
        [
            {"parsed": desired, "subtitle": _DESIRED_LABEL,
             "node_style_fn": _plain_node_style},
            {"parsed": discovered, "subtitle": _discovered_caption(described),
             "node_style_fn": _plain_node_style},
        ],
        os.path.join(output_dir, "task24_flow_chart_elaborate_bpmn.svg"),
        title=_TASK24_TITLE,
        legend_items=[],
    )


def task24_flow_chart_basic(desired, discovered, output_dir: str,
                            described: str = ""):
    """The guideline as BPMN, the discovered model as a chevron strip below it."""
    path = os.path.join(output_dir, "task24_flow_chart_basic.svg")
    activities = _linearise(discovered)
    if not activities:
        render_empty_state_svg(path, _TASK24_TITLE, "No activities were discovered.")
        return

    nodes = [{"label": name, "color": "#ffffff"} for name in activities]
    fig, ax = plt.subplots(figsize=(chevron_figure_width(nodes), 2.1))
    draw_chevron_strip(ax, nodes, fontsize=9.5)
    ax.set_title(_discovered_caption(described), fontsize=FONT_LABEL,
                 loc="left", pad=8)
    fig.subplots_adjust(left=0.02, right=0.99, top=0.74, bottom=0.08)
    _stack_svgs(_desired_panel_svg(desired), _figure_to_svg(fig), path)


def task24_table(desired, discovered, output_dir: str, described: str = ""):
    """The guideline as BPMN, the discovered model as its list of steps below it.

    compose_bpmn_panels draws a table into the same canvas as the panel, so
    this idiom needs no compositing.
    """
    path = os.path.join(output_dir, "task24_table.svg")
    activities = _linearise(discovered)
    if not activities:
        render_empty_state_svg(path, _TASK24_TITLE, "No activities were discovered.")
        return

    compose_bpmn_panels(
        [{"parsed": desired, "subtitle": _DESIRED_LABEL,
          "node_style_fn": _plain_node_style}],
        path,
        title=_TASK24_TITLE,
        legend_items=[],
        table_cols=["Step", _discovered_caption(described)],
        table_rows=[[str(i + 1), name] for i, name in enumerate(activities)],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, model_path: str, output_dir: str, trace_ids=None,
             trace_count: int = DEFAULT_VARIANTS):
    """Generate all Task ID 24 SVGs into output_dir.

    ``trace_ids`` / ``trace_count`` choose what the model is discovered from —
    the named traces, or every trace of the ``trace_count`` most frequent
    variants. Each idiom then puts the discovered model under the guideline and
    leaves the comparing to the participant.
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
    logger.info(f"      -> Discovering from {described}.")

    try:
        desired = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task24: the reference model could not be parsed: {e}")
        return
    if not desired["elements"]:
        logger.warning("      task24: no elements found in the reference BPMN — skipping.")
        return

    try:
        discovered = _discover_model(sublog)
    except Exception as e:
        logger.warning(f"      task24: discovery failed: {e}")
        return

    desired_order, discovered_order = _linearise(desired), _linearise(discovered)
    logger.info(f"      -> {len(desired_order)} desired activity(ies), "
                f"{len(discovered_order)} discovered; "
                f"{_difference_summary(desired_order, discovered_order)}.")

    task24_flow_chart_elaborate_bpmn(desired, discovered, output_dir, described)
    task24_flow_chart_basic(desired, discovered, output_dir, described)
    task24_table(desired, discovered, output_dir, described)
