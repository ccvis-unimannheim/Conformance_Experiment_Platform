from typing import Annotated

from fastapi import APIRouter, Cookie
from fastapi.responses import FileResponse, JSONResponse
import json
import DfgBackend.utils.config as config
import DfgBackend.utils.redis_handler as redis_handler


router = APIRouter(
    prefix="/vis"
)


def _no_cookie():
    return JSONResponse(content={"message": "No session cookie. Please call POST /auth/ first."}, status_code=401)


def _dataset_location(user_id: str):
    """Resolve the participant's dataset directory, or None if the session or
    dataset is unknown to Redis."""
    try:
        dataset_id = redis_handler.get_value_from_redis(user_id)
        return config.BASE_DIRECTORY / redis_handler.get_value_from_redis(dataset_id)
    except ValueError:
        return None


def _missing(what: str):
    # Generated files live in the output volume; a dataset registered before
    # that volume existed has its files gone and must be uploaded again.
    return JSONResponse(content={"message": f"{what} not found on the server. Re-upload the dataset in /dfg/admin."}, status_code=404)


@router.get("/mapping", tags=["vis"])
async def get_vis_mapping(dfg_user_id: Annotated[str | None, Cookie()] = None):
    if dfg_user_id is None:
        return _no_cookie()
    location = _dataset_location(dfg_user_id)
    if location is None:
        return JSONResponse(content={"message": "Unknown session. Please reload the page."}, status_code=401)
    mapping_file_path = location.parent / "normalmapping.json"
    if not mapping_file_path.is_file():
        return _missing("Graph mapping")
    with open(mapping_file_path) as f:
        return json.load(f)


@router.get("/{svg_id}", tags=["vis"])
async def get_visualization(svg_id: str, dfg_user_id: Annotated[str | None, Cookie()] = None):
    if dfg_user_id is None:
        return _no_cookie()
    location = _dataset_location(dfg_user_id)
    if location is None:
        return JSONResponse(content={"message": "Unknown session. Please reload the page."}, status_code=401)
    svg_path = location / f"{svg_id}.svg"
    if not svg_path.is_file():
        return _missing(f"Graph {svg_id}")
    return FileResponse(svg_path)
