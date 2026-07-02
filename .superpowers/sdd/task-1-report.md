# Task 1 Implementation Report — `param_hints` in trial response

## What was changed

**File modified:** `provibackend/ProViBackend/app/routers/participant.py`

### Change 1: Added `task_registry` import (line 10)

```python
from ProViBackend.scripts.tasks import task_registry
```

This matches the exact import pattern already used in `admin.py`.

### Change 2: Added `_build_param_hints` helper (after `_trial_contract_fields`)

```python
def _build_param_hints(task_key: str, parameters: dict) -> list[dict]:
    """Return [{label, value}] for each non-empty configured parameter."""
    hints = []
    for entry in task_registry.get_param_spec(task_key):
        key = entry.get("key", "")
        value = parameters.get(key)
        if value is None or value == "":
            continue
        hints.append({"label": entry["label"], "value": str(value)})
    return hints
```

- Iterates over `PARAM_SPEC` entries for the given `task_key` (returns `[]` for tasks without a `PARAM_SPEC`).
- Skips parameters that are `None` or empty string.
- Converts values to `str` for consistent JSON serialisation.

### Change 3: Called `_build_param_hints` in `get_assigned_trials` and added `param_hints` to trial dict

Inside the loop in `get_assigned_trials`, after `contract = _trial_contract_fields(...)`:

```python
ti = task_instances_by_task_id.get(task_id, {})
parameters = (ti.get("parameters") or {})
param_hints = _build_param_hints(task["task_key"], parameters)
```

And `"param_hints": param_hints` added to the `trials.append({...})` dict.

Note: `task_instances_by_task_id` is already built at line 304 from `exp.get("task_instances", [])`. The `ti` variable here mirrors what `_trial_contract_fields` does internally — extracting the task instance for the current `task_id`. There is no double-fetch; both reads come from the in-memory dict.

## Why these choices

- **Only `get_assigned_trials` was modified**, not `get_active_experiment`. The brief scope is the assignment-based endpoint (Task 2 consumes `trial.param_hints` from the assignment flow). The active-experiment endpoint is a legacy/admin-preview path and adding `param_hints` there was not requested.
- **`_build_param_hints` is a pure helper** with no DB I/O, consistent with the style of `_trial_contract_fields` and `_participant_options`.
- **`parameters` uses `or {}`** to guard against `None` stored in MongoDB (same defensive pattern used for `answer_format` and `ground_truth` in `_trial_contract_fields`).

## Concerns / Surprises

None. The codebase already had all the scaffolding (`task_registry` accessible, `task_instances_by_task_id` built before the loop, `ti` pattern established in `_trial_contract_fields`). The change was mechanical.

## Self-review

- Import added with correct module path (matches admin.py usage).
- Helper function placed logically after existing helpers, before route handlers.
- `_build_param_hints` is called with `task["task_key"]` (not `task_id`), which is what `get_param_spec` expects.
- `parameters` gracefully defaults to `{}` if the task instance is missing or `parameters` key is absent.
- Python AST parse confirms no syntax errors.
- The `"param_hints"` key is added at the end of the trial dict, which is the correct non-breaking addition for downstream consumers.

## Verification

Cannot verify without running backend (no test suite covers FastAPI routes per task brief). Manual verification command from the brief:

```bash
curl -s -b "provi_user_id=<any_valid_cookie>" \
  http://localhost:8000/api/participant/assignment/<experiment_id>/trials \
  | python3 -m json.tool | grep -A5 "param_hints"
```

Expected: each trial object contains `"param_hints": [...]`.
