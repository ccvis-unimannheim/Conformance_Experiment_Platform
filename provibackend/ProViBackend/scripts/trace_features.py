"""
Trace-level feature registry.

Single source of truth for what an admin can split a log by. Every entry here is
a **trace-level** feature: event-level raw columns (``concept:name``,
``org:resource``, ``time:timestamp``) never appear, only the trace-level
features derived from them. One raw column yields several features, each
separately named and canonically defined, so there is no per-feature
"aggregation" parameter to choose.

This replaces key-scanning (``task13.discover_candidate_attributes``), which
enumerated raw log keys and hard-coded a single derived feature (throughput).
Control-flow features in particular were unreachable that way: ``concept:name``
is a structural key, so "does this trace contain activity X" could never be
offered even though ``task20`` computes it internally.

Two rules shape the catalog:

1. **Cardinality never gates availability.** A high-cardinality feature (61
   distinct resources, say) is still offered; ``cardinality`` and ``coverage``
   are reported so the caller can pick a split strategy, or warn. Gating on
   "can this be bucketed" is what silently removed ``org:resource``.
2. **case-level vs event-level is decided by value constancy** — if a data
   attribute holds one value across every event of every trace, it describes the
   case and yields a single feature; otherwise it yields mean/max (numeric) or
   mode (categorical). This does not depend on whether a CSV header happens to
   carry a ``case:`` prefix.

Keys are stable: a data attribute keeps its own name (``AMOUNT_REQ``) and
throughput keeps ``__throughput_hours__``, so ``attribute_set`` values saved by
existing experiments keep resolving.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Backwards-compatible key for trace duration (was task13.THROUGHPUT_KEY).
DURATION_KEY = "__throughput_hours__"
START_TIME_KEY = "__start_time__"

# Namespaced keys for the activity- and resource-derived features.
#: "Did this trace ever execute <activity> with <attribute> = <value>" — the
#: event class of the attribute picker. Not enumerated by discover_features: the
#: cross product of activities, attributes and values is a catalogue, not a
#: feature set, so the candidates come from the log (get_log_event_conditions)
#: and the admin names the ones worth asking about.
AT_PREFIX = "at::"
#: A log-level attribute. Constant for every trace by definition, so it groups
#: nothing — it describes the whole log, and a task that selects one is asking
#: for the log as a single group.
LOG_PREFIX = "log::"
CONTAINS_PREFIX = "contains::"
COUNT_PREFIX = "count::"
FIRST_ACTIVITY_KEY = "__first_activity__"
LAST_ACTIVITY_KEY = "__last_activity__"
RESOURCE_DOMINANT_KEY = "resource::dominant"
RESOURCE_FIRST_KEY = "resource::first"
RESOURCE_LAST_KEY = "resource::last"
RESOURCE_N_DISTINCT_KEY = "resource::n_distinct"
CONFORMANCE_KEY = "conformance::value"

_ACTIVITY_ATTR = "concept:name"
_RESOURCE_ATTR = "org:resource"
_TIMESTAMP_ATTR = "time:timestamp"

# Keys that describe the log's structure rather than the case. Unlike the list
# this replaces, no dataset-specific column (BPIC12's REG_DATE) is hard-coded
# here — a useless column now shows up with a telling cardinality instead of
# being hidden.
_STRUCTURAL_KEYS = {
    _ACTIVITY_ATTR,
    _TIMESTAMP_ATTR,
    "lifecycle:transition",
    "case:concept:name",
    "concept:instance",
}

PERSPECTIVES = ("control-flow", "data", "resource", "time")
VALUE_TYPES = ("numeric", "categorical", "boolean", "ordinal")

#: Value types the bucketer understands. All of them — "ordinal" (a timestamp)
#: is cut into calendar periods by the ordered-bins strategy.
BUCKETABLE_TYPES = ("numeric", "categorical", "boolean", "ordinal")

#: Calendar periods an ordinal feature can be cut into, coarsest first, with the
#: pandas period alias for each. Duplicated from shared.TIME_GRANULARITY_FREQ
#: rather than imported: this module is deliberately free of heavy dependencies
#: so the attribute picker never pulls matplotlib in behind it.
TIME_GRANULARITIES = ("year", "month", "day")
TIME_GRANULARITY_FREQ = {"year": "Y", "month": "M", "day": "D"}


@dataclass(frozen=True)
class Feature:
    """One selectable trace-level feature.

    ``role`` keeps alignment-derived quantities (fitness, violation counts) off
    the predictor side — a task that explains violations with violations
    produces a chart with a correlation of 1 and nothing to analyse. Everything
    in this module is a predictor; the response side is a separate parameter.

    ``cardinality`` is the number of distinct trace-level values and
    ``coverage`` the share of traces carrying one. Both inform the split
    strategy; neither decides whether the feature is offered.
    """

    key: str
    label: str
    perspective: str
    source: str            # "raw" | "derived"
    value_type: str
    requires: str = "log"  # "log" | "log+model" | "log+alignment"
    role: str = "predictor"
    cardinality: Optional[int] = None
    coverage: float = 1.0
    #: The canonical reading of its raw attribute. One raw column yields several
    #: features — an amount has a final value, a mean and a maximum — and a
    #: picker that lists them all equally makes the admin choose an aggregation
    #: before they have chosen an attribute. The primary is the one the default
    #: set takes and the picker lists first; the others stay selectable.
    primary: bool = False
    meta: dict = field(default_factory=dict)

    def as_option(self) -> dict:
        """Row shape for the /specify parameter picker.

        ``value``/``label`` are what _param_candidates and the option editor
        read; the rest is extra context the UI may show and validation ignores.
        """
        return {
            "value": self.key,
            "label": self.label,
            "perspective": self.perspective,
            "value_type": self.value_type,
            "cardinality": self.cardinality,
            "coverage": round(self.coverage, 4),
            "primary": self.primary,
        }


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------

def _as_float(value) -> Optional[float]:
    """Numeric reading of a raw attribute value, or None if it is not numeric."""
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_missing(value) -> bool:
    if value is None:
        return True
    # NaN is the only value that is not equal to itself.
    return isinstance(value, float) and value != value


def _mode(values: list):
    """Most frequent value, ties broken by first appearance."""
    counts: dict = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=lambda k: (counts[k], -list(counts).index(k)))


def _stats(values: list) -> tuple[Optional[int], float]:
    """(cardinality, coverage) over one per-trace value list."""
    present = [v for v in values if not _is_missing(v)]
    if not values:
        return 0, 0.0
    try:
        cardinality = len({v for v in present})
    except TypeError:                      # unhashable values
        cardinality = None
    return cardinality, len(present) / len(values)


# ---------------------------------------------------------------------------
# Log inspection
# ---------------------------------------------------------------------------

def _trace_case_value(trace, key: str):
    """Case-level value of *key*, tolerating PM4Py's two placements."""
    for candidate in (key, f"case:{key}"):
        if candidate in trace.attributes:
            return trace.attributes[candidate]
    return None


