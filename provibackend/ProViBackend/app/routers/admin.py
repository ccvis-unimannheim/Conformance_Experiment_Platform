import json
import uuid
import io
import csv
import re
import shutil
import sys
import os
import logging
from fastapi import APIRouter, BackgroundTasks, UploadFile, HTTPException, Form
from fastapi.responses import StreamingResponse, JSONResponse
_logger = logging.getLogger(__name__)
_scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    from ProViBackend.scripts.create_all_visualizations import (
        run_pipeline as run_visualization_pipeline,
        generate_for_task_instances,
        get_log_activities,
        get_log_time_granularities,
        get_log_violations,
        get_log_worst_traces,
        get_log_trace_ids,
        get_log_candidate_attributes,
        get_log_violated_activities_task34,
        _FILE_RENAME,
        _TASK_RENAME_SKIP,
    )
except ImportError:
    # The visualization pipeline pulls in heavy, optional deps (pm4py, etc.).
    # Degrade gracefully so the rest of the admin API still works, but log the
    # full traceback so the cause is never hidden.
    _logger.exception("Could not import visualization pipeline; run_pipeline disabled")
    run_visualization_pipeline = None
    generate_for_task_instances = None
    get_log_activities = None
    get_log_time_granularities = None
    get_log_violations = None
    get_log_worst_traces = None
    get_log_trace_ids = None
    get_log_candidate_attributes = None
    get_log_violated_activities_task34 = None
    _FILE_RENAME = {}
    _TASK_RENAME_SKIP = {}

try:
    from ProViBackend.scripts.tasks import task_registry
    _TASK_MODULES = task_registry.TASK_MODULES
except ImportError:
    # These task modules are required for the task-idiom mapping. Failing fast
    # here surfaces the problem in startup logs instead of silently returning an
    # empty mapping (which makes the admin UI show every idiom for every task).
    _logger.exception("Failed to import task modules required for /task-idioms")
    raise
from ProViBackend.utils import config, utils
from ProViBackend.app.datamodels import data_schemas as ds
import pathlib as pl

import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.redis_handler as redis_handler
from ProViBackend.utils.database.migration import (
    task_instances_to_configs,
    task_configs_to_instances,
)

router = APIRouter(
    prefix="/admin"
)

DATA_DIRECTORY = config.BASE_DIRECTORY / "data"

# Bundled sample dataset used by the "Preview with sample data" feature.
# Generated at startup by scripts/generate_sample_data.py.
_SCRIPTS_PATH = pl.Path(__file__).parents[2] / "scripts"
SAMPLE_DATA_DIR = _SCRIPTS_PATH / "sample_data"

# In-memory preview status: experiment_id -> mode -> task_key -> status string.
# Ephemeral — lost on restart, which is fine (preview is a transient UX step).
_preview_status: dict[str, dict[str, dict[str, str]]] = {}

ALLOWED_LOG_EXTENSIONS   = {".xes", ".csv"}
ALLOWED_MODEL_EXTENSIONS = {".bpmn"}
EVENTLOG_BASENAME = "EventLog"
GUIDELINE_FILENAME = "Guideline.bpmn"

# Cache of distinct activity names per dataset, so /specify's param-spec
# candidate enumeration doesn't reload the event log on every page render
# (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §5). Keyed by dataset_id.
_LOG_ACTIVITIES_CACHE: dict[str, list[str]] = {}
# Cache of dataset-meaningful time-bin granularities (task07), same rationale.
_LOG_TIME_GRANULARITIES_CACHE: dict[str, list[str]] = {}
# Cache of distinct (activity, move_type) violation pairs (task11); alignment
# computation is expensive, so results are cached in-process per dataset_id.
_LOG_VIOLATIONS_CACHE: dict[str, list[dict]] = {}
# Cache of top-10 worst-fitness traces (task34); alignment computation is shared
# with _LOG_VIOLATIONS_CACHE but cached separately to avoid coupled invalidation.
_LOG_WORST_TRACES_CACHE: dict[str, list[dict]] = {}
# Cache of all traces as {value, label} picker options (task04's trace_ids).
_LOG_TRACE_IDS_CACHE: dict[str, list[dict]] = {}
# Cache of bucketable candidate attributes (task20's attribute_set picker).
_LOG_CANDIDATE_ATTRS_CACHE: dict[str, list[dict]] = {}
# Cache of violated activities for task34's activity-picker dropdown.
_LOG_VIOLATED_ACTS_TASK34_CACHE: dict[str, list[dict]] = {}


def _dataset_activities(dataset_id: str) -> list[str]:
    """Sorted distinct activities in a dataset's event log (cached)."""
    if dataset_id in _LOG_ACTIVITIES_CACHE:
        return _LOG_ACTIVITIES_CACHE[dataset_id]
    if get_log_activities is None:
        return []
    activities = get_log_activities(str(DATA_DIRECTORY / dataset_id))
    _LOG_ACTIVITIES_CACHE[dataset_id] = activities
    return activities


def _dataset_time_granularities(dataset_id: str) -> list[str]:
    """Time-bin granularities that yield >=2 bins for this dataset (cached)."""
    if dataset_id in _LOG_TIME_GRANULARITIES_CACHE:
        return _LOG_TIME_GRANULARITIES_CACHE[dataset_id]
    if get_log_time_granularities is None:
        return []
    grans = get_log_time_granularities(str(DATA_DIRECTORY / dataset_id))
    _LOG_TIME_GRANULARITIES_CACHE[dataset_id] = grans
    return grans


def _dataset_violations(dataset_id: str) -> list[dict]:
    """Distinct (activity, move_type) violation pairs for this dataset (cached).

    Each element is {"value": "activity|move_type", "label": "activity · Type  (N traces, X%)"}.
    Alignment computation runs once on first call; subsequent calls return the cache.
    """
    if dataset_id in _LOG_VIOLATIONS_CACHE:
        return _LOG_VIOLATIONS_CACHE[dataset_id]
    if get_log_violations is None:
        return []
    violations = get_log_violations(str(DATA_DIRECTORY / dataset_id))
    _LOG_VIOLATIONS_CACHE[dataset_id] = violations
    return violations


def _dataset_worst_traces(dataset_id: str) -> list[dict]:
    """Top-10 worst-fitness traces for this dataset as dropdown options (cached)."""
    if dataset_id in _LOG_WORST_TRACES_CACHE:
        return _LOG_WORST_TRACES_CACHE[dataset_id]
    if get_log_worst_traces is None:
        return []
    traces = get_log_worst_traces(str(DATA_DIRECTORY / dataset_id))
    _LOG_WORST_TRACES_CACHE[dataset_id] = traces
    return traces


def _dataset_trace_ids(dataset_id: str) -> list[dict]:
    """All traces of this dataset as {value, label} picker options (task04, cached)."""
    if dataset_id in _LOG_TRACE_IDS_CACHE:
        return _LOG_TRACE_IDS_CACHE[dataset_id]
    if get_log_trace_ids is None:
        return []
    traces = get_log_trace_ids(str(DATA_DIRECTORY / dataset_id))
    _LOG_TRACE_IDS_CACHE[dataset_id] = traces
    return traces


def _dataset_candidate_attributes(dataset_id: str) -> list[dict]:
    """Bucketable candidate attributes for task20's attribute_set picker (cached)."""
    if dataset_id in _LOG_CANDIDATE_ATTRS_CACHE:
        return _LOG_CANDIDATE_ATTRS_CACHE[dataset_id]
    if get_log_candidate_attributes is None:
        return []
    attrs = get_log_candidate_attributes(str(DATA_DIRECTORY / dataset_id))
    _LOG_CANDIDATE_ATTRS_CACHE[dataset_id] = attrs
    return attrs


