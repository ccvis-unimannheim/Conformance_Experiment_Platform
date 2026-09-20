"""Export and import an experiment's idiom images, for reproducibility.

The export is a zip of exactly the images participants see (plus each task's
traces.json) with a manifest recording how they were produced. Importing it —
into the same experiment or a new one set up with the same tasks and idioms —
pins those images as overrides (utils/idiom_files), so they keep being shown
even if the generator code changes and the experiment is regenerated. Single
images can be replaced the same way, e.g. with an edited or hand-made figure.

Zip layout, matched by task_key and idiom_key (never by experiment id):
    manifest.json               (required on import: it is what the checks read)
    <task_key>/<idiom_key>.svg  (or .png / .jpg / .jpeg)
    <task_key>/traces.json      (only tasks that show "given traces")

An import runs in one of two modes, and every task is checked before any of its
files is taken:
    specify   the images arrive together with the parameters they were drawn
              with, which replace this experiment's (reproducing a study).
    overview  this experiment's parameters stay; a task whose parameters differ
              from the zip's is rejected (swapping in images for a set-up task).
In both, a task exported from a different dataset is rejected. Imported tasks
are marked `images_imported_from`, which locks their parameters (see
admin._keep_imported_parameters) until the import is reverted.
"""
import datetime
import io
import json
import os
import re
import uuid
import zipfile
from typing import Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

import ProViBackend.app.datamodels.data_schemas as ds
import ProViBackend.utils.database.connection as dbc
from ProViBackend.app.task_wording import effective_wording
from ProViBackend.app.routers.admin import _entry_applies
from ProViBackend.scripts.tasks import task_registry
from ProViBackend.utils import idiom_files
from ProViBackend.utils.database.migration import task_instances_to_configs

router = APIRouter(prefix="/admin")

BUNDLE_FORMAT = "procon-idiom-bundle"
# 2: each task records its dataset's title and file checksums, so an import on
#    another server can tell the same dataset from a different one.
# 3: each task also records its wording and answer shape, and each idiom its
#    label and type, so POST /experiments/from-bundle can rebuild a whole
#    experiment — custom tasks and idioms included — on a server that has
#    never seen them.
BUNDLE_VERSION = 3
MAX_BUNDLE_BYTES = 200 * 1024 * 1024        # the uploaded zip
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # everything inside it
MAX_IMAGE_BYTES = 20 * 1024 * 1024          # one image


def _get_experiment(experiment_id: str) -> dict:
    exp = dbc.get_document("Experiment", {"_id": experiment_id})
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return exp


