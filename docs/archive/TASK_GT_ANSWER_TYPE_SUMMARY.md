# Ground Truth Tier & Answer Type — Reasoning Summary

Scope: the 8 tasks currently selected for the idiom study (Task-ID 6, 10, 34, 11, 3, 4, 20, 19).
Source: `provibackend/ProViBackend/scripts/tasks/taskNN.py` (`GT_TIER`, `ANSWER_FORMATS`, `RUBRIC`,
`compute_ground_truth`) and `task_registry.py` (fallback defaults).

Legend:
- **GT_TIER** — how the ground truth is produced: `AUTO` (computed with no human input),
  `SEMI` (an admin sets one parameter, then computation is objective), `MANUAL` (final answer
  is an analyst judgement, graded against a rubric, no single correct value).
- **ANSWER_FORMATS** — the response format(s) offered to participants for grading; `decisive_default`
  marks the format used as the primary/auto-graded one when multiple formats exist.

---

## Task 6 — Overall degree of conformance
*Describe · Derive · Process conformance*
"What is the overall degree of conformance between an event log and a set of guidelines?"

- **GT_TIER: AUTO** — Mean per-trace fitness × 100, rounded. No parameter needs a human decision;
  the question asks for one objective, log-derived number.
  (`task06.py:38-41`)
- **ANSWER_FORMATS:**
  - `pct` (scalar, decisive) — direct numeric readout, matches the question's single-value nature.
  - `mc-single` (decisive) — correct % plus 3 distractors spread across low/high/mid zones,
    snapped to 5-pp multiples, so options don't cluster and can't be guessed by elimination.
  - No `free-text` / rubric — unnecessary, since the answer is a single verifiable number.
- **Idiom note:** `scatter_plot` and `donut_chart` were deliberately dropped from `IDIOMS` — task
  is "purely about fitness," and per-trace scatter / conformant-vs-non-conformant donut mix in
  counts that don't belong to this single-value question. (`task06.py:29-31`)

## Task 10 — Conformance distribution
*Describe · Present · Conformance distribution*
"Which percentage of traces in the event log fall into which conformance category?"

- **GT_TIER: not declared → falls back to registry default `MANUAL`** (`task_registry.py:51,71-73`).
  No `compute_ground_truth` function exists in `task10.py`.
- **ANSWER_FORMATS: not declared → falls back to default `[{"key": "free-text", ...}]`**
  (`task_registry.py:48-49,66-68`).
- **Reasoning gap:** the question is structurally identical in kind to Task 6 (bucket traces by
  fitness into the shared `CONFORMANCE_BINS` from `shared.py`, then report % per bucket) — this is
  fully computable without any admin judgement. The current MANUAL/free-text fallback looks like an
  **unfinished contract, not an intentional design choice**. Recommend authoring `GT_TIER = "AUTO"`
  and a `pct-set` (or `mc-multi`) `compute_ground_truth` before this task goes live, otherwise every
  submission needs manual grading with no rubric to grade against.

## Task 34 — Where violations occur (trace level)
*Present · Present · Guideline violations*
"In which part of the process does a guideline violation occur at the trace level?"

- **GT_TIER: SEMI** — "which trace to look at" is inherently a scoping choice, so an admin first
  picks a representative trace via `violated_activity` (select-one, sourced from
  `log.violated_activities_task34`). Once the trace is fixed, which activities in it are
  violations vs. conformant is 100% computable from the alignment. (`task34.py:37-53`)
- **ANSWER_FORMATS:**
  - `mc-multi` (decisive) — correct options = activities with violations in the chosen trace
    (labelled Model-move / Log-move), distractors = the trace's conformant activities. Multi-select
    fits because a trace can have more than one violating activity.
- **RUBRIC:** requires correctly identifying all violating activities in the trace (used for the
  `free-text` fallback / partial-credit grading context).

## Task 11 — Predefined violation frequency
*Describe · Summarize · Guideline violations*
"How often did predefined guideline violation(s) occur?"

- **GT_TIER: SEMI** — "predefined" means an admin must first name the violation(s) of interest as
  one or more (activity, move_type) pairs (`target_violations`, select-many, sourced from
  `log.violations`, required). Given that selection, "% of traces containing each violation" is
  purely computed. (`task11.py:24-42`)
- **ANSWER_FORMATS:**
  - `pct-set` (labelled-set, decisive) — one percentage per selected violation; matches "how often
    for each of these."
  - `free-text` (reference) — fallback graded via `RUBRIC`.
- **RUBRIC:** full credit for correct trace-level % per violation (rounded); partial credit within
  ±5pp or for correct ranking; no credit for raw counts or percentages over a subset of traces.
  (`task11.py:49-58`)

## Task 3 — Conformant vs. non-conformant behavior
*Describe · Compare · Conformant/non-conformant traces*
"How does the overall behavior of conformant traces differ from that of non-conformant traces?"

- **GT_TIER: SEMI** — "conformant" needs a threshold decision (`conformant_threshold`, default
  fitness ≥ 1.0) that changes group membership, so an admin sets it once; the comparison itself is
  then computed. (`task03.py:32-38`)
