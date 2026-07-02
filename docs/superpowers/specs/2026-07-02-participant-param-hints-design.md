# Participant Parameter Hints Design

## Goal

Show admin-configured task parameters to experiment participants during task execution, so they understand what the chart is based on (e.g. which activity marks a positive outcome, how many variants are shown).

## Architecture

Two-layer change: backend adds `param_hints` to the trial response; frontend renders a callout block in the answer panel.

No changes to SVG generation, no new API endpoints, no new database fields.

## Data Flow

### Backend — `participant.py` `get_assigned_trials`

For each trial, after reading `task_instances[task_id]["parameters"]`:

1. Dynamically import the task module by `task_key` (e.g. `tasks.task05`) — same pattern already used elsewhere in the backend.
2. Read `PARAM_SPEC` from the module. If the module has no `PARAM_SPEC`, treat it as `[]`.
3. For each entry in `PARAM_SPEC`, look up the configured value in `parameters`. Skip entries where the value is `None`, `""`, or the key is absent.
4. Append `{"label": spec["label"], "value": str(value)}` to the `param_hints` list.
5. Include `"param_hints": param_hints` in the trial dict (empty list `[]` when nothing to show).

**Example output for task05 configured with `outcome_activity = "CARE_ACTIVATED"`:**
```json
"param_hints": [
  { "label": "Positive-outcome activity (present in trace = Positive group)", "value": "CARE_ACTIVATED" }
]
```

**Tasks with no PARAM_SPEC (task06, task12, task20, task23):** `param_hints` is `[]`.

### Frontend — three files touched

**`taskexecution/page.js` — `groupTrialsByTask`**

Add `param_hints` to the group object (taken from the first trial of each group, since all idioms of the same task share the same parameters):
```js
param_hints: trial.param_hints ?? [],
```

**`taskexecution/page.js` — render**

Pass `paramHints={group.param_hints}` to `<TaskAnswerPanel>`.

**`TaskAnswerPanel.js`**

Add `paramHints = []` to the prop list. Render the callout between the task label block and the answer widget, only when `paramHints.length > 0`:

```
┌───────────────────────────────────────┐
│ Task question text           [i]      │  ← existing
├───────────────────────────────────────┤
│ ▌ Chart parameters                    │  ← NEW (hidden when list is empty)
│   Outcome activity: CARE_ACTIVATED    │
│   Threshold: 0.1                      │
├───────────────────────────────────────┤
│  [ Answer widget ]                    │  ← existing
│  [ Submit ]                           │  ← existing
└───────────────────────────────────────┘
```

## Visual Design (Design C — accent callout)

```
background : #f0f4f8
left border : 3px solid #00305e
border-radius: 0 0.375rem 0.375rem 0
padding     : 0.625rem 0.75rem
margin-bottom: 0.875rem

header text : 0.62rem / bold / uppercase / #5a6061 / "Chart parameters"
row layout  : flex, gap 0.3rem
key text    : 0.72rem / bold / #00305e
value text  : 0.72rem / monospace / #2d3435
```

Long labels (e.g. full PARAM_SPEC label string) are truncated at 2 lines with `overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2`.

## Scope

- Only `required: True` and `required: False` params with a non-empty configured value are shown. The display does not distinguish between them.
- The `param_hints` field is read-only for participants; no interaction.
- No tracking event is needed for viewing this callout (it is always visible, not a tooltip).
- The callout is not shown on the loading skeleton.

## Files Changed

| File | Change |
|------|--------|
| `provibackend/ProViBackend/app/routers/participant.py` | Add `param_hints` generation in `get_assigned_trials` |
| `ProViFrontend/provi-frontend/src/app/taskexecution/page.js` | Pass `param_hints` through `groupTrialsByTask` and into `TaskAnswerPanel` |
| `ProViFrontend/provi-frontend/src/components/Task/TaskAnswerPanel.js` | Add `paramHints` prop and render callout |
