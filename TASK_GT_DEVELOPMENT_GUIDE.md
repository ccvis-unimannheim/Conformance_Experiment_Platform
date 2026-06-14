# Task Ground Truth Development Guide

This guide explains how to add a new task's Ground Truth (GT) contract to ProVi. In the common case (using an existing answer format), **you only need to edit one file**: `provibackend/ProViBackend/scripts/tasks/taskNN.py`.

---

## Architecture Overview

Two pipelines connect each task's contract to the participant experience.

### Pipeline 1 — Question Type (which widget the participant sees)

```
taskNN.py          →  admin.py               →  participant.py              →  Frontend
ANSWER_FORMATS        _resolve_answer_format    ANSWER_FORMAT_TO_ANSWER_TYPE   AnswerWidgets.js
                      _build_gt_block           _participant_options
```

### Pipeline 2 — Answer Scoring (is_correct written at submit time)

```
taskNN.py              →  admin.py          →  questionnaire.py          →  scoring.py
compute_ground_truth      _build_gt_block      _lookup_ground_truth         score_answer
                          → exp.task_instances  (looks up GT at submit)      (grades by format)
```

Both pipelines are **fully generic** — they read the task contract from `taskNN.py` at runtime. You never need to register a new task in admin, participant, or scoring code unless you introduce a brand-new answer format.

---

## Step-by-Step: Adding GT for a New Task

### Step 1 — Declare `GT_TIER`

```python
GT_TIER = "AUTO"   # AUTO: no params needed, GT computed from log alone
                   # SEMI: admin sets params first, then GT is computed
                   # MANUAL: no auto GT, rubric-only human grading
```

### Step 2 — Declare `PARAM_SPEC` (SEMI tasks only)

Skip for AUTO. For SEMI, list each param the admin must set:

```python
PARAM_SPEC = [
    {
        "key":      "my_threshold",
        "label":    "Human-readable label shown in the UI",
        "widget":   "threshold",   # see widget types below
        "default":  0.5,
        "required": False,
        "min": 0.01, "max": 1.0, "step": 0.01,
    },
]
```

**Available widget types:**

| widget | UI rendered | Use for |
|---|---|---|
| `threshold` | number input (0–1) | ratios, thresholds |
| `number` | number input | counts, integers |
| `select-one` | dropdown | fixed choice |
| `select-many` | multi-select | multiple fixed choices |
| `activity-picker` | dropdown from log activities | picking an activity |
| `attribute-picker` | dropdown from log attributes | picking a trace attribute |

For `activity-picker` / `attribute-picker`, add `"source": "log.activities"` or `"source": "log.attributes"` to auto-populate candidates from the uploaded dataset.

### Step 3 — Declare `ANSWER_FORMATS`

List every format the admin can choose for this task. Pick from the **9 supported formats**:

```python
ANSWER_FORMATS = [
    {"key": "mc-multi",  "gt_shape": "mc",           "decisive_default": True},
    {"key": "free-text", "gt_shape": "reference",     "decisive_default": False},
]
```

**Supported `key` → `gt_shape` pairs:**

