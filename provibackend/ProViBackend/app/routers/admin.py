import uuid
import io
import csv
from fastapi import APIRouter, BackgroundTasks, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from ProViBackend.scripts.create_all_visualizations import create_all_visualizations
from ProViBackend.utils import config, utils
from ProViBackend.app.datamodels import data_schemas as ds
import pathlib as pl

import ProViBackend.utils.database.connection as dbc
import ProViBackend.utils.redis_handler as redis_handler

router = APIRouter(
    prefix="/admin"
)

def process_xes_file(file_path: pl.Path):
    create_all_visualizations(file_path, config.BASE_DIRECTORY / "output")
    upload_meta_xes_data_to_db(file_path)


# Todo: Add dataset_id, dataset_location and user mapping to redis when not found by redis lookup
def upload_meta_xes_data_to_db(file_path: pl.Path):
    # upload dataset to database
    dataset_id = str(uuid.uuid1())
    dataset_title = file_path.stem
    dataset_checksum = utils.get_file_checksum(file_path)
    dataset_is_active = False
    insert_datetime = utils.get_current_datetime()
    dataset_id_normal = dataset_id + "_normal"
    dataset_location_normal = f"output/{dataset_title}/normal"
    dataset_normal = ds.Dataset(dataset_id=dataset_id_normal,
                                dataset_title=dataset_title + "_normal",
                                dataset_checksum=dataset_checksum,
                                dataset_is_active=dataset_is_active,
                                dataset_location=dataset_location_normal,
                                insert_datetime=insert_datetime)

    dataset_id_mentalmap = dataset_id + "_mentalmap"
    dataset_location_mentalmap = f"output/{dataset_title}/mentalmap"
    dataset_mental = ds.Dataset(dataset_id=dataset_id_mentalmap,
                                dataset_title=dataset_title + "_mentalmap",
                                dataset_checksum=dataset_checksum,
                                dataset_is_active=dataset_is_active,
                                dataset_location=dataset_location_mentalmap,
                                insert_datetime=insert_datetime)


    # upload user to database
    dbc.create_dataset(dataset_normal)
    dbc.create_dataset(dataset_mental)

    redis_handler.write_key_to_redis(dataset_id_mentalmap, dataset_location_mentalmap)
    redis_handler.write_key_to_redis(dataset_id_normal, dataset_location_normal)


@router.post("/upload", tags=["admin"])
async def upload_xes_file(file: UploadFile, background_tasks: BackgroundTasks):
    try:
        contents = file.file.read()
        file_path = config.BASE_DIRECTORY / "output" / file.filename
        with open(utils.convert_path_to_str(file_path), 'wb') as f:
            f.write(contents)
        background_tasks.add_task(process_xes_file, file_path)
        return {"message": f"Successfully uploaded {file.filename}. File is being processed."}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload file")
    finally:
        file.file.close()


# Todo: Add validation for csv file and verify content after df structure.
@router.post("/questionnaire", tags=["admin"])
async def upload_questionnaire_data(file: UploadFile):
    try:
        contents = file.file.read()
        file_path = config.BASE_DIRECTORY / "app/static/questionnaire.csv"
        with open(utils.convert_path_to_str(file_path), 'wb') as f:
            f.write(contents)
        return {"message": f"Successfully uploaded {file.filename}"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload file")
    finally:
        file.file.close()


def generate_csv_for_download(collection_name: str):
    # download all data from database from collection
    data = dbc.get_query_db(collection_name, query={})
    output = io.StringIO()
    writer = csv.writer(output)
    # Write header
    if data:
        writer.writerow(data[0].keys())
    # Write data rows
    for item in data:
        writer.writerow(item.values())
    output.seek(0)
    return output


# Todo: If bad performance, consider using a background task/celery
@router.get("/users", tags=["admin"])
async def get_users_data_from_db():
    data = generate_csv_for_download("User")
    response = StreamingResponse(data, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=user_collection_data.csv"
    return response


@router.get("/answers", tags=["admin"])
async def get_answers_from_db():
    data = generate_csv_for_download("Answer")
    response = StreamingResponse(data, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=answer_collection_data.csv"
    return response


@router.get("/uitracking", tags=["admin"])
async def get_ui_tracking_from_db():
    data = generate_csv_for_download("UILogging")
    response = StreamingResponse(data, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=ui_logging_collection_data.csv"
    return response


@router.get("/datasets", tags=["admin"])
async def get_datasets_from_db():
    datasets = dbc.get_query_db("Dataset",
                                query={},
                                projection={"_id": 0,
                                            "dataset_id": 1,
                                            "dataset_title": 1,
                                            "dataset_is_active": 1,
                                            "dataset_location": 1,
                                            })
    return JSONResponse(content=datasets)


# Todo: Add validation for dataset_id and dataset_is_active that always two datasets are selected as active
@router.post("/datasets", tags=["admin"])
async def select_active_datasets(selected_datasets_from_frontend: ds.ListDatasetsFromFrontend):
    # update dataset_is_active in database
    for dataset in selected_datasets_from_frontend.datasets:
        dbc.update_dataset_is_active_status(dataset.dataset_id, dataset.dataset_is_active)
    return {"message": "Successfully updated dataset_is_active in database"}


@router.get("/usagedataset", tags=["admin"])
async def get_users_usage_of_datasets():
    # get all users and group count them by their assigned dataset_ids
    users = dbc.get_query_db("User", query={})
    dataset_usage_count = {}
    for user in users:
        if user["dataset_id"] in dataset_usage_count:
            dataset_usage_count[user["dataset_id"]] += 1
        else:
            dataset_usage_count[user["dataset_id"]] = 1
    return dataset_usage_count
