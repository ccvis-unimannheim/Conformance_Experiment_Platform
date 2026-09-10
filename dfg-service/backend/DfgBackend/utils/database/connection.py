from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

import DfgBackend.app.datamodels.data_schemas as ds

_client: MongoClient | None = None


def connect_to_database():
    """Returns the TeamProject database. The MongoClient is created once and reused (singleton)."""
    global _client
    if _client is None:
        load_dotenv()
        db_username = os.environ["LOCAL_DATABASE_USERNAME"]
        db_password = os.environ["LOCAL_DATABASE_PASSWORD"]
        uri = f"mongodb://{db_username}:{db_password}@mongo:27017/TeamProject?authSource=admin"
        try:
            _client = MongoClient(uri, server_api=ServerApi('1'))
            _client.admin.command("ping")
        except Exception as e:
            _client = None
            raise Exception("Unable to connect to the database due to the following error: ", e)
    return _client.get_database("TeamProject")


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
    dataset_collection.update_one({"dataset_id": dataset_id}, {"$set": {"is_active": is_active}})
    print("Dataset is_active status updated successfully in database")


def get_query_db(collection: str, query=None, projection=None) -> list:
    if query is None:
        query = {}
    db = connect_to_database()
    collection = db[collection]
    if projection:
        res = collection.find(query, projection)
    else:
        res = collection.find(query)
    return list(res)


def save_knowledge_answers(user_id: str, knowledge_answers: ds.KnowledgeAnswers):
    db = connect_to_database()
    knowledge_collection = db["KnowledgeAnswers"]
    knowledge_collection.insert_one(knowledge_answers.model_dump(by_alias=True))
    user_collection = db["User"]
    user_collection.update_one({"user_id": user_id}, {"$set": {"knowledge_id": knowledge_answers.id}})
    print("Knowledge answers saved and User.knowledge_id updated successfully in database")


def save_ui_logging_data(ui_log_database: ds.UILogDataDatabase):
    db = connect_to_database()
    ui_log_collection = db["UILogging"]
    for log_entry in ui_log_database.ui_log_data.ui_logs:
        ui_log_collection.insert_one(log_entry.model_dump())
    print("UI logging data saved successfully in database")


def create_document(collection_name: str, data: dict):
    db = connect_to_database()
    collection = db[collection_name]
    collection.insert_one(data)
    print(f"Document created successfully in collection '{collection_name}'")


def update_document(collection_name: str, query: dict, update: dict) -> bool:
    db = connect_to_database()
    collection = db[collection_name]
    result = collection.update_one(query, update)
    return result.matched_count > 0


def delete_document(collection_name: str, query: dict) -> bool:
    """Deletes a single document matching the query. Returns True if a document was deleted."""
    db = connect_to_database()
    collection = db[collection_name]
    result = collection.delete_one(query)
    return result.deleted_count > 0


def get_document(collection_name: str, query: dict) -> dict | None:
    """Returns a single document matching the query, or None if not found."""
    db = connect_to_database()
    collection = db[collection_name]
    return collection.find_one(query)


def get_user_assignment(user_id: str, experiment_id: str) -> dict | None:
    """Returns the UserAssignment for a given user and experiment, or None if not found."""
    return get_document("UserAssignment", {"user_id": user_id, "experiment_id": experiment_id})


def update_trial_index(assignment_id: str, new_index: int) -> bool:
    """Updates current_trial_index for a UserAssignment. Returns True if the document was found."""
    return update_document(
        "UserAssignment",
        query={"_id": assignment_id},
        update={"$set": {"current_trial_index": new_index}},
    )


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
