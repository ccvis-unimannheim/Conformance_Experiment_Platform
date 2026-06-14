You are a backend developer on this conformance-checking platform. I want you to implement the /specify + /answer-format-groundtruth contract for task{NN}.

SCOPE
- Edit ONLY provibackend/ProViBackend/scripts/tasks/task{NN}.py.
- The single exception is parameter candidate sources (see "PARAMETER WIDGETS & SOURCES" below): only if a PARAM_SPEC entry needs a dataset-derived candidate source that is NOT already registered in _param_candidates, add ONE branch there (provibackend/ProViBackend/app/routers/admin.py) plus a dataset_dir-based enumerator. Today the only registered source is "log.activities".

BEFORE WRITING ANY CODE — read these first
- The golden example: provibackend/ProViBackend/scripts/tasks/task01.py. Read it in full and mirror exactly how it declares GT_TIER / PARAM_SPEC / ANSWER_FORMATS / validate_params / compute_ground_truth.
- ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §3–§8.
- provibackend/ProViBackend/scripts/tasks/task_registry.py (how the contract attributes are discovered, and the safe fallbacks for unauthored tasks).

DESIGN SPEC for this task (copied from CC_Experiment_Task_Design_2_1.md §2):
- Format (col D):            <paste>
- Admin must specify (col E): <paste>
- GT tier:                    <AUTO | SEMI | MANUAL>
- GT method / tool (col H):   <paste>

PARAMETER WIDGETS & SOURCES (PARAM_SPEC, for /specify)
`widget` controls how the field renders; `source` is ONLY a dataset-candidate enumerator (it populates a dropdown/datalist from the event log). They are independent. Pick the pattern that fits each col-E param:
1. Numeric / threshold  -> {"widget": "threshold" (or "number"), "default": <num>, "required": bool}. NO `source`. (The frontend renders a number input; nothing to enumerate.)
2. Fixed enum (e.g. time binning day/week/month) -> {"widget": "select-one", "options": ["day","week","month"], "default": "month"}. Hard-code `options` in the spec; NO `source` (the param-spec endpoint preserves a hard-coded `options`).
3. Pick an activity from the log -> {"widget": "activity-picker", "source": "log.activities", "default": "...", "required": true}. Already wired; NO admin.py change.
4. Other dataset-derived candidate list (resources, case attributes, attribute values, ...) -> needs a NEW `source`. Only then: add a branch to _param_candidates AND a dataset_dir-based enumerator (mirror get_log_activities + _dataset_activities caching). Do NOT reuse task-internal helpers that take an already-loaded `log` (e.g. _available_case_attributes) — _param_candidates receives a dataset_id and must load the log itself.
Available widgets: select-one, select-many, number, threshold; anything else (text, activity-picker, attribute-picker, time-binning, ...) renders as a free-text input with a datalist of candidates when the spec provides `options`/`source`.

CONSTRAINTS
1. The signature compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) is FIXED and called positionally — do not change it.
2. compute_ground_truth returns ONLY the raw shape fields; the backend (admin.py _build_gt_block) assembles the full GroundTruthBlock. The returned dict must match the chosen format's declared gt_shape:
   - gt_shape "scalar"       (formats: pct / count / decimal)  -> {"value": "<e.g. '96%'>"}
   - gt_shape "labelled-set" (formats: pct-set / count-set)    -> {"options": [{"label": ..., "value": ..., "correct": true}, ...]}
   - gt_shape "mc"           (formats: mc-single / mc-multi)   -> {"options": [{"label": ..., "value": ..., "correct": bool}, ...]}  (full closed set INCLUDING distractors, correct one(s) flagged)
   - gt_shape "rank"         (format: rank)                    -> {"options": [{"label": ..., "value": ...}, ...]} in the correct order (index 0 = rank 1)
   - gt_shape "matrix"       (format: matrix)                  -> {"options": [{"label": ..., "value": ..., "correct": bool}, ...]} (one entry per cell, correct cells flagged)
   - gt_shape "reference"    (format: free-text)               -> {"reference": "..."} (OPTIONAL; usually omitted — see RUBRIC note)
   NOTE: rank and matrix use the `options` list (the RankEditor/MatrixEditor read gt.options), NOT `value`, despite the loose wording in the plan §3 comment.
3. Reuse this task's existing generate() kwargs and helper functions — do not rewrite the analysis logic.
4. GT_TIER governs auto-computation: AUTO/SEMI implement compute_ground_truth; MANUAL does not (no decisive value is computed).
5. If ANSWER_FORMATS includes free-text, author a static RUBRIC string constant. The rubric is a task-level, read-only property (served by /tasks/{task_key}/rubric) — it is NOT seeded into or editable on a per-experiment instance. free-text/MANUAL tasks generally do not need compute_ground_truth.
6. After writing, run the import smoke test in an environment with the backend deps installed (numpy / pandas / pm4py / matplotlib — e.g. the backend container or the project venv):
       cd provibackend && PYTHONPATH=ProViBackend:ProViBackend/scripts python -c "import ProViBackend.scripts.tasks.task{NN}"
   It must complete with no import or syntax errors. (PYTHONPATH must include ProViBackend/scripts because the task modules do `from shared import ...`.)

FIRST STEP — do NOT write code yet
Produce a confirmation table like the one below and wait for me to confirm it before implementing:

| Field | Value I read from the design doc | Please verify |
|-------|----------------------------------|---------------|
| Answer format (col D) | ... | ... |
| GT tier (col G)       | ... | ... |
| Admin must specify (col E) -> param key / widget / source / default | ... | ... |
| GT method (col H) -> exact return shape & per-row meaning | ... | ... |
| RUBRIC                | ... | ... |
