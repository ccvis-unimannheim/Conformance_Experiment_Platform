"""
Trace-alignment class: which traces a task shows, and from which perspective.

Scope: **task04 (trace level), task09, task14, task27, task28, task34** — the
tasks whose figures are the alignment of individual traces rather than an
aggregate over the log. The companion to ``violation_profile`` (how violations
are grouped) and ``trace_features`` (how the log is split).

Seven tasks were each picking their traces their own way, with the rule buried
in code: task04 took the two traces with the largest fitness gap, task28 the
first non-conformant one, task34 the worst-fitness one. Those rules are good
defaults but they were not choices anyone could make — so they live here as one
named ``trace_pick_rule`` vocabulary, and a task exposes the subset that means
something for it.

Two things are deliberately *not* here:

* **The renderers.** task04's and task34's figures are frozen experiment
  stimuli (see docs/TRACE_ALIGNMENT_CLASS.md), so their drawing code stays
  where it is and is called, never re-derived.
* **A conformant-fitness cut.** Only task27 needs one — conformant vs
  non-conformant *is* its question — and it declares
  ``trace_response.CONFORMANT_THRESHOLD_PARAM`` itself. Everywhere else a
  violation is a non-synchronous move, which needs no threshold.

Participant-facing wording: every selection parameter carries
``hide_hint: True``. Which traces are shown is visible in the figure itself, so
repeating it in the question wording only tells the participant where to look.
The perspective and the conformant values are the opposite — they *are* the
question — and stay visible.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

#: How the traces are picked when the admin names none. Each entry is the rule
#: one task already applied in code; the label is what /specify shows.
PICK_RULES: dict[str, str] = {
    "violation_gap":          "Traces spread across the violation counts (most- and least-violating first)",
    "worst_fitness":          "The worst-fitness trace(s)",
    "first_nonconformant":    "The first trace that violates the guideline",
    "conformant_vs_non":      "Conformant and non-conformant traces in equal number",
    "most_frequent_variants": "The most frequent trace variants",
}

PERSPECTIVES = ("control-flow", "data", "resource")

MANUAL, AUTO = "manual", "auto"


# --------------------------------------------------------------------------
# PARAM_SPEC entries — declared here so six tasks cannot drift apart
# --------------------------------------------------------------------------

#: Which perspective a violation is judged on. Only task09 and task28 ask this:
#: their wording ("control-flow relations, but also resource and data
#: constraints") is the only one that admits more than the control flow.
PERSPECTIVE_PARAM = {
    "key": "perspective",
    "slot": "perspective",
    "label": "Perspective the traces are judged on",
    "hint": "Which kind of guideline the shown traces are checked against",
    "widget": "select-one",
    "options": [
        {"value": "control-flow", "label": "Control flow — the order of activities"},
        {"value": "data",         "label": "Data — a case attribute's value"},
        {"value": "resource",     "label": "Resource — who executed the activity"},
    ],
    "default": "control-flow",
    "required": False,
}

TRACE_SELECTION_MODE_PARAM = {
    "key": "trace_selection_mode",
    "slot": "trace_selection",
    "label": "How the shown traces are chosen",
    "hide_hint": True,
    "widget": "select-one",
    "options": [
        {"value": "auto",   "label": "Automatically, by a rule"},
        {"value": "manual", "label": "I pick them myself"},
    ],
    "default": "auto",
    "required": False,
}

TRACE_IDS_PARAM = {
    "key": "trace_ids",
    "label": "Traces to show",
    "hide_hint": True,
    "widget": "select-many",
    "source": "log.trace_ids",
    # Admin convenience: a checkbox that auto-selects one trace from each of the
    # first N distinct variants. Handled in the specify-page select-many UI.
    "variant_autoselect": True,
    "autoselect_count": 2,
    "default": [],
    "required": False,
    "visible_if": {"trace_selection_mode": "manual"},
}

#: There is no "trace or variant" parameter. Every rule below already keeps one
#: representative per distinct activity sequence — two identical chevron strips
#: side by side compare nothing — so picking "variants" instead of "traces"
#: changed no figure, and "the most frequent variants" is a rule of its own.

#: What "violates the guideline" means in the control-flow perspective. The data
#: and resource perspectives are defined by their conformant values; the control
#: flow had no such definition, so every rule counted *any* deviation and a task
#: asking about one specific violation still ranked traces by their unrelated
#: ones. Empty keeps that behaviour: any deviation counts.
#: It decides *which traces are picked*, and nothing else — the figures colour
#: by move type whatever pattern is named — so a task that has the traces named
#: for it has no use for one. Every task therefore adds
#: ``trace_selection_mode: auto`` to the condition below.
VIOLATION_PATTERN_PARAM = {
    "key": "violation_pattern",
    "slot": "guideline",
    "label": "Violation that defines the guideline (empty = any deviation)",
    "hint": "The traces shown are the ones that violate this",
    "widget": "select-one",
    "source": "log.violations",
    "default": "",
    "required": False,
    "optional_hint": "(optional — leave empty to count any deviation as a violation)",
    "visible_if": {"trace_selection_mode": "auto"},
}

# --- data / resource branch ------------------------------------------------

#: The attribute under scrutiny. Its *values* are picked separately (below)
#: rather than being narrowed to this attribute's own: /specify bakes each
#: param's options in once per dataset and has no way to re-fetch them when
#: another param changes, so a dependent picker would render empty.
DATA_ATTRIBUTE_PARAM = {
    "key": "data_attribute",
    "label": "Data attribute the traces are checked on",
    "widget": "select-one",
    "source": "log.data_attributes",
    "default": "",
    "required": False,
    "visible_if": {"perspective": "data"},
}

CONFORMANT_VALUES_PARAM = {
    "key": "conformant_values",
    "label": "Values that count as conformant (any other value is a violation)",
    "widget": "select-many",
    "source": "log.attribute_values",
    "default": [],
    "required": False,
    "visible_if": {"perspective": "data"},
}

CONFORMANT_RESOURCES_PARAM = {
    "key": "conformant_resources",
    "label": "Resources allowed to execute the activity (any other is a violation)",
    "widget": "select-many",
    "source": "log.resource_values",
    "default": [],
    "required": False,
    "visible_if": {"perspective": "resource"},
}

SCOPED_ACTIVITY_PARAM = {
    "key": "scoped_activity",
    "label": "Activity the resource rule applies to (empty = every activity)",
    "widget": "activity-picker",
    "source": "log.activities",
    "default": "",
    "required": False,
    "optional_hint": "(optional — leave empty to check every activity in the trace)",
    "visible_if": {"perspective": "resource"},
}

PERSPECTIVE_PARAMS = [
    PERSPECTIVE_PARAM,
    DATA_ATTRIBUTE_PARAM,
    CONFORMANT_VALUES_PARAM,
    CONFORMANT_RESOURCES_PARAM,
    SCOPED_ACTIVITY_PARAM,
]


def trace_pick_rule_param(rules: list, default: str) -> dict:
    """The auto-pick rule, offering only the rules this task can act on."""
    unknown = [r for r in rules if r not in PICK_RULES]
    if unknown:
        raise ValueError(f"Unknown trace pick rule(s): {unknown}")
    return {
        "key": "trace_pick_rule",
        "label": "Rule for choosing the traces",
        "hide_hint": True,
        "widget": "select-one",
        "options": [{"value": r, "label": PICK_RULES[r]} for r in rules],
        "default": default,
        "required": False,
        "visible_if": {"trace_selection_mode": "auto"},
    }


def trace_count_param(default: int, minimum: int = 1, maximum: int = 4) -> dict:
    """How many traces the rule picks.

    The maximum is a legibility cap, not a technical one: each trace is a
    chevron strip and a BPMN panel stacked in one figure, and past four the
    panels are too short to read.
    """
    return {
        "key": "trace_count",
        "label": "How many traces to show",
        "hide_hint": True,
        "widget": "number",
        "min": minimum,
        "max": maximum,
        "step": 1,
        "default": default,
        "required": False,
        "visible_if": {"trace_selection_mode": "auto"},
    }


def selection_params(rules: list, default_rule: str, count_default: int,
                     count_min: int = 1, count_max: int = 4,
                     only_when: Optional[dict] = None) -> list:
    """The full trace-selection block for one task, in display order.

    ``only_when`` is merged into every entry's ``visible_if`` — task04 shows the
    whole block only at trace level. /specify requires *all* of an entry's
    conditions to hold, so merging rather than replacing keeps the mode-driven
    conditions intact.
    """
    params = [
        dict(TRACE_SELECTION_MODE_PARAM),
        dict(TRACE_IDS_PARAM),
        trace_pick_rule_param(rules, default_rule),
    ]
    # A task fixed at one trace (task14 annotates "a given trace") has nothing
    # to count, and offering a control whose only legal value is 1 reads as a
    # choice that isn't there.
    if count_max > 1:
        params.append(trace_count_param(count_default, count_min, count_max))
    if only_when:
        for entry in params:
            entry["visible_if"] = {**entry.get("visible_if", {}), **only_when}
    return params


# --------------------------------------------------------------------------
# Reading the parameters back
# --------------------------------------------------------------------------

def selected_trace_ids(params: dict) -> list:
    """The admin's explicit trace ids, or [] when the rule decides instead.

    Only an explicit ``auto`` discards a saved list. Experiments specified
    before this class existed saved ``trace_ids`` with no mode alongside it —
    naming the traces *was* the only selection there was — so an absent mode
    honours the list rather than silently swapping their stimuli for whatever
    the default rule picks.

    Manual mode with an empty list is not an error either: the admin opened the
    picker and chose nothing, which falls back to the rule rather than rendering
    an empty figure.
    """
    params = params or {}
    if params.get("trace_selection_mode") == AUTO:
        return []
    return [str(t) for t in (params.get("trace_ids") or [])]


def pick_rule(params: dict, default: str) -> str:
    return (params or {}).get("trace_pick_rule") or default


def trace_count(params: dict, default: int) -> int:
    raw = (params or {}).get("trace_count")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


def perspective(params: dict) -> str:
    value = (params or {}).get("perspective") or "control-flow"
    return value if value in PERSPECTIVES else "control-flow"


# --------------------------------------------------------------------------
# The record the class's renderers read
# --------------------------------------------------------------------------

def trace_records(log, alignments, indices, fitness_df=None) -> list:
    """``[{label, case_id, fitness, rows, violations}]`` for the given traces.

    The shape task04's chevron / BPMN / move-table renderers take, built here so
    every task in the class hands them the same thing. ``label`` is the running
    "Trace 1".."Trace N" the participant sees — the raw case id is noise to hunt
    for in a figure, and the admin has the mapping in the picker.
    """
    from shared import alignment_pairs_to_rows  # heavy (matplotlib) — import late

    records = []
    for position, i in enumerate(indices):
        if i >= len(alignments) or i >= len(log):
            continue
        rows = alignment_pairs_to_rows(alignments[i].get("alignment", []))
        if fitness_df is not None and i < len(fitness_df):
            fitness = float(fitness_df.iloc[i]["fitness"])
        else:
            fitness = float(alignments[i].get("fitness", 1.0))
        records.append({
            "label":      f"Trace {position + 1}",
            "case_id":    str(log[i].attributes.get("concept:name", i)),
            "trace_index": i,
            "fitness":    round(fitness, 3),
            "rows":       rows,
            "violations": sum(1 for r in rows if r["moveType"] != "Synchronous Move"),
        })
    return records


def variant_order(log, n_traces: int) -> list:
    """First trace index of each distinct activity sequence, most frequent first.

    Same variant key as ``get_log_trace_ids`` uses for the picker's
    variant-autoselect, so "one per variant" means the same thing in both places.
    """
    order, counts = [], {}
    for i in range(n_traces):
        seq = tuple(str(e.get("concept:name", "")) for e in log[i])
        if seq not in counts:
            counts[seq] = 0
            order.append((seq, i))
        counts[seq] += 1
    order.sort(key=lambda item: (-counts[item[0]], item[1]))
    return [i for _seq, i in order]


def sequence_of(log, i: int) -> tuple:
    """The trace's activity sequence — its variant key."""
    return tuple(str(e.get("concept:name", "")) for e in log[i])


