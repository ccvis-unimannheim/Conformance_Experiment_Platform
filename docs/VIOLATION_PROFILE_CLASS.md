# Violation profile: what the class shares

Scope: **task05, task11, task12, task23, task29, task32, task36** — the tasks
whose subject is the violations themselves. Not what caused them (that is
[TRACE_FEATURE_REGISTRY.md](TRACE_FEATURE_REGISTRY.md), Attribute → Violation)
and not what they led to (that is
[CONFORMANCE_ATTRIBUTE_CLASS.md](CONFORMANCE_ATTRIBUTE_CLASS.md), Conformance →
Attribute), only what they *are* and how they are distributed.

---

## One groupby, three keys

The seven tasks already differed in exactly one way: what a violation is counted
*as*. That is not three pipelines, so `grouping_strategy` is a parameter:

| strategy | unit | what drew it before |
|---|---|---|
| `move_type` | Model Move / Log Move / Mismatch | task29's bar, pie and table |
| `activity` | one activity, split by move type | task11's tuned screenshots |
| `pattern` | "Log Move on Ship Order" as one unit | task23's tables |

The kernel was checked against all three before anything was rewired: it
reproduces task29's summary dataframe, task11's trace coverage and task23's
pattern dataframe exactly, on both datasets, percentages included.

task29 is worth a note. Its eleven idioms already showed **all three** units —
`bar_chart`/`pie_chart`/`table` from move types, `stacked_bar`/`matrix`/
`parallel_sets` from an activity × type pivot, `tree_map`/`sunburst` from a
pattern frame — each hardcoded per idiom, three separate extractions of the
same alignments. The strategy did not have to be invented, only named.

### Who exposes it

| task | strategy | split | cut | notes |
|---|---|---|---|---|
| task29 | A/B/C | — | — | the class's baseline |
| task05 | A/B/C | `split_attribute` (its only split) | — | outcome picker removed |
| task32 | A/B/C | `split_attribute` | "main" | exposed no parameters at all before |
| task36 | A/B/C | — | "predominant" | redefined, see below |
| task11 | fixed `activity` | — | — | + `activities` selection |
| task23 | fixed `activity` | — | — | draws task11's renderers |
| task12 | fixed `pattern` | — | — | one row per violation |

A fixed-strategy task takes its selection parameter from
`selection_param_for()`, which strips `visible_if`: with no strategy picker to
read, `/specify` would judge the condition unmet and hide the only control the
task has.

## task23 draws task11's figures

The two tasks showed the same violations in two shapes: task23 one flat bar per
pattern counted in occurrences, task11 two bars per activity counted in traces.
A reader moving between them met two encodings of one thing. task23's four
shared idioms — bar chart, matrix, table, table+bar — are now drawn *by*
task11's renderers, from the same coverage Counter, parameterised on filename
and heading. Checked by rendering both through the same call with the same
heading: byte-identical.

Its own two idioms, the composition stacked bar and the parallel sets, have no
task11 counterpart. They keep their shape and were switched from occurrence
counts to trace counts so nothing inside the task contradicts anything else —
a no-op on both datasets here, where no trace repeats a violation, but not in
general.

The four superseded task23 renderers are deleted.

---

What an admin picks need not be the unit reported. task23 asks how the
violations differ from one another, so a row is a pattern — but the dropdown
lists activities, because picking "Ship Order" and getting both of its move
types is the question a reader actually has. `select_by` separates the two.

---

## An activity's rows stay together

Rows were ordered by trace count alone, which scattered them: "Ship Order
(Model Move)" led the table while "Ship Order (Log Move)" sat nine rows below,
so a reader comparing one activity's two move types had to hunt for the second.
Both the `activity` and `pattern` strategies now order activity-major —
activities ranked by total violation *occurrences* (occurrences, not traces: a
trace deviating both ways on one activity would be counted twice in the
ranking), move types inside an activity in their conceptual order, Model then
Log then Mismatch, as task11's tuned screenshots read.

Three of task23's six idioms — matrix, parallel sets, stacked bar — already
computed that exact ranking themselves, while its bar chart and two tables used
the raw order. One task ordered the same data two ways depending on the idiom.
That ranking now lives in the kernel and all six agree.

task11 had the same split inside itself. Its bar chart and matrix are two
dimensional — activity against move type — so an activity's two bars sit
together by construction. Its table and table+bar chart were flat lists sorted
by trace count, which put "Ship Order (Model Move)" third and its Log Move
twelfth. All four now follow the kernel's order, through `ordered_pairs`: task11
keeps a trace-count Counter, and ranking activities by summing it would
double-count a trace deviating both ways on one activity, which is the same
trap `activity_coverage` fell into.

**This changes a frozen screenshot.** Picture 20 is that flat table, and it was
frozen in the scattered state; the decision was to make the four idioms agree.
Pictures 19 and 21 — the bar chart and matrix — are untouched.

---

## Two denominators, because the tasks mean different things

`pct_traces` is the share of the log's traces touched by a group; `pct_count`
the share of all violation occurrences it accounts for. task11's screenshots
show the first, task23's tables the second, and neither is derivable from the
other — a trace deviating twice on one activity contributes two occurrences and
one trace. Both are always returned so no caller recomputes the other and gets
it subtly wrong.

That trap is not hypothetical. The first draft of `log.violation_activities`
summed the per-move-type trace counts to get a per-activity total, which
double-counts every trace that deviates both ways on the same activity: it
reported A_APPROVED as 1738 traces of 13087 when 869 deviate, and ranked
A_ACTIVATED above A_DECLINED on the strength of that. Distinct traces are
counted, never summed.

---

