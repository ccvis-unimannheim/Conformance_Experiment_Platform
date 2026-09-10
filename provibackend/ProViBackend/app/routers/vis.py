from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import ProViBackend.utils.config as config
import ProViBackend.utils.database.connection as dbc


router = APIRouter(
    prefix="/vis"
)


@router.get("/{dataset_id}/{task_key}/{idiom_key}", tags=["vis"])
async def get_visualization_by_keys(
    dataset_id: str,
    task_key: str,
    idiom_key: str,
    provi_user_id: Annotated[str | None, Cookie()] = None,
):
    """
    Serve a visualization file by semantic keys.
    File path: output/{dataset_id}/{task_key}/{idiom_key}.svg
    """
    if provi_user_id is None:
        return JSONResponse(
            content={"message": "No cookie detected! Please call GET /auth to receive a cookie"},
            status_code=401,
        )
    dataset = dbc.get_document("DatasetPair", {"dataset_id": dataset_id})
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    svg_path = config.BASE_DIRECTORY / "output" / dataset_id / task_key / f"{idiom_key}.svg"
    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Visualization not found: {task_key}/{idiom_key} for dataset {dataset_id}",
        )
    return FileResponse(svg_path)
