from typing import Annotated

from fastapi import APIRouter, Cookie
from fastapi.responses import FileResponse, JSONResponse
import json
import DfgBackend.utils.config as config
import DfgBackend.utils.redis_handler as redis_handler


router = APIRouter(
    prefix="/vis"
)


# Todo: Add exception handling when redis returns None for dataset_location, check if redis mount takes care of this
@router.get("/mapping", tags=["vis"])
async def get_vis_mapping(provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "No cookie detected! Please call GET /auth to receive a cookie"})
    user_id = provi_user_id
    user_assigned_dataset_id = redis_handler.get_value_from_redis(user_id) # Error: Is None after restart
    user_assigned_dataset_location = redis_handler.get_value_from_redis(user_assigned_dataset_id)
    mapping_file_path = config.BASE_DIRECTORY / user_assigned_dataset_location
    mapping_file_path = mapping_file_path.parent / "normalmapping.json"
    with open(mapping_file_path) as f:
        d = json.load(f)
        return d


@router.get("/{svg_id}", tags=["vis"])
async def get_visualization(svg_id: str, provi_user_id: Annotated[str | None, Cookie()] = None):
    if provi_user_id is None:
        return JSONResponse(content={"message": "No cookie detected! Please call GET /auth to receive a cookie"})
    user_id = provi_user_id
    user_assigned_dataset_id = redis_handler.get_value_from_redis(user_id)
    user_assigned_dataset_location = redis_handler.get_value_from_redis(user_assigned_dataset_id)
    return FileResponse(config.BASE_DIRECTORY / user_assigned_dataset_location / f"{svg_id}.svg")