def _event_values(trace, key: str) -> list:
    return [ev[key] for ev in trace if key in ev and not _is_missing(ev[key])]


def _raw_attribute_keys(log) -> list[str]:
    """Every non-structural attribute key in the log.

    Scans **all** traces, not just the first. An XES log's event attributes vary
    by activity, so a key carried only by a later activity is invisible to a
    first-trace scan; a CSV log has a fixed column set and is unaffected either
    way.
    """
    keys: set = set()
    for trace in log:
        keys.update(trace.attributes.keys())
        for event in trace:
            keys.update(event.keys())

    out = []
    for key in sorted(keys):
        text = str(key)
        if key in _STRUCTURAL_KEYS or text.startswith("@@") or text.lower().startswith("unnamed"):
            continue
        if text.startswith("case:") and text[len("case:"):] in _STRUCTURAL_KEYS:
            continue
        out.append(key)
    return out


def _collect(log, key: str) -> tuple[list, str, bool]:
    """Per-trace values for *key*.

    Returns ``(per_trace_values, kind, constant_within_traces)`` where the third
    element applies rule 2: True when the key holds at most one distinct value
    inside every trace, which is what makes it describe the case rather than the
    event. ``kind`` is "numeric", "categorical" or "missing"; a column counts as
    numeric only if every observed value coerces to float.
    """
    per_trace: list[list] = []
    constant = True
    for trace in log:
        case_value = _trace_case_value(trace, key)
        if not _is_missing(case_value):
            per_trace.append([case_value])
            continue
        values = _event_values(trace, key)
        per_trace.append(values)
        if len({str(v) for v in values}) > 1:
            constant = False

    flat = [v for values in per_trace for v in values]
    if not flat:
        return per_trace, "missing", constant
    kind = "numeric" if all(_as_float(v) is not None for v in flat) else "categorical"
    return per_trace, kind, constant


def _activity_stats(log) -> tuple[dict, list[str]]:
    """(traces containing each activity, activities ordered by that count)."""
    containment: dict = {}
    for trace in log:
        for activity in {str(ev[_ACTIVITY_ATTR]) for ev in trace if _ACTIVITY_ATTR in ev}:
            containment[activity] = containment.get(activity, 0) + 1
    ordered = sorted(containment, key=lambda a: (-containment[a], a))
    return containment, ordered


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_features(log, activity_cap: Optional[int] = None,
                      fitness_per_trace=None) -> list[Feature]:
    """Every trace-level feature this log supports, as Feature rows.

    ``activity_cap`` limits how many activities get ``contains::`` / ``count::``
    entries, most-common first; None offers all of them. The picker wants all —
    the cap exists for callers building a fixed-width feature matrix, which is
    the only reason task20's tree ever looked at 14 activities.

    Needs only the event log: no model, no alignments. The picker used to
    compute alignments purely to reach the throughput column.

    ``fitness_per_trace`` adds the one feature the log alone cannot supply —
    conformance itself. It is what the Conformance → Attribute tasks split by,
    and it is a predictor there rather than a response: they ask what
    distinguishes conformant traces, not what causes non-conformance, so no
    circularity arises as long as the measured response is not also alignment-
    derived.
    """
    n_traces = len(log)
    if n_traces == 0:
        return []

    features: list[Feature] = []
    features.extend(_control_flow_features(log, activity_cap))
    features.extend(_data_features(log))
    features.extend(_resource_features(log))
    features.extend(_time_features(log))
    if fitness_per_trace is not None:
        features.extend(_conformance_features(fitness_per_trace))
    return features


def _conformance_features(fitness_per_trace) -> list:
    values = [None if _is_missing(v) else float(v) for v in fitness_per_trace]
    cardinality, coverage = _stats(values)
    return [Feature(
        key=CONFORMANCE_KEY, label="Conformance (fitness)", perspective="control-flow",
        source="alignment", value_type="numeric", requires="log+alignment",
        cardinality=cardinality, coverage=coverage,
    )]


