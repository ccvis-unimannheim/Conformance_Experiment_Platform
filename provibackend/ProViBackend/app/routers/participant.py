from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from bson import ObjectId
import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.config as config


def _get_doc_by_id(collection: str, id_str: str) -> dict | None:
    """Look up a document by _id, trying both string and ObjectId formats."""
    doc = dbc.get_document(collection, {"_id": id_str})
    if doc:
        return doc
    try:
        doc = dbc.get_document(collection, {"_id": ObjectId(id_str)})
    except Exception:
        pass
    return doc

router = APIRouter(prefix="/participant")


def _get_or_sync_active() -> dict | None:
    """Return active ParticipantExperiment, auto-syncing from Experiment if missing."""
    exp = dbc.get_document("ParticipantExperiment", {"status": "active"})
    if exp:
        return exp

    # Fallback: sync from published Experiment directly
    published = dbc.get_document("Experiment", {"status": "published"})
    if not published:
        return None

    exp_id = published.get("_id")
    if exp_id and not isinstance(exp_id, str):
        exp_id = str(exp_id)

    task_assignments = []
    for tc in published.get("task_configs", []):
        task_doc = _get_doc_by_id("Task", tc["task_id"])
        idiom_doc = _get_doc_by_id("Idiom", tc["idiom_id"])
        task_key = task_doc["task_key"] if task_doc else None
        idiom_key = idiom_doc["idiom_key"] if idiom_doc else None
        svg_path = (
            f"output/{tc['dataset_id']}/{task_key}/{idiom_key}.svg"
            if task_key and idiom_key else None
        )
        task_assignments.append({
            "dataset_id": tc["dataset_id"],
            "task_id": tc["task_id"],
            "idiom_id": tc["idiom_id"],
            "svg_path": svg_path,
        })

    db = dbc.connect_to_database()
    db["ParticipantExperiment"].replace_one(
        {"_id": exp_id},
        {"_id": exp_id, "experiment_id": exp_id, "status": "active", "task_assignments": task_assignments},
        upsert=True,
    )
    return dbc.get_document("ParticipantExperiment", {"status": "active"})


@router.get("/debug", tags=["participant"])
async def debug_sync():
    step1 = dbc.get_document("ParticipantExperiment", {"status": "active"})
    step2 = dbc.get_document("Experiment", {"status": "published"})
    exp_id = None
    write_result = None
    if step2:
        exp_id = step2.get("_id")
        if exp_id and not isinstance(exp_id, str):
            exp_id = str(exp_id)
        try:
            db = dbc.connect_to_database()
            r = db["ParticipantExperiment"].replace_one(
                {"_id": exp_id},
                {"_id": exp_id, "experiment_id": exp_id, "status": "active", "task_assignments": []},
                upsert=True,
            )
            write_result = {"matched": r.matched_count, "modified": r.modified_count, "upserted_id": str(r.upserted_id)}
        except Exception as e:
            write_result = {"error": str(e)}
    step3 = dbc.get_document("ParticipantExperiment", {"status": "active"})
    return {
        "step1_participant_exp": str(step1) if step1 else None,
        "step2_published_exp_id": exp_id,
        "step2_found": step2 is not None,
        "write_result": write_result,
        "step3_after_write": str(step3) if step3 else None,
    }


@router.get("/experiment/active", tags=["participant"])
async def get_active_experiment():
    """Return the active participant experiment with UUID-based task assignments."""
    exp = _get_or_sync_active()
    if not exp:
        raise HTTPException(status_code=404, detail="No active experiment found.")
    if "_id" in exp and not isinstance(exp["_id"], str):
        exp["_id"] = str(exp["_id"])
    return JSONResponse(content=exp)


@router.get("/vis/{dataset_id}/{task_id}/{idiom_id}", tags=["participant"])
async def get_visualization(dataset_id: str, task_id: str, idiom_id: str):
    """Serve SVG by dataset_id / task_id (UUID) / idiom_id (UUID)."""
    exp = _get_or_sync_active()
    if not exp:
        raise HTTPException(status_code=404, detail="No active experiment found.")

    assignment = next(
        (a for a in exp.get("task_assignments", [])
         if a["dataset_id"] == dataset_id
         and a["task_id"] == task_id
         and a["idiom_id"] == idiom_id),
        None,
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="No matching visualization found.")

    svg_path = config.BASE_DIRECTORY / assignment["svg_path"]
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail=f"SVG file not found: {assignment['svg_path']}")

    return FileResponse(svg_path)
