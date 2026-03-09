import uuid
from typing import Annotated
from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse

import ProViBackend.app.datamodels.data_schemas as ds
import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.redis_handler as redis_handler

router = APIRouter(
    prefix="/uitracking"
)


@router.post("/", tags=["ui-log"])
async def post_ui_log_data(ui_log_data: ds.UILogDataFrontend, provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "No cookie detected! Please call GET /auth to receive a cookie"})
    ui_log_data_db = ds.UILogDataDatabase(user_id=provi_user_id, ui_log_data=ui_log_data)
    dbc.save_ui_logging_data(ui_log_data_db)
    return JSONResponse(content={"message": "UI tracking data added to database."})