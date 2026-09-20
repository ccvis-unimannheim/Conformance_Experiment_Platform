# Trace-alignment parameters

The parameter reference for **task04 (trace level), task09, task14, task27,
task28, task34** and **task35** — the tasks whose figures are the alignment of
individual traces. [TRACE_ALIGNMENT_CLASS.md](TRACE_ALIGNMENT_CLASS.md) explains
why the class exists and what changed; this file is what each parameter means
and how they fit together.

Code: `provibackend/ProViBackend/scripts/trace_alignment.py` declares every
entry below; each task assembles its own `PARAM_SPEC` from them and the pipeline
threads them through `make_task_generators` in
`scripts/create_all_visualizations.py`.

---

## 1. The model: three questions, three families

An admin configuring one of these tasks answers three questions, and each
parameter belongs to exactly one of them. Keeping them separate is the point —
a parameter that answers two questions at once ends up fighting itself.

| Question | Parameters | Affects |
|---|---|---|
| **Which traces are shown?** | `trace_selection_mode`, `trace_ids`, `trace_pick_rule`, `trace_count` | selection only |
| **What counts as a violation?** | `perspective`, `violation_pattern`, `data_attribute` + `conformant_values`, `conformant_resources` + `scoped_activity`, `conformant_threshold` | selection **and** what the figures draw |
| **What is drawn at all?** | `analysis_level` (task04), `move_types` (task35) | which pipeline runs |

The second family is the subtle one. It defines the guideline, so it decides
both which traces are worth showing *and* how each step is coloured or labelled.
That is why those parameters stay visible when the traces are named by hand,
while the first family's do not.

---

## 2. Which traces are shown

### `trace_selection_mode` — `auto` (default) or `manual`

Whether a rule picks the traces or the admin names them. Everything else in this
family is conditional on it, so /specify shows one path at a time rather than a
picker and a rule that quietly disagree.

### `trace_ids` — visible under `manual`

Case ids from `log.trace_ids`, used **in the order given**; the first becomes
"Trace 1". Ids absent from the log are skipped. An empty list under `manual` is
not an error — it falls back to the rule rather than rendering an empty figure.

A `trace_ids` value saved before this class existed is still honoured even
though no mode was saved with it: only an explicit `auto` discards a saved list.

### `trace_pick_rule` — visible under `auto`

Which rule picks. Each task offers only the rules that mean something for it
(§6), and its default is the rule it applied in code before the parameter
existed. **Two filters apply before any rule ranks anything:**

1. **One trace per distinct activity sequence.** Identical traces have identical
   fitness and sort adjacent, so without this `worst_fitness` returned the same
   chevron strip two and three times over.
2. **Only traces that violate the guideline** — as defined by the second
   parameter family, in the current perspective. Without this, `violation_gap`
   picked a fully conformant trace as one of its two, and a data-perspective
   task could show traces whose attribute value was perfectly conformant.

If nothing violates at all, the second filter lifts and a warning is logged: a
fully conformant log is a finding, not a failure.

| Rule | What it returns |
|---|---|
| `violation_gap` | Traces spread across the violation counts present, both ends always included: at three traces, counts 3, 2 and 1. Within one count the trace touching the most distinct activities wins, so the strips stay substantial. Fewer distinct counts than traces asked for → topped up from the most-violating end. |
| `worst_fitness` | Most violations first, then lowest fitness. In a data or resource perspective every trace has the same alignment fitness, so the violation count is what ranks them at all. |
| `first_nonconformant` | The violating traces in log order. |
| `most_frequent_variants` | The most frequent activity sequences, most frequent first — still only the violating ones, which the option's label now says too ("The most frequent variants that violate the guideline"). The other three read as violation rules by themselves. |

There is no "conformant and non-conformant in equal number" rule: that is
task27's whole question rather than one way of answering it, so task27 has no
rule picker at all (§6).

### `trace_count` — visible under `auto`

How many traces the rule picks. The maximum is a legibility cap, not a technical
one: each trace is a chevron strip and a BPMN panel stacked in one figure, and
past four the panels are too short to read. task14 has no such parameter — its
wording ("a given trace") fixes it at one, and a control whose only legal value
is 1 reads as a choice that is not there.

**task27 reads it per status**: 2 means two conformant and two non-conformant.

### There is no trace-vs-variant unit

Deduplication by activity sequence already means every rule returns one
representative per variant, so a "variants instead of traces" switch changed no
figure. "The most frequent variants" survives as a rule.

