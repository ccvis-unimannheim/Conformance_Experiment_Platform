import json
import logging
import random

from typing import Annotated
from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import ProViBackend.app.answer_formats as afmt
import ProViBackend.utils.config as config
import ProViBackend.utils.database.connection as dbc
from ProViBackend.scripts.tasks import task_registry
from ProViBackend.app.label_overrides import resolve_idiom_label
from ProViBackend.utils.database.assignment import (
    assign_participant_to_experiment,
    get_assignment,
    parse_trial_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/participant")


class AssignmentRequest(BaseModel):
    experiment_id: str


# answer_format -> widget, from the global format registry (app/answer_formats.py).
ANSWER_FORMAT_TO_ANSWER_TYPE = dict(afmt.FORMAT_TO_WIDGET)

FALLBACK_ANSWER_FORMAT = afmt.FALLBACK_ANSWER_FORMAT


def _participant_options(answer_format: str, options: list) -> list:
    """The admin-authored option set for this format, ready to send.

    Every option is {label, value}, where `value` is the token the frontend
    submits (falling back to the label). Formats that take free input get [].

    `rank` is shuffled: the stored order is the admin's authoring order and
    carries no answer, but presenting it unchanged to every participant would
    still bias responses towards it.
    """
    if not afmt.needs_options(answer_format):
        return []
    opts = [
        {"label": opt.get("label", ""), "value": opt.get("value") or opt.get("label", "")}
        for opt in options
    ]
    if answer_format in afmt.RANK_FORMATS:
        random.shuffle(opts)
    return opts


def _trial_contract_fields(task_instances_by_task_id: dict, task_id: str) -> dict:
    """Derive the stable trial-contract fields for one task.

    Reads the answer shape the admin configured on /answer-format
    (`answer_format`, `number_kind`, `answer_options`). Falls back to
    free-text/free_text/[] when the instance has no format set
    (PARTICIPANT_TRIAL_CONTRACT.md "Fallback").
    """
    ti = task_instances_by_task_id.get(task_id) or {}
    answer_format = ti.get("answer_format") or FALLBACK_ANSWER_FORMAT
    answer_type = afmt.widget_for(answer_format)
    options = _participant_options(answer_format, ti.get("answer_options") or [])

    return {
        "answer_format": answer_format,
        "answer_type": answer_type,
        "number_kind": ti.get("number_kind") or afmt.DEFAULT_NUMBER_KIND,
        "options": options,
    }


def _build_param_hints(task_key: str, parameters: dict) -> list[dict]:
    """Return [{label, value}] for each configured parameter shown to participants.

    Participant-facing wording is decoupled from the (precise, admin-facing)
    PARAM_SPEC ``label``:
      - ``hide_hint: True`` suppresses the hint entirely (param is internal to
        reading the visualization, e.g. which traces are shown).
      - ``hint`` overrides the displayed text (falls back to ``label``).
    Empty values (None, "", empty list/dict) are skipped so unset pickers do not
    render a confusing "[ ]".
    """
    try:
        spec = task_registry.get_param_spec(task_key)
    except KeyError:
        return []
    hints = []
    for entry in spec:
        if entry.get("hide_hint"):
            continue
        key = entry.get("key", "")
        value = parameters.get(key)
        if value is None or (isinstance(value, (str, list, dict, tuple)) and len(value) == 0):
            continue
        if isinstance(value, (list, tuple)):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)
        label = entry.get("hint") or entry["label"]
        hints.append({"label": label, "value": value_str})
    return hints


def _resolve_svg_path(task_id: str, idiom_id: str, dataset_id: str, experiment_id: str | None = None):
    """Resolve DB IDs to a filesystem SVG path.

    If `experiment_id` is given and the per-experiment SVG exists at
    data/{dataset_id}/output/{experiment_id}/{task_key}/{idiom_key}.svg
    (see ADMIN_EXPERIMENT_SETUP.md), that path is returned. Otherwise
    falls back to the legacy shared path data/{dataset_id}/output/{task_key}/{idiom_key}.svg.

    Returns (path, error_message). On success error_message is None.
    """
    task  = dbc.get_document("Task",  {"_id": task_id})
    idiom = dbc.get_document("Idiom", {"_id": idiom_id})

    if not task:
        return None, f"Task not found: {task_id}"
    if not idiom:
        return None, f"Idiom not found: {idiom_id}"
    if not dataset_id:
        return None, "dataset_id is required"

    task_key  = task["task_key"]    # e.g. "task1"
    idiom_key = idiom["idiom_key"]  # e.g. "bar_chart"
    output_dir = config.BASE_DIRECTORY / "data" / dataset_id / "output"

    if experiment_id:
        per_experiment_path = output_dir / experiment_id / task_key / f"{idiom_key}.svg"
        if per_experiment_path.exists():
            return per_experiment_path, None

    legacy_path = output_dir / task_key / f"{idiom_key}.svg"
    return legacy_path, None


def _resolve_traces_path(task_key: str, dataset_id: str, experiment_id: str | None = None):
    """Resolve to this task's traces.json (shared by every idiom of the task —
    written once per generate() call, alongside the SVGs). Mirrors
    _resolve_svg_path's per-experiment / legacy fallback, minus the idiom_key.
    """
    output_dir = config.BASE_DIRECTORY / "data" / dataset_id / "output"
    if experiment_id:
        per_experiment_path = output_dir / experiment_id / task_key / "traces.json"
        if per_experiment_path.exists():
            return per_experiment_path
    return output_dir / task_key / "traces.json"


def _load_display_traces(task_key: str, dataset_id: str, experiment_id: str | None = None) -> list:
    """Read the given trace(s) for this task, or [] if this task doesn't have any
    (most tasks don't — only ones whose question refers to "the given trace(s)",
    e.g. Task 34 / Task 4)."""
    path = _resolve_traces_path(task_key, dataset_id, experiment_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("traces", [])
    except Exception:
        logger.exception("Failed to read traces.json at %s", path)
        return []


def _get_experiment_knowledge_questions(exp: dict) -> list:
    """Return knowledge questions for an experiment, stripping correct_option_index."""
    db = dbc.connect_to_database()
    kq_ids = exp.get("knowledge_question_ids", [])
    if kq_ids:
        questions = list(db["KnowledgeQuestion"].find({"_id": {"$in": kq_ids}}))
        id_order = {qid: i for i, qid in enumerate(kq_ids)}
        questions.sort(key=lambda q: id_order.get(q["_id"], 999))
    else:
        questions = list(db["KnowledgeQuestion"].find({"is_system": True}))
    for q in questions:
        q.pop("correct_option_index", None)
        if "_id" in q and not isinstance(q["_id"], str):
            q["_id"] = str(q["_id"])
    return questions


_DEFAULT_PREQUESTIONNAIRE_SECTIONS = [
    "personal_info", "academic_profile", "technical_expertise", "tool_experience"
]

@router.get("/prequestionnaire-sections", tags=["participant"])
async def get_active_prequestionnaire_sections():
    """Return enabled pre-questionnaire sections for the currently active/published experiment."""
    experiments = dbc.get_query_db("Experiment", {"status": {"$in": ["active", "published"]}})
    if not experiments:
        return JSONResponse(content={"sections": _DEFAULT_PREQUESTIONNAIRE_SECTIONS})
    exp = sorted(experiments, key=lambda e: e.get("created_at", ""), reverse=True)[0]
    sections = exp.get("prequestionnaire_sections", _DEFAULT_PREQUESTIONNAIRE_SECTIONS)
    return JSONResponse(content={"sections": sections})


@router.get("/knowledge-questions", tags=["participant"])
async def get_active_knowledge_questions():
    """Return knowledge questions for the currently active/published experiment."""
    experiments = dbc.get_query_db("Experiment", {"status": {"$in": ["active", "published"]}})
    if not experiments:
        raise HTTPException(status_code=404, detail="No active experiment found.")
    exp = sorted(experiments, key=lambda e: e.get("created_at", ""), reverse=True)[0]
    return JSONResponse(content={"questions": _get_experiment_knowledge_questions(exp)})


@router.get("/experiment/{experiment_id}/knowledge-questions", tags=["participant"])
async def get_experiment_knowledge_questions(experiment_id: str):
    """Return knowledge questions for a specific experiment (admin preview)."""
    db = dbc.connect_to_database()
    exp = db["Experiment"].find_one({"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return JSONResponse(content={"questions": _get_experiment_knowledge_questions(exp)})


@router.get("/experiment/active", tags=["participant"])
async def get_active_experiment():
    """Return the trial list for the currently active experiment.

    Each trial contains task/idiom metadata and the svg_path the frontend
    uses to call GET /participant/vis/{dataset_id}/{task_id}/{idiom_id}.
    """
    experiments = dbc.get_query_db("Experiment", {"status": {"$in": ["active", "published"]}})
    if not experiments:
        raise HTTPException(status_code=404, detail="No active experiment found.")

    exp = sorted(experiments, key=lambda e: e.get("created_at", ""), reverse=True)[0]
    experiment_id = str(exp.get("_id", ""))
    trials = []

    task_instances_by_task_id = {ti["task_id"]: ti for ti in exp.get("task_instances", [])}

    for tc in exp.get("task_configs", []):
        task_id    = tc.get("task_id", "")
        idiom_id   = tc.get("idiom_id", "")
        dataset_id = tc.get("dataset_id", "")

        if not task_id or not idiom_id:
            continue

        task  = dbc.get_document("Task",  {"_id": task_id})
        idiom = dbc.get_document("Idiom", {"_id": idiom_id})
        if not task or not idiom:
            continue

        svg_path, _ = _resolve_svg_path(task_id, idiom_id, dataset_id, experiment_id)
        svg_available = bool(svg_path and svg_path.exists())
        contract = _trial_contract_fields(task_instances_by_task_id, task_id)

        trials.append({
            "task_id":       task_id,
            "idiom_id":      idiom_id,
            "dataset_id":    dataset_id,
            "task_key":      task["task_key"],
            "task_label":    task["label"],
            "idiom_key":     idiom["idiom_key"],
            "idiom_label":   resolve_idiom_label(task["task_key"], idiom["idiom_key"], idiom["label"]),
            "answer_format": contract["answer_format"],
            "answer_type":   contract["answer_type"],
            "number_kind":   contract["number_kind"],
            "options":       contract["options"],
            "svg_available": svg_available,
        })

    return JSONResponse({
        "experiment_id":   str(exp.get("_id", "")),
        "experiment_name": exp.get("name", ""),
        "trials":          trials,
    })


@router.get("/vis/{dataset_id}/{task_id}/{idiom_id}", tags=["participant"])
async def get_visualization(dataset_id: str, task_id: str, idiom_id: str, experiment_id: str | None = None):
    """Return the SVG file for a specific task/idiom/dataset combination.

    `experiment_id` is optional; if given and a per-experiment SVG exists at
    data/{dataset_id}/output/{experiment_id}/{task_key}/{idiom_key}.svg it is
    served, otherwise the legacy shared path is used (see _resolve_svg_path).
    """
    svg_path, err = _resolve_svg_path(task_id, idiom_id, dataset_id, experiment_id)
    if err:
        raise HTTPException(status_code=404, detail=err)
    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"SVG not found on disk: {svg_path.relative_to(config.BASE_DIRECTORY)}",
        )
    return FileResponse(str(svg_path), media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Assignment endpoints
# ---------------------------------------------------------------------------

@router.post("/assignment", tags=["participant"])
async def create_or_get_assignment(
    body: AssignmentRequest,
    provi_user_id: Annotated[str | None, Cookie()] = None,
):
    """
    Assign a participant to an experiment (idempotent).

    Reads user_id from the provi_user_id cookie (set by POST /auth/).
    On first call: selects one idiom per task using balanced random allocation
    and persists a UserAssignment document.
    On subsequent calls: returns the existing assignment unchanged.

    Returns the full assignment including the ordered trial_sequence.
    """
    if provi_user_id is None:
        raise HTTPException(status_code=401, detail="No user cookie found. Call POST /auth/ first.")
    try:
        assignment = assign_participant_to_experiment(provi_user_id, body.experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if "_id" in assignment and not isinstance(assignment["_id"], str):
        assignment["_id"] = str(assignment["_id"])
    return JSONResponse(content=assignment)


@router.get("/assignment/{experiment_id}/trials", tags=["participant"])
async def get_assigned_trials(
    experiment_id: str,
    provi_user_id: Annotated[str | None, Cookie()] = None,
):
    """
    Return the participant's personalised trial list with full task/idiom metadata.

    Each element in `trials` corresponds to one entry in trial_sequence and
    contains the same fields as the active-experiment endpoint, plus
    `trial_index` for ordered display.
    """
    if provi_user_id is None:
        raise HTTPException(status_code=401, detail="No user cookie found. Call POST /auth/ first.")
    assignment = get_assignment(provi_user_id, experiment_id)
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="No assignment found. Call POST /participant/assignment first.",
        )

    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    task_instances_by_task_id = {ti["task_id"]: ti for ti in (exp or {}).get("task_instances", [])}

    trials = []
    for idx, token in enumerate(assignment.get("trial_sequence", [])):
        try:
            task_id, idiom_id, dataset_id = parse_trial_token(token)
        except ValueError:
            continue

        task  = dbc.get_document("Task",  {"_id": task_id})
        idiom = dbc.get_document("Idiom", {"_id": idiom_id})
        if not task or not idiom:
            continue

        svg_path, _ = _resolve_svg_path(task_id, idiom_id, dataset_id, experiment_id)
        svg_available = bool(svg_path and svg_path.exists())
        contract = _trial_contract_fields(task_instances_by_task_id, task_id)

        ti = task_instances_by_task_id.get(task_id, {})
        parameters = (ti.get("parameters") or {})
        param_hints = _build_param_hints(task["task_key"], parameters)
        display_traces = _load_display_traces(task["task_key"], dataset_id, experiment_id)

        trials.append({
            "trial_index":   idx,
            "task_id":       task_id,
            "idiom_id":      idiom_id,
            "dataset_id":    dataset_id,
            "task_key":      task["task_key"],
            "task_label":    task["label"],
            "idiom_key":     idiom["idiom_key"],
            "idiom_label":   resolve_idiom_label(task["task_key"], idiom["idiom_key"], idiom["label"]),
            "answer_format": contract["answer_format"],
            "answer_type":   contract["answer_type"],
            "number_kind":   contract["number_kind"],
            "options":       contract["options"],
            "svg_available": svg_available,
            "param_hints":   param_hints,
            "display_traces": display_traces,
        })

    return JSONResponse({
        "assignment_id":       assignment["_id"],
        "experiment_id":       experiment_id,
        "user_id":             provi_user_id,
        "current_trial_index": assignment.get("current_trial_index", 0),
        "trials":              trials,
    })


@router.post("/complete", tags=["participant"])
async def mark_experiment_complete(provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        raise HTTPException(status_code=401, detail="No user cookie found.")

    db = dbc.connect_to_database()

    # Find the currently active/published experiment so we update the right assignment.
    experiments = dbc.get_query_db("Experiment", {"status": {"$in": ["active", "published"]}})
    if not experiments:
        raise HTTPException(status_code=404, detail="No active experiment found.")
    experiment_id = str(sorted(experiments, key=lambda e: e.get("created_at", ""), reverse=True)[0].get("_id", ""))

    assignment = db["UserAssignment"].find_one({"user_id": provi_user_id, "experiment_id": experiment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="No assignment found for this user.")

    total = len(assignment.get("trial_sequence", []))
    db["UserAssignment"].update_one(
        {"_id": assignment["_id"]},
        {"$set": {"current_trial_index": total}}
    )
    return JSONResponse(content={"message": "Experiment marked as complete."})
