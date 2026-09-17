"""
Violation profile: what violations occurred, and how often.

The third shared kernel, after ``trace_features`` (how traces are grouped) and
``trace_response`` (what is measured per group). Those two answer "which
attribute explains the violations" and "what does conformance imply". This one
takes the violations themselves as the subject: it never asks what caused them
or what they led to, only what they *are* and how they are distributed.

Seven tasks ask that question, and they already differ in exactly one way —
what a violation is counted *as*:

    move_type   Model Move / Log Move / Mismatch Move          (task29 today)
    activity    per activity, broken down by move type         (task11 today)
    pattern     "Log Move on Ship Order" as one unit           (task23 today)

Those are not three pipelines, they are one ``groupby`` with three keys, which
is why ``grouping_strategy`` is a parameter rather than three modules. Every
count comes from ``trace_response.violation_table``, so the tau/activity
filtering and the move-name spelling are decided in one place for this class
and the Attribute -> Violation one alike.

Two numbers are reported per group, because the tasks disagree about which they
mean: ``count`` is occurrences (a trace deviating twice on one activity counts
twice) and ``traces`` is distinct traces (it counts once). task29 shows both,
task11's screenshots show ``traces`` and its percentage of the whole log. Which
one an idiom draws is the idiom's business; both are always available so no
caller has to recompute the other.
"""

import logging

import pandas as pd

import trace_response

logger = logging.getLogger(__name__)

#: The three ways a violation can be counted. The order is the order they are
#: offered in, from coarsest to finest.
STRATEGIES = ("move_type", "activity", "pattern")

#: Column of the violation table each strategy groups by, and the column it
#: keeps as a secondary series. "activity" keeps the move type so one activity
#: shows its Model and Log moves side by side — that is what task11's frozen
#: screenshots draw — while "pattern" folds the two into one label instead.
_STRATEGY_COLUMNS = {
    "move_type": ("move_type", None),
    "activity":  ("activity", "move_type"),
    "pattern":   ("pattern", None),
}

#: Which selection parameter narrows which strategy. A selection is always
#: optional: empty means every group, which is what the tasks did before the
#: choice existed.
STRATEGY_SELECTION_KEY = {
    "move_type": "move_types",
    "activity":  "activities",
    "pattern":   "violation_patterns",
}

MOVE_TYPES = ("Model Move", "Log Move", "Mismatch Move")


# ---------------------------------------------------------------------------
# PARAM_SPEC entries — declared here so seven tasks cannot drift apart
# ---------------------------------------------------------------------------

GROUPING_STRATEGY_PARAM = {
    "key": "grouping_strategy",
    "slot": "grouping",
    "label": "How violations are grouped",
    "hint": "Counts every violation the same way; only the unit they are grouped into changes",
    "widget": "select-one",
    "options": [
        {"value": "move_type", "label": "By move type (Model Move / Log Move / Mismatch)"},
        {"value": "activity",  "label": "By activity, broken down by move type"},
        {"value": "pattern",   "label": "Not grouped — one unit per 'Move on Activity'"},
    ],
    "default": "move_type",
    "required": False,
}

#: One per strategy, and only the one matching `grouping_strategy` applies.
#: `visible_if` lets /specify hide the other two rather than offering an admin
#: three controls where two are inert.
MOVE_TYPE_SELECTION_PARAM = {
    "key": "move_types",
    "slot": "selection",
    "label": "Move types to include (empty = all)",
    "widget": "select-many",
    "options": list(MOVE_TYPES),
    "default": [],
    "required": False,
    "visible_if": {"grouping_strategy": "move_type"},
}

ACTIVITY_SELECTION_PARAM = {
    "key": "activities",
    "slot": "selection",
    "label": "Activities to include (empty = all)",
    "widget": "select-many",
    "source": "log.violation_activities",
    "default": [],
    "required": False,
    "visible_if": {"grouping_strategy": "activity"},
}

PATTERN_SELECTION_PARAM = {
    "key": "violation_patterns",
    "slot": "selection",
    "label": "Violation patterns to include (empty = all)",
    "widget": "select-many",
    "source": "log.violations",
    "default": [],
    "required": False,
    "visible_if": {"grouping_strategy": "pattern"},
}

SELECTION_PARAMS = [
    MOVE_TYPE_SELECTION_PARAM,
    ACTIVITY_SELECTION_PARAM,
    PATTERN_SELECTION_PARAM,
]

_SELECTION_PARAM_BY_STRATEGY = {
    "move_type": MOVE_TYPE_SELECTION_PARAM,
    "activity":  ACTIVITY_SELECTION_PARAM,
    "pattern":   PATTERN_SELECTION_PARAM,
}