---

## 3. What counts as a violation

### `perspective` — task09 and task28 only

`control-flow` (default), `data` or `resource`. Their wording is the only one
that admits more than the control flow: *"this can relate to different
control-flow relations, but also resource and data constraints"*.

* **control-flow** — a violation is a non-synchronous alignment move. The
  figures colour by move type (Synchronous / Model Move / Log Move).
* **data** — a violation is an attribute value outside the conformant set. The
  chevron turns neutral and carries the value, the model colours by verdict, and
  the table reads `prescribed → executed`.
* **resource** — the same, judged on `org:resource`.

Every other task in the class is control-flow only.

### `violation_pattern` — control flow

An `activity | move type` pair from `log.violations` (e.g. `Confirm Order · Log
Move`). It **defines the guideline** for the control-flow perspective: with one
named, a trace violates iff its alignment contains that pattern, and every rule
ranks on that count. Empty keeps the older meaning, that any deviation counts.

Two things follow from it deciding selection *and nothing else* — the figures
colour by move type whatever is named:

* it is hidden under `manual`, where no rule reads it;
* in `violation_gap` its filtering job and its counting job are **split**. A
  pattern occurs at most once per trace in practice, so counting it leaves every
  qualifying trace on 1 and the spread axis collapses to a point. The pattern
  keeps the filter; the axis falls back to the perspective's own violation count
  whenever the pattern leaves every trace on the same number.

It supersedes task34's `violated_activity`, which named an activity and left the
move type open — "Confirm Order" meant a skipped one and an inserted one at once
— and which only the worst-fitness rule honoured. A saved `violated_activity`
still narrows that task's selection; it is no longer offered.

### `data_attribute` + `conformant_values` — data perspective

The attribute under scrutiny, and the values that count as conformant; any other
value is a violation. Both stay visible under a manual selection, because they
are the verdict the figures draw rather than a condition on the selection.

`conformant_values` is a **flat** `attribute = value` list over the whole log,
not the chosen attribute's own values: /specify bakes each parameter's options in
once per dataset and cannot re-fetch them when another parameter changes, so a
dependent picker would be built before the attribute is known and render empty.
`validate_params` rejects a selection spanning two attributes.

### `conformant_resources` + `scoped_activity` — resource perspective

The resources allowed to execute a step, and optionally the single activity the
rule applies to (empty = every activity). Activities outside the scope are
`n/a`, not violations — colouring them as violations would invent findings, as
would colouring a step with no event behind it (a skipped activity has no
executor).

A log without `org:resource` enumerates no candidates, and /specify reports that
the source returned nothing for this dataset — the honest answer: this
perspective cannot be asked of such a log.

### `conformant_threshold` — task27 only

The fitness at or above which a variant counts as conformant (default 1.0 —
perfect conformance, which is what the code assumed before the parameter
existed). Conformant vs non-conformant *is* task27's question, which is why only
task27 has this cut; everywhere else a violation is a non-synchronous move and
needs no threshold.

It stays visible under a manual selection, unlike `violation_pattern`, because
it keeps deciding what the figures say after the traces are named: the bar chart,
parallel sets, matrix, heatmap, stacked bar and box plot all colour and label
their rows Conformant / Non-conformant by it, whether those rows are the named
traces or the log's variants.

Which rows they are depends on the mode. **Named traces reach every idiom** — one
row per trace, labelled `Trace 1..N` exactly as the move table labels them.
**Under the automatic rule the frequency and distribution idioms keep aggregating
over the log's variants** (top 15), because that rule picks one trace per status
by default and a box plot of one value per group has no distribution to show.

---

## 4. What is drawn at all

### `analysis_level` — task04 only

`trace` (default) or `log`. Task 4 is asked at two levels and they are different
pipelines, not two views of one: at log level the log is split into sub-logs and
their conformance compared, which is task01's question and task01's figures, so
task04 delegates to `task01.generate` rather than keeping a second copy of it.
`outcome_activity` is that level's split condition; the whole trace-level block
is hidden there, and vice versa.

### `move_types` — task35 only

Which deviation types get annotated on the model (empty = all). task35 keeps
aggregating over the whole log; it is in this document because it shares the
class's vocabulary, not its selection.

---

## 5. How they interact

Precedence and gating, in one place:

1. **A named trace wins over a rule.** With `trace_ids` non-empty the rule,
   count and pattern are not read at all.