| key | gt_shape | Participant widget | Scoring rule |
|---|---|---|---|
| `mc-single` | `mc` | Radio (pick one) | selected token ∈ correct set |
| `mc-multi` | `mc` | Checkbox (pick many) | selected set == correct set |
| `pct` | `scalar` | Number input (%) | integer % equal |
| `count` | `scalar` | Number input (#) | integer equal |
| `decimal` | `scalar` | Number input | 3 d.p. equal |
| `pct-set` | `labelled-set` | Number per label (%) | all labels match |
| `count-set` | `labelled-set` | Number per label (#) | all labels match |
| `rank` | `rank` | Drag-to-order list | order list equal |
| `matrix` | `matrix` | Pair-tick grid | selected pair set == correct set |
| `free-text` | `reference` | Textarea | manual grading (is_correct = null) |

`decisive_default`: if `true`, this format produces a binary correct/wrong grade. Set `false` for formats used as exploratory reference only.

### Step 4 — Implement `validate_params` (SEMI tasks only)

Skip for AUTO. Called before generation; return a list of error strings (empty = valid):

```python
def validate_params(log, params) -> list:
    raw = params.get("my_threshold")
    if raw is None or raw == "":
        return []
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return ["my_threshold must be a number."]
    if not (0.0 < v <= 1.0):
        return ["my_threshold must be between 0 and 1."]
    return []
```

### Step 5 — Implement `compute_ground_truth`

This is the only substantive work. Signature is fixed:

```python
def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    ...
```

Return a dict shaped to match the `gt_shape` of the chosen `answer_format`:

#### `gt_shape: "scalar"` (pct / count / decimal)

```python
return {"value": f"{round(mean_fitness * 100)}%"}
```

#### `gt_shape: "mc"` (mc-single / mc-multi)

Include every option (correct + distractors). Shuffle if desired.

```python
return {
    "options": [
        {"label": "Option A", "value": "a", "correct": True},
        {"label": "Option B", "value": "b", "correct": False},
    ]
}
```

#### `gt_shape: "labelled-set"` (pct-set / count-set)

One option per label. `value` holds the GT number as a string (e.g. `"40%"`). Always `"correct": True` — the value itself is the answer.

```python
return {
    "options": [
        {"label": "Group A", "value": "72%", "correct": True},
        {"label": "Group B", "value": "28%", "correct": True},
    ]
}
```

#### `gt_shape: "matrix"` (matrix)

One option per valid pair. `value` must be `"TokenA__TokenB"` (sorted alphabetically). Label is `"TokenA × TokenB"`.

```python
return {
    "options": [
        {"label": "Skip × Dup",  "value": "Dup__Skip",  "correct": True},
        {"label": "Skip × Late", "value": "Late__Skip",  "correct": False},
        {"label": "Dup × Late",  "value": "Dup__Late",   "correct": True},
    ]
}
```

#### `gt_shape: "rank"` (rank)

Options in the **correct order** (index 0 = rank 1). No `correct` flag needed — the order itself is the GT. The frontend shuffles before display to avoid leaking the answer.

```python
return {
    "options": [
        {"label": "Variant 3", "value": "Variant 3"},
        {"label": "Variant 1", "value": "Variant 1"},
        {"label": "Variant 2", "value": "Variant 2"},
    ]
}
```

#### `gt_shape: "reference"` (free-text)

Optional reference text for human grading. `is_correct` is always `null`.

```python
return {"reference": "Expected answer: traces with fitness < 0.8 exhibit skipped approvals."}
```

---

## What You Do NOT Need to Change

These files are fully generic and require no edits for new tasks using existing formats:

| File | Why you don't need to touch it |
|---|---|
| `task_registry.py` | reads `GT_TIER`, `ANSWER_FORMATS`, `PARAM_SPEC`, `compute_ground_truth` via `getattr` |
| `admin.py` | `_build_gt_block` and `_validate_task_instances` are format-agnostic |
| `participant.py` | `_participant_options` and `ANSWER_FORMAT_TO_ANSWER_TYPE` cover all 9 formats |
| `scoring.py` | `score_answer` covers all 9 formats |
| `AnswerWidgets.js` | all 9 widget types already implemented |
| `questionnaire.py` | `post_answer` calls `score_answer` generically |

---

## If You Need a Brand-New Answer Format

If none of the 9 formats above fits, you must update **4 files in sync**:

1. **`taskNN.py`** — declare the new `key` in `ANSWER_FORMATS` + implement `compute_ground_truth`
2. **`participant.py`** — add the new `key → answer_type` entry to `ANSWER_FORMAT_TO_ANSWER_TYPE`; add a stripping branch in `_participant_options`
3. **`scoring.py`** — add a grading branch in `score_answer`
4. **`AnswerWidgets.js`** — add a new widget component + a `case` in the dispatcher, plus `initialAnswer` / `isAnswered` / `serializeAnswer` handling

Keep the `answer: str` submit contract. Multi-value answers are JSON-encoded into that single field; `scoring.py` decodes them server-side.

---

## Quick Checklist

```
[ ] GT_TIER declared
[ ] PARAM_SPEC declared (SEMI only)
[ ] ANSWER_FORMATS declared — keys chosen from the 9 supported formats
[ ] validate_params implemented (SEMI only)
[ ] compute_ground_truth implemented, return shape matches gt_shape
[ ] Generated GT verified: run generate + check options/value fields
[ ] No changes needed to admin, participant, scoring, or frontend (existing formats only)
```

---

## Existing Task Reference

| Task | GT_TIER | answer_format | gt_shape |
|---|---|---|---|
| task01 | AUTO | pct-set | labelled-set |
| task02 | AUTO | pct, mc-single | scalar, mc |
| task03 | SEMI | mc-multi, free-text | mc, reference |
| task04 | AUTO | pct-set, rank | labelled-set, rank |
| task06 | AUTO | pct, mc-single | scalar, mc |
| task07 | AUTO | pct-set | labelled-set |
| task08 | SEMI | matrix | matrix |
| task12 | AUTO | pct, mc-single | scalar, mc |
| task13 | AUTO | free-text | reference |
| task14 | AUTO | mc-multi, free-text | mc, reference |
| task25 | AUTO | pct, count | scalar, scalar |