def _dataset_violated_activities_task34(dataset_id: str) -> list[dict]:
    """Violated activities for task34's activity-picker dropdown (cached)."""
    if dataset_id in _LOG_VIOLATED_ACTS_TASK34_CACHE:
        return _LOG_VIOLATED_ACTS_TASK34_CACHE[dataset_id]
    if get_log_violated_activities_task34 is None:
        return []
    acts = get_log_violated_activities_task34(str(DATA_DIRECTORY / dataset_id))
    _LOG_VIOLATED_ACTS_TASK34_CACHE[dataset_id] = acts
    return acts


# Maps a PARAM_SPEC entry's `source` to the dataset-candidate enumerator.
def _param_candidates(source: str, dataset_id: str) -> list:
    if source == "log.activities":
        return _dataset_activities(dataset_id)
    if source == "log.time_granularities":
        return _dataset_time_granularities(dataset_id)
    if source == "log.violations":
        return _dataset_violations(dataset_id)
    if source == "log.worst_traces":
        return _dataset_worst_traces(dataset_id)
    if source == "log.trace_ids":
        return _dataset_trace_ids(dataset_id)
    if source == "log.candidate_attributes":
        return _dataset_candidate_attributes(dataset_id)
    if source == "log.violated_activities_task34":
        return _dataset_violated_activities_task34(dataset_id)
    return []


def _validate_extension(filename: str, allowed: set, label: str) -> str:
    """Return the lower-cased extension if allowed, else raise HTTP 400."""
    ext = pl.Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"{label} must have one of {sorted(allowed)} extensions, got '{ext}'.",
        )
    return ext


