from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import questionnaire
from .routers import vis
from .routers import ui_tracking

# nginx strips the /dfg/api prefix before proxying here (see provibackend/nginx/nginx.conf),
# so routes below are mounted at the bare paths (/vis/..., /survey/..., /uitracking/...),
# matching the main backend's routers exactly.
app = FastAPI(
    title="DFG Backend",
    description="Standalone backend for the previous team's Directly-Follows-Graph experiment",
    version="0.1.0",
    openapi_url="/v1/openapi.json",
    docs_url="/v1/docs",
    redoc_url=None,
)

# Same-origin in production (single nginx host proxies both /dfg/* and the main
# app) — these extra origins only matter for local dev without nginx in front.
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://dfgfrontend:3000",
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
app.include_router(ui_tracking.router)


@app.get("/")
def read_root():
    return {"message": "DFG backend"}
