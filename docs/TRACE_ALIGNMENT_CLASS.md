# Trace alignment: what the class shares

Scope: **task04 (trace level), task09, task14, task27, task28, task34** — the
tasks whose figures are the alignment of individual traces rather than an
aggregate over the log — plus **task35**, which annotates the same violations on
the model and is trimmed to that one idiom. The third class document, after
[TRACE_FEATURE_REGISTRY.md](TRACE_FEATURE_REGISTRY.md) (Attribute → Violation)
and [VIOLATION_PROFILE_CLASS.md](VIOLATION_PROFILE_CLASS.md).

---

## What was wrong

Six tasks showed the alignment of a few traces, and each picked those traces its
own way, with the rule buried in code and nothing an admin could change:

| task | how it picked | where |
|---|---|---|
| task04 | the two traces with the largest fitness gap | `_task04_select_compare_traces` |
| task14 | the highest-alignment-cost trace | `_pick_representative_trace` |
| task27 | the first three variants either side of `fitness == 1.0` | `task27_flow_chart_and_table` |
| task28 | the first trace with `fitness < 1` | `pick_representative_trace_index` |
| task34 | the most-violating, then worst-fitness trace | `_build_contexts` + `_pick_ctx` |

Those are good defaults. They were not choices. The rules now live in one
vocabulary — `trace_alignment.PICK_RULES` — and each task offers the subset that
means something for it, with its historical rule as the default.

task09 and task28 had a second problem: the task text asks about "control-flow
relations, **but also** resource and data constraints", and both tasks could only
ever answer the control-flow half.

## The shared parameters

`scripts/trace_alignment.py`, imported by the six tasks:

| key | what it decides | who declares it |
|---|---|---|
| `trace_selection_mode` | admin names the traces, or a rule picks them | all six |
| `trace_ids` | which traces (manual mode) | all six |
| `trace_pick_rule` | which rule (auto mode) | all but task27 |
| `trace_count` | how many the rule picks — for task27, how many *of each status* | all but task14 |
| `violation_pattern` | which violation defines the guideline (control flow) | task04, task09, task14, task28, task34 |
| `analysis_level` | log level vs trace level | task04 only |
| `perspective` | control-flow / data / resource | task09, task28 |
| `data_attribute`, `conformant_values` | the data rule | task09, task28 |
| `conformant_resources`, `scoped_activity` | the resource rule | task09, task28 |
| `conformant_threshold` | where conformant stops | task27 only |

`visible_if` keeps each branch's parameters out of sight at the other: /specify
requires *all* of an entry's conditions, so task04's selection block carries both
`{analysis_level: trace}` and its own mode condition.

**Participant-facing wording.** Every selection parameter is `hide_hint: True` —
which traces are shown is visible in the figure, and repeating it in the question
only tells the participant where to look. The perspective and the conformant
values are the opposite: they *are* the question, so they stay visible.

### Why the threshold is on task27 alone

Conformant vs non-conformant *is* task27's question, and it was hard-coded at
`fitness >= 1.0` in `_status`. Everywhere else in this class a violation is a
non-synchronous move, which needs no cut — so task01's `conformant_threshold`,
which reached no drawing at all (`_task01_group_stats` took it, but
`task01.generate` never passed it), is gone rather than propagated.

task27's threshold is threaded as an explicit argument through the eleven
renderers that read it. A module-level default would have been one line, but
generation can run for two experiments at once and a mutable module global would
let one experiment's threshold decide the other's figures.

## Picking traces that have something to show

Every rule applies two filters before it ranks anything, because without them
each rule could select a trace that answers nothing:

1. **One trace per distinct activity sequence.** `worst_fitness` returned the
   same strip two and three times over — identical traces have identical
   fitness, so they sort adjacent.
2. **Only traces that violate the guideline in the current perspective.**
   `violation_gap` picked a trace with fitness 1.0 and no deviation at all as
   one of its two; `first_nonconformant` and `worst_fitness` ranked by
   *control-flow* deviation even when the task was asking about a data or
   resource rule, so task09 in the data perspective could show two traces whose
   attribute value was perfectly conformant. `trace_alignment.violation_count`
   counts violations **in `view`**, and the rules rank on that.

If nothing violates at all, the filter lifts rather than leaving the figure
empty: a fully conformant log is a finding, not a failure.

### What defines "the guideline"

In the data and resource perspectives the admin's conformant values define it.
The control flow had no such definition — every rule counted *any* deviation, so
a task asking about one specific violation still ranked traces by their
unrelated ones. `violation_pattern` (an `activity | move type` pair from
`log.violations`) supplies it: when set, a trace violates iff its alignment
contains that pattern, and every rule ranks on that count. Empty keeps the old
meaning, any deviation.

It supersedes task34's `violated_activity`, which named an activity and left the
move type open — "Confirm Order" meant a skipped one and an inserted one at
once — and which only the worst-fitness rule honoured. A `violated_activity`
saved by an existing experiment still narrows that task's selection; it is no
longer offered.

task27 does not get it: `conformant_threshold` already defines conformance
there, and two parameters deciding one thing is what this class exists to
prevent.

The pattern decides which traces are *picked* and nothing else — the figures
colour by move type whatever is named — so it is hidden when the admin names the
traces themselves. `conformant_threshold` is not: ten of task27's idioms colour
and label whole-log variants by it, so it keeps working when the selection is
manual. Neither are the data and resource rules, which are what the figures draw
a verdict from.

### How `violation_gap` generalises past two traces

At two traces it is the most- and the least-violating trace, which is what the
name plainly means. Above two it used to be those two extremes plus whatever had
the widest activity coverage — at four traces it returned violation counts of
3, 1, 1, 1, three of which compare nothing.

The distinct violation counts present in the pool are now the axis, and the
traces taken are evenly spaced along it with both ends always included: four
traces come back as 3, 2, 1 and whatever the fourth step lands on. Within one
count the trace touching the most distinct activities wins, so the strips stay
substantial. When the log holds fewer distinct counts than traces asked for, the
rest are topped up from the most-violating end rather than repeating a count's
representative.

**There is no "trace or variant" unit parameter.** With the deduplication above,
picking "variants" instead of "traces" changed no figure — each rule already
returns one representative per activity sequence — and "the most frequent
variants" is a rule of its own. It was a control that decided nothing.

## The three figures

A task in this class draws the same trio, so a participant who has read one can
read the others:

| | control-flow | data | resource |
|---|---|---|---|
| chevron | move type per step | value verdict per step, value named beside the trace | executor verdict per step |
| BPMN | model coloured by move type, log moves as external badges | model coloured by value verdict | model coloured by executor verdict |
| table | activity × trace → move type | activity × trace → prescribed vs executed value | activity × trace → prescribed vs executed resource |

The control-flow trio is **task04's renderers**, called by task09, task14,
task27, task28 and multi-trace task34 with nothing but a different `filename`.
This follows task23→task11: the figure belongs to the class, not to the task, and
five copies of one comparison is what the class exists to prevent. The data and
resource trio is `trace_alignment.draw_value_*`.

A violation in the data/resource perspective is a **value mismatch**, not an
alignment move: the admin names the values that count as conformant and anything
else is a violation. A step with no event behind it (a skipped activity) and,
under a scoped resource rule, every activity the rule does not cover are `n/a` —
not violations, because colouring them as such would invent findings.

### Why the conformant values are a flat list

`/specify` bakes each parameter's options in once per dataset and cannot re-fetch
them when another parameter changes. A value picker that narrowed itself to a
separately-chosen attribute would therefore be built before the attribute is
known, and render empty. So `log.attribute_values` enumerates every
`attribute = value` pair in the log and `validate_params` rejects a selection
that spans two attributes. Making /specify re-fetch dependent options is the real
fix and is not done here.

## The pictures in Context_0209 are not this pipeline's output

`Context_0209/Picture 13–15` and `22–24` were treated as frozen stimuli that no
change may move. They are not what the pipeline emits: Picture 13's Trace 1 is a
four-step trace whose `Confirm Order` is a log move, while the code selected a
seven-step trace with fitness 1.0 and no deviation at all. Both of Picture 13's
sequences do exist in this log (17 traces at fitness 0.857, and index 55 at
0.571), so the figure came from this dataset — under a selection rule the code no
longer contains.

