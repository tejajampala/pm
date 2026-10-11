from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import STATIC_DIR
from app.models import format_errors
from app.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Project Management MVP", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": format_errors(exc.errors())})


app.include_router(router)


def configure_static(app_instance: FastAPI, static_directory: Path) -> None:
    if static_directory.exists():
        app_instance.mount("/", StaticFiles(directory=str(static_directory), html=True), name="static")
        return

    @app_instance.get("/", response_class=HTMLResponse)
    def root_placeholder() -> str:
        return "<!doctype html><title>Project Management MVP</title><h1>Backend running</h1><p>No frontend build found.</p>"


# Mounted last so the /api routes above take precedence over the catch-all static mount.
configure_static(app, STATIC_DIR)