2. **`perspective` gates the guideline parameters.** The control-flow pattern is
   hidden outside `control-flow`; the data and resource rules are hidden outside
   their own perspective.
3. **The guideline decides both the selection and the drawing** — except
   `violation_pattern`, which decides only the selection, and is hidden under a
   manual one for exactly that reason.
4. **`conformant_threshold` is independent of the selection** and always applies.
5. **Nothing silently renders an empty figure.** No violating trace → the filter
   lifts with a warning; no trace at all → the task falls back to its whole-log
   figures (task09, task28) or its empty state.
6. **/specify requires every condition of a `visible_if` to hold**, so a task
   merges its own condition onto the class's rather than replacing it —
   `violation_pattern` in task04 is visible only at trace level *and* under an
   automatic selection.

---

## 6. Per task

| | task04 | task09 | task14 | task27 | task28 | task34 | task35 |
|---|---|---|---|---|---|---|---|
| `analysis_level` | ✓ (trace) | | | | | | |
| `outcome_activity` | log level | | | | | | |
| `perspective` | | ✓ | | | ✓ | | |
| `trace_selection_mode` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| `trace_ids` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| `trace_pick_rule` | gap / worst / frequent (gap) | + first (gap) | worst / first / frequent (worst) | — | all four (first) | worst / first / frequent (worst) | |
| `trace_count` | 2–4 (2) | 1–4 (2) | — | 1–3 (1), per status | 1–4 (1) | 1–4 (1) | |
| `violation_pattern` | ✓ | control flow | ✓ | | control flow | ✓ | |
| data / resource rules | | ✓ | | | ✓ | | |
| `conformant_threshold` | | | | ✓ (1.0) | | | |
| `move_types` | | | | | | | ✓ |

Defaults in parentheses. task34 also still accepts a saved `violated_activity`.

---

## 7. Validation

`validate_params(log, params)` runs before generation and hard-fails it. Beyond
the generic check that every selected id exists in the dataset:

| Task | Rule |
|---|---|
| all | manual selection within the task's min/max; `trace_count` within range |
| task04 (log level) | `outcome_activity` required, and present in *some but not all* traces — an activity every trace contains puts them all in one group |
| task04 (trace level) | at least two traces |
| task09, task28 (data) | `data_attribute` required; at least one conformant value; every selected value belongs to that attribute |
| task09, task28 (resource) | at least one allowed resource |
| task14 | exactly one trace |
| task27 | `conformant_threshold` a number in 0–1 |

---

## 8. What the participant sees

Every selection parameter carries `hide_hint: True`. Which traces are shown is
visible in the figure itself, and repeating it in the question wording only tells
the participant where to look.

The guideline parameters are the opposite — `perspective`, `violation_pattern`,
`data_attribute`, `conformant_values`, `conformant_resources`,
`scoped_activity`, `conformant_threshold` are what the question *is*, so they
stay in the participant-facing wording.

---

## 9. Where the candidates come from

`source` populates a picker from the dataset; the enumerators live in
`create_all_visualizations.py` and are cached per dataset in `admin.py`.

| Source | Yields |
|---|---|
| `log.trace_ids` | every trace as `case id — fitness 0.812`, with a variant index for the picker's "one per variant" checkbox |
| `log.violations` | `activity · move type (N traces, X%)` pairs, most covered first |
| `log.activities` | distinct activity names |
| `log.data_attributes` | attributes a data rule can be written about, with their cardinality |
| `log.attribute_values` | flat `attribute = value` pairs over the whole log |
| `log.resource_values` | distinct `org:resource` values |

---

## 10. Adding a task to the class

1. Assemble `PARAM_SPEC` from `trace_alignment.selection_params(...)` plus the
   guideline parameters the task's wording admits. Do not re-declare an entry
   with a different label: the point of the module is that six tasks cannot
   drift.
2. `validate_params` = `trace_alignment.validate_selection(...)` plus
   `validate_perspective(...)` if the task has a perspective.
3. Select with `trace_alignment.select_records(...)`, which applies both filters
   and annotates the value verdicts.
4. Draw with task04's renderers (control flow) or
   `trace_alignment.draw_value_*` (data, resource), passing your own `filename`.
   The figure belongs to the class, not to the task.
5. Thread every parameter through `make_task_generators` — that function is the
   single source of per-task `generate()` signatures, and a parameter that
   reaches no drawing does not belong in `PARAM_SPEC`.
6. Regenerate a dataset and compare with `tools/svg_diff.py` before and after;
   name every figure that changes.
