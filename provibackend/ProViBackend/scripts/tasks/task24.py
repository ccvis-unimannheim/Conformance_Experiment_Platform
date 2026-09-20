"""
tasks/task24.py – Task ID 24: Explore / Discover / Guideline violations in model.

Discovers the directly-follows graph (DFG) from the event log and compares it to the
reference BPMN to reveal where observed behaviour deviates from the desired model.

Public API:
    generate(log, model_path, output_dir)
        log        – PM4Py EventLog
        model_path – path to the reference BPMN file
        output_dir – directory where SVGs are written

One idiom (renamed by pipeline to a canonical slug):
    task24_flow_chart_elaborate_bpmn  →  flow_chart_elaborate.svg
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_elaborate_bpmn"]

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
from collections import Counter

from shared import (
    parse_bpmn_model, render_bpmn_annotated,
    GREY_DARK, GREY_MED, GREY_LIGHTER,
)

# Minimum DFG edge frequency to count as real observed behaviour (raise to de-clutter)
NOISE_THRESHOLD = 1

#: Default number of most-frequent variants the model is discovered from.
DEFAULT_VARIANTS = 3


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
# Data helpers
# ---------------------------------------------------------------------------

def _discover_dfg(log, noise_threshold: int) -> dict:
    """Return {(a, b): count} directly-follows pairs with count >= noise_threshold."""
    dfg: Counter = Counter()
    for trace in log:
        acts = [str(e.get("concept:name", "")) for e in trace if e.get("concept:name")]
        for a, b in zip(acts, acts[1:]):
            dfg[(a, b)] += 1
    return {pair: cnt for pair, cnt in dfg.items() if cnt >= noise_threshold}


def _model_task_edges(elements: dict, sequence_flows: dict) -> set:
    """Set of (src_name, tgt_name) for task-to-task reachability; gateways collapsed."""
    adj = {}
    for sf in sequence_flows.values():
        adj.setdefault(sf["source"], []).append(sf["target"])

    task_ids = {eid for eid, e in elements.items() if e["kind"] == "task" and e.get("name")}
    model_edges = set()
    for src_id in task_ids:
        src_name = elements[src_id]["name"]
        queue, visited = list(adj.get(src_id, [])), set()
        while queue:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            elem = elements.get(cur)
            if elem and elem["kind"] == "task" and elem.get("name"):
                model_edges.add((src_name, elem["name"]))
            else:
                queue.extend(adj.get(cur, []))
    return model_edges


def _compute_diff(log, model_path: str, noise_threshold: int = NOISE_THRESHOLD,
                  log_summary: bool = True) -> dict:
    """Diff observed DFG against reference BPMN model edges.

    log_summary: when False, the DFG/diff INFO lines are suppressed. Reusers
    (e.g. task25) set this so the summary is not logged again under their own
    section.
    """
    dfg_counts     = _discover_dfg(log, noise_threshold)
    observed_edges = set(dfg_counts.keys())
    observed_acts  = {a for pair in observed_edges for a in pair}

    parsed = parse_bpmn_model(model_path)
    elements      = parsed["elements"];      sequence_flows = parsed["sequence_flows"]
    shapes        = parsed["shapes"];        edge_pts       = parsed["edge_pts"]
    name_to_ids   = parsed["name_to_ids"]
    model_task_names = {e["name"] for e in elements.values() if e["kind"] == "task" and e["name"]}
    model_edges      = _model_task_edges(elements, sequence_flows)

    conform_edges         = observed_edges & model_edges
    in_model_not_observed = model_edges    - observed_edges
    observed_not_in_model = observed_edges - model_edges
    extra_activities      = observed_acts  - model_task_names
    missing_activities    = model_task_names - observed_acts

    if log_summary:
        logger.info(f"      -> DFG edges (≥{noise_threshold}): {len(observed_edges)}"
                    f"  |  Model edges: {len(model_edges)}")
        logger.info(f"      -> Conform: {len(conform_edges)}"
                    f"  |  In-model-not-observed: {len(in_model_not_observed)}"
                    f"  |  Observed-not-in-model: {len(observed_not_in_model)}")

    return {
        "model_task_names": model_task_names, "observed_activities": observed_acts,
        "model_edges": model_edges, "observed_edges": observed_edges,
        "conform_edges": conform_edges,
        "in_model_not_observed": in_model_not_observed,
        "observed_not_in_model": observed_not_in_model,
        "extra_activities": extra_activities,
        "missing_activities": missing_activities,
        "dfg_counts": dfg_counts,
        "elements": elements, "sequence_flows": sequence_flows,
        "shapes": shapes, "edge_pts": edge_pts, "name_to_ids": name_to_ids,
    }


# ---------------------------------------------------------------------------
# Idiom – Process graph with aggregate diff coloring
# ---------------------------------------------------------------------------

def _build_diff_panel(diff: dict) -> dict:
    """Build the discovery-diff annotation (node/flow styling + summary + legend)
    for flow_chart_elaborate_bpmn.

      missing task nodes         → faded fill + light stroke
      violation endpoint nodes   → dark border (endpoint of observed-not-in-model edge)
      flows from/to missing task → faded dashed line
    """
    elements    = diff["elements"];  seq_flows = diff["sequence_flows"]
    name_to_ids = diff["name_to_ids"]
    missing_activities    = diff["missing_activities"]
    observed_not_in_model = diff["observed_not_in_model"]

    missing_ids   = {eid for n in missing_activities for eid in name_to_ids.get(n, [])}
    violation_eps = {a for (a, b) in observed_not_in_model} | {b for (a, b) in observed_not_in_model}
    violation_ids = {eid for n in violation_eps for eid in name_to_ids.get(n, [])}

    def _node_style(eid, elem):
        if eid in missing_ids:
            return (GREY_LIGHTER, GREY_MED, 2, GREY_DARK)
        if eid in violation_ids:
            return ("white", GREY_DARK, 3, GREY_DARK)
        return ("white", GREY_MED, 2, GREY_DARK)

    def _flow_faded(flow_id):
        sf = seq_flows.get(flow_id)
        if not sf:
            return False
        for role in ("source", "target"):
            e = elements.get(sf[role], {})
            if e.get("kind") == "task" and e.get("name", "") in missing_activities:
                return True
        return False

    has_viol = bool(observed_not_in_model)
    has_miss = bool(missing_activities)
    has_imno = bool(diff["in_model_not_observed"])
    if not (has_viol or has_miss or has_imno):
        summary = "No structural differences detected between log behaviour and model."
    else:
        parts = []
        if has_viol: parts.append(f"{len(observed_not_in_model)} observed-not-in-model transition(s)")
        if has_miss: parts.append(f"{len(missing_activities)} task(s) never observed")
        if has_imno: parts.append(f"{len(diff['in_model_not_observed'])} model edge(s) not observed")
        summary = "; ".join(parts)

    legend_items = [
        ("white",    GREY_MED,     2, "Conform (in model and observed)"),
        (GREY_LIGHTER, GREY_MED,   2, "In model, not observed"),
        ("white",    GREY_DARK,    3, "Endpoint of observed-not-in-model transition"),
    ]

    return {
        "node_style_fn": _node_style,
        "faded_flow_fn": _flow_faded,
        "summary": summary,
        "legend_items": legend_items,
    }


def task24_flow_chart_elaborate_bpmn(diff: dict, output_dir: str, subtitle: str = ""):
    """The guideline BPMN, annotated with what the discovery found.

    One visual vocabulary only: the differences are painted onto the model the
    analyst already knows. The discovered behaviour is what produces the
    annotation — faded nodes, dark violation endpoints, the summary line — it is
    not drawn as a second, differently-shaped graph beside it.
    """
    path  = os.path.join(output_dir, "task24_flow_chart_elaborate_bpmn.svg")
    panel = _build_diff_panel(diff)
    render_bpmn_annotated(
        diff, path,
        title="Discovered vs. Desired Model — Differences",
        summary=" · ".join(x for x in (subtitle, panel["summary"]) if x),
        node_style_fn=panel["node_style_fn"],
        faded_flow_fn=panel["faded_flow_fn"],
        legend_items=panel["legend_items"],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, model_path: str, output_dir: str, trace_ids=None,
             trace_count: int = DEFAULT_VARIANTS):
    """Generate all Task ID 24 SVGs into output_dir.

    ``trace_ids`` / ``trace_count`` choose what the model is discovered from —
    the named traces, or every trace of the ``trace_count`` most frequent
    variants. The idiom then annotates the guideline with what was discovered.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 24 visualizations ---")

    if not log:
        logger.warning("      task24: empty log — skipping.")
        return

    sublog, described = _select_sublog(log, trace_ids=trace_ids, n_variants=trace_count)
    if not sublog:
        logger.warning("      task24: no traces selected — discovering from the whole log.")
        sublog, described = list(log), f"{len(log)} trace(s), whole log"
    logger.info(f"      -> Discovering from {described}.")

    try:
        diff = _compute_diff(sublog, model_path, noise_threshold=NOISE_THRESHOLD)
    except Exception as e:
        logger.warning(f"      task24: computation failed: {e}")
        return

    if not diff["elements"]:
        logger.warning("      task24: no elements found in BPMN — skipping.")
        return

    task24_flow_chart_elaborate_bpmn(diff, output_dir, subtitle=described)
