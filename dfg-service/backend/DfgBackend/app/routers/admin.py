import uuid
import pathlib as pl
from typing import List

from fastapi import APIRouter, BackgroundTasks, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from DfgBackend.scripts.create_all_visualizations import create_all_visualizations
from DfgBackend.utils import config, utils
import DfgBackend.utils.database.connection as dbc
import DfgBackend.utils.redis_handler as redis_handler

router = APIRouter(
    prefix="/admin"
)

# Uses its own DfgDataset collection (not the main app's Dataset/DatasetPair)
# — see auth.py for why.


def process_xes_file(file_path: pl.Path):
    create_all_visualizations(file_path, config.BASE_DIRECTORY / "output")
    _register_dataset(file_path)


def _register_dataset(file_path: pl.Path):
    dataset_id = str(uuid.uuid1())
    dataset_title = file_path.stem
    dataset_checksum = utils.get_file_checksum(file_path)
    insert_datetime = utils.get_current_datetime()

    for variant in ("normal", "mentalmap"):
        variant_id = f"{dataset_id}_{variant}"
        variant_location = f"output/{dataset_title}/{variant}"
        dbc.create_document("DfgDataset", {
            "dataset_id": variant_id,
            "dataset_title": f"{dataset_title}_{variant}",
            "dataset_checksum": dataset_checksum,
            "dataset_is_active": False,
            "dataset_location": variant_location,
            "insert_datetime": insert_datetime,
        })
        redis_handler.write_key_to_redis(variant_id, variant_location)


@router.post("/upload", tags=["admin"])
async def upload_xes_file(file: UploadFile, background_tasks: BackgroundTasks):
    try:
        contents = file.file.read()
        file_path = config.BASE_DIRECTORY / "output" / file.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(utils.convert_path_to_str(file_path), "wb") as f:
            f.write(contents)
        background_tasks.add_task(process_xes_file, file_path)
        return {"message": f"Successfully uploaded {file.filename}. File is being processed in the background — this can take a few minutes."}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload file")
    finally:
        file.file.close()


@router.post("/questionnaire", tags=["admin"])
async def upload_questionnaire_data(file: UploadFile):
    try:
        contents = file.file.read()
        file_path = config.BASE_DIRECTORY / "app/static/questionnaire.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(utils.convert_path_to_str(file_path), "wb") as f:
            f.write(contents)
        return {"message": f"Successfully uploaded {file.filename}"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload file")
    finally:
        file.file.close()


@router.get("/datasets", tags=["admin"])
async def get_datasets_from_db():
    datasets = dbc.get_query_db(
        "DfgDataset",
        query={},
        projection={"_id": 0, "dataset_id": 1, "dataset_title": 1, "dataset_is_active": 1, "dataset_location": 1},
    )
    return JSONResponse(content=datasets)


class DatasetActiveUpdate(BaseModel):
    dataset_id: str
    dataset_is_active: bool


class SelectActiveDatasetsRequest(BaseModel):
    datasets: List[DatasetActiveUpdate]


@router.post("/datasets", tags=["admin"])
async def select_active_datasets(body: SelectActiveDatasetsRequest):
    for dataset in body.datasets:
        dbc.update_document(
            "DfgDataset",
            {"dataset_id": dataset.dataset_id},
            {"$set": {"dataset_is_active": dataset.dataset_is_active}},
        )
    return {"message": "Successfully updated dataset_is_active in database"}


# Minimal, unstyled test/verification UI — a plain HTML page (no build step) so
# this pass can be verified from a browser alone. Not the polished admin
# experience; standing that up properly is future work.
_UI_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>DFG Test Admin</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 2rem auto;">
  <h2>1. Upload a .xes event log</h2>
  <input type="file" id="xesFile" accept=".xes" />
  <button onclick="uploadXes()">Upload</button>
  <p id="uploadStatus"></p>

  <h2>2. Activate a dataset</h2>
  <button onclick="loadDatasets()">Refresh list</button>
  <div id="datasetList"></div>
  <button onclick="saveActive()">Save active selection</button>
  <p id="datasetStatus"></p>

  <h2>3. Start a test session</h2>
  <button onclick="startSession()">Start session &amp; open experiment</button>
  <p id="sessionStatus"></p>

<script>
async function uploadXes() {
  const f = document.getElementById('xesFile').files[0];
  if (!f) { alert('Choose a .xes file first'); return; }
  const form = new FormData();
  form.append('file', f);
  const res = await fetch('/dfg/api/admin/upload', { method: 'POST', body: form });
  const data = await res.json();
  document.getElementById('uploadStatus').textContent = data.message || JSON.stringify(data);
}

async function loadDatasets() {
  const res = await fetch('/dfg/api/admin/datasets');
  const datasets = await res.json();
  const el = document.getElementById('datasetList');
  el.innerHTML = datasets.map(d =>
    `<label style="display:block"><input type="checkbox" data-id="${d.dataset_id}" ${d.dataset_is_active ? 'checked' : ''}/> ${d.dataset_title} (${d.dataset_id})</label>`
  ).join('') || '<em>No datasets uploaded yet.</em>';
}

async function saveActive() {
  const boxes = document.querySelectorAll('#datasetList input[type=checkbox]');
  const datasets = Array.from(boxes).map(b => ({ dataset_id: b.dataset.id, dataset_is_active: b.checked }));
  const res = await fetch('/dfg/api/admin/datasets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ datasets }),
  });
  const data = await res.json();
  document.getElementById('datasetStatus').textContent = data.message || JSON.stringify(data);
}

async function startSession() {
  const res = await fetch('/dfg/api/auth/', { method: 'POST', credentials: 'include' });
  const data = await res.json();
  document.getElementById('sessionStatus').textContent = data.message || JSON.stringify(data);
  if (res.ok) window.location.href = '/dfg/';
}

loadDatasets();
</script>
</body>
</html>"""


@router.get("/ui", tags=["admin"], response_class=HTMLResponse)
async def admin_ui():
    return _UI_HTML