def _control_flow_features(log, activity_cap: Optional[int]) -> list[Feature]:
    containment, ordered = _activity_stats(log)
    if not ordered:
        return []
    n_traces = len(log)
    selected = ordered if activity_cap is None else ordered[:activity_cap]

    out: list[Feature] = []
    for activity in selected:
        # A feature true (or false) for every trace cannot separate anything;
        # it is reported with cardinality 1 rather than hidden, but there is no
        # point generating a count companion for it either.
        out.append(Feature(
            key=f"{CONTAINS_PREFIX}{activity}",
            label=f"Contains '{activity}'",
            perspective="control-flow",
            source="derived",
            value_type="boolean",
            cardinality=1 if containment[activity] in (0, n_traces) else 2,
            coverage=1.0,
            # "Did it happen" is the canonical question about an activity; "how
            # many times" is the follow-up, and on most logs it answers the same
            # thing with more buckets.
            primary=True,
            meta={"activity": activity, "n_traces_containing": containment[activity]},
        ))

    counts_by_activity = _activity_count_values(log, selected)
    for activity in selected:
        cardinality, coverage = _stats(counts_by_activity[activity])
        out.append(Feature(
            key=f"{COUNT_PREFIX}{activity}",
            label=f"Occurrences of '{activity}'",
            perspective="control-flow",
            source="derived",
            value_type="numeric",
            cardinality=cardinality,
            coverage=coverage,
            meta={"activity": activity},
        ))

    firsts = [_first_activity(trace) for trace in log]
    lasts = [_last_activity(trace) for trace in log]
    for key, label, values in (
        (FIRST_ACTIVITY_KEY, "First activity", firsts),
        (LAST_ACTIVITY_KEY, "Last activity", lasts),
    ):
        cardinality, coverage = _stats(values)
        out.append(Feature(
            key=key, label=label, perspective="control-flow", source="derived",
            value_type="categorical", cardinality=cardinality, coverage=coverage,
        ))
    return out


def _activity_count_values(log, activities: list[str]) -> dict:
    per_activity = {activity: [] for activity in activities}
    wanted = set(activities)
    for trace in log:
        counts: dict = {}
        for event in trace:
            activity = str(event.get(_ACTIVITY_ATTR)) if _ACTIVITY_ATTR in event else None
            if activity in wanted:
                counts[activity] = counts.get(activity, 0) + 1
        for activity in activities:
            per_activity[activity].append(counts.get(activity, 0))
    return per_activity


def _first_activity(trace):
    for event in trace:
        if _ACTIVITY_ATTR in event:
            return str(event[_ACTIVITY_ATTR])
    return None


def _last_activity(trace):
    found = None
    for event in trace:
        if _ACTIVITY_ATTR in event:
            found = str(event[_ACTIVITY_ATTR])
    return found


def _data_features(log) -> list[Feature]:
    out: list[Feature] = []
    for key in _raw_attribute_keys(log):
        if key in (_RESOURCE_ATTR, f"case:{_RESOURCE_ATTR}"):
            continue                                   # handled as resource features
        per_trace, kind, constant = _collect(log, key)
        if kind == "missing":
            continue

        if constant:
            # Rule 2: one value per trace, so the attribute describes the case.
            values = [vs[0] if vs else None for vs in per_trace]
            cardinality, coverage = _stats(values)
            out.append(Feature(
                key=str(key), label=str(key), perspective="data", source="raw",
                value_type=kind, cardinality=cardinality, coverage=coverage,
                primary=True, meta={"granularity": "case"},
            ))
            continue

        if kind == "numeric":
            # `last` is the canonical reading: an event-level number is usually a
            # state the process rewrites (the amount after the last adjustment),
            # and a mean over rewrites answers no question anyone asks. `sum` is
            # offered for the additive ones (cost), which no rule can tell apart
            # from the state-like ones by name.
            for suffix, label_suffix in (("last", "final value"), ("mean", "mean"),
                                         ("max", "max"), ("sum", "sum")):
                values = _aggregate_numeric(per_trace, suffix)
                cardinality, coverage = _stats(values)
                out.append(Feature(
                    key=f"{key}::{suffix}", label=f"{key} ({label_suffix})",
                    perspective="data", source="derived", value_type="numeric",
                    cardinality=cardinality, coverage=coverage,
                    primary=(suffix == "last"),
                    meta={"granularity": "event", "attribute": str(key)},
                ))
        else:
            for suffix, label_suffix in (("last", "final value"), ("mode", "most frequent")):
                if suffix == "last":
                    values = [str(vs[-1]) if vs else None for vs in per_trace]
                else:
                    values = [_mode([str(v) for v in vs]) if vs else None for vs in per_trace]
                cardinality, coverage = _stats(values)
                out.append(Feature(
                    key=f"{key}::{suffix}", label=f"{key} ({label_suffix})",
                    perspective="data", source="derived", value_type="categorical",
                    cardinality=cardinality, coverage=coverage,
                    primary=(suffix == "last"),
                    meta={"granularity": "event", "attribute": str(key)},
                ))
    return out


def _aggregate_numeric(per_trace: list[list], how: str) -> list:
    """Collapse each trace's event values to one number.

    ``last`` is the value the process left behind, ``sum`` the total it
    accumulated, ``max`` the worst it reached, ``mean`` the typical one. Four
    different questions; the caller names which.
    """
    out = []
    for values in per_trace:
        numbers = [f for f in (_as_float(v) for v in values) if f is not None]
        if not numbers:
            out.append(None)
        elif how == "max":
            out.append(max(numbers))
        elif how == "sum":
            out.append(sum(numbers))
        elif how == "last":
            out.append(numbers[-1])
        else:
            out.append(sum(numbers) / len(numbers))
    return out