def _require_revertible(exp: dict) -> None:
    """Reverting shows the generated image again — a bundle experiment has none,
    so its uploaded image is the only one there is."""
    if exp.get("bundle_only"):
        raise HTTPException(status_code=409, detail=(
            "This experiment's images come from an uploaded bundle; there is no generated "
            "image to revert to. Replace the image instead, or remove the idiom on the "
            "Select Idiom step."
        ))


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

    custom_by_id = {t.get("_id"): t for t in exp.get("custom_tasks") or []}

    out = []
    for ti in exp.get("task_instances") or []:
        task_id = ti.get("task_id")
        task = dbc.get_task(task_id) or custom_by_id.get(task_id) or {}
        task_key = ti.get("task_key") or task.get("task_key")
        if not task_key:
            continue
        idioms = []
        for iid in ti.get("idiom_ids") or idiom_ids_by_task.get(task_id, []):
            idiom = dbc.get_document("Idiom", {"_id": iid})
            if idiom:
                idioms.append(idiom)
        wording = effective_wording(exp, task_id or "", task, ti)
        out.append({
            "task_id": task_id,
            "task_key": task_key,
            "label": wording["label"],
            "description": wording["description"],
            "answer_type": wording["answer_type"],
            "is_custom": task_id in custom_by_id,
            "dataset_id": ti.get("dataset_id") or "",
            "parameters": ti.get("parameters") or {},
            "answer_format": ti.get("answer_format"),
            "number_kind": ti.get("number_kind"),
            "answer_options": ti.get("answer_options") or [],
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


def _dataset_info(dataset_id: str) -> dict:
    """Title and file checksums of a dataset, as recorded in the manifest."""
    pair = dbc.get_document("DatasetPair", {"dataset_id": dataset_id}) if dataset_id else None
    pair = pair or {}
    return {
        "id": dataset_id or None,
        "title": pair.get("dataset_title"),
        "log_checksum": (pair.get("log") or {}).get("checksum"),
        "guideline_checksum": (pair.get("guideline") or {}).get("checksum"),
    }


def _dataset_mismatch(zip_task: dict, dataset_id: str) -> str | None:
    """Why this zip task's images cannot come from this dataset, or None.

    Checksums identify the dataset across servers; a version-1 manifest has
    none, so it has to name the very same dataset id.
    """
    theirs = zip_task.get("dataset") or {}
    ours = _dataset_info(dataset_id)
    if theirs.get("log_checksum") and ours["log_checksum"]:
        same = (theirs["log_checksum"] == ours["log_checksum"]
                and theirs.get("guideline_checksum") == ours["guideline_checksum"])
    else:
        same = bool(zip_task.get("dataset_id")) and zip_task.get("dataset_id") == dataset_id
    if same:
        return None
    zip_name = theirs.get("title") or zip_task.get("dataset_id") or "unknown"
    our_name = ours["title"] or dataset_id or "none"
    return f'Exported from a different dataset (zip: "{zip_name}", this experiment: "{our_name}").'


def _normalize_param(value):
    """Make two stored values of one parameter comparable: empty is empty
    whatever its type, numbers compare by value, multi-selects ignore order."""
    if value is None or (isinstance(value, (str, list, tuple, dict)) and len(value) == 0):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)):
        return tuple(sorted(str(v) for v in value))
    return value


def _show_param(value) -> str:
    if _normalize_param(value) is None:
        return "(empty)"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _parameter_differences(task_key: str, theirs: dict, ours: dict) -> list[str]:
    """Human-readable differences between two parameter sets of one task.

    Missing keys take the PARAM_SPEC default, and a parameter that applies to
    neither set (see `visible_if`) is ignored: neither changes the drawing.
    """
    try:
        spec = [e for e in task_registry.get_param_spec(task_key) if e.get("key")]
    except KeyError:
        spec = []
    entries = {e["key"]: e for e in spec}
    keys = list(entries) or sorted(set(theirs) | set(ours))
    diffs = []
    for key in keys:
        entry = entries.get(key)
        if entry and not (_entry_applies(entry, theirs) or _entry_applies(entry, ours)):
            continue
        default = (entry or {}).get("default")
        a, b = theirs.get(key, default), ours.get(key, default)
        if _normalize_param(a) != _normalize_param(b):
            diffs.append(f"{key}: zip = {_show_param(a)}; this experiment = {_show_param(b)}")
    return diffs


def _clear_import_marker(experiment_id: str, task_keys: set[str] | None = None) -> None:
    """Release imported tasks (all of them when task_keys is None): their
    parameters become editable again."""
    exp = _get_experiment(experiment_id)
    key_by_task_id = {t["task_id"]: t["task_key"] for t in _layout(exp)}
    instances = exp.get("task_instances") or []
    changed = False
    for ti in instances:
        if ti.get("images_imported_from") and (
            task_keys is None or key_by_task_id.get(ti.get("task_id")) in task_keys
        ):
            ti["images_imported_from"] = None
            changed = True
    if changed:
        dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
            "task_instances": instances,
            "task_configs": task_instances_to_configs(instances),
        }})


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name or "experiment").strip("_") or "experiment"


def _open_bundle(content: bytes) -> tuple[zipfile.ZipFile, dict]:
    """The uploaded zip and its manifest, or a 400 explaining what is wrong.

    The manifest is required: it is what every check reads, and what says which
    dataset, parameters and answer shape the images belong to.
    """
    if len(content) > MAX_BUNDLE_BYTES:
        raise HTTPException(status_code=400, detail="The zip must be 200 MB or smaller.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid zip.")
    if sum(i.file_size for i in zf.infolist()) > MAX_UNCOMPRESSED_BYTES:
        raise HTTPException(status_code=400, detail="The zip's contents are too large (over 500 MB).")

    manifest = None
    if "manifest.json" in zf.namelist():
        try:
            manifest = json.loads(zf.read("manifest.json"))
        except (ValueError, UnicodeDecodeError):
            manifest = None
    if not isinstance(manifest, dict) or not isinstance(manifest.get("tasks"), list):
        raise HTTPException(status_code=400, detail=(
            "The zip has no readable manifest.json, so the dataset and parameters its images "
            "were drawn from cannot be checked. Import a zip downloaded from this platform, "
            "or replace single images on the Overview page."
        ))
    return zf, manifest


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
    datasets: dict[str, dict] = {}

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in _layout(exp):
            task_key, dataset_id = entry["task_key"], entry["dataset_id"]
            if dataset_id not in datasets:
                datasets[dataset_id] = _dataset_info(dataset_id)
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
                    # Enough to recreate the Idiom document on a server that has
                    # never seen this (custom) idiom.
                    "is_custom": bool(idiom.get("is_custom")),
                    "granularity": idiom.get("granularity"),
                    "renderer_type": idiom.get("renderer_type"),
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
                "description": entry["description"],
                "answer_type": entry["answer_type"],
                "is_custom": entry["is_custom"],
                "dataset_id": dataset_id,
                "dataset": datasets[dataset_id],
                "parameters": entry["parameters"],
                # The answer shape the admin configured on /answer-format, so a
                # rebuilt experiment does not have to be set up a second time.
                "answer_format": entry["answer_format"],
                "number_kind": entry["number_kind"],
                "answer_options": entry["answer_options"],
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
async def import_experiment_idioms(
    experiment_id: str,
    file: UploadFile,
    mode: Literal["specify", "overview"] = "overview",
):
    """Pin the images of an idiom bundle zip onto this experiment.

    Each task in the zip is checked first (see the module docstring for the
    two modes): a task from another dataset, or in overview mode with other
    parameters, is rejected whole. Files are then matched by
    <task_key>/<idiom_key>. Everything not taken is reported back as rejected
    with its reason; nothing is written unless at least one file is taken.
    """
    try:
        exp = _get_experiment(experiment_id)
        _require_draft(exp)
        content = await file.read()
    finally:
        await file.close()
    zf, manifest = _open_bundle(content)
    layout = _layout(exp)
    zip_tasks = {t.get("task_key"): t for t in manifest["tasks"] if isinstance(t, dict)}

    # Whole-task checks, once per task: why every file of it is rejected, or None.
    verdicts: dict[str, str | None] = {}
    dataset_mismatch = False

    def task_rejection(task: dict) -> str | None:
        nonlocal dataset_mismatch
        key = task["task_key"]
        if key not in verdicts:
            zip_task = zip_tasks.get(key)
            if zip_task is None:
                verdicts[key] = "Not listed in the zip's manifest.json."
            elif reason := _dataset_mismatch(zip_task, task["dataset_id"]):
                dataset_mismatch = True
                verdicts[key] = reason
            elif mode == "overview" and (
                diffs := _parameter_differences(key, zip_task.get("parameters") or {}, task["parameters"])
            ):
                verdicts[key] = "Parameters differ from this experiment — " + "; ".join(diffs) + "."
            else:
                verdicts[key] = None
        return verdicts[key]

    images, traces, rejected = [], [], []
    seen = set()
    for info in zf.infolist():
        name = info.filename
        if info.is_dir() or name == "manifest.json" or name.startswith("__MACOSX/"):
            continue
        parts = name.split("/")
        if parts[-1].startswith("."):
            continue
        if len(parts) != 2 or any(p in ("", ".", "..") for p in parts):
            rejected.append({"file": name, "reason": "Not in <task_key>/<file> layout."})
            continue
        task_key, fname = parts
        task = _find_task(layout, task_key)
        if task is None:
            rejected.append({"file": name, "reason": f"Task '{task_key}' is not in this experiment."})
            continue
        if reason := task_rejection(task):
            rejected.append({"file": name, "reason": reason})
            continue
        if info.file_size > MAX_IMAGE_BYTES:
            rejected.append({"file": name, "reason": "File is larger than 20 MB."})
            continue
        if fname == idiom_files.TRACES_FILENAME:
            try:
                parsed = json.loads(zf.read(info))
                if not isinstance(parsed.get("traces"), list):
                    raise ValueError
            except (ValueError, UnicodeDecodeError, AttributeError):
                rejected.append({"file": name, "reason": "traces.json is not in the expected format."})
                continue
            traces.append((task_key, zf.read(info)))
            continue
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in idiom_files.IMAGE_EXTENSIONS:
            rejected.append({"file": name, "reason": "Unsupported file type (use SVG, PNG or JPG)."})
            continue
        if not any(i["idiom_key"] == stem for i in task["idioms"]):
            rejected.append({"file": name, "reason": f"Idiom '{stem}' is not selected for {task_key} in this experiment."})
            continue
        if (task_key, stem) in seen:
            rejected.append({"file": name, "reason": "Another file for the same idiom is already in the zip."})
            continue
        seen.add((task_key, stem))
        images.append((task_key, stem, ext.lower(), zf.read(info)))

    if not images and not traces:
        raise HTTPException(status_code=400, detail={
            "message": "Nothing in the zip could be imported into this experiment.",
            "rejected": rejected,
            "dataset_mismatch": dataset_mismatch,
        })

    for task_key, idiom_key, ext, data in images:
        idiom_files.write_override(experiment_id, task_key, idiom_key, ext, data)
    for task_key, data in traces:
        target = idiom_files.override_dir(experiment_id, task_key)
        target.mkdir(parents=True, exist_ok=True)
        (target / idiom_files.TRACES_FILENAME).write_bytes(data)

    # Mark the imported tasks, which locks their parameters; in specify mode
    # those become the zip's, in overview mode they already equal them.
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    source = manifest.get("experiment") or {}
    origin = {
        "file": file.filename,
        "experiment_id": source.get("id"),
        "experiment_name": source.get("name"),
        "exported_at": manifest.get("exported_at"),
        "imported_at": now,
    }
    imported_keys = {t for t, *_ in images} | {t for t, _ in traces}
    key_by_task_id = {t["task_id"]: t["task_key"] for t in layout}
    instances = exp.get("task_instances") or []
    for ti in instances:
        key = key_by_task_id.get(ti.get("task_id"))
        if key in imported_keys:
            ti["images_imported_from"] = origin
            if mode == "specify":
                ti["parameters"] = zip_tasks[key].get("parameters") or {}
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "task_instances": instances,
        "task_configs": task_instances_to_configs(instances),
        "idioms_imported_at": now,
        "idioms_imported_from": {k: v for k, v in origin.items() if k != "imported_at"},
    }})
    _refresh_generation_status(experiment_id, imported_keys)

    return JSONResponse(content={
        "message": f"Imported {len(images)} image(s).",
        "imported": [f"{t}/{i}{e}" for t, i, e, _ in images] + [f"{t}/{idiom_files.TRACES_FILENAME}" for t, _ in traces],
        "rejected": rejected,
        "dataset_mismatch": dataset_mismatch,
    })


# ---------------------------------------------------------------------------
# A whole experiment from a bundle
# ---------------------------------------------------------------------------

def _bundle_payload(zf: zipfile.ZipFile) -> tuple[dict, list[dict]]:
    """What the zip holds, per task: {task_key: {images: [...], traces: bytes}}.

    Only the layout is checked here — which task a file belongs to, that it is
    an image, that it is not oversized. There is no experiment to check it
    against yet: this zip *is* the experiment.
    """
    by_task: dict[str, dict] = {}
    rejected: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for info in zf.infolist():
        name = info.filename
        if info.is_dir() or name == "manifest.json" or name.startswith("__MACOSX/"):
            continue
        parts = name.split("/")
        if parts[-1].startswith("."):
            continue
        if len(parts) != 2 or any(p in ("", ".", "..") for p in parts):
            rejected.append({"file": name, "reason": "Not in <task_key>/<file> layout."})
            continue
        task_key, fname = parts
        if info.file_size > MAX_IMAGE_BYTES:
            rejected.append({"file": name, "reason": "File is larger than 20 MB."})
            continue
        entry = by_task.setdefault(task_key, {"images": [], "traces": None})
        if fname == idiom_files.TRACES_FILENAME:
            try:
                parsed = json.loads(zf.read(info))
                if not isinstance(parsed.get("traces"), list):
                    raise ValueError
            except (ValueError, UnicodeDecodeError, AttributeError):
                rejected.append({"file": name, "reason": "traces.json is not in the expected format."})
                continue
            entry["traces"] = zf.read(info)
            continue
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in idiom_files.IMAGE_EXTENSIONS:
            rejected.append({"file": name, "reason": "Unsupported file type (use SVG, PNG or JPG)."})
            continue
        if (task_key, stem) in seen:
            rejected.append({"file": name, "reason": "Another file for the same idiom is already in the zip."})
            continue
        seen.add((task_key, stem))
        entry["images"].append({"idiom_key": stem, "ext": ext.lower(), "data": zf.read(info)})
    return by_task, rejected


def _resolve_bundle_task(zip_task: dict, task_key: str) -> tuple[str, dict | None, dict | None]:
    """The task id this bundle task becomes, plus a custom task and a wording
    override to record.

    A built-in task keeps the question bank's id, so the experiment reads the
    bank as any other experiment does; the zip's wording, if it differs, is
    stored as this experiment's own (task_overrides). A task the bank does not
    have — a custom task from the experiment it was exported from — is
    recreated on this experiment under the zip's task_key, because that key is
    what its image files are named after.
    """
    task = dbc.get_document("Task", {"task_key": task_key})
    label = (zip_task.get("label") or "").strip()
    description = (zip_task.get("description") or "").strip()
    answer_type = zip_task.get("answer_type") or "text"
    if task:
        override = None
        if label and label != task.get("label"):
            override = {"label": label, "description": description, "answer_type": answer_type}
        return task["_id"], None, override
    custom = {
        "_id": str(uuid.uuid4()),
        "task_key": task_key,
        "label": label or task_key,
        "description": description,
        "answer_type": answer_type,
        "is_custom": True,
    }
    return custom["_id"], custom, None


def _resolve_bundle_idiom(idiom_key: str, zip_idiom: dict, task_key: str,
                          experiment_id: str, ext: str) -> str:
    """The Idiom document id for one image of the bundle.

    A built-in idiom key is matched to the seeded document, so the experiment
    uses the same idiom every other experiment does. A key this server does not
    know — a custom idiom, or one from another install — becomes a document
    scoped to this experiment, listed on /idiom for it alone. Its image is the
    override written from the zip.
    """
    for doc in dbc.get_query_db("Idiom", query={"idiom_key": idiom_key}):
        if not doc.get("is_custom"):
            return doc["_id"]
        if doc.get("experiment_id") == experiment_id:
            return doc["_id"]
    idiom = ds.Idiom(
        _id=str(uuid.uuid4()),
        idiom_key=idiom_key,
        label=zip_idiom.get("label") or idiom_key,
        granularity=zip_idiom.get("granularity") or "custom",
        renderer_type=zip_idiom.get("renderer_type") or "custom-upload",
        active=True,
        is_custom=True,
        asset_ext=ext,
        task_keys=[task_key],
        experiment_id=experiment_id,
    )
    dbc.create_document("Idiom", idiom.model_dump(by_alias=True))
    return idiom.id


@router.post("/experiments/from-bundle", tags=["admin"])
async def create_experiment_from_bundle(
    file: UploadFile,
    name: str = Form(""),
    design_type: str = Form("between"),
    within_sequence_mode: str = Form("fixed"),
    created_by: str = Form("admin"),
):
    """Build a whole draft experiment from an idiom bundle zip.

    The wizard's other route picks a dataset and generates images from it; this
    one takes an experiment that already has its images. The zip decides which
    tasks it asks and which idioms each task is shown as, so there is no dataset
    to choose and nothing to generate: the experiment is marked `bundle_only`
    (see the field's comment in data_schemas.py), and every task is `ready` the
    moment it is created.

    A version-3 zip also carries each task's answer shape, so such an experiment
    can go straight to /overview and be published. An older zip has none, and
    the response says so (`needs_answer_format`) — the answer format has to be
    chosen before publishing, as for any other experiment.
    """
    try:
        content = await file.read()
    finally:
        await file.close()
    zf, manifest = _open_bundle(content)
    by_task, rejected = _bundle_payload(zf)

    experiment_id = str(uuid.uuid4())
    instances: list[dict] = []
    custom_tasks: list[dict] = []
    overrides: dict[str, dict] = {}
    task_overrides: dict[str, dict] = {}
    imported: list[str] = []
    needs_answer_format = False

    for zip_task in manifest["tasks"]:
        if not isinstance(zip_task, dict):
            continue
        task_key = zip_task.get("task_key")
        payload = by_task.get(task_key)
        if not task_key or not payload or not payload["images"]:
            if task_key:
                rejected.append({"file": f"{task_key}/", "reason": "No image in the zip for this task."})
            continue

        task_id, custom_task, wording = _resolve_bundle_task(zip_task, task_key)
        if custom_task:
            custom_tasks.append(custom_task)
        if wording:
            task_overrides[task_id] = wording

        # Idiom order follows the manifest; a file the manifest does not list is
        # still taken, after the ones it does.
        listed = [i.get("idiom_key") for i in zip_task.get("idioms") or [] if isinstance(i, dict)]
        images = sorted(payload["images"],
                        key=lambda im: (listed.index(im["idiom_key"]) if im["idiom_key"] in listed else len(listed)))
        zip_idioms = {i.get("idiom_key"): i for i in zip_task.get("idioms") or [] if isinstance(i, dict)}

        idiom_ids = []
        for image in images:
            idiom_ids.append(_resolve_bundle_idiom(
                image["idiom_key"], zip_idioms.get(image["idiom_key"]) or {},
                task_key, experiment_id, image["ext"],
            ))
            imported.append(f"{task_key}/{image['idiom_key']}{image['ext']}")
        if payload["traces"]:
            imported.append(f"{task_key}/{idiom_files.TRACES_FILENAME}")

        answer_format = zip_task.get("answer_format")
        if not answer_format:
            needs_answer_format = True
        instances.append({
            "task_id": task_id,
            "dataset_id": idiom_files.BUNDLE_DATASET_ID,
            "idiom_ids": idiom_ids,
            "parameters": zip_task.get("parameters") or {},
            "answer_format": answer_format,
            "number_kind": zip_task.get("number_kind"),
            "answer_options": zip_task.get("answer_options") or [],
            # Nothing is ever generated for these: the images are already here.
            "generation_status": "ready",
            "generation_error": None,
            "images_imported_from": None,  # filled in below, once the origin is built
            "question_ids": [],
            "task_key": task_key,
        })
        overrides[task_key] = payload

    if not instances:
        raise HTTPException(status_code=400, detail={
            "message": "No task in the zip could be turned into an experiment.",
            "rejected": rejected,
        })

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    source = manifest.get("experiment") or {}
    origin = {
        "file": file.filename,
        "experiment_id": source.get("id"),
        "experiment_name": source.get("name"),
        "exported_at": manifest.get("exported_at"),
        "imported_at": now,
    }
    for inst in instances:
        inst["images_imported_from"] = origin

    for task_key, payload in overrides.items():
        for image in payload["images"]:
            idiom_files.write_override(experiment_id, task_key, image["idiom_key"],
                                       image["ext"], image["data"])
        if payload["traces"]:
            target = idiom_files.override_dir(experiment_id, task_key)
            target.mkdir(parents=True, exist_ok=True)
            (target / idiom_files.TRACES_FILENAME).write_bytes(payload["traces"])

    experiment = ds.Experiment(
        _id=experiment_id,
        name=(name or "").strip() or source.get("name") or "Imported experiment",
        type="CC",
        status="draft",
        design_type=design_type,
        between_factors=[],
        within_factors=[],
        stratification_fields=[],
        between_balance_mode="random",
        within_sequence_mode=within_sequence_mode,
        dataset_ids=[],
        task_instances=[ds.TaskInstance(**inst) for inst in instances],
        task_configs=[ds.TaskConfig(**tc) for tc in task_instances_to_configs(instances)],
        task_overrides=task_overrides,
        custom_tasks=custom_tasks,
        bundle_only=True,
        current_step="overview",
        created_by=created_by,
        created_at=now,
    )
    doc = experiment.model_dump(by_alias=True)
    doc["idioms_imported_at"] = now
    doc["idioms_imported_from"] = {k: v for k, v in origin.items() if k != "imported_at"}
    dbc.create_document("Experiment", doc)

    return JSONResponse(status_code=201, content={
        "message": f"Created an experiment with {len(instances)} task(s) from the zip.",
        "experiment_id": experiment_id,
        "tasks": len(instances),
        "imported": imported,
        "rejected": rejected,
        "needs_answer_format": needs_answer_format,
    })


@router.post("/experiments/{experiment_id}/discard-bundle", tags=["admin"])
async def discard_bundle(experiment_id: str):
    """Undo a bundle upload, leaving an empty draft that can take a dataset.

    The zip supplied this experiment's tasks, idioms and images; undoing it has
    to take all three, since a task from the zip has no generator to fall back
    on and an idiom recreated from it has no image but the one being removed.
    What survives is what the admin typed: the name, the design and the task
    order. The experiment stops being `bundle_only`, so /new offers the dataset
    table again and the wizard runs as it does for any other experiment.
    """
    exp = _get_experiment(experiment_id)
    _require_draft(exp)
    if not exp.get("bundle_only"):
        raise HTTPException(status_code=409, detail="This experiment was not built from a bundle.")

    idiom_files.remove_all_overrides(experiment_id)
    db = dbc.connect_to_database()
    # Idiom documents that exist only for this experiment (recreated from the
    # zip): nothing else can reach them, and their image has just gone.
    db["Idiom"].delete_many({"is_custom": True, "experiment_id": experiment_id})
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "bundle_only": False,
        "dataset_ids": [],
        "task_instances": [],
        "task_configs": [],
        "custom_tasks": [],
        "idioms_imported_at": None,
        "idioms_imported_from": None,
        "current_step": "new",
    }})
    return JSONResponse(content={
        "message": "The uploaded images were discarded. Choose a dataset to set this experiment up.",
        "experiment_id": experiment_id,
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
    """Drop every uploaded/imported image; the generated ones show again, and
    imported tasks' parameters become editable."""
    exp = _get_experiment(experiment_id)
    _require_draft(exp)
    _require_revertible(exp)
    task_keys = {o["task_key"] for o in idiom_files.list_overrides(experiment_id)}
    idiom_files.remove_all_overrides(experiment_id)
    dbc.update_document("Experiment", {"_id": experiment_id}, {"$set": {
        "idioms_imported_at": None,
        "idioms_imported_from": None,
    }})
    _clear_import_marker(experiment_id)
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
    """Drop the uploaded image of one idiom; the generated one shows again.
    Once a task has no uploaded image left, its parameters become editable."""
    exp = _get_experiment(experiment_id)
    _require_draft(exp)
    _require_revertible(exp)
    if not idiom_files.remove_override(experiment_id, task_key, idiom_key):
        raise HTTPException(status_code=404, detail="No uploaded image for this idiom.")
    if not any(o["task_key"] == task_key for o in idiom_files.list_overrides(experiment_id)):
        _clear_import_marker(experiment_id, {task_key})
    _refresh_generation_status(experiment_id, {task_key})
    return JSONResponse(content={"message": "Reverted to the generated image."})
