# Standalone tasks: task08, task24, task37

Three tasks that belong to no class — each asks something no other task asks, so
there is nothing for them to share and nothing to keep in step. What they do
have in common is that each was given its parameter recently, and in each case
the parameter the design table named was **not** the one that turned out to
exist. This file records what each got and why, so the next reader does not
re-derive it from the table.

The class documents are [TRACE_FEATURE_REGISTRY.md](TRACE_FEATURE_REGISTRY.md),
[VIOLATION_PROFILE_CLASS.md](VIOLATION_PROFILE_CLASS.md),
[TRACE_ALIGNMENT_CLASS.md](TRACE_ALIGNMENT_CLASS.md) (+
[its parameter reference](TRACE_ALIGNMENT_PARAMETERS.md)) and
[AGGREGATE_FITNESS_CLASS.md](AGGREGATE_FITNESS_CLASS.md).

| task | question | parameter | design table said |
|---|---|---|---|
| task08 | which violations co-occur in a trace | `violation_patterns` | "threshold of high co-occurrence" |
| task24 | where the discovered model differs from the guideline | `trace_selection_mode`, `trace_ids`, `trace_count` | "discovered model / discovery algorithm" |
<!-- task24 draws one idiom, flow_chart_elaborate; see "The juxtaposition, and why it is gone again". -->
| task37 | how two techniques' fitness values differ | `conformance_bins` | "the two techniques" |

---

## task08 — which violations the axes are built from

`violation_patterns` is **the Violation-profile class's parameter**
(`violation_profile.selection_param_for("pattern")`, a select-many over
`log.violations`), declared here so "violation pattern" means one thing across
the platform — task05, task11, task12, task23 and task32 offer the same picker.
Empty keeps the task's own top-N by trace coverage.

A selection restricts the axes to those patterns and the pairs to those between
two of them, and **is never truncated**: the axis grows to hold every pattern
named. The caps (10 for heatmap and matrix, 12 for the network diagram) are
legibility guards for the default, not a budget an explicit choice has to fit —
silently dropping three of fifteen chosen patterns would answer a question
nobody asked.

Two details at the boundary:

* the picker speaks `activity|move type` while this module labels a violation
  `Model Move: Ship Order`; they are translated where the parameter enters,
  rather than either vocabulary being rewritten;
* a pattern that does not occur in the log is named in a warning instead of
  becoming an empty row.

`validate_params` rejects a selection of exactly one — a co-occurrence between a
pattern and itself is not a finding.

### Why there is no co-occurrence threshold

The design table names one, and the plumbing for it exists — every renderer
takes `thr_count` / `thr_frac` — but `generate` passes `None` on purpose:

> Threshold annotations are intentionally not drawn: ... leaving the
> co-occurrence counts to speak for themselves.

Naming the patterns worth looking at is what choosing them does. A threshold on
top would pre-judge which pairs are noteworthy, which is the analyst's call in
this task.

### Known wart (pre-existing)

The heatmap and matrix show the top 10 violations, the network diagram the top
12. Three idioms of one task with different axes is an information-equivalence
problem; it predates the parameter and is untouched. One number for all three
would fix it.

---

## task24 — which traces the model is discovered from

The task's wording — "multiple traces are taken and the model is discovered" —
makes the selection the whole choice, so task24 borrows the trace-alignment
vocabulary (`trace_selection_mode`, `trace_ids`, `trace_count`) with **no rule
picker**: either the admin names the traces, or the most frequent variants are
taken and `trace_count` is how many (default 3, range 1–15).

Two deliberate departures from that class:

* **The selection is not restricted to violating traces.** Discovery describes
  the behaviour that occurred; leaving the conformant traces out would discover
  a model of the deviations alone and overstate every difference against the
  guideline.
* **"The n most frequent variants" takes every trace of those variants**, not one
  representative each, so edge frequencies mean what they say — on
  order-to-cash the top 3 variants are 538 traces, not 3.

`validate_params` rejects a manual selection of one trace: a model discovered
from one trace is that trace.

### The juxtaposition, and why it is gone again

task24 briefly stacked **the discovered model above the guideline**, each under
its own caption, drawn with graphviz: an edge the guideline also prescribes thin
and grey, one it does not heavy and dark. The argument was that painting the diff
onto the guideline alone leaves the other half of a question about two models to
the reader's imagination.

It was removed. The two panels are two *notations* — a directly-follows graph
above a BPMN — at different scales in one image, and the mixture reads as one
picture of one model rather than as a comparison. This follows task35, whose
Petri-net and DFG variants were dropped for the same reason: re-drawing the same
finding in a second notation is a notation comparison, not the task.

The DFG did not go with it. `_discover_dfg` still produces the edges that
`_compute_diff` turns into the annotation — faded nodes for activities never
observed, dark borders on the endpoints of observed-not-in-model transitions, and
the summary line. Discovery is still what the figure reports; it is no longer
drawn as a second graph. `task24_flow_chart_elaborate_bpmn` now renders straight
to its output path, so the graphviz call, the temporary guideline file and the
base64 juxtaposition helpers (`_discovered_model_svg`, `_juxtapose`, `_svg_dims`)
are gone.

task24 also lost its second idiom, `flow_chart_table`, and is now a single
`flow_chart_elaborate`.

---

## task37 — where the fitness axis is cut

### Why "the two techniques" is not a parameter

Only two techniques produce a fitness **per trace**, which is what every idiom
here plots: alignments and token-based replay. pm4py's third, footprints, is
log-level only (`fitness_footprints` returns `perc_fit_traces` and
`log_fitness`), and its alignment variants — Dijkstra, A*, less-memory — are
algorithms for the same optimum returning the same numbers. A picker over a set
with exactly one legal pair decides nothing.

### What is a choice

`conformance_bins` — **task10's parameter**, because it is the same choice about
the same number: where the fitness axis is cut. It drives the heatmap's two
axes, the stacked bar's segments and the bucket bar chart, all of which were
fixed at quarters in code. Presets: quarters (default, what the code did),
fifths, and task10's high-fitness focus.

The bands are computed once in `_extract_data` and carried in the payload, so
every idiom cuts the axis the same way. Labels and colours follow the
boundaries: past four bands the four fixed greys would give two adjacent bands
the same colour, so the ramp's own colormap is sampled instead; a band holding
only perfect traces is labelled `1.0` rather than `[1.0, 1.0]`.

### Open: which number the task asks for

The answer format in the design table is "one percentage per technique". Seven
idioms, and only `bar_chart` carries a log-level fitness — in a corner
annotation box, and only when a model path is given. The others show per-trace
values and their mean, and **the mean of per-trace fitness is not the log
fitness** (the latter is cost-weighted; the code says so where it computes it).

So a participant in the boxplot condition can produce a mean and cannot produce
a log fitness. Three ways out, unresolved:

* **ask for the mean per-trace fitness** — then drop the log-level annotation
  box from `bar_chart`, and all seven idioms are equivalent again;
* **ask for the log fitness** — then it has to appear on every idiom, which
  makes the task "read the printed number" and collides with task06;
* **ask for the trend and the disagreement between techniques**, which is what
  the task's own wording asks and what the per-trace scatter, boxplot and
  heatmap already support — then the first bullet's cleanup applies too.
