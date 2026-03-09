import uuid
from typing import Annotated
import datetime
from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse
from pydantic_core._pydantic_core import ValidationError

import ProViBackend.app.datamodels.data_schemas as ds
import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.redis_handler as redis_handler

router = APIRouter(
    prefix="/auth"
)

def get_expiry():
    expiry = datetime.datetime.now(datetime.UTC)
    expiry += datetime.timedelta(days=1)
    return expiry.strftime('%a, %d-%b-%Y %T GMT')


def get_least_assigned_dataset_for_user(pre_eliminary_answers: ds.PreEliminaryAnswers):
    # 1. Get all users with the specified proficiency criteria
    proficiency_users = dbc.get_query_db(collection="User", query={
        "pre_eliminary_answers.expertise_level_process_mining": pre_eliminary_answers.expertise_level_process_mining
    })
    print(f"Users in the same proficiency class: {proficiency_users}")

    active_datasests = dbc.get_query_db(collection="Dataset", query={
        "dataset_is_active": True
    })
    print(f"Active datasets: {active_datasests}")

    # 2. Count the occurrences of each dataset assignment
    active_dataset_counts = {}
    for dataset in active_datasests:
        active_dataset_counts[dataset["dataset_id"]] = 0

    for user in proficiency_users:
        dataset_id = user["dataset_id"]
        if dataset_id in active_dataset_counts:
            active_dataset_counts[dataset_id] += 1

    # 3. Find the dataset with the least number of users assigned over all active datasets
    try:
        least_assigned_dataset = min(active_dataset_counts, key=active_dataset_counts.get)
        print(f"Least assigned dataset: {least_assigned_dataset}")
    except ValueError:
        least_assigned_dataset = None
        print("No active datasets found")
    return least_assigned_dataset

# Todo: Increase time to load, currently at 7 sec per request. Need to find bottlenecks
@router.post("/", tags=["auth"])
async def auth(pre_eliminary_answers: ds.PreEliminaryAnswers):
    user_id = str(uuid.uuid1())
    try:
        dataset_id = get_least_assigned_dataset_for_user(pre_eliminary_answers)
        user = ds.User(user_id=user_id, pre_eliminary_answers=pre_eliminary_answers, dataset_id=dataset_id)
        dbc.create_user(user)
    except ValidationError:
        return JSONResponse(content={"message": "There is currently no active dataset where the user can get assigned "
                                                "to. Please upload datasets and select them for the survey "
                                                "via the admin page."},
                            status_code=500)
    redis_handler.write_key_to_redis(user_id, dataset_id)
    response = JSONResponse(content={"message": "New user created and added to database. You get a cookie to authenticate yourself."})
    response.set_cookie(key="provi_user_id", value=user_id, expires=get_expiry(), secure=True, samesite="none")
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
async def knowledge_answers(knowledge_answers: ds.KnowledgeAnswers, provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "No cookie detected! Please call GET /auth to receive a cookie"})
    user_id = provi_user_id
    dbc.update_user_knowledge_answers(user_id, knowledge_answers)
    return JSONResponse(content={"message": "Knowledge answers added to database."})