@router.post("/datasets/pair", tags=["admin"])
async def upload_dataset_pair(
    log: UploadFile,
    guideline: UploadFile,
    dataset_title: str = Form(None),
):
    """Upload an event log + BPMN guideline.

    Generation no longer runs at upload time (see ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md
    §7) — it is triggered per-experiment via POST /admin/experiments/{id}/generate,
    once the admin has selected idioms (/idiom) and hyperparameters (/specify).
    """
    # Validate file extensions BEFORE creating any directories on disk
    log_ext = _validate_extension(log.filename, ALLOWED_LOG_EXTENSIONS, "Event log")
    _validate_extension(guideline.filename, ALLOWED_MODEL_EXTENSIONS, "Guideline")

    pair_id    = str(uuid.uuid4())
    pair_dir   = DATA_DIRECTORY / pair_id
    input_dir  = pair_dir / "input"
    output_dir = pair_dir / "output"

    try:
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Normalize filenames to the pipeline's expected convention,
        # so the pipeline can find them regardless of the original upload name.
        log_path       = input_dir / f"{EVENTLOG_BASENAME}{log_ext}"
        guideline_path = input_dir / GUIDELINE_FILENAME

        log_path.write_bytes(await log.read())
        guideline_path.write_bytes(await guideline.read())

        dataset_pair = ds.DatasetPair(
            dataset_id=pair_id,
            dataset_title=dataset_title or pl.Path(log.filename).stem,
            dataset_is_active=False,
            insert_datetime=utils.get_current_datetime(),
            log=ds.DatasetFile(
                filename=log_path.name,                 # normalized name on disk
                location=str(log_path),                 # absolute path inside container
                checksum=utils.get_file_checksum(log_path),
            ),
            guideline=ds.DatasetFile(
                filename=guideline_path.name,
                location=str(guideline_path),
                checksum=utils.get_file_checksum(guideline_path),
            ),
        )

        db = dbc.connect_to_database()
        db["DatasetPair"].insert_one(dataset_pair.model_dump())

        return {"dataset_id": pair_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload dataset pair: {str(e)}")
    finally:
        await log.close()
        await guideline.close()


# Todo: Add validation for csv file and verify content after df structure.
@router.post("/questionnaire", tags=["admin"])
async def upload_questionnaire_data(file: UploadFile):
    try:
        contents = file.file.read()
        file_path = config.BASE_DIRECTORY / "app/static/questionnaire.csv"
        with open(utils.convert_path_to_str(file_path), 'wb') as f:
            f.write(contents)
        return {"message": f"Successfully uploaded {file.filename}"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload file")
    finally:
        file.file.close()


def generate_csv_for_download(collection_name: str):
    # download all data from database from collection
    data = dbc.get_query_db(collection_name, query={})
    output = io.StringIO()
    writer = csv.writer(output)
    # Write header
    if data:
        writer.writerow(data[0].keys())
    # Write data rows
    for item in data:
        writer.writerow(item.values())
    output.seek(0)
    return output


# Todo: If bad performance, consider using a background task/celery
@router.get("/users", tags=["admin"])
async def get_users_data_from_db():
    data = generate_csv_for_download("User")
    response = StreamingResponse(data, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=user_collection_data.csv"
    return response


@router.get("/answers", tags=["admin"])
async def get_answers_from_db():
    data = generate_csv_for_download("Answer")
    response = StreamingResponse(data, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=answer_collection_data.csv"
    return response


@router.get("/experiments/{experiment_id}/answers/download", tags=["admin"])
async def download_experiment_answers(experiment_id: str):
    """Download experiment data as an Excel file with four sheets:
    Sheet 1 - Participant background (prequestionnaire + knowledge survey)
    Sheet 2 - Task answers
    Sheet 3 - End-page survey ratings
    Sheet 4 - Blind review (_id, task_name, answer only — for blind scoring)
    """
    import pandas as pd

    # ── Sheet 2: task answers ──────────────────────────────────────────────
    answers = dbc.get_query_db("Answer", query={"experiment_id": experiment_id})
    df_answers = pd.DataFrame(answers) if answers else pd.DataFrame()

    # ── Sheet 1: participant background ───────────────────────────────────
    user_ids = list({a["user_id"] for a in answers}) if answers else []

    # Pre-load all knowledge questions ordered by kq_key so column order is stable
    kq_all = sorted(
        dbc.get_query_db("KnowledgeQuestion", {}),
        key=lambda q: q.get("kq_key", ""),
    )

    level_map = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}
    rows = []
    for uid in user_ids:
        user = dbc.get_document("User", {"user_id": uid})
        if not user:
            continue
        pre  = dbc.get_document("PreliminaryAnswers", {"_id": user.get("preliminary_id", "")}) or {}
        know = dbc.get_document("KnowledgeAnswers",   {"_id": user.get("knowledge_id",   "")}) or {}

        # Parse the per-question answer map stored as JSON in know["notes"]
        raw_notes = know.get("notes", "{}")
        try:
            notes: dict = json.loads(raw_notes) if isinstance(raw_notes, str) else (raw_notes or {})
        except Exception:
            notes = {}

        row: dict = {
            "user_id": uid,
            **{k: v for k, v in pre.items() if k != "_id"},
        }

        # One response + score column per knowledge question
        # Scoring rule: correct = 1, wrong = 0, "I don't know" = 0 (no correction for guessing)
        for q in kq_all:
            qid        = q["_id"]
            kq_key     = q.get("kq_key", qid)
            options    = q.get("options", [])
            correct_i  = q.get("correct_option_index")
            selected_i = notes.get(qid)

            if selected_i is None:
                response_text = ""
                q_score       = ""
            else:
                response_text = options[selected_i] if selected_i < len(options) else str(selected_i)
                q_score       = "" if correct_i is None else int(selected_i == correct_i)

            row[f"{kq_key}_response"] = response_text
            row[f"{kq_key}_score"]    = q_score

        row["knowledge_score_total"] = know.get("score", "")
        row["knowledge_level"]       = level_map.get(know.get("level"), know.get("level", ""))
        row["pm_tools"]              = ", ".join(pre.get("tools", [])) if pre.get("tools") else ""
        rows.append(row)

    df_background = pd.DataFrame(rows) if rows else pd.DataFrame()

    # ── Clean up Task Answers columns ─────────────────────────────────────
    if not df_answers.empty:
        # Resolve task_id → task_key + task_name
        unique_task_ids = df_answers["task_id"].dropna().unique().tolist()
        task_lookup = {}
        for tid in unique_task_ids:
            doc = dbc.get_document("Task", {"_id": tid})
            if doc:
                task_lookup[tid] = {"task_key": doc.get("task_key", ""), "task_name": doc.get("label", "")}
        df_answers["task_key"] = df_answers["task_id"].map(lambda x: task_lookup.get(x, {}).get("task_key", ""))
        df_answers["task_name"] = df_answers["task_id"].map(lambda x: task_lookup.get(x, {}).get("task_name", ""))

        # Resolve idiom_id → idiom_key + idiom_name
        unique_idiom_ids = df_answers["idiom_id"].dropna().unique().tolist()
        idiom_lookup = {}
        for iid in unique_idiom_ids:
            doc = dbc.get_document("Idiom", {"_id": iid})
            if doc:
                idiom_lookup[iid] = {"idiom_key": doc.get("idiom_key", ""), "idiom_name": doc.get("label", "")}
        df_answers["idiom_key"] = df_answers["idiom_id"].map(lambda x: idiom_lookup.get(x, {}).get("idiom_key", ""))
        df_answers["idiom_name"] = df_answers["idiom_id"].map(lambda x: idiom_lookup.get(x, {}).get("idiom_name", ""))

        # Add ground truth from experiment task_instances
        exp_doc = dbc.get_document("Experiment", {"_id": experiment_id})
        gt_by_task = {}
        if exp_doc:
            for ti in exp_doc.get("task_instances", []):
                gt_by_task[ti.get("task_id")] = {
                    "ground_truth": ti.get("ground_truth"),
                    "answer_format": ti.get("answer_format"),
                }
        df_answers["ground_truth"] = df_answers["task_id"].map(
            lambda x: str(gt_by_task.get(x, {}).get("ground_truth", "")) if gt_by_task.get(x, {}).get("ground_truth") is not None else ""
        )
        df_answers["answer_format"] = df_answers["task_id"].map(
            lambda x: gt_by_task.get(x, {}).get("answer_format", "")
        )

        if "response_time_ms" in df_answers.columns:
            df_answers["response_time_s"] = (df_answers["response_time_ms"] / 1000).round(2)
            df_answers = df_answers.drop(columns=["response_time_ms"])
        if "insert_datetime" in df_answers.columns:
            df_answers = df_answers.rename(columns={"insert_datetime": "completion_time"})

        # Post-task idiom ratings (1–7 Likert; higher = stronger agreement)
        df_answers = df_answers.rename(columns={
            "capabilities_meet_requirements": "capabilities_meet_requirements (1-7)",
            "easy_to_use": "easy_to_use (1-7)",
        })

    # ── Sheet 3: end-page survey ratings ──────────────────────────────────
    RATING_KEYS = [
        ("priorKnowledge", "Prior Knowledge"),
        ("clarity",        "Clarity of Instructions"),
        ("readability",    "Readability of Visualizations"),
        ("helpfulness",    "Helpfulness of Tooltips"),
        ("usefulness",     "Usefulness of Visualizations"),
        ("difficulty",     "Difficulty of Tasks"),
        ("effort",         "Time & Effort Required"),
    ]
    survey_rows = []
    for uid in (list({a["user_id"] for a in answers}) if answers else []):
        user = dbc.get_document("User", {"user_id": uid})
        if not user or not user.get("feedback_id"):
            continue
        fb = dbc.get_document("FeedbackAnswers", {"_id": user["feedback_id"]}) or {}
        ratings = fb.get("ratings") or {}
        row = {"user_id": uid}
        for key, col in RATING_KEYS:
            row[col] = ratings.get(key)
        row["Additional Feedback"] = fb.get("feedback")
        survey_rows.append(row)
    df_survey = pd.DataFrame(survey_rows) if survey_rows else pd.DataFrame()

    # ── Sheet 4: blind review ─────────────────────────────────────────────
    # Minimal columns only, so answers can be scored without revealing the
    # participant, idiom, or ground truth. _id keys each row back to the
    # Task Answers sheet.
    BLIND_COLS = ["_id", "task_name", "answer"]
    if not df_answers.empty:
        df_blind = df_answers.reindex(columns=BLIND_COLS).copy()
        df_blind["_id"] = df_blind["_id"].astype(str)
        # Shuffle rows so adjacency can't leak the participant/idiom grouping.
        df_blind = df_blind.sample(frac=1).reset_index(drop=True)
    else:
        df_blind = pd.DataFrame(columns=BLIND_COLS)

    # ── Write to Excel ─────────────────────────────────────────────────────
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_background.to_excel(writer, sheet_name="Participant Background", index=False)
        df_answers.to_excel(writer, sheet_name="Task Answers", index=False)
        df_survey.to_excel(writer, sheet_name="End Survey", index=False)
        df_blind.to_excel(writer, sheet_name="Blind Review", index=False)
    output.seek(0)

    response = StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["Content-Disposition"] = (
        f"attachment; filename=experiment_{experiment_id}_data.xlsx"
    )
    return response


@router.get("/uitracking", tags=["admin"])
async def get_ui_tracking_from_db():
    data = generate_csv_for_download("UILogging")
    response = StreamingResponse(data, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=ui_logging_collection_data.csv"
    return response


@router.get("/datasets", tags=["admin"])
async def get_datasets_from_db():
    pairs = dbc.get_query_db("DatasetPair",
                             query={},
                             projection={"_id": 0,
                                         "dataset_id": 1,
                                         "dataset_title": 1,
                                         "dataset_is_active": 1,
                                         "insert_datetime": 1,
                                         "log.filename": 1,
                                         "guideline.filename": 1,
                                         })
    return JSONResponse(content=pairs)


@router.delete("/datasets/{dataset_id}", tags=["admin"])
async def delete_dataset(dataset_id: str, force: bool = False):
    db = dbc.connect_to_database()
    referencing = list(db["Experiment"].find({"dataset_ids": dataset_id}))

    if referencing and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Dataset is referenced by experiments.",
                "referencing_experiments": [
                    {"_id": e["_id"], "name": e.get("name"), "status": e.get("status")}
                    for e in referencing
                ],
            },
        )

    demoted = []
    for exp in referencing:
        new_ids = [d for d in exp.get("dataset_ids", []) if d != dataset_id]
        db["Experiment"].update_one(
            {"_id": exp["_id"]},
            {"$set": {"dataset_ids": new_ids, "status": "draft"}},
        )
        demoted.append({"_id": exp["_id"], "name": exp.get("name")})

    pair_dir = DATA_DIRECTORY / dataset_id
    if pair_dir.exists():
        shutil.rmtree(pair_dir, ignore_errors=True)

    result = db["DatasetPair"].delete_one({"dataset_id": dataset_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")

    return JSONResponse(content={"message": "Dataset deleted.", "demoted_experiments": demoted})


# Todo: Add validation for dataset_id and dataset_is_active that always two datasets are selected as active
@router.post("/datasets", tags=["admin"])
async def select_active_datasets(selected_datasets_from_frontend: ds.ListDatasetsFromFrontend):
    # update dataset_is_active in database
    for dataset in selected_datasets_from_frontend.datasets:
        dbc.update_dataset_is_active_status(dataset.dataset_id, dataset.is_active)
    return {"message": "Successfully updated dataset_is_active in database"}


@router.get("/usagedataset", tags=["admin"])
async def get_users_usage_of_datasets():
    # dataset assignment is stored in UserAssignment.assigned_between (Dict[str, str])
    assignments = dbc.get_query_db("UserAssignment", query={})
    dataset_usage_count = {}
    for assignment in assignments:
        assigned_between = assignment.get("assigned_between", {})
        for dataset_id in assigned_between.values():
            dataset_usage_count[dataset_id] = dataset_usage_count.get(dataset_id, 0) + 1
    return dataset_usage_count


# ---------------------------------------------------------------------------
# Idiom management
# ---------------------------------------------------------------------------

@router.post("/idioms", tags=["admin"])
async def create_idiom(idiom: ds.Idiom):
    dbc.create_document("Idiom", idiom.model_dump(by_alias=True))
    return JSONResponse(content={"message": f"Idiom '{idiom.label}' created.", "idiom_id": idiom.id}, status_code=201)


@router.get("/idioms", tags=["admin"])
async def get_idioms():
    idioms = dbc.get_query_db("Idiom", query={})
    for doc in idioms:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    return JSONResponse(content=idioms)


# ---------------------------------------------------------------------------
# Task management
# ---------------------------------------------------------------------------

@router.post("/tasks", tags=["admin"])
async def create_task(task: ds.Task):
    dbc.create_document("Task", task.model_dump(by_alias=True))
    return JSONResponse(content={"message": f"Task '{task.label}' created.", "task_id": task.id}, status_code=201)


@router.get("/tasks", tags=["admin"])
async def get_tasks():
    tasks = dbc.get_query_db("Task", query={})
    for doc in tasks:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    tasks.sort(key=lambda t: int(re.search(r'\d+', t.get("task_key", "0")).group()))
    return JSONResponse(content=tasks)


@router.patch("/tasks/{task_id}", tags=["admin"])
async def update_task(task_id: str, update_data: ds.TaskUpdate):
    fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    # Marks this document as admin-customized so the startup seed (main.py
    # _seed_collection) stops overwriting it with seed_data.py's hardcoded values.
    fields["_admin_edited"] = True
    updated = dbc.update_document("Task", query={"_id": task_id}, update={"$set": fields})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return JSONResponse(content={"message": "Task updated.", "task_id": task_id})


@router.get("/task-idioms", tags=["admin"])
async def get_task_idioms():
    """Returns {task_key: [canonical_idiom_key, ...]} from each task script's IDIOMS list.

    Raw idiom names from task scripts use file-stem conventions (e.g. scatter_plot,
    flow_chart_elaborate_bpmn); this endpoint translates them to canonical idiom_keys
    matching the Idiom collection so the admin UI can filter correctly.
    """
    result = {}
    for task_key, mod in _TASK_MODULES.items():
        skip = _TASK_RENAME_SKIP.get(task_key, set())
        raw_idioms = list(getattr(mod, "IDIOMS", []))
        canonical = []
        for idiom in raw_idioms:
            if idiom not in skip:
                canonical.append(_FILE_RENAME.get(idiom, idiom))
            else:
                canonical.append(idiom)
        result[task_key] = canonical
    return JSONResponse(content=result)


@router.get("/tasks/{task_key}/param-spec", tags=["admin"])
async def get_task_param_spec(task_key: str, dataset_id: str | None = None):
    """Return this task's hyperparameter spec for /specify (col E, see
    ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4-5, §9-10).

    Unauthored or param-free tasks return `param_spec: []`, which /specify
    renders as "No parameters required — ready to generate". `dataset_id` is
    accepted for forward-compatibility: once a task declares PARAM_SPEC entries
    with a `source` (e.g. "log.activities"), candidate values for that dataset
    are populated here (§14, step 6).
    """
    if task_key not in _TASK_MODULES:
        raise HTTPException(status_code=404, detail=f"Unknown task '{task_key}'.")

    # Copy entries so we never mutate the module's PARAM_SPEC, then populate
    # candidate `options` for entries with a dataset-backed `source`.
    spec = [dict(entry) for entry in task_registry.get_param_spec(task_key)]
    if dataset_id:
        for entry in spec:
            source = entry.get("source")
            if source:
                try:
                    candidates = _param_candidates(source, dataset_id)
                    if candidates:
                        entry["options"] = candidates
                except Exception:
                    _logger.exception(
                        "Failed to enumerate candidates for %s param '%s' (source=%s)",
                        task_key, entry.get("key"), source,
                    )
    return JSONResponse(content={
        "task_key": task_key,
        "param_spec": spec,
    })


@router.get("/tasks/{task_key}/answer-formats", tags=["admin"])
async def get_task_answer_formats(task_key: str):
    """Return this task's allowed answer formats for /answer-format-groundtruth
    (col D, see ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4-5, §11).

    Unauthored tasks fall back to a single generic `free-text` format.
    """
    if task_key not in _TASK_MODULES:
        raise HTTPException(status_code=404, detail=f"Unknown task '{task_key}'.")
    return JSONResponse(content={
        "task_key": task_key,
        "answer_formats": task_registry.get_answer_formats(task_key),
    })


@router.get("/tasks/{task_key}/rubric", tags=["admin"])
async def get_task_rubric(task_key: str):
    """Return this task's static, task-level grading rubric for read-only display
    on /answer-format-groundtruth and /overview (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §8, §11).

    The rubric is a single source of truth per task (the task's RUBRIC constant);
    it is never copied into or editable on a per-experiment instance. `rubric` is
    `null` if the task hasn't authored one yet (step 6).
    """
    if task_key not in _TASK_MODULES:
        raise HTTPException(status_code=404, detail=f"Unknown task '{task_key}'.")
    return JSONResponse(content={
        "task_key": task_key,
        "rubric": task_registry.get_rubric(task_key),
        "gt_tier": task_registry.get_gt_tier(task_key),
    })


# ---------------------------------------------------------------------------
# Question management
# ---------------------------------------------------------------------------

@router.post("/questions", tags=["admin"])
async def create_question(question: ds.Question):
    dbc.create_document("Question", question.model_dump(by_alias=True))
    return JSONResponse(content={"message": "Question created.", "question_id": question.id}, status_code=201)


@router.get("/questions", tags=["admin"])
async def get_questions(task_id: str | None = None):
    query = {"task_id": task_id} if task_id else {}
    questions = dbc.get_query_db("Question", query=query, projection={"_id": 0})
    return JSONResponse(content=questions)


# ---------------------------------------------------------------------------
# Experiment management
# ---------------------------------------------------------------------------

@router.post("/experiments", tags=["admin"])
async def create_experiment(experiment: ds.Experiment):
    dbc.create_document("Experiment", experiment.model_dump(by_alias=True))
    return JSONResponse(content={"message": f"Experiment '{experiment.name}' created.", "experiment_id": experiment.id}, status_code=201)


@router.get("/experiments", tags=["admin"])
async def get_experiments():
    experiments = dbc.get_query_db("Experiment", query={})
    for doc in experiments:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    return JSONResponse(content=experiments)


@router.get("/experiments/{experiment_id}", tags=["admin"])
async def get_experiment(experiment_id: str):
    """Return one experiment, including task_instances (with generation_status)
    for polling after POST /experiments/{experiment_id}/generate."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    if "_id" in exp and not isinstance(exp["_id"], str):
        exp["_id"] = str(exp["_id"])
    return JSONResponse(content=exp)


@router.get("/experiments/{experiment_id}/stats", tags=["admin"])
async def get_experiment_stats(experiment_id: str):
    db = dbc.connect_to_database()
    exp = db["Experiment"].find_one({"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

    task_configs = exp.get("task_configs", [])
    total_tasks = len(task_configs)
    assignments = list(db["UserAssignment"].find({"experiment_id": experiment_id}))
    participants = len(assignments)

    completed = sum(
        1 for a in assignments
        if a.get("current_trial_index", 0) >= len(a.get("trial_sequence", []))
        and len(a.get("trial_sequence", [])) > 0
    )

    return JSONResponse(content={
        "participants": participants,
        "completed": completed,
        "total_tasks": total_tasks,
    })


@router.delete("/experiments/{experiment_id}", tags=["admin"])
async def delete_experiment(experiment_id: str, force: bool = False):
    db = dbc.connect_to_database()
    exp = db["Experiment"].find_one({"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

    assignment_count = db["UserAssignment"].count_documents({"experiment_id": experiment_id})
    answer_count     = db["Answer"].count_documents({"experiment_id": experiment_id})
    log_count        = db["UILogging"].count_documents({"experiment_id": experiment_id})
    status           = exp.get("status", "draft")
    has_data         = assignment_count > 0 or answer_count > 0 or log_count > 0

    if (status != "draft" or has_data) and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Experiment has collected data or is not in draft.",
                "experiment": {"_id": experiment_id, "name": exp.get("name"), "status": status},
                "counts": {
                    "assignments": assignment_count,
                    "answers": answer_count,
                    "ui_logs": log_count,
                },
            },
        )

    db["UserAssignment"].delete_many({"experiment_id": experiment_id})
    db["Answer"].delete_many({"experiment_id": experiment_id})
    db["UILogging"].delete_many({"experiment_id": experiment_id})
    db["Experiment"].delete_one({"_id": experiment_id})

    # Remove the generated idiom SVGs for this experiment so they don't pile up as
    # orphaned files on disk (mirrors dataset deletion's shutil.rmtree cleanup).
    # The per-experiment output lives at data/{dataset_id}/output/{experiment_id}/;
    # collect dataset ids from both the experiment's dataset_ids and its
    # task_configs (a task may target a dataset not in dataset_ids).
    dataset_ids = set(exp.get("dataset_ids", []) or [])
    for tc in exp.get("task_configs", []):
        if tc.get("dataset_id"):
            dataset_ids.add(tc["dataset_id"])

    removed_output_dirs = []
    for dataset_id in dataset_ids:
        out_dir = DATA_DIRECTORY / dataset_id / "output" / experiment_id
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
            removed_output_dirs.append(f"{dataset_id}/output/{experiment_id}")

    return JSONResponse(content={
        "message": "Experiment deleted.",
        "deleted_counts": {
            "assignments": assignment_count,
            "answers": answer_count,
            "ui_logs": log_count,
        },
        "removed_output_dirs": removed_output_dirs,
    })


@router.patch("/experiments/{experiment_id}/status", tags=["admin"])
async def update_experiment_status(experiment_id: str, status: str):
    updated = dbc.update_document("Experiment", query={"_id": experiment_id}, update={"$set": {"status": status}})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": f"Experiment status updated to '{status}'."})


@router.patch("/experiments/{experiment_id}", tags=["admin"])
async def update_experiment(experiment_id: str, update_data: ds.ExperimentUpdate):
    # Keep task_instances (canonical) and task_configs (legacy mirror) in sync,
    # regardless of which one the caller sends.
    fields: dict = {}
    if update_data.task_instances is not None:
        instances = [ti.model_dump() for ti in update_data.task_instances]
        fields["task_instances"] = instances
        fields["task_configs"] = task_instances_to_configs(instances)
    elif update_data.task_configs is not None:
        configs = [tc.model_dump() for tc in update_data.task_configs]
        fields["task_configs"] = configs
        fields["task_instances"] = task_configs_to_instances(configs)
    if update_data.status is not None:
        fields["status"] = update_data.status
    if update_data.current_step is not None:
        fields["current_step"] = update_data.current_step
    if update_data.name is not None:
        fields["name"] = update_data.name
    if update_data.design_type is not None:
        fields["design_type"] = update_data.design_type
    if update_data.between_balance_mode is not None:
        fields["between_balance_mode"] = update_data.between_balance_mode
    if update_data.within_sequence_mode is not None:
        fields["within_sequence_mode"] = update_data.within_sequence_mode
    if update_data.dataset_ids is not None:
        fields["dataset_ids"] = update_data.dataset_ids
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    updated = dbc.update_document("Experiment", query={"_id": experiment_id}, update={"$set": fields})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Experiment updated.", "experiment_id": experiment_id})


def _task_key_for(task_id: str | None) -> str | None:
    """Resolve a task_instance's task_id to its canonical task_key (e.g. 'task01')."""
    if not task_id:
        return None
    task = dbc.get_document("Task", {"_id": task_id})
    return task.get("task_key") if task else None


def _resolve_answer_format(task_key: str, ti: dict) -> str | None:
    """The answer_format to compute GT for: the one chosen on
    /answer-format-groundtruth, else the task's sole/first declared format
    (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §7, §11)."""
    if ti.get("answer_format"):
        return ti["answer_format"]
    formats = task_registry.get_answer_formats(task_key)
    return formats[0]["key"] if formats else None


def _build_gt_block(task_key: str, answer_format: str, gt_raw: dict) -> dict:
    """Assemble a GroundTruthBlock from compute_ground_truth's raw output, filling
    tier/format/decisive defaults from the task's contract (§3, §8).

    The grading rubric is a static, task-level property (served by
    /tasks/{task_key}/rubric) and is intentionally NOT copied into the
    per-instance ground truth — `reference` only ever holds reference text that
    compute_ground_truth explicitly returns."""
    formats = task_registry.get_answer_formats(task_key)
    fmt = next((f for f in formats if f.get("key") == answer_format), None) or (formats[0] if formats else {})
    return {
        "tier": task_registry.get_gt_tier(task_key),
        "format": answer_format,
        "decisive": bool(gt_raw.get("decisive", fmt.get("decisive_default", False))),
        "value": gt_raw.get("value"),
        "options": gt_raw.get("options", []),
        "reference": gt_raw.get("reference"),
        "artefact_path": gt_raw.get("artefact_path"),
    }


def _load_dataset_log(dataset_id: str):
    """Load a dataset's event log as a pm4py EventLog (for validate_params hooks)."""
    input_dir = DATA_DIRECTORY / dataset_id / "input"
    log_path = None
    for fname in os.listdir(input_dir):
        if os.path.splitext(fname)[1].lower() in ALLOWED_LOG_EXTENSIONS:
            log_path = str(input_dir / fname)
            break
    if log_path is None:
        raise FileNotFoundError(f"No event log found in {input_dir}")
    from io_helpers import load_event_log
    return load_event_log(log_path)


def _validate_task_instances(exp: dict) -> list[str]:
    """Hard-validate every task_instance's parameters against its PARAM_SPEC and
    optional validate_params hook (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §10). Returns
    a list of human-readable error messages; empty means all valid."""
    errors: list[str] = []
    log_cache: dict[str, object] = {}
    for ti in exp.get("task_instances", []):
        task_key = _task_key_for(ti.get("task_id"))
        if not task_key or task_key not in _TASK_MODULES:
            continue
        dataset_id = ti.get("dataset_id") or ""
        params = ti.get("parameters") or {}
        spec = task_registry.get_param_spec(task_key)

        # Generic: required present + membership against dataset candidates
        # (catches gibberish and typo'd activity names).
        for entry in spec:
            key = entry.get("key")
            label = entry.get("label", key)
            val = params.get(key)
            is_empty = val is None or val == "" or (isinstance(val, list) and len(val) == 0)
            if entry.get("required") and is_empty:
                errors.append(f"{task_key}: '{label}' is required.")
                continue
            source = entry.get("source")
            if source and not is_empty:
                try:
                    candidates = _param_candidates(source, dataset_id)
                except Exception:
                    candidates = []
                # Candidates may be plain strings (e.g. log.activities) or
                # {value, label} dicts (e.g. log.violations); compare on value.
                candidate_values = [c if isinstance(c, str) else c.get("value") for c in candidates]
                if candidate_values:
                    # select-many params hold a list of values; scalar params hold one.
                    selected_values = val if isinstance(val, list) else [val]
                    for sv in selected_values:
                        if sv not in candidate_values:
                            errors.append(
                                f"{task_key}: '{sv}' is not a valid {label} — not found in the event log."
                            )

        # Task-specific semantic validation (e.g. the condition must split the log).
        validate = task_registry.get_validate_params(task_key)
        if validate is not None and dataset_id:
            if dataset_id not in log_cache:
                try:
                    log_cache[dataset_id] = _load_dataset_log(dataset_id)
                except (Exception, SystemExit) as e:
                    log_cache[dataset_id] = None
                    errors.append(f"{task_key}: could not load event log for validation ({e}).")
            log = log_cache.get(dataset_id)
            if log is not None:
                try:
                    for msg in (validate(log, params) or []):
                        errors.append(f"{task_key}: {msg}")
                except (Exception, SystemExit) as e:
                    errors.append(f"{task_key}: parameter validation error ({e}).")
    return errors


def _run_generation_job(experiment_id: str):
    """Background job: per dataset, render the experiment's task_instances with
    their chosen parameters and compute ground truth, then mark each instance
    'ready'/'failed' and store the computed GT (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §7)."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        return
    task_instances = exp.get("task_instances", [])

    # Group instances per dataset; remember each ti's resolved task_key + format.
    by_dataset: dict[str, list[dict]] = {}
    meta: dict[str, tuple] = {}  # task_id -> (task_key, answer_format)
    for ti in task_instances:
        ds = ti.get("dataset_id")
        task_key = _task_key_for(ti.get("task_id"))
        answer_format = _resolve_answer_format(task_key, ti) if task_key else None
        meta[ti.get("task_id")] = (task_key, answer_format)
        if not ds or not task_key:
            continue
        by_dataset.setdefault(ds, []).append({
            "task_key": task_key,
            "parameters": ti.get("parameters") or {},
            "answer_format": answer_format,
        })

    results: dict[tuple, dict] = {}  # (dataset_id, task_key) -> result entry
    for ds, insts in by_dataset.items():
        try:
            res = generate_for_task_instances(str(DATA_DIRECTORY / ds), experiment_id, insts)
            for tk, entry in res.items():
                results[(ds, tk)] = entry
        except Exception as e:
            _logger.exception("Generation failed for experiment %s, dataset %s", experiment_id, ds)
            for inst in insts:
                results[(ds, inst["task_key"])] = {"render_error": str(e), "gt_raw": None, "gt_error": None}

    for ti in task_instances:
        ds = ti.get("dataset_id")
        task_key, answer_format = meta.get(ti.get("task_id"), (None, None))
        if not ds:
            ti["generation_status"] = "failed"
            ti["generation_error"] = "No dataset assigned to this task."
            continue
        if not task_key:
            ti["generation_status"] = "failed"
            ti["generation_error"] = "Unknown task — no generator available."
            continue
        r = results.get((ds, task_key))
        if r is None:
            ti["generation_status"] = "failed"
            ti["generation_error"] = "Task was not generated."
            continue
        if r.get("render_error"):
            ti["generation_status"] = "failed"
            ti["generation_error"] = r["render_error"]
        else:
            ti["generation_status"] = "ready"
            ti["generation_error"] = None
        gt_raw_by_format = r.get("gt_raw_by_format") or {}
        if gt_raw_by_format:
            gt_block_by_format = {
                fmt_key: _build_gt_block(task_key, fmt_key, fmt_raw)
                for fmt_key, fmt_raw in gt_raw_by_format.items()
            }
            ti["ground_truth_by_format"] = gt_block_by_format
            selected = answer_format if (answer_format and answer_format in gt_block_by_format) \
                else next(iter(gt_block_by_format), None)
            if selected:
                ti["ground_truth"] = gt_block_by_format[selected]
        elif r.get("gt_error"):
            _logger.warning("compute_ground_truth failed for %s: %s", task_key, r["gt_error"])

    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "task_instances": task_instances,
        "task_configs": task_instances_to_configs(task_instances),
    }})


@router.post("/experiments/{experiment_id}/generate", tags=["admin"])
async def generate_experiment_visualizations(experiment_id: str, background_tasks: BackgroundTasks):
    """Validate parameters, then run generation + ground-truth computation for this
    experiment's task_instances in the background, writing SVGs to
    data/{dataset_id}/output/{experiment_id}/... (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §7).
    Invalid parameters are rejected with a 400 before anything runs. Poll
    GET /experiments/{experiment_id} for per-task generation_status."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    task_instances = exp.get("task_instances", [])
    if not task_instances:
        raise HTTPException(status_code=400, detail="Experiment has no task_instances to generate.")
    if generate_for_task_instances is None:
        raise HTTPException(status_code=503, detail="Visualization pipeline unavailable.")

    # Hard-error on invalid parameters before touching anything (§10).
    param_errors = _validate_task_instances(exp)
    if param_errors:
        raise HTTPException(status_code=400, detail={
            "message": "Cannot generate — fix the following parameters first.",
            "errors": param_errors,
        })

    for ti in task_instances:
        ti["generation_status"] = "running"
        ti["generation_error"] = None
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "task_instances": task_instances,
        "task_configs": task_instances_to_configs(task_instances),
    }})

    dataset_ids = sorted({ti["dataset_id"] for ti in task_instances if ti.get("dataset_id")})
    background_tasks.add_task(_run_generation_job, experiment_id)
    return JSONResponse(content={
        "message": "Generation started.",
        "experiment_id": experiment_id,
        "dataset_ids": dataset_ids,
    })


# ---------------------------------------------------------------------------
# Preview generation (2-step preview before publishing)
# ---------------------------------------------------------------------------

def _run_preview_job(experiment_id: str, mode: str):
    """Background job: generate preview SVGs without touching the experiment's
    permanent output or GT data.

    mode='sample' — uses the bundled synthetic sample dataset so the admin can
                    quickly see what each idiom looks like regardless of whether
                    the real data is slow to process.
    mode='real'   — uses the experiment's actual uploaded dataset so the admin
                    can verify the real output before clicking Generate.

    SVGs land at:
      sample → SAMPLE_DATA_DIR/output/__prev_{exp_id}_sample/{task_key}/
      real   → DATA_DIRECTORY/{dataset_id}/output/__prev_{exp_id}_real/{task_key}/
    """
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        return

    task_instances = exp.get("task_instances", [])
    preview_exp_id = f"__prev_{experiment_id}_{mode}"

    if mode == "sample":
        dataset_dir = str(SAMPLE_DATA_DIR)
        insts = []
        for ti in task_instances:
            task_key = _task_key_for(ti.get("task_id"))
            if task_key:
                insts.append({
                    "task_key": task_key,
                    "parameters": ti.get("parameters") or {},
                    "answer_format": None,
                })
        try:
            results = generate_for_task_instances(dataset_dir, preview_exp_id, insts)
            for tk, entry in results.items():
                _preview_status[experiment_id][mode][tk] = (
                    "failed" if entry.get("render_error") else "ready"
                )
        except Exception:
            _logger.exception("Preview (sample) failed for experiment %s", experiment_id)
            for tk in list(_preview_status.get(experiment_id, {}).get(mode, {})):
                _preview_status[experiment_id][mode][tk] = "failed"

    else:  # real
        by_dataset: dict[str, list[dict]] = {}
        for ti in task_instances:
            ds_id    = ti.get("dataset_id")
            task_key = _task_key_for(ti.get("task_id"))
            if ds_id and task_key:
                by_dataset.setdefault(ds_id, []).append({
                    "task_key": task_key,
                    "parameters": ti.get("parameters") or {},
                    "answer_format": None,
                })

        for ds_id, insts in by_dataset.items():
            try:
                results = generate_for_task_instances(
                    str(DATA_DIRECTORY / ds_id), preview_exp_id, insts
                )
                for tk, entry in results.items():
                    _preview_status[experiment_id][mode][tk] = (
                        "failed" if entry.get("render_error") else "ready"
                    )
            except Exception:
                _logger.exception(
                    "Preview (real) failed for experiment %s dataset %s", experiment_id, ds_id
                )
                for inst in insts:
                    _preview_status[experiment_id][mode][inst["task_key"]] = "failed"


@router.post("/experiments/{experiment_id}/preview", tags=["admin"])
async def start_preview(
    experiment_id: str,
    mode: str,
    background_tasks: BackgroundTasks,
):
    """Start a preview generation run without committing to the experiment's output.

    mode=sample : uses the bundled synthetic dataset — fast, shows idiom shapes.
    mode=real   : uses the experiment's actual uploaded dataset — full-fidelity check.

    Poll GET /admin/experiments/{id}/preview-status?mode=... for per-task progress,
    then fetch SVGs via GET /admin/experiments/{id}/preview/{mode}/{task_key}/{idiom_key}.
    """
    if mode not in ("sample", "real"):
        raise HTTPException(status_code=400, detail="mode must be 'sample' or 'real'.")

    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

    if mode == "sample":
        _sample_input = SAMPLE_DATA_DIR / "input"
        _has_dir   = _sample_input.is_dir()
        _has_log   = _has_dir and (any(_sample_input.glob("*.xes")) or any(_sample_input.glob("*.csv")))
        _has_model = _has_dir and any(_sample_input.glob("*.bpmn"))
        if not (_has_log and _has_model):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Sample dataset is incomplete (XES or BPMN missing). "
                    "Check backend startup logs for 'sample_data' errors."
                ),
            )

    if generate_for_task_instances is None:
        raise HTTPException(status_code=503, detail="Visualization pipeline unavailable.")

    # Mark every task as "running" before the background job starts.
    task_statuses: dict[str, str] = {}
    for ti in exp.get("task_instances", []):
        tk = _task_key_for(ti.get("task_id"))
        if tk:
            task_statuses[tk] = "running"

    _preview_status.setdefault(experiment_id, {})[mode] = task_statuses
    background_tasks.add_task(_run_preview_job, experiment_id, mode)

    return JSONResponse(content={
        "message": f"Preview ({mode}) started.",
        "experiment_id": experiment_id,
        "mode": mode,
    })


