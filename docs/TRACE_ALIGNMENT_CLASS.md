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
| `trace_pick_rule` | which rule (auto mode) | all six |
| `trace_count` | how many the rule picks | all but task14 |
| `trace_unit` | individual traces, or one per variant | task04, task09, task27, task28, task34 |
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

## The frozen figures

Six figures are experiment stimuli and must not move: task04's and task34's
chevron, BPMN and table (`Context_0209/Picture 13–15` and `22–24`). Two rules kept
them still, and both are load-bearing:

1. **The default path is never rewritten.** task04's two-trace `violation_gap`
   selection and task34's single-trace rendering keep their original code;
   another rule or count branches *around* them (`_task04_pick_by_rule`,
   `_select_ctxs` / `_multi_trace_alignment_figures`). Byte-identity on the
   default is then a property of the code not having been touched, not of a
   test having passed.
2. **Shared renderers only gain keyword arguments whose defaults are the current
   behaviour** (`filename=`, `title=`, `threshold=`).

Every step was checked by regenerating the whole dataset and comparing all 262
SVGs against a baseline. The final state differs in exactly six files — task09's
and task28's chevron, BPMN and table, which move from log-aggregate to
trace-level by design.

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
* **task27** picks conformant and non-conformant variants in equal number by
  default, so the contrast the question asks about is always on screen even when
  one side is rare.
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
