from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

import ProViBackend.utils.config as config
import ProViBackend.utils.database.connection as dbc

router = APIRouter(prefix="/participant")


def _resolve_svg_path(task_id: str, idiom_id: str, dataset_id: str):
    """Resolve DB IDs to a filesystem SVG path.

    Returns (path, error_message). On success error_message is None.
    """
    task  = dbc.get_document("Task",  {"_id": task_id})
    idiom = dbc.get_document("Idiom", {"_id": idiom_id})

    if not task:
        return None, f"Task not found: {task_id}"
    if not idiom:
        return None, f"Idiom not found: {idiom_id}"
    if not dataset_id:
        return None, "dataset_id is required"

    task_key  = task["task_key"]    # e.g. "task1"
    idiom_key = idiom["idiom_key"]  # e.g. "bar_chart"
    svg_path  = (
        config.BASE_DIRECTORY / "data" / dataset_id / "output" / task_key / f"{idiom_key}.svg"
    )
    return svg_path, None


@router.get("/experiment/active", tags=["participant"])
async def get_active_experiment():
    """Return the trial list for the currently active experiment.

    Each trial contains task/idiom metadata and the svg_path the frontend
    uses to call GET /participant/vis/{dataset_id}/{task_id}/{idiom_id}.
    """
    experiments = dbc.get_query_db("Experiment", {"status": {"$in": ["active", "published"]}})
    if not experiments:
        raise HTTPException(status_code=404, detail="No active experiment found.")

    exp = sorted(experiments, key=lambda e: e.get("created_at", ""), reverse=True)[0]
    trials = []

    for tc in exp.get("task_configs", []):
        task_id    = tc.get("task_id", "")
        idiom_id   = tc.get("idiom_id", "")
        dataset_id = tc.get("dataset_id", "")

        if not task_id or not idiom_id:
            continue

        task  = dbc.get_document("Task",  {"_id": task_id})
        idiom = dbc.get_document("Idiom", {"_id": idiom_id})
        if not task or not idiom:
            continue

        svg_path, _ = _resolve_svg_path(task_id, idiom_id, dataset_id)
        svg_available = bool(svg_path and svg_path.exists())

        trials.append({
            "task_id":       task_id,
            "idiom_id":      idiom_id,
            "dataset_id":    dataset_id,
            "task_key":      task["task_key"],
            "task_label":    task["label"],
            "idiom_key":     idiom["idiom_key"],
            "idiom_label":   idiom["label"],
            "answer_type":   task["answer_type"],
            "svg_available": svg_available,
        })

    return JSONResponse({
        "experiment_id":   str(exp.get("_id", "")),
        "experiment_name": exp.get("name", ""),
        "trials":          trials,
    })


@router.get("/vis/{dataset_id}/{task_id}/{idiom_id}", tags=["participant"])
async def get_visualization(dataset_id: str, task_id: str, idiom_id: str):
    """Return the SVG file for a specific task/idiom/dataset combination."""
    svg_path, err = _resolve_svg_path(task_id, idiom_id, dataset_id)
    if err:
        raise HTTPException(status_code=404, detail=err)
    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"SVG not found on disk: {svg_path.relative_to(config.BASE_DIRECTORY)}",
        )
    return FileResponse(str(svg_path), media_type="image/svg+xml")