Published stimuli are pinned outside the pipeline instead, by downloading the
generated idiom image and uploading it back as a fixed asset. That is what makes
a stimulus stable; byte-identical regeneration never could, for the reason in the
next section.

The rules below still hold — a change should not move a figure *by accident* —
but they are no longer a reason to keep a defect:

1. **Shared renderers only gain keyword arguments whose defaults are the current
   behaviour** (`filename=`, `title=`, `threshold=`).
2. **Every step is checked by regenerating the whole dataset and comparing all
   262 SVGs against a baseline**, so a difference is always a deliberate one
   that can be named.

Against the baseline the class now differs in fifteen files, all accounted for:
task04's eight, because its selection no longer includes a conformant trace;
task09's and task28's chevron, BPMN and table, which move from log-aggregate to
trace-level; and task27's table, which now shows the traces it selected rather
than the top fifteen variants.

### Comparing SVGs needs normalising first

A plain `diff` reports ~238 of 262 files as changed when nothing has: matplotlib
stamps a `<dc:date>` and mints a fresh random id per process for every clip path,
marker definition and rasterised image (`pb7467015c3`, `image8bd634ecf3`,
`C0_0_a2a0687d4c`), and task09/task35 embed a whole SVG as base64 inside another,
with its own ids. Normalise all of that away — then the render stage is exactly
deterministic: **262/262 identical across runs**.

### What is not deterministic

`pm4py.conformance_diagnostics_alignments` returns a different *equally optimal*
alignment for the same trace from run to run — in this log, 55 of 800 traces over
five runs, with identical fitness every time. Same cost, different placement of
the same moves, so which activity carries the violation changes, and 109–124 of
the 262 figures change with it.

It is not the hash seed (`PYTHONHASHSEED=0` changes nothing, and two calls inside
one process already disagree), and pm4py exposes no deterministic tie-break. So:

* **While working in this class, never delete `<dataset>/cache/alignments.pkl`.**
  The baseline comparison is only meaningful against the alignments it was taken
  with.
* The cache alone does not make the stimuli reproducible: its signature is the
  log's and model's `size + mtime` (`create_all_visualizations.py:269`), so a
  clone, a copy, a Docker rebuild or an iCloud sync invalidates it without a byte
  of the log changing. **Reproducibility of the published stimuli is handled
  outside the pipeline, by downloading the generated idiom and uploading it back
  as a fixed asset.**

## Per-task notes

* **task04** routes on `analysis_level`. At log level it *is* task01 — the same
  sub-log split and the same figures — so it delegates to `task01.generate`
  rather than growing a second copy of it.
* **task14** is fixed at one trace by its own wording ("a given trace"), so it
  offers no count, and it gained the chevron and BPMN it was missing.
* **task27** has no rule picker: its question *is* "what are conformant and what
  are non-conformant traces", so the traces come one group at a time and any
  other rule would answer something else. Its count is therefore per group — two
  means two conformant and two non-conformant.
* **task27**'s table is the class's activity × trace table. It used to list the
  top fifteen variants regardless of the selection, so an admin asking for one
  conformant and one non-conformant variant got a table contradicting the two
  strips beside it. The aggregate variant view remains as `bar_chart` and
  `table_bar_chart`.
* **task28** is task09 explored rather than presented. Same parameters, same
  figures; the difference is `HIGHLIGHT_VIOLATIONS = False`, a task property
  rather than an admin choice.
* **task34** draws one trace exactly as before; two or more go through task04's
  renderers. The per-activity summaries (bar, stacked bar, heatmap, matrix) stay
  on the first trace — stacking one of those per trace answers a different
  question.
* **task35** keeps aggregating over the whole log and is trimmed to
  `flow_chart_elaborate`; the Petri-net and DFG variants re-drew the same
  annotation in another notation, which is a notation comparison, not this task.
  Its `move_types` parameter chooses which deviations get annotated.
