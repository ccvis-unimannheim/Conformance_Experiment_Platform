from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import ProViBackend.utils.database.connection as dbc
from ProViBackend.app.label_overrides import resolve_idiom_label

router = APIRouter(prefix="/experiment")


def _resolve_task_configs(task_configs: list) -> list:
    """Replace task_id/idiom_id UUIDs with their semantic task_key/idiom_key."""
    resolved = []
    for tc in task_configs:
        task_doc = dbc.get_document("Task", {"_id": tc.get("task_id")})
        idiom_doc = dbc.get_document("Idiom", {"_id": tc.get("idiom_id")})
        resolved.append({
            **tc,
            "task_key":   task_doc["task_key"]  if task_doc  else None,
            "idiom_key":  idiom_doc["idiom_key"] if idiom_doc else None,
            "idiom_label": resolve_idiom_label(
                task_doc["task_key"]  if task_doc  else "",
                idiom_doc["idiom_key"] if idiom_doc else "",
                idiom_doc["label"]    if idiom_doc else "",
            ) or None,
        })
    return resolved


@router.get("/active", tags=["experiment"])
async def get_active_experiment():
    """Return the single published experiment with task_key and idiom_key resolved."""
    experiments = dbc.get_query_db("Experiment", query={"status": "published"})
    if not experiments:
        raise HTTPException(status_code=404, detail="No published experiment found.")
    exp = experiments[0]
    if "_id" in exp and not isinstance(exp["_id"], str):
        exp["_id"] = str(exp["_id"])
    exp["task_configs"] = _resolve_task_configs(exp.get("task_configs", []))
    return JSONResponse(content=exp)


@router.get("/active/datasets", tags=["experiment"])
async def get_active_experiment_datasets():
    """Return the dataset_ids of the currently published experiment."""
    experiments = dbc.get_query_db("Experiment", query={"status": "published"})
    if not experiments:
        raise HTTPException(status_code=404, detail="No published experiment found.")
    exp = experiments[0]
    dataset_ids = exp.get("dataset_ids", [])
    datasets = []
    for did in dataset_ids:
        doc = dbc.get_document("DatasetPair", {"dataset_id": did})
        if doc:
            datasets.append({
                "dataset_id":    doc["dataset_id"],
                "dataset_title": doc["dataset_title"],
            })
    return JSONResponse(content=datasets)
