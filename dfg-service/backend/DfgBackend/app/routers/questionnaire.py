from typing import Annotated
from fastapi import APIRouter, Cookie
from fastapi.responses import FileResponse, JSONResponse
import DfgBackend.utils.config as config
import DfgBackend.app.datamodels.data_schemas as ds
import DfgBackend.utils.database.connection as dbc
import DfgBackend.utils.utils as utils

QUESTIONNAIRE_FILE_PATH = config.BASE_DIRECTORY / "app/static/questionnaire.csv"

router = APIRouter(
    prefix="/survey"
)


@router.get("/questionnaire", tags=["questionnaire"])
async def get_questionnaire():
    return FileResponse(QUESTIONNAIRE_FILE_PATH, filename="questionnaire.csv")


@router.post("/answer", tags=["questionnaire"])
async def post_answer(answer_from_frontend: ds.AnswerFromFrontend, dfg_user_id: Annotated[str | None, Cookie()] = None):
    if dfg_user_id is None:
        return JSONResponse(content={"message": "Authentication cookie is missing."}, status_code=401)

    user_id = dfg_user_id

    answer = ds.AnswerForDatabase(user_id=user_id, answer=answer_from_frontend, insert_datetime=utils.get_current_datetime())

    dbc.create_answer(answer)
    return JSONResponse(content={"message": "Answer received.", "answer": answer_from_frontend.model_dump()}, status_code=200)
