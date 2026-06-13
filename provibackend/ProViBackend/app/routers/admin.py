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
        _FILE_RENAME,
        _TASK_RENAME_SKIP,
    )
except ImportError:
    # The visualization pipeline pulls in heavy, optional deps (pm4py, etc.).
    # Degrade gracefully so the rest of the admin API still works, but log the
    # full traceback so the cause is never hidden.
    _logger.exception("Could not import visualization pipeline; run_pipeline disabled")
    run_visualization_pipeline = None
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

ALLOWED_LOG_EXTENSIONS   = {".xes", ".csv"}
ALLOWED_MODEL_EXTENSIONS = {".bpmn"}
EVENTLOG_BASENAME = "EventLog"
GUIDELINE_FILENAME = "Guideline.bpmn"


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
    """Download experiment data as an Excel file with two sheets:
    Sheet 1 - Participant background (prequestionnaire + knowledge survey)
    Sheet 2 - Task answers
    """
    import pandas as pd

    # ── Sheet 2: task answers ──────────────────────────────────────────────
    answers = dbc.get_query_db("Answer", query={"experiment_id": experiment_id})
    df_answers = pd.DataFrame(answers) if answers else pd.DataFrame()

    # ── Sheet 1: participant background ───────────────────────────────────
    user_ids = list({a["user_id"] for a in answers}) if answers else []
    rows = []
    for uid in user_ids:
        user = dbc.get_document("User", {"user_id": uid})
        if not user:
            continue
        pre = dbc.get_document("PreliminaryAnswers", {"_id": user.get("preliminary_id", "")}) or {}
        know = dbc.get_document("KnowledgeAnswers",  {"_id": user.get("knowledge_id", "")})  or {}
        level_map = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}
        rows.append({
            "user_id":        uid,
            **{k: v for k, v in pre.items()  if k != "_id"},
            "knowledge_notes": know.get("notes"),
            "knowledge_score": know.get("score"),
            "knowledge_level": level_map.get(know.get("level"), know.get("level")),
        })
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

        if "response_time_ms" in df_answers.columns:
            df_answers["response_time_s"] = (df_answers["response_time_ms"] / 1000).round(2)
            df_answers = df_answers.drop(columns=["response_time_ms"])
        if "insert_datetime" in df_answers.columns:
            df_answers = df_answers.rename(columns={"insert_datetime": "completion_time"})

    # ── Write to Excel ─────────────────────────────────────────────────────
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_background.to_excel(writer, sheet_name="Participant Background", index=False)
        df_answers.to_excel(writer, sheet_name="Task Answers", index=False)
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
    return JSONResponse(content={
        "task_key": task_key,
        "param_spec": task_registry.get_param_spec(task_key),
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
    """Return this task's static grading rubric for /answer-format-groundtruth's
    "Reset to default rubric" action (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §8, §11).

    `rubric` is `null` if the task hasn't authored one yet (step 6) — the page
    falls back to an empty editable reference.
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
    return JSONResponse(content={
        "message": "Experiment deleted.",
        "deleted_counts": {
            "assignments": assignment_count,
            "answers": answer_count,
            "ui_logs": log_count,
        },
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
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    updated = dbc.update_document("Experiment", query={"_id": experiment_id}, update={"$set": fields})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Experiment updated.", "experiment_id": experiment_id})


def _run_generation_job(experiment_id: str, dataset_ids: list[str]):
    """Background job: run the visualization pipeline for each dataset used by
    this experiment, writing SVGs to the per-experiment output directory, then
    mark every task_instance as 'ready' or 'failed' (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §7)."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        return
    task_instances = exp.get("task_instances", [])
    errors: dict[str, str] = {}
    for dataset_id in dataset_ids:
        dataset_dir = DATA_DIRECTORY / dataset_id
        try:
            run_visualization_pipeline(str(dataset_dir), experiment_id=experiment_id)
        except Exception as e:
            _logger.exception("Generation failed for experiment %s, dataset %s", experiment_id, dataset_id)
            errors[dataset_id] = str(e)
    for ti in task_instances:
        ds_id = ti.get("dataset_id")
        if ds_id in errors:
            ti["generation_status"] = "failed"
            ti["generation_error"] = errors[ds_id]
        else:
            ti["generation_status"] = "ready"
            ti["generation_error"] = None
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "task_instances": task_instances,
        "task_configs": task_instances_to_configs(task_instances),
    }})


@router.post("/experiments/{experiment_id}/generate", tags=["admin"])
async def generate_experiment_visualizations(experiment_id: str, background_tasks: BackgroundTasks):
    """Run the visualization pipeline for this experiment's datasets in the
    background, writing SVGs to data/{dataset_id}/output/{experiment_id}/...
    (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §7). Poll GET /experiments/{experiment_id}
    for per-task generation_status."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    task_instances = exp.get("task_instances", [])
    if not task_instances:
        raise HTTPException(status_code=400, detail="Experiment has no task_instances to generate.")
    if run_visualization_pipeline is None:
        raise HTTPException(status_code=503, detail="Visualization pipeline unavailable.")

    for ti in task_instances:
        ti["generation_status"] = "running"
        ti["generation_error"] = None
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "task_instances": task_instances,
        "task_configs": task_instances_to_configs(task_instances),
    }})

    dataset_ids = sorted({ti["dataset_id"] for ti in task_instances if ti.get("dataset_id")})
    background_tasks.add_task(_run_generation_job, experiment_id, dataset_ids)
    return JSONResponse(content={
        "message": "Generation started.",
        "experiment_id": experiment_id,
        "dataset_ids": dataset_ids,
    })


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
    updated = dbc.update_document(
        "Experiment",
        query={"_id": experiment_id},
        update={"$set": {"knowledge_question_ids": body.knowledge_question_ids}},
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Knowledge questions updated."})


# ---------------------------------------------------------------------------
# GroundTruth management
# ---------------------------------------------------------------------------

@router.post("/groundtruth", tags=["admin"])
async def create_ground_truth(ground_truth: ds.GroundTruth):
    dbc.create_document("GroundTruth", ground_truth.model_dump(by_alias=True))
    return JSONResponse(content={"message": "GroundTruth entry created.", "ground_truth_id": ground_truth.id}, status_code=201)