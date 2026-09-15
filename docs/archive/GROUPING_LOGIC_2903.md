# Grouping Logic: Current vs Target (29 Mar 2026)

## Part 1 — Current grouping logic (as implemented)

### 1.1 What the “group” is

- After the preliminary questionnaire, the participant calls **`POST /auth/`**.
- The backend assigns a **`dataset_id`** (stored in MongoDB `User` and Redis: `user_id → dataset_id`, plus `dataset_id → dataset_location`).
- **Grouping is effectively “which dataset directory”**; **`GET /vis/mapping`** and **`GET /vis/{svg_id}`** resolve filesystem paths from that `dataset_id`.

### 1.2 Where datasets come from

- When an admin uploads one XES file, the system creates **two** `Dataset` rows for the same upload:
  - `{uuid}_normal` → `output/{title}/normal`
  - `{uuid}_mentalmap` → `output/{title}/mentalmap`
- Admins toggle **`dataset_is_active`**; **only active datasets** enter the assignment pool.

### 1.3 Assignment algorithm

- **`get_least_assigned_dataset_for_user`** (`auth.py`):
  1. Load all existing users with the **same** `expertise_level_process_mining` as the new user.
  2. Load all datasets with **`dataset_is_active: true`**.
  3. Count how many users (from step 1) are already on each active dataset.
  4. Assign the **`dataset_id`** with the **smallest** count (**load balancing**).
- Thus: **within each expertise stratum**, participants are spread approximately evenly across active datasets — **stratification + least-loaded**, not uniform random assignment.

### 1.4 Mapping to experimental design

- There is **no** first-class **`Experiment`**, **`task`**, or **`visualization condition`** in the schema.
- **Between-subject differences** come mainly from which **`dataset_id`** values are active (often normal vs mental-map for the same log, or mixes of uploads if admins activate many rows).
- **Preliminary questionnaire**: required with `POST /auth/`; **expertise** is used for stratification; other fields are stored but **do not** affect assignment today.

### 1.5 Result export

- **`GET /admin/users`**, **`/answers`**, **`/uitracking`** export whole collections as CSV.
- There is **no** **`experiment_id`**, no explicit **visualization condition** column (only **inferable** from `dataset_id` / paths).

---

## Part 2 — Target grouping logic (product design)

### 2.1 Admin journey (configure an experiment)

1. After **login**, configure an experiment.
2. **Choose a Task** first; the system reports:
   - **How many datasets** the task requires (e.g. one vs several);
   - Which **visualizations (idioms)** are valid for that task (or the selectable set).
3. The admin selects:
   - The **required number** of datasets;
   - **Several** visualizations (count **V** or a list).
4. **Declare the factorial structure** (including mixed designs):
   - Which factors are **between-subjects** (e.g. dataset, visualization, or only one of them);
   - Which factors are **within-subjects** (the same participant sees multiple visualization types, etc.);
   - **Number of “groups”** follows the design: e.g. if **visualization** is purely between with **V** levels → **V** groups; if **visualization** is **within**, participants are **not** partitioned into **V** disjoint groups — each gets a **trial sequence**.
5. **Assignment policy (random family only)**:
   - Optional stratification on **some** preliminary fields, or **no** use of prelim for assignment;
   - Configurable **target group sizes** (balanced or weighted);
   - Under **pure balanced random**, stratification fields are **not required** for assignment; the full prelim may still be kept for analysis or compliance.

### 2.2 Participant flow and when assignment runs

- **Between factors**: typically assigned **once** at enrollment / first auth and kept for the session (unless you define multi-stage studies).
- **Within factors**: no single static “group”; generate an **order / trial list** and maintain **progress** across blocks.
- **Mixed designs**: **one** between assignment **plus** a **within sequence** (or order randomization); persisted data must tag **trials**.

### 2.3 Result export

- Exports should carry **`experiment_id`**, **between** levels, **within** trial / level, **presentation order**, etc., for mixed and repeated-measures analyses.

---

## Part 3 — Current vs target (summary table)

| Dimension | Current | Target |
|-----------|---------|--------|
| Configuration | Admin toggles multiple `dataset_is_active` | Explicit **experiment**: Task → dataset count & list → visualizations & design type |
| Object of assignment | `dataset_id` (incl. `_normal` / `_mentalmap` rows) | `experiment` + **between condition** + **within sequence** when applicable |
| Algorithm | Stratify by expertise + least load across **active** datasets | Configurable: **optional strata** + **balanced / weighted random**; supports pure random |
| Link to Task / Viz | Not modeled; implied by uploads + active list | Task fixes dataset cardinality and idiom set; aligns with between/within |
| Prelim vs assignment | Required; expertise drives strata | Assignment may **ignore** some items; optional required fields |
| Export | Full-collection CSV; no experiment / trial axes | Filter by experiment + condition / trial metadata |

---

## Part 4 — Migration / implementation notes (high level)

1. **Experiment + task metadata** (e.g. `TaskDefinition`, `Experiment`, `assignment_spec`) — cannot rely on “global active datasets” alone.
2. **Extend `User` or add `Enrollment`**: `experiment_id`, **between** assignment fields, **`trial_sequence`**, **`current_trial_index`**, etc.
3. **Rewrite `POST /auth/` (or add `enroll`)**: inputs = experiment config + optional prelim; outputs = **between** assignment and, if needed, **within** order.
4. **`/vis`, questionnaire, UI logging**: resolve **current trial / condition**; attach **trial id** to answers and logs.
5. **Admin export**: join on **`experiment_id`** and emit design columns.

**Suggested implementation order:** data model + Mongo access → auth/enroll → admin CRUD + export → vis/questionnaire → frontend wizard + multi-block flow + tracking fields.

---

## Part 5 — Scope of this document

This note aligns **what the codebase does today** with **what the product should support** for planning and API design. It **does not** replace IRB documents, pre-registration, or the final statistical analysis plan.

---

## Part 6 — Database changes to express within- vs between-subjects

This section focuses on **how the datastore should represent** between and within factors. Names can follow your ERD (`Experiment`, `UserAssignment`, `Answers`, etc.).

### 6.1 Experiment-level (design declaration)

- Add or extend an **`Experiment`** (or equivalent) document that **declares** the design, for example:
  - **`between_factors`**: ordered list of factor names and their **levels** (e.g. `idiom` → `[dfg, petri, ...]`; optionally `dataset` if dataset is between-subjects).
  - **`within_factors`**: factors repeated **per participant** (e.g. `idiom` when everyone sees multiple idioms on the **same** assigned dataset).
  - **`design_type`**: `between_only` | `within_only` | `mixed` (or a small enum set).
- Store **assignment knobs** as **concrete fields** rather than a single opaque `AssignmentStrategy` string (see below): e.g. `stratification_fields[]`, `between_balance_mode` (`equal` | `weighted`), optional `group_weights`, `within_sequence_mode` (`random` | `fixed` | `latin_square`), optional caps/quotas.

This makes **within vs between** **queryable and validatable** at save time (e.g. “if `design_type=mixed`, require `within_factors` non-empty and `UserAssignment` sequence”).

### 6.2 Per-participant assignment (`UserAssignment` or extended `User`)

- **Between-subjects**: persist **one** resolved level per between factor, e.g.:
  - `group_id` (cross-product code or canonical id), **or**
  - `assigned_between: { dataset_id?, idiom_id?, ... }` (snapshot **IDs actually used**, not only labels).
- **Within-subjects**: persist an **ordered** structure, e.g.:
  - `trial_sequence: [{ trial_index, within_level: { idiom_id, ... }, dataset_id? }, ...]`
  - `current_trial_index` (or `current_block_id`) for server-side progression.
- **Snapshot** dataset / idiom **identifiers at enrollment** so later admin edits to `Experiment` do not break ongoing participants.

**Rule of thumb:** anything needed to render the **next** screen for this user should be reconstructible from **this row** (plus `Experiment`), not only from Redis.

### 6.3 Observational collections (`Answers`, `UI_Logging`, …)

For every row, add (when applicable):

- `experiment_id`
- **Between** tags (redundant copy acceptable for export): e.g. `group_id`, `between_dataset_id`, `between_idiom_id`
- **Within** tags: `trial_index`, `within_idiom_id` (or generic `within_level`), `presentation_order`

Then mixed designs remain **analyzable** without inferring from timestamps alone.

### 6.4 `Task` / `Question` / `GroundTruth`

- If **dataset** is between-subjects, **ground truth** and stimuli should key off **`dataset_id`** (or per-level id).
- If **idiom** is within-subjects, the **same** `question_id` may appear in **multiple trials** with **different** `idiom_id`; **primary key** for an answer row must include **`user_id` + `experiment_id` + `trial_index`** (or equivalent), not only `question_id`.

### 6.5 Redis and Mongo

- Redis can remain a **cache** of `user_id → { experiment_id, current_trial, ... }` for hot paths; **authoritative** state should live in **`UserAssignment` / Mongo** so restarts do not lose assignment.
- Alternatively, drop Redis for assignment and read Mongo each time if load is acceptable — the important part is **one source of truth** that includes **between + within** state.

### 6.6 Clarifying `AssignmentStrategy`

If the schema keeps a single **`assignment_strategy`** field, constrain it to a **small enum** mapped to server code paths, e.g. `RANDOM_BALANCED`, `STRATIFIED_BALANCED`, `STRATIFIED_WEIGHTED`, or **replace** it with the explicit subfields in §6.1 so the implementation is not “one vague string.”

---

*End of document.*
