from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

import ProViBackend.utils.config as config
import ProViBackend.utils.database.connection as dbc
from ProViBackend.app.routers.vis_mapping import TASK_KEY_TO_DIR, IDIOM_KEY_TO_SVG_SUFFIX

router = APIRouter(prefix="/participant")


def _resolve_svg_path(task_id: str, idiom_id: str, dataset_id: str):
    """Resolve DB IDs to a filesystem SVG path.

    Returns (path, error_message). On success error_message is None.
    Falls back to new_output/ when dataset_id is empty.
    """
    task  = dbc.get_document("Task",  {"_id": task_id})
    idiom = dbc.get_document("Idiom", {"_id": idiom_id})

    if not task:
        return None, f"Task not found: {task_id}"
    if not idiom:
        return None, f"Idiom not found: {idiom_id}"

    task_dir   = TASK_KEY_TO_DIR.get(task["task_key"])
    svg_suffix = IDIOM_KEY_TO_SVG_SUFFIX.get(idiom["idiom_key"])

    if not task_dir:
        return None, f"No directory mapping for task_key: {task['task_key']}"
    if not svg_suffix:
        return None, f"No SVG mapping for idiom_key: {idiom['idiom_key']}"

    dataset_loc = "new_output" if (not dataset_id or dataset_id == "new_output") else f"output/{dataset_id}"

    svg_path = (
        config.BASE_DIRECTORY
        / dataset_loc
        / task_dir
        / f"{task_dir}_{svg_suffix}.svg"
    )
    return svg_path, None


@router.get("/experiment/active", tags=["participant"])
async def get_active_experiment():
    """Return the trial list for the currently active experiment.

    Each trial contains the task/idiom metadata and a precomputed svg_path
    that the frontend can use to construct the /participant/vis/... URL.
    """
    experiments = dbc.get_query_db("Experiment", {"status": "active"})
    if not experiments:
        raise HTTPException(status_code=404, detail="No active experiment found.")

    exp = sorted(experiments, key=lambda e: e.get("created_at", ""), reverse=True)[0]
    trials = []

    for tc in exp.get("task_configs", []):
        task_id   = tc.get("task_id", "")
        idiom_id  = tc.get("idiom_id", "")
        dataset_id = tc.get("dataset_id", "")

        if not task_id or not idiom_id:
            continue

        task  = dbc.get_document("Task",  {"_id": task_id})
        idiom = dbc.get_document("Idiom", {"_id": idiom_id})
        if not task or not idiom:
            continue

        task_dir   = TASK_KEY_TO_DIR.get(task["task_key"])
        svg_suffix = IDIOM_KEY_TO_SVG_SUFFIX.get(idiom["idiom_key"])

        trials.append({
            "task_id":     task_id,
            "idiom_id":    idiom_id,
            "dataset_id":  dataset_id,
            "task_key":    task["task_key"],
            "task_label":  task["label"],
            "idiom_key":   idiom["idiom_key"],
            "idiom_label": idiom["label"],
            "answer_type": task["answer_type"],
            "svg_available": bool(task_dir and svg_suffix),
        })

    return JSONResponse({
        "experiment_id":   str(exp.get("_id", "")),
        "experiment_name": exp.get("name", ""),
        "trials":          trials,
    })


@router.get("/vis/{dataset_id}/{task_id}/{idiom_id}", tags=["participant"])
async def get_visualization(dataset_id: str, task_id: str, idiom_id: str):
    """Return the SVG file for a specific task/idiom combination.

    Pass dataset_id as "new_output" to use the pre-generated static SVGs.
    """
    svg_path, err = _resolve_svg_path(task_id, idiom_id, dataset_id)
    if err:
        raise HTTPException(status_code=404, detail=err)
    if not svg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"SVG file not found on disk: {svg_path.name}",
        )
    return FileResponse(str(svg_path), media_type="image/svg+xml")
