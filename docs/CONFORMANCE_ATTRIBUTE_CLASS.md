# Conformance → Attribute: what the class shares

Scope: **task03, task10, task19, task31** — the tasks that split by conformance
(or by a violation) and measure something about the traces in each group. The
companion to [TRACE_FEATURE_REGISTRY.md](TRACE_FEATURE_REGISTRY.md), which
covers Attribute → Violation.

(An earlier draft listed task32 here. That was a slip for task31: task32 ranks
violation frequencies and belongs with the Violation-profile tasks.)

---

## Why this class was refactored differently

Attribute → Violation could be unified behind one kernel because its tasks were
free to converge — asked to choose, the decision was to let task15, task16,
task22 and task33 draw what task20 draws.

Here that option does not exist. Every task in this class has tuned screenshots
in the running experiment, and so do task04, task06, task11, task20 and task34.
**Twenty-four images are frozen**, and the acceptance criterion for every change
below was that they come out byte-identical.

Two of the four also have a shape the shared panel renderers cannot draw:

| task | split | measure | shape |
|---|---|---|---|
| task03 | conformance, at a threshold | distribution over attribute bins | rows × 2 series |
| task19 | each violation pattern | share reaching the goal | rows × 2 series |
| task10 | conformance, in bins | share of traces | single series |
| task31 | conformance, in bins | share reaching the goal | single series |

The panel kernel draws one value per bucket. task03 and task19 need two series
per row — a conformant and a non-conformant column, a with-violation and a
without — which is a different figure, not a variant of the same one. task10 and
task31 do fit the kernel's shape, but their renderers differ in ways the frozen
images record (task10 colours its bars by category and has a pie chart the
kernel has no equivalent for).

So this class shares **data**, not drawing. Every renderer is untouched.

---

## What each task shares now

| task | reads | instead of |
|---|---|---|
| task03 | `trace_features` throughput feature | its own walk over every trace's timestamps |
| task19 | `trace_response.violation_table` | its own walk over every alignment |
| task31 | `trace_features` last-activity feature | its own "does this trace contain X" |
| task10 | — | (its explicit bins are already its parameter) |

task10's bin presets are down to two, Standard and High-fitness focus; the
"Study-defined categories" preset is gone. Standard is the default and what the
frozen screenshots show, so they are unaffected.

task03's compared attribute is now a parameter rather than throughput time
fixed in code — `response_attribute`, `slot: response`, drawing its options from
the same `log.candidate_attributes` the Attribute → Violation class uses. It is
**not** that class's `attribute_set`: task03's figure has one attribute axis, so
a multi-select would be a control the frozen renderers cannot honour, and the
key sits in the response slot rather than the split slot. Empty keeps throughput
time, and on that default all 262 rendered SVGs are unchanged.

The value reaches `trace_features.split` with the registry's own value type
rather than one guessed from the values. Guessing coerced attributes to float,
which turned a resource id into a number: `resource::dominant` is 94% one
resource, so its quantiles collapsed to a single bucket and the task drew an
empty chart instead of the comparison — non-conformant traces are in fact 4.7×
likelier to be handled by a resource other than the dominant one.

Each swap was checked by computing both ways and comparing: task03's durations
agreed to the last float over 13,087 traces, and task19's pattern sets agreed on
every one of them.

`conformance::value` — per-trace fitness — is in the registry for this class,
offered only when a caller passes the fitness it already has and marked
`requires: log+alignment`. It is a **predictor** here, which is not the
circularity the registry otherwise guards against: these tasks ask what
distinguishes conformant traces, not what causes non-conformance. The rule is
that predictor and response must not *both* be alignment-derived.

Splitting it needed boundaries the data cannot imply, since a conformance scale
has meaningful cut points that no quantile lands on:

```
edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]   explicit bins      (task10, task31)
cut   = 1.0                               explicit threshold (task03)
```

A `cut` reads as "at or above this counts", unlike a median, which splits the
data so its midpoint falls below. Conformance at 1.0 has to include the traces
that fit exactly; checked against `io_helpers` — 11,497 conformant, 1,590 not.

---

## task31's goal changed meaning

It counted a case as reaching the goal if the chosen activity appeared anywhere
in it. That reads softer than the question: a case that reaches approval and is
later withdrawn contains the approval. It also needed a second list of rejection
activities to decide which traces had a definite answer, dropping the rest.