def _matches_pattern(row, activity: str, move_type: str) -> bool:
    """Does this alignment step realise the (activity, move type) pattern?

    A mismatch move carries both labels, so it answers to either side's
    activity — it is a deviation on both.
    """
    kind = row["moveType"]
    if move_type and kind != move_type and kind != "Mismatch Move":
        return False
    if kind == "Model Move":
        return str(row["model_move"]) == activity
    if kind == "Log Move":
        return str(row["log_move"]) == activity
    if kind == "Mismatch Move":
        return activity in (str(row["log_move"]), str(row["model_move"]))
    return False


def violation_count(log, alignments, i: int, view: str = "control-flow", *,
                    pattern: str = "", **rule) -> int:
    """How many steps of this trace violate **the guideline being asked about**.

    The perspective decides, and this is the whole point: a rule that always
    counted alignment moves would hand a data-perspective task the trace with
    the most control-flow deviations, which may satisfy the data rule perfectly
    — a figure whose answer is "no violations here" to a question asking where
    the violations are.
    """
    from shared import alignment_pairs_to_rows

    rows = alignment_pairs_to_rows(alignments[i].get("alignment", []))
    if view == "control-flow":
        if pattern:
            activity, _, move_type = str(pattern).partition("|")
            return sum(1 for r in rows if _matches_pattern(r, activity, move_type))
        return sum(1 for r in rows if r["moveType"] != "Synchronous Move")
    steps = value_steps(log[i], {"rows": rows}, view, **rule)
    return sum(1 for s in steps if s["verdict"] == "violation")