def _resource_features(log) -> list[Feature]:
    per_trace = [[str(v) for v in _event_values(trace, _RESOURCE_ATTR)] for trace in log]
    if not any(per_trace):
        return []

    dominant = [_mode(values) if values else None for values in per_trace]
    firsts = [values[0] if values else None for values in per_trace]
    lasts = [values[-1] if values else None for values in per_trace]
    distinct = [len(set(values)) for values in per_trace]

    out: list[Feature] = []
    for key, label, values, value_type in (
        # Who did most of the case is the canonical "who owns this"; the others
        # answer different questions (who started it, who closed it, how many
        # hands it passed through) and stay selectable.
        (RESOURCE_DOMINANT_KEY, "Executor (most frequent)", dominant, "categorical"),
        (RESOURCE_FIRST_KEY, "Executor (first event)", firsts, "categorical"),
        (RESOURCE_LAST_KEY, "Executor (last event)", lasts, "categorical"),
        (RESOURCE_N_DISTINCT_KEY, "Number of distinct executors", distinct, "numeric"),
    ):
        cardinality, coverage = _stats(values)
        out.append(Feature(
            key=key, label=label, perspective="resource", source="derived",
            value_type=value_type, cardinality=cardinality, coverage=coverage,
            primary=(key == RESOURCE_DOMINANT_KEY),
        ))
    return out


def _time_features(log) -> list[Feature]:
    starts, durations = [], []
    for trace in log:
        stamps = [ev[_TIMESTAMP_ATTR] for ev in trace
                  if _TIMESTAMP_ATTR in ev and not _is_missing(ev[_TIMESTAMP_ATTR])]
        if not stamps:
            starts.append(None)
            durations.append(None)
            continue
        starts.append(min(stamps))
        durations.append((max(stamps) - min(stamps)).total_seconds() / 3600.0)

    out: list[Feature] = []
    cardinality, coverage = _stats(durations)
    out.append(Feature(
        key=DURATION_KEY, label="Throughput time (h)", perspective="time",
        source="derived", value_type="numeric",
        cardinality=cardinality, coverage=coverage, primary=True,
    ))
    cardinality, coverage = _stats([str(s) for s in starts])
    out.append(Feature(
        key=START_TIME_KEY, label="Trace start time", perspective="time",
        source="derived", value_type="ordinal",
        cardinality=cardinality, coverage=coverage,
        meta={"bucketing": "ordered_bins", "granularities": ["year", "month", "day"]},
    ))
    return out


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def label_for(key: str) -> str:
    """Display label for a feature key, without needing the log.

    Callers that hold only the key (a saved ``attribute_set``, say) get the same
    wording the picker showed, instead of falling back to the raw key.

    Pure key -> string: it must work from a stored parameter value alone, so
    nothing here touches a log. (It used to open with a copy of ``extract``'s
    conformance branch, which referenced arguments this function does not have
    and raised NameError for that one key.)
    """
    if key.startswith(AT_PREFIX):
        activity, _, rest = key[len(AT_PREFIX):].partition("|")
        attribute, _, value = rest.partition("|")
        return f"At '{activity}': {attribute} = {value}"
    if key.startswith(LOG_PREFIX):
        return f"{key[len(LOG_PREFIX):]} (log level)"
    if key.startswith(CONTAINS_PREFIX):
        return f"Contains '{key[len(CONTAINS_PREFIX):]}'"
    if key.startswith(COUNT_PREFIX):
        return f"Occurrences of '{key[len(COUNT_PREFIX):]}'"
    fixed = {
        FIRST_ACTIVITY_KEY: "First activity",
        LAST_ACTIVITY_KEY: "Last activity",
        RESOURCE_DOMINANT_KEY: "Executor (most frequent)",
        RESOURCE_FIRST_KEY: "Executor (first event)",
        RESOURCE_LAST_KEY: "Executor (last event)",
        RESOURCE_N_DISTINCT_KEY: "Number of distinct executors",
        CONFORMANCE_KEY: "Conformance (fitness)",
        DURATION_KEY: "Throughput time (h)",
        START_TIME_KEY: "Trace start time",
    }
    if key in fixed:
        return fixed[key]
    for suffix, wording in (("::mean", "mean"), ("::max", "max"), ("::sum", "sum"),
                            ("::last", "final value"), ("::mode", "most frequent")):
        if key.endswith(suffix):
            return f"{key[: -len(suffix)]} ({wording})"
    return key


def as_bucketable(values: list, value_type: str) -> tuple[list, str]:
    """Adapt extracted values to what the bucketer accepts: numeric or categorical.

    Booleans become readable category labels rather than 0/1, so a bucket reads
    "Yes"/"No" instead of a number that looks like a measurement. Ordinal values
    have no bucketer yet and raise, which is why the picker filters them out.
    """
    if value_type == "boolean":
        return (["Yes" if v else "No" for v in values], "categorical")
    if value_type in ("numeric", "categorical", "ordinal"):
        return (values, value_type)
    raise ValueError(f"Value type '{value_type}' has no bucketing strategy.")


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

STRATEGIES = ("none", "binary", "nominal_n", "ordered_bins")

DEFAULT_BIN_COUNT = 4      # quantile bins for ordered_bins
DEFAULT_GROUP_CAP = 4      # named groups for nominal_n, before "Other"

_MISSING_LABEL = "Missing"


