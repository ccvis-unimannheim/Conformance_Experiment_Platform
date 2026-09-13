from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

import DfgBackend.app.datamodels.data_schemas as ds

_client: MongoClient | None = None

# Every collection this service touches is prefixed `Dfg` (DfgUser, DfgDataset,
# DfgAnswer, DfgUILogging). The main Conformance-Experiment app shares this
# database and owns the unprefixed names with different field shapes, so
# writing to those would mix two studies' data into one collection — which its
# unfiltered CSV exports then hand to an admin as a single file.


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


def create_answer(answer: ds.AnswerForDatabase):
    db = connect_to_database()
    answer_collection = db["DfgAnswer"]
    answer_collection.insert_one(answer.model_dump())
    print("Answer created successfully in database")


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


def save_ui_logging_data(ui_log_database: ds.UILogDataDatabase):
    db = connect_to_database()
    ui_log_collection = db["DfgUILogging"]
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
