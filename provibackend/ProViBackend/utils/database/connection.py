from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

import ProViBackend.app.datamodels.data_schemas as ds

# Todo: Add test assert script to test connection by calling db.client.admin.command("ping")
def connect_to_database():
    load_dotenv()
    db_username = os.environ["LOCAL_DATABASE_USERNAME"]
    db_password = os.environ["LOCAL_DATABASE_PASSWORD"]
    uri = f"mongodb://{db_username}:{db_password}@mongo:27017/TeamProject?authSource=admin"
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        db_client = client.get_database("TeamProject")
        return db_client
    except Exception as e:
        raise Exception("Unable to connect to the database due to the following error: ", e)


def create_user(user: ds.User):
    db = connect_to_database()
    users_collection = db["User"]
    users_collection.insert_one(user.model_dump())
    print("User created successfully in database")


def create_dataset(dataset: ds.Dataset):
    db = connect_to_database()
    dataset_collection = db["Dataset"]
    dataset_collection.insert_one(dataset.model_dump())
    print("Dataset created successfully in database")


def create_answer(answer: ds.AnswerForDatabase):
    db = connect_to_database()
    answer_collection = db["Answer"]
    answer_collection.insert_one(answer.model_dump())
    print("Answer created successfully in database")


def update_dataset_is_active_status(dataset_id: str, is_active: bool):
    db = connect_to_database()
    dataset_collection = db["Dataset"]
    dataset_collection.update_one({"dataset_id": dataset_id}, {"$set": {"dataset_is_active": is_active}})
    print("Dataset is_active status updated successfully in database")


def get_query_db(collection: str, query=None, projection=None) -> list :
    if query is None:
        query = {}
    db = connect_to_database()
    collection = db[collection]
    if projection:
        res = collection.find(query, projection)
    else:
        res = collection.find(query)
    return list(res)


def update_user_knowledge_answers(user_id: str, knowledge_answers: ds.KnowledgeAnswers):
    db = connect_to_database()
    user_collection = db["User"]
    user_collection.update_one({"user_id": user_id}, {"$set": {"knowledge_answers": knowledge_answers.model_dump()}})
    print("User knowledge answers updated successfully in database")


def save_ui_logging_data(ui_log_database: ds.UILogDataDatabase):
    db = connect_to_database()
    ui_log_collection = db["UILogging"]
    ui_log_collection.insert_one(ui_log_database.model_dump())
    print("UI logging data saved successfully in database")


def create_experiment(experiment: ds.Experiment):
    db = connect_to_database()
    db["Experiment"].insert_one(experiment.model_dump())
    print("Experiment created successfully in database")


def get_experiment(experiment_id: str) -> dict | None:
    db = connect_to_database()
    return db["Experiment"].find_one({"experiment_id": experiment_id}, {"_id": 0})


def update_experiment(experiment_id: str, fields: dict):
    db = connect_to_database()
    db["Experiment"].update_one({"experiment_id": experiment_id}, {"$set": fields})