- **ANSWER_FORMATS:**
  - `mc-multi` (decisive) — GT spans 3 behavioral dimensions: activity presence (top-2 by |Δ| → 4
    options, 2 correct), throughput time (which group is slower → 2 options, 1 correct), variant
    composition (top-1 variant by |Δ| → 2 options, 1 correct); up to 8 options / 4 correct,
    deterministically shuffled. Multi-select captures that "how behavior differs" is
    multi-dimensional, not a single fact. (`task03.py:620-626`)
  - `free-text` (reference) — fallback graded via `RUBRIC`.
- **RUBRIC:** full marks for ≥2 differentiating activities with correct direction and approximate
  presence rates; partial marks for correct direction without rates; marks deducted for wrong
  direction. (`task03.py:52-58`)

## Task 4 — Conformance across multiple logs/traces
*Describe · Compare · Process conformance*
"How does the degree of conformance differ between multiple logs or traces?"

- **GT_TIER: SEMI** — scope needs an admin-set `top_n` (default 10 variants, ranked by frequency);
  once fixed, per-variant fitness is computed automatically. (`task04.py:30-45`)
- **ANSWER_FORMATS:**
  - `pct-set` (labelled-set, decisive) — fitness % per top-N variant, matches "differ between
    which entities" as a labelled set of values.
  - `rank` (decisive) — variants ordered most→least conformant; a valid alternate way to express
    the same comparison without requiring exact percentages.
  - No `free-text` — both offered formats are already objectively gradable once `top_n` is set, so
    a rubric-graded fallback isn't needed.

## Task 20 — Attributes explaining violations
*Explain · Discover · Reasons for guideline violations*
"What control-flow, data, resource, or time attributes of events, traces, or event logs lead to
guideline violations?"

- **GT_TIER: MANUAL** — explicitly, because naming *the* causal attribute is an analyst judgement,
  not a single computable fact (there can be several plausible discriminating attributes, and
  "leads to" implies a causal read, not just a correlation the code can assert as ground truth).
- **ANSWER_FORMATS:**
  - `free-text` only (reference) — no MC/percentage format fits an open causal-attribution question.
- **RUBRIC:** full credit for naming a concrete attribute (control-flow / data / resource / time)
  that distinguishes violating from conforming cases **and** stating the direction of the effect
  (e.g. "longer cases show more violations"); partial credit for naming the attribute without
  direction; the answer must read as a root cause, not merely restate a correlation.
  (`task20.py:54-61`)

## Task 19 — Effect of violations on process goals
*Explain · Discover · Effects of goal deviations*
"What is the effect of a guideline violation on overall process goals?"

- **GT_TIER: MANUAL** — same reasoning as Task 20: "effect on the goal" is an interpretive claim.
  Structurally, an admin first defines the goal via `outcome_activity` (activity-picker, e.g.
  "Activate Care" = goal achieved if present in the trace); GT design compares goal-achievement
  rate between traces with vs. without the violation pattern, but the final "so what does this mean
  for the goal" statement is left to the participant to articulate, hence MANUAL rather than AUTO/SEMI.
  (`task19.py:46-52`)
- **ANSWER_FORMATS:**
  - `free-text` only (reference) — matches the open, explanatory nature of the question.
- **RUBRIC: missing.** Unlike Task 3 / 11 / 20 / 34, `task19.py` has no `RUBRIC` constant, so there
  is currently no documented grading standard for `free-text` answers on this task. **Gap to close
  before this task is used for real grading.**

---

## Cross-task summary

| Task | GT_TIER | Reasoning driver | ANSWER_FORMATS | RUBRIC present |
|---|---|---|---|---|
| 6  | AUTO | single objective number, no scoping choice | pct, mc-single | — (not needed) |
| 10 | MANUAL *(fallback — likely a gap)* | not authored yet; should be AUTO like Task 6 | free-text *(fallback)* | no |
| 34 | SEMI | which trace to inspect is a scoping choice | mc-multi | yes |
| 11 | SEMI | which violations count as "predefined" is a scoping choice | pct-set, free-text | yes |
| 3  | SEMI | conformance threshold is a scoping choice | mc-multi, free-text | yes |
| 4  | SEMI | which/how many variants to compare is a scoping choice | pct-set, rank | — (not needed) |
| 20 | MANUAL | naming *the* causal attribute is analyst judgement | free-text | yes |
| 19 | MANUAL | "effect on goal" is an interpretive claim | free-text | **no — gap** |

**Two open items to resolve with the team before finalizing this task set:**
1. **Task 10** has no `GT_TIER` / `ANSWER_FORMATS` / `compute_ground_truth` authored at all — it
   silently falls back to MANUAL + free-text. Given the question is structurally computable, this
   should very likely be authored as AUTO (or at least SEMI), not left on the default.
2. **Task 19** has no `RUBRIC`, unlike every other MANUAL/SEMI task with a `free-text` format —
   needed before free-text answers on this task can be graded consistently.
