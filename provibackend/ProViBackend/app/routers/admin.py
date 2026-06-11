import uuid
import io
import csv
import re
from fastapi import APIRouter, BackgroundTasks, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
try:
    from ProViBackend.scripts.create_all_visualizations import (
        run_pipeline as run_visualization_pipeline,
        _FILE_RENAME,
        _TASK_RENAME_SKIP,
    )
except ImportError:
    run_visualization_pipeline = None
    _FILE_RENAME = {}
    _TASK_RENAME_SKIP = {}

try:
    from ProViBackend.scripts.tasks import (
        task01, task02, task03, task04, task05,
        task06, task07, task08, task09, task10, task11, task12, task20,
        task23, task24, task25, task26, task27,
        task28, task29, task30, task31,
        task35, task36, task37,
    )
    _TASK_MODULES = {
        "task01": task01, "task02": task02, "task03": task03, "task04": task04, "task05": task05,
        "task06": task06, "task07": task07, "task08": task08, "task09": task09,
        "task10": task10, "task11": task11, "task12": task12, "task20": task20,
        "task23": task23, "task24": task24, "task25": task25, "task26": task26, "task27": task27,
        "task28": task28, "task29": task29, "task30": task30, "task31": task31,
        "task35": task35, "task36": task36, "task37": task37,
    }
except ImportError:
    _TASK_MODULES = {}
from ProViBackend.utils import config, utils
from ProViBackend.app.datamodels import data_schemas as ds
import pathlib as pl

import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.redis_handler as redis_handler

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
async def upload_dataset_pair(log: UploadFile, guideline: UploadFile, background_tasks: BackgroundTasks):
    """Upload an event log + BPMN guideline; triggers the visualization pipeline asynchronously."""
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
            dataset_title=pl.Path(log.filename).stem,   # keep original log name as title
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

        if run_visualization_pipeline is not None:
            background_tasks.add_task(run_visualization_pipeline, str(pair_dir))

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


@router.patch("/experiments/{experiment_id}/status", tags=["admin"])
async def update_experiment_status(experiment_id: str, status: str):
    updated = dbc.update_document("Experiment", query={"_id": experiment_id}, update={"$set": {"status": status}})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": f"Experiment status updated to '{status}'."})


def _sync_participant_experiment(experiment_id: str, participant_status: str):
    """Build and upsert a ParticipantExperiment document for participant-facing queries."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        return
    def _get_by_id(collection, id_str):
        doc = dbc.get_document(collection, {"_id": id_str})
        if doc:
            return doc
        try:
            doc = dbc.get_document(collection, {"_id": ObjectId(id_str)})
        except Exception:
            pass
        return doc

    task_assignments = []
    for tc in exp.get("task_configs", []):
        task_doc = _get_by_id("Task", tc["task_id"])
        idiom_doc = _get_by_id("Idiom", tc["idiom_id"])
        task_key = task_doc["task_key"] if task_doc else None
        idiom_key = idiom_doc["idiom_key"] if idiom_doc else None
        pair_id = tc["dataset_id"]
        svg_path = (
            f"data/{pair_id}/output/{task_key}/{idiom_key}.svg"
            if task_key and idiom_key else None
        )
        task_assignments.append({
            "dataset_id": tc["dataset_id"],
            "task_id": tc["task_id"],
            "idiom_id": tc["idiom_id"],
            "svg_path": svg_path,
        })
    db = dbc.connect_to_database()
    db["ParticipantExperiment"].replace_one(
        {"_id": experiment_id},
        {
            "_id": experiment_id,
            "experiment_id": experiment_id,
            "status": participant_status,
            "task_assignments": task_assignments,
        },
        upsert=True,
    )


@router.patch("/experiments/{experiment_id}", tags=["admin"])
async def update_experiment(experiment_id: str, update_data: ds.ExperimentUpdate):
    fields: dict = {"task_configs": [tc.model_dump() for tc in update_data.task_configs]}
    if update_data.status is not None:
        fields["status"] = update_data.status
    updated = dbc.update_document("Experiment", query={"_id": experiment_id}, update={"$set": fields})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Experiment updated.", "experiment_id": experiment_id})


# ---------------------------------------------------------------------------
# GroundTruth management
# ---------------------------------------------------------------------------

@router.post("/groundtruth", tags=["admin"])
async def create_ground_truth(ground_truth: ds.GroundTruth):
    dbc.create_document("GroundTruth", ground_truth.model_dump(by_alias=True))
    return JSONResponse(content={"message": "GroundTruth entry created.", "ground_truth_id": ground_truth.id}, status_code=201)