def pick_indices(log, alignments, fitness_df, n: int, rule: str, *,
                 view: str = "control-flow", require_violation: bool = True,
                 pattern: str = "", **rule_kwargs) -> list:
    """Trace indices for one pick rule, in display order.

    Two filters apply before any rule does, because every rule was picking
    traces with nothing to show:

    * **one trace per distinct activity sequence** — the worst-fitness rule used
      to return the same strip two or three times over, since identical traces
      have identical fitness;
    * **only traces that violate the guideline in ``view``** — otherwise the
      figure answers a question the task did not ask. ``require_violation``
      turns this off for task27, whose question needs a conformant trace too.

    If nothing violates, the filter lifts rather than leaving the figure empty:
    a fully conformant log is a finding, not a failure.
    """
    n_traces = min(len(log), len(alignments), len(fitness_df))
    if not n_traces:
        return []

    order = (variant_order(log, n_traces) if rule == "most_frequent_variants"
             else range(n_traces))
    seen, candidates = set(), []
    for i in order:
        seq = sequence_of(log, i)
        if seq in seen:
            continue
        seen.add(seq)
        candidates.append(i)

    fitness = {i: float(fitness_df.iloc[i]["fitness"]) for i in candidates}
    violations = {i: violation_count(log, alignments, i, view, pattern=pattern,
                                     **rule_kwargs)
                  for i in candidates}

    pool = [i for i in candidates if violations[i] > 0] if require_violation else candidates
    if not pool:
        logger.warning(
            "trace_alignment: no trace violates the guideline in the %s "
            "perspective — showing conformant traces instead", view)
        pool = candidates

    if rule == "most_frequent_variants":
        return pool[:n]

    if rule == "first_nonconformant":
        return sorted(pool)[:n]

    if rule == "worst_fitness":
        # Most violations first, then lowest fitness: in a value perspective
        # every trace has the same fitness, so the violation count is what
        # ranks them at all.
        return sorted(pool, key=lambda i: (-violations[i], fitness[i], i))[:n]

    # violation_gap. The pattern has two jobs — which traces qualify, and how
    # far apart they are — and they pull against each other: a pattern occurs at
    # most once in a trace in every log looked at here, so counting *it* leaves
    # every qualifying trace on 1 and the axis collapses to a point. The pattern
    # keeps the filtering job; the spread falls back to how much each trace
    # deviates overall, which is the contrast the rule's name promises.
    axis = violations
    if pattern and len({violations[i] for i in pool}) < 2:
        axis = {i: violation_count(log, alignments, i, view, **rule_kwargs)
                for i in pool}
    return _spread_by_violations(log, pool, axis, fitness, n)