## Selections are parsed, not string-matched

The pattern dropdown (`log.violations`) stores `"activity|Move Type"`; the
violation table labels the same thing `"activity (Move Type)"`. An `isin()` on
the display label matches nothing at all — silently, leaving the admin with a
selection that appears to apply and does not. `parse_pattern` accepts both
forms, plus `"activity::Move Type"`, a 2-tuple, the short codes MoM / MoL / MM,
and the pre-unification `"Move on Log"` spelling still present in saved
selections. A wholly unparseable selection keeps every row and says so.

`select()` and `unit_labels()` live in the kernel for the same reason: the first
draft of task05 reimplemented both and got the activity case wrong, which is
exactly the drift the class exists to prevent.

---

## What changed in results

**task36 was redefined.** It discovered a Declare model and computed
per-constraint conformance with pm4py — while taking `alignments` and never
reading them. "Conformance per rule" was a different kind of conformance from
the one every other task in the study reports, and the two could disagree about
the same log without either being wrong. A rule is now a violation group and
its conformance rate the share of traces that do not carry it.

Its `heatmap` and `network_diagram` draw activity-pair constraints, and an
alignment violation is not a pair. They now render an empty state saying so
rather than nothing at all — the previous code returned without writing a file,
which would have left the task with one SVG of three. **Both await a redesign.**

**task05 lost its outcome-activity picker.** It split two outcome groups of
one log, which the task's own question — how often a set of violations occurs
*across different logs* — never described. The sub-log attribute does describe
it, so it is now the only split. Its eight figures change accordingly, and
every "Outcome Group" caption with them: ten participant-visible strings that
would otherwise have told a reader the chart splits by outcome while it splits
by a case attribute.

Without an attribute the whole log is one group and the second series is named
"(no second sub-log)" rather than left blank — the pipeline falls back to the
auto-detected compare attribute, so this is reachable only by calling
`generate` directly.

**task05's group labels follow the data.** Its eight renderers had "Positive
outcome" / "Negative outcome" written into them; a chart captioned that while
showing `customer_segment = returning` tells a participant something untrue.
The internal column keys are unchanged, so only visible strings move, and the
defaults reproduce all three original wordings — `Positive`,
`Positive outcome`, `Positive (n / rate)` — exactly.

**task12 reports one row per violation.** It classified traces into five
categories (conformant / one move type only / mixed) and drew the conformant
share; it now gives the percentage of traces containing each violation, which
is what its question asks.

Two of its six idioms cannot draw that number. A pie and a 100% stacked bar
partition a whole, and the per-violation trace shares overlap — one trace
carrying two violations is counted under each — so they sum past the share of
traces that deviate at all: 38.2% against 28.4% on order_to_cash. Those two
draw the share of violation *occurrences*, which does sum to 100, and name that
denominator in their titles. The other four say "% of traces". Silently mixing
the two would have been the same confound the class was built to remove.

The overall deviating count is distinct traces, not the sum of the rows, for
the same reason.

**task29 no longer counts tau moves.** It counted every non-synchronous step,
including moves on hidden transitions, which name no activity and so could
never be attributed to one. Neither dataset here has any, so no number moved.

Everything else is unchanged: 262 of 262 SVGs byte-identical on both datasets
through the first three steps, and only task36's three at the end.

---

## task11's screenshots

Pictures 19–21 are frozen, and they show **every** activity, because the
question — how do the violations for activity X compare to those of others —
needs the others on the chart. So selecting X cannot filter the figure, and X
is not a backend parameter: nothing downstream would read it (RUBRIC is a
static constant and no ground truth is generated from parameters), which makes
it the dead control this codebase has removed before. The subject belongs in
the question text, which an admin edits directly via `PATCH /admin/tasks/{id}`.

What task11 does take is `activities`, which really does narrow the figure,
defaulting to empty = all = what the screenshots show. All five of its idioms
were compared one by one against HEAD on the real dataset: identical.

### The screenshots cannot be regenerated

`Context_0209/order_to_cash_experiment.xes` and `order_to_cash.bpmn` produce the
right shape — 800 traces, 10 activities, 16 violation pairs, all matching — but
not the right numbers: Ship Order is 29 Model Moves and 17 Log Moves here
against the screenshots' 43 and 23. The frozen images were made from a different
version of the log or the model. Regression testing compares HEAD against the
working tree on the same data, which is unaffected by this; using the
screenshots themselves as an acceptance baseline would need the files they came
from.

---

## Reproducibility

The order_to_cash dataset exposed a nondeterminism BPIC12 does not.
`task24_flow_chart_and_table` sorted a **set** of edges by frequency alone,
leaving equal-frequency edges in set-iteration order, which changes with every
Python process — two runs of the same data produced different tables. Tie-broken
on the edge. All 262 SVGs now match across two processes on this dataset too.

The earlier claim that all 264 were reproducible held only for BPIC12. A second
dataset is worth more than a second run.

---

## Open

* **task12 and task23 both report one row per pattern.** task12 measures the
  share of traces containing each, task23 each pattern's share of all
  occurrences, and they select differently (patterns against activities) — but
  a class is the sampling unit when drawing an experiment, and these two are
  close enough to be worth checking before both go into one.
* **task11 and task23 are the same pipeline** once the strategy is a parameter,
  differing only in which unit their question names. That is true *after* the
  unification, not before it: task11 had a selection and a BPMN idiom, task23
  had neither.
* **task36's two pair-based idioms** have no data under the redefinition.
* **task05 no longer has a default split.** The pipeline falls back to the
  auto-detected compare attribute when the admin picks none, which is a guess
  the admin cannot see. Making `split_attribute` required would surface it.
