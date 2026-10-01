"""
Response-side measures for the Attribute → Violation class.

The companion to ``trace_features``: that module decides how traces are grouped,
this one decides what is measured per group. Three measures, deliberately
orthogonal:

    fitness         mean alignment fitness per group — continuous
    violation_rate  share of traces carrying at least one violating step
    patterns        the violations themselves (see task30's violation table)

``violation_rate`` is defined from the alignment steps, **not** from a fitness
cut. That keeps it invariant to the conformant threshold and consistent with
``patterns``, which reads the same alignments — and it reflects that fitness and
violation counting are genuinely different quantities, not complements. Fitness
is cost-weighted and length-normalised; a violation count is neither, so a
five-step trace with one deviation and a fifty-step trace with one deviation
share a violation count but not a fitness.

"% conformant" is not a measure here. It needs a cut on fitness, and the four
call sites that computed one disagreed about where the cut goes: task01 and
task30 used ``fitness >= 1.0`` while task15, task16, task22 and task33 each
wrote out ``_FIT_THRESHOLD = 0.8`` separately, so a trace at 0.9 was conformant
in one task and non-conformant in another. Where a cut is still wanted it comes
from one admin parameter, passed in as ``conformant_threshold``.
"""

import logging

import numpy as np
import pandas as pd

from shared import alignment_pairs_to_rows

logger = logging.getLogger(__name__)

RESPONSE_MEASURES = ("fitness", "violation_rate", "patterns")

#: Fitness at or above this counts as conformant when no threshold is given.
#: Perfect conformance — any deviating move at all puts a trace below it.
DEFAULT_CONFORMANT_THRESHOLD = 1.0


def violating_traces(alignments) -> list:
    """One flag per trace: does its alignment contain any non-synchronous move?

    Computed **before** the tau/activity filter that the pattern table applies.
    A trace deviating only on hidden transitions is still deviating — its
    fitness is below 1 either way — so filtering those rows out first would
    report it as conformant and disagree with every fitness-based number.
    """
    flags = []
    for result in alignments:
        rows = alignment_pairs_to_rows(result.get("alignment", []))
        flags.append(any(row["moveType"] != "Synchronous Move" for row in rows))
    return flags


#: PARAM_SPEC entries for the threshold slot. Neither is shared by every task:
#: a conformant cut only means something for the fitness measure, and a top-N
#: only for patterns — which is why they carry the same `slot` and a task
#: declares at most one of them.
CONFORMANT_THRESHOLD_PARAM = {
    "key": "conformant_threshold",
    "slot": "threshold",
    "label": "Fitness at or above which a trace counts as conformant",
    "hint": "1.0 means only perfectly fitting traces count as conformant",
    "widget": "number",
    "min": 0.0,
    "max": 1.0,
    "step": 0.05,
    "default": 1.0,
    "required": False,
}

PATTERN_TOP_N_PARAM = {
    "key": "pattern_top_n",
    "slot": "threshold",
    "label": "How many violation patterns to show",
    "widget": "number",
    "min": 3,
    "max": 30,
    "step": 1,
    "default": 10,
    "required": False,
}

#: Alignment labels that name no real activity (tau / hidden transitions).
_NON_ACTIVITY_LABELS = {"-", "None", "(skip)", ">>", ""}

#: Label for traces whose grouping feature has no value, under
#: missing_policy="own_group".
MISSING_GROUP = "Missing"


def violation_table(alignments) -> pd.DataFrame:
    """One row per violating alignment step, independent of any grouping.

    Columns: trace_index, activity, move_type, pattern.

    ``activity`` and ``move_type`` are separate columns so either can serve as a
    grouping axis on its own — "all Model Moves regardless of activity", "every
    violation on activity X regardless of type". They used to exist only baked
    into ``pattern`` as ``"X (Log Move)"``, which forced callers to parse the
    string back apart to get at either half. ``pattern`` remains as the display
    label.

    Computing this without an assignment means a change of grouping no longer
    re-walks every alignment, and the table can be reused by tasks that do not
    group at all.
    """
    rows = []
    for trace_index, result in enumerate(alignments):
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            move_type = step["moveType"]
            if move_type == "Synchronous Move":
                continue
            activity = (step["model_move"] if move_type == "Model Move"
                        else step["log_move"])
            if not activity or str(activity) in _NON_ACTIVITY_LABELS:
                continue
            activity = str(activity)
            rows.append({
                "trace_index": trace_index,
                "activity": activity,
                "move_type": move_type,
                "pattern": f"{activity} ({move_type})",
            })
    if not rows:
        return pd.DataFrame(columns=["trace_index", "activity", "move_type", "pattern"])
    return pd.DataFrame(rows)


def assign_groups(violations: pd.DataFrame, assignment,
                  missing_policy: str = "drop") -> pd.DataFrame:
    """Attach a ``group`` column to a violation table.

    ``missing_policy="drop"`` removes rows whose trace has no group, which is
    what the callers did implicitly — silently, so an attribute with poor
    coverage quietly shrank every denominator. ``"own_group"`` keeps them under
    ``MISSING_GROUP`` instead, making the loss visible in the output.
    """
    if missing_policy not in ("drop", "own_group"):
        raise ValueError(f"Unknown missing_policy '{missing_policy}'.")
    if violations.empty:
        return violations.assign(group=pd.Series(dtype=object))

    labels = list(assignment)
    groups = [
        labels[i] if i < len(labels) else None
        for i in violations["trace_index"]
    ]
    out = violations.copy()
    out["group"] = groups
    if missing_policy == "own_group":
        out["group"] = out["group"].where(out["group"].notna(), MISSING_GROUP)
        return out.reset_index(drop=True)
    return out[out["group"].notna()].reset_index(drop=True)