def _spread_by_violations(log, pool: list, violations: dict, fitness: dict,
                          n: int) -> list:
    """The ``violation_gap`` rule: n traces spread across the violation counts.

    ``violations`` is the axis the traces are spread along — the count of the
    named guideline's violations, or, when naming one leaves every trace on the
    same count, of their deviations overall.

    At two traces this is the most- and least-violating trace, which is what
    "largest violation gap" plainly means. Above two it was the two extremes
    plus whatever had the widest activity coverage, which had nothing to do with
    the gap — at four traces it returned violation counts of 3, 1, 1, 1, three
    of which compare nothing.

    Now the distinct violation counts present in the pool are the axis, and the
    n counts taken are evenly spaced along it (always including both ends), so
    four traces come back as 3, 2, 1 and whatever the fourth step lands on.
    Within one count the trace touching the most distinct activities wins, so
    the strips stay substantial rather than trivially short.
    """
    if not pool:
        return []
    coverage = {i: len(set(sequence_of(log, i))) for i in pool}
    best_of_count: dict = {}
    for i in sorted(pool, key=lambda i: (-coverage[i], fitness[i], i)):
        best_of_count.setdefault(violations[i], i)

    counts = sorted(best_of_count)
    if len(counts) <= n:
        picked = [best_of_count[c] for c in counts]
        # Fewer distinct counts than traces asked for: top up with the next-best
        # trace of each count rather than repeating a count's representative.
        if len(picked) < n:
            for i in sorted(pool, key=lambda i: (-violations[i], -coverage[i], i)):
                if len(picked) >= n:
                    break
                if i not in picked:
                    picked.append(i)
    else:
        # Evenly spaced positions over the distinct counts, ends included.
        positions = [round(k * (len(counts) - 1) / (n - 1)) for k in range(n)] \
            if n > 1 else [len(counts) - 1]
        picked, seen = [], set()
        for pos in positions:
            while pos in seen and pos < len(counts) - 1:
                pos += 1
            while pos in seen and pos > 0:
                pos -= 1
            if pos in seen:
                continue
            seen.add(pos)
            picked.append(best_of_count[counts[pos]])

    return sorted(picked[:n], key=lambda i: (-violations[i], fitness[i], i))


