"""
tasks/task24.py – Task ID 24: Explore / Discover / Guideline violations in model.

Discovers a process model from the selected traces and puts it beside the
reference BPMN that holds the desired behaviour. Finding the differences is the
participant's work: nothing in these figures marks them.

Both idioms show the same two things — the desired model as BPMN, and the
discovered model in that idiom's own encoding. The desired side is always the
BPMN because it is the only notation here that shows concurrency, and a
guideline redrawn as a flat list of steps would claim an order its gateways do
not prescribe. What the experiment varies is how the *discovered* model is
presented.

The discovered side is read off the miner's process tree, not off a flattened
sequence: the table names, per activity, whether it always happens, whether it
is optional, what it runs in parallel with and what it is an alternative to.
That is the same branching the BPMN panel draws with gateways — one payload,
two encodings.

Public API:
    generate(log, model_path, output_dir, trace_ids=None,
             trace_count=DEFAULT_VARIANTS)
        log         – PM4Py EventLog
        model_path  – path to the reference (desired) BPMN file
        output_dir  – directory where SVGs are written
        trace_ids,
        trace_count – what the model is discovered from

Two idioms:
    task24_flow_chart_elaborate_bpmn  →  flow_chart_elaborate  (BPMN + BPMN)
    task24_table                      →  table                 (BPMN + block list)
"""

import logging
logger = logging.getLogger(__name__)

#: Canonical idiom keys (create_all_visualizations._FILE_RENAME maps the
#: flow_chart_elaborate_bpmn file stem onto flow_chart_elaborate). This used to
#: declare the file stem itself, which is not a key the Idiom collection knows.
#: The chevron is gone. A model discovered from several variants has choices
#: and concurrency — the sample's process tree carries seven XOR nodes and one
#: AND — and a chevron strip says "these steps, in this order, all of them".
#: Pressed into one it did not simplify the model, it misstated it, and a
#: participant holding it against the guideline would have found differences
#: that were artefacts of the flattening. The table can carry the branching in
#: a column; the chevron would have had to carry it in a cell, which is no
#: longer a chevron.
IDIOMS = ["flow_chart_elaborate", "table"]

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

import os
import tempfile

from shared import (
    parse_bpmn_model, compose_bpmn_panels, render_empty_state_svg,
    GREY_MED, GREY_DARK,
)

#: Default number of most-frequent variants the model is discovered from.
DEFAULT_VARIANTS = 3

#: One title over all three idioms, in the words of the task.
_TASK24_TITLE = "Where the Discovered Model Differs from the Desired Model"

_DESIRED_LABEL = "Desired model (guideline)"


