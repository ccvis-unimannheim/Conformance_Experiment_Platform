# Change Log

Tracks files modified or created during development sessions.

## Session: /new Stops Asking for the Name and Design Twice (2026-09-20)

### Problem solved

Opening "Already have the images? Start from a downloaded zip" on /new showed
its own Experiment name field and Study design picker, right below the page's
own Name field and Experiment Settings section asking the same two things —
two name boxes, two design pickers, with no visible link between them and the
dataset table still sitting there as if it applied. An admin choosing the zip
route had no way to tell what any of it meant.

### Changes

| File | Change |
|------|--------|
| `ProViFrontend/.../components/Admin/BundleStartCard.js` | Its own Name / Study design / Randomise controls removed; it now reads `name`, `designType`, `randomizeOrder` from the page and states what it will use them as. `open` is a prop the page controls instead of the card's own state. |
| `ProViFrontend/.../admin/experiments/new/page.js` | Experiment Settings (design, trial order) moved above the fork so it reads as shared by both routes rather than duplicated in one of them. While the zip card is open, the dataset table is replaced by a one-line note instead of sitting there unused. |

`eslint` — no errors or warnings on either file.

## Session: Jumping to an Earlier Step Returns There Instead of Marching Forward (2026-09-20)

### Problem solved

The step bar (previous session) let an admin jump from Overview straight to
Concepts to fix the intro pages, but its Next button did not know that: it
saved and carried on to Tasks, so returning to Overview still meant clicking
Next through Tasks, Idioms, Specify and Answer Format again.

### Changes

Every jump made through `WizardSteps` (and the equivalent "View / change" /
"Change on Specify" / "Edit" links on Overview) now carries `return_to=<page
jumped from>`. The page landed on reads it: Next saves and goes straight back
there instead of to its normal next step, its label changes to "Save & Return",
and its own Previous Step link forwards the same `return_to` — so stepping
further back and later forward still returns to Overview rather than resuming
the ordinary forward march.

| File | Change |
|------|--------|
| `ProViFrontend/.../components/Admin/WizardSteps.js` | Every step link appends `return_to=<current>`. |
| `ProViFrontend/.../admin/experiments/overview/page.js` | The Participant flow card's links, the idiom "Edit" link, the answer-format link and "Change on Specify" all carry `return_to=overview`. |
| `ProViFrontend/.../admin/experiments/{new,prequestionnaire,knowledge,concepts,task,idiom,specify,answer-format}/page.js` | Each reads `return_to`; Next/Save targets it when present (idiom's "all-custom" and specify's "nothing to generate" shortcuts still yield to it), the button reads "Save & Return", and each page's own Previous Step link/handler carries it onward. |

`eslint` — no errors under `admin/experiments` or `components/Admin`, only the
same 8 pre-existing warnings. Not exercised in a browser.

## Session: A Step Bar for the Setup Wizard (2026-09-20)

### Problem solved

Each wizard step linked only to its neighbour, so returning from /overview to
the first step meant pressing *Previous Step* eight times. An experiment built
from a zip could not get back at all: /specify, the step it skips, redirected
forward to /overview, so stepping back bounced between the two.

### Changes

| File | Change |
|------|--------|
| `ProViFrontend/.../components/Admin/WizardSteps.js` | **New.** The nine steps as a bar, the current one marked, every other one a link. A bundle experiment's bar leaves out Specify. Without an experiment id (a draft not yet created) the steps show but do not link. |
| `ProViFrontend/.../components/Admin/ExperimentSetupHeader.js` | Renders the bar when given `experimentId` and `step`. |
| `ProViFrontend/.../admin/experiments/{new,prequestionnaire,knowledge,concepts,task,idiom,specify,answer-format,overview}/page.js` | Each names its step; the four that carry `AdminNav` render the bar themselves. /specify redirects a bundle experiment to /idiom (its neighbour) instead of /overview, and /answer-format's *Previous Step* points at /idiom for one. |
| `ProViFrontend/.../admin/experiments/new/page.js` | For a bundle experiment the dataset table is replaced by why there is none and a *Discard the uploaded images* action; Next no longer demands a dataset. The upload card is hidden while editing an existing draft, where it would have built a second experiment. |
| `provibackend/.../app/routers/idiom_bundle.py` | **New `POST /admin/experiments/{id}/discard-bundle`**: removes the images, the idioms recreated for that experiment and the tasks that came with them, and clears `bundle_only`, leaving an empty draft with its name and design that can take a dataset. |

Four pre-existing `react/no-unescaped-entities` errors fixed along the way
(knowledge page, dataset upload modal).

`py_compile` and `eslint` — no errors left under `admin/experiments` or
`components/Admin`. Not exercised in a browser.

## Session: task06's Bar Chart and Matrix Follow the Same Fix (2026-09-20)

| Area | Change |
|------|--------|
| Bar chart | Its one "Overall" bar was `GREY_MED`, cividis's olive-grey middle — the same colour the review has been moving other idioms off of. task02 draws the same shape (one "Overall" bar, one log, no second group to pair it against) in `GREY_DARK`; task06 now matches it. |
| Matrix | Was a single cell shaded on a light→dark grey scale with a colorbar — the value encoded twice, once by shade and once by the printed number. Now colourless: a white cell ruled by `draw_cell_grid` (the same helper tasks 01, 03, 04 and 27-32 use), the fitness carried by the number alone, no colorbar. |

`LinearSegmentedColormap` and the two-tone `GREY_LIGHT`/`GREY_LIGHTER` import it
needed are gone with it.

### Verification

`py_compile`. Not regenerated.

## Session: task04's Table Keeps Its Log Moves, and Its Order (2026-09-20)

### Every idiom now states the degree of conformance

task04's question is its label — *How does the **overall degree** of conformance
with a set of guidelines differ between multiple logs or traces?* Its
`seed_data` description asked a different one ("**where** each conforms to or
deviates from the guideline"), and that is the text the participant reads, so
the two pulled the task apart: `bar_chart` and `matrix` answered the label,
`table` and the two flow charts answered the description.

| File | Change |
|------|--------|
| `app/seed_data.py` | task04's description follows the label: "Compare how far the traces conform to the guideline overall, and by how much they differ." |
| `scripts/tasks/task04.py` | New `_trace_caption`. The chevron labels each strip `"Trace 1 — Fitness 0.571"`, the BPMN subtitles each panel the same way, and the table gains a leading `Fitness (0-1)` row. The alignment idioms now answer the question on their own instead of leaving a participant to infer a degree by counting moves — which fitness, a normalised alignment cost, is not. |

All three are opt-in behind `show_fitness=False`: task09, task14, task27,
task28 and task34 reuse these renderers to ask about the deviations themselves,
and a fitness number there would be a payload none of their other idioms carry.
Only task04 passes `show_fitness=True`.

### line_graph removed

The x axis is the compared traces, which have no order: "Trace 1", "Trace 2" is
the order the pick rule returned them in, not a sequence in the data. A line and
a filled area between them draw a trend that does not exist — change the rule
and the same two traces slope the other way. The bar chart carries the same
fitness values without claiming one. task04 is down to five idioms, two of them
fitness (`bar_chart`, `matrix`).

Excel remark: *removed - traces have no order, so the line implies a trend that
is not there; the Bar Chart shows the same fitness values*.


### Problem solved

`_task04_move_map` returned `{activity name: colour}`, so an activity taking
part in two moves of one trace kept only the last. In the order-to-cash log
Trace 2 executes an extra `Ship Order` (log move, step 5) and later skips the
modelled `Ship Order` (model move, step 7): the model move overwrote the log
move, and the table showed `Ship Order → Model Move` with no trace of the
insertion. The chevron drew it in navy and the BPMN drew it as a badge, so the
three alignment idioms contradicted each other — on exactly the deviation the
`Ship Order|Model Move` violation parameter names.

`task04_table` had a guard meant to catch this (`if c == GREY_DARK and a not in
activities`), but it only fired for an inserted activity that is *not* a model
task. A log move of a modelled activity — the common case — could never reach it.

Separately, the rows sit in model order, so a trace that runs two activities out
of order read exactly like one that runs them in order. The chevron shows that
difference; the table dropped it.
## Session: task29's Idioms Agree on Vocabulary, Palette and Numbers (2026-09-20)

### Changes

| Area | Change |
|------|--------|
| Vocabulary | `TASK29_TYPE_LABELS` mapped the move types onto "Model Move (Missing in Log)" and "Log Move (Unexpected in Log)". task04, task34 and every move table say "Model Move" and "Log Move"; a reader comparing two idioms of one task should not have to decide whether "Unexpected in Log" is a third kind of move. |
| Palette | `_VTYPE_COLOR` is `PAIR_COLORS` — cividis navy and cividis bright yellow, as task31 and task32 use them. It was `GREY_MED` over `GREY_DARK`: two neighbours in cividis's dark half, which read as one emphasis level rather than two categories, and left the bright secondary unused. The bar chart and pie chart read the same map instead of repeating the colour rule inline. |
| Heatmap | Was the last greyscale figure in the task (`cmap="Greys"`) and printed the count in every cell, encoding one variable twice and leaving the matrix with nothing of its own. It goes through `draw_value_heatmap` now: cividis, `annotate=False`, colorbar. Matrix = annotated grid, Heatmap = continuous colour, as shared.py has it. |
| Table | The Percentage column and the Total row are gone. No other idiom of this task carries either, and a table that adds a derived measure is not the same information in another encoding — which is what this task varies. |
| Pie chart | The wedges carry the count now, not the share. The share is still there as the angle, which is the pie's encoding; without the count it was the one idiom here a reader could take no absolute figure from. |
| Sunburst | Each ring label carries its count. It had neither a number nor a share, so rank was all it showed. |

### Verification

Eight SVGs render. Labels come out "Model Move" / "Log Move"; `_VTYPE_COLOR` is
`{'Model Move': '#243c6e', 'Log Move': '#e5cf52'}`. Decoding the embedded
rasters: the heatmap's cells are cividis (navy to yellow) where they were greys,
and the matrix's single raster colour is pure white — it has been colourless
since the tasks 27-31 round.

### Open point: four idioms ignore the admin's parameters

Generating twice on BPIC12-A, once per `grouping_strategy`, and comparing the
normalised SVGs:

| reacts to the strategy | ignores it, byte-identical |
|---|---|
| bar_chart, heatmap, pie_chart, table | matrix, stacked_bar, parallel_sets, sunburst |

The first four read `task29_violation_summary_dataframe`, which honours
`grouping_strategy` and `selection`. The other four take `alignments` straight
and build activity × move type through `_task29_activity_type_pivot`, capped at
the top 15 activities. So under the default strategy four idioms show two rows
and four show fifteen activities × two types: not the same information in
another encoding, and half the task does not answer the parameter at all. Left
as it is pending a decision on which of the two the task is about.

## Session: The Choices That Were Made For You Now Carry an Asterisk (2026-09-20)

### Problem solved

task32's "How violations are grouped" silently defaulted to "By move type", with
no asterisk to say a choice was in force. Auditing every declared parameter for
the same shape — a fixed-option select, a non-empty default, `required: False`,
and no statement anywhere of what empty means — found exactly five, reaching
eleven tasks between them.

### Changes

| Parameter | Declared by | Default that was applied in silence |
|---|---|---|
| `grouping_strategy` | task05, task29, task32, task36 | By move type (Model Move / Log Move) |
| `trace_selection_mode` | task04, task09, task14, task24, task27, task28, task34 | Automatically, by a rule |
| `trace_pick_rule` | task04, task09, task14, task28, task34 | the task's own historical rule |
| `perspective` | task09, task28 | Control flow |
| `analysis_level` | task04 | Trace level |

All five are `required: True` now, so /specify marks them and both the page and
`admin.py` refuse to generate on an empty one. `trace_pick_rule` keeps its
`visible_if`, and both checks skip a hidden entry, so naming the traces by hand
never blocks on a rule that is not on screen.

Nothing else changed. The parameters that stay optional are the ones whose empty
value has a meaning their own label states — `split_strategy` ("empty = ranges
for numbers and dates, one group per value otherwise"), `violation_pattern`
("empty = any deviation"), the attribute pickers ("empty = every attribute of
this log that can be grouped") — and the numeric fields, which cannot be empty
in a meaningful way.

### Verification

Re-running the audit: no fixed-option select with a silent default is left
without an asterisk. Every task declaring one of the five imports and reports
`required: True` — 4, 7, 5, 2 and 1 tasks respectively, plus the nine carrying
`attribute_class` from the session before.

## Session: Three Parameters That Changed Nothing (2026-09-20)

### Problem solved

task30's "How many violation patterns to show" had no effect on any idiom, and
the feeling that /specify does little turned out to be right in four places. An
audit of every task — the keys each `PARAM_SPEC` declares against the keys its
dispatcher entry in `create_all_visualizations.py` actually reads — found four
declared-but-unplumbed parameters across four tasks. Everything else it flagged
reaches its task through a class helper (`trace_alignment.pick_rule`,
`violation_profile`'s selection helpers) and is live.

### Changes

| Area | Change |
|------|--------|
| task30 `pattern_top_n` | Declared in `PARAM_SPEC`, never passed. `_aggregate_patterns` has taken a `top_n` all along and nobody gave it one, so every figure ranked the module default of 10 whatever the admin typed. Threaded: dispatcher -> `generate(pattern_top_n=...)` -> `_aggregate_patterns(top_n=...)`, and the log line now names the number in force. |
| task13, task20, task21 | They declared `split_strategy` and `group_cap` through `grouping_params()` and their `generate()` signatures have no such arguments — two controls on /specify that changed nothing. All three bucket through task13's `_bucket_rates`: quartiles for a numeric attribute, top categories for a categorical one. That is a rule settled in code, so they now declare `attribute_params()` and offer only what they can act on. No figure changes. |
| `attribute_class` required | "Level the attributes are taken from" was optional with a silent default of "trace", so leaving it blank produced case-level attributes the admin never asked for and /specify showed no asterisk. It is required now: the frontend marks it and refuses to generate on an empty one. The picker under it stays optional — an empty attribute selection means "every attribute of this log that can be grouped", and its own label says so. |

### Verification

`pattern_top_n` cut to 2, 3, 5 and 10 over a five-pattern frame gives 2, 3, 5
and 5 rows. Three `generate` runs on BPIC12-A at 3, default and 20 all log the
number in force; that log holds only three distinct patterns, so the cut is not
visible there. `PARAM_SPEC` keys after the change: task13, task20 and task21
carry the attribute block alone, task30 keeps all seven.

## Session: task33 Is Four Panel Idioms, and Names Its Attribute on the Axis (2026-09-20)

### Changes

| Area | Change |
|------|--------|
| Idioms removed | Box and whisker plot, scatter plot, stacked bar, table & bar chart. Four left: `bar_chart`, `table`, `matrix`, `heatmap`, all four task20's panel renderers handed fitness instead of a violation rate. The first three read a per-trace distribution, which is more than the mean per bucket their neighbours show, and they could only ever do it for the *first* attribute selected — so a two-attribute selection gave four figures about both attributes and three about one. |
| task33 shrinks | With those three gone, everything they used went too: `_build_trace_df`, `_group_stats`, `_band_rates`, `_fine_bin_rates`, `_group_colors`, `_FITNESS_BANDS`, `_GROUP_PALETTE`, `_FIT_THRESHOLD`, the `split_by_attribute` import and the `_ALL_FNAMES_TITLES` empty-state table. The second half of `generate` cut the log a second way purely to log per-group stats; task20's renderers do their own bucketing and handle the empty case themselves. task33 draws nothing of its own now, and says so. |
| Matrix | `colorless=True`: white cells ruled into a grid, the value carried by the number, as in tasks 01, 03 and 27-34. The panels alternate between a flat yellow and a flat blue wash which, by the renderer's own docstring, "carries no data" — it tells the panels apart, which their labels already do. A reader cannot know a colour means nothing without being told, and the heatmap beside it uses colour for the value. The wash stays the default for the other four tasks. |
| Attribute name | It is a subplot title: centred over the bar chart, centred over the matrix and heatmap, left-aligned above the table, and inside the table a generic "Attribute Value" header. Four placements for one thing, and over the grids it reads as a floating caption. `attribute_on_axis=True` puts it on the axis its own buckets sit on instead — x on the bar chart, y on the matrix and heatmap, and the header of the table column holding its values. |
| Vocabulary | task33 passes `value_label_header` explicitly, so the measure is "Mean Fitness" everywhere. task20 title-cases `value_label` into the header when none is given, which put "Mean fitness" on the bar chart's axis and "Mean Fitness" on the matrix beside it. |
| Title | `_SPLIT_SUPTITLE` is "Mean Fitness by Attribute". "Process Conformance by Candidate Attribute" was task20's vocabulary, where the attributes are candidate root causes; in task33 the admin has chosen the attribute. |

**Scoped to task33.** Both live in task20's shared renderers, which task15,
task16, task20 and task22 also call, and those four have tuned screenshots in
the running experiment (CONFORMANCE_ATTRIBUTE_CLASS.md). So each is an opt-in
keyword — `colorless` on the matrix, `attribute_on_axis` on all five — and only
task33 sets them. Two styles in one renderer is the price; when those tasks come
up for review, the switches are what to delete.

### Verification

`pyflakes` against HEAD on both files: task33 clean, task20 unchanged from its
four pre-existing warnings. Both modes rendered from two synthetic panels — the
case where the matrix draws both of its alternating washes. Every colour in
task33's matrix SVG: `#ffffff` cells, `#cccccc` grid, `#243c6e` text. task20's,
with the same data and no keywords: `#e5cf52` and `#243c6e` washes, as before.

## Session: The Variant Rule Says That It Only Picks Violators (2026-09-20)

### Changes

| Area | Change |
|------|--------|
| `PICK_RULES` | "The most frequent trace variants" is now "The most frequent variants that violate the guideline". `pick_indices` filters every rule to the traces that violate before any of them ranks anything — the tasks in this class present violations, and a conformant trace answers nothing there. The other three labels carry that by themselves; this one read as if it ranged over the whole log, so an admin picking it saw fewer variants than the log's frequency order would suggest and had no way to tell why. The stored value is unchanged, so existing experiments keep working. |

### Verification

`py_compile`. The label is data, read straight into the /specify select.

## Session: task34 Shows Every Trace That Was Asked For (2026-09-20)

### Problem solved

Asking for four traces gave three, or fewer depending on the rule; naming four
by hand gave one. Every idiom agreed with every other, so the figures looked
consistent — they were consistently short.

### Changes

| Area | Change |
|------|--------|
| The drop | `_build_contexts` keeps a pool of the 30 most-violating traces, and `_select_ctxs` looked each chosen trace up in it with `by_index[i]`, skipping whatever was missing. Anything outside the pool was discarded without a word, whether the admin had named it or a rule had picked it. On BPIC12-A: four hand-picked traces came back as one, and `most_frequent_variants` returned index 7549 — a frequent variant with few violations, nowhere near the top 30 — which left three of four. |
| The fix | `_context_at(alignments, i)` builds one trace's context on demand; `_select_ctxs` falls back to it for any index the pool does not hold. `_build_contexts` is now only the fallback pool and what `violated_activity` narrows, and says so. |
| Short selections | A log can hold fewer distinct violating variants than the admin asked for — the rules keep one trace per activity sequence. `generate` logs that case instead of leaving the figure quietly short. |

### Verification

On BPIC12-A (13087 traces), before and after: four hand-picked traces 1 -> 4,
`most_frequent_variants` at count 4 3 -> 4, `worst_fitness` and
`first_nonconformant` 4 -> 4. Two full `generate` runs, by rule and by hand,
write six SVGs and a `traces.json` holding four traces.

## Session: Every task34 Idiom Names the Violation Type (2026-09-20)

### Problem solved

Three of task34's idioms said which kind of violation a step was — the chevron,
the BPMN and the move table all distinguish Model Move from Log Move. The
aggregates counted violations per activity and dropped that distinction, so half
the task's idioms answered a question the other half could not.

### Changes

| Area | Change |
|------|--------|
| Violation type | The aggregates' unit is the pair, labelled `Activity (Move Type)` — "Ship Order (Log Move)". Folded into the category rather than given an axis of its own: a second axis would have doubled every bar and every column, while the pair carries the same information at the cost of some longer labels. Only pairs that actually occur get a row. |
| Stacked bar removed | Its bars split on the move type, which is now the category itself, so every bar would have held a single segment. Six idioms left. |
| Trace numbering | `_build_canonical_payload` labelled traces from `ctx["trace_label"]`, which counts positions in the whole log. The move table numbers the shown traces 1..N through `trace_alignment.trace_records`, so matrix, bar chart and heatmap named ids nothing else mentioned. All of them use the running number now, and `traces.json` with them — the sidecar must not desync from the figures. |
| Vocabulary | `_MOVE_DISPLAY` is the one spelling: "Synchronous Move", "Model Move", "Log Move". The stacked bar's legend and a dead `_move_legend()` carried their own "(skipped)" / "(extra)" / "(conform)" glosses, which read as if "extra" were a third kind of move. |
| Table | Its own now, not task04's, and built from the same payload as the other three: `Activity (Move Type)` down, traces across, a count per cell. Both tables it replaces said things their neighbours could not. They listed Synchronous Moves — conformant steps the aggregates do not count — and task04's `_task04_move_map` is activity × colour, one move type per cell, so an activity both skipped and inserted in the same trace lost one of the two: the bar chart drew two bars where the table showed one cell. A count per cell removes the collapse, because the pair is the row. task04's own table is untouched. |
| Grid width | `_grid_size` sizes the heatmap and the matrix from the longest row label instead of a fixed margin, which cropped the now longer category names. |
| Idiom mapping | task34's table in TASK_IDIOM_MAPPING.md still listed flow chart & table, flow chart+ & table, table & bar chart and parallel sets, deleted the session before. |

### Verification

`py_compile` and `pyflakes` against HEAD — the only two warnings are the
pre-existing unused imports. Bar chart, table, heatmap and matrix rendered from
two synthetic contexts, one of which holds two moves on one activity: three
categories, traces labelled "Trace 1" / "Trace 2".

## Session: task34's Idioms All Speak About the Chosen Traces (2026-09-20)

### Changes

| Area | Change |
|------|--------|
| `_task04_move_map` → `_task04_move_steps` | Returns `[(activity, move type, step)]` in alignment order instead of a name-keyed dict. Nothing is overwritten, because nothing is keyed by name. |
| `_task04_row_cells` (new) | Turns those steps into `row label → "step · move type"`. A log move takes the row label `"<activity> (inserted)"`, so it cannot collide with the model task of the same name — the same separation the BPMN idiom makes by drawing it as an external badge rather than colouring the node. |
| `task04_table` | Builds its rows from those cells. The `Ship Order (inserted)` row now appears, `—` where a trace does not make that move. Columns are headed `"<trace> (step · move)"` and each cell leads with the step, which is what lets a reader see that Trace 2 ran `Issue Invoice` (4) before `Prepare Shipment` (6) while Trace 1 skipped both. Figure width per trace column 2.1 → 2.7 for the longer cells. |
| Module docstring | Said `table – Trace \| Fitness, one row per trace`, which has not been what the renderer draws for some time, and claimed information equivalence across all idioms. It now names the two families — fitness (`bar_chart`, `line_graph`, `matrix`) and alignment (`table`, the two flow charts) — says they are not equivalent to each other, and says what the three alignment idioms each can and cannot express. |

### Known limit

An activity that appears twice in the **same** role in one trace (a modelled
loop executed twice) still keeps only its first occurrence. One row per activity
is what makes this a table rather than a second chevron; the collision that
mattered — log move against model move — is the one that is fixed.

### Reaches the other tasks in this class

`task04_table` is also drawn by task09, task27 and task34. The log-move fix and
the step numbers reach their tables too — correctly, since the collision was a
defect, but **their move tables change with this commit**, and any baseline
recorded for them predates it. The fitness row does not reach them.

### Verification

`py_compile` on task04 and on every module that reuses its renderers (task09,
task14, task27, task34). The expected Trace 2 column was worked through by hand
against the rendered chevron in the admin preview (steps 1-8, log move at 5,
model move at 7); `pyflakes` is not installed in this environment. Not
regenerated — **no figure in this section has been rendered**.
| Idioms removed | flow chart & table, table & bar chart, flow chart+ & table, parallel sets. Seven left. `_log_activity_violations` and `_add_trace_heading` went with them, the heading being where the trace id and fitness were printed. |
| Multi-trace | bar_chart, stacked_bar, heatmap and matrix drew the first selected trace however many the admin asked for, while the chevron, BPMN and move table drew all of them — one figure set, different traces depending on which idiom you read. `_build_canonical_payload` now takes the list and returns the whole (activity × trace) table: totals plus the Model Move / Log Move split. The four read only from it. |
| Orientation | bar_chart and stacked_bar stand upright, activities on the x axis, one bar per trace within each activity; the stacked bar splits each of those by move type. They used to lie on their side. `_wrap_activity` breaks long names so the tick labels stay apart. |
| Heatmap and matrix | Both are activities × traces now, one column per trace instead of a single row or column. The heatmap carries the count as colour, the matrix as a number on a white cell (`colorless=True`), as in tasks 27-32. |
| Titles | One constant, `_VIOLATION_TITLE = "Violations per Activity"`, across the four. They used to name the trace, and the stacked bar its fitness — a value the figure beside it did not carry, and wrong as soon as more than one trace was drawn. |

This overrides what TRACE_ALIGNMENT_CLASS.md recorded for task34; that note is
updated with why.

### Verification

`py_compile` and `pyflakes` (against HEAD, so only new warnings count — none),
plus one run of `generate` with `trace_count=3` on BPIC12: the seven idioms
render.

## Session: task04 Colours Its Traces, and Drops Two Idioms (2026-09-20)

### Changes

| Area | Change |
|------|--------|
| Bar chart | Every bar was `GREY_MED`, cividis's olive-grey middle, which read as a muted category rather than the figure's subject. Each trace now takes its own colour from `categorical_colors(len(tdf))` — navy and yellow for the usual two traces, the pair task01 and task03 draw their bars with, spread over cividis's blue and yellow ends for the three or four this task also allows. The colour encodes **which trace**, never how conformant it is: task04 asks the participant to read conformance off the fitness values, so no idiom here colours a trace by conformance. |
| Line graph | One line cannot be navy at one end and yellow at the other, so the line stays neutral (`_LINE_COLOR`, `GREY_DARK`) — it joins every trace and belongs to none — and the markers become a `scatter` in each trace's own colour. A trace is the same colour in the bar chart and the line graph. |
| Matrix | `colorless=True`, as tasks 01, 03 and 27-32 now draw theirs: white cells ruled into a grid, each fitness carried by its printed number, no colorbar. |
| `heatmap` removed | Activity × trace, cell colour = move type. Its whole payload was colour over four nominal categories, and `table` already carries the same activity × trace move types as words. |
| `table_bar_chart` removed | Two idioms in one — the same reason the review dropped it from task01 and task03. |

task04 is down to six idioms: `flow_chart_basic`, `flow_chart_elaborate`,
`bar_chart`, `table`, `line_graph`, `matrix`. Renderers, `IDIOMS` entries and
`generate()` calls are deleted rather than commented out, as in tasks 24-32.

### Knock-on in task01

`task01_table_and_bar_chart` was already out of task01's own `IDIOMS` but still
called, because task04's log level ran task01's `generate()` and offered the
file as `table_bar_chart` (`_FILE_RENAME` maps the stem). With task04 dropping
that idiom the call had no consumer left anywhere, so it is commented out beside
`box_plot` and `parallel_sets`, and the note at `IDIOMS` that pointed at task04
is corrected. The entry earlier in this log that calls it "still drawn" records
what was true then; this section supersedes it.

### Docs

`docs/TASK_IDIOM_MAPPING.md`: the `Table & Bar Chart` and `Heatmap` rows under
task04.

### Verification

`py_compile` on both modules, and a grep for the removed names across the repo.
`pyflakes` is not installed in this environment; nothing the change orphans was
found by hand — `mpatches`, `gridspec`, `GREY_MED`, `_MOVE_LEGEND` and
`_task04_move_map` all keep other callers (the chevron, BPMN and table idioms).
Not regenerated.

## Session: task01 and task03 Matrices Lose Their Colour (2026-09-20)

Tasks 27-32 already draw their matrices colourless: white cells ruled into a
grid, the value carried by the printed number alone. task01 and task03 were the
two left over. Numbers, geometry, labels, titles and empty states are unchanged
— only the fill and the colorbar go.

| File | Change |
|------|--------|
| `scripts/tasks/task01.py` | `task01_matrix` passes `colorless=True` to `draw_value_heatmap`. It was a cividis heatmap that also printed its shares, which encodes one variable twice and left it differing from a heatmap only in annotation. The `vmax=100` fixed scale and the colorbar label stay in the call, ignored while colourless, as tasks 30 and 32 pass them. |
| `scripts/tasks/task03.py` | `task03_matrix` draws its own cells rather than an `imshow`, so the flag does not reach it: the per-column fill (`_COLOR_CONFORM` / `_COLOR_NON_CONFORM`) becomes white and the white cell border becomes `#CCCCCC`, the grey `draw_cell_grid` rules the shared matrices with — on a white fill it is the rule, not the fill, that makes the cells a grid. Cell text is `GREY_DARK` throughout, so `contrasting_text_color` has no caller left here and leaves the imports. The column headers already name the group the fill stood for. |

The two idioms stay distinct from their tables: a matrix is the bucket × group
grid, a table is one row per record.

### Verification

`py_compile` on both modules. `pyflakes` is not installed in this environment;
the one import the change orphans was removed by hand. Not regenerated.

## Session: Name, Design and Task Order on the Overview Page (2026-09-20)

An experiment's name, between/within design and task-order setting were asked
for once, on /new, and never again. An experiment built from a zip never visits
that page — and stepping back to it shows a dataset table that route has no use
for. `ExperimentSettingsCard` on /overview now shows all three and saves each
one as it changes (`PATCH /admin/experiments/{id}`, which already took them),
while the experiment is a draft; once published it is read-only, since
participants have been allocated under those settings.

`eslint` on `overview/page.js` — clean apart from the pre-existing
`react/no-unescaped-entities` errors in the publish-conflict dialog.

## Session: An Experiment From an Uploaded Zip (2026-09-20)

### Problem solved

The images of a finished study could be exported and imported back, but only
into an experiment that had already been set up the same way — a dataset, the
same tasks, the same idioms, and a generation run whose output the import then
replaced. An admin who already has the images had no way to say so.

### Changes

| File | Change |
|------|--------|
| `provibackend/ProViBackend/app/routers/idiom_bundle.py` | Manifest version 3: each task also records its wording, `is_custom` and answer shape (`answer_format`, `number_kind`, `answer_options`), each idiom its `is_custom`, granularity and renderer. **New `POST /admin/experiments/from-bundle`**: builds a whole draft experiment out of a zip — recreating tasks the question bank does not have and idioms this server does not know, writing the images as overrides, and marking every task `ready`. Reverting an image is refused for such an experiment (there is nothing behind it). Zip reading factored into `_open_bundle`. |
| `provibackend/ProViBackend/app/routers/admin.py` | Generation and attaching a dataset are refused for a `bundle_only` experiment. New `_mark_image_backed_tasks_ready`: a task whose every idiom is an uploaded image is `ready` when it is saved, so skipping /specify does not block publishing. |
| `provibackend/ProViBackend/app/datamodels/data_schemas.py` | `Experiment.bundle_only`. |
| `provibackend/ProViBackend/utils/idiom_files.py` | `BUNDLE_DATASET_ID` (`_bundle`): the placeholder such an experiment carries where a dataset id goes, resolving to its overrides and nothing else. |
| `ProViFrontend/.../components/Admin/BundleStartCard.js` | **New.** The collapsed "Start from a downloaded zip" panel on /new: the expected layout, the upload, and what was not used. |
| `ProViFrontend/.../admin/experiments/new/page.js` | Shows it; on success goes to /overview, or /answer-format when the zip carries no formats. |
| `ProViFrontend/.../admin/experiments/specify/page.js` | Import and *Discard import* removed; a `bundle_only` experiment is redirected to /overview. Imported tasks still show why their parameters are locked. |
| `ProViFrontend/.../admin/experiments/idiom/page.js` | Next skips /specify when every selected idiom is an uploaded image. |
| `ProViFrontend/.../admin/experiments/overview/page.js` | A banner for bundle experiments (no dataset, nothing to generate, no revert); import and *Revert all* hidden for them. New *Participant flow* card: what the pre-questionnaire, knowledge questions and intro pages are set to, with links to change them. |
| `ProViFrontend/.../components/Admin/IdiomImport.js` | Import asks first and lists what it changes — images and the matched tasks' parameters — and what it does not. |
| `ProViFrontend/.../admin/page.js` | *Continue Editing* never resumes a bundle experiment at /specify. |

`docs/ADMIN_EXPERIMENT_SETUP.md` gains the second route and the /specify skip.

### Verification

`py_compile` over the changed Python files; `eslint` over the changed JS files —
clean apart from the pre-existing `react/no-unescaped-entities` errors in
`overview/page.js` (publish-conflict dialog) and `admin/page.js` (dataset
delete text). **Not run end to end:** no zip was uploaded against a running
backend.

### Known gaps

- A zip exported before this change (version 1 or 2) carries no answer formats,
  so an experiment built from one has to be taken through /answer-format.
- The images of a bundle experiment can be replaced but not reverted, and its
  tasks and idioms can only be removed on /task and /idiom, not added to.

## Session: Removed Idioms Leave the Admin Panel, task01 and task03 (2026-09-20)

The idiom review removed three of task01's idioms and two of task03's. They are
commented out of each module's `IDIOMS`, which is what `/admin/task-idioms`
offers on /idiom, and their calls in `generate()` are commented out — as
task16 already does. The renderers stay.

| Task | Removed | Reason |
|------|---------|--------|
| task01 | box_plot | draws quantiles, not the per-group shares; its boxes collapse at fitness 1.0 |
| task01 | table_and_bar_chart | two idioms in one — **still drawn**: task04's log level runs task01's `generate()` and offers it as `table_bar_chart` |
| task01 | parallel_sets | shows no count of traces per conformance category |
| task03 | table_and_bar_chart | two idioms in one |
| task03 | stacked_bar | removed in the review |

A draft that had already selected one of these keeps it selected, but
regenerating no longer draws its image. `py_compile` only.

## Session: task32's Idioms Agree on Unit, Palette and Numbers (2026-09-19)

### Changes

| Area | Change |
|------|--------|
| Box plot | Removed. Its unit was the trace, not the violation pattern, and it summed every pattern together — dropping the dimension this task is about — while carrying median, IQR and outliers that no other idiom here has. task06's box plot went for the same reason (see AGGREGATE_FITNESS_CLASS.md). There is no honest re-targeting: per pattern and sub-process there is one number, so no distribution. task32 is down to six idioms. |
| Palette | `_GROUP_PALETTE` starts at `PAIR_COLORS` — navy and cividis's bright yellow, as task31 uses — instead of `GREY_MED` / `GREY_LIGHT`, which sat in cividis's olive-grey middle and read as muted extra categories. It reaches every idiom through `_group_colors`. |
| Matrix | `colorless=True`: white cells, ruled grid, no colorbar, as in tasks 27-31. |
| Table | The Total and Cum % columns are gone. The cumulative share is a Pareto reading no other idiom supports, and the row total is a number only this table and the bar chart's cluster label carried — the rows are ranked by it anyway. |
| Bar chart | The `Σ N` per cluster is gone with the other totals. Each bar now carries its own count, rotated inside the bar in `contrasting_text_color`, or just above it when the bar is too short. The bar geometry lives in `_BAR_WIDTH_TOTAL`, passed to `draw_grouped_rate_bars` and reused for the labels so the two cannot drift. |
| Bar chart title | Names a cut only where there is one: "Violations — …" when every pattern is shown, "Top 10 of 23 Violations — …" when not. Under the move_type strategy there are only ever two patterns, so the old "top 2" claimed a ranking over the whole set — and, sitting next to "Sub-process", read as if it counted the bars. `_aggregate_frequency` carries `n_all_patterns` on every row for this, as a column rather than `df.attrs` so it survives the prominence filter. |

### Verification

`py_compile` and `pyflakes`, the latter against HEAD so only new warnings count
— there are none. Not regenerated.

## Session: task31 Reads Like task10, and Says When a Category Is Empty (2026-09-19)

### Changes

| Area | Change |
|------|--------|
| Bar chart | The `Bin '= 1.0'` caption is gone and the axis stops at 100 — a rate cannot pass it, and the 20% headroom made the tallest bar look short of a ceiling that does not exist. A label on a bar above 93% moves inside it, stacked over two lines: on one line it is wider than the bar, so its ends were white on the white background and unreadable. |
| Stacked bar | `PAIR_COLORS` (navy against cividis's bright yellow) instead of `GREY_LIGHT` `#a99f73`, which sat in the olive middle and read as a third, muted category. |
| Wording | All five idioms name the unit as task10 does: **Conformance Category**, not Conformance Degree, Conformance Band or Fitness Band. Empty-state titles included, so a blank idiom is not titled differently from a filled one. |
| Empty categories | `_band_outcome_rates` returns NaN, not 0.0, for a category no trace falls into. A zero reads as "none of these traces had a positive outcome", which is a finding; there are none. The heatmap left such cells at the yellow end of its scale and now leaves them blank; the stacked bar dropped the category entirely and now keeps its slot empty. The bar chart, table and matrix already marked them (no bar, `—`, `—`). |

All five idioms now show the same six categories and agree on what an empty one
looks like.

### Verification

`py_compile` and `pyflakes`, the latter against HEAD so only new warnings count
— there are none. Not regenerated.

## Session: task30 and task31 Idioms Carry One Payload (2026-09-19)

### Problem solved

Within a task the idioms must answer the same question. In task30 and task31
several of them answered more than the rest, and task31's table cut the log a
different way entirely.

### Changes

| File | Change |
|------|--------|
| `scripts/tasks/task30.py` | The table drops its sub-log summary (#Traces, % Conformant, Mean Fitness) — a conformance level no other idiom states — and its pattern rows drop the counts and the Total column, leaving rates. Losing the `(n / rate)` header line also unsqueezes the column headers. Parallel sets drops its "Other" bucket, which measured the deviation the top-N leaves out. |
| `scripts/tasks/task31.py` | The decision tree is gone, with the fitting helpers and split constants nothing else used. The table listed tree branch conditions and the case counts behind each rate; it now lists the bar chart's bands, traces and positive-outcome rate. Matrix and heatmap read one `_band_outcome_rates` table — the matrix as numbers, the heatmap as colour; the heatmap loses its calendar axis and the matrix its "All bands" row. All five idioms bin fitness the same way, `= 1.0` included, and the bar chart draws in task30's dark blue instead of grey. |

task31 is down to five idioms: `table`, `bar_chart`, `stacked_bar`, `matrix`,
`heatmap`.

### Known asymmetry

The bar chart and the table show the positive-outcome rate only; the stacked
bar, matrix and heatmap show both outcomes. Negative is 100 - positive, so the
five stay information-equivalent; it is a visual difference, not a payload one.

### Verification

`py_compile` and `pyflakes` on the two modules, the latter against HEAD so only
new warnings count — there are none. Not regenerated.

## Session: Idiom Review for Tasks 24-32, and Matrices Without Colour (2026-09-19)

### Problem solved

Three things, all in the visualization scripts:

1. **The idiom review removed nineteen images.** Tasks 24, 25 and 27-32 each
   offered idioms the review dropped. Unlike task01/task03, these are deleted
   rather than commented out: renderer, `IDIOMS` entry, `generate()` call and
   empty-state row all go, together with whatever helper, import or section
   banner had no other caller left.
2. **task27 ignored its own trace selection in six idioms out of nine.**
   `trace_ids` was resolved inside the chevron/BPMN/table path, so an admin who
   named traces got those three figures plus six that kept slicing the top
   fifteen variants — the figures contradicted each other.
3. **Every Matrix was a Heatmap that also printed its numbers.** The two idioms
   differed only in annotation, which encodes one variable twice and leaves a
   participant nothing to tell them apart by.

### Idioms removed

| Task | Removed | Left with |
|------|---------|-----------|
| task24 | flow chart & table | `flow_chart_elaborate` |
| task25 | flow chart & table | `flow_chart_elaborate` |
| task27 | scatterplot, flow chart & table, table & bar chart, gantt chart, flow chart+ & table, calendar | 9 idioms |
| task28 | flow chart & table, table & bar chart, flow chart+ & table, network diagram, scatter plot | 8 idioms |
| task29 | flow chart & table, table & bar chart, treemap | 8 idioms |
| task30 | table & bar chart | 6 idioms |
| task31 | scatterplot | 6 idioms |
| task32 | table & bar chart | 7 idioms |

A draft that has one of these selected keeps it selected; regenerating no longer
draws its image.

### Changes

| File | Change |
|------|--------|
| `scripts/tasks/task24.py` | Second idiom gone. The discovered model is no longer drawn as a graphviz DFG above the guideline BPMN: `_discovered_model_svg`, `_juxtapose`, `_svg_dims` and the base64 juxtaposition are removed and `task24_flow_chart_elaborate_bpmn` renders straight to its path. `_discover_dfg` stays — discovery is what produces the annotation (faded nodes, dark violation endpoints, the summary line), it is just not drawn as a second notation. Follows task35, whose Petri-net and DFG variants went for the same reason. |
| `scripts/tasks/task25.py` | Second idiom gone; `_draw` loses its `with_table` branch. |
| `scripts/tasks/task27.py` | Six idioms gone. The trace selection resolves once in the new `_selected_indices` and, when the admin **names** traces, `_selected_variant_df` gives every idiom one row per named trace — `build_variant_df`'s schema, so the renderers are unchanged and only their wording branches; `count` stays the frequency of that trace's behaviour in the whole log. Under the automatic rule the frequency and distribution idioms keep aggregating over the log's variants: that rule picks one trace per status by default, and a box plot of one value per group has no distribution to show. |
| `scripts/tasks/task28.py` | Five idioms gone, including the `if ctx is not None:` guard whose only statement was one of the calls. |
| `scripts/tasks/task29.py`, `task30.py`, `task31.py`, `task32.py` | Three / one / one / one idiom gone. |
| `scripts/shared.py` | `draw_value_heatmap` gains `colorless=False` — white cells, the value carried by the printed number alone, no colorbar. New `draw_cell_grid` rules an `imshow` grid into cells, which is what makes a colourless matrix a table rather than floating numbers. `draw_rate_matrix` passes the flag through. Defaults are the current behaviour, so no other caller moves. |
| `scripts/tasks/task27.py` … `task31.py` (matrices) | Matrices in tasks 27-31 draw `colorless=True`. task27's matrix is categorical, so colour was its whole payload: the four relations now print as letters (`C` contained, `L` unexpected log move, `M` skipped model move, blank absent) with a text key instead of a colour legend. A colour ramp over four nominal categories ranked them anyway. |
| `scripts/create_all_visualizations.py` | `_TASK_RENAME_SKIP` loses task28 and task31, which no longer write a `scatter_plot` file. |

### Docs

| File | Change |
|------|--------|
| `docs/TASK_IDIOM_MAPPING.md` | The eighteen rows for the removed idioms. |
| `docs/TRACE_ALIGNMENT_CLASS.md` | task27's per-task notes: a named selection reaches every idiom, the automatic rule does not, and why. "eleven renderers" read the threshold → four, plus the trace frame and the selection. The baseline counts are marked as predating this change. **task28 and task09 no longer offer the same idiom set** — trimming task09 to match is the open half of that decision. |
| `docs/TRACE_ALIGNMENT_PARAMETERS.md` | `conformant_threshold` stays visible under a manual selection, but not for the reason given ("ten idioms colour whole-log variants by it, none depend on which traces were chosen"); replaced with what the two modes actually do. |
| `docs/AGGREGATE_FITNESS_CLASS.md` | task25 is a single `flow_chart_elaborate`. |
| `docs/STANDALONE_TASK_PARAMETERS.md` | "The juxtaposition" → "…, and why it is gone again", with the DFG-drawn / DFG-computed distinction. |
| `docs/VIOLATION_PROFILE_CLASS.md` | The reproducibility fix lived in a deleted function; the rule it stands for — never sort a set by a key that leaves ties — is kept. |

### Verification

Whole dataset regenerated and compared against HEAD with `svg_compare.py`, both
runs sharing one `cache/alignments.pkl` so pm4py's equally-optimal alignments
cannot show up as a difference:

```
HEAD 265 SVGs → 246 SVGs;  19 removed, 0 added
246 in common: 241 byte-identical, 5 changed
  ~ task24/flow_chart_elaborate.svg   (the DFG panel is gone)
  ~ task27/matrix.svg  task28/matrix.svg  task29/matrix.svg  task30/matrix.svg
```

The colourless cells are checked by decoding each matrix's embedded PNG rather
than by reading fill attributes, since `imshow` puts the cell colours in the
raster: every one is a single colour, pure white, where HEAD had three to six
plus a 186-255 colour colorbar strip. task31's matrix takes its empty-state path
on BPIC12 (fewer than two populated fitness bands), so that one was rendered
separately from synthetic data.

`pyflakes` over the touched modules reports **no warning that HEAD did not
already report**. Four helpers that were dead before this session
(`_task28_status_color`, `_as_float`, `_trace_attribute_value`,
`_task31_collect_table_rows`) are deliberately left alone.

## Session: task03 Asks About Overall Behavior; Readable Boolean Buckets (2026-09-19)

| File | Change |
|------|--------|
| `provibackend/ProViBackend/app/seed_data.py` | task03's description matches its question (already "overall behavior", from Tasks and Idioms.pdf): compare the groups over the chosen attributes, throughput time by default — no longer "which group is slower". |
| `provibackend/ProViBackend/scripts/tasks/task03.py` | Module docstring and `RUBRIC` follow the question: any compared attribute, throughput time as the default. |
| `provibackend/ProViBackend/scripts/trace_features.py` | `as_bucketable(..., key=)`: a `contains::X` boolean buckets as "With 'X'" / "Without 'X'" instead of a bare Yes / No. |
| `scripts/tasks/task03.py`, `tasks/task13.py`, `trace_response.py` | Pass the key. task30 and `violation_profile` prefix every label with the attribute already, so they keep Yes / No. |

`py_compile` only; not rendered.

## Session: task02 Idioms Show the Same Information (2026-09-19)

| File | Change |
|------|--------|
| `provibackend/ProViBackend/scripts/tasks/task02.py` | Table reduced to Mean Fitness and Fitness Threshold, what the tile and bar chart show; its trace counts and "% conformant" (cut at 1.0 beside a 0.8 threshold) are gone. Bar chart: the threshold label sat on the navy bar, dark on dark — it moves to a legend below the axes, and the dashed line gets a white outline so it shows across the bar. |
| `docs/AGGREGATE_FITNESS_CLASS.md` | §2 matches: the table's threshold is a column, the bar chart's is named in a legend, and the three idioms carry the same two numbers. |

`py_compile` only; not rendered.

## Session: task01 Idioms Show the Same Information (2026-09-19)

### Problem solved

task01's idioms showed different data: the bar chart only each group's mean
fitness, the table counts, % conformant and the mean, the matrix, stacked bar
and parallel sets counts per fitness category. Participants given different
idioms were given different information, not the same information drawn
differently. Counts also made the larger group look better.

### Changes

| File | Change |
|------|--------|
| `provibackend/ProViBackend/scripts/tasks/task01.py` | One kernel, `_task01_category_counts`: per group, traces in Major (<0.8) / Minor (0.8–<1.0) / Conformant (=1.0). Every idiom but the box plot draws its within-group shares, with `n` in the group label. Bar chart → grouped bars per category; table and table + bar chart → `count (share%)` per category (mean fitness dropped); stacked bar → 100% stacked; parallel sets → equal-height groups; matrix → row shares on a fixed 0–100% scale. Category colours: Major yellow, Minor ochre, Conformant navy — yellow is low fitness, and both deviation categories stay on cividis's yellow end so deviating vs conformant reads as yellow vs blue (the slate blue `categorical_colors(3)` gives Minor drew a log without major deviations all blue). `_task01_group_stats` removed. |
| `provibackend/ProViBackend/scripts/shared.py` | The colour-direction comment: yellow is the low end of what is encoded, so fitness categories run yellow (deviating) → navy (conformant). |

The box plot is unchanged and cannot show this: it draws quantiles, and with
most fitness values at exactly 1.0 its boxes collapse. It stays in `IDIOMS`.
task04 at log level draws task01's figures, so it changes with them.

### Verification

`py_compile` only. Not rendered: check the /idiom previews after deploying.

## Session: Custom Idioms Belong to Their Experiment (2026-09-19)

### Problem solved

A custom idiom was a global `Idiom` document bound only to tasks, so every
later experiment offered it for those tasks — test uploads included — and no
page could remove one.

### Changes

| File | Change |
|------|--------|
| `provibackend/ProViBackend/app/datamodels/data_schemas.py` | `Idiom.experiment_id`. |
| `provibackend/ProViBackend/app/routers/admin.py` | `POST /idioms/upload` requires `experiment_id` and records it. `/task-idioms` offers a custom idiom only to its experiment; older ones (no `experiment_id`) only where already selected or bound to the experiment's own custom task. Deleting an experiment deletes the custom idioms uploaded in it. |
| `ProViFrontend/provi-frontend/src/components/Admin/UploadIdiomModal.js`, `src/app/admin/experiments/idiom/page.js` | The modal posts the experiment id and says the idiom belongs to this experiment. |

`docs/ADMIN_EXPERIMENT_SETUP.md` gains *Custom idioms*.

### Verification

`py_compile` and `eslint` on the changed files. Not run end to end. Nothing is
deleted from the database: an experiment already using a custom idiom — a
published one included — resolves it by id as before.

## Session: Grey-Free Idiom Colours, First Five Tasks (2026-09-19)

### Problem solved

The palette guide moved every chart to cividis, but cividis is nearly neutral
grey in its middle, and the stops the tasks used sit there: `GREY_MED` (0.45) is
`#727274`, saturation 0.01. Group comparisons, move types and category ramps
therefore still drew in grey. The eight tasks of the published experiment are
left as they are; this starts the others.

### Backend (`provibackend/ProViBackend/scripts/`)

| File | Change |
|------|--------|
| `shared.py` | New `PAIR_COLORS`, `MOVE_LOG` / `MOVE_MODEL` / `MOVE_MISMATCH` / `MOVE_SYNC` and `categorical_colors(n)`, all sampled outside cividis's grey middle; `GREY_*` values unchanged. `render_conformance_line_graph` takes `line_color` / `mean_color` (defaults = the old grey, which task10 keeps). `draw_grouped_box_plot` picks each median line's colour for contrast with its box — white vanished on a yellow box; no frozen task calls it. |
| `tasks/task01.py` | Positive / Negative blue / yellow; conformance categories `categorical_colors(3)`. |
| `tasks/task02.py` | The single bar is blue. |
| `tasks/task05.py` | Sub-logs blue / yellow; stacked-bar segments and the parallel sets' right axis `categorical_colors`; box-plot jitter points neutral dark. |
| `tasks/task07.py` | Line graph blue with a neutral mean line; horizon chart already blue / yellow. |
| `tasks/task08.py` | Network nodes by `MOVE_*`, edges on cividis's blue end instead of `plt.cm.Greys`; matrix cell text by `contrasting_text_color`. |

### Docs

The rule — data colours come from cividis's blue and yellow ends, grey only for
axes, borders, text, reference lines and empty cells, the eight frozen tasks
untouched — is recorded in the comment above the new constants in `shared.py`.
(`PALETTE_GUIDE.md` has the same as §0, but that file is git-ignored.)

### Verification

- `py_compile` over the changed files. The eight frozen tasks are unaffected by
  construction: no `GREY_*` value changed, the line graph's defaults are the old
  colours, and none of them calls `draw_grouped_box_plot`.
- **Not rendered:** the new colours are to be checked on the /idiom previews after
  deploying.

### Known gaps

- `categorical_colors(n)` for n ≈ 10 puts its first three blues close together;
  task05's stacked bar can have 11 segments (top 10 + Other).
- Box-plot whiskers keep the box colour, so yellow whiskers are faint on white.

## Session: Idiom Previews Drawn by the Current Code (2026-09-19)

### Problem solved

The preview on the idiom step served SVGs committed to the repo on 2026-07-19
(12 tasks, exported from a container by `export_idiom_previews.sh`), and marked
those tasks ready at startup without ever drawing them. The task modules have
changed substantially since, so an admin choosing idioms saw July's drawings,
while the Overview page — and participants — saw the current generator's
output.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Previews are only ever drawn at runtime, into a container-local cache that every image rebuild empties. `prewarm_idiom_previews` draws all tasks one after another; `_claim_idiom_preview` (under a lock) keeps it and admin requests from drawing the same task twice. Sample-dataset check factored into `_sample_dataset_ready`. Preview SVGs are served with `Cache-Control: no-cache`. |
| `ProViBackend/app/main.py` | Starts the prewarm in a daemon thread once the sample dataset exists. |
| `ProViBackend/scripts/sample_data/output/__idiom_preview/` | **Deleted** (84 committed SVGs); now in `.gitignore`. |
| `scripts/export_idiom_previews.sh` | **Deleted** — it existed to commit those SVGs. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/idiom/page.js` | The page text, the preview button's tooltip and a note in the preview modal say what a preview is: roughly how the idiom looks, drawn from a bundled BPIC 2012 loan-application log with default parameters, not the admin's dataset — the real images come from generating on the Specify step. The note is left out for custom idioms, whose preview is the real image. |

### Docs

`docs/ADMIN_EXPERIMENT_SETUP.md` (*Idiom previews on /idiom*).

### Verification

- `py_compile` over the changed Python files.
- **Not verified end to end:** the prewarm's duration and its effect on
  request latency right after a deploy are unmeasured; its log lines
  (`[idiom-preview] … in Ns`, `prewarm finished in Ns`) report both on the
  server.

### Known gaps

- Still the sample dataset with default parameters, not the experiment's own
  dataset — a preview shows how an idiom is drawn, not this experiment's data.
- Generation shares the interpreter with request handling; the prewarm runs one
  task at a time with a pause, but requests may still be slower until it ends.

## Session: Idiom Import Checks Dataset and Parameters (2026-09-19)

### Problem solved

- **Importing required generating first.** Import lived on the Overview page,
  but /specify's Next only unlocks once every task is `ready`. An admin
  reproducing a study had to set parameters and generate images only to replace
  them a step later — and the wizard gave no hint that import existed at all.
- **Imported images kept the wrong parameters.** Import pinned the images but
  left the experiment's parameters as set on /specify. The participant-facing
  parameter hints and any later export were built from those, so both could
  describe something other than what the images showed.
- **Nothing checked where images came from.** A zip from an experiment on
  another dataset, or drawn with other parameters, was imported as long as the
  task and idiom keys matched.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/idiom_bundle.py` | Import takes `mode=specify\|overview` and checks each task before taking its files: rejected if exported from another dataset (by log/guideline checksum, or dataset id for version-1 manifests); in `overview` mode also if its parameters differ (differences listed). `specify` mode writes the zip's parameters onto the task. Imported tasks get `images_imported_from`; reverting clears it. A manifest is now required. Export writes manifest version 2 with each task's dataset title and checksums. The response lists `imported` and `rejected` (was `skipped`) plus `dataset_mismatch`. |
| `ProViBackend/app/routers/admin.py` | `PATCH /experiments/{id}` keeps an imported task's parameters and marker whatever the caller sends (`_keep_imported_parameters`). Generation skips tasks whose every idiom shows an uploaded image (`_fully_uploaded_task_ids`), neither validating nor re-running them; if that is every task, it returns without starting a job. |
| `ProViBackend/app/datamodels/data_schemas.py` | `TaskInstance.images_imported_from`. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/components/Admin/IdiomImport.js` | **New.** Import button (posts with a mode) and result view: imported files, rejected files with reasons, a dataset warning, and — for parameter rejections on Overview — a pointer to the Specify step. |
| `src/app/admin/experiments/specify/page.js` | "Images from an earlier experiment" card: import (`specify` mode), count of imported tasks, *Discard import*. Imported tasks show a lock notice and read-only parameters. Generate leaves imported, ready tasks alone and is disabled once every task is imported. |
| `src/app/admin/experiments/overview/page.js` | Import uses `overview` mode with the new result view and says which images it accepts. Replacing a single image asks for confirmation. Preview fallback text no longer points at the removed idiom selection page. |
| `src/components/Admin/UploadIdiomModal 2.js` | **Deleted** — an unreferenced Finder duplicate of `UploadIdiomModal.js`. |

### Docs

`docs/ADMIN_EXPERIMENT_SETUP.md` (data model, *Generation*, *Idiom images*).

### Verification

- `py_compile` over the changed Python files; `eslint` over the changed JS
  files — no new findings (the `react/no-unescaped-entities` errors in
  `overview/page.js` are the pre-existing ones in the publish-conflict dialog).
- **Not verified end to end:** no endpoint or page was run locally; testing
  happens on the `develop` deployment.

### Known gaps

- Zips exported before this change are version 1 and carry no checksums, so
  they only import into an experiment on the same server using the same
  dataset id; exporting again from the source experiment produces a version-2
  zip.
- *Discard import* reverts every uploaded image of the experiment, including
  single replacements made on the Overview page.
- An experiment's dataset can still be changed after an import; the lock does
  not re-check it, so the imported images would then no longer match.

## Session: Configurable Intro Pages, Idiom Image Export/Import (2026-09-18)

### Problem solved

- **The intro pages were hard-coded.** *Key Concepts* (`/conformance-terms`)
  and *Before You Begin* (`/taskintro`) were fixed JSX tied to the
  order-to-cash dataset, with a fixed citation. An experiment on another
  process showed participants the wrong diagram and definitions, and the only
  way out was editing code.
- **Stimuli were not reproducible.** Idiom images existed only as generator
  output on the server. Regenerating after the generator code changed (as the
  violation-profile refactor did to seven tasks) silently changed what
  participants saw, and there was no way to archive the images a study used or
  load them into another experiment.
- **Custom idiom assets did not survive a deploy.** They were written to
  `app/static/custom_idioms`, inside the container rather than on the
  `/srv/provi-data` volume, so every redeploy that rebuilt `provibackend` lost
  them while their `Idiom` records stayed. (Checked on the server before this
  change: the directory did not exist and no custom `Idiom` records existed, so
  nothing had been lost yet.)

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/datamodels/data_schemas.py` | `Experiment` gains `concept_sections`, `taskintro_sections`, per-page `*_citation_enabled` / `*_citation_text`, and `process_model_ext`; defaults reproduce the old pages. New `IntroPageSections` request model. |
| `ProViBackend/app/routers/admin.py` | `PATCH /experiments/{id}/intro-pages`; `POST`/`DELETE`/`GET /experiments/{id}/process-model`. The overview preview (`/experiments/{id}/vis/…`) shows an uploaded image first. Deleting an experiment removes its process model image and idiom overrides. Custom idiom assets served as `image/jpeg` instead of the invalid `image/jpg`. |
| `ProViBackend/app/routers/idiom_bundle.py` | **New.** Export an experiment's images as a zip with a manifest; import one into any draft experiment, matched by `task_key`/`idiom_key`; replace or revert a single image; list and revert all overrides. |
| `ProViBackend/app/routers/participant.py` | `GET /participant/intro-pages` and `/participant/process-model` for the active experiment. Image and `traces.json` resolution goes through `utils/idiom_files`, so uploaded images win. |
| `ProViBackend/utils/idiom_files.py` | **New.** The one place deciding which file is shown for an idiom (upload → custom asset → generated → legacy); override storage; moves custom idiom assets out of the old location at startup. |
| `ProViBackend/utils/config.py` | `CUSTOM_IDIOM_DIRECTORY` moves to `data/_custom_idioms`; new `IDIOM_OVERRIDE_DIRECTORY` and `PROCESS_MODEL_DIRECTORY`, all on the volume. |
| `ProViBackend/utils/utils.py` | `process_model_path`, `image_media_type`. |
| `ProViBackend/app/main.py` | Registers `idiom_bundle`; runs the custom idiom move at startup. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/concepts/page.js` | **New wizard step** (after `/knowledge`): sections of both intro pages, per-page citation toggle and text, process model upload. Shows the participant flow and marks pages that will be skipped. |
| `src/utils/introPages.js` | **New.** Section lists, defaults, fetching the config, and where each intro page leads when its neighbour is skipped. |
| `src/components/General/ProcessModelImage.js`, `IntroCitation.js` | **New.** The diagram (uploaded image via `<img>`, so scripts in an SVG never run) and the citation box, shared by both pages and the admin preview. |
| `src/app/conformance-terms/page.js`, `src/app/taskintro/page.js` | Render only the configured sections; skip themselves when empty; text that pointed at another section or at order-to-cash follows what is actually shown. |
| `src/app/knowledgequestion/page.js` | Goes on to the first intro page that is enabled; the button names it. Combined with develop's "no knowledge questions" skip. |
| `src/app/admin/experiments/overview/page.js` | *Idiom Images* panel (download, import, revert all, import report); per-idiom replace/revert and an "Uploaded" badge. |
| `src/app/admin/experiments/specify/page.js` | Confirms before generating when uploaded images exist, since they stay in place. |
| `src/app/admin/page.js` | `concepts` in `WIZARD_STEPS`; idiom download link on published/finished experiments. |
| `src/app/admin/experiments/knowledge/page.js` | Next leads to `/concepts`. |

### Docs

`docs/ADMIN_EXPERIMENT_SETUP.md` (workflow, *Idiom images*, *Intro pages*),
`docs/PARTICIPANT_TRIAL_CONTRACT.md` (*SVG resolution*).

### Verification

- `py_compile` over the changed Python files; `@babel/parser` and `eslint` over
  the changed JS files — clean apart from pre-existing
  `react/no-unescaped-entities` errors in `admin/page.js` and
  `overview/page.js` that this change did not touch.
- **Not verified end to end:** no endpoint or page was run locally; testing
  happens on the `develop` deployment.

### Known gaps

- Imported images are pinned: regenerating does not replace them until the
  admin reverts them. Intended, but a surprise if the /specify warning is
  dismissed.
- The manifest's `git_commit` is `null` until the deploy sets `GIT_COMMIT` for
  the backend.
- Custom tasks and custom idioms only match on import within the experiment
  and server they came from, since their keys are random.
- `.bpmn` files are not accepted as process models; only images.

---

## Session: DFG / Main-App Data Isolation (2026-09-14)

### Problem solved

`dfg-service` and the main app share one Mongo database (`TeamProject`) and one
nginx origin, so nothing but naming kept the two studies' data apart — and two
names still overlapped:

- DFG wrote participant answers and UI logs into `Answer` / `UILogging`, the
  same collections the idiom study uses. The main app's bulk exports
  (`generate_csv_for_download`, called with `query={}`) dump those collections
  whole, with no field identifying which study a row came from, so "download
  Answers" returned a CSV mixing both studies — with columns that shift
  depending on which rows are present, since the two answer schemas diverged in
  the 2026-09-09 refactor.
- Both apps set a session cookie named `provi_user_id`, neither with a `path`,
  on one origin — so whichever study a participant opened last owned the
  identity for the whole site. The main app's write endpoints take that cookie
  as `user_id` verbatim, so a participant who opened the DFG card on the landing
  page mid-study and came back had their next answer stored under a DFG user id:
  a row joinable to no `User` / `PreliminaryAnswers` / `KnowledgeAnswers`
  record, with no error raised.

Both leaks ran one-directionally into the idiom study's data, and both were
silent. Two rules now keep them closed: every DFG collection is prefixed `Dfg`,
and the two studies never share a cookie name.

### DFG service (`dfg-service/`)

| File | Change |
|------|--------|
| `backend/DfgBackend/utils/database/connection.py` | `create_answer` → `DfgAnswer`, `save_ui_logging_data` → `DfgUILogging`, completing the `DfgUser`/`DfgDataset` prefixing this service already applied elsewhere. **Deleted nine helpers** that wrote to the main app's collections — `create_user`, `create_dataset`, `update_dataset_is_active_status` (`User`/`Dataset`), `save_knowledge_answers` (`KnowledgeAnswers`+`User`), `create_experiment`, `get_experiment`, `update_experiment`, `get_user_assignment`, `update_trial_index` (`Experiment`/`UserAssignment`): all uncalled by any DFG router, but one stray call away from writing into the other study. Header comment records the prefix rule. |
| `backend/DfgBackend/app/routers/admin.py` | Its two CSV exports read `DfgAnswer` / `DfgUILogging` to match the renamed writes. |
| `backend/DfgBackend/app/routers/auth.py` | Session cookie issued as `dfg_user_id` instead of `provi_user_id`; `GET /auth/test` reads the new name. Comment records why a shared cookie name is unsafe here. |
| `backend/DfgBackend/app/routers/vis.py`, `questionnaire.py`, `ui_tracking.py` | Read `dfg_user_id`. No frontend change was needed — `dfg-service/frontend` never names the cookie, relying on `credentials: "include"`. |

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/utils/database/connection.py` | **New `user_exists(user_id)`** — true only when this app issued the id (a `User` document exists for it). |
| `ProViBackend/app/routers/questionnaire.py`, `app/routers/auth.py`, `app/routers/participant.py` | The four endpoints that write cookie-keyed data — `POST /survey/answer`, `POST /auth/knowledge`, `POST /auth/feedback`, `POST /participant/assignment` — now return 401 on a cookie this app did not issue. Belt-and-braces after the rename; what it actually catches is a pre-rename `provi_user_id` cookie still sitting in a participant's browser (they live one day). `POST /participant/complete` needed nothing: it already 404s when no assignment exists. |
| `nginx/nginx.conf` | Comment on the `/dfg/` blocks rewritten — it previously documented the shared `provi_user_id` cookie as intended behaviour, which is exactly what this session removed. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/components/Task/TaskAnswerPanel.js` | `submitWithRatings` advanced the trial from a `finally` block, so a failed `POST /api/survey/answer` — a 500, a dropped connection, or the 401 added above — discarded the participant's answer, cleared the form and moved on, recording the loss only as a `console.error`. Now the trial advances only after a 2xx; a failure leaves the rating modal open with the answer and both ratings intact, shows what went wrong, and turns the button into "Try again". `response_time_ms` is still the value captured on first click, so retrying does not inflate it. Needed for the 401 above to be visible rather than silent. |

### Verification

- `py_compile` over all ten changed Python files — clean.
- `eslint` on `TaskAnswerPanel.js` — clean apart from one pre-existing
  `react-hooks/exhaustive-deps` warning about `options`, untouched by this change.
- Re-grepped `dfg-service/backend` for `provi_user_id`, `"Answer"` and
  `"UILogging"` after the edits: only the explanatory comment in `auth.py` is
  left.
- Confirmed each of the nine deleted helpers was uncalled anywhere in
  `dfg-service/backend`, and that `dfg-service/frontend` never references the
  cookie by name.
- **Not verified end to end:** nothing was run against a live Mongo or a
  browser. Neither study's participant flow was exercised after the change.

### Known gaps

- Rows written *before* the rename are still in `Answer` / `UILogging` and will
  still appear in the main app's bulk exports. They are identifiable — a row is
  DFG's if its `user_id` is present in `DfgUser` — but were left untouched,
  since moving or deleting them is a call on live data. Needs a one-off script
  in the style of `scripts/drop_ground_truth_data.py` (`--dry-run` / `--yes`).
- The retry path in `TaskAnswerPanel.js` was reasoned through but not exercised
  in a browser — no failing-backend scenario was actually played out against the
  running app.
- The cookie rename invalidates any in-flight DFG session on deploy, and the
  `test_cookie_ssl` / `_strict` / `_lax` dev routes in `provibackend`'s
  `auth.py` now hand out cookies that the four guarded endpoints reject.

---

## Session: DFG Study Extracted Into a Standalone Service (2026-09-10)

### Problem solved

The previous team's DFG (Directly-Follows-Graph) tool had lived inside
`provibackend` / `ProViFrontend` since the repo's initial commit (`9967cb4`,
2026-03-09), sharing their dependencies, routers and build. The idiom study has
since grown its own task / idiom / answer-format model around those same files,
so neither study could be changed or deployed without touching the other. The
DFG study is still needed, so it was moved out intact rather than deleted.

Done copy-first: the code was duplicated into `dfg-service/` and made to work
there (Phase 1) before being removed from the main project (Phase 2), so the
main app was never left broken by a half-finished move.

### New service (`dfg-service/`)

| Commit | Change |
|--------|--------|
| `055ebc1` | **Phase 1 — copy.** `dfg-service/backend/DfgBackend` (FastAPI plus `FilterModel/`, `MentalMapModel/`) and `dfg-service/frontend` (Next.js: graph view, sliders, questionnaire) created as copies — 59 files. `docker-compose.yml` gains `dfgbackend` / `dfgfrontend`; `provibackend/nginx/nginx.conf` gains the `/dfg/`, `/dfg/api/` and `/dfg/api/admin/` blocks. |
| `ced5edc`, `d0d586d` | Deps missing from the copied `package.json`, each surfacing at build time: `react-zoom-pan-pinch`, `@mui/icons-material`, `@coreui/react`, then `autoprefixer`. |
| `dfbede8` | The dataset upload/activation pipeline had been dropped in the copy; restored. |
| `b150a39` | The copied admin page had been replaced by a placeholder test page; the previous team's real one restored. |
| `dcc23d5` | Static assets 404'd. Fixed by `basePath: "/dfg"` in `next.config.mjs` plus nginx's `/dfg/` block **not** stripping the prefix — unlike the `/dfg/api/` blocks, which must strip it. |
| `7c574fb`, `ca4492f` | Previous team's original ProVi logo and favicon restored. |

### Removed from the main project

| Commit | Change |
|--------|--------|
| `18618a4` | **Phase 2 — delete**, once the standalone service worked: 22 files, 2440 lines. From `provibackend`: `ProViBackend/FilterModel/` (7 files), `ProViBackend/MentalMapModel/` (3 files), `app/routers/vis.py`, `app/routers/ui_tracking.py`. From `ProViFrontend`: `app/home/page.js`, `components/Graph/*` (4 files), `components/Questionnaire/*` (2 files), `components/General/Navigation.js`, part of `ExpNavigation.js`, and the deps they were the only users of in `package.json`. |

### Known gaps

- `dfgbackend`'s volume mount maps the host's `/srv/provi-data` to
  `/code/DfgBackend/data`, but the service writes uploads and generated SVGs to
  `/code/DfgBackend/output` — an unmounted path. The mount therefore does
  nothing, and because `.github/workflows/deploy.yml` force-removes the
  `dfgbackend` container on every deploy, DFG's datasets and SVGs are wiped each
  time and have to be re-uploaded and re-activated.
- `dfg-service`'s copies of the shared data models are frozen at extraction
  time and will drift from `provibackend`'s as it evolves; the same model name
  in the two services no longer implies the same shape.
- Data isolation between the two studies was not addressed here — the two apps
  still shared collections and a cookie name. See the 2026-09-14 entry.

---

## Session: Answer-Format Refactor — Formats Decoupled from Tasks, Grading Removed (2026-09-09)

### Problem solved

Answer formats were a per-task whitelist (`ANSWER_FORMATS`), and the option set a
participant chose from was computed by the same code that decided which option was
correct (`compute_ground_truth`). That coupled three things that should be
independent: what a task draws, how its question is answered, and whether an answer
is right. It also meant a task could only use the formats its module happened to
declare — 17 of 37 tasks declared none at all.

Automatic grading is removed entirely (answers are recorded, analysed later by hand),
formats are global (any task may use any format), and option sets are authored by the
admin — imported from the event log or typed in. Grading rubrics are kept unchanged:
they never fed automatic scoring, they are reference text for manually coding
free-text answers.

Formats consolidated 11 → 7: `yes-no` folded into `mc-single`; `pct`/`count`/`decimal`
into `number` with a `number_kind` setting; `pct-set`/`count-set` into `number-set`;
`rank` — implemented but never used by any task — becomes available for the first time.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `app/answer_formats.py` | **New file.** The global format registry: 7 formats with widget + `needs_options` + `numeric`, `NUMBER_KINDS`, and the `widget_for` / `needs_options` helpers. Replaces the per-task `ANSWER_FORMATS` whitelist. |
| `app/scoring.py` | **Deleted** (129 lines). Answers are no longer scored. |
| `app/datamodels/data_schemas.py` | `OptionItem` loses `correct`. `GroundTruthBlock` and the legacy `GroundTruth` model deleted. `TaskInstance.ground_truth` → `answer_options: List[OptionItem]`, plus `number_kind`. `Answer.is_correct`, `Answer.ground_truth_id` and `PreliminaryAnswers.ground_truth_id` removed. |
| `app/routers/admin.py` | Added `GET /admin/answer-formats` (global), `GET /admin/datasets/{id}/option-sources` and `GET /admin/datasets/{id}/option-candidates` (with `pairs=true` for matrix upper triangles). Removed `GET /admin/tasks/{key}/answer-formats`, `POST /admin/groundtruth`, `_build_gt_block`, `_resolve_answer_format`, and the ground-truth branch of the generation job. `/tasks/{key}/rubric` kept, minus `gt_tier`. Export drops the `ground_truth` column. |
| `app/routers/participant.py` | `_participant_options` collapses to pass-through plus the `rank` shuffle (now justified by presentation-order bias, not by hiding an answer). Sends `number_kind`; stops sending `decisive`. |
| `app/routers/questionnaire.py` | Submit no longer grades: `_lookup_ground_truth` and the `scoring` call removed. |
| `scripts/create_all_visualizations.py` | Generation only draws — the `compute_ground_truth` loop and the per-task module table are gone. Added `get_log_time_bins` + the shared `_trace_start_timestamps` reader. Removed the `--high-cooccurrence-threshold` and `--target-violation` CLI flags and their (dead) wiring. |
| `scripts/tasks/*.py` | Across 20 modules: `ANSWER_FORMATS`, `GT_TIER` and the 16 `compute_ground_truth` functions (~950 lines) removed, plus the two helpers only they used. All 11 `RUBRIC` constants kept as-is. task08's `high_cooccurrence_threshold` removed — it only ever flagged matrix cells correct and affected no drawing. |
| `scripts/tasks/task_registry.py` | Lost `get_answer_formats`, `get_gt_tier`, `get_compute_ground_truth` and their defaults. The task contract is now `IDIOMS` / `PARAM_SPEC` / `validate_params` / `RUBRIC`. |
| `scripts/drop_ground_truth_data.py` | **New file.** One-off cleanup: unsets the ground-truth fields on experiments and answers, drops the `GroundTruth` collection, and clears `answer_format` (every stored key was retired). `--dry-run` / `--yes`; idempotent. |
| `utils/database/migration.py` | Task-instance defaults follow the new shape (`answer_options: []`, `number_kind: None`). No conversion — existing data is discarded. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/answer-format/page.js` | **New file**, replacing `answer-format-groundtruth/` (802 → ~630 lines). The six ground-truth editors collapse into one `OptionsEditor` serving every option-bearing format: import from an event-log source (with a granularity picker for time bins and an axis size for matrices) or author rows by hand, reorder, delete. Adds `NumberKindSelector`, and carries over develop's editable, DB-backed `RubricEditor` so the rubric shows (and can be edited) for every format, not just free-text. |
| `src/app/admin/experiments/overview/page.js` | `GroundTruthSummary` splits into `AnswerSummary` (option preview) and `RubricSummary`. The Decisive/Reference badge becomes option-count and number-kind chips. The publish gate now also requires options wherever the format needs them. |
| `src/app/admin/experiments/specify/page.js` | Redirects to `/answer-format`. |
| `src/components/Task/AnswerWidgets.js` | `numericMeta` keys off `number_kind` instead of the retired numeric formats. The `yes-no` special case in the `single_choice` dispatcher is gone. |
| `src/components/Task/TaskAnswerPanel.js`, `src/app/taskexecution/page.js` | Thread `number_kind` through in place of `answer_format`. |

### Documentation

| File | Change |
|------|--------|
| `docs/ADMIN_EXPERIMENT_SETUP.md` | **New file**, replacing `ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md`. Describes the setup workflow as built rather than as planned. |
| `docs/PARTICIPANT_ANSWER_WIDGETS.md` | **New file**, replacing `PARTICIPANT_ANSWER_WIDGETS_PLAN.md` — the widgets as built. |
| `TASK_GT_DEVELOPMENT_GUIDE.md` | **Deleted.** Ground-truth authoring no longer exists. |
| `docs/PARTICIPANT_TRIAL_CONTRACT.md` | Format catalogue 11 → 7; `decisive` replaced by `number_kind`; grading notes removed. |
| `docs/TASK_CONTRACT_PROMPT.md` | Rewritten as a PARAM_SPEC-only authoring prompt, with an explicit "not in scope" section for the removed attributes. |
| 17 code comments | `ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §N` references repointed at `docs/ADMIN_EXPERIMENT_SETUP.md`. |

### Verification

- All 37 tasks rendered against `data/test` (BPIC12, 13087 traces) with this code and
  with the pre-refactor code from a git worktree, over the same dataset directory and
  alignment cache. Two identical runs first identify 18 nondeterministic SVGs (network
  diagrams, Petri-net/BPMN layouts, alignment-order-dependent renderers); of the 244
  deterministic ones, **244/244 are byte-identical** after normalising SVG ids and dates.
- `/answer-format` driven end to end in a real browser against the live option-candidate
  endpoints: format selection, import (10 activities from BPIC12), the publish gate
  blocking on missing options, and the saved payload carrying no legacy field.
- `drop_ground_truth_data.py` exercised against an in-memory Mongo with legacy documents,
  including idempotence on a second run.

### Known gaps

- 18 SVGs differ between two identical renders. Pre-existing and unrelated to this
  change, but it blocks any visual regression testing until fixed.
- `rank` has never run against real data — no task ever declared it. Worth exercising
  once before relying on it.

---

## Session: Knowledge Questions — Full DB Implementation (2026-06-11)

### Problem solved

Knowledge questions were hardcoded in the frontend. Admins had no way to add new questions or configure which questions each experiment uses without touching the source code.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `app/datamodels/data_schemas.py` | Added `KnowledgeQuestion` and `KnowledgeQuestionCreate` models. Added `KnowledgeQuestionIds` model. Updated `KnowledgeAnswersRequest` to `{answers: Dict[str, int], tools: List[str]}` (server-side scoring). Added `knowledge_question_ids: List[str] = []` field to `Experiment` (empty = all system questions). |
| `app/seed_data.py` | Added `CANONICAL_KNOWLEDGE_QUESTIONS` with the 6 existing hardcoded questions seeded as `is_system=True`. |
| `app/main.py` | Imported `CANONICAL_KNOWLEDGE_QUESTIONS`; added seed call for `KnowledgeQuestion` collection on startup. |
| `app/routers/admin.py` | Added `GET /admin/knowledge-questions`, `POST /admin/knowledge-questions`, `DELETE /admin/knowledge-questions/{id}` (system questions protected, 409 if referenced by experiments), `PATCH /admin/experiments/{id}/knowledge-questions` endpoints. |
| `app/routers/participant.py` | Added `GET /participant/knowledge-questions` (active experiment, strips `correct_option_index`). Added `GET /participant/experiment/{id}/knowledge-questions` (admin preview). |
| `app/routers/auth.py` | Updated `POST /auth/knowledge` to accept `{answers: {qid: optionIndex}, tools: [...]}`. Score computed server-side by comparing submitted indices against `correct_option_index` in DB. Stored format (`notes`, `score`, `level` in `KnowledgeAnswers`) unchanged for CSV export compatibility. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/experiments/knowledge/page.js` | **New file.** Wizard step 2 between `/new` and `/task`. Lists all KQ with checkboxes (system + custom sections). "Add Question" opens a modal to create a new DB question with 2–6 options, optional "I don't know" toggle, and correct answer selection. On "Next", PATCHes the experiment with selected question IDs. |
| `src/app/admin/experiments/new/page.js` | Changed post-create redirect from `/admin/experiments/task` to `/admin/experiments/knowledge`. |
| `src/app/admin/page.js` | "Continue Editing" for experiments without task configs now points to `/admin/experiments/knowledge` instead of `/admin/experiments/task`. |
| `src/app/knowledgequestion/page.js` | Replaced hardcoded question array with dynamic fetch from `GET /api/participant/knowledge-questions`. Answers submitted as `{answers: {question_id: option_index}, tools: [...]}` instead of pre-computed `{notes, score, level}`. Questions grouped by `section_title` from DB. |

---

## Session: Scrollable Dataset Tables (2026-06-11)

### Problem solved

Both dataset display surfaces lacked consistent scroll behaviour when the dataset list grew long.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | Added `max-h-72 overflow-y-auto pr-1` to the table wrapper so the Choose Dataset(s) table on `/admin/experiments/new` scrolls vertically beyond 288 px. Added `sticky top-0 bg-surface-container-lowest z-10` to `<thead>` so column headers remain visible while scrolling. |

*Note: the `/admin` Datasets list already had `max-h-72 overflow-y-auto pr-1` from the Datasets Section Redesign session.*

---

## Session: Timestamp Timezone Fix (2026-06-11)

### Problem solved

Dataset upload timestamps were displaying in UTC instead of the admin's local (Berlin) time. Root cause: the backend stores naive UTC datetime strings (e.g. `"2026-06-11 12:32:00.123456"`) without timezone info. JavaScript's `new Date()` treats space-separated datetime strings as local time rather than UTC, so no UTC→local conversion was applied and the times appeared 2 hours behind CEST.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Updated `formatDateTime`: replaces the space separator with `T`, then appends `Z` if no timezone offset is already present (checked via `/Z$\|[+-]\d{2}:?\d{2}$/`). `new Date()` now parses the value as UTC and `getHours()`/`getMinutes()` output the browser's local time — Berlin time for German admins, system time elsewhere. |
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | Same `formatDateTime` fix, so the "Uploaded:" timestamp in `/admin/experiments/new` is also timezone-correct. |

---

## Session: Experiment Manage Mode (2026-06-11)

### Problem solved

The Experiments section on `/admin` had no way to delete experiments. Admins needed a Manage mode (mirroring the Datasets section) with a two-phase delete flow that surfaces participant-data counts and offers a "Download data first" link before force-deleting.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | **New `DELETE /admin/experiments/{experiment_id}?force=false`**. Counts `UserAssignment`, `Answer`, and `UILogging` documents for the experiment. If `status != "draft"` **or** any count > 0 and `force=false` → returns 409 with `detail.experiment` (name, status) and `detail.counts` (assignments, answers, ui_logs). If `force=true` or a draft with no data → cascades `delete_many` across all three collections then deletes the `Experiment` document. Returns `deleted_counts` in the response body. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Added Manage mode to the Experiments right column, mirroring the Datasets left column: `expManageMode`, `selectedExpIds`, `expDeleteConfirmOpen`, `expForceConfirm` state; `toggleSelectExp`, `exitExpManage`, `performExpDelete`, `handleExpDeleteConfirmed`, `handleExpForceConfirmed` helpers. In Manage mode each experiment card shows a checkbox; action buttons (Continue Editing / Mark as Finished / Download Data) are hidden to avoid misclicks. Footer switches to `[Cancel] [Delete Selected (n)]`. Delete follows the same two-phase pattern as datasets: first confirm modal lists selected names with a note that draft-with-no-data experiments delete immediately; if any return 409, a second force-confirm modal shows per-experiment data counts (assignments · answers · UI logs) and a "Download data first ↓" link for experiments with answers > 0, warning that force delete permanently removes all participant data. Renamed dataset manage state vars to `dsManageMode`/`selectedDsIds` to avoid collision with the new experiment equivalents. |

---

## Session: Datasets Section Redesign (2026-06-11)

### Problem solved

The admin home page had a permanently-open "Upload Dataset" form on the left and no way to view, browse, or delete existing datasets. Admins had no UI to see what was already uploaded or to clean up obsolete datasets, and there was no protection against uploading a second dataset with the same name as an existing one (silently producing two entries with identical titles).

### Approach

Replaced the left column with a "Datasets" section that lists existing datasets (scrollable) with upload date/time and exposes Manage / Upload affordances. Upload is now an explicit modal action. Duplicate-name detection happens client-side at save time; deletes use a two-phase confirm-then-force flow so the admin can choose to abort or proceed when referenced experiments would be demoted.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Added `import shutil` and `Form` from fastapi. **POST `/admin/datasets/pair`** now accepts an optional `dataset_title` form field that overrides the default log-stem-derived title (used by the frontend's "Keep Both" rename flow). **New `DELETE /admin/datasets/{dataset_id}`** with `force: bool = False` query param: when `force=false` and any `Experiment.dataset_ids` references the dataset, returns 409 with `detail.referencing_experiments` (list of `{_id, name, status}`); when `force=true` (or no references exist), demotes each referencing experiment to `draft` (also removing the deleted dataset id from `dataset_ids`), removes the `data/{dataset_id}/` directory via `shutil.rmtree`, and deletes the `DatasetPair` document. Response includes `demoted_experiments` so the UI can name what was reverted. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/components/Admin/UploadDatasetModal.js` | **New** — modal that wraps the previous upload UI (two `FileUploadCard`s + Save button). Receives `existingDatasets` to derive the title set; on Save derives `title` from the log filename stem and checks for collision. If a collision exists, renders an inner conflict dialog with three actions: **Cancel** (return to upload form), **Keep Both** (computes next-available `"{title} ({n})"` starting at n=2, posts with `dataset_title` form field), **Replace** (DELETEs the existing dataset with `?force=true` then re-posts with default title). Backdrop and close button are disabled while `isSaving` to prevent mid-upload close. |
| `provi-frontend/src/app/admin/page.js` | Replaced the "Upload Dataset" left column with a "Datasets" section: scrollable list (max-h-72) showing `dataset_title` + `formatDateTime(insert_datetime)` (dd/mm/yy HH:MM, minute precision). Footer has two modes — **default**: `[Manage] [Upload]`; **manage**: per-row checkboxes + `[Cancel] [Delete Selected (n)]`. Delete uses a two-phase flow: first confirm modal (list of names + warning), then iterate `DELETE /api/admin/datasets/{id}` without force. 409 responses are collected into `forceConfirm` state; when present, a second modal lists each conflicting dataset alongside its referencing experiments (name + status) and offers `[Cancel] [Force Delete]`. Force path re-issues DELETE with `?force=true` and reports demoted experiment names in a toast. Removed `FileUploadCard`/`SaveResultModal` imports and the related `logFile`/`guidelineFile`/`isSaving`/`handleSave`/`modal` state — all migrated into the new modal. Added `Toast` for inline feedback (replaces the post-upload `SaveResultModal`). |
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | Added inline `formatDateTime` helper (same dd/mm/yy HH:MM format) and swapped the two `new Date(...).toLocaleDateString()` calls under "Uploaded:" to use it, so timestamps on `/admin/experiments/new` match the new datasets list and include minute precision. |

### Notes

- `/admin/experiments/new` already fetches from the same `GET /api/admin/datasets` endpoint, so the data source is consistent without further changes.
- "Force Delete" is destructive but reversible only in the sense that the demoted experiments can be re-published manually after their datasets are re-uploaded. The admin sees exactly which experiments will be affected before confirming.
- Frontend duplicate detection is client-side (against the in-memory `datasets` list). A race condition exists if two admins upload simultaneously, but is harmless: the second upload will succeed with a different UUID and the duplicate title will simply coexist until cleaned up.

---

## Session: Publish Mutex Check (2026-06-11)

### Problem solved

The overview page's "Publish Experiment" button always called `PATCH /experiments/{id}/status?status=published` unconditionally, allowing multiple experiments to be in `published` state simultaneously. Business rule: at most one experiment may be published at a time.

### Approach

Frontend-only check on the overview page. When the admin clicks Publish, the page refetches the experiments list to detect any other experiment with `status === "published"`. If one is found, a confirmation modal blocks the action and offers two choices:

- **Cancel** — abort publishing.
- **Finish & Publish** — PATCH the conflicting experiment to `finished`, then publish the current one.

No backend change yet, so a race condition remains if two admins click Publish simultaneously. Backend 409 enforcement is deferred to a future session (likely bundled with merging the two status-update endpoints).

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/experiments/overview/page.js` | Added `publishConflict` and `publishing` state. Split `publishExperiment()` into a validation entrypoint (refetches experiments, detects another published one, opens modal if found) and a private `_doPublish()` helper that contains the actual `PATCH …/status?status=published` call. Added `confirmFinishAndPublish()` which PATCHes the conflicting experiment to `finished` then calls `_doPublish()`. Publish button now also disables during `publishing` and shows "Publishing…". New inline conflict modal (styled like `SaveResultModal`) displays the conflicting experiment name with Cancel / "Finish & Publish" actions. |

---

## Session: Admin Experiments List Scrollable (2026-06-11)

### Problem solved

The Experiments section on `/admin` had no height limit, so the page grew taller as more experiment instances accumulated, eventually pushing other content off-screen and breaking the two-column layout balance.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Added `max-h-72 overflow-y-auto pr-1` to the experiments list container (`<div className="space-y-4 mb-10">`). The list now caps at 288px (≈3–4 cards visible), scrolls vertically when exceeded, and `pr-1` reserves space for the scrollbar so card content isn't clipped. |

---

## Session: Task List Natural Sort (2026-06-11)

### Problem solved

Tasks on `/admin/experiments/task` were displayed in MongoDB insertion order rather than logical order (task1, task2, …, taskN). With more than 9 tasks, lexicographic string sort would also break (e.g. task10 before task2).

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Added `import re` at top. In `GET /admin/tasks`, added a natural-sort step after fetching: `tasks.sort(key=lambda t: int(re.search(r'\d+', t.get("task_key", "0")).group()))`. Tasks are now returned in task1 → task2 → … → taskN order regardless of insertion order in MongoDB. |

---

## Session: Experiment Overview Page (2026-05-24)

### Goal
Add a read-only overview page as the final step of the admin experiment-setup wizard (after idiom selection), showing all selected tasks and idioms. Migrate "Save as Draft" and "Publish Experiment" actions from idiom-selection to this new page. Add per-task placeholder sections for two upcoming features: answer-type configuration and ground-truth generation.

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/experiments/overview/page.js` | **New** — Step 3 overview page. Fetches experiment, tasks, and idioms in parallel via `Promise.all`; groups `task_configs` by `task_id`. Top metadata strip shows experiment name, ID, task count, and a live status badge (yellow = draft, green = published). One card per task with three sections: **Selected Idioms** (non-interactive chips showing label + granularity · renderer), **Answer Type** (dashed-border placeholder, "Coming Soon" pill, disabled "Configure" button), **Ground Truth** (dashed-border placeholder, "Coming Soon" pill, disabled "Generate" button). Sticky footer: ← Previous Step, **Save as Draft** (`PATCH {status: "draft"}`), **Publish Experiment** (`PATCH /status?status=published`). After publish the status badge flips to "published" and the Publish button disables — page stays open. |
| `provi-frontend/src/app/admin/experiments/idiom/page.js` | Replaced `saveExperiment` with `handleNext`: PATCHes only `task_configs`, then navigates to `/admin/experiments/overview?experiment_id=…`. Removed `showSuccess`, `successDetail`, `expModalOpen`, `experiments` state; removed `saveExperiment` and `viewExperiments` functions; removed success-banner JSX, "Save as Draft" / "Publish Experiment" footer buttons, and "View All Experiments" modal — all superseded by the overview page. Footer now has a single "Next →" button. Also fixed a latent bug: the old `publish` branch referenced an undefined `BASE_URL`. |
| `provi-frontend/src/app/admin/idiom-selection/page.js` | Same changes as `experiments/idiom/page.js` — this is the legacy parallel flow. |

---

## Session: Safari Cookie Fix (2026-05-18)

### Problem solved

The pipeline completed successfully in Chrome but the `/knowledgequestion` submit failed silently in Safari (returned 401 "No cookie detected").

**Root cause:** `auth.py` set the `provi_user_id` cookie with `Secure=True; SameSite=None`. Chrome exempts `localhost` from the HTTPS requirement for `Secure` cookies, so it accepted and resent the cookie over plain HTTP. Safari does not make this exception — it strictly dropped any `Secure` cookie received over HTTP, so every subsequent request arrived without a cookie and was rejected by the backend.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `.env` | Added `COOKIE_SECURE=false` — disables the `Secure` flag for local HTTP dev. Set to `true` in production (HTTPS). |
| `ProViBackend/app/routers/auth.py` | Reads `COOKIE_SECURE` env var (defaults to `true`). When `false`, sets `secure=False, samesite="lax"` on the `provi_user_id` cookie instead of `secure=True, samesite="none"`. (`SameSite=None` requires `Secure` by spec, so both attributes must change together.) Production behaviour is unchanged. |
| `docker-compose.override.yml` | Added `COOKIE_SECURE: "false"` to the `provibackend` service environment. The override file is gitignored and local-only, so production (`docker-compose.yml`) is unaffected. Restart with `docker compose up -d provibackend` — no rebuild needed. |


---

## Session: SVG Path Fix & Participant Assignment Endpoints (2026-05-11)

### Problem solved

Two bugs prevented visualization images from loading for participants:

1. **`admin.py` used the wrong base path** — `DATA_DIRECTORY = pl.Path("/data")` stored uploaded datasets at `/data/{pair_id}/…` inside the container, while `participant.py` read SVGs from `config.BASE_DIRECTORY / "data" / {pair_id} / …` (`/code/ProViBackend/data/…`). These paths never matched, so SVG fetches always returned 404.

2. **`data/` was not excluded from the Docker build context** — `provibackend/ProViBackend/data/` is gitignored, so generated SVG files are never committed. Because `ProViBackend/data/` was missing from `.dockerignore`, local SVG files were silently baked into images built on developer machines. Anyone who cloned the repo fresh got an image with no SVGs and broken visualizations on `/taskexecution`.

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Replaced `DATA_DIRECTORY = pl.Path("/data")` with `DATA_DIRECTORY = config.BASE_DIRECTORY / "data"`. Dataset files now land in the `provibackend_data` Docker volume (`/code/ProViBackend/data/{pair_id}/…`), matching the path `participant.py` reads from. |
| `ProViBackend/app/routers/participant.py` | Added `POST /participant/assignment` — idempotent endpoint that assigns a participant to an experiment using balanced random allocation and persists a `UserAssignment` document. Added `GET /participant/assignment/{user_id}/{experiment_id}/trials` — returns the participant's personalised trial list (full task/idiom metadata, `svg_available` flag, `trial_index`) from their stored `trial_sequence`. |

### Infra

| File | Change |
|------|--------|
| `provibackend/.dockerignore` | Added `ProViBackend/data/` — prevents locally generated SVG/dataset files from being baked into Docker images, ensuring consistent builds for all team members. |

---

## Session: Docker One-Command Deploy (2026-05-07)

### GitHub repository configuration (done via GitHub web UI)

| Setting | Value |
|---------|-------|
| Actions permissions | All actions allowed (Settings → Actions → General) |
| Secret `SECRET_ENV` | Added under Settings → Secrets and variables → Actions. Contains the prod `.env` file content: `PUBLIC_API_BASE`, `MONGO_USERNAME`, `MONGO_PASSWORD`, `COMPOSE_PROFILES`. |
| Self-hosted runner `cc-vis` | Registered for this repo (Settings → Actions → Runners). Installed on the server as a systemd service (`sudo ./svc.sh install && sudo ./svc.sh start`) so it survives reboots. Architecture: x64 Linux. |
| Collaborator access | Team members added as collaborators with write access (Settings → Collaborators) so they can push to `develop` directly. |

### Infrastructure (file changes)

| File | Change |
|------|--------|
| `docker-compose.yml` | **New** — Root-level compose file consolidating all four services (mongo, redis, provibackend, provifrontend) plus nginx behind a `prod` profile. Uses `build:` so `--build` compiles images from source. Named volumes replace hard-coded host paths. `depends_on` with `condition: service_healthy` so backend waits for mongo and redis to be ready. `restart: unless-stopped` on every service. |
| `.env.example` | **New** — Documents env vars needed: `PUBLIC_API_BASE` (Next.js build-time API URL), `MONGO_USERNAME`, `MONGO_PASSWORD`, `COMPOSE_PROFILES` (`prod` on server activates nginx). |
| `Makefile` | **New** — `make up` / `make down` / `make logs` shortcuts. |
| `.github/workflows/deploy.yml` | **New** — Single root-level workflow; triggers on push to `develop`; self-hosted runner writes `.env` from `SECRET_ENV` GitHub secret then runs `docker compose up -d --build`. Uses `actions/checkout@v4`. Includes a pre-deploy step that force-removes any containers left over from the previous manual setup (`docker rm -f redis mongo provibackend provifrontend nginx`) so naming conflicts don't block the first compose-managed deploy. |
| `ProViFrontend/Dockerfile` | Rewrote to fix three issues: (1) `ARG NEXT_PUBLIC_API_BASE` moved to after `FROM` — args declared before `FROM` are global scope and not available inside the build stage; (2) added explicit `sharp` install (`npm install sharp`) after the main `npm install` — `sharp` is an optional Next.js peer dependency and is required at build time to generate blur placeholders for imported PNG images; (3) `CMD` changed to JSON array form to handle OS signals correctly. |
| `ProViFrontend/.dockerignore` | **New** — Excludes `provi-frontend/node_modules` and `provi-frontend/.next` from the Docker build context. Without this, `COPY . .` overwrites the Linux node_modules (installed inside the container) with the local macOS ones, whose native binaries (e.g. `sharp`) cannot run on Linux. |
| `.gitignore` | Added `.env` so machine-specific env files are never committed. |
| `ProViFrontend/docker-compose.yml` | **Deleted** — replaced by root compose file. |
| `provibackend/docker-compose.yml` | **Deleted** — replaced by root compose file. |
| `provibackend/docker-compose.override.yml` | **Deleted** — named volumes in root compose file replace this. |
| `provibackend/docker-compose.local.yml` | **Deleted** — local/prod distinction now handled by `.env` + `COMPOSE_PROFILES`. |
| `provibackend/.github/workflows/deploy.yml` | **Deleted** — dead code (GitHub only reads `.github/workflows/` at repo root). |
| `ProViFrontend/.github/workflows/deploy.yml` | **Deleted** — same reason. |

### Current server config (temporary, until TLS certs are available)

`SECRET_ENV` on the server uses direct IP access with no nginx:
```
PUBLIC_API_BASE=http://134.155.106.59:1234/api
MONGO_USERNAME=root
MONGO_PASSWORD=example
COMPOSE_PROFILES=
```
Frontend accessible at `http://134.155.106.59:22222`. Once TLS certs are in place, switch to `COMPOSE_PROFILES=prod` and `PUBLIC_API_BASE=https://cc-vis.rz.uni-mannheim.de/api`.

### How to deploy

**Local dev** — copy `.env.example` to `.env` (defaults work as-is), then:
```bash
docker compose up -d --build   # or: make up
```

**Server** — push to `develop`; the self-hosted runner deploys automatically.

---

## Session: Dataset structure, task/idiom source of truth, path unification (2026-05-08)

### Goal
Restructure file storage to `data/{pair_id}/input/` + `data/{pair_id}/output/task1..task6/`, make Tasks and Idioms backend-authoritative (auto-seeded, no frontend hardcoding), expose a `GET /admin/task-idioms` endpoint, and rename the Save button to "Save and Generate Graphs".

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/scripts/tasks/task1-6.py` | Added module-level `IDIOMS = [...]` constant to each script listing canonical idiom_keys that script generates (post-rename). Single source of truth for task→idiom mapping. |
| `ProViBackend/app/seed_data.py` | **New** — `CANONICAL_TASKS` (6 tasks, task_key=`task1..task6`) and `CANONICAL_IDIOMS` (13 idioms). Replaces the frontend `ALL_TASKS` and `ALL_IDIOMS` constants. |
| `ProViBackend/app/main.py` | Added `asynccontextmanager` lifespan. On startup: if `Task` or `Idiom` collection is empty, inserts from `seed_data.py` with stable UUIDs (`uuid5`). Eliminates manual "Seed" buttons. |
| `ProViBackend/app/routers/admin.py` | Added `GET /admin/task-idioms` — returns `{task_key: [idiom_key, ...]}` from each task module's `IDIOMS` constant. Updated `POST /admin/datasets/pair`: saves uploaded files in `data/{pair_id}/input/` (preserving original filename), writes graphs to `data/{pair_id}/output/`, calls `run_pipeline(pair_dir)` instead of old `create_all_visualizations`. Updated `_sync_participant_experiment`: `svg_path = f"data/{pair_id}/output/{task_key}/{idiom_key}.svg"`. |
| `ProViBackend/app/routers/participant.py` | Updated fallback `svg_path` construction to match new `data/{pair_id}/output/...` layout. |
| `ProViBackend/scripts/create_all_visualizations.py` | Replaced per-filename discovery with extension-based scanning (`LOG_EXTENSIONS={".xes",".csv"}`, `MODEL_EXTENSIONS={".bpmn"}`). Added `_FILE_RENAME` constant (idiom name normalisation). `run_pipeline()` now also strips `taskN_` prefix and applies `_FILE_RENAME` after each generator. Removed old `create_all_visualizations()` function (T-01 naming). |

### Infra

| File | Change |
|------|--------|
| `docker-compose.yml` | Renamed volume `provibackend_output → provibackend_data`, mount path `/code/ProViBackend/output/ → /code/ProViBackend/data/`. |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `src/app/admin/page.js` | Renamed "Save" button → "Save and Generate Graphs"; loading state → "Saving and generating...". |
| `src/components/Admin/SaveResultModal.js` | Success copy updated to inform user that graph generation runs in the background (~30s). |
| `src/app/admin/experiments/task/page.js` | Removed hardcoded `ALL_TASKS`, "Seed Tasks" button, "Add Task" modal. Tasks now fetched purely from `GET /api/admin/tasks` (auto-seeded from backend on startup). |
| `src/app/admin/experiments/idiom/page.js` | Removed hardcoded `ALL_IDIOMS`, `TASK_IDIOM_KEYS`, "Seed Idioms" button. Idioms fetched from `GET /api/admin/idioms`; task→idiom filter mapping fetched from `GET /api/admin/task-idioms`. Both fetched in parallel via `Promise.all`. |

### Deploy action required
```bash
docker compose down -v          # removes provibackend_output volume
# drop Task, Idiom, Experiment, DatasetPair, ParticipantExperiment collections in MongoDB
docker compose up -d --build    # auto-seeds Task + Idiom on first startup
```

### Known gap
`task3.py` declares `flow_chart_table` in its `IDIOMS` list (matching the original frontend mapping) but does not yet generate a `task3_flow_chart_table.svg`. Selecting this idiom for task3 will produce a missing-SVG 404 for participants. Needs a generator added to `task3.py`.

---

## Session: Admin API URL Unification (2026-05-08)

### Problem solved

All four admin pages were using inconsistent strategies to reach the backend:
- `admin/page.js` read from `localStorage` via `lib/apiConfig.js` (with an on-page input box for pasting the API base URL)
- `admin/experiments/{new,task,idiom}/page.js` each declared their own `const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1234"` — an env var that was never set in any build or deploy config, so they always fell back to `localhost:1234` and were broken on the server

Additionally, the server is accessed via SSH local-port forwarding (`-L 3000:127.0.0.1:22222`), so `window.location.hostname` is always `localhost` regardless of environment — runtime hostname detection would not have distinguished local from tunnelled-server access.

### Approach

Next.js `rewrites()` in `next.config.mjs` proxy all `/api/*` requests from the browser to the backend over the internal Docker network. The browser only ever talks to the frontend; Next.js (running inside the container on the server) forwards `/api/:path*` → `http://provibackend:80/api/:path*`. One Docker image works for local dev and the server with no env var, no input box, and no rebuild.

The SSH tunnel command can now be simplified — the backend forward (`-L 8000:127.0.0.1:1234`) is no longer needed:
```bash
ssh -p 1907 -L 3000:127.0.0.1:22222 ccvis@134.155.106.59
```

### Infrastructure

| File | Change |
|------|--------|
| `ProViFrontend/provi-frontend/next.config.mjs` | Added `async rewrites()` — proxies `/api/:path*` to `${BACKEND_INTERNAL_URL}/api/:path*` (defaults to `http://provibackend:80`) |
| `docker-compose.yml` | Replaced `NEXT_PUBLIC_API_BASE` build arg with `BACKEND_INTERNAL_URL: http://provibackend:80` runtime env var on `provifrontend` service |
| `ProViFrontend/Dockerfile` | Removed `ARG NEXT_PUBLIC_API_BASE` and `ENV NEXT_PUBLIC_API_BASE=...` lines — no longer needed at build time |
| `.env.example` | Removed `PUBLIC_API_BASE` — superseded by the rewrite approach |
| `ProViFrontend/provi-frontend/src/lib/apiConfig.js` | **Deleted** — `getApiBase`, `setApiBase`, `normalizeApiBase`, localStorage logic no longer needed |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Removed "API base URL" input box section, `apiBaseInput` state, related `useEffect`, and `apiConfig` imports. All three `fetch` calls switched to relative `/api/...` URLs. |
| `provi-frontend/src/app/admin/experiments/new/page.js` | Removed top-level `BASE_URL` const. Both `fetch` calls switched to relative `/api/...` URLs. |
| `provi-frontend/src/app/admin/experiments/task/page.js` | Removed top-level `BASE_URL` const. All five `fetch` calls switched to relative `/api/...` URLs. Cleaned up error message that previously printed `BASE_URL`. |
| `provi-frontend/src/app/admin/experiments/idiom/page.js` | Removed top-level `BASE_URL` const. All eight `fetch` calls switched to relative `/api/...` URLs. |

### Note on `SECRET_ENV`

The `PUBLIC_API_BASE` line in `SECRET_ENV` (GitHub Actions secret) is now unused and can be removed when convenient. The other three vars (`MONGO_USERNAME`, `MONGO_PASSWORD`, `COMPOSE_PROFILES`) remain needed.

---

## Session: Admin Passcode Gate (2026-05-04)

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/layout.js` | Converted to client component; gates all `/admin/*` routes. Hydrates `authed` from `localStorage["adminAuthed"]` (no backend, no admin record — flag only). Unauthed visits to suffix routes (`/admin/experiments/new`, etc.) `router.replace("/admin")`. On `/admin` while unauthed, renders `LoginModal` overlay; on success sets the flag and reveals content. Authed users navigate freely; flag persists across tab/browser restarts until cleared. |

---

## Session: Admin Home — Two-Column Layout (2026-05-03)

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/routers/admin.py` | Added `GET /admin/experiments` — returns list of all experiments (id, name, status, created_at) |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/page.js` | Redesigned admin home as two-column layout: left column retains Upload Dataset + API base URL config; right column shows live experiment list fetched from `GET /admin/experiments`, with status-coded border colours (blue = published, amber = draft, grey = closed). "Create New Experiment" button links to `/admin/experiments/new` (the existing experiment setup page). |

---

## Session: Experiment Creation Wizard — Step 1 (Name, Description, Dataset)

### Backend (`provibackend/`)

| File | Change |
|------|--------|
| `ProViBackend/app/datamodels/data_schemas.py` | Revised `Experiment` model (removed `experiment_created_by`, `experiment_description` made optional, nullable defaults for enum fields, list defaults); added `ExperimentCreate` and `ExperimentPatch` models |
| `ProViBackend/app/routers/admin.py` | Repurposed `GET /admin/datasets` to return `DatasetPair` collection; added `POST /admin/experiments` (create draft); added `PATCH /admin/experiments/{id}` (partial update) |
| `ProViBackend/utils/database/connection.py` | Added `create_experiment`, `get_experiment`, `update_experiment` helpers |

### Frontend (`ProViFrontend/`)

| File | Change |
|------|--------|
| `provi-frontend/src/app/admin/experiments/new/page.js` | **New** — Step 1 page: fetches dataset pairs, POSTs draft experiment on Next, navigates to `/admin/experiments/[id]/design` |
| `provi-frontend/src/components/Admin/ExperimentDetailsForm.js` | **New** — Controlled name + description inputs |
| `provi-frontend/src/components/Admin/DatasetSelectTable.js` | **New** — Checkbox multi-select table of dataset pairs |
| `provi-frontend/src/components/Admin/AdminNav.js` | Added "Experiment Setup" nav item |
