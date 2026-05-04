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


def upload_meta_xes_data_to_db(file_path: pl.Path):
    dataset_id = str(uuid.uuid1())
    dataset_title = file_path.stem
    checksum = utils.get_file_checksum(file_path)
    location = f"output/{dataset_title}"

    dataset = ds.Dataset(
        dataset_id=dataset_id,
        dataset_title=dataset_title,
        checksum=checksum,
        is_active=False,
        location=location,
    )
    dbc.create_dataset(dataset)
    redis_handler.write_key_to_redis(dataset_id, location)


# @router.post("/upload", tags=["admin"])
# async def upload_xes_file(file: UploadFile, background_tasks: BackgroundTasks):
#     try:
#         contents = file.file.read()
#         file_path = config.BASE_DIRECTORY / "output" / file.filename
#         with open(utils.convert_path_to_str(file_path), 'wb') as f:
#             f.write(contents)
#         background_tasks.add_task(process_xes_file, file_path)
#         return {"message": f"Successfully uploaded {file.filename}. File is being processed."}
#     except Exception:
#         raise HTTPException(status_code=500, detail="Failed to upload file")
#     finally:
#         file.file.close()

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


@router.post("/datasets/pair", tags=["admin"])
async def upload_dataset_pair(log: UploadFile, guideline: UploadFile):
    pair_id = str(uuid.uuid4())
    pair_dir = config.BASE_DIRECTORY / "output" / pair_id
    try:
        pair_dir.mkdir(parents=True, exist_ok=True)

        log_contents = await log.read()
        log_path = pair_dir / log.filename
        log_path.write_bytes(log_contents)

        guideline_contents = await guideline.read()
        guideline_path = pair_dir / guideline.filename
        guideline_path.write_bytes(guideline_contents)

        dataset_pair = ds.DatasetPair(
            dataset_id=pair_id,
            dataset_title=pl.Path(log.filename).stem,
            dataset_is_active=False,
            insert_datetime=utils.get_current_datetime(),
            log=ds.DatasetFile(
                filename=log.filename,
                location=str(log_path.relative_to(config.BASE_DIRECTORY)),
                checksum=utils.get_file_checksum(log_path),
            ),
            guideline=ds.DatasetFile(
                filename=guideline.filename,
                location=str(guideline_path.relative_to(config.BASE_DIRECTORY)),
                checksum=utils.get_file_checksum(guideline_path),
            ),
        )

        db = dbc.connect_to_database()
        db["DatasetPair"].insert_one(dataset_pair.model_dump())
        return {"dataset_id": pair_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload dataset pair: {str(e)}")
    finally:
        await log.close()
        await guideline.close()


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
    pairs = dbc.get_query_db("DatasetPair",
                             query={},
                             projection={"_id": 0,
                                         "dataset_id": 1,
                                         "dataset_title": 1,
                                         "dataset_is_active": 1,
                                         "insert_datetime": 1,
                                         "log.filename": 1,
                                         "guideline.filename": 1,
                                         })
    return JSONResponse(content=pairs)


# Todo: Add validation for dataset_id and dataset_is_active that always two datasets are selected as active
@router.post("/datasets", tags=["admin"])
async def select_active_datasets(selected_datasets_from_frontend: ds.ListDatasetsFromFrontend):
    # update dataset_is_active in database
    for dataset in selected_datasets_from_frontend.datasets:
        dbc.update_dataset_is_active_status(dataset.dataset_id, dataset.is_active)
    return {"message": "Successfully updated dataset_is_active in database"}


@router.get("/experiments", tags=["admin"])
async def list_experiments():
    experiments = dbc.get_query_db(
        "Experiment",
        query={},
        projection={
            "_id": 0,
            "experiment_id": 1,
            "experiment_name": 1,
            "experiment_status": 1,
            "experiment_created_at": 1,
        },
    )
    return JSONResponse(content=experiments)


@router.post("/experiments", tags=["admin"])
async def create_experiment(body: ds.ExperimentCreate):
    experiment_id = str(uuid.uuid4())
    experiment = ds.Experiment(
        experiment_id=experiment_id,
        experiment_name=body.experiment_name,
        experiment_description=body.experiment_description,
        experiment_dataset_ids=body.experiment_dataset_ids,
        experiment_status="draft",
        experiment_created_at=utils.get_current_datetime(),
    )
    dbc.create_experiment(experiment)
    return {"experiment_id": experiment_id}


@router.patch("/experiments/{experiment_id}", tags=["admin"])
async def update_experiment(experiment_id: str, body: ds.ExperimentPatch):
    if dbc.get_experiment(experiment_id) is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    dbc.update_experiment(experiment_id, fields)
    return {"message": "Experiment updated successfully"}


@router.get("/usagedataset", tags=["admin"])
async def get_users_usage_of_datasets():
    # dataset assignment is stored in UserAssignment.assigned_between (Dict[str, str])
    assignments = dbc.get_query_db("UserAssignment", query={})
    dataset_usage_count = {}
    for assignment in assignments:
        assigned_between = assignment.get("assigned_between", {})
        for dataset_id in assigned_between.values():
            dataset_usage_count[dataset_id] = dataset_usage_count.get(dataset_id, 0) + 1
    return dataset_usage_count


# ---------------------------------------------------------------------------
# Idiom management
# ---------------------------------------------------------------------------

@router.post("/idioms", tags=["admin"])
async def create_idiom(idiom: ds.Idiom):
    dbc.create_document("Idiom", idiom.model_dump())
    return JSONResponse(content={"message": f"Idiom '{idiom.label}' created.", "idiom_id": idiom.id}, status_code=201)


@router.get("/idioms", tags=["admin"])
async def get_idioms():
    idioms = dbc.get_query_db("Idiom", query={})
    for doc in idioms:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    return JSONResponse(content=idioms)


# ---------------------------------------------------------------------------
# Task management
# ---------------------------------------------------------------------------

@router.post("/tasks", tags=["admin"])
async def create_task(task: ds.Task):
    dbc.create_document("Task", task.model_dump(by_alias=True))
    return JSONResponse(content={"message": f"Task '{task.label}' created.", "task_id": task.id}, status_code=201)


@router.get("/tasks", tags=["admin"])
async def get_tasks():
    tasks = dbc.get_query_db("Task", query={})
    for doc in tasks:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    return JSONResponse(content=tasks)


# ---------------------------------------------------------------------------
# Question management
# ---------------------------------------------------------------------------

@router.post("/questions", tags=["admin"])
async def create_question(question: ds.Question):
    dbc.create_document("Question", question.model_dump(by_alias=True))
    return JSONResponse(content={"message": "Question created.", "question_id": question.id}, status_code=201)


@router.get("/questions", tags=["admin"])
async def get_questions(task_id: str | None = None):
    query = {"task_id": task_id} if task_id else {}
    questions = dbc.get_query_db("Question", query=query, projection={"_id": 0})
    return JSONResponse(content=questions)


# ---------------------------------------------------------------------------
# Experiment management
# ---------------------------------------------------------------------------

@router.post("/experiments", tags=["admin"])
async def create_experiment(experiment: ds.Experiment):
    dbc.create_document("Experiment", experiment.model_dump(by_alias=True))
    return JSONResponse(content={"message": f"Experiment '{experiment.name}' created.", "experiment_id": experiment.id}, status_code=201)


@router.get("/experiments", tags=["admin"])
async def get_experiments():
    experiments = dbc.get_query_db("Experiment", query={})
    for doc in experiments:
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
    return JSONResponse(content=experiments)


@router.patch("/experiments/{experiment_id}/status", tags=["admin"])
async def update_experiment_status(experiment_id: str, status: str):
    updated = dbc.update_document("Experiment", query={"_id": experiment_id}, update={"$set": {"status": status}})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": f"Experiment status updated to '{status}'."})


@router.patch("/experiments/{experiment_id}", tags=["admin"])
async def update_experiment(experiment_id: str, update_data: ds.ExperimentUpdate):
    fields: dict = {"task_configs": [tc.model_dump() for tc in update_data.task_configs]}
    if update_data.status is not None:
        fields["status"] = update_data.status
    updated = dbc.update_document("Experiment", query={"_id": experiment_id}, update={"$set": fields})
    if not updated:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return JSONResponse(content={"message": "Experiment updated.", "experiment_id": experiment_id})


# ---------------------------------------------------------------------------
# GroundTruth management
# ---------------------------------------------------------------------------

@router.post("/groundtruth", tags=["admin"])
async def create_ground_truth(ground_truth: ds.GroundTruth):
    dbc.create_document("GroundTruth", ground_truth.model_dump(by_alias=True))
    return JSONResponse(content={"message": "GroundTruth entry created.", "ground_truth_id": ground_truth.id}, status_code=201)
