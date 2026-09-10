import random
import uuid
import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import DfgBackend.utils.database.connection as dbc
import DfgBackend.utils.redis_handler as redis_handler

router = APIRouter(
    prefix="/auth"
)

# Uses its own DfgUser/DfgDataset collections (not the main app's User/Dataset)
# so DFG test data never mixes with CC's collections, which now use different
# field shapes for those same collection names.


class StartSessionRequest(BaseModel):
    """Kept intentionally minimal for the standalone test flow — the original
    previous-team version balanced assignment by self-reported PM proficiency;
    that's dropped here in favor of a plain random pick among active datasets."""
    pass


def get_expiry():
    expiry = datetime.datetime.now(datetime.UTC)
    expiry += datetime.timedelta(days=1)
    return expiry.strftime('%a, %d-%b-%Y %T GMT')


@router.post("/", tags=["auth"])
async def start_session(_: StartSessionRequest | None = None):
    active_datasets = dbc.get_query_db("DfgDataset", query={"dataset_is_active": True})
    if not active_datasets:
        return JSONResponse(
            content={"message": "No active dataset found. Upload and activate one via /dfg/api/admin first."},
            status_code=500,
        )
    dataset = random.choice(active_datasets)
    dataset_id = dataset["dataset_id"]

    user_id = str(uuid.uuid1())
    dbc.create_document("DfgUser", {
        "user_id": user_id,
        "dataset_id": dataset_id,
        "insert_datetime": datetime.datetime.now(datetime.UTC).isoformat(),
    })
    redis_handler.write_key_to_redis(user_id, dataset_id)

    response = JSONResponse(content={"message": "Session started.", "dataset_id": dataset_id})
    response.set_cookie(key="provi_user_id", value=user_id, expires=get_expiry(), secure=True, samesite="none")
    return response


@router.get("/test", tags=["auth"])
async def check_for_cookie(provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "No cookie detected! Please call POST /auth/ to receive a cookie"})
    return JSONResponse(content={"message": "Cookie detected.", "user_id": provi_user_id})