def select_records(log, alignments, *, view="control-flow", trace_ids=None,
                   rule="violation_gap", count=2, pattern="", attribute="",
                   conformant_values=(), resources=(), scoped_activity="") -> list:
    """The traces a task09-shaped task shows, annotated for its perspective."""
    import pandas as pd

    n_traces = min(len(log), len(alignments))
    if not n_traces:
        return []

    if trace_ids:
        index_of = case_index(log)
        indices = [index_of[str(t)] for t in trace_ids if str(t) in index_of]
        indices = indices[:max(count, len(indices))]
    else:
        fitness_df = pd.DataFrame(
            [{"fitness": float(a.get("fitness", 1.0))} for a in alignments[:n_traces]])
        indices = pick_indices(
            log, alignments, fitness_df, count, rule, view=view, pattern=pattern,
            attribute=attribute, conformant_values=conformant_values,
            resources=resources, scoped_activity=scoped_activity)

    records = trace_records(log, alignments, indices)
    if view != "control-flow":
        annotate_values(log, records, view, attribute=attribute,
                        conformant_values=conformant_values, resources=resources,
                        scoped_activity=scoped_activity)
    return records


def case_index(log) -> dict:
    """case id (str) -> first trace index carrying it."""
    index = {}
    for i, trace in enumerate(log):
        index.setdefault(str(trace.attributes.get("concept:name", i)), i)
    return index