def fitness_stats(fitness_per_trace, assignment, groups,
                  conformant_threshold=None) -> pd.DataFrame:
    """Per-group fitness summary.

    Columns: group, n, mean, median, std, min, max. When
    ``conformant_threshold`` is given, n_conformant and pct_conformant are added
    — omit it and the group is described by its mean alone, with no cut.

    ``assignment`` is one group label per trace (None = excluded), as returned
    by ``trace_features.split``.
    """
    series = pd.Series(list(fitness_per_trace), dtype=float)
    labels = pd.Series(list(assignment), dtype=object)

    rows = []
    for group in groups:
        sub = series[labels == group]
        n = len(sub)
        row = {
            "group": group,
            "n": n,
            "mean": float(sub.mean()) if n else 0.0,
            "median": float(sub.median()) if n else 0.0,
            "std": float(sub.std()) if n else 0.0,
            "min": float(sub.min()) if n else 0.0,
            "max": float(sub.max()) if n else 0.0,
        }
        if conformant_threshold is not None:
            n_conformant = int((sub >= conformant_threshold).sum()) if n else 0
            row["n_conformant"] = n_conformant
            row["pct_conformant"] = (n_conformant / n * 100) if n else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def violation_rate_stats(violating, assignment, groups) -> pd.DataFrame:
    """Per-group violation rate: share of traces with at least one violating step.

    Columns: group, n, n_violating, pct_violating. Takes the flags from
    ``violating_traces`` so every caller shares one definition.
    """
    flags = pd.Series([bool(v) for v in violating], dtype=bool)
    labels = pd.Series(list(assignment), dtype=object)

    rows = []
    for group in groups:
        sub = flags[labels == group]
        n = len(sub)
        n_violating = int(sub.sum()) if n else 0
        rows.append({
            "group": group,
            "n": n,
            "n_violating": n_violating,
            "pct_violating": (n_violating / n * 100) if n else 0.0,
        })
    return pd.DataFrame(rows)


def attribute_panels(log, features, response_measure, *, alignments=None,
                     fitness_per_trace=None, strategy=None, cap=None,
                     missing_policy="drop", labels_only_missing=False) -> list:
    """One panel per feature: ``[(meta, (labels, values, counts)), ...]``.

    The shared kernel behind every "split by an attribute, measure per group"
    idiom. ``meta`` carries the feature's key, label and value type; ``labels``
    are the group labels, ``values`` the measured quantity per group and
    ``counts`` the traces behind each.

    What ``values`` holds follows ``response_measure``:

        violation_rate  % of the group's traces carrying a violating step
        fitness         the group's mean fitness

    Features that cannot be split (one value throughout, or no value at all)
    are skipped rather than drawn as a single meaningless bar.
    """
    import trace_features

    if response_measure not in ("violation_rate", "fitness"):
        raise ValueError(
            f"attribute_panels supports 'violation_rate' and 'fitness', "
            f"not '{response_measure}'."
        )
    if response_measure == "violation_rate":
        if alignments is None:
            raise ValueError("violation_rate needs alignments.")
        per_trace = violating_traces(alignments)
    else:
        if fitness_per_trace is None:
            raise ValueError("fitness needs fitness_per_trace.")
        per_trace = list(fitness_per_trace)

    panels = []
    for key in features:
        try:
            values, value_type = trace_features.extract(log, key)
            values, value_type = trace_features.as_bucketable(values, value_type, key=key)
        except (KeyError, ValueError) as e:
            logger.warning(f"      attribute_panels: skipping '{key}' — {e}")
            continue

        result = trace_features.split(values, value_type, strategy=strategy,
                                      cap=cap, missing_policy=missing_policy)
        if not result or len(result.labels) < 2:
            continue

        if response_measure == "violation_rate":
            stats = violation_rate_stats(per_trace, result.assignment, result.labels)
            measured = [float(v) for v in stats["pct_violating"]]
        else:
            stats = fitness_stats(per_trace, result.assignment, result.labels)
            measured = [float(v) for v in stats["mean"]]
        counts = [int(v) for v in stats["n"]]
        # Traces with no value for this feature leave every group and every
        # denominator. That used to be a silent drop configurable by an admin
        # who had no way to know it mattered; say how many instead.
        excluded = len(per_trace) - sum(counts)
        if excluded:
            logger.warning(
                f"      attribute_panels: '{key}' has no value for {excluded} of "
                f"{len(per_trace)} traces — they are excluded from its panel."
            )

        meta = {
            "key": key,
            "label": trace_features.label_for(key),
            "type": value_type,
            "measure": response_measure,
        }
        panels.append((meta, (list(result.labels), measured, counts)))
    return panels


def measure(response_measure: str, *, fitness_per_trace=None, violating=None,
            assignment=None, groups=None, conformant_threshold=None) -> pd.DataFrame:
    """Dispatch to the per-group statistics for one response measure.

    `patterns` is not computed here — it needs the violation table rather than a
    per-group scalar, so task30's aggregation owns it.
    """
    if response_measure == "fitness":
        return fitness_stats(fitness_per_trace, assignment, groups,
                             conformant_threshold=conformant_threshold)
    if response_measure == "violation_rate":
        return violation_rate_stats(violating, assignment, groups)
    if response_measure == "patterns":
        raise ValueError(
            "The 'patterns' measure is produced by the violation table, not by a "
            "per-group statistic — see task30._aggregate_patterns."
        )
    raise ValueError(
        f"Unknown response measure '{response_measure}'. "
        f"Expected one of {', '.join(RESPONSE_MEASURES)}."
    )
