import uuid
import io
import csv
import pathlib as pl
from typing import List

from fastapi import APIRouter, BackgroundTasks, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
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


def _csv_download(collection_name: str, download_filename: str):
    data = dbc.get_query_db(collection_name, query={})
    output = io.StringIO()
    writer = csv.writer(output)
    if data:
        writer.writerow(data[0].keys())
    for item in data:
        writer.writerow(item.values())
    output.seek(0)
    response = StreamingResponse(output, media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={download_filename}"
    return response


@router.get("/users", tags=["admin"])
async def get_users_data_from_db():
    return _csv_download("DfgUser", "user_collection_data.csv")


@router.get("/answers", tags=["admin"])
async def get_answers_from_db():
    return _csv_download("Answer", "answer_collection_data.csv")


@router.get("/uitracking", tags=["admin"])
async def get_ui_tracking_from_db():
    return _csv_download("UILogging", "ui_logging_collection_data.csv")


@router.get("/usagedataset", tags=["admin"])
async def get_users_usage_of_datasets():
    users = dbc.get_query_db("DfgUser", query={})
    dataset_usage_count = {}
    for user in users:
        dataset_usage_count[user["dataset_id"]] = dataset_usage_count.get(user["dataset_id"], 0) + 1
    return dataset_usage_count


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
