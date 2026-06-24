import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import ProViBackend.utils.config as config
import ProViBackend.utils.database.connection as dbc
from ProViBackend.utils.database.migration import migrate_experiments_to_task_instances
from .seed_data import CANONICAL_TASKS, CANONICAL_IDIOMS, CANONICAL_KNOWLEDGE_QUESTIONS

logger = logging.getLogger(__name__)
from .routers import questionnaire
from .routers import vis
from .routers import admin
from .routers import auth
from .routers import ui_tracking
from .routers import participant


_SEED_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _seed_collection(collection_name: str, items: list, key_field: str):
    """Upsert canonical items — inserts missing ones, leaves existing ones untouched."""
    db = dbc.connect_to_database()
    for item in items:
        doc = dict(item)
        doc["_id"] = str(uuid.uuid5(_SEED_NAMESPACE, item[key_field]))
        db[collection_name].update_one(
            {"_id": doc["_id"]},
            {"$setOnInsert": doc},
            upsert=True,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_collection("Task", CANONICAL_TASKS, key_field="task_key")
    _seed_collection("Idiom", CANONICAL_IDIOMS, key_field="idiom_key")
    _seed_collection("KnowledgeQuestion", CANONICAL_KNOWLEDGE_QUESTIONS, key_field="kq_key")
    try:
        migrate_experiments_to_task_instances()
    except Exception:
        logger.exception("task_instances migration failed; continuing startup")
    try:
        from ProViBackend.scripts.generate_sample_data import generate as _gen_sample
        _gen_sample()
    except Exception:
        logger.exception("Sample dataset generation failed; preview (sample) will be unavailable")
    yield


app = FastAPI(
    title="ProVi Backend",
    description="Backend for the ProVi project",
    version="0.1.0",
    openapi_url="/v1/openapi.json",
    docs_url="/v1/docs",
    redoc_url=None,
    root_path="/api",
    lifespan=lifespan,
)

origins = [
    "http://pm-vis.uni-mannheim.de",
    "https://pm-vis.uni-mannheim.de",
    "http://localhost:3000",
    "http://127.0.0.1:3000",  
    "http://127.0.0.1:8080",
    "http://provifrontend:3000",
    "http://127.0.0.1:22222",
    "http://localhost:22222"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questionnaire.router)
app.include_router(vis.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(ui_tracking.router)
app.include_router(participant.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}

