# Attribute → Violation: parameter specification

Scope: the **Attribute → Violation** task class — task01, 07, 13, 15, 16, 20, 21,
22, 30, 33, and task18, which shares the attribute picker below even though its
event-level unit kept it out of the split/response framing (a Model Move carries
no `(activity, resource, timestamp)` identity).

Every task in the class is one configuration of

```
split(trace-level feature) × measure(response)
```

so the parameters fall into three slots. A task fills each slot with at most one
value, which is what keeps an admin from selecting two conflicting parameters.

---

## Slot 1 — split (predictor side)

```
split_feature    select-many, source = log.candidate_attributes
split_strategy   none | binary | nominal_n | ordered_bins
group_cap        int
missing_policy   drop | own_group
```

### Features

All entries are **trace-level**. Event-level raw columns (`concept:name`,
`org:resource`, `time:timestamp`) never appear — only the trace-level features
derived from them. One raw column yields several features, each separately named
and canonically defined, so no per-feature "aggregation" parameter is needed.

| Feature | Type | Perspective | Status |
|---|---|---|---|
| `contains::<activity>` | boolean | control-flow | implemented (`trace_features`) |
| `count::<activity>` | numeric | control-flow | implemented |
| `__first_activity__` | categorical | control-flow | implemented |
| `__last_activity__` | categorical | control-flow | implemented |
| `attr::K` (case-level) | numeric / categorical | data | implemented; key is the attribute's own name |
| `K::mean`, `K::max` (event-level) | numeric | data | implemented |
| `K::mode` (event-level) | categorical | data | implemented |
| `resource::dominant` / `::first` / `::last` | categorical | resource | implemented |
| `resource::n_distinct` | numeric | resource | implemented |
| `__throughput_hours__` | numeric | time | implemented |
| `__start_time__` | ordinal | time | discovered, but withheld from the picker until ordered bins ship |

On BPIC12-A the registry yields 30 features (22 control-flow, 2 data, 4 resource,
2 time) where key-scanning offered 3.


`K` = a data attribute discovered in the log; the key set is dataset-specific,
so these entries are generated per attribute rather than enumerated by hand.

Dropped from earlier drafts: order/precedence features (directly-follows,
eventually-follows).

### case-level vs event-level for `attr::K`

Decided: **by value constancy.**

```
K constant within every trace  →  attr::K
K varies in some trace         →  attr::K::mean / ::max / ::mode
```