The goal is now that the trace **ends** on the activity. Every trace answers
that, so the rejection list, the filter, and the "Definitive outcomes only"
captions are gone — along with two hardcoded BPIC12 names,
`_OUTCOME_ACTIVITY = "Activate Care"` and
`_REJECTED_FINAL_ACTIVITIES = {"Reject Case", "Withdraw Case"}`.

This is a change in results, not a refactor. task31 has no frozen screenshots,
which is why it was available to change.

### The heuristic had to follow

`infer_outcome_activity` ranks activities by how many traces contain one, which
suits the old reading and picks mid-process activities. On BPIC12 it returns
`A_ACCEPTED` — present in 39% of traces, final in 0.02% — which would leave
task31 with three positive cases out of 13,087.

`infer_terminal_activity` counts presence at the end instead (reading the
registry's last-activity feature rather than walking the log again) and returns
`A_DECLINED`, final in 58%.

**Which ending counts as the goal is a domain question no heuristic answers** —
`A_DECLINED` is a rejection. The fallback only keeps the chart from being
degenerate. `outcome_activity` stays required, and the log records what was
inferred.

---

## Reproducibility, found while taking the baseline

Rendering the same dataset twice produced different images for 11 of 264 SVGs.
An experiment cannot regenerate its own stimuli that way — a participant added
later would see a different chart from the same data — and **task19's three
frozen screenshots were among the ones that could not be reproduced**.

Three causes, all "an arbitrary order became a visible one":

* **Ties ranked by luck.** `Counter.most_common` and `sorted(key=-x)` leave
  equal values in input order, and those counters are filled by iterating sets,
  whose order changes with every Python process. Ties are common here: a Log
  Move and a Model Move on one activity usually touch exactly the same traces,
  so their rates match to the decimal. `shared.most_common_stable` breaks them
  on the key.
* **A set discarding a ranking.** task08 ranked its violations and then wrapped
  the result in `set()`.
* **Memory addresses as node names.** task35 built its Petri net with
  `dot.node(str(id(place)))` while iterating a set, so Graphviz saw a different
  input every run.

All 264 now match across two processes.

The comparator this needed is `scripts/svg_compare.py`. A naive diff is useless
(two identical runs differ on hundreds of lines) and comparing text nodes finds
nothing at all, since matplotlib draws glyphs as paths — an earlier check did
exactly that, reported every idiom as unchanged, and missed a real regression in
task20's column headers.

---

## The move names were unified

`classify_step` said "Move on Model" where `alignment_pairs_to_rows` said "Model
Move", and **both reached participants**: task09 showed one, task11 the other,
and task34 showed both in the same task. For a study that asks people to read
violations, that is a confound.

The short form won — it is what the frozen screenshots show. Selections saved
before the change read `activity|Move on Model`, so `_resolve_target_patterns`
accepts the old spelling and resolves it, and no database migration is needed.

---

## Frozen artefacts

Twenty-four screenshots in `Context_0209/`, three per task:

| Pictures | task | idioms |
|---|---|---|
| 1–3 | task20 | bar chart, table, matrix |
| 4–6 | task19 | bar chart, table, matrix |
| 7–9 | task03 | bar chart, table, matrix |
| 10–12 | task10 | bar chart, table, pie chart |
| 13–15 | task04 | *not yet matched to filenames* |
| 16–18 | task06 | *not yet matched to filenames* |
| 19–21 | task11 | *not yet matched to filenames* |
| 22–24 | task34 | flow chart, annotated BPMN, table |

Fifteen are matched to filenames and checked individually after every change.
task04, task06 and task11 are checked by comparing **every** idiom they produce,
which covers their three whichever they are.

---

## Open

* **task10 and task31 split on the same axis** — conformance bins — and differ
  only in what they measure. The decision was to keep both tasks; worth
  remembering when drawing an experiment, since a class is the sampling unit.
* **task19 keeps its own parameters.** `target_patterns` still selects violation
  patterns directly rather than going through `split_feature`, and `violates::`
  features were not added: only one task in the class splits by violation, so
  the registry entry would have had a single consumer.
* The pink tasks are only partly slotted: task03's `response_attribute` carries
  `slot: response`, but `conformant_threshold` and `conformance_bins` still
  carry none, unlike the Attribute → Violation class.
