import json
import uuid
from itertools import combinations
import io
import csv
import re
import shutil
import sys
import os
import logging
import threading
import time
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
        get_log_violation_activities,
        get_log_data_attributes,
        get_log_attribute_values,
        get_log_resource_values,
        get_log_event_conditions,
        get_log_log_attributes,
        get_log_time_bins,
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
    get_log_violation_activities = None
    get_log_data_attributes = None
    get_log_attribute_values = None
    get_log_resource_values = None
    get_log_event_conditions = None
    get_log_log_attributes = None
    get_log_time_bins = None
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
from ProViBackend.utils import config, idiom_files, utils
from ProViBackend.app.datamodels import data_schemas as ds
from ProViBackend.app.task_wording import effective_wording
import ProViBackend.app.answer_formats as afmt
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

ALLOWED_IDIOM_IMAGE_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg"}
CUSTOM_IDIOM_DIRECTORY = config.CUSTOM_IDIOM_DIRECTORY

ALLOWED_PROCESS_MODEL_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg"}
PROCESS_MODEL_DIRECTORY = config.PROCESS_MODEL_DIRECTORY
MAX_PROCESS_MODEL_BYTES = 10 * 1024 * 1024

# Cache of distinct activity names per dataset, so /specify's param-spec
# candidate enumeration doesn't reload the event log on every page render
# (see docs/ADMIN_EXPERIMENT_SETUP.md). Keyed by dataset_id.
_LOG_ACTIVITIES_CACHE: dict[str, list[str]] = {}
# Cache of dataset-meaningful time-bin granularities (task07), same rationale.
_LOG_TIME_GRANULARITIES_CACHE: dict[str, list[str]] = {}
# Cache of distinct (activity, move_type) violation pairs (task11); alignment
# computation is expensive, so results are cached in-process per dataset_id.
_LOG_VIOLATIONS_CACHE: dict[str, list[dict]] = {}
_LOG_VIOLATION_ACTS_CACHE: dict[str, list[dict]] = {}
# Cache of top-10 worst-fitness traces (task34); alignment computation is shared
# with _LOG_VIOLATIONS_CACHE but cached separately to avoid coupled invalidation.
_LOG_WORST_TRACES_CACHE: dict[str, list[dict]] = {}
# Cache of all traces as {value, label} picker options (task04's trace_ids).
_LOG_TRACE_IDS_CACHE: dict[str, list[dict]] = {}
# Cache of bucketable candidate attributes (task20's attribute_set picker).
_LOG_CANDIDATE_ATTRS_CACHE: dict[str, list[dict]] = {}
# Cache of violated activities for task34's activity-picker dropdown.
_LOG_VIOLATED_ACTS_TASK34_CACHE: dict[str, list[dict]] = {}
# Caches for the data / resource perspective of task09 and task28.
_LOG_DATA_ATTRS_CACHE: dict[str, list[dict]] = {}
_LOG_ATTR_VALUES_CACHE: dict[str, list[dict]] = {}
_LOG_RESOURCE_VALUES_CACHE: dict[str, list[dict]] = {}
_LOG_EVENT_CONDITIONS_CACHE: dict[str, list[dict]] = {}
_LOG_LOG_ATTRIBUTES_CACHE: dict[str, list[dict]] = {}


def _dataset_data_attributes(dataset_id: str) -> list[dict]:
    """Attributes a data rule can be written about (task09 / task28, cached)."""
    if dataset_id in _LOG_DATA_ATTRS_CACHE:
        return _LOG_DATA_ATTRS_CACHE[dataset_id]
    if get_log_data_attributes is None:
        return []
    attrs = get_log_data_attributes(str(DATA_DIRECTORY / dataset_id))
    _LOG_DATA_ATTRS_CACHE[dataset_id] = attrs
    return attrs


def _dataset_attribute_values(dataset_id: str) -> list[dict]:
    """Flat "attribute = value" candidates (task09 / task28, cached)."""
    if dataset_id in _LOG_ATTR_VALUES_CACHE:
        return _LOG_ATTR_VALUES_CACHE[dataset_id]
    if get_log_attribute_values is None:
        return []
    values = get_log_attribute_values(str(DATA_DIRECTORY / dataset_id))
    _LOG_ATTR_VALUES_CACHE[dataset_id] = values
    return values


def _dataset_log_attributes(dataset_id: str) -> list[dict]:
    """Log-level attributes (the log class of the attribute picker, cached)."""
    if dataset_id in _LOG_LOG_ATTRIBUTES_CACHE:
        return _LOG_LOG_ATTRIBUTES_CACHE[dataset_id]
    if get_log_log_attributes is None:
        return []
    rows = get_log_log_attributes(str(DATA_DIRECTORY / dataset_id))
    _LOG_LOG_ATTRIBUTES_CACHE[dataset_id] = rows
    return rows


def _dataset_event_conditions(dataset_id: str) -> list[dict]:
    """"At activity X, attribute Y = Z" conditions (the event class, cached)."""
    if dataset_id in _LOG_EVENT_CONDITIONS_CACHE:
        return _LOG_EVENT_CONDITIONS_CACHE[dataset_id]
    if get_log_event_conditions is None:
        return []
    rows = get_log_event_conditions(str(DATA_DIRECTORY / dataset_id))
    _LOG_EVENT_CONDITIONS_CACHE[dataset_id] = rows
    return rows


def _dataset_resource_values(dataset_id: str) -> list[dict]:
    """Distinct org:resource values (task09 / task28, cached)."""
    if dataset_id in _LOG_RESOURCE_VALUES_CACHE:
        return _LOG_RESOURCE_VALUES_CACHE[dataset_id]
    if get_log_resource_values is None:
        return []
    values = get_log_resource_values(str(DATA_DIRECTORY / dataset_id))
    _LOG_RESOURCE_VALUES_CACHE[dataset_id] = values
    return values


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


def _dataset_violation_activities(dataset_id: str) -> list[dict]:
    """Activities carrying violations, for the Violation-profile class (cached)."""
    if dataset_id in _LOG_VIOLATION_ACTS_CACHE:
        return _LOG_VIOLATION_ACTS_CACHE[dataset_id]
    if get_log_violation_activities is None:
        return []
    acts = get_log_violation_activities(str(DATA_DIRECTORY / dataset_id))
    _LOG_VIOLATION_ACTS_CACHE[dataset_id] = acts
    return acts


def _dataset_violated_activities_task34(dataset_id: str) -> list[dict]:
    """Violated activities for task34's activity-picker dropdown (cached)."""
    if dataset_id in _LOG_VIOLATED_ACTS_TASK34_CACHE:
        return _LOG_VIOLATED_ACTS_TASK34_CACHE[dataset_id]
    if get_log_violated_activities_task34 is None:
        return []
    acts = get_log_violated_activities_task34(str(DATA_DIRECTORY / dataset_id))
    _LOG_VIOLATED_ACTS_TASK34_CACHE[dataset_id] = acts
    return acts


# Time bins are cached per (dataset_id, granularity) — unlike the other
# enumerators the result depends on a second argument.
_LOG_TIME_BINS_CACHE: dict[tuple[str, str], list[dict]] = {}


def _dataset_time_bins(dataset_id: str, granularity: str) -> list[dict]:
    """Ordered time-bin labels for this dataset at `granularity` (cached)."""
    key = (dataset_id, granularity or "")
    if key in _LOG_TIME_BINS_CACHE:
        return _LOG_TIME_BINS_CACHE[key]
    if get_log_time_bins is None:
        return []
    bins = get_log_time_bins(str(DATA_DIRECTORY / dataset_id), granularity)
    _LOG_TIME_BINS_CACHE[key] = bins
    return bins


# Option sources offered on /answer-format. Task-independent by construction:
# every one enumerates entities from the dataset itself, so any task may import
# from any of them. `granularity` marks the one source that takes a second
# argument (the page renders a granularity picker next to it).
# Matrix axis size: the grid is read cell-by-cell, so a large axis is unusable
# (n candidates -> n*(n-1)/2 cells). 10 mirrors task08's old _MATRIX_TOP_N.
_MATRIX_AXIS_DEFAULT = 10
_MATRIX_AXIS_MAX = 16

OPTION_SOURCES: list[dict] = [
    {"source": "log.activities",           "label": "Activities"},
    {"source": "log.violations",           "label": "Violation types (activity · move type)"},
    {"source": "log.violation_activities", "label": "Activities carrying violations"},
    {"source": "log.candidate_attributes", "label": "Case-attribute buckets"},
    {"source": "log.time_bins",            "label": "Time bins", "granularity": True},
    {"source": "log.trace_ids",            "label": "Traces"},
    {"source": "log.worst_traces",         "label": "Worst-fitness traces"},
    {"source": "log.data_attributes",      "label": "Data attributes"},
    {"source": "log.attribute_values",     "label": "Attribute values (attribute = value)"},
    {"source": "log.resource_values",      "label": "Resources"},
    {"source": "log.event_conditions",     "label": "Event conditions (activity · attribute = value)"},
    {"source": "log.log_attributes",       "label": "Log-level attributes"},
]


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
    if source == "log.violation_activities":
        return _dataset_violation_activities(dataset_id)
    if source == "log.violated_activities_task34":
        return _dataset_violated_activities_task34(dataset_id)
    if source == "log.data_attributes":
        return _dataset_data_attributes(dataset_id)
    if source == "log.attribute_values":
        return _dataset_attribute_values(dataset_id)
    if source == "log.resource_values":
        return _dataset_resource_values(dataset_id)
    if source == "log.event_conditions":
        return _dataset_event_conditions(dataset_id)
    if source == "log.log_attributes":
        return _dataset_log_attributes(dataset_id)
    return []


