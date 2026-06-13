from typing import Annotated
from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import ProViBackend.utils.config as config
import ProViBackend.utils.database.connection as dbc
from ProViBackend.utils.database.assignment import (
    assign_participant_to_experiment,
    get_assignment,
    parse_trial_token,
)

router = APIRouter(prefix="/participant")


class AssignmentRequest(BaseModel):
    experiment_id: str


def _resolve_svg_path(task_id: str, idiom_id: str, dataset_id: str, experiment_id: str | None = None):
    """Resolve DB IDs to a filesystem SVG path.

    If `experiment_id` is given and the per-experiment SVG exists at
    data/{dataset_id}/output/{experiment_id}/{task_key}/{idiom_key}.svg
    (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §7), that path is returned. Otherwise
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

        trials.append({
            "task_id":       task_id,
            "idiom_id":      idiom_id,
            "dataset_id":    dataset_id,
            "task_key":      task["task_key"],
            "task_label":    task["label"],
            "idiom_key":     idiom["idiom_key"],
            "idiom_label":   idiom["label"],
            "answer_type":   task["answer_type"],
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

        trials.append({
            "trial_index":   idx,
            "task_id":       task_id,
            "idiom_id":      idiom_id,
            "dataset_id":    dataset_id,
            "task_key":      task["task_key"],
            "task_label":    task["label"],
            "idiom_key":     idiom["idiom_key"],
            "idiom_label":   idiom["label"],
            "answer_type":   task["answer_type"],
            "svg_available": svg_available,
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
    assignment = db["UserAssignment"].find_one({"user_id": provi_user_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="No assignment found for this user.")

    total = len(assignment.get("trial_sequence", []))
    db["UserAssignment"].update_one(
        {"_id": assignment["_id"]},
        {"$set": {"current_trial_index": total}}
    )
    return JSONResponse(content={"message": "Experiment marked as complete."})
