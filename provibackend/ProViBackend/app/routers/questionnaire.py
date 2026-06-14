from typing import Annotated
from fastapi import APIRouter, Cookie
from fastapi.responses import FileResponse, JSONResponse
import ProViBackend.utils.config as config
import ProViBackend.app.datamodels.data_schemas as ds
import ProViBackend.app.scoring as scoring
import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.utils as utils

QUESTIONNAIRE_FILE_PATH = config.BASE_DIRECTORY / "app/static/questionnaire.csv"

router = APIRouter(
    prefix="/survey"
)


def _lookup_ground_truth(experiment_id: str | None, task_id: str):
    """Find (answer_format, ground_truth) for a task in an experiment.

    Reads the experiment's task_instances (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §7).
    Returns (None, None) when the experiment/task isn't found or GT not authored —
    the answer then stays ungraded (is_correct = None).
    """
    if not experiment_id:
        return None, None
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        return None, None
    for ti in exp.get("task_instances", []):
        if ti.get("task_id") == task_id:
            return ti.get("answer_format"), ti.get("ground_truth")
    return None, None

@router.get("/questionnaire", tags=["questionnaire"])
async def get_questionnaire():
    return FileResponse(QUESTIONNAIRE_FILE_PATH, filename="questionnaire.csv")


@router.post("/answer", tags=["questionnaire"])
async def post_answer(answer_from_frontend: ds.AnswerFromFrontend, provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "Authentication cookie is missing."}, status_code=401)
    
    user_id = provi_user_id

    # Grade at submit time: look up this task's stored ground truth and compare.
    # Unauthored GT or free-text answers stay ungraded (is_correct = None).
    answer_format, ground_truth = _lookup_ground_truth(
        answer_from_frontend.experiment_id, answer_from_frontend.task_id
    )
    is_correct = scoring.score_answer(answer_format, ground_truth, answer_from_frontend.answer)

    answer = ds.AnswerForDatabase(
        user_id=user_id,
        experiment_id=answer_from_frontend.experiment_id,
        question_id=answer_from_frontend.question_id,
        task_id=answer_from_frontend.task_id,
        idiom_id=answer_from_frontend.idiom_id,
        dataset_id=answer_from_frontend.dataset_id,
        ground_truth_id=answer_from_frontend.ground_truth_id,
        trial_index=answer_from_frontend.trial_index,
        presentation_order=answer_from_frontend.presentation_order,
        answer=answer_from_frontend.answer,
        is_correct=is_correct,
        response_time_ms=answer_from_frontend.response_time_ms,
        insert_datetime=utils.get_current_datetime(),
    )

    dbc.create_answer(answer)
    return JSONResponse(content={"message": "Answer received.", "answer": answer_from_frontend.model_dump()}, status_code=200)