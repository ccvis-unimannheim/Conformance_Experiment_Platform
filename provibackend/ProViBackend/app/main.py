from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import ProViBackend.utils.config as config
from .routers import questionnaire
from .routers import vis
from .routers import admin
from .routers import auth
from .routers import ui_tracking

app = FastAPI(
    title="ProVi Backend",
    description="Backend for the ProVi project",
    version="0.1.0",
    openapi_url="/v1/openapi.json",
    docs_url="/v1/docs",
    redoc_url=None,
    root_path="/api"
)

origins = [
    "http://pm-vis.uni-mannheim.de",
    "https://pm-vis.uni-mannheim.de",
    "http://localhost:3000",
    "http://127.0.0.1:3000",  # SSH 隧道在浏览器用 127.0.0.1 打开时与 localhost 不同源
    "http://127.0.0.1:8080",
    "http://provifrontend:3000",
    "http://127.0.0.1:22222"
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


@app.get("/")
def read_root():
    return {"Hello": "World"}

