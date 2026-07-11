import random

from typing import Annotated
from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import ProViBackend.utils.config as config
import ProViBackend.utils.database.connection as dbc
from ProViBackend.scripts.tasks import task_registry
from ProViBackend.utils.database.assignment import (
    assign_participant_to_experiment,
    get_assignment,
    parse_trial_token,
)

router = APIRouter(prefix="/participant")


class AssignmentRequest(BaseModel):
    experiment_id: str


# PARTICIPANT_TRIAL_CONTRACT.md "answer_format -> answer_type (widget) mapping"
ANSWER_FORMAT_TO_ANSWER_TYPE = {
    "mc-single": "single_choice",
    "yes-no": "single_choice",      # Yes/No rendered as two radio options
    "mc-multi": "multiple_choice",
    "pct": "numeric",
    "count": "numeric",
    "decimal": "numeric",
    "pct-set": "numeric_set",
    "count-set": "numeric_set",
    "rank": "rank",
    "matrix": "matrix",
    "free-text": "free_text",
}

# PARTICIPANT_TRIAL_CONTRACT.md "Fallback (task not yet authored - step 6 pending)"
FALLBACK_ANSWER_FORMAT = "free-text"

# Choice formats: the option `value` is the submittable token (safe to send).
# matrix options are pair tokens (e.g. "a__b"); their `correct` flag is stripped
# below, so the candidate set is safe to send the same way as a choice set.
# yes-no is a two-option choice set (Yes/No) handled exactly like mc-single.
_CHOICE_FORMATS = {"mc-single", "mc-multi", "matrix", "yes-no"}
# Labelled-set formats: options are row labels; the `value` column holds the GT
# number, which must NOT be sent to participants (PARTICIPANT_TRIAL_CONTRACT.md
# "The frontend must never receive ... any other ground-truth value").
_LABELLED_SET_FORMATS = {"pct-set", "count-set"}
# Rank: the GT option ORDER is the answer, so it must be shuffled before sending.
_RANK_FORMATS = {"rank"}


def _participant_options(answer_format: str, gt_options: list) -> list:
    """Strip ground-truth from a task's option set per answer_format.

    - choice (mc-single/mc-multi/matrix): send {label, value} (value = submit
      token). The `correct` flag is dropped, so only the candidate set is exposed.
    - labelled-set (pct-set/count-set): send {label, value:label} only — the GT
      number in `value` is withheld so the answer isn't leaked.
    - rank: send {label, value} but SHUFFLED — the GT lives in option order, so
      the stored order must never reach the participant.
    - everything else: no options.
    """
    if answer_format in _CHOICE_FORMATS:
        return [
            {"label": opt.get("label", ""), "value": opt.get("value") or opt.get("label", "")}
            for opt in gt_options
        ]
    if answer_format in _LABELLED_SET_FORMATS:
        return [{"label": opt.get("label", ""), "value": opt.get("label", "")} for opt in gt_options]
    if answer_format in _RANK_FORMATS:
        opts = [
            {"label": opt.get("label", ""), "value": opt.get("value") or opt.get("label", "")}
            for opt in gt_options
        ]
        random.shuffle(opts)
        return opts
    return []


def _trial_contract_fields(task_instances_by_task_id: dict, task_id: str) -> dict:
    """Derive the stable trial-contract fields for one task.

    Reads `answer_format`/`ground_truth` from the experiment's task_instances
    (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md step 7). Falls back to free-text/
    free_text/[]/false when the task hasn't been authored yet
    (PARTICIPANT_TRIAL_CONTRACT.md "Fallback"). Ground-truth values are stripped
    from `options` so they never reach the participant.
    """
    ti = task_instances_by_task_id.get(task_id) or {}
    answer_format = ti.get("answer_format") or FALLBACK_ANSWER_FORMAT
    answer_type = ANSWER_FORMAT_TO_ANSWER_TYPE.get(answer_format, "free_text")

    ground_truth = ti.get("ground_truth") or {}
    options = _participant_options(answer_format, ground_truth.get("options", []))

    return {
        "answer_format": answer_format,
        "answer_type": answer_type,
        "decisive": bool(ground_truth.get("decisive", False)),
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
            "idiom_label":   idiom["label"],
            "answer_format": contract["answer_format"],
            "answer_type":   contract["answer_type"],
            "decisive":      contract["decisive"],
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

        trials.append({
            "trial_index":   idx,
            "task_id":       task_id,
            "idiom_id":      idiom_id,
            "dataset_id":    dataset_id,
            "task_key":      task["task_key"],
            "task_label":    task["label"],
            "idiom_key":     idiom["idiom_key"],
            "idiom_label":   idiom["label"],
            "answer_format": contract["answer_format"],
            "answer_type":   contract["answer_type"],
            "decisive":      contract["decisive"],
            "options":       contract["options"],
            "svg_available": svg_available,
            "param_hints":   param_hints,
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
