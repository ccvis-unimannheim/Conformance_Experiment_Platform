import os
import uuid
from typing import Annotated
import datetime
from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse
from pydantic_core._pydantic_core import ValidationError

import ProViBackend.app.datamodels.data_schemas as ds
import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.utils as utils

router = APIRouter(
    prefix="/auth"
)

# COOKIE_SECURE=false for local HTTP dev; true in production (HTTPS).
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"
_COOKIE_SAMESITE = "none" if _COOKIE_SECURE else "lax"

def get_expiry():
    expiry = datetime.datetime.now(datetime.UTC)
    expiry += datetime.timedelta(days=1)
    return expiry.strftime('%a, %d-%b-%Y %T GMT')


@router.post("/", tags=["auth"])
@router.post("", tags=["auth"], include_in_schema=False)
async def auth(body: ds.PreliminaryAnswersRequest):
    preliminary_id = str(uuid.uuid4())
    preliminary_doc = {"_id": preliminary_id, **body.model_dump()}
    dbc.create_document("PreliminaryAnswers", preliminary_doc)

    user_id = str(uuid.uuid1())
    user_doc = {
        "user_id": user_id,
        "preliminary_id": preliminary_id,
        "knowledge_id": "",
        "insert_datetime": utils.get_current_datetime(),
    }
    dbc.create_document("User", user_doc)

    response = JSONResponse(content={"message": "User created."})
    response.set_cookie(key="provi_user_id", value=user_id, expires=get_expiry(), secure=_COOKIE_SECURE, samesite=_COOKIE_SAMESITE)
    return response


# Todo: Clear routes once testing is done
# This route can be called from every site as long as it is called via https
@router.get("/test_cookie_ssl", tags=["auth"])
async def test_cookie_ssl():
    response = JSONResponse(
        content={"message": "Test cookie to authenticate yourself"})
    response.set_cookie(key="provi_user_id", value="test cookie user id", expires=get_expiry(), secure=True, samesite="none")
    return response


# This route can only be called from the same site but does not need https
@router.get("/test_cookie_strict", tags=["auth"])
async def test_cookie_strict():
    response = JSONResponse(
        content={"message": "Test cookie to authenticate yourself"})
    response.set_cookie(key="provi_user_id", value="test cookie user id", expires=get_expiry(), samesite="strict")
    return response

@router.get("/test_cookie_lax", tags=["auth"])
async def test_cookie_strict():
    response = JSONResponse(
        content={"message": "Test cookie to authenticate yourself"})
    response.set_cookie(key="provi_user_id", value="test cookie user id", expires=get_expiry(), samesite="lax")
    return response

@router.get("/test", tags=["auth"])
async def check_for_cookie(provi_user_id: Annotated[str | None, Cookie()] = None):
    content = {"message": "Cookie detected."}
    if provi_user_id is None:
        content = {"message": "No cookie detected! Please call GET /auth to receive a cookie"}
    response = JSONResponse(content=content)
    return response

@router.post("/knowledge", tags=["auth"])
async def knowledge_answers(body: ds.KnowledgeAnswersRequest, provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "No cookie detected! Please call GET /auth to receive a cookie"}, status_code=401)
    knowledge_id = str(uuid.uuid4())
    doc = {"_id": knowledge_id, **body.model_dump()}
    dbc.create_document("KnowledgeAnswers", doc)
    dbc.update_document("User", {"user_id": provi_user_id}, {"$set": {"knowledge_id": knowledge_id}})
    return JSONResponse(content={"message": "Knowledge answers added to database."})


@router.post("/feedback", tags=["auth"])
async def feedback_answers(body: ds.FeedbackAnswersRequest, provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "No cookie detected!"}, status_code=401)
    feedback_id = str(uuid.uuid4())
    doc = {"_id": feedback_id, **body.model_dump(), "insert_datetime": utils.get_current_datetime()}
    dbc.create_document("FeedbackAnswers", doc)
    dbc.update_document("User", {"user_id": provi_user_id}, {"$set": {"feedback_id": feedback_id}})
    return JSONResponse(content={"message": "Feedback saved."})