# --------------------------------------------------------------------------
# The data and resource perspectives
#
# A control-flow violation is a non-synchronous move: the alignment itself says
# where it is. The other two perspectives are judged on a *value* instead — the
# attribute the trace carries, or the resource that executed the step — against
# the values the admin declared conformant. Nothing about the alignment changes;
# what counts as a violation does.
# --------------------------------------------------------------------------

#: Missing / structural alignment labels that name no real event.
_MISSING_LABELS = {"-", "None", "(skip)", ">>", ""}

RESOURCE_ATTR = "org:resource"


def _value_of(trace, event, attribute: str):
    """The attribute's value for one event, falling back to the case's own.

    A case-level attribute (``region`` on the trace) and an event-level one are
    read the same way by the caller: constancy across a trace is a property of
    the log, not something the admin should have to declare.
    """
    if event is not None and attribute in event:
        return event.get(attribute)
    attrs = getattr(trace, "attributes", {}) or {}
    if attribute in attrs:
        return attrs.get(attribute)
    return attrs.get(f"case:{attribute}")


def _bare_value(selected: str) -> str:
    """"region = International" -> "International"; a bare value passes through."""
    return selected.split("=", 1)[1].strip() if "=" in selected else selected.strip()


def value_steps(trace, record, view: str, *, attribute: str = "",
                conformant_values=(), resources=(), scoped_activity: str = "") -> list:
    """One entry per alignment step: what was prescribed, what was executed.

    ``[{activity, prescribed, executed, verdict}]`` with verdict in
    ``conformant`` / ``violation`` / ``n/a``. ``n/a`` covers a step with no
    event behind it (a skipped activity has no value and no executor) and, for
    a scoped resource rule, every activity the rule does not cover — those are
    not violations, and colouring them as such would invent findings.
    """
    if view == "resource":
        attribute = RESOURCE_ATTR
        allowed = {str(r) for r in (resources or [])}
    else:
        allowed = {_bare_value(str(v)) for v in (conformant_values or [])}

    prescribed = " / ".join(sorted(allowed)) if allowed else "—"
    events = list(trace)
    cursor = 0
    steps = []

    for row in record["rows"]:
        move = row["moveType"]
        log_label = str(row.get("log_move", ""))
        model_label = str(row.get("model_move", ""))
        has_event = move != "Model Move" and log_label not in _MISSING_LABELS
        activity = log_label if has_event else model_label

        event = None
        if has_event and cursor < len(events):
            event = events[cursor]
            cursor += 1

        in_scope = not (view == "resource" and scoped_activity
                        and activity != scoped_activity)
        if event is None or not in_scope:
            steps.append({"activity": activity, "prescribed": prescribed if in_scope else "—",
                          "executed": "—", "verdict": "n/a"})
            continue

        raw = _value_of(trace, event, attribute)
        executed = "—" if raw is None else str(raw)
        verdict = ("n/a" if raw is None
                   else "conformant" if executed in allowed
                   else "violation")
        steps.append({"activity": activity, "prescribed": prescribed,
                      "executed": executed, "verdict": verdict})

    return steps


def annotate_values(log, records, view: str, **rule) -> list:
    """Attach ``steps`` (see ``value_steps``) to each trace record."""
    for record in records:
        trace = log[record["trace_index"]]
        record["steps"] = value_steps(trace, record, view, **rule)
        record["violations"] = sum(1 for s in record["steps"]
                                   if s["verdict"] == "violation")
    return records


def perspective_title(view: str, attribute: str = "") -> str:
    if view == "resource":
        return "Resource Conformance Across Traces"
    return f"Data Conformance on '{attribute}' Across Traces" if attribute \
        else "Data Conformance Across Traces"


def perspective_legend(view: str) -> list:
    """(label, verdict) pairs, in legend order."""
    if view == "resource":
        return [("Allowed resource", "conformant"),
                ("Resource not allowed", "violation"),
                ("No resource recorded", "n/a")]
    return [("Value as prescribed", "conformant"),
            ("Value violates the rule", "violation"),
            ("No value recorded", "n/a")]


# --------------------------------------------------------------------------
# Validation shared by every task in the class
# --------------------------------------------------------------------------

def validate_selection(log, params: dict, *, min_traces: int = 1,
                       max_traces: int = 4) -> list:
    """Errors in the trace-selection block, as human-readable strings.

    Only manual mode is checked against the counts: a rule that finds fewer
    traces than asked for is a property of the log, reported by the task when it
    draws, not a mis-entered parameter.
    """
    errors = []
    params = params or {}
    ids = selected_trace_ids(params)
    if params.get("trace_selection_mode") == MANUAL and ids:
        if len(ids) < min_traces:
            errors.append(
                f"Select at least {min_traces} trace(s) to show — {len(ids)} selected."
            )
        if len(ids) > max_traces:
            errors.append(
                f"At most {max_traces} traces fit in one figure — {len(ids)} selected."
            )
    n = trace_count(params, min_traces)
    if n < min_traces or n > max_traces:
        errors.append(
            f"'How many traces to show' must be between {min_traces} and {max_traces}."
        )
    return errors


def validate_perspective(log, params: dict) -> list:
    """Errors in the data / resource branch of task09 and task28."""
    errors = []
    params = params or {}
    view = perspective(params)

    if view == "data":
        attribute = (params.get("data_attribute") or "").strip()
        values = [str(v) for v in (params.get("conformant_values") or [])]
        if not attribute:
            errors.append("Pick the data attribute the traces are checked on.")
        if not values:
            errors.append(
                "Pick at least one conformant value — without one every trace "
                "violates the rule and the figure has nothing to contrast."
            )
        # A value is offered as "attribute = value"; all of them must belong to
        # the attribute under scrutiny, or the figure would judge two attributes
        # at once.
        foreign = [v for v in values
                   if "=" in v and v.split("=", 1)[0].strip() != attribute]
        if attribute and foreign:
            errors.append(
                f"These values do not belong to '{attribute}': {', '.join(foreign)}."
            )

    elif view == "resource":
        if not (params.get("conformant_resources") or []):
            errors.append(
                "Pick at least one allowed resource — without one every event "
                "violates the rule."
            )

    return errors


# --------------------------------------------------------------------------
# Drawing the data / resource perspective
#
# The three trace-alignment figures keep their shape across all three
# perspectives — chevron strip, annotated model, activity × trace table — so a
# participant who has read one can read the others. Only what the colour means
# changes, which is what the legend says. The control-flow perspective is drawn
# by task04's renderers; these draw the other two.
# --------------------------------------------------------------------------

def _verdict_colors():
    from shared import GREY_LIGHTER, GREY_DARK
    return {"conformant": GREY_LIGHTER, "violation": GREY_DARK, "n/a": "#ffffff"}


def draw_value_chevrons(records, output_dir, filename, *, view, attribute="",
                        fontsize=17):
    """One chevron strip per trace, each step coloured by its value verdict."""
    import os
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib import gridspec
    from shared import (save_svg, draw_chevron_strip, chevron_figure_width,
                        render_empty_state_svg, FONT_LABEL, FONT_ANNOT)

    path = os.path.join(output_dir, filename)
    title = perspective_title(view, attribute)
    if not records:
        render_empty_state_svg(path, title, "No traces available.")
        return

    colors = _verdict_colors()
    nodes_per_trace = [
        [{"label": s["activity"], "color": colors[s["verdict"]]}
         for s in record.get("steps", [])]
        for record in records
    ]

    fig_w = max((chevron_figure_width(n) for n in nodes_per_trace if n), default=9.0)
    fig_h = 1.9 * len(records) + 1.6
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(len(records), 1, hspace=0.9)
    for r, (record, nodes) in enumerate(zip(records, nodes_per_trace)):
        ax = fig.add_subplot(gs[r])
        if nodes:
            draw_chevron_strip(ax, nodes, fontsize=fontsize)
        else:
            ax.axis("off")
        # The value is the finding here, so it is named next to the trace rather
        # than left for the reader to infer from a colour.
        executed = {s["executed"] for s in record.get("steps", []) if s["executed"] != "—"}
        shown = ", ".join(sorted(executed)[:3]) if executed else "no value recorded"
        ax.set_title(f"{record['label']} — {shown}", fontsize=FONT_LABEL,
                     loc="left", pad=6)

    handles = [mpatches.Patch(facecolor=colors[v], edgecolor="#4a4a4a", label=lbl)
               for lbl, v in perspective_legend(view)]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
               ncol=len(handles), frameon=False, fontsize=FONT_ANNOT - 1)
    fig.tight_layout(rect=[0, 0.08, 1, 1.0])
    save_svg(fig, path)


def draw_value_bpmn(records, model_path, output_dir, filename, *, view, attribute=""):
    """The guideline model once per trace, each task coloured by its verdict."""
    import os
    from shared import (parse_bpmn_model, compose_bpmn_panels, render_empty_state_svg,
                        contrasting_text_color)

    path = os.path.join(output_dir, filename)
    title = perspective_title(view, attribute)
    if not records or not model_path:
        render_empty_state_svg(path, title, "No traces or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path, node_scale=1.6)
    except Exception as exc:  # a malformed model is the admin's to fix
        logger.warning("trace_alignment: BPMN parse failed: %s", exc)
        render_empty_state_svg(path, title, "BPMN model could not be parsed.")
        return

    colors = _verdict_colors()

    def style_for(record):
        verdict_of = {}
        for step in record.get("steps", []):
            # A trace touching one activity twice keeps the worse verdict: the
            # violation is what the task asks the participant to find.
            current = verdict_of.get(step["activity"])
            if current != "violation":
                verdict_of[step["activity"]] = step["verdict"]

        def _style(_eid, elem):
            if elem.get("kind") == "task":
                verdict = verdict_of.get(elem.get("name", ""))
                if verdict in ("conformant", "violation"):
                    fill = colors[verdict]
                    return (fill, "#444444", 3 if verdict == "violation" else 2,
                            contrasting_text_color(fill))
            return ("white", "#888888", 2, "#333333")

        return _style

    panels = [{
        "parsed": parsed,
        "node_style_fn": style_for(record),
        "subtitle": record["label"],
    } for record in records]

    compose_bpmn_panels(
        panels, path, title=title,
        legend_items=[(colors[v], "#444444", 2, lbl)
                      for lbl, v in perspective_legend(view)],
        node_font_size=20,
    )


def draw_value_table(records, output_dir, filename, *, view, attribute=""):
    """Activity × trace table of prescribed vs executed values.

    The prescribed/executed pair per activity is what task09 asks the
    participant to report, so the table states it rather than encoding it.
    """
    import os
    import matplotlib.pyplot as plt
    from shared import (save_svg, make_table, auto_col_widths, FONT_TITLE)

    path = os.path.join(output_dir, filename)
    title = perspective_title(view, attribute)

    activities, prescribed = [], "—"
    for record in records:
        for step in record.get("steps", []):
            if step["activity"] not in activities:
                activities.append(step["activity"])
            if step["prescribed"] != "—":
                prescribed = step["prescribed"]

    if not activities:
        fig, ax = plt.subplots(figsize=(6.5, 3.0))
        ax.axis("off")
        make_table(ax, cell_text=[["—", "—"]], col_labels=["Activity", "Value"],
                   bbox=[0.05, 0.05, 0.9, 0.92])
        ax.set_title(title, fontsize=FONT_TITLE, pad=3)
        fig.tight_layout(pad=1.2)
        save_svg(fig, path)
        return

    marks = {"conformant": "✓", "violation": "✗", "n/a": ""}
    cell_text = []
    for activity in activities:
        row = [activity, prescribed]
        for record in records:
            step = next((s for s in record.get("steps", [])
                         if s["activity"] == activity), None)
            if step is None:
                row.append("—")
            else:
                row.append(f"{step['executed']} {marks[step['verdict']]}".strip())
        cell_text.append(row)

    col_labels = ["Activity", "Prescribed"] + [r["label"] for r in records]
    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig_w = max(7.5, 4.4 + 2.1 * len(records))
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
