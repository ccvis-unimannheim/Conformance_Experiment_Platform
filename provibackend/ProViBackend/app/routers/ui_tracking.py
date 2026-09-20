from typing import Annotated
from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse

import ProViBackend.app.datamodels.data_schemas as ds
import ProViBackend.utils.database.connection as dbc

router = APIRouter(
    prefix="/uitracking"
)


@router.post("/fitness-help", tags=["ui-log"])
async def post_fitness_help_event(
    event: ds.FitnessHelpEvent,
    provi_user_id: Annotated[str | None, Cookie()] = None,
):
    """Record one open→close interaction with the fitness definition popup."""
    doc = event.model_dump()
    doc["user_id"] = provi_user_id
    dbc.create_document("FitnessHelpEvents", doc)
    return JSONResponse(content={"message": "Fitness help event recorded."})


@router.post("/term-help", tags=["ui-log"])
async def post_term_help_event(
    event: ds.TermHelpEvent,
    provi_user_id: Annotated[str | None, Cookie()] = None,
):
    """Record one open→close interaction with a per-task term explanation chip."""
    doc = event.model_dump()
    doc["user_id"] = provi_user_id
    dbc.create_document("TermHelpEvents", doc)
    return JSONResponse(content={"message": "Term help event recorded."})