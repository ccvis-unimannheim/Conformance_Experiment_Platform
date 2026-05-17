from typing import Annotated
from fastapi import APIRouter, Cookie
from fastapi.responses import FileResponse, JSONResponse
import ProViBackend.utils.config as config
import ProViBackend.app.datamodels.data_schemas as ds
import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.utils as utils

QUESTIONNAIRE_FILE_PATH = config.BASE_DIRECTORY / "app/static/questionnaire.csv"

router = APIRouter(
    prefix="/survey"
)

@router.get("/questionnaire", tags=["questionnaire"])
async def get_questionnaire():
    return FileResponse(QUESTIONNAIRE_FILE_PATH, filename="questionnaire.csv")


@router.post("/answer", tags=["questionnaire"])
async def post_answer(answer_from_frontend: ds.AnswerFromFrontend, provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "Authentication cookie is missing."}, status_code=401)
    
    user_id = provi_user_id

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
        response_time_ms=answer_from_frontend.response_time_ms,
        insert_datetime=utils.get_current_datetime(),
    )

    dbc.create_answer(answer)
    return JSONResponse(content={"message": "Answer received.", "answer": answer_from_frontend.model_dump()}, status_code=200)