@router.get("/experiments/{experiment_id}/preview-status", tags=["admin"])
async def get_preview_status(experiment_id: str, mode: str):
    """Poll for preview generation progress.

    Returns { "mode": str, "status": { task_key: "running"|"ready"|"failed" } }.
    """
    status = _preview_status.get(experiment_id, {}).get(mode, {})
    return JSONResponse(content={"mode": mode, "status": status})


@router.get("/experiments/{experiment_id}/preview/{mode}/{task_key}/{idiom_key}", tags=["admin"])
async def get_preview_svg(
    experiment_id: str,
    mode: str,
    task_key: str,
    idiom_key: str,
):
    """Serve a preview SVG generated by start_preview().

    For sample mode the file lives inside SAMPLE_DATA_DIR/output/...;
    for real mode it lives inside DATA_DIRECTORY/{dataset_id}/output/...
    """
    if mode not in ("sample", "real"):
        raise HTTPException(status_code=400, detail="mode must be 'sample' or 'real'.")

    preview_exp_id = f"__prev_{experiment_id}_{mode}"

    if mode == "sample":
        svg_path = (
            SAMPLE_DATA_DIR / "output" / preview_exp_id / task_key / f"{idiom_key}.svg"
        )
    else:
        exp = dbc.get_document("Experiment", {"_id": experiment_id})
        if not exp:
            raise HTTPException(status_code=404)
        dataset_id = next(
            (ti.get("dataset_id") for ti in exp.get("task_instances", [])
             if _task_key_for(ti.get("task_id")) == task_key),
            None,
        )
        if not dataset_id:
            raise HTTPException(status_code=404, detail=f"No dataset found for task '{task_key}'.")
        svg_path = (
            DATA_DIRECTORY / dataset_id / "output" / preview_exp_id / task_key / f"{idiom_key}.svg"
        )

    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Preview SVG not found: {task_key}/{idiom_key} (mode={mode}). "
                   "Run the preview first.",
        )
    from fastapi.responses import FileResponse as _FileResponse
    return _FileResponse(svg_path, media_type="image/svg+xml")


@router.get("/experiments/{experiment_id}/vis/{task_key}/{idiom_key}", tags=["admin"])
async def get_generated_vis_svg(experiment_id: str, task_key: str, idiom_key: str):
    """Serve the actual generated SVG for the admin overview preview.

    Reads from DATA_DIRECTORY/{dataset_id}/output/{experiment_id}/{task_key}/{idiom_key}.svg.
    Returns 404 if generation has not been run yet.
    """
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    dataset_id = next(
        (ti.get("dataset_id") for ti in exp.get("task_instances", [])
         if _task_key_for(ti.get("task_id")) == task_key),
        None,
    )
    if not dataset_id:
        raise HTTPException(status_code=404, detail=f"No dataset found for task '{task_key}'.")
    svg_path = DATA_DIRECTORY / dataset_id / "output" / experiment_id / task_key / f"{idiom_key}.svg"
    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Visualization not generated yet: {task_key}/{idiom_key}.",
        )
    from fastapi.responses import FileResponse as _FileResponse
    return _FileResponse(svg_path, media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Idiom-level sample preview (used by the Select Idiom page)
# ---------------------------------------------------------------------------
# SVGs are stored at SAMPLE_DATA_DIR/output/__idiom_preview/{task_key}/{idiom_key}.svg.
# Pre-generated SVGs committed to the repo are baked into the Docker image and
# served immediately (status "ready") without any runtime generation.
# On-demand generation is still supported as a fallback for tasks without
# pre-generated SVGs.

_IDIOM_PREVIEW_EXP_ID = "__idiom_preview"
_idiom_preview_status: dict[str, str] = {}  # task_key → "generating"|"ready"|"failed"

_IDIOM_PREVIEW_BASE = SAMPLE_DATA_DIR / "output" / _IDIOM_PREVIEW_EXP_ID


def _idiom_svgs_exist(task_key: str) -> bool:
    """Return True if at least one pre-generated SVG exists on disk for this task."""
    task_dir = _IDIOM_PREVIEW_BASE / task_key
    return task_dir.is_dir() and any(task_dir.glob("*.svg"))


def _preload_idiom_preview_status():
    """Scan disk at startup and mark any task with existing SVGs as ready."""
    if not _IDIOM_PREVIEW_BASE.is_dir():
        return
    for task_dir in _IDIOM_PREVIEW_BASE.iterdir():
        if task_dir.is_dir() and any(task_dir.glob("*.svg")):
            _idiom_preview_status[task_dir.name] = "ready"
            _logger.info("[idiom-preview] Pre-loaded static SVGs for %s", task_dir.name)


_preload_idiom_preview_status()


def _run_idiom_preview_task(task_key: str):
    """Generate sample SVGs for one task with default parameters."""
    try:
        insts = [{"task_key": task_key, "parameters": {}, "answer_format": None}]
        results = generate_for_task_instances(
            str(SAMPLE_DATA_DIR), _IDIOM_PREVIEW_EXP_ID, insts
        )
        entry = results.get(task_key, {})
        _idiom_preview_status[task_key] = (
            "failed" if entry.get("render_error") else "ready"
        )
    except Exception:
        _logger.exception("Idiom preview generation failed for task %s", task_key)
        _idiom_preview_status[task_key] = "failed"


@router.post("/idiom-preview/{task_key}", tags=["admin"])
async def generate_idiom_preview(task_key: str, background_tasks: BackgroundTasks):
    """Serve pre-generated SVGs immediately if available; otherwise generate on demand.

    If static SVGs are already on disk (committed to the image), returns "ready"
    instantly without scheduling any background work.
    """
    current = _idiom_preview_status.get(task_key, "idle")
    if current in ("generating", "ready"):
        return JSONResponse({"status": current})

    # If SVGs were committed to the repo and baked into the image, use them directly.
    if _idiom_svgs_exist(task_key):
        _idiom_preview_status[task_key] = "ready"
        return JSONResponse({"status": "ready"})

    if generate_for_task_instances is None:
        raise HTTPException(status_code=503, detail="Visualization pipeline unavailable.")

    _sample_input = SAMPLE_DATA_DIR / "input"
    _has_dir   = _sample_input.is_dir()
    _has_log   = _has_dir and (any(_sample_input.glob("*.xes")) or any(_sample_input.glob("*.csv")))
    _has_model = _has_dir and any(_sample_input.glob("*.bpmn"))
    if not (_has_log and _has_model):
        raise HTTPException(
            status_code=503,
            detail="Sample dataset not ready. Check backend startup logs for errors.",
        )

    _idiom_preview_status[task_key] = "generating"
    background_tasks.add_task(_run_idiom_preview_task, task_key)
    return JSONResponse({"status": "generating"})


@router.post("/idiom-preview-all", tags=["admin"])
async def generate_all_idiom_previews(background_tasks: BackgroundTasks):
    """Trigger idiom preview generation for every task in the database.

    Tasks whose SVGs already exist on disk are skipped (already ready).
    Returns a per-task status snapshot so the caller can track progress.
    """
    tasks = dbc.get_query_db("Task", query={})
    task_keys = [t["task_key"] for t in tasks if t.get("task_key")]

    _sample_input = SAMPLE_DATA_DIR / "input"
    _has_dir   = _sample_input.is_dir()
    _has_log   = _has_dir and (any(_sample_input.glob("*.xes")) or any(_sample_input.glob("*.csv")))
    _has_model = _has_dir and any(_sample_input.glob("*.bpmn"))
    sample_ready = _has_log and _has_model

    snapshot: dict[str, str] = {}
    for tk in task_keys:
        current = _idiom_preview_status.get(tk, "idle")
        if current in ("generating", "ready"):
            snapshot[tk] = current
            continue
        if _idiom_svgs_exist(tk):
            _idiom_preview_status[tk] = "ready"
            snapshot[tk] = "ready"
            continue
        if not sample_ready or generate_for_task_instances is None:
            snapshot[tk] = "skipped"
            continue
        _idiom_preview_status[tk] = "generating"
        background_tasks.add_task(_run_idiom_preview_task, tk)
        snapshot[tk] = "generating"

    return JSONResponse({"tasks": snapshot})


@router.get("/idiom-preview/{task_key}/status", tags=["admin"])
async def get_idiom_preview_status(task_key: str):
    """Return the generation status for one task's idiom previews."""
    status = _idiom_preview_status.get(task_key, "idle")
    # Catch the case where SVGs exist on disk but memory cache was not populated
    # (e.g. server restarted mid-session).
    if status == "idle" and _idiom_svgs_exist(task_key):
        _idiom_preview_status[task_key] = "ready"
        status = "ready"
    return JSONResponse({"status": status})


@router.get("/idiom-preview/{task_key}/{idiom_key}", tags=["admin"])
async def get_idiom_preview_svg(task_key: str, idiom_key: str):
    """Serve a pre-generated sample-data SVG for one task/idiom pair."""
    svg_path = (
        SAMPLE_DATA_DIR / "output" / _IDIOM_PREVIEW_EXP_ID / task_key / f"{idiom_key}.svg"
    )
    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Preview not found for {task_key}/{idiom_key}. Trigger generation first.",
        )
    from fastapi.responses import FileResponse as _FileResponse
    return _FileResponse(str(svg_path), media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Knowledge Question management
# ---------------------------------------------------------------------------

@router.get("/knowledge-questions", tags=["admin"])
async def get_knowledge_questions():
    questions = dbc.get_query_db("KnowledgeQuestion", query={})
    for doc in questions:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    return JSONResponse(content=questions)


@router.post("/knowledge-questions", tags=["admin"])
async def create_knowledge_question(q: ds.KnowledgeQuestionCreate):
    qid = str(uuid.uuid4())
    options = list(q.options)
    if q.include_idk and (not options or options[-1] != "I don't know"):
        options.append("I don't know")
    doc = {
        "_id": qid,
        "section_title": q.section_title,
        "text": q.text,
        "options": options,
        "include_idk": q.include_idk,
        "correct_option_index": q.correct_option_index,
        "is_system": False,
        "created_at": utils.get_current_datetime(),
    }
    dbc.create_document("KnowledgeQuestion", doc)
    return JSONResponse(
        content={"message": "Knowledge question created.", "question_id": qid},
        status_code=201,
    )


@router.delete("/knowledge-questions/{question_id}", tags=["admin"])
async def delete_knowledge_question(question_id: str):
    db = dbc.connect_to_database()
    q = db["KnowledgeQuestion"].find_one({"_id": question_id})
    if not q:
        raise HTTPException(status_code=404, detail="Knowledge question not found.")
    if q.get("is_system"):
        raise HTTPException(status_code=403, detail="System questions cannot be deleted.")
    referencing = list(db["Experiment"].find({"knowledge_question_ids": question_id}))
    if referencing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Question is referenced by one or more experiments.",
                "referencing_experiments": [
                    {"_id": e["_id"], "name": e.get("name")} for e in referencing
                ],
            },
        )
    db["KnowledgeQuestion"].delete_one({"_id": question_id})
    return JSONResponse(content={"message": "Knowledge question deleted."})


