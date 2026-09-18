"""Export and import an experiment's idiom images, for reproducibility.

The export is a zip of exactly the images participants see (plus each task's
traces.json) with a manifest recording how they were produced. Importing it —
into the same experiment or a new one set up with the same tasks and idioms —
pins those images as overrides (utils/idiom_files), so they keep being shown
even if the generator code changes and the experiment is regenerated. Single
images can be replaced the same way, e.g. with an edited or hand-made figure.

Zip layout, matched by task_key and idiom_key (never by experiment id):
    manifest.json               (optional on import)
    <task_key>/<idiom_key>.svg  (or .png / .jpg / .jpeg)
    <task_key>/traces.json      (only tasks that show "given traces")
"""
import datetime
import io
import json
import os
import re
import zipfile

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

import ProViBackend.utils.database.connection as dbc
from ProViBackend.utils import idiom_files
from ProViBackend.utils.database.migration import task_instances_to_configs

router = APIRouter(prefix="/admin")

BUNDLE_FORMAT = "procon-idiom-bundle"
BUNDLE_VERSION = 1
MAX_BUNDLE_BYTES = 200 * 1024 * 1024        # the uploaded zip
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # everything inside it
MAX_IMAGE_BYTES = 20 * 1024 * 1024          # one image


def _get_experiment(experiment_id: str) -> dict:
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return exp


def _require_draft(exp: dict) -> None:
    # Swapping images under a running study would show participants different
    # stimuli partway through, which is exactly what this feature guards against.
    if exp.get("status", "draft") != "draft":
        raise HTTPException(
            status_code=409,
            detail="Images can only be changed while the experiment is a draft.",
        )


def _layout(exp: dict) -> list[dict]:
    """One entry per task of the experiment: its key, dataset, parameters and
    the Idiom documents selected for it, in the experiment's order."""
    idiom_ids_by_task: dict[str, list[str]] = {}
    for tc in exp.get("task_configs") or []:
        if tc.get("idiom_id"):
            idiom_ids_by_task.setdefault(tc["task_id"], []).append(tc["idiom_id"])

    out = []
    for ti in exp.get("task_instances") or []:
        task = dbc.get_task(ti.get("task_id")) or {}
        task_key = ti.get("task_key") or task.get("task_key")
        if not task_key:
            continue
        idioms = []
        for iid in ti.get("idiom_ids") or idiom_ids_by_task.get(ti.get("task_id"), []):
            idiom = dbc.get_document("Idiom", {"_id": iid})
            if idiom:
                idioms.append(idiom)
        out.append({
            "task_id": ti.get("task_id"),
            "task_key": task_key,
            "label": ti.get("label") or task.get("label"),
            "dataset_id": ti.get("dataset_id") or "",
            "parameters": ti.get("parameters") or {},
            "idioms": idioms,
        })
    return out


def _find_task(layout: list[dict], task_key: str) -> dict | None:
    return next((t for t in layout if t["task_key"] == task_key), None)


def _refresh_generation_status(experiment_id: str, task_keys: set[str]) -> None:
    """Mark the given tasks ready when every selected idiom now has an image,
    and pending when one went missing (e.g. an upload was reverted before the
    task was ever generated), so publishing stays blocked until it's fixed."""
    def has_image(entry: dict, idiom: dict) -> bool:
        path, _ = idiom_files.resolve_idiom_image(entry["dataset_id"], experiment_id, entry["task_key"], idiom)
        return path is not None and path.exists()

    exp = _get_experiment(experiment_id)
    by_task_id = {t["task_id"]: t for t in _layout(exp)}
    instances = exp.get("task_instances") or []
    changed = False
    for ti in instances:
        entry = by_task_id.get(ti.get("task_id"))
        if not entry or entry["task_key"] not in task_keys or ti.get("generation_status") == "running":
            continue
        complete = bool(entry["idioms"]) and all(has_image(entry, i) for i in entry["idioms"])
        if complete and ti.get("generation_status") != "ready":
            ti["generation_status"], ti["generation_error"] = "ready", None
            changed = True
        elif not complete and ti.get("generation_status") == "ready":
            ti["generation_status"] = "pending"
            ti["generation_error"] = "Some idiom images are missing — generate or upload them."
            changed = True
    if changed:
        dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
            "task_instances": instances,
            "task_configs": task_instances_to_configs(instances),
        }})


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name or "experiment").strip("_") or "experiment"


def _image_ext(filename: str | None) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in idiom_files.IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type '{ext or '(none)'}'. Use SVG, PNG or JPG.",
        )
    return ext


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@router.get("/experiments/{experiment_id}/idioms/export", tags=["admin"])
async def export_experiment_idioms(experiment_id: str):
    """Zip of every image participants of this experiment see, plus manifest."""
    exp = _get_experiment(experiment_id)
    buf = io.BytesIO()
    manifest_tasks, missing = [], []

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in _layout(exp):
            task_key, dataset_id = entry["task_key"], entry["dataset_id"]
            idioms_out = []
            for idiom in entry["idioms"]:
                path, source = idiom_files.resolve_idiom_image(dataset_id, experiment_id, task_key, idiom)
                if path is None or not path.exists():
                    missing.append(f"{task_key}/{idiom['idiom_key']}")
                    continue
                arcname = f"{task_key}/{idiom['idiom_key']}{path.suffix.lower()}"
                zf.write(path, arcname)
                idioms_out.append({
                    "idiom_key": idiom["idiom_key"],
                    "label": idiom.get("label"),
                    "file": arcname,
                    "source": source,  # uploaded | custom | generated | legacy
                })
            traces = idiom_files.resolve_traces(dataset_id, experiment_id, task_key)
            traces_file = None
            if traces is not None and traces.exists():
                traces_file = f"{task_key}/{idiom_files.TRACES_FILENAME}"
                zf.write(traces, traces_file)
            manifest_tasks.append({
                "task_key": task_key,
                "label": entry["label"],
                "dataset_id": dataset_id,
                "parameters": entry["parameters"],
                "idioms": idioms_out,
                "traces_file": traces_file,
            })

        manifest = {
            "format": BUNDLE_FORMAT,
            "version": BUNDLE_VERSION,
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            # Set GIT_COMMIT in the backend's environment to record which
            # generator code drew the "generated" images.
            "git_commit": os.environ.get("GIT_COMMIT"),
            "experiment": {"id": experiment_id, "name": exp.get("name")},
            "tasks": manifest_tasks,
            "missing": missing,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    buf.seek(0)
    date = datetime.date.today().isoformat()
    filename = f"{_safe_filename(exp.get('name'))}_idioms_{date}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@router.post("/experiments/{experiment_id}/idioms/import", tags=["admin"])
async def import_experiment_idioms(experiment_id: str, file: UploadFile):
    """Pin the images of an idiom bundle zip onto this experiment.

    Files are matched by <task_key>/<idiom_key>; anything that doesn't match a
    task and idiom selected in this experiment is reported back as skipped.
    Nothing is written unless at least one file matches.
    """
    try:
        exp = _get_experiment(experiment_id)
        _require_draft(exp)
        content = await file.read()
    finally:
        await file.close()
    if len(content) > MAX_BUNDLE_BYTES:
        raise HTTPException(status_code=400, detail="The zip must be 200 MB or smaller.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid zip.")
    if sum(i.file_size for i in zf.infolist()) > MAX_UNCOMPRESSED_BYTES:
        raise HTTPException(status_code=400, detail="The zip's contents are too large (over 500 MB).")

    layout = _layout(exp)
    manifest = {}
    if "manifest.json" in zf.namelist():
        try:
            manifest = json.loads(zf.read("manifest.json"))
        except (ValueError, UnicodeDecodeError):
            manifest = {}

    images, traces, skipped = [], [], []
    seen = set()
    for info in zf.infolist():
        name = info.filename
        if info.is_dir() or name == "manifest.json" or name.startswith("__MACOSX/"):
            continue
        parts = name.split("/")
        if parts[-1].startswith("."):
            continue
        if len(parts) != 2 or any(p in ("", ".", "..") for p in parts):
            skipped.append({"file": name, "reason": "Not in <task_key>/<file> layout."})
            continue
        task_key, fname = parts
        task = _find_task(layout, task_key)
        if task is None:
            skipped.append({"file": name, "reason": f"Task '{task_key}' is not in this experiment."})
            continue
        if info.file_size > MAX_IMAGE_BYTES:
            skipped.append({"file": name, "reason": "File is larger than 20 MB."})
            continue
        if fname == idiom_files.TRACES_FILENAME:
            try:
                parsed = json.loads(zf.read(info))
                if not isinstance(parsed.get("traces"), list):
                    raise ValueError
            except (ValueError, UnicodeDecodeError, AttributeError):
                skipped.append({"file": name, "reason": "traces.json is not in the expected format."})
                continue
            traces.append((task_key, zf.read(info)))
            continue
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in idiom_files.IMAGE_EXTENSIONS:
            skipped.append({"file": name, "reason": "Unsupported file type (use SVG, PNG or JPG)."})
            continue
        if not any(i["idiom_key"] == stem for i in task["idioms"]):
            skipped.append({"file": name, "reason": f"Idiom '{stem}' is not selected for {task_key} in this experiment."})
            continue
        if (task_key, stem) in seen:
            skipped.append({"file": name, "reason": "Another file for the same idiom is already in the zip."})
            continue
        seen.add((task_key, stem))
        images.append((task_key, stem, ext.lower(), zf.read(info)))

    if not images and not traces:
        raise HTTPException(status_code=400, detail={
            "message": "Nothing in the zip matches this experiment's tasks and idioms.",
            "skipped": skipped,
        })

    for task_key, idiom_key, ext, data in images:
        idiom_files.write_override(experiment_id, task_key, idiom_key, ext, data)
    for task_key, data in traces:
        target = idiom_files.override_dir(experiment_id, task_key)
        target.mkdir(parents=True, exist_ok=True)
        (target / idiom_files.TRACES_FILENAME).write_bytes(data)

    source = manifest.get("experiment") or {}
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "idioms_imported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "idioms_imported_from": {
            "file": file.filename,
            "experiment_id": source.get("id"),
            "experiment_name": source.get("name"),
            "exported_at": manifest.get("exported_at"),
        },
    }})
    _refresh_generation_status(experiment_id, {t for t, *_ in images} | {t for t, _ in traces})

    return JSONResponse(content={
        "message": f"Imported {len(images)} image(s).",
        "imported": [f"{t}/{i}{e}" for t, i, e, _ in images] + [f"{t}/{idiom_files.TRACES_FILENAME}" for t, _ in traces],
        "skipped": skipped,
    })