def _option_candidates(source: str, dataset_id: str, granularity: str | None) -> list[dict]:
    """Candidate option rows for one source, normalised to [{label, value}].

    PARAM_SPEC enumerators return either plain strings (log.activities) or
    {value, label} dicts; the option editor always wants both fields.
    """
    if source == "log.time_bins":
        raw = _dataset_time_bins(dataset_id, granularity or "")
    else:
        raw = _param_candidates(source, dataset_id)
    rows = []
    for c in raw:
        if isinstance(c, str):
            rows.append({"label": c, "value": c})
        else:
            label = c.get("label") or c.get("value") or ""
            rows.append({"label": label, "value": c.get("value") or label})
    return rows


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

    Generation no longer runs at upload time (see docs/ADMIN_EXPERIMENT_SETUP.md) — it is triggered per-experiment via POST /admin/experiments/{id}/generate,
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

        # A CSV whose case / activity / timestamp columns cannot be identified
        # would only fail later, at generation, so turn it away here with the
        # reason. Only the header is read.
        if log_ext == ".csv":
            import pandas as pd
            from io_helpers import EventLogFormatError, detect_csv_columns
            try:
                header = pd.read_csv(log_path, nrows=0).columns
            except (ValueError, pd.errors.ParserError) as e:
                raise HTTPException(status_code=400,
                                    detail=f"The event log CSV could not be parsed: {e}")
            try:
                detect_csv_columns(header)
            except EventLogFormatError as e:
                raise HTTPException(status_code=400, detail=str(e))

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
        # Rejected before any DatasetPair was stored: leave nothing on disk.
        shutil.rmtree(pair_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(pair_dir, ignore_errors=True)
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
        # Resolve task_id → task_key + task_name. The name is the question as
        # *this* experiment asked it, which is what its participants answered.
        exp_doc = dbc.get_document("Experiment", {"_id": experiment_id})
        instances_by_task_id = {ti.get("task_id"): ti
                                for ti in (exp_doc or {}).get("task_instances", [])}
        unique_task_ids = df_answers["task_id"].dropna().unique().tolist()
        task_lookup = {}
        for tid in unique_task_ids:
            doc = dbc.get_task(tid)
            if doc:
                wording = effective_wording(exp_doc, tid, doc, instances_by_task_id.get(tid))
                task_lookup[tid] = {"task_key": doc.get("task_key", ""),
                                    "task_name": wording["label"]}
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

        # Add the configured answer format from the experiment's task_instances
        format_by_task = {tid: (ti.get("answer_format") or "")
                          for tid, ti in instances_by_task_id.items()}
        df_answers["answer_format"] = df_answers["task_id"].map(
            lambda x: format_by_task.get(x, "")
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
    # Keys are whatever the endpage's QUESTIONS submit (the NASA-TLX items,
    # 7-point scales). Known keys get a readable column in this order; any
    # other key found in the data is exported under its own name rather than
    # dropped, so a changed questionnaire can never silently empty the sheet.
    RATING_LABELS = {
        "mentalDemand":   "Mental Demand (1-7)",
        "physicalDemand": "Physical Demand (1-7)",
        "temporalDemand": "Temporal Demand (1-7)",
        # NASA-TLX runs this one the other way round: 1 = very good.
        "performance":    "Performance (1-7, 1 = very good)",
        "effort":         "Effort (1-7)",
        "frustration":    "Frustration (1-7)",
    }
    feedback_by_user = {}
    for uid in (list({a["user_id"] for a in answers}) if answers else []):
        user = dbc.get_document("User", {"user_id": uid})
        if not user or not user.get("feedback_id"):
            continue
        feedback_by_user[uid] = dbc.get_document("FeedbackAnswers", {"_id": user["feedback_id"]}) or {}
    seen_keys = {k for fb in feedback_by_user.values() for k in (fb.get("ratings") or {})}
    rating_keys = [k for k in RATING_LABELS if k in seen_keys] + sorted(seen_keys - RATING_LABELS.keys())

    survey_rows = []
    for uid, fb in feedback_by_user.items():
        ratings = fb.get("ratings") or {}
        row = {"user_id": uid}
        for key in rating_keys:
            row[RATING_LABELS.get(key, key)] = ratings.get(key)
        row["Additional Feedback"] = fb.get("feedback")
        survey_rows.append(row)
    df_survey = pd.DataFrame(survey_rows) if survey_rows else pd.DataFrame()

    # ── Sheet 4: blind review ─────────────────────────────────────────────
    # Minimal columns only, so answers can be scored without revealing the
    # participant or idiom. _id keys each row back to the
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
    # Despite the name, this counts idioms, not datasets: assigned_between maps
    # task_id -> idiom_id (between-subjects only). Left from the ProVi-era
    # dataset rotation; no page calls this endpoint any more.
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


@router.post("/idioms/upload", tags=["admin"])
async def upload_custom_idiom(file: UploadFile, label: str = Form(...), task_keys: str = Form(...),
                              experiment_id: str = Form(...)):
    """Admin-uploaded static image/SVG idiom, scoped to one experiment and
    specific task(s) in it.

    Unlike code-generated idioms (rendered per task+dataset by a task script's
    Python function, see /task-idioms), a custom idiom is a single fixed asset
    stored once and served as-is via GET /idioms/{idiom_key}/asset. `task_keys`
    is a comma-separated list of task keys (e.g. "task01,task05") — the idiom
    is only selectable on /admin/experiments/idiom for those tasks of
    `experiment_id` (see /task-idioms); at least one is required. Other
    experiments never offer it, so one study's uploads do not turn up in the next.
    """
    if not dbc.get_document("Experiment", {"_id": experiment_id}):
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    ext = _validate_extension(file.filename, ALLOWED_IDIOM_IMAGE_EXTENSIONS, "Idiom image")
    keys = [k.strip() for k in task_keys.split(",") if k.strip()]
    if not keys:
        raise HTTPException(status_code=400, detail="At least one task must be selected.")
    unknown = [k for k in keys if not _is_known_task_key(k)]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown task(s): {', '.join(unknown)}")

    idiom_key = f"custom-{uuid.uuid4().hex[:12]}"

    try:
        CUSTOM_IDIOM_DIRECTORY.mkdir(parents=True, exist_ok=True)
        asset_path = CUSTOM_IDIOM_DIRECTORY / f"{idiom_key}{ext}"
        asset_path.write_bytes(await file.read())

        idiom = ds.Idiom(
            _id=str(uuid.uuid4()),
            idiom_key=idiom_key,
            label=label,
            granularity="custom",
            renderer_type="custom-upload",
            active=True,
            is_custom=True,
            asset_ext=ext,
            task_keys=keys,
            experiment_id=experiment_id,
        )
        dbc.create_document("Idiom", idiom.model_dump(by_alias=True))
        return JSONResponse(
            content={"message": f"Idiom '{label}' uploaded.", "idiom_id": idiom.id, "idiom_key": idiom_key},
            status_code=201,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload idiom: {str(e)}")
    finally:
        await file.close()


@router.patch("/idioms/{idiom_id}", tags=["admin"])
async def update_idiom(idiom_id: str, update: ds.IdiomUpdate):
    """Rename or re-scope a custom (admin-uploaded) idiom.

    Only custom idioms can be edited here — built-in idioms are code-seeded
    (see seed_data.py CANONICAL_IDIOMS) and are not owned by any one admin
    upload.
    """
    doc = dbc.get_document("Idiom", {"_id": idiom_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Idiom '{idiom_id}' not found.")
    if not doc.get("is_custom"):
        raise HTTPException(status_code=400, detail="Only custom (admin-uploaded) idioms can be edited.")

    fields = {k: v for k, v in update.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "task_keys" in fields:
        if not fields["task_keys"]:
            raise HTTPException(status_code=400, detail="At least one task must be selected.")
        unknown = [k for k in fields["task_keys"] if not _is_known_task_key(k)]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown task(s): {', '.join(unknown)}")

    dbc.update_document("Idiom", query={"_id": idiom_id}, update={"$set": fields})
    return JSONResponse(content={"message": "Idiom updated.", "idiom_id": idiom_id})


@router.get("/idioms/{idiom_key}/asset", tags=["admin"])
async def get_custom_idiom_asset(idiom_key: str):
    """Serve a custom (admin-uploaded) idiom's fixed image/SVG asset."""
    docs = dbc.get_query_db("Idiom", query={"idiom_key": idiom_key, "is_custom": True})
    if not docs:
        raise HTTPException(status_code=404, detail=f"No custom idiom '{idiom_key}'.")
    ext = docs[0].get("asset_ext") or ".svg"
    asset_path = CUSTOM_IDIOM_DIRECTORY / f"{idiom_key}{ext}"
    if not asset_path.exists():
        raise HTTPException(status_code=404, detail="Idiom asset file missing.")
    from fastapi.responses import FileResponse as _FileResponse
    return _FileResponse(str(asset_path), media_type=utils.image_media_type(ext))


# ---------------------------------------------------------------------------
# Task management
# ---------------------------------------------------------------------------

@router.post("/tasks", tags=["admin"])
async def create_task(task: ds.Task):
    dbc.create_document("Task", task.model_dump(by_alias=True))
    return JSONResponse(content={"message": f"Task '{task.label}' created.", "task_id": task.id}, status_code=201)


def _task_sort_key(task: dict):
    """Built-in tasks by number (task01, task02, ...); keys without a number last."""
    task_key = task.get("task_key", "")
    match = re.search(r"\d+", task_key)
    return (0, int(match.group()), task_key) if match else (1, 0, task_key)


def _is_known_task_key(task_key: str) -> bool:
    """A built-in task (has a generator module) or an experiment-scoped custom task."""
    return task_key in _TASK_MODULES or dbc.get_custom_task_by_key(task_key) is not None


def _is_custom_task_key(task_key: str | None) -> bool:
    """Custom tasks have no generator module: their idioms are static uploaded assets."""
    return bool(task_key) and task_key not in _TASK_MODULES


def _remove_custom_task_idioms(task_keys: list[str]):
    """Unscope custom idioms from deleted custom tasks.

    An idiom still scoped to another task keeps existing; one left with no
    task at all is deleted together with its asset file.
    """
    if not task_keys:
        return
    for idiom in dbc.get_query_db("Idiom", query={"is_custom": True, "task_keys": {"$in": task_keys}}):
        remaining = [k for k in (idiom.get("task_keys") or []) if k not in task_keys]
        if remaining:
            dbc.update_document("Idiom", {"_id": idiom["_id"]}, {"$set": {"task_keys": remaining}})
            continue
        dbc.delete_document("Idiom", {"_id": idiom["_id"]})
        asset_path = CUSTOM_IDIOM_DIRECTORY / f"{idiom['idiom_key']}{idiom.get('asset_ext') or '.svg'}"
        asset_path.unlink(missing_ok=True)


@router.get("/tasks", tags=["admin"])
async def get_tasks(experiment_id: str | None = None):
    """The shared Task question bank, plus `experiment_id`'s own custom tasks if given.

    With an `experiment_id`, each task is returned as *that experiment* asks it:
    a task its admin reworded (PATCH /tasks/{id}?experiment_id=…) carries the
    reworded text, every other task the bank's. Participants read the same way
    (participant.py), so the admin pages and the study never disagree.
    """
    tasks = dbc.get_query_db("Task", query={})
    for doc in tasks:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    tasks.sort(key=_task_sort_key)
    if experiment_id:
        exp = dbc.get_document("Experiment", {"_id": experiment_id}) or {}
        for doc in tasks:
            doc.update(effective_wording(exp, doc.get("_id", ""), doc))
        tasks.extend(exp.get("custom_tasks") or [])
    return JSONResponse(content=tasks)


@router.patch("/tasks/{task_id}", tags=["admin"])
async def update_task(task_id: str, update_data: ds.TaskUpdate,
                      experiment_id: str | None = None):
    """Reword one task **for one experiment**, or edit its shared rubric.

    The question bank (the Task collection) holds the wording every experiment
    starts from and is owned by seed_data.py, so a reworded question is stored
    on the experiment (`task_overrides`, see app/task_wording.py): it reaches
    this experiment's participants and no one else's. Editing the bank itself
    used to be what this endpoint did, which made one experiment's wording
    ("…for Ship Order", "…customer segments and region") everybody's default and
    stopped the startup seed from ever correcting it.

    `rubric` is the exception and still goes to the bank: it is reference text
    for whoever codes the answers by hand, not something a participant sees, and
    /answer-format reads it per task rather than per experiment.
    """
    fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    wording = {k: v for k, v in fields.items()
               if k in ("label", "description", "answer_type")}
    shared = {k: v for k, v in fields.items() if k not in wording}
    if dbc.get_document("Task", {"_id": task_id}) is None:
        # Experiment-scoped custom task: edit it in place on its experiment.
        updated = dbc.update_document(
            "Experiment",
            query={"custom_tasks._id": task_id},
            update={"$set": {f"custom_tasks.$.{k}": v for k, v in fields.items()}},
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        return JSONResponse(content={"message": "Task updated.", "task_id": task_id})
    if shared:
        # Non-canonical, so the startup seed leaves it alone (main._seed_collection
        # only $sets the fields seed_data.py names).
        if not dbc.update_document("Task", query={"_id": task_id}, update={"$set": shared}):
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    if not wording:
        return JSONResponse(content={"message": "Task updated.", "task_id": task_id})
    if not experiment_id:
        raise HTTPException(
            status_code=400,
            detail="experiment_id is required: a task's wording is edited for one "
                   "experiment, not for the shared question bank.",
        )
    # Keyed by task_id on the experiment itself, not on its task_instances: on
    # /task the tasks are still being chosen, so the instance does not exist yet
    # (and should not be conjured up by an edit), and an override has to outlive
    # deselecting the task and picking it again.
    updated = dbc.update_document(
        "Experiment",
        query={"_id": experiment_id},
        update={"$set": {f"task_overrides.{task_id}.{k}": v for k, v in wording.items()}},
    )
    if not updated:
        raise HTTPException(
            status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Task updated for this experiment.",
                                 "task_id": task_id, "experiment_id": experiment_id})


@router.post("/experiments/{experiment_id}/custom-tasks", tags=["admin"])
async def create_custom_task(experiment_id: str, body: ds.CustomTaskCreate):
    """Add a task that exists only in this experiment.

    It is stored on the Experiment (custom_tasks), not in the shared Task
    question bank, so other experiments never list it. A custom task has no
    generator code — its visualizations are custom idioms uploaded on /idiom.
    """
    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="The task question is required.")
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

    task = {
        "_id": str(uuid.uuid4()),
        # Globally unique, since custom idioms are scoped to tasks by task_key.
        "task_key": f"custom-{uuid.uuid4().hex[:6]}",
        "label": label,
        "description": body.description.strip(),
        "answer_type": "text",
        "is_custom": True,
    }
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$push": {"custom_tasks": task}})
    return JSONResponse(content=task, status_code=201)


@router.delete("/experiments/{experiment_id}/custom-tasks/{task_id}", tags=["admin"])
async def delete_custom_task(experiment_id: str, task_id: str):
    """Remove a custom task from its (draft) experiment, together with its
    task_instances and any custom idioms that were only scoped to it."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    task = next((t for t in exp.get("custom_tasks") or [] if t.get("_id") == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Custom task '{task_id}' not found.")
    if exp.get("status", "draft") != "draft":
        raise HTTPException(status_code=409, detail="Custom tasks can only be deleted from a draft experiment.")

    instances = [ti for ti in exp.get("task_instances", []) if ti.get("task_id") != task_id]
    dbc.update_document("Experiment", {"_id": experiment_id}, {
        "$pull": {"custom_tasks": {"_id": task_id}},
        "$set": {
            "task_instances": instances,
            "task_configs": task_instances_to_configs(instances),
        },
    })
    _remove_custom_task_idioms([task["task_key"]])
    return JSONResponse(content={"message": "Custom task deleted.", "task_id": task_id})


@router.get("/task-idioms", tags=["admin"])
async def get_task_idioms(experiment_id: str | None = None):
    """Returns {task_key: [canonical_idiom_key, ...]} from each task script's IDIOMS list.

    Raw idiom names from task scripts use file-stem conventions (e.g. scatter_plot,
    flow_chart_elaborate_bpmn); this endpoint translates them to canonical idiom_keys
    matching the Idiom collection so the admin UI can filter correctly.

    Custom (admin-uploaded, see POST /idioms/upload) idioms are fixed static
    assets rather than code-generated per task; each one is scoped to the
    specific task(s) the admin picked at upload time (its `task_keys` field),
    so it's only appended to those tasks' lists here — not every task. They are
    offered only to `experiment_id`: the ones uploaded in it, plus any older
    upload (no `experiment_id` recorded) it has already selected, so that no
    experiment loses an idiom it uses. Without `experiment_id`, none are listed.

    With `experiment_id`, that experiment's custom tasks are included too; they
    have no code-generated idioms, only the custom idioms scoped to them.
    """
    custom_idioms = []
    exp = {}
    if experiment_id:
        exp = dbc.get_document("Experiment", {"_id": experiment_id}) or {}
        selected = {tc.get("idiom_id") for tc in exp.get("task_configs") or []}
        for ti in exp.get("task_instances") or []:
            selected.update(ti.get("idiom_ids") or [])
        # Custom task keys exist in one experiment only, so an older upload
        # bound to one of them belongs to this experiment too.
        own_task_keys = {t["task_key"] for t in exp.get("custom_tasks") or []}

        def offered(doc: dict) -> bool:
            if doc.get("experiment_id"):
                return doc["experiment_id"] == experiment_id
            return doc.get("_id") in selected or bool(own_task_keys & set(doc.get("task_keys") or []))

        custom_idioms = [doc for doc in dbc.get_query_db("Idiom", query={"is_custom": True}) if offered(doc)]

    result = {}
    if experiment_id:
        for task in exp.get("custom_tasks") or []:
            result[task["task_key"]] = [
                doc["idiom_key"] for doc in custom_idioms
                if task["task_key"] in (doc.get("task_keys") or [])
            ]
    for task_key, mod in _TASK_MODULES.items():
        skip = _TASK_RENAME_SKIP.get(task_key, set())
        raw_idioms = list(getattr(mod, "IDIOMS", []))
        canonical = []
        for idiom in raw_idioms:
            if idiom not in skip:
                canonical.append(_FILE_RENAME.get(idiom, idiom))
            else:
                canonical.append(idiom)
        task_custom_keys = [
            doc["idiom_key"] for doc in custom_idioms
            if task_key in (doc.get("task_keys") or [])
        ]
        result[task_key] = canonical + task_custom_keys
    return JSONResponse(content=result)


@router.get("/tasks/{task_key}/param-spec", tags=["admin"])
async def get_task_param_spec(task_key: str, dataset_id: str | None = None):
    """Return this task's hyperparameter spec for /specify (col E, see
    docs/ADMIN_EXPERIMENT_SETUP.md).

    Unauthored or param-free tasks return `param_spec: []`, which /specify
    renders as "No parameters required — ready to generate". `dataset_id` is
    accepted for forward-compatibility: once a task declares PARAM_SPEC entries
    with a `source` (e.g. "log.activities"), candidate values for that dataset
    are populated here.

    A task offers exactly the parameters its own PARAM_SPEC declares. There used
    to be a global catalog here — every parameter any task declared, switchable
    on per task from /admin/experiments/parameters — but a parameter a task's
    generation code does not read was collected and then ignored, and nothing
    stopped two parameters competing for the same decision from being enabled
    together. Each entry carries a `slot`, and a task declares at most one entry
    per slot.
    """
    if task_key not in _TASK_MODULES:
        if dbc.get_custom_task_by_key(task_key):
            # Custom tasks have no generation code, so no parameter consumes anything.
            return JSONResponse(content={"task_key": task_key, "param_spec": []})
        raise HTTPException(status_code=404, detail=f"Unknown task '{task_key}'.")

    # Copied so a request never mutates the module's PARAM_SPEC, then given
    # candidate `options` where the entry names a dataset-backed `source`.
    spec = [dict(entry) for entry in task_registry.get_param_spec(task_key)]

    if dataset_id:
        for entry in spec:
            source = entry.get("source")
            if not source:
                continue
            try:
                candidates = _param_candidates(source, dataset_id)
            except Exception as e:
                # An empty picker used to be indistinguishable from a broken
                # one: the admin saw "no candidates" either way while the reason
                # sat in the container log. Send the reason along so /specify can
                # say which it is.
                _logger.exception(
                    "Failed to enumerate candidates for %s param '%s' (source=%s)",
                    task_key, entry.get("key"), source,
                )
                entry["options_error"] = f"{type(e).__name__}: {e}"
                continue
            entry["options"] = candidates or []
            if not candidates:
                entry["options_error"] = (
                    f"'{source}' returned nothing for this dataset."
                )
    return JSONResponse(content={
        "task_key": task_key,
        "param_spec": spec,
    })


@router.get("/answer-formats", tags=["admin"])
async def get_answer_formats():
    """The global answer-format registry for /answer-format.

    Formats are not task-scoped: every task may use every format. `needs_options`
    tells the page whether to render the option editor, `numeric` whether to
    render the number-kind selector.
    """
    return JSONResponse(content={
        "answer_formats": afmt.ANSWER_FORMATS,
        "number_kinds": afmt.NUMBER_KINDS,
        "default_number_kind": afmt.DEFAULT_NUMBER_KIND,
    })


@router.get("/datasets/{dataset_id}/option-sources", tags=["admin"])
async def get_option_sources(dataset_id: str):
    """Event-log sources an admin can import answer options from on /answer-format.

    Task-independent: each source enumerates entities from the dataset, so any
    task may import from any of them.
    """
    return JSONResponse(content={
        "dataset_id": dataset_id,
        "option_sources": OPTION_SOURCES,
        "matrix_axis_default": _MATRIX_AXIS_DEFAULT,
    })


@router.get("/datasets/{dataset_id}/option-candidates", tags=["admin"])
async def get_option_candidates(
    dataset_id: str,
    source: str,
    granularity: str | None = None,
    pairs: bool = False,
    axis_limit: int = _MATRIX_AXIS_DEFAULT,
):
    """Option rows for one source, ready to drop into the option editor.

    `pairs=true` (matrix) turns the candidates into the upper triangle of a
    symmetric grid: the first `axis_limit` candidates become the shared axis and
    each cell is one {label: "a × b", value: "a__b"} option, matching the token
    shape AnswerWidgets.parsePairs expects. `axis_total` reports how many
    candidates existed so the page can say what it truncated.
    """
    known = {s["source"] for s in OPTION_SOURCES}
    if source not in known:
        raise HTTPException(status_code=400,
                            detail=f"Unknown option source '{source}'. Known: {sorted(known)}.")
    try:
        rows = _option_candidates(source, dataset_id, granularity)
    except Exception as e:
        _logger.exception("Failed to enumerate option candidates (%s / %s)", dataset_id, source)
        raise HTTPException(status_code=500, detail=f"Could not read the event log: {e}")

    axis_total = len(rows)
    if not pairs:
        return JSONResponse(content={"options": rows, "axis_total": axis_total})

    axis = [r for r in rows if "__" not in r["label"]][:max(2, min(axis_limit, _MATRIX_AXIS_MAX))]
    options = [
        {"label": f"{a['label']} × {b['label']}", "value": f"{a['label']}__{b['label']}"}
        for a, b in combinations(axis, 2)
    ]
    return JSONResponse(content={
        "options": options,
        "axis": [a["label"] for a in axis],
        "axis_total": axis_total,
    })



@router.get("/tasks/{task_key}/rubric", tags=["admin"])
async def get_task_rubric(task_key: str):
    """Return this task's grading rubric for display/editing on /answer-format.

    Reference text for manually coding free-text answers — it feeds no automatic
    scoring. Whatever an admin wrote (PATCH /tasks/{task_id} with a `rubric`
    field, stored on the Task document) is it; `rubric` is `null` until someone
    does, which is every task today. A module may still ship a `RUBRIC` constant
    as a starting point — none currently does, because a rubric nobody has
    reviewed is worse than an empty box that says a rubric is missing.
    """
    if task_key not in _TASK_MODULES:
        custom = dbc.get_custom_task_by_key(task_key)
        if not custom:
            raise HTTPException(status_code=404, detail=f"Unknown task '{task_key}'.")
        return JSONResponse(content={"task_key": task_key, "rubric": custom.get("rubric")})
    task_docs = dbc.get_query_db("Task", query={"task_key": task_key})
    override = task_docs[0].get("rubric") if task_docs else None
    return JSONResponse(content={
        "task_key": task_key,
        "rubric": override if override is not None else task_registry.get_rubric(task_key),
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

    # task_configs has one row per task × idiom, so count distinct tasks.
    total_tasks = len({tc.get("task_id") for tc in exp.get("task_configs", []) if tc.get("task_id")})
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
    # Its custom tasks go with the experiment document; drop the custom idioms
    # that were only scoped to them, and those uploaded in it, which no other
    # experiment is offered (see /task-idioms).
    _remove_custom_task_idioms([t["task_key"] for t in exp.get("custom_tasks") or []])
    for idiom in dbc.get_query_db("Idiom", query={"is_custom": True, "experiment_id": experiment_id}):
        dbc.delete_document("Idiom", {"_id": idiom["_id"]})
        (CUSTOM_IDIOM_DIRECTORY / f"{idiom['idiom_key']}{idiom.get('asset_ext') or '.svg'}").unlink(missing_ok=True)
    _remove_process_model_file(exp)
    idiom_files.remove_all_overrides(experiment_id)

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


def _freeze_task_snapshots(instances: list[dict], existing_by_task_id: dict) -> list[dict]:
    """Stamp each task instance with its `task_key`, and carry any legacy frozen
    wording through untouched.

    Wording is not this function's business any more: an experiment asks each
    task in the question bank's words unless an admin reworded it there, which
    is stored on the experiment (`task_overrides`, app/task_wording.py). This
    used to freeze the bank's label into every instance the first time the task
    entered the experiment, and three readers then disagreed — /task showed the
    bank, participants the frozen copy, and an admin's edit went to the bank, so
    it reached neither their own experiment nor, correctly, everyone else's.

    Instances written back then still carry that copy; it is preserved here
    rather than dropped, so an experiment that has already run keeps the text
    its participants saw until reseed_task_questions.py --apply clears it.

    `task_key` is identity rather than wording, so it is always stamped: an
    experiment whose Task document is later deleted still knows which generator
    drew its figures.
    """
    task_cache: dict = {}
    for inst in instances:
        task_id = inst.get("task_id", "")
        if not task_id:
            continue
        existing = existing_by_task_id.get(task_id) or {}
        # Legacy frozen wording survives every save; nothing writes it any more.
        for field in ("label", "description", "answer_type"):
            if not inst.get(field) and existing.get(field):
                inst[field] = existing[field]
        if inst.get("task_key"):
            continue
        if existing.get("task_key"):
            inst["task_key"] = existing["task_key"]
            continue
        if task_id not in task_cache:
            task_cache[task_id] = dbc.get_task(task_id) or {}
        inst["task_key"] = task_cache[task_id].get("task_key", "")
    return instances


def _keep_imported_parameters(instances: list[dict], existing_by_task_id: dict) -> list[dict]:
    """A task whose images were imported keeps the parameters it was imported
    with, whatever the caller sends: those images were drawn with them, and the
    participant-facing parameter hints are built from them. Only reverting the
    import (routers/idiom_bundle.py) releases the task, so the marker is never
    taken from the caller either.
    """
    for inst in instances:
        existing = existing_by_task_id.get(inst.get("task_id")) or {}
        if existing.get("images_imported_from"):
            inst["images_imported_from"] = existing["images_imported_from"]
            inst["parameters"] = existing.get("parameters") or {}
        else:
            inst["images_imported_from"] = None
    return instances


@router.patch("/experiments/{experiment_id}", tags=["admin"])
async def update_experiment(experiment_id: str, update_data: ds.ExperimentUpdate):
    # Keep task_instances (canonical) and task_configs (legacy mirror) in sync,
    # regardless of which one the caller sends.
    fields: dict = {}
    if update_data.task_instances is not None or update_data.task_configs is not None:
        existing_exp = dbc.get_document("Experiment", {"_id": experiment_id}) or {}
        existing_by_task_id = {
            ti.get("task_id"): ti for ti in existing_exp.get("task_instances", []) if ti.get("task_id")
        }
        if update_data.task_instances is not None:
            instances = [ti.model_dump() for ti in update_data.task_instances]
        else:
            configs = [tc.model_dump() for tc in update_data.task_configs]
            instances = task_configs_to_instances(configs)
        instances = _freeze_task_snapshots(instances, existing_by_task_id)
        instances = _keep_imported_parameters(instances, existing_by_task_id)
        fields["task_instances"] = instances
        fields["task_configs"] = task_instances_to_configs(instances)
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
    task = dbc.get_task(task_id)
    return task.get("task_key") if task else None


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


def _entry_applies(entry: dict, params: dict) -> bool:
    """Does this PARAM_SPEC entry apply, given the other parameters?

    The mirror of entryApplies() on the specify page: an entry may declare
    `visible_if: {other_key: value}` (or a list of values) and only applies when
    every one of those holds. Without this the generate endpoint rejected a
    required parameter the admin was never shown — task04's log-level split
    condition while the task is set to trace level, say.
    """
    condition = entry.get("visible_if")
    if not condition:
        return True
    for key, wanted in condition.items():
        have = (params or {}).get(key)
        if isinstance(wanted, (list, tuple, set)):
            if have not in wanted:
                return False
        elif have != wanted:
            return False
    return True


def _fully_uploaded_task_ids(exp: dict) -> set[str]:
    """Tasks whose every selected idiom shows an uploaded or imported image.

    Generating them would draw images nobody sees (uploads win, see
    utils/idiom_files), and for imported tasks it would put them back to
    "running" for nothing, so generation leaves them alone. A task with one
    idiom still lacking an upload is generated as usual — with the imported
    parameters, when it has them, so its new images match the imported ones.
    """
    overrides = {(o["task_key"], o["idiom_key"]) for o in idiom_files.list_overrides(exp["_id"])}
    if not overrides:
        return set()
    out = set()
    for ti in exp.get("task_instances", []):
        task_key = _task_key_for(ti.get("task_id"))
        idiom_keys = [
            (dbc.get_document("Idiom", {"_id": iid}) or {}).get("idiom_key")
            for iid in ti.get("idiom_ids") or []
        ]
        if task_key and idiom_keys and all((task_key, k) in overrides for k in idiom_keys):
            out.add(ti.get("task_id"))
    return out


def _validate_task_instances(exp: dict, skip_task_ids: set[str] = frozenset()) -> list[str]:
    """Hard-validate every task_instance's parameters against its PARAM_SPEC and
    optional validate_params hook (see docs/ADMIN_EXPERIMENT_SETUP.md). Returns
    a list of human-readable error messages; empty means all valid."""
    errors: list[str] = []
    log_cache: dict[str, object] = {}
    for ti in exp.get("task_instances", []):
        if ti.get("task_id") in skip_task_ids:
            continue
        task_key = _task_key_for(ti.get("task_id"))
        if not task_key or task_key not in _TASK_MODULES:
            continue
        dataset_id = ti.get("dataset_id") or ""
        params = ti.get("parameters") or {}
        spec = task_registry.get_param_spec(task_key)

        # Generic: required present + membership against dataset candidates
        # (catches gibberish and typo'd activity names).
        for entry in spec:
            if not _entry_applies(entry, params):
                continue
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
                except Exception as e:
                    log_cache[dataset_id] = None
                    errors.append(f"{task_key}: could not load event log for validation ({e}).")
            log = log_cache.get(dataset_id)
            if log is not None:
                try:
                    for msg in (validate(log, params) or []):
                        errors.append(f"{task_key}: {msg}")
                except Exception as e:
                    errors.append(f"{task_key}: parameter validation error ({e}).")
    return errors


def _run_generation_job(experiment_id: str):
    """Background job: per dataset, render the experiment's task_instances with
    their chosen parameters, then mark each instance 'ready'/'failed'.

    Generation only draws — the answer shape (format, options, number kind) is
    authored by the admin on /answer-format and never computed here."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        return
    task_instances = exp.get("task_instances", [])
    skip = _fully_uploaded_task_ids(exp)

    # Group instances per dataset; remember each ti's resolved task_key.
    by_dataset: dict[str, list[dict]] = {}
    meta: dict[str, str | None] = {}  # task_id -> task_key
    for ti in task_instances:
        if ti.get("task_id") in skip:
            continue
        ds = ti.get("dataset_id")
        task_key = _task_key_for(ti.get("task_id"))
        meta[ti.get("task_id")] = task_key
        if not ds or not task_key or _is_custom_task_key(task_key):
            continue
        by_dataset.setdefault(ds, []).append({
            "task_key": task_key,
            "parameters": ti.get("parameters") or {},
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
                results[(ds, inst["task_key"])] = {"render_error": str(e)}

    for ti in task_instances:
        if ti.get("task_id") in skip:
            continue
        ds = ti.get("dataset_id")
        task_key = meta.get(ti.get("task_id"))
        if _is_custom_task_key(task_key):
            # Only static uploaded idioms — nothing to render.
            ti["generation_status"] = "ready"
            ti["generation_error"] = None
            continue
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

    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "task_instances": task_instances,
        "task_configs": task_instances_to_configs(task_instances),
    }})


@router.post("/experiments/{experiment_id}/generate", tags=["admin"])
async def generate_experiment_visualizations(experiment_id: str, background_tasks: BackgroundTasks):
    """Validate parameters, then run idiom generation for this
    experiment's task_instances in the background, writing SVGs to
    data/{dataset_id}/output/{experiment_id}/... (see docs/ADMIN_EXPERIMENT_SETUP.md).
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

    skip = _fully_uploaded_task_ids(exp)
    if all(ti.get("task_id") in skip for ti in task_instances):
        return JSONResponse(content={
            "message": "Nothing to generate — every task shows uploaded or imported images.",
            "experiment_id": experiment_id,
            "dataset_ids": [],
        })

    # Hard-error on invalid parameters before touching anything (§10).
    param_errors = _validate_task_instances(exp, skip)
    if param_errors:
        raise HTTPException(status_code=400, detail={
            "message": "Cannot generate — fix the following parameters first.",
            "errors": param_errors,
        })

    for ti in task_instances:
        if ti.get("task_id") in skip:
            continue
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
    permanent output.

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
            if task_key and not _is_custom_task_key(task_key):
                insts.append({
                    "task_key": task_key,
                    "parameters": ti.get("parameters") or {},
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
            if ds_id and task_key and not _is_custom_task_key(task_key):
                by_dataset.setdefault(ds_id, []).append({
                    "task_key": task_key,
                    "parameters": ti.get("parameters") or {},
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
            # Custom tasks only have static idioms, so their preview is ready at once.
            task_statuses[tk] = "ready" if _is_custom_task_key(tk) else "running"

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

    custom_docs = dbc.get_query_db("Idiom", query={"idiom_key": idiom_key, "is_custom": True})
    if custom_docs:
        return await get_custom_idiom_asset(idiom_key)

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
    """Serve the image participants will see for this task/idiom, for the admin
    overview preview: an uploaded/imported replacement if there is one, else the
    custom idiom's asset, else the generated SVG (see utils/idiom_files).
    Returns 404 if nothing has been generated or uploaded yet."""
    override = idiom_files.find_override(experiment_id, task_key, idiom_key)
    if override:
        from fastapi.responses import FileResponse as _FileResponse
        return _FileResponse(str(override), media_type=utils.image_media_type(override.suffix))

    custom_docs = dbc.get_query_db("Idiom", query={"idiom_key": idiom_key, "is_custom": True})
    if custom_docs:
        return await get_custom_idiom_asset(idiom_key)

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
# Drawn by the same generator as an experiment's images (generate_for_task_instances),
# from the bundled sample dataset with default parameters, into
# SAMPLE_DATA_DIR/output/__idiom_preview/{task_key}/{idiom_key}.svg.
#
# That directory is a cache, never committed: it lives in the container, not on
# the data volume, so it starts empty whenever the image is rebuilt — that is,
# whenever the generator code changes. (Previews used to be committed to the
# repo, and went on showing July's drawings long after the tasks had changed.)
# A task's previews are generated once per container: on its first request, or
# earlier by prewarm_idiom_previews() at startup. Running the backend outside
# Docker, delete the directory after changing a task to see its new previews.

_IDIOM_PREVIEW_EXP_ID = "__idiom_preview"
_idiom_preview_status: dict[str, str] = {}  # task_key → "generating"|"ready"|"failed"
# Guards the check-and-set in _claim_idiom_preview: the startup prewarm and
# admin requests may reach the same task at the same time.
_idiom_preview_lock = threading.Lock()

_IDIOM_PREVIEW_BASE = SAMPLE_DATA_DIR / "output" / _IDIOM_PREVIEW_EXP_ID


def _idiom_svgs_exist(task_key: str) -> bool:
    """True if this container already drew previews for this task."""
    task_dir = _IDIOM_PREVIEW_BASE / task_key
    return task_dir.is_dir() and any(task_dir.glob("*.svg"))


def _preload_idiom_preview_status():
    """Mark tasks already drawn in this container ready, after a restart that
    kept the container (and so the same generator code)."""
    if not _IDIOM_PREVIEW_BASE.is_dir():
        return
    for task_dir in _IDIOM_PREVIEW_BASE.iterdir():
        if task_dir.is_dir() and any(task_dir.glob("*.svg")):
            _idiom_preview_status[task_dir.name] = "ready"


_preload_idiom_preview_status()


def _sample_dataset_ready() -> bool:
    sample_input = SAMPLE_DATA_DIR / "input"
    if not sample_input.is_dir():
        return False
    has_log = any(sample_input.glob("*.xes")) or any(sample_input.glob("*.csv"))
    return has_log and any(sample_input.glob("*.bpmn"))


def _claim_idiom_preview(task_key: str) -> str:
    """The task's preview status; "claimed" when the caller should draw it now.

    Marks it "generating" under the lock, so that of a startup prewarm and an
    admin request reaching the same task, only one draws it.
    """
    with _idiom_preview_lock:
        current = _idiom_preview_status.get(task_key, "idle")
        if current in ("generating", "ready"):
            return current
        if _idiom_svgs_exist(task_key):
            _idiom_preview_status[task_key] = "ready"
            return "ready"
        _idiom_preview_status[task_key] = "generating"
        return "claimed"


def _run_idiom_preview_task(task_key: str):
    """Generate sample SVGs for one task with default parameters."""
    started = time.monotonic()
    try:
        insts = [{"task_key": task_key, "parameters": {}}]
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
    _logger.info("[idiom-preview] %s %s in %.1fs",
                 task_key, _idiom_preview_status[task_key], time.monotonic() - started)


def prewarm_idiom_previews():
    """Draw every task's previews once, one task after another, so the Select
    Idiom page need not wait. Run in a daemon thread at startup (app/main.py).

    Sequential and paced on purpose: generation is CPU-bound and shares the
    interpreter with request handling, so drawing all tasks at once would slow
    the participant-facing endpoints right after a deploy.
    """
    if generate_for_task_instances is None or not _sample_dataset_ready():
        _logger.warning("[idiom-preview] prewarm skipped: pipeline or sample dataset unavailable")
        return
    started = time.monotonic()
    for task_key in sorted(_TASK_MODULES):
        if _claim_idiom_preview(task_key) == "claimed":
            _run_idiom_preview_task(task_key)
            time.sleep(1)
    _logger.info("[idiom-preview] prewarm finished in %.0fs", time.monotonic() - started)


@router.post("/idiom-preview/{task_key}", tags=["admin"])
async def generate_idiom_preview(task_key: str, background_tasks: BackgroundTasks):
    """Serve this task's previews if this container already drew them;
    otherwise draw them in the background and report "generating"."""
    # Custom tasks have no generator; their idioms are served as static assets.
    if _is_custom_task_key(task_key):
        return JSONResponse({"status": "ready"})

    if generate_for_task_instances is None:
        raise HTTPException(status_code=503, detail="Visualization pipeline unavailable.")
    if not _sample_dataset_ready():
        raise HTTPException(
            status_code=503,
            detail="Sample dataset not ready. Check backend startup logs for errors.",
        )

    status = _claim_idiom_preview(task_key)
    if status != "claimed":
        return JSONResponse({"status": status})
    background_tasks.add_task(_run_idiom_preview_task, task_key)
    return JSONResponse({"status": "generating"})


@router.post("/idiom-preview-all", tags=["admin"])
async def generate_all_idiom_previews(background_tasks: BackgroundTasks):
    """Trigger idiom preview generation for every task in the database.

    Tasks already drawn in this container are skipped (already ready).
    Returns a per-task status snapshot so the caller can track progress.
    """
    tasks = dbc.get_query_db("Task", query={})
    task_keys = [t["task_key"] for t in tasks if t.get("task_key")]
    sample_ready = _sample_dataset_ready() and generate_for_task_instances is not None

    snapshot: dict[str, str] = {}
    for tk in task_keys:
        if not sample_ready and not _idiom_svgs_exist(tk):
            snapshot[tk] = "skipped"
            continue
        status = _claim_idiom_preview(tk)
        if status == "claimed":
            background_tasks.add_task(_run_idiom_preview_task, tk)
            status = "generating"
        snapshot[tk] = status

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
    """Serve a pre-generated sample-data SVG for one task/idiom pair.

    Custom (admin-uploaded) idioms have no per-task sample render — they're
    fixed assets, served straight from CUSTOM_IDIOM_DIRECTORY instead.
    """
    custom_docs = dbc.get_query_db("Idiom", query={"idiom_key": idiom_key, "is_custom": True})
    if custom_docs:
        return await get_custom_idiom_asset(idiom_key)

    svg_path = (
        SAMPLE_DATA_DIR / "output" / _IDIOM_PREVIEW_EXP_ID / task_key / f"{idiom_key}.svg"
    )
    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Preview not found for {task_key}/{idiom_key}. Trigger generation first.",
        )
    from fastapi.responses import FileResponse as _FileResponse
    # The URL stays the same when a deploy redraws the preview, so make the
    # browser revalidate instead of showing the drawing it cached before.
    return _FileResponse(str(svg_path), media_type="image/svg+xml",
                         headers={"Cache-Control": "no-cache"})


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
    # Reaching this endpoint at all means the admin chose; an empty list is
    # then "ask nothing", not "fall back to every system question".
    set_fields = {
        "knowledge_question_ids": body.knowledge_question_ids,
        "knowledge_questions_configured": True,
    }
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
# Participant intro pages (Key Concepts + Before You Begin) and process model
# ---------------------------------------------------------------------------

@router.patch("/experiments/{experiment_id}/intro-pages", tags=["admin"])
async def update_experiment_intro_pages(experiment_id: str, body: ds.IntroPageSections):
    set_fields = {
        "concept_sections": body.concept_sections,
        "taskintro_sections": body.taskintro_sections,
        "concept_citation_enabled": body.concept_citation_enabled,
        # Blank text means "use the default reference", stored as None.
        "concept_citation_text": (body.concept_citation_text or "").strip() or None,
        "taskintro_citation_enabled": body.taskintro_citation_enabled,
        "taskintro_citation_text": (body.taskintro_citation_text or "").strip() or None,
    }
    if body.current_step is not None:
        set_fields["current_step"] = body.current_step
    updated = dbc.update_document(
        "Experiment",
        query={"_id": experiment_id},
        update={"$set": set_fields},
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Intro pages updated."})


def _remove_process_model_file(exp: dict) -> None:
    ext = exp.get("process_model_ext")
    if ext:
        (PROCESS_MODEL_DIRECTORY / f"{exp['_id']}{ext}").unlink(missing_ok=True)


@router.post("/experiments/{experiment_id}/process-model", tags=["admin"])
async def upload_experiment_process_model(experiment_id: str, file: UploadFile):
    """Replace the bundled order-to-cash diagram on the participant intro pages
    with an admin-uploaded image (SVG/PNG/JPG) for this experiment."""
    try:
        exp = dbc.get_document("Experiment", {"_id": experiment_id})
        if not exp:
            raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
        ext = _validate_extension(file.filename, ALLOWED_PROCESS_MODEL_EXTENSIONS, "Process model image")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > MAX_PROCESS_MODEL_BYTES:
            raise HTTPException(status_code=400, detail="Process model image must be 10 MB or smaller.")

        PROCESS_MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
        _remove_process_model_file(exp)
        (PROCESS_MODEL_DIRECTORY / f"{experiment_id}{ext}").write_bytes(content)
        dbc.update_document(
            "Experiment",
            query={"_id": experiment_id},
            update={"$set": {"process_model_ext": ext}},
        )
        return JSONResponse(content={"message": "Process model uploaded.", "process_model_ext": ext}, status_code=201)
    finally:
        await file.close()


@router.delete("/experiments/{experiment_id}/process-model", tags=["admin"])
async def delete_experiment_process_model(experiment_id: str):
    """Drop the uploaded process model; the intro pages fall back to the bundled diagram."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    _remove_process_model_file(exp)
    dbc.update_document(
        "Experiment",
        query={"_id": experiment_id},
        update={"$set": {"process_model_ext": None}},
    )
    return JSONResponse(content={"message": "Process model reset to default."})


@router.get("/experiments/{experiment_id}/process-model", tags=["admin"])
async def get_experiment_process_model(experiment_id: str):
    """Serve the experiment's uploaded process model image (admin preview)."""
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    path = utils.process_model_path(exp)
    if path is None:
        raise HTTPException(status_code=404, detail="No uploaded process model for this experiment.")
    from fastapi.responses import FileResponse as _FileResponse
    return _FileResponse(str(path), media_type=utils.image_media_type(path.suffix))
