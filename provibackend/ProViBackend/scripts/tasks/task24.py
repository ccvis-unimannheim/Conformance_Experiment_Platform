"""
tasks/task24.py – Task ID 24: Explore / Discover / Guideline violations in model.

Discovers the directly-follows graph (DFG) from the event log and compares it to the
reference BPMN to reveal where observed behaviour deviates from the desired model.

Public API:
    generate(log, model_path, output_dir)
        log        – PM4Py EventLog
        model_path – path to the reference BPMN file
        output_dir – directory where SVGs are written

Two idioms (renamed by pipeline to canonical slugs):
    task24_flow_chart_elaborate_bpmn  →  flow_chart_elaborate.svg
    task24_flow_chart_and_table       →  flow_chart_table.svg
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_elaborate_bpmn", "flow_chart_and_table"]

import os
from collections import Counter

from shared import (
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
)

# Minimum DFG edge frequency to count as real observed behaviour (raise to de-clutter)
NOISE_THRESHOLD = 1


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
# Idiom 1 – Process graph with aggregate diff coloring
# ---------------------------------------------------------------------------

def _build_diff_panel(diff: dict) -> dict:
    """Build the discovery-diff annotation (node/flow styling + summary + legend)
    shared by flow_chart_elaborate_bpmn and flow_chart_and_table.

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
            return ("#EBEBEB", "#BBBBBB", 2, "#AAAAAA")
        if eid in violation_ids:
            return ("white", "#444444", 3, "#333333")
        return ("white", "#888888", 2, "#333333")

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
        ("white",   "#888888", 2, "Conform (in model and observed)"),
        ("#EBEBEB", "#BBBBBB", 2, "In model, not observed"),
        ("white",   "#444444", 3, "Endpoint of observed-not-in-model transition"),
    ]

    return {
        "node_style_fn": _node_style,
        "faded_flow_fn": _flow_faded,
        "summary": summary,
        "legend_items": legend_items,
    }


def task24_flow_chart_elaborate_bpmn(diff: dict, output_dir: str):
    """BPMN model graph decorated with discovery-diff coloring (shared renderer)."""
    logger.info("      -> Fallback mode: observed-not-in-model edges shown via node highlighting.")

    panel = _build_diff_panel(diff)
    render_bpmn_annotated(
        diff,
        os.path.join(output_dir, "task24_flow_chart_elaborate_bpmn.svg"),
        title="Discovered vs. Desired Model — Differences",
        summary=panel["summary"],
        node_style_fn=panel["node_style_fn"],
        faded_flow_fn=panel["faded_flow_fn"],
        legend_items=panel["legend_items"],
    )


# ---------------------------------------------------------------------------
# Idiom 2 – Difference table
# ---------------------------------------------------------------------------

def task24_flow_chart_and_table(diff: dict, output_dir: str):
    """Diff graph (same annotated BPMN as flow_chart_elaborate) on top, the
    discovery-diff table — Type | From / Activity | To | Observed Frequency —
    beneath it."""
    dfg_counts            = diff["dfg_counts"]
    observed_not_in_model = diff["observed_not_in_model"]
    in_model_not_observed = diff["in_model_not_observed"]
    extra_activities      = diff["extra_activities"]
    missing_activities    = diff["missing_activities"]

    rows = []
    for (a, b) in sorted(observed_not_in_model, key=lambda e: -dfg_counts.get(e, 0)):
        rows.append(["Observed not in model", a, b, str(dfg_counts.get((a, b), 0))])
    for (a, b) in sorted(in_model_not_observed):
        rows.append(["In model, not observed", a, b, "—"])
    for act in sorted(extra_activities):
        rows.append(["Extra activity (log only)", act, "—", "—"])
    for act in sorted(missing_activities):
        rows.append(["Missing activity (model only)", act, "—", "—"])

    if not rows:
        rows = [["(No structural differences detected)", "—", "—", "—"]]

    panel = _build_diff_panel(diff)
    compose_bpmn_panels(
        [{
            "parsed": diff,
            "node_style_fn": panel["node_style_fn"],
            "faded_flow_fn": panel["faded_flow_fn"],
            "subtitle": panel["summary"],
        }],
        os.path.join(output_dir, "task24_flow_chart_and_table.svg"),
        title="Guideline Violations — Discovery Diff",
        legend_items=panel["legend_items"],
        table_rows=rows,
        table_cols=["Type", "From / Activity", "To", "Observed Frequency"],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, model_path: str, output_dir: str):
    """Generate all Task ID 24 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 24 visualizations ---")

    if not log:
        logger.warning("      task24: empty log — skipping.")
        return

    try:
        diff = _compute_diff(log, model_path, noise_threshold=NOISE_THRESHOLD)
    except Exception as e:
        logger.warning(f"      task24: computation failed: {e}")
        return

    if not diff["elements"]:
        logger.warning("      task24: no elements found in BPMN — skipping.")
        return

    task24_flow_chart_elaborate_bpmn(diff, output_dir)
    task24_flow_chart_and_table(diff, output_dir)
