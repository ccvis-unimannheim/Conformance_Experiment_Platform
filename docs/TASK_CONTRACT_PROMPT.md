You are a backend developer on this conformance-checking platform. I want you to implement the /specify contract (PARAM_SPEC + validate_params) for task{NN}.

SCOPE
- Edit ONLY provibackend/ProViBackend/scripts/tasks/task{NN}.py.
- The single exception is parameter candidate sources (see "PARAMETER WIDGETS & SOURCES" below): only if a PARAM_SPEC entry needs a dataset-derived candidate source that is NOT already registered in _param_candidates, add ONE branch there (provibackend/ProViBackend/app/routers/admin.py) plus a dataset_dir-based enumerator.

BEFORE WRITING ANY CODE — read these first
- The golden example: provibackend/ProViBackend/scripts/tasks/task01.py. Read it in full and mirror exactly how it declares PARAM_SPEC and validate_params.
- ADMIN_EXPERIMENT_SETUP.md, sections "The task contract" and "PARAM_SPEC".
- provibackend/ProViBackend/scripts/tasks/task_registry.py (how the contract attributes are discovered, and the fallbacks for tasks that declare none).

WHAT IS *NOT* IN SCOPE
Answer formats are global and chosen per experiment by the admin on
/answer-format — a task module has no say in them. Do NOT add ANSWER_FORMATS,
GT_TIER, or compute_ground_truth: they no longer exist, and nothing reads them.
There is no automatic grading anywhere in the platform.

DESIGN SPEC for this task (copied from CC_Experiment_Task_Design_2_1.md §2):
- Admin must specify (col E): <paste>

PARAMETER WIDGETS & SOURCES (PARAM_SPEC, for /specify)
`widget` controls how the field renders; `source` is ONLY a dataset-candidate enumerator (it populates a dropdown/datalist from the event log). They are independent. Pick the pattern that fits each col-E param:
1. Numeric / threshold  -> {"widget": "threshold" (or "number"), "default": <num>, "required": bool}. NO `source`. (The frontend renders a number input; nothing to enumerate.)
2. Fixed enum (e.g. time binning day/week/month) -> {"widget": "select-one", "options": ["day","week","month"], "default": "month"}. Hard-code `options` in the spec; NO `source` (the param-spec endpoint preserves a hard-coded `options`).
3. Pick an activity from the log -> {"widget": "activity-picker", "source": "log.activities", "default": "...", "required": true}. Already wired; NO admin.py change.
4. Other dataset-derived candidate list (resources, case attributes, attribute values, ...) -> check whether an existing source already fits (log.activities, log.violations, log.candidate_attributes, log.trace_ids, log.worst_traces, log.time_bins, log.time_granularities). Only if none does: add a branch to _param_candidates AND a dataset_dir-based enumerator (mirror get_log_activities + _dataset_activities caching). Do NOT reuse task-internal helpers that take an already-loaded `log` (e.g. _available_case_attributes) — _param_candidates receives a dataset_id and must load the log itself.
Available widgets: select-one, select-many, number, threshold; anything else (text, activity-picker, attribute-picker, time-binning, ...) renders as a free-text input with a datalist of candidates when the spec provides `options`/`source`.

PARTICIPANT-FACING WORDING
Each PARAM_SPEC entry may carry `hint` (participant-facing phrasing, overrides `label`) and `hide_hint: True` (suppress it entirely — use this when the parameter is internal to reading the chart, e.g. which traces are shown). See participant.py _build_param_hints.

CONSTRAINTS
1. validate_params(log, params) -> list[str] returns human-readable errors; an empty list means valid. It runs BEFORE generation and hard-fails it, so use it for choices that would produce a meaningless visualization (e.g. a split condition present in every trace).
2. Every parameter must actually reach the drawings. Thread it through this task's generate() signature and add it to make_task_generators in scripts/create_all_visualizations.py — that function is the single source of per-task generate() signatures. A parameter that changes no rendered output does not belong in PARAM_SPEC.
3. Prefer acting on the shared data kernel the task computes before drawing, so every idiom of the task reflects the parameter consistently.
4. Reuse this task's existing generate() kwargs and helper functions — do not rewrite the analysis logic.
5. If the task will be answered as free text, author a static RUBRIC string constant. The rubric is a task-level, read-only property (served by /tasks/{task_key}/rubric) for manually coding answers — it feeds no automatic scoring and is never copied into a per-experiment instance.
6. After writing, run the import smoke test in an environment with the backend deps installed (numpy / pandas / pm4py / matplotlib — e.g. the backend container or the project venv):
       cd provibackend && PYTHONPATH=ProViBackend:ProViBackend/scripts python -c "import ProViBackend.scripts.tasks.task{NN}"
   It must complete with no import or syntax errors. (PYTHONPATH must include ProViBackend/scripts because the task modules do `from shared import ...`.)

FIRST STEP — do NOT write code yet
Produce a confirmation table like the one below and wait for me to confirm it before implementing:

| Field | Value I read from the design doc | Please verify |
|-------|----------------------------------|---------------|
| Admin must specify (col E) -> param key / widget / source / default | ... | ... |
| Which idioms the parameter changes, and how | ... | ... |
| validate_params rules | ... | ... |
| RUBRIC (only if answered as free text) | ... | ... |