@router.patch("/experiments/{experiment_id}/knowledge-questions", tags=["admin"])
async def update_experiment_knowledge_questions(experiment_id: str, body: ds.KnowledgeQuestionIds):
    set_fields = {"knowledge_question_ids": body.knowledge_question_ids}
    if body.current_step is not None:
        set_fields["current_step"] = body.current_step
    updated = dbc.update_document(
        "Experiment",
        query={"_id": experiment_id},
        update={"$set": set_fields},
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Knowledge questions updated."})


@router.patch("/experiments/{experiment_id}/prequestionnaire-sections", tags=["admin"])
async def update_experiment_prequestionnaire_sections(experiment_id: str, body: ds.PrequestionnaireSections):
    set_fields = {"prequestionnaire_sections": body.sections}
    if body.current_step is not None:
        set_fields["current_step"] = body.current_step
    updated = dbc.update_document(
        "Experiment",
        query={"_id": experiment_id},
        update={"$set": set_fields},
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Pre-questionnaire sections updated."})


# ---------------------------------------------------------------------------
# GroundTruth management
# ---------------------------------------------------------------------------

@router.post("/groundtruth", tags=["admin"])
async def create_ground_truth(ground_truth: ds.GroundTruth):
    dbc.create_document("GroundTruth", ground_truth.model_dump(by_alias=True))
    return JSONResponse(content={"message": "GroundTruth entry created.", "ground_truth_id": ground_truth.id}, status_code=201)