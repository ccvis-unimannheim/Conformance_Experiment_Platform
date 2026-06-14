# Plan: `/taskexecution` Wiring + Per-Format Answer Widgets

> Status: **draft, not yet implemented**. Scope: consume the trial-contract
> fields already returned by the backend (`PARTICIPANT_TRIAL_CONTRACT.md`) on
> `/taskexecution`, and build the answer-input widget for each `answer_type` so
> the page renders the right control for whatever `answer_format` a task
> declares (`ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md` step 6).

## 0. Goal

Today every `task_instance` falls back to `answer_format="free-text"` /
`answer_type="free_text"` / `options=[]` / `decisive=false`
(`PARTICIPANT_TRIAL_CONTRACT.md` "Fallback"), so `/taskexecution` only ever
exercises a free-text textarea. Once step 6 authors real `ANSWER_FORMATS` for
the 37 tasks, the page must render the correct widget per trial and submit
`answer` encoded per the contract's "Answer submission" table — none of that
exists yet.

## 1. Current state

- `ProViFrontend/.../taskexecution/page.js`:
  - `groupTrialsByTask` only carries `answer_type` per task group; `decisive`,
    `options`, `answer_format` are dropped.
  - `TaskAnswerPanel` is always called with `options={[]}`.
- `ProViFrontend/.../components/Task/TaskAnswerPanel.js`:
  - Two render branches only: `options.length > 0` → a vertical list of
    single-select buttons (writes `option.value`), else → a free-text
    `<textarea>`.
  - Submits `answer: selectedAnswer.toString()` to `POST /survey/answer`.
- Backend already returns, per trial: `answer_format`, `answer_type`,
  `decisive`, `options: [{label, value}]` (checkpoint 7, done).
- Auto-grading against `decisive` GT remains **out of scope** — `answer` is
  stored as-is either way.

## 2. Target widget set

One widget per `answer_type` (`PARTICIPANT_TRIAL_CONTRACT.md` mapping table).
Some widgets must further branch on `answer_format` for input masking/rules:

| `answer_type` | `answer_format`(s) | Widget |
|---|---|---|
| `single_choice` | `mc-single` | radio list (existing button-list, reused) |
| `multiple_choice` | `mc-multi` | checkbox list |
| `numeric` | `pct` \| `count` \| `decimal` | single number input, masked per format |
| `numeric_set` | `pct-set` \| `count-set` | one number input per `options` row, masked per format |
| `rank` | `rank` | ordered list of `options` items, reorderable |
| `matrix` | `matrix` | toggle grid over `options` cells |
| `free_text` | `free-text` | textarea (existing) |

## 3. Page-level wiring (`/taskexecution/page.js`)

- `groupTrialsByTask`: also carry `answer_format`, `decisive`, and `options`
  on each task group (these are per-`task_instance`, i.e. shared across all
  idioms of that task — same as `answer_type` today).
- Pass `answer_format`, `answer_type`, `decisive`, `options` from
  `currentGroup` down to `TaskAnswerPanel` (replacing the hardcoded
  `options={[]}`).
- `decisive` is not used for grading (out of scope) but should be threaded
  through so it's available in the submitted payload / future use without
  another contract change.

## 4. `TaskAnswerPanel` restructure

Split the current monolithic form body into a dispatcher + one component per
`answer_type`, each owning:
1. its local answer-state shape,
2. a `canSubmit` check (replaces the current blanket
   `!selectedAnswer.trim()` guard, which doesn't fit array/object answers),
3. an `encode()` that produces the `answer` string per §6 below.

```jsx
function AnswerInput({ answerFormat, answerType, options, value, onChange }) {
  switch (answerType) {
    case "single_choice":   return <SingleChoice ... />;   // existing button list
    case "multiple_choice": return <MultiChoice ... />;
    case "numeric":         return <NumericInput answerFormat={answerFormat} ... />;
    case "numeric_set":     return <NumericSet answerFormat={answerFormat} ... />;
    case "rank":            return <RankList ... />;
    case "matrix":          return <MatrixGrid ... />;
    default:                return <FreeText ... />;       // existing textarea
  }
}
```

`selectedAnswer` (currently always a string) becomes a generic `value` whose
shape depends on `answerType` (string | string[] | Record<string,string> |
string[] ordering | string[] of cell ids). The per-trial reset effect (today:
`setSelectedAnswer("")` on `currentTaskIndex` change) must reset to the
correct empty shape for the new `answerType`.

### 4.1 `single_choice` (`mc-single`)

Reuse the existing button-list exactly as-is; `options` already has the right
shape (`{label, value}`). `value = option.value`.

### 4.2 `multiple_choice` (`mc-multi`)

Checkbox variant of the same button list (toggle membership in a `Set`/array
instead of single selection). Require **at least one** selection to submit.

### 4.3 `numeric` (`pct` | `count` | `decimal`)

Single `<input type="number">` (or text input with custom masking). Per-format
entry rule (`PARTICIPANT_TRIAL_CONTRACT.md` "Answer-format catalogue"):

| `answer_format` | rule | example | stored `answer` |
|---|---|---|---|
| `pct` | integer percent, append `%` | `96` → `"96%"` | `"96%"` |
| `count` | non-negative integer | `42` | `"42"` |
| `decimal` | two decimals, leading zero | `0.42` | `"0.42"` |

Validate/clamp on blur or submit; widget appends `%` for `pct` and formats to
2dp for `decimal` before encoding.

### 4.4 `numeric_set` (`pct-set` | `count-set`)

One row per `options[i].label`, each an `numeric` input following the same
per-format rule as §4.3 (rows of `pct-set` follow `pct`, rows of `count-set`
follow `count`). Optional: for `pct-set`, show a running sum and a soft
"should total 100%" hint — **not** a hard submit-blocker (decided in §8).

### 4.5 `rank`

`options` is the closed set of items to order. Render as a reorderable list
(drag handles, or simpler up/down arrow buttons per row — pick the lighter
implementation, no new drag-and-drop dependency unless one is already in the
project). Initial order = `options` order; participant reorders before
submit.

### 4.6 `matrix`

`options` represents the grid's cells. **Open item (§8)**: the contract
doesn't yet define how a flat `options: [{label, value}]` list maps to a 2D
grid (row/column labels). Needs a small contract addition (e.g. `row`/`col`
fields on each option, or a separate `rows`/`cols` array on the GT block)
before this widget can be built — flagged as a blocker, not solved here.

### 4.7 `free_text` (`free-text`)

No change — existing `<textarea>`, `value` stays a plain string.

## 5. Per-widget submit gating (`canSubmit`)

| `answerType` | `canSubmit` when |
|---|---|
| `single_choice` | one option selected |
| `multiple_choice` | ≥1 option selected |
| `numeric` | input non-empty and passes format validation |
| `numeric_set` | every row filled and passes format validation |
| `rank` | always true (initial order is a valid answer) |
| `matrix` | always true (empty selection = no cells, valid) |
| `free_text` | non-empty (current behaviour, unchanged) |

## 6. Answer encoding (`POST /survey/answer`, `answer: string`)

Mirrors `PARTICIPANT_TRIAL_CONTRACT.md` "Answer submission":

| `answer_format` | `encode(value)` |
|---|---|
| `pct` / `count` / `decimal` | formatted scalar string, e.g. `"96%"`, `"42"`, `"0.42"` |
| `pct-set` / `count-set` | `JSON.stringify({label: value, ...})` |
| `mc-single` | the chosen `option.value` |
| `mc-multi` | `JSON.stringify([value, ...])` |
| `rank` | `JSON.stringify([value, ...])` in chosen order |
| `matrix` | `JSON.stringify([cellId, ...])` |
| `free-text` | raw text |

No backend changes needed — `AnswerFromFrontend.answer` is already `str` and
stored as-is (`provibackend/.../routers/questionnaire.py`).

## 7. Build order

1. **Page wiring**: thread `answer_format`/`decisive`/`options` through
   `groupTrialsByTask` → `TaskAnswerPanel` props. No visible behaviour change
   yet (all live tasks are still `free-text`).
2. **Refactor** `TaskAnswerPanel` into the dispatcher + extract the two
   existing branches as `SingleChoice` / `FreeText`, generalize the
   reset-on-trial-change effect to a per-`answerType` empty value. Verify
   free-text flow still works end-to-end (regression check).
3. `multiple_choice` widget + encoding.
4. `numeric` widget (all three formats) + encoding.
5. `numeric_set` widget + encoding.
6. `rank` widget + encoding.
7. `matrix` widget — **after** §8's open item is resolved.
8. End-to-end test: since checkpoint 6 hasn't authored real non-free-text
   tasks yet, test each new widget against **mock trial data** matching the
   contract shapes (per `PARTICIPANT_TRIAL_CONTRACT.md`'s own suggestion for
   exercising widgets ahead of per-task authoring).

## 8. Open items

- **`matrix` cell layout**: how `options` encodes a 2D grid (row/col labels
  or ids) is undefined in the current `GroundTruthBlock`/contract — needs a
  small schema addition before step 7 of the build order. Affects
  `compute_ground_truth` for matrix-shaped tasks too (admin side).
- **`pct-set` sum-to-100**: validate client-side as a soft hint only, not a
  hard submit gate (distributions may legitimately not sum to exactly 100 due
  to rounding; decisive grading, if ever added, would handle tolerance
  server-side).
- **`rank` UI**: drag-and-drop vs. up/down buttons — default to up/down
  buttons (no new dependency) unless the team already has a drag library in
  use elsewhere in the frontend.
- Auto-grading (`is_correct`) stays out of scope, per
  `PARTICIPANT_TRIAL_CONTRACT.md`.