#: The caption over the discovered side, in every idiom. It used to name what
#: the model was discovered from ("from 625 trace(s) of the 8 most frequent
#: variant(s)"), which is how the admin configured the task, not something a
#: participant is asked about — and it made the caption a different length in
#: every idiom. The selection is still logged for the admin.
_DISCOVERED_LABEL = "Discovered model"


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

    Returns ``(parsed BPMN, process tree)``. The tree is the same discovery in
    the form the table reads: block-structured, so every activity's choices and
    concurrency can be named without inspecting gateway topology.
    """
    import pm4py
    from pm4py.objects.log.obj import EventLog

    # _select_sublog hands back a plain list of traces; the miner wants a log.
    sub = sublog if isinstance(sublog, EventLog) else EventLog(list(sublog))
    # The tree first, the BPMN converted from it, so the two idioms describe
    # one discovery rather than two runs of the miner that could disagree.
    tree = pm4py.discover_process_tree_inductive(sub, noise_threshold=0.0)
    bpmn = pm4py.convert_to_bpmn(tree)
    handle, path = tempfile.mkstemp(suffix=".bpmn")
    os.close(handle)
    try:
        pm4py.write_bpmn(bpmn, path, auto_layout=True)
        return _relayout(_simplify(parse_bpmn_model(path))), tree
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


def _simplify(parsed) -> dict:
    """Remove the gateways the miner leaves behind that route nothing.

    Two reductions, applied until neither fires:

    * A gateway with one way in and one way out routes nothing at all, so it
      goes and its neighbours are joined.
    * A gateway whose single outgoing flow is the *only* way into another
      gateway of the same kind is that gateway: a join immediately followed by
      a split is one router drawn as two. They merge into one.

    Both come out of how a process tree nests: every optional activity becomes
    its own split/join pair, and nesting them puts the pairs back to back. The
    sample model ran "Confirm Order" into a run of diamonds before reaching
    "Ship Order", each of which a reader has to look at and rule out.

    Neither reduction changes which sequences the model allows. A split with
    two ways out and a join with two ways in are left alone, so the choices
    and the concurrency this notation exists to show survive intact.
    """
    elements = dict(parsed["elements"])
    flows = dict(parsed["sequence_flows"])
    shapes = dict(parsed["shapes"])

    while True:
        incoming, outgoing = {}, {}
        for fid, sf in flows.items():
            outgoing.setdefault(sf["source"], []).append(fid)
            incoming.setdefault(sf["target"], []).append(fid)

        def is_gateway(eid):
            return str(elements.get(eid, {}).get("kind", "")).endswith("Gateway")

        # (1) the pass-through gateway
        removable = None
        for eid in elements:
            if not is_gateway(eid):
                continue
            ins, outs = incoming.get(eid, []), outgoing.get(eid, [])
            if len(ins) != 1 or len(outs) != 1:
                continue
            # One flow that both enters and leaves, or a self-loop, is not a
            # pass-through; leave it be.
            if ins[0] == outs[0] or flows[ins[0]]["source"] == eid:
                continue
            removable = (eid, ins[0], outs[0])
            break
        if removable is not None:
            eid, flow_in, flow_out = removable
            flows[flow_in] = {**flows[flow_in], "target": flows[flow_out]["target"]}
            del flows[flow_out]
            del elements[eid]
            shapes.pop(eid, None)
            continue

        # (2) the join that runs straight into a split of the same kind
        mergeable = None
        for fid, sf in flows.items():
            src, tgt = sf["source"], sf["target"]
            if src == tgt or not (is_gateway(src) and is_gateway(tgt)):
                continue
            if elements[src]["kind"] != elements[tgt]["kind"]:
                continue
            if outgoing.get(src) != [fid] or incoming.get(tgt) != [fid]:
                continue
            mergeable = (fid, src, tgt)
            break
        if mergeable is None:
            break

        fid, keep, drop = mergeable
        for other in outgoing.get(drop, []):
            flows[other] = {**flows[other], "source": keep}
        del flows[fid]
        del elements[drop]
        shapes.pop(drop, None)

    out = dict(parsed)
    out["elements"] = elements
    out["sequence_flows"] = flows
    out["shapes"] = shapes
    out["edge_pts"] = {fid: parsed["edge_pts"].get(fid, []) for fid in flows}
    return out


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
#: Where an edge goes that does not join two neighbouring columns. A backward
#: edge drops below the diagram, a skip-ahead edge rises above it, and each
#: gets its own lane so two of them never share a line.
_BACK_EDGE_DROP = 34.0
_SKIP_LANE_GAP = 26.0
_SKIP_LANE_STEP = 14.0
#: How far into the gap beside a column a skip-ahead edge steps before it
#: climbs. Rising straight from a node's top edge would cross whatever else
#: stands in that node's own column; the gaps between columns are empty by
#: construction.
_SKIP_STUB = 14.0


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
    top = min(b["y"] for b in placed.values())

    # An edge that skips a column would otherwise be drawn as a straight run at
    # its own height, straight through whatever stands in the columns between
    # — which is what the miner's skip-this-activity branches all do. They go
    # over the top instead, one lane each, longest first so the longer spans
    # sit further out and the lanes do not cross.
    def span(sf):
        return depth.get(sf["target"], 0) - depth.get(sf["source"], 0)

    skipping = sorted((fid for fid, sf in flows.items()
                       if sf["source"] in placed and sf["target"] in placed
                       and span(sf) > 1),
                      key=lambda fid: -span(flows[fid]))
    lane_of = {fid: i for i, fid in enumerate(skipping)}

    edge_pts = {}
    for fid, sf in flows.items():
        src, tgt = placed.get(sf["source"]), placed.get(sf["target"])
        if not src or not tgt:
            continue
        sxc = src["x"] + src["width"] / 2.0
        txc = tgt["x"] + tgt["width"] / 2.0
        if fid in lane_of:
            lane = top - _SKIP_LANE_GAP - _SKIP_LANE_STEP * lane_of[fid]
            out_x = src["x"] + src["width"] + _SKIP_STUB
            in_x = tgt["x"] - _SKIP_STUB
            src_mid = src["y"] + src["height"] / 2.0
            tgt_mid = tgt["y"] + tgt["height"] / 2.0
            edge_pts[fid] = [(src["x"] + src["width"], src_mid), (out_x, src_mid),
                             (out_x, lane), (in_x, lane),
                             (in_x, tgt_mid), (tgt["x"], tgt_mid)]
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
            edge_pts[fid] = [(sxc, src["y"] + src["height"]), (sxc, drop),
                             (txc, drop), (txc, tgt["y"] + tgt["height"])]

    out = dict(parsed)
    out["shapes"] = placed
    out["edge_pts"] = edge_pts
    return out


#: How many sibling activities are named before a condition says "and 2 more".
_MAX_NAMED_SIBLINGS = 3


def _tree_leaves(node) -> list:
    """The activity labels under a process-tree node, in its own order."""
    if node.operator is None:
        return [node.label] if node.label is not None else []
    out = []
    for child in node.children:
        out += _tree_leaves(child)
    return out


def _is_tau(node) -> bool:
    return node.operator is None and node.label is None


def _sibling_names(parent, child, limit: int = _MAX_NAMED_SIBLINGS) -> str:
    """"A, B and 2 more" over the other branches of ``parent``."""
    names = []
    for other in parent.children:
        if other is child or _is_tau(other):
            continue
        names += _tree_leaves(other)
    if not names:
        return ""
    if len(names) <= limit:
        return " and ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else names[0]
    return ", ".join(names[:limit]) + f" and {len(names) - limit} more"


def _condition(parent, child) -> str:
    """What ``parent`` says about how its child ``child`` occurs."""
    from pm4py.objects.process_tree.obj import Operator

    op = parent.operator
    if op == Operator.XOR:
        real = [c for c in parent.children if not _is_tau(c)]
        if len(real) == 1:
            return "Optional"
        others = _sibling_names(parent, child)
        skippable = len(real) < len(parent.children)
        text = f"Either this or {others}" if others else "One of several"
        return f"{text} (or neither)" if skippable else text
    if op == Operator.PARALLEL:
        others = _sibling_names(parent, child)
        return f"Any order with {others}" if others else "Any order"
    if op == Operator.LOOP:
        return "Repeatable"
    if op == Operator.OR:
        others = _sibling_names(parent, child)
        return f"This and/or {others}" if others else "One or more of these"
    return ""


def _block_rows(tree) -> list:
    """[(activity, condition)] — the discovered model as the table reads it.

    A process tree is a nested sequence, so its activities do have a reading
    order; what they do not have is a single mandatory one. Each row therefore
    carries the order *and* the condition attached to it: whether the activity
    always happens, is optional, runs in any order with others, is an
    alternative to them, or repeats.

    Two conditions at most per row — the innermost operator that says
    something about this activity, and, when an outer one spans more than a
    single activity, its block letter. The tree nests six deep on the sample,
    and a row that listed every enclosing operator read "optional, optional,
    any order, optional", which is no more usable than the flat list it
    replaced.
    """
    # Letters for the blocks that hold more than one activity, in the order
    # they first appear, so rows that belong together can be seen to.
    letters, order = {}, []

    def assign(node):
        if node.operator is not None and len(_tree_leaves(node)) > 1:
            if id(node) not in letters:
                order.append(node)
                letters[id(node)] = chr(ord("A") + len(order) - 1)
        for child in node.children if node.operator is not None else []:
            assign(child)

    from pm4py.objects.process_tree.obj import Operator
    for node in ([tree] if tree.operator is not None else []):
        for child in node.children:
            assign(child)

    rows = []

    def walk(node, ancestors):
        if node.operator is None:
            if node.label is None:
                return
            # Innermost first, but "Optional" does not win over a condition
            # that says something else: almost every activity in a mined model
            # sits in some X(tau, ...) wrapper, so stopping at the first one
            # would have reported "Optional" for an activity whose real news
            # is that it runs in any order with another.
            strong, optional = "", False
            for parent, child in reversed(ancestors):
                text = _condition(parent, child)
                if text == "Optional":
                    optional = True
                elif text and not strong:
                    strong = text
            inner = strong or ("Optional" if optional else "")
            if strong and optional:
                inner = f"Optional · {strong[0].lower()}{strong[1:]}"
            block = ""
            for parent, _child in ancestors:
                if parent.operator != Operator.SEQUENCE and id(parent) in letters:
                    block = f" (block {letters[id(parent)]})"
                    break
            rows.append((node.label, (inner or "Always") + block))
            return
        for child in node.children:
            walk(child, ancestors + [(node, child)])

    walk(tree, [])
    return rows


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
            {"parsed": discovered, "subtitle": _DISCOVERED_LABEL,
             "node_style_fn": _plain_node_style},
        ],
        os.path.join(output_dir, "task24_flow_chart_elaborate_bpmn.svg"),
        title=_TASK24_TITLE,
        legend_items=[],
    )


def task24_table(desired, tree, output_dir: str):
    """The guideline as BPMN, the discovered model as its blocks below it.

    The third column is what makes this idiom able to answer the task at all.
    A model discovered from several variants branches, and a plain list of
    steps would assert one mandatory order through it; "Optional", "Any order
    with X", "Either this or Y" is the same branching the BPMN panel above
    draws with gateways.

    compose_bpmn_panels draws a table into the same canvas as the panel, so
    this idiom needs no compositing.
    """
    path = os.path.join(output_dir, "task24_table.svg")
    rows = _block_rows(tree)
    if not rows:
        render_empty_state_svg(path, _TASK24_TITLE, "No activities were discovered.")
        return

    compose_bpmn_panels(
        [{"parsed": desired, "subtitle": _DESIRED_LABEL,
          "node_style_fn": _plain_node_style}],
        path,
        title=_TASK24_TITLE,
        legend_items=[],
        table_subtitle=_DISCOVERED_LABEL,
        table_cols=["Step", "Activity", "How it occurs"],
        table_rows=[[str(i + 1), name, condition]
                    for i, (name, condition) in enumerate(rows)],
        table_stretch=True,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, model_path: str, output_dir: str, trace_ids=None,
             trace_count: int = DEFAULT_VARIANTS):
    """Generate all Task ID 24 SVGs into output_dir.

    ``trace_ids`` / ``trace_count`` choose what the model is discovered from —
    the named traces, or every trace of the ``trace_count`` most frequent
    variants. Both idioms then put the discovered model under the guideline and
    leave the comparing to the participant.
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
        discovered, tree = _discover_model(sublog)
    except Exception as e:
        logger.warning(f"      task24: discovery failed: {e}")
        return

    desired_names = sorted(set(_named_tasks(desired).values()))
    discovered_names = [name for name, _condition in _block_rows(tree)]
    logger.info(f"      -> {len(desired_names)} desired activity(ies), "
                f"{len(set(discovered_names))} discovered; "
                f"{_difference_summary(desired_names, discovered_names)}.")

    task24_flow_chart_elaborate_bpmn(desired, discovered, output_dir, described)
    task24_table(desired, tree, output_dir)