def selection_param_for(strategy: str) -> dict:
    """The selection parameter for a task whose strategy is fixed in code.

    Strips `visible_if`: with no strategy picker on the task there is nothing
    for the condition to read, so /specify would evaluate it against an absent
    value, decide the entry does not apply, and hide the only control the task
    has.
    """
    entry = dict(_SELECTION_PARAM_BY_STRATEGY[strategy])
    entry.pop("visible_if", None)
    return entry

#: Splits the log into sub-logs whose profiles are compared. Single-select: the
#: figures put one sub-log per series, and two split attributes at once would be
#: a cross-tabulation none of these idioms draw.
SPLIT_ATTRIBUTE_PARAM = {
    "key": "split_attribute",
    "slot": "split",
    "label": "Attribute splitting the log into sub-logs (empty = whole log)",
    "hint": "Each sub-log gets its own violation profile, compared side by side",
    "widget": "select-one",
    "source": "log.candidate_attributes",
    "default": "",
    "required": False,
}

#: Cut separating the violations worth naming from the long tail. task32 calls
#: them "main" and task36 "predominant"; it is the same cut on the same number,
#: so it is one parameter with the task's own wording in its label.
def prominence_threshold_param(label: str, hint: str = "") -> dict:
    return {
        "key": "prominence_threshold",
        "slot": "threshold",
        "label": label,
        "hint": hint or "Share of all violation occurrences a group must reach",
        "widget": "number",
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
        "default": 5.0,
        "required": False,
    }


# ---------------------------------------------------------------------------
# The profile
# ---------------------------------------------------------------------------

#: Spellings a saved move type can arrive in. The short codes are what
#: ``log.violations`` and task11's saved selections use, and "Move on Model" is
#: the pre-unification long form (see the move-name note in
#: docs/CONFORMANCE_ATTRIBUTE_CLASS.md), still present in selections saved then.
_MOVE_TYPE_ALIASES = {
    "mom": "Model Move", "move on model": "Model Move", "model move": "Model Move",
    "mol": "Log Move", "move on log": "Log Move", "log move": "Log Move",
    "mm": "Mismatch Move", "mismatch move": "Mismatch Move",
}


def parse_pattern(spec):
    """One pattern selection to an ``(activity, move_type)`` pair, or None.

    The pattern dropdown (``log.violations``) stores ``"activity|Move Type"``
    while the violation table labels the same thing ``"activity (Move Type)"``,
    so matching the two on the display string silently selects nothing. Both
    forms are accepted here, as are ``"activity::Move Type"``, a 2-tuple, and
    the short codes MoM / MoL / MM.
    """
    if spec is None:
        return None
    if isinstance(spec, (tuple, list)) and len(spec) == 2:
        act, move = str(spec[0]).strip(), str(spec[1]).strip()
    else:
        text = str(spec).strip()
        if "|" in text:
            act, move = text.rsplit("|", 1)
        elif "::" in text:
            act, move = text.rsplit("::", 1)
        elif text.endswith(")") and "(" in text:
            act, move = text[:-1].rsplit("(", 1)
        else:
            return None
        act, move = act.strip(), move.strip()
    return act, _MOVE_TYPE_ALIASES.get(move.lower(), move)


def normalise_move_type(spec) -> str:
    """One move-type selection to its canonical spelling."""
    return _MOVE_TYPE_ALIASES.get(str(spec).strip().lower(), str(spec).strip())