#: PARAM_SPEC entries every splitting task shares. The feature picker itself
#: stays per-task (its key and wording differ), but how the chosen feature is
#: cut into groups is the same question everywhere. `slot` groups parameters
#: that compete for the same decision, so a task cannot offer two of them and an
#: admin cannot select a conflicting pair.
SPLIT_PARAMS = [
    {
        "key": "split_strategy",
        "slot": "split",
        "label": "How each attribute is cut into groups "
                 "(empty = ranges for numbers and dates, one group per value otherwise)",
        # Participant-facing: which groups the figure compares, not how the
        # platform arrived at them.
        "hint": "Groups compared",
        "widget": "select-one",
        # A strategy that does not fit an attribute falls back to the one its
        # type deserves (see `split`), so these read as preferences rather than
        # instructions — "two halves" cannot mean anything for Yes/No.
        "options": [
            {"value": "ordered_bins",
             "label": "Ranges — numbers into quantile bands, dates into calendar periods"},
            {"value": "binary",
             "label": "Two halves — above and below the median (numbers and dates only)"},
            {"value": "nominal_n",
             "label": "One group per value — the most frequent, the rest as “Other”"},
        ],
        "default": "",
        "required": False,
    },
    {
        "key": "group_cap",
        "slot": "split",
        "label": "Most groups to name before the rest become “Other”",
        "widget": "number",
        "min": 2,
        "max": 12,
        "step": 1,
        "default": DEFAULT_GROUP_CAP,
        "required": False,
    },
]


def split_params_for(strategy: Optional[str] = None) -> list:
    """The split-slot parameters that still make sense for a fixed strategy.

    A task whose strategy is settled in code does not offer it to the admin, and
    the cap is meaningless for a two-way cut — so `binary` exposes nothing here,
    while a free strategy exposes both.
    """
    if strategy is None:
        return [dict(p) for p in SPLIT_PARAMS]
    if strategy in ("nominal_n", "ordered_bins"):
        return [dict(p) for p in SPLIT_PARAMS if p["key"] == "group_cap"]
    return []


@dataclass(frozen=True)
class Split:
    """Trace-to-group assignment produced by one split strategy.

    ``labels`` is empty when the values cannot be split at all (every value
    missing, or a numeric column with no variance under ordered_bins), which the
    caller renders as its empty state.
    """

    labels: list
    assignment: list
    strategy: str
    value_type: str
    meta: dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.labels)


def is_identifier_like(cardinality: int, n_traces: int) -> bool:
    """A categorical with about one value per trace names cases, not groups."""
    return cardinality > max(5, n_traces * 0.5)


def offerable(log, features=None) -> list:
    """The features worth putting in front of an admin, in picker order.

    The registry's own rule is that cardinality never gates *availability* —
    a 61-value resource is a feature, and the split strategy deals with it. But
    a picker is a different question: a feature with one distinct value puts
    every trace in one group, and a categorical one with a value per trace is an
    identifier whose buckets are singletons plus a huge "Other". Neither can
    answer "how does this relate to violations". Numeric and ordinal features
    are exempt — quantiles and calendar periods cope with any number of values,
    and throughput time (one value per trace) is the most useful feature here.

    Canonical readings come first, so the admin meets "amount" before "amount
    (mean) / (max) / (sum)".
    """
    n_traces = len(log)
    features = discover_features(log) if features is None else features
    out = []
    for f in features:
        if f.value_type not in BUCKETABLE_TYPES or (f.cardinality or 0) <= 1:
            continue
        if f.value_type == "categorical" and is_identifier_like(f.cardinality, n_traces):
            continue
        out.append(f)
    out.sort(key=lambda f: (not f.primary, f.perspective, f.key))
    return out


def default_keys(log, features=None) -> list:
    """What an empty attribute selection falls back to: the canonical features.

    The same list the picker shows first, so "leave it empty" and "take the
    obvious ones" agree — they used to be two different rules, and the picker
    offered features the default set could never produce.
    """
    return [f.key for f in offerable(log, features) if f.primary]


def default_strategy(value_type: str) -> str:
    """The strategy a value type gets when the admin picks none."""
    if value_type == "numeric":
        return "ordered_bins"
    if value_type == "ordinal":
        return "ordered_bins"
    return "nominal_n"


def split(values, value_type: str, strategy: Optional[str] = None,
          cap: Optional[int] = None, label_prefix: Optional[str] = None,
          missing_policy: str = "drop", granularity: Optional[str] = None,
          edges=None, cut: Optional[float] = None) -> Split:
    """Assign each trace to a group.

    Replaces two separate bucketers that disagreed on the numeric case:
    task13's quantile ranges and task30's median split are the same operation
    under ``ordered_bins`` and ``binary``. Their two caps disagreed too —
    ``MAX_CATEGORIES`` counted total buckets while ``MAX_CATEGORICAL_GROUPS``
    counted real groups — so ``cap`` here always means **named groups before
    "Other"**.

    An ordinal feature — a timestamp — is cut into calendar periods rather than
    quantiles, since an even split of dates reads as arbitrary ranges while
    "2011-10", "2011-11" reads as a timeline. ``granularity`` picks the period;
    without one the finest that yields at least two periods is used.

    ``edges`` and ``cut`` name the boundaries instead of deriving them: a
    conformance scale has meaningful cut points (1.0 is perfect, 0.8 is a
    convention) that quantiles of the observed data would never land on, and a
    study that fixes its categories needs the same bins whatever the log holds.

    ``label_prefix`` reproduces task30's "ATTR = value" / "ATTR ≤ x" wording;
    without it labels are bare, as task13 renders them. ``missing_policy``
    decides whether traces with no value are dropped (assignment None) or
    collected into their own group, so they stop vanishing from every
    denominator without a trace.
    """
    if missing_policy not in ("drop", "own_group"):
        raise ValueError(f"Unknown missing_policy '{missing_policy}'.")
    strategy = strategy or default_strategy(value_type)
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown split strategy '{strategy}'.")

    # A boolean is two groups already; asking for a median of True/False raises
    # inside numpy, and the value is offered as bucketable, so normalise here
    # rather than at each of the call sites that remembered to.
    if value_type == "boolean":
        values, value_type = as_bucketable(list(values), value_type)

    # The strategy is one parameter over a selection of attributes whose types
    # differ, so it cannot be right for all of them: "cut at the median" means
    # nothing for `contains::X` (Yes/No) or for a region. It used to produce no
    # groups at all there — a silently blank panel, with the figure's own
    # "no candidate attribute could be bucketed" state as the only clue. An
    # attribute the strategy does not fit now falls back to the one its type
    # deserves.
    if strategy in ("binary", "ordered_bins") and value_type == "categorical":
        logger.info(
            "trace_features: '%s' does not apply to a categorical attribute — "
            "grouping by value instead", strategy)
        strategy = "nominal_n"

    values = list(values)
    n_missing = sum(1 for v in values if _is_missing(v))
    meta = {"type": value_type, "median": None, "numeric_values": None,
            "n_missing": n_missing, "strategy": strategy}

    if strategy == "none":
        label = label_prefix or "All traces"
        assignment = [None if _is_missing(v) else label for v in values]
        return _finish(Split([label], assignment, strategy, value_type, meta),
                       values, missing_policy)

    if value_type == "ordinal" and strategy == "ordered_bins":
        result = _split_calendar(values, cap, label_prefix, meta, granularity)
    elif strategy in ("binary", "ordered_bins"):
        result = _split_numeric(values, strategy, cap, label_prefix, meta,
                                edges=edges, cut=cut)
    else:
        result = _split_nominal(values, cap, label_prefix, meta)

    return _finish(result, values, missing_policy)