# ---------------------------------------------------------------------------
# Single-image replacements
# ---------------------------------------------------------------------------

@router.get("/experiments/{experiment_id}/idioms/overrides", tags=["admin"])
async def list_idiom_overrides(experiment_id: str):
    exp = _get_experiment(experiment_id)
    return JSONResponse(content={
        "overrides": idiom_files.list_overrides(experiment_id),
        "imported_at": exp.get("idioms_imported_at"),
        "imported_from": exp.get("idioms_imported_from"),
    })


@router.delete("/experiments/{experiment_id}/idioms/overrides", tags=["admin"])
async def revert_all_idiom_overrides(experiment_id: str):
    """Drop every uploaded/imported image; the generated ones show again."""
    exp = _get_experiment(experiment_id)
    _require_draft(exp)
    task_keys = {o["task_key"] for o in idiom_files.list_overrides(experiment_id)}
    idiom_files.remove_all_overrides(experiment_id)
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "idioms_imported_at": None,
        "idioms_imported_from": None,
    }})
    _refresh_generation_status(experiment_id, task_keys)
    return JSONResponse(content={"message": "All uploaded images reverted."})


@router.post("/experiments/{experiment_id}/idioms/{task_key}/{idiom_key}", tags=["admin"])
async def replace_idiom_image(experiment_id: str, task_key: str, idiom_key: str, file: UploadFile):
    """Replace the image of one idiom of one task in this experiment."""
    try:
        exp = _get_experiment(experiment_id)
        _require_draft(exp)
        task = _find_task(_layout(exp), task_key)
        if task is None or not any(i["idiom_key"] == idiom_key for i in task["idioms"]):
            raise HTTPException(status_code=404, detail=f"{task_key}/{idiom_key} is not part of this experiment.")
        ext = _image_ext(file.filename)
        content = await file.read()
    finally:
        await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image must be 20 MB or smaller.")
    idiom_files.write_override(experiment_id, task_key, idiom_key, ext, content)
    _refresh_generation_status(experiment_id, {task_key})
    return JSONResponse(content={"message": "Image replaced.", "ext": ext}, status_code=201)


@router.delete("/experiments/{experiment_id}/idioms/{task_key}/{idiom_key}", tags=["admin"])
async def revert_idiom_image(experiment_id: str, task_key: str, idiom_key: str):
    """Drop the uploaded image of one idiom; the generated one shows again."""
    exp = _get_experiment(experiment_id)
    _require_draft(exp)
    if not idiom_files.remove_override(experiment_id, task_key, idiom_key):
        raise HTTPException(status_code=404, detail="No uploaded image for this idiom.")
    _refresh_generation_status(experiment_id, {task_key})
    return JSONResponse(content={"message": "Reverted to the generated image."})