def profile(alignments, strategy: str = "move_type", *, selection=None,
            n_traces: int = None, assignment=None) -> pd.DataFrame:
    """The violation profile, one row per group.

    Columns: ``group``, ``series``, ``count``, ``traces``, ``pct_traces``,
    ``pct_count``, and ``split_group`` when ``assignment`` is given.

    The two percentages have different denominators because the tasks mean
    different things by "how often": ``pct_traces`` is the share of the log's
    traces touched by this group (task11's screenshots), ``pct_count`` the share
    of all violation occurrences it accounts for (task23's tables). Deriving one
    from the other is not possible, so both are returned.

    ``series`` is the secondary breakdown — the move type under the "activity"
    strategy, and None otherwise. Rows are ordered by trace count descending
    with the group name breaking ties, so the same data always produces the same
    order (an arbitrary order became a visible one more than once in this
    codebase).

    ``selection`` narrows which groups appear, in the units the strategy counts
    in: move-type names, activity names, or ``"activity|Move Type"`` patterns.
    Empty means every group.

    ``assignment`` is one sub-log label per trace (None = excluded), as returned
    by ``trace_features.split`` — the same shape the Attribute -> Violation
    class uses, so a sub-log split is declared once for both classes.
    """
    if strategy not in _STRATEGY_COLUMNS:
        raise ValueError(
            f"Unknown grouping strategy '{strategy}'. "
            f"Expected one of {', '.join(STRATEGIES)}."
        )
    group_col, series_col = _STRATEGY_COLUMNS[strategy]

    table = trace_response.violation_table(alignments)
    if n_traces is None:
        n_traces = len(alignments)

    empty_cols = ["group", "series", "count", "traces", "pct_traces", "pct_count"]
    if assignment is not None:
        empty_cols.append("split_group")
    if table.empty:
        return pd.DataFrame(columns=empty_cols)

    df = table.copy()

    # Each strategy's dropdown stores its own value shape, and none of them is
    # the display label: match on the table's own columns instead.
    if selection:
        if strategy == "activity":
            df = df[df["activity"].isin({str(a).strip() for a in selection})]
        elif strategy == "move_type":
            df = df[df["move_type"].isin({normalise_move_type(m) for m in selection})]
        else:
            pairs = {p for p in (parse_pattern(s) for s in selection) if p}
            if not pairs:
                logger.warning(
                    "      violation_profile: none of the %d selected patterns "
                    "could be parsed — showing every pattern instead.", len(selection)
                )
            else:
                df = df[[(a, m) in pairs
                         for a, m in zip(df["activity"], df["move_type"])]]
        if df.empty:
            return pd.DataFrame(columns=empty_cols)

    keys = [group_col] + ([series_col] if series_col else [])
    if assignment is not None:
        labels = list(assignment)
        df["split_group"] = [
            labels[i] if i < len(labels) else None for i in df["trace_index"]
        ]
        df = df[df["split_group"].notna()]
        if df.empty:
            return pd.DataFrame(columns=empty_cols)
        keys = ["split_group"] + keys

    agg = (df.groupby(keys, as_index=False)
             .agg(count=("trace_index", "size"),
                  traces=("trace_index", "nunique")))

    agg = agg.rename(columns={group_col: "group"})
    if series_col:
        agg = agg.rename(columns={series_col: "series"})
    else:
        agg["series"] = None

    agg["pct_traces"] = (agg["traces"] / n_traces * 100) if n_traces else 0.0
    # Denominator is every violation occurrence in the log, not just the rows
    # left after a selection — a selected subset still reports its true share.
    total_count = float(len(table))
    agg["pct_count"] = (agg["count"] / total_count * 100) if total_count else 0.0

    sort_cols = ["traces", "group"] + (["series"] if series_col else [])
    ascending = [False, True] + ([True] if series_col else [])
    if assignment is not None:
        sort_cols = ["split_group"] + sort_cols
        ascending = [True] + ascending
    agg = agg.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)

    cols = ["group", "series", "count", "traces", "pct_traces", "pct_count"]
    if assignment is not None:
        cols.append("split_group")
    return agg[cols]


def prominent(profile_df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """The groups at or above ``threshold`` percent of all violation occurrences.

    The "main" violations of task32 and the "predominant" ones of task36 — the
    same cut, named differently by the two tasks. Measured on occurrence share
    rather than trace share, because the question is which violations dominate
    the process, not how widely each is spread.
    """
    if profile_df.empty:
        return profile_df
    return profile_df[profile_df["pct_count"] >= float(threshold)].reset_index(drop=True)


def activity_coverage(alignments, n_traces: int = None):
    """Per activity, how many distinct traces carry any violation on it.

    Returns ``[(activity, traces, pct_traces), ...]``, most traces first.

    Not derivable from the "activity" profile by summing its move-type rows: a
    trace that deviates on one activity both ways appears under Model Move and
    under Log Move, and adding those counts it twice. On BPIC12 that turns
    A_APPROVED's 869 traces into 1738 — more traces than actually deviate.
    """
    table = trace_response.violation_table(alignments)
    if n_traces is None:
        n_traces = len(alignments)
    if table.empty:
        return []
    per = (table.groupby("activity", as_index=False)
                .agg(traces=("trace_index", "nunique"))
                .sort_values(["traces", "activity"], ascending=[False, True]))
    return [(str(r["activity"]), int(r["traces"]),
             (r["traces"] / n_traces * 100) if n_traces else 0.0)
            for _, r in per.iterrows()]


def violation_activities(alignments) -> list:
    """Activities that carry at least one violation, most traces first.

    Powers the "activities" selection dropdown. Distinct from
    ``log.activities``, which lists every activity in the log — offering an
    admin an activity with nothing to show would produce an empty group.
    """
    return [a for a, _, _ in activity_coverage(alignments)]
