"""
tasks/task25.py – Task ID 25: Explore / Discover / Process conformance.

The analyst discovers the overall degree of conformance themself, from the
process model rather than from a computed number. Three principles:

  * **Discovery, not description.** No aggregated conformance value is handed
    over — no fitness figure, no mean line, no summary row. The task's whole
    difference from task06 (which states the number) is that here it has to be
    worked out.
  * **On the model.** The guideline model is the visual, annotated per activity
    with how its recorded behaviour replayed: how often the activity was
    executed where the model prescribes it, and how often it deviated (executed
    where the model does not prescribe it, or prescribed and not executed).
    Conformance is read off the process the analyst already knows.
  * **Recoverable, not binned.** The counts are exact and per activity, never
    bands or ranges, so the overall degree can actually be derived from them.
    Colour only ranks the activities; the numbers carry the information.

The idiom draws the per-activity counts on the model itself; the node labels
carry the whole payload.

**What the figure supports is not task06's number.** Pooling the labels gives
the share of replayed steps that were synchronous — an event-weighted rate. The
fitness task06 states is the mean of the per-trace alignment fitness, which
weights every trace equally and is itself a cost ratio rather than a step count.
On the order-to-cash log the two are 93.7% and 95.3%. Both are defensible
readings of "overall degree of conformance", but an answer key for this task has
to come from what this figure supports, not from pm4py's fitness — no
per-activity decomposition reproduces that number exactly.

Reuses the centrally computed alignments; nothing is re-run here.

Public API:
    generate(log, alignments, output_dir, model_path=None)
        log        – PM4Py EventLog (unused; kept for the calling convention)
        alignments – raw alignment results from io_helpers.run_alignments
        output_dir – directory where SVGs are written
        model_path – the guideline BPMN; without it the idiom renders its
                     empty state, since the model is the visual
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_elaborate"]


PARAM_SPEC = []


import os

from matplotlib.colors import to_hex

from shared import (
    alignment_pairs_to_rows, parse_bpmn_model, compose_bpmn_panels,
    render_empty_state_svg, contrasting_text_color, CIVIDIS_R,
)

#: Alignment labels naming no real activity (tau / hidden transitions).
_MISSING = {"-", "None", "(skip)", ">>", ""}

_TITLE = "Recorded Behaviour on the Process Model"
#: Says how to read the figure without saying what the answer is.
_SUMMARY = ("Each activity: times executed as the model prescribes / times it was "
            "involved at all. Darker = a larger share deviated.")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _task25_activity_replay(alignments):
    """Per activity ``{"as_prescribed": n, "deviating": n}`` over the whole log.

    A synchronous move is behaviour the model prescribes and the log records. A
    model move (prescribed, not executed) and a log move (executed, not
    prescribed) are both deviations of that activity.
    """
    stats: dict = {}

    def bump(activity, key):
        activity = str(activity)
        if activity in _MISSING:
            return
        stats.setdefault(activity, {"as_prescribed": 0, "deviating": 0})[key] += 1

    for result in alignments or []:
        for row in alignment_pairs_to_rows(result.get("alignment", [])):
            move = row["moveType"]
            log_label, model_label = str(row["log_move"]), str(row["model_move"])
            if move == "Synchronous Move":
                bump(log_label if log_label not in _MISSING else model_label,
                     "as_prescribed")
            elif move == "Model Move":
                bump(model_label, "deviating")
            elif move == "Log Move":
                bump(log_label, "deviating")
    return stats


def _involved(entry) -> int:
    return entry["as_prescribed"] + entry["deviating"]


def _annotated_model(model_path, stats):
    """``(parsed, by_element_id)``: the model with each task's counts appended to
    its label, and the stats reachable by element id.

    The shared renderer draws a node's ``name``, so the counts ride along with it
    — there is no separate annotation channel, and putting them in the label
    keeps them inside the node they describe. The style function is then keyed on
    the element id rather than parsing the activity name back out of the label it
    was just appended to.
    """
    parsed = parse_bpmn_model(model_path, node_scale=1.6)
    elements = parsed.get("elements", {})
    items = elements.items() if isinstance(elements, dict) else enumerate(elements)
    by_element_id = {}
    for eid, elem in items:
        if elem.get("kind") != "task":
            continue
        entry = stats.get(elem.get("name", ""))
        if not entry or not _involved(entry):
            continue
        by_element_id[eid] = entry
        elem["name"] = f"{elem['name']} {entry['as_prescribed']}/{_involved(entry)}"
    return parsed, by_element_id


def _node_style_fn(by_element_id):
    """Shade each task by the share of its occurrences that deviated."""
    def _style(eid, elem):
        entry = by_element_id.get(eid)
        if elem.get("kind") == "task" and entry:
            deviating = entry["deviating"] / _involved(entry)
            fill = to_hex(CIVIDIS_R(0.15 + 0.6 * deviating))
            return (fill, "#444444", 2, contrasting_text_color(fill))
        return ("white", "#888888", 2, "#333333")
    return _style


_LEGEND = [
    (to_hex(CIVIDIS_R(0.15)), "#444444", 2, "Mostly as prescribed"),
    (to_hex(CIVIDIS_R(0.45)), "#444444", 2, "Partly deviating"),
    (to_hex(CIVIDIS_R(0.75)), "#444444", 2, "Mostly deviating"),
    ("white", "#888888", 2, "Never recorded"),
]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def _draw(stats, model_path, output_dir, filename):
    path = os.path.join(output_dir, filename)
    if not model_path:
        render_empty_state_svg(path, _TITLE, "No process model provided.")
        return
    if not stats:
        render_empty_state_svg(path, _TITLE, "No alignment data available.")
        return
    try:
        parsed, by_element_id = _annotated_model(model_path, stats)
    except Exception as exc:
        logger.warning(f"      task25: BPMN parse failed: {exc}")
        render_empty_state_svg(path, _TITLE, "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, _TITLE, "No BPMN geometry to render.")
        return

    compose_bpmn_panels(
        [{"parsed": parsed, "node_style_fn": _node_style_fn(by_element_id),
          "subtitle": _SUMMARY}],
        path, title=_TITLE, legend_items=_LEGEND, node_font_size=18,
    )


def task25_flow_chart_elaborate(stats, model_path, output_dir: str):
    """The guideline model, each activity labelled with its replay counts and
    shaded by the share that deviated. The overall degree of conformance is
    derivable from the labels; it is nowhere stated."""
    _draw(stats, model_path, output_dir, "task25_flow_chart_elaborate.svg")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str, model_path: str = None):
    """Generate all Task 25 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 25 visualizations ---")

    stats = _task25_activity_replay(alignments)
    if not stats:
        logger.warning("      Skipped Task 25: no alignment data.")
    else:
        involved = sum(_involved(e) for e in stats.values())
        logger.info(f"      -> {len(stats)} activities, {involved} replayed steps.")

    task25_flow_chart_elaborate(stats, model_path, output_dir)
