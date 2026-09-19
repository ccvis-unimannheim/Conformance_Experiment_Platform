# Aggregate fitness: what the class shares

Scope: **task02, task06, task25** — the three tasks whose answer is one number
for the whole log. The fourth class document, after
[TRACE_FEATURE_REGISTRY.md](TRACE_FEATURE_REGISTRY.md),
[VIOLATION_PROFILE_CLASS.md](VIOLATION_PROFILE_CLASS.md) and
[TRACE_ALIGNMENT_CLASS.md](TRACE_ALIGNMENT_CLASS.md).

---

## 1. The three ask the same thing of different people

All three are about the overall degree of conformance. What separates them is
**who produces the number and what the figure hands over**, and that is the only
thing the class has to keep straight — otherwise two of the tasks become the
same task with different titles.

| | task02 | task06 | task25 |
|---|---|---|---|
| Question | Does behaviour *predominantly* follow the model? | What **is** the overall conformance? | What is it — work it out yourself |
| The figure states | the fitness **and** a threshold to judge it against | the fitness | nothing aggregated |
| The participant | compares one number to another | reads a number | derives a number |
| Parameters | `predominant_threshold` | — | — |
| Idioms | tile_metric, bar_chart, table | tile_metric, bar_chart, table, matrix, gauge_chart | flow_chart_elaborate |

task06 is the baseline: five encodings of one scalar, deliberately nothing else.
A trace-level distribution (boxplot) was removed from it because median, IQR and
outliers are information the other four encodings do not carry, and the only
variable between conditions must be the encoding.

---

## 2. task02 — the threshold is the task

`predominant_threshold` (0–1, default 0.8) is not a display option: "does
behaviour *predominantly* follow the model" has no answer without saying what
predominantly means. It reaches all three idioms, and always as a reference
value rather than a verdict — no idiom prints "yes" or "no", because deciding
that is the participant's job:

| idiom | how the threshold appears |
|---|---|
| tile_metric | a second value beside the fitness |
| bar_chart | a dashed line across the bar, labelled `Fitness Threshold = 0.80` |
| table | its own row |

It is participant-facing (no `hide_hint`): the question cannot be asked without
naming the threshold.

---

## 3. task25 — discovery, on the model

task25's difference from task06 is that the number is **not** handed over. It
used to show per-trace fitness in three idioms, one of which — a tile listing
the trace count and the summed fitness under the caption "Conformance rate =
sum ÷ traces" — was the answer minus one division.

It now draws the guideline model, each activity labelled with how often it was
executed where the model prescribes it out of how often it was involved at all
(`779/821`), shaded by the share that deviated. Nothing aggregated is printed
anywhere.

`flow_chart_table`, which listed the same counts in a table beneath the model —
one payload, two readings, so neither idiom exposed more than the other — has
been removed; task25 is now the single `flow_chart_elaborate`.

The counts come from the centrally computed alignments — a synchronous move is
behaviour the model prescribes and the log records; a model move (prescribed,
not executed) and a log move (executed, not prescribed) are both deviations of
that activity; a mismatch move deviates on both its labels.

### The number it supports is not task06's number

Pooling the labels gives the share of replayed **steps** that were synchronous.
The fitness task06 states is the mean of the per-trace alignment fitness, which
weights every trace equally and is a cost ratio rather than a step count. On the
order-to-cash log:

```
task25, read off the figure   4580 / 4886 = 93.7 %   (event-weighted)
task06, mean per-trace fitness              95.3 %   (trace-weighted cost ratio)
```

Both are defensible readings of "overall degree of conformance", and no
per-activity decomposition reproduces a mean of per-trace cost ratios. **An
answer key for task25 therefore has to come from what its figure supports, not
from pm4py's fitness** — the design table's "same GT as #6" does not hold for
this implementation. Which of the two the study asks for is an open decision;
the platform grades nothing automatically, so it is a question for whoever
writes the key.

---

## 4. Why task06 has no parameters, and should not grow any

Every candidate is already somewhere else:

* a **sub-log** to restrict to — that is task04 at log level, which splits the
  log by a condition and compares the parts;
* a **conformant threshold** — that is task02's `predominant_threshold`, and
  giving task06 one would turn it into task02;
* **fitness bands** — that is task10 (the distribution over categories) and
  task37 (`conformance_bins`).

task06's whole role in the set is "the number, stated plainly". A parameter
would make it another task that happens to share a title.