def _finish(result: Split, values: list, missing_policy: str) -> Split:
    """Apply the missing-value policy to a finished assignment."""
    if missing_policy == "drop" or not result.labels:
        return result
    if not any(a is None for a in result.assignment):
        return result
    assignment = [a if a is not None else _MISSING_LABEL for a in result.assignment]
    return Split(list(result.labels) + [_MISSING_LABEL], assignment,
                 result.strategy, result.value_type, result.meta)


def _split_numeric(values, strategy, cap, label_prefix, meta, edges=None, cut=None) -> Split:
    import numpy as np
    import pandas as pd
    from shared import format_threshold

    numbers = pd.to_numeric(pd.Series(values), errors="coerce")
    meta["numeric_values"] = [None if pd.isna(x) else float(x) for x in numbers]
    present = numbers.dropna()
    if present.empty:
        return Split([], [None] * len(values), strategy, meta["type"], meta)

    if strategy == "binary":
        median = float(cut) if cut is not None else float(np.median(present))
        meta["median"] = median
        meta["cut"] = median
        if float(present.max()) - float(present.min()) < 1e-12:
            # Every trace carries the same value: one group, not a split.
            label = (f"{label_prefix} = {format_threshold(median)}" if label_prefix
                     else format_threshold(median))
            assignment = [None if pd.isna(x) else label for x in numbers]
            return Split([label], assignment, strategy, meta["type"], meta)
        # A median splits the data in two, so the midpoint belongs to the lower
        # half. A named threshold means "at or above this counts", so the cut
        # point belongs to the upper one — "conformant at 1.0" has to include
        # the traces that fit exactly.
        if cut is not None:
            below, at_or_above = "<", "≥"
            in_low = lambda x: x < median
        else:
            below, at_or_above = "≤", ">"
            in_low = lambda x: x <= median
        edge = format_threshold(median)
        low = f"{label_prefix} {below} {edge}" if label_prefix else f"{below} {edge}"
        high = f"{label_prefix} {at_or_above} {edge}" if label_prefix else f"{at_or_above} {edge}"
        assignment = [None if pd.isna(x) else (low if in_low(x) else high) for x in numbers]
        return Split([low, high], assignment, strategy, meta["type"], meta)

    # ordered_bins
    if present.nunique() < 2 or len(present) < 2:
        return Split([], [None] * len(values), strategy, meta["type"], meta)
    if edges is not None:
        edges = np.asarray(sorted(float(e) for e in edges), dtype=float)
    else:
        bins = cap or DEFAULT_BIN_COUNT
        edges = np.unique(np.quantile(present, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:
        return Split([], [None] * len(values), strategy, meta["type"], meta)
    labels = [f"{format_threshold(edges[i])}–{format_threshold(edges[i + 1])}"
              for i in range(len(edges) - 1)]
    if label_prefix:
        labels = [f"{label_prefix} {lab}" for lab in labels]
    assignment = []
    for x in numbers:
        if pd.isna(x):
            assignment.append(None)
        else:
            idx = int(np.clip(np.digitize([x], edges[1:-1])[0], 0, len(labels) - 1))
            assignment.append(labels[idx])
    return Split(labels, assignment, strategy, meta["type"], meta)


def _split_calendar(values, cap, label_prefix, meta, granularity) -> Split:
    """Cut timestamps into calendar periods, coarsest that still separates them.

    Bins are the periods actually present, in order, so an empty month between
    two busy ones does not appear — the axis follows the data rather than the
    calendar.
    """
    import pandas as pd

    stamps = pd.to_datetime(pd.Series(list(values)), errors="coerce", utc=True)
    meta["granularity"] = granularity
    if stamps.notna().sum() == 0:
        return Split([], [None] * len(values), "ordered_bins", meta["type"], meta)

    order = list(TIME_GRANULARITIES)
    candidates = [granularity] if granularity else order
    chosen, periods = None, None
    for gran in candidates:
        if gran not in TIME_GRANULARITY_FREQ:
            raise ValueError(
                f"Unknown granularity '{gran}' — expected one of {', '.join(order)}."
            )
        binned = stamps.dt.to_period(TIME_GRANULARITY_FREQ[gran])
        if granularity or binned.dropna().nunique() >= 2:
            chosen, periods = gran, binned
            break
    if chosen is None:                      # every period identical at every grain
        chosen, periods = order[-1], stamps.dt.to_period(TIME_GRANULARITY_FREQ[order[-1]])

    meta["granularity"] = chosen
    present = sorted(p for p in periods.dropna().unique())
    if cap and len(present) > cap:
        # Too many periods to read: keep the most recent `cap`, since a timeline
        # that runs off the axis is worse than one that starts later.
        present = present[-cap:]
    keep = set(present)
    labels = [f"{label_prefix} {p}" if label_prefix else str(p) for p in present]
    label_of = {p: lab for p, lab in zip(present, labels)}
    assignment = [label_of.get(p) if p in keep else None for p in periods]
    return Split(labels, assignment, "ordered_bins", meta["type"], meta)


def _split_nominal(values, cap, label_prefix, meta) -> Split:
    import pandas as pd

    texts = pd.Series([None if _is_missing(v) else str(v) for v in values])
    present = texts.dropna()
    if present.empty:
        return Split([], [None] * len(values), "nominal_n", meta["type"], meta)

    cap = cap or DEFAULT_GROUP_CAP
    top = present.value_counts().head(cap).index.tolist()
    has_other = present.nunique() > len(top)

    def label_of(value: str) -> str:
        return f"{label_prefix} = {value}" if label_prefix else value

    labels = [label_of(v) for v in top] + (["Other"] if has_other else [])
    lookup = {v: label_of(v) for v in top}
    assignment = [
        None if v is None else lookup.get(v, "Other" if has_other else None)
        for v in texts
    ]
    meta["n_other"] = sum(1 for a in assignment if a == "Other")
    return Split(labels, assignment, "nominal_n", meta["type"], meta)


def extract(log, key: str, fitness_per_trace=None) -> tuple[list, str]:
    """Per-trace values for one feature key, as ``(values, value_type)``.

    One entry per trace, in log order, None where the trace carries no value.
    Raises KeyError for a key this log does not support, so a stale
    ``attribute_set`` fails loudly instead of rendering an empty panel.
    """
    if key == CONFORMANCE_KEY:
        if fitness_per_trace is None:
            raise KeyError(
                f"'{key}' is alignment-derived — pass fitness_per_trace to read it."
            )
        return ([None if _is_missing(v) else float(v) for v in fitness_per_trace], "numeric")

    if key.startswith(AT_PREFIX):
        activity, _, rest = key[len(AT_PREFIX):].partition("|")
        attribute, _, wanted = rest.partition("|")
        values = []
        for trace in log:
            hit = any(str(ev.get(_ACTIVITY_ATTR, "")) == activity
                      and attribute in ev and str(ev[attribute]) == wanted
                      for ev in trace)
            values.append(hit)
        return (values, "boolean")

    if key.startswith(LOG_PREFIX):
        attribute = key[len(LOG_PREFIX):]
        attrs = getattr(log, "attributes", {}) or {}
        if attribute not in attrs:
            raise KeyError(f"'{attribute}' is not a log-level attribute of this log.")
        return ([str(attrs[attribute])] * len(log), "categorical")

    if key.startswith(CONTAINS_PREFIX):
        activity = key[len(CONTAINS_PREFIX):]
        return ([activity in {str(ev[_ACTIVITY_ATTR]) for ev in trace if _ACTIVITY_ATTR in ev}
                 for trace in log], "boolean")

    if key.startswith(COUNT_PREFIX):
        activity = key[len(COUNT_PREFIX):]
        return (_activity_count_values(log, [activity])[activity], "numeric")

    if key == FIRST_ACTIVITY_KEY:
        return ([_first_activity(trace) for trace in log], "categorical")
    if key == LAST_ACTIVITY_KEY:
        return ([_last_activity(trace) for trace in log], "categorical")

    if key in (RESOURCE_DOMINANT_KEY, RESOURCE_FIRST_KEY,
               RESOURCE_LAST_KEY, RESOURCE_N_DISTINCT_KEY):
        per_trace = [[str(v) for v in _event_values(trace, _RESOURCE_ATTR)] for trace in log]
        if key == RESOURCE_N_DISTINCT_KEY:
            return ([len(set(values)) for values in per_trace], "numeric")
        if key == RESOURCE_FIRST_KEY:
            return ([values[0] if values else None for values in per_trace], "categorical")
        if key == RESOURCE_LAST_KEY:
            return ([values[-1] if values else None for values in per_trace], "categorical")
        return ([_mode(values) if values else None for values in per_trace], "categorical")

    if key in (DURATION_KEY, START_TIME_KEY):
        values = []
        for trace in log:
            stamps = [ev[_TIMESTAMP_ATTR] for ev in trace
                      if _TIMESTAMP_ATTR in ev and not _is_missing(ev[_TIMESTAMP_ATTR])]
            if not stamps:
                values.append(None)
            elif key == START_TIME_KEY:
                values.append(min(stamps))
            else:
                values.append((max(stamps) - min(stamps)).total_seconds() / 3600.0)
        return (values, "numeric" if key == DURATION_KEY else "ordinal")

    for suffix in ("::mean", "::max", "::sum", "::last", "::mode"):
        if key.endswith(suffix):
            attribute = key[: -len(suffix)]
            per_trace, kind, _constant = _collect(log, attribute)
            if kind == "missing":
                raise KeyError(f"Attribute '{attribute}' is not present in this log.")
            if suffix == "::mode":
                return ([_mode([str(v) for v in vs]) if vs else None for vs in per_trace],
                        "categorical")
            if suffix == "::last" and kind != "numeric":
                return ([str(vs[-1]) if vs else None for vs in per_trace], "categorical")
            return (_aggregate_numeric(per_trace, suffix[2:]), "numeric")

    per_trace, kind, constant = _collect(log, key)
    if kind == "missing":
        raise KeyError(f"Unknown trace feature '{key}'.")
    if not constant:
        # Rule 2 again: a bare key only names a case-level feature. Taking the
        # first event's value here is what silently mislabelled event-level
        # attributes as case-level; say so instead.
        suffixes = "::mean / ::max" if kind == "numeric" else "::mode"
        raise KeyError(
            f"'{key}' varies within a trace, so it is event-level and has no single "
            f"trace value — use {suffixes}."
        )
    return ([vs[0] if vs else None for vs in per_trace], kind)

# ---------------------------------------------------------------------------
# The attribute picker: three classes, one selection
#
# An attribute is selectable at three levels, and they are different analyses
# rather than three lists to mix:
#
#   trace  one value per case — a case attribute, or an event-level one
#          aggregated (see _data_features). Groups traces, which is what every
#          task in this family draws.
#   event  "at activity X, attribute Y = Z" — a question about one step, asked
#          of every trace as yes/no. Also groups traces, but by what happened at
#          a named step rather than by a case-wide value.
#   log    one value for the whole log. Groups nothing: every trace lands in the
#          same bucket, so a task selecting one is asking for the log as a
#          single group. Most logs carry only export metadata here and the
#          picker is empty, which the page says.
#
# Only one class applies at a time: mixing a case attribute with a step
# condition would put two different questions on one axis.
# ---------------------------------------------------------------------------

ATTRIBUTE_CLASS_PARAM = {
    "key": "attribute_class",
    "slot": "attribute_class",
    "label": "Level the attributes are taken from",
    "hint": "Whether the traces are grouped by a case-level value or by what happened at one step",
    "widget": "select-one",
    "options": [
        {"value": "trace", "label": "Trace level — one value per case"},
        {"value": "event", "label": "Event level — at activity X, attribute Y = Z"},
        {"value": "log",   "label": "Log level — one value for the whole log"},
    ],
    "default": "trace",
    "required": False,
}


def _picker(key: str, label: str, source: str, klass: str, multi: bool) -> dict:
    return {
        "key": key,
        "slot": "attribute",
        "label": label,
        "hint": "Attributes analysed",
        "widget": "select-many" if multi else "select-one",
        "source": source,
        "default": [] if multi else "",
        "required": False,
        "visible_if": {"attribute_class": klass},
    }


def attribute_params(multi: bool = True) -> list:
    """The class selector plus one picker per class.

    ``multi`` is False for a task that splits by a single attribute (task30).
    """
    return [
        dict(ATTRIBUTE_CLASS_PARAM),
        _picker("attribute_set" if multi else "compare_attribute",
                "Attributes to analyse (empty = every attribute of this log that can be grouped)"
                if multi else "Case attribute used to split traces into sub-logs",
                "log.candidate_attributes", "trace", multi),
        _picker("event_conditions" if multi else "compare_event_condition",
                "Event conditions to analyse" if multi else
                "Event condition used to split traces into sub-logs",
                "log.event_conditions", "event", multi),
        _picker("log_attributes" if multi else "compare_log_attribute",
                "Log-level attributes" if multi else "Log-level attribute",
                "log.log_attributes", "log", multi),
    ]


def selected_keys(params: dict, log=None) -> list:
    """The feature keys the admin's selection resolves to.

    An empty *trace* selection falls back to the canonical set (`default_keys`);
    an empty event or log selection does not, because there is nothing canonical
    about one step condition out of hundreds — validate_attribute_class rejects
    it instead.
    """
    params = params or {}
    klass = params.get("attribute_class") or "trace"
    if klass == "event":
        return [str(k) for k in (params.get("event_conditions") or [])]
    if klass == "log":
        return [str(k) for k in (params.get("log_attributes") or [])]
    chosen = [str(k) for k in (params.get("attribute_set") or [])]
    if chosen:
        return chosen
    return default_keys(log) if log is not None else []


def selected_key(params: dict) -> str:
    """The single key a split-by-one task resolves to (task30)."""
    params = params or {}
    klass = params.get("attribute_class") or "trace"
    if klass == "event":
        return str(params.get("compare_event_condition") or "")
    if klass == "log":
        return str(params.get("compare_log_attribute") or "")
    return str(params.get("compare_attribute") or "")


def validate_attribute_class(params: dict, *, multi: bool = True) -> list:
    """Errors in the attribute block: one class only, and it must say something."""
    params = params or {}
    klass = params.get("attribute_class") or "trace"
    fields = (("trace", "attribute_set" if multi else "compare_attribute"),
              ("event", "event_conditions" if multi else "compare_event_condition"),
              ("log", "log_attributes" if multi else "compare_log_attribute"))
    filled = [name for cls, name in fields if params.get(name)]
    errors = []
    if len(filled) > 1:
        errors.append(
            "Attributes are selected from one level at a time — clear "
            + " and ".join(n for n in filled if n != dict(fields)[klass])
            + " or switch the level."
        )
    own = dict((cls, name) for cls, name in fields)[klass]
    if klass in ("event", "log") and not params.get(own):
        errors.append(f"Select at least one {klass}-level attribute, or switch the level.")
    return errors