This does not depend on whether the CSV header carries a `case:` prefix (BPIC12's
does; a future dataset's may not). The registry records the observed fact — "this
attribute is constant within every case in this dataset" — rather than asserting
intent, because a genuinely event-level attribute that happens to be constant
would otherwise be misclassified silently. Verified on BPIC12: `org:resource` is
constant within only 28.6% of cases, so the rule correctly calls it event-level.

### `attribute_set` and `compare_attribute` merge into `split_feature`

They are the same operation at different multiplicity — "bucket traces by one
attribute" — but the two spellings differ in four ways, and `compare_attribute`
is worse on every one:

| | `attribute_set` (task20) | `compare_attribute` (task22/30/32/33) |
|---|---|---|
| cardinality | list | single string |
| widget | `select-many` | `text` — free typing |
| candidates | `source: log.candidate_attributes` | none |
| validation | membership-checked | none |
| default | `[]` → auto-discover | `"AMOUNT_REQ"` hard-coded |
| bucketing | `task13._bucket_assign`, cap `MAX_CATEGORIES = 5` | `task30.split_by_attribute`, cap `MAX_CATEGORICAL_GROUPS = 4` |

A typo'd `compare_attribute` makes `split_by_attribute` return
`group_labels = None`, which renders an empty-state SVG with no error. The merged
slot keeps `attribute_set`'s behaviour; single-attribute tasks pass a list of one.

### The picker has three classes, and only one applies at a time

An attribute is selectable at three levels, and they are different analyses
rather than three lists to merge. `trace_features.attribute_params()` declares
the selector and one picker per class; `selected_keys(params, log)` resolves
whichever is active into feature keys, and `validate_attribute_class` refuses a
selection that spans two.

| class | what it offers | source | groups traces by |
|---|---|---|---|
| **trace** | one value per case — a case attribute, or an event-level one aggregated | `log.candidate_attributes` | a case-wide value |
| **event** | "at activity X, attribute Y = Z", as yes/no per trace | `log.event_conditions` | what happened at one named step |
| **log** | one value for the whole log | `log.log_attributes` | nothing — every trace lands in one group |

The **event** class exists because the cross product of activities, attributes
and values is a catalogue, not a feature set: enumerating it as trace features
would add hundreds of entries nobody asked for. The candidates instead come from
the log ranked by trace coverage, the admin names the ones worth asking about,
and each becomes an ordinary boolean feature (`at::Check Credit|decision|rejected`)
that the existing panels draw like `contains::X`. Conditions every trace
satisfies, or none does, are left out — on BPIC12 that removes the four most
frequent ones, all variants of "A_SUBMITTED was executed by resource 112".

The **log** class groups nothing by construction. It is offered because a log
*can* carry a meaningful attribute, and a task selecting one is asking for the
log as a single annotated group; most logs carry only export metadata, and then
the picker is empty and the page says so.

### One canonical reading per attribute

One raw column yields several features — an amount has a final value, a mean, a
maximum and a sum — and a picker listing them all equally makes the admin choose
an aggregation before they have chosen an attribute. Each family marks one
`Feature.primary`: the picker lists it first and an empty selection falls back to
exactly those (`default_keys`).

| attribute | canonical | also offered |
|---|---|---|
| event-level numeric (amount, score, cost) | `::last` — the value the process left behind | `::mean` `::max` `::sum` |
| event-level categorical (decision, result) | `::last` | `::mode` |
| `org:resource` | `resource::dominant` — who did most of the case | `resource::first` `resource::last` `resource::n_distinct` |
| activity | `contains::X` — did it happen | `count::X`, first/last activity |
| timestamp | `__throughput_hours__` | `__start_time__` |
| constant within every trace | the attribute itself, no suffix | — |

`::last` rather than `::mean` for numbers is deliberate: an event-level number is
usually a state the process rewrites, and a mean over rewrites answers no
question anyone asks. `::sum` is there for the additive ones (cost), which no
rule can tell apart from the state-like ones by name.

### What the picker refuses to offer

The registry's own rule is that cardinality never gates *availability* — a
61-value resource is a feature and the split strategy deals with it. A picker is
a different question, so `trace_features.offerable` filters two kinds of entry
that cannot answer "how does this relate to violations":

* **one distinct value** — every trace in one group;
* **a categorical with about one value per trace** — an identifier, whose buckets
  are singletons plus a huge "Other". Numeric and ordinal features are exempt:
  quantiles and calendar periods cope with any number of values, and throughput
  time (one value per trace) is the most useful feature in the set.

The same rule applies to the flattened value candidates: BPIC12's `REG_DATE`
turned `log.attribute_values` into **148 503 checkboxes** before it was applied.
Numeric attributes are left out of that list too — a data rule over a number is a
range ("amount ≤ 10000"), which a conformant *set* cannot express. That is an
open gap, not a decision: BPIC12's only data attribute is numeric, so its data
perspective now correctly offers nothing at all.

Long lists are a UI problem as well as a data one. The `select-many` widget
renders one checkbox per candidate in a scroll box, so it gained a filter field
(shown past 12 options, selected entries always visible); candidate lists are
capped at `MAX_PICKER_CANDIDATES = 200`, ranked by trace coverage.

---

## Slot 2 — response

`RESPONSE_MEASURE` is declared per task module like `IDIOMS`, not offered in
`PARAM_SPEC`: the wording of a task fixes what it measures, so letting an admin
change it would make the task's own question wrong.

```
response_measure   fitness | violation_rate | patterns
```

| Measure | Definition | Source |
|---|---|---|
| `fitness` | **mean fitness per group**, continuous. No conformant/non-conformant cut. | `fitness_summary_dataframe` |
| `violation_rate` | share of traces with **≥ 1 violating step**. Threshold-free. | violation table |
| `patterns` | the violations themselves, per group | `_build_violation_df` |

`violation_rate` is defined from the violation table, not from a fitness cut, so
it stays invariant to slot 3 and stays consistent with `patterns` (same source).
The trace-level violating flag must be computed **before** the tau/activity
filter, so that a trace deviating only on hidden transitions is not counted as
conformant while its fitness is below 1.

"% conformant" is **not** a response. Removing it is what lets slot 3 disappear
from most tasks.

Violation types are alignment-based control-flow only: Move on Model, Move on
Log, Mismatch Move. Data guards, resource SoD and time SLAs are out of scope as
violations — they may still appear in slot 1 as grouping features.

---

## Slot 3 — threshold

```
conformant_threshold   float   only where a conformant/non-conformant cut is still shown
pattern_top_n          int     only when response_measure = patterns  (replaces TOP_N = 10)
```

"Conformant" used to mean two things inside one class: `io_helpers.is_fit`
cut at `fitness >= 1.0` (task01, task30) while `_FIT_THRESHOLD = 0.8` was
written out separately in task15, task16, task22 and task33, so a trace at 0.9
was conformant in one task and not in another. Dropping "% conformant" as a
response removed the cut from task15, task16, task22 and task33 entirely.
task01 keeps it — a binary split is its point — and it is now the
`conformant_threshold` parameter, defaulting to 1.0. The remaining
`_FIT_THRESHOLD` constants in task15 and task33 only position reference lines on
fitness charts; they no longer decide any reported number.

---

## Per-task exposure

`RESPONSE_MEASURE` and `SPLIT_STRATEGY` are module constants; the rest are
`PARAM_SPEC` entries carrying a `slot`. A strategy fixed in code is not offered
to the admin, and the group cap is dropped where it cannot apply (a binary cut
has no cap).

| task | feature picker | `SPLIT_STRATEGY` | `RESPONSE_MEASURE` | other slots |
|---|---|---|---|---|
| task01 | `outcome_activity` | `binary` | fitness | `missing_policy`, `conformant_threshold` |
| task07 | `time_granularity` | `ordered_bins` | fitness | `group_cap`, `missing_policy` |
| task13 | `attribute_set` | admin | violation_rate | `split_strategy`, `group_cap`, `missing_policy` |
| task15 | `attribute_set` | admin | fitness | same |
| task16 | `attribute_set` | admin | violation_rate | same |
| task20 | `attribute_set` | admin | violation_rate | same |
| task21 | `attribute_set` | admin | violation_rate | same |
| task22 | `compare_attribute` | admin | fitness | same |
| task30 | `compare_attribute` | admin | patterns | same + `pattern_top_n` |
| task33 | `compare_attribute` | admin | fitness | same |

All ten are wired. task15 and task16 were converted from whole-log views to
attribute splits, which means their panel idioms (table, bar chart, table+bar,
parallel sets) now render the same kernel as task20's through the same
renderers, differing in wording and in the idioms each keeps. Their model and
per-trace idioms stay log-level: a BPMN annotated with overall violations has no
per-bucket form.

`attribute_set` is multi-select everywhere except task30, which keeps a single
`compare_attribute`. Not an oversight: its response is `patterns`, whose panel is
a pattern-by-group matrix rather than one value per bucket, so it needs a panel
shape the shared renderers do not have. Every other task in the class analyses
as many attributes as the admin selects, one panel each.

The consequence is deliberate but worth restating for experiment design: task16
and task20 now draw the same thing, as do task15, task22 and task33. A class is
the sampling unit — drawing two members into one study shows a participant the
same chart twice.

---

## Defect: the default set read the first event as the case value

`task13.discover_candidate_attributes` scanned raw log keys and asked
`task30._trace_attribute_value` for each trace's value. That helper tolerates
"case attribute replicated onto every event" by falling back to `trace[0][key]` —
and cannot tell that apart from an attribute that genuinely varies within the
trace. So for **every** event-level attribute it returned the first event's
value and called it the case value.

On BPIC12 that made `org:resource` look constant at 112 — the automatic
submitter of the first event — in all 13 087 traces. The column had no variance,
so it was dropped, and the log's 61 executors were never analysed by any task in
the class. The documented fallback ("otherwise the event-level values are
aggregated per trace — numeric by mean, categorical by mode") was unreachable for
any attribute present on the first event.

`discover_candidate_attributes` now delegates to `trace_features.default_keys`,
which decides case-level vs event-level by constancy and derives named features
for the ones that vary. The default set on BPIC12 went from `['AMOUNT_REQ']` to
`AMOUNT_REQ`, `resource::dominant`, `__throughput_hours__` and eight
`contains::` features. `task20._EXCLUDE_ATTRIBUTES`, which dropped `org:resource`
from four of the nine tasks and not the other five, is gone with it: the same
picker, the same log and the same empty selection now give every task the same
default set.

`label_for` was carrying a stray copy of `extract`'s conformance branch — it
referenced arguments the function does not have, so `label_for(CONFORMANCE_KEY)`
raised NameError instead of returning a label. It is a pure key → string
function again.

## Defects addressed

1. **Fixed — attribute key discovery reads every trace.** `trace_features`
   scans all traces for keys; the old first-trace scan survives only in
   `task13._available_attributes`, which now feeds the default set alone.
   Previously:
   `_available_attributes` unions `log[0].attributes` with `log[0][0].keys()`.
   Value collection is full-log, so the risk is a key that never gets
   discovered — real for XES logs where event attributes vary by activity, not
   an issue for CSV logs (fixed column set).

2. **Fixed — one path for event-level attributes.** `trace_features.extract`
   raises rather than silently taking the first event's value, and
   `_build_evidence_frame` goes through it. Previously:
   `_trace_attribute_value` falls back to `trace[0][key]`, so an event-level
   attribute present on the first event is silently treated as case-level and
   reduced to the first value — the remaining events are never read. task20's
   feature frame instead always aggregates all events by mean and max. task13,
   task16 and task21 take the first path; task20 takes the second.

3. **Fixed — one `_group_stats`.** All four delegate to
   `trace_response.fitness_stats`, verified value-for-value. Previously: task01 (`_task01_group_stats`), task22,
   task30 and task33 each implement per-group conformance stats separately, with
   the threshold disagreement noted under slot 3.

4. **Fixed — `count_level` is explicit.** Ranking and per-group columns now
   count the same way, defaulting to traces. The two coincided on BPIC12-A
   (no trace repeats a pattern), so this was latent. Previously: `total` counts violation
   *occurrences* (step-level, not deduped) and drives the top-N ranking, while
   `{g}__count` counts *traces*. So `total ≠ Σ {g}__count`, and the pattern
   ranked first is not necessarily the one affecting the most traces.

5. **Fixed — `activity` and `move_type` are columns.** Previously: `pattern` is
   `f"{activity} ({moveType})"`, so activity and move type cannot be used as
   independent axes without parsing the string back apart. Split into two
   columns; keep `pattern` as a display label.

6. **Fixed — `missing_policy`.** Previously, `_build_violation_df` silently
   dropped traces with a missing attribute value (`assignment[i] is None`) — they leave every group and every
   denominator with no indication. Hence `missing_policy` in slot 1.

7. **Fixed — no key-name exclusions.** `_EXCLUDE_ATTRIBUTES` is gone and the
   identifier filter is by cardinality, not by name. Previously:
   `task20._EXCLUDE_ATTRIBUTES` applies in `_default_attributes`, but the admin
   picker calls `task13.discover_candidate_attributes`, which does not exclude
   it — so it is already selectable today. Lifting the exclusion changes the
   no-selection fallback and nothing else. Its real problem is cardinality (61
   distinct values in BPIC12, bucketing to top-4 + "Other"), which belongs to
   `split_strategy`, not to whether the feature is offered.

8. **Mostly fixed.** `_auto_detect_compare_attribute` no longer falls back to a
   BPIC12 column (it returns None and warns), `REG_DATE` and the dead
   `CANDIDATE_ATTRIBUTES` / `_OUTCOME_ACTIVITY` constants are gone, and task15
   and task16 lost their dead `compare_attribute` parameters. Still open:
   `task31._OUTCOME_ACTIVITY`, which `_task31_positive_outcome_from_trace` reads
   unconditionally, and the CLI defaults. Original list: These change behaviour when no explicit parameter
   is passed and must be removed, not re-defaulted:
   - `create_all_visualizations.py:727` `_auto_detect_compare_attribute(log, "AMOUNT_REQ")` — the fallback is the bug
   - `create_all_visualizations.py:768-769` `run_pipeline(outcome_activity="Activate Care", compare_attribute="AMOUNT_REQ")`
   - `task13.py:281` `"REG_DATE"` inside `_NON_CANDIDATE_KEYS`
   - `task16.py:635`, `task19.py:188`, `task22.py:504`, `task32.py:451` — same two defaults
   - CLI defaults: `create_all_visualizations.py:873,877`, `generate_all_local.py:79-80`

9. **Fixed — caps are parameters.** `group_cap` and `pattern_top_n` are
   admin-settable; `split()` defines a cap as named groups before "Other",
   ending the disagreement between the two constants. Previously: top-14 activities and top-6
   attributes (task20), `MAX_CATEGORIES = 5` (task13),
   `MAX_CATEGORICAL_GROUPS = 4` (task30), `TOP_N = 10` (task30). The two group
   caps count different things — real groups vs total buckets — and happen to
   produce the same result today.

---

## Regression baseline

The three tuned idioms in the running experiment are task20's `bar_chart`,
`table` and `matrix`, over a dataset with `customer_segment`
(returning / new / premium) and `region` (Germany / International) — two
categorical attributes, 3 and 2 buckets. That dataset is **not in the repo**;
only BPIC12 copies are. Every task20 SVG checked into the repo predates the
current code (Jun 13 / Jul 12 / Jul 26 vs task20.py on Sep 9) and does not match
it — the committed `bar_chart` still draws sample-size labels and the committed
`matrix` still uses a per-cell gradient with a colourbar.

None of the changes above touch those three idioms, with one condition: task20
must have `attribute_set` set **explicitly**. With a non-empty
`attribute_set`, `_default_attributes` never runs and `_EXCLUDE_ATTRIBUTES` is
irrelevant; left empty, lifting the exclusion could add a third panel and change
all three images. Freezing the current value explicitly closes this regardless.

---

## Open issue: empty attribute picker, empty panels

Observed on the live platform after the first deploy of this work, on a dataset
carrying `customer_segment` and `region`. Two symptoms, almost certainly one
cause:

1. `/specify` shows no dropdown for `attribute_set` — the picker renders
   "No candidates available for this dataset yet."
2. Some idioms render the empty state **"No candidate attribute could be
   bucketed."**

### Why they are the same failure

```
picker empty            →  the admin cannot select anything
                        →  attribute_set stays []
                        →  generate() falls back to _default_attributes(log, feat)
                        →  that also returns nothing
                        →  attribute_panels() returns []
                        →  every panel idiom renders the empty state
```

Both ends read the same features. The picker goes through
`get_log_candidate_attributes` → `trace_features.discover_features`; the
fallback goes through `task20._default_attributes` →
`task13.discover_candidate_attributes`. **These are still two different paths**
— unifying them is the remaining half of defect 7 — so a dataset that defeats
one may or may not defeat the other, and confirming both are empty is itself
diagnostic.

### What has been ruled out

Tested against BPIC12-A, which behaves correctly:

| | |
|---|---|
| the function itself | returns 29 rows through the admin import path, JSON-serialisable |
| speed | `discover_features` takes 0.1 s over 13,087 traces / 60,849 events |
| deployment | `trace_features.py` and `trace_response.py` are on `origin/develop`; `COPY ./ProViBackend` takes the whole tree and neither file is ignored |
| the pipeline | CI/CD completed successfully |
| the front end | it handles `select-many`, and reaches the empty-state branch only when `options.length === 0` |

So the cause is specific to that dataset, or to the request rather than the code.

### How to tell which

A later commit made the failure self-reporting: the param-spec endpoint returns
`options_error`, and `/specify` prints it under the empty-state line.

| What the picker shows | Meaning |
|---|---|
| an exception, e.g. `FileNotFoundError: …` | enumeration raised; the message names the cause |
| `'log.candidate_attributes' returned nothing for this dataset.` | enumeration ran and the dataset genuinely yields no feature |
| the empty-state line with no red text | `dataset_id` reached the endpoint empty — the task instance has no dataset bound, so candidates were never enumerated |

The third case is worth checking first: `/specify` sends
`dataset_id=${ti.dataset_id || ""}`, and the endpoint skips enumeration
entirely for an empty value.

### If the dataset is the cause

The likely candidates, in the order worth testing:

* **Timestamps that are not datetimes.** `_time_features` subtracts them; a log
  whose `time:timestamp` survived as text would raise, and the exception would
  take the whole feature list with it, not just the two time features.
* **An empty log.** `discover_features` returns `[]` for a log of no traces, and
  `_resolve_dataset_paths` would have raised earlier only if the files were
  missing, not if the log parsed to nothing.
* **Attributes present only as case attributes with no events carrying them.**
  Handled, but worth confirming against the real file.

The fastest way to settle it is to put that dataset's `EventLog.csv` beside the
BPIC12 copies and run `discover_features` over it directly.
