from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import init_db
from app.routes.demo import demo_router
from app.routes.sprints import sessions_router, sprints_router
from app.routes.ui import ui_router
from app.schemas import ErrorResponse
from app.services.errors import ErrorCode


TAGS_METADATA = [
    {
        "name": "Sprints",
        "description": "Управление учебными спринтами и базовой статистикой.",
    },
    {
        "name": "Sessions",
        "description": "Создание и обновление учебных фокус-сессий внутри спринтов.",
    },
    {
        "name": "Habits",
        "description": "Привычки, связанные со спринтами (паттерны и целевые сессии в день).",
    },
    {
        "name": "Demo",
        "description": "DEMO-эндпоинты для быстрого наполнения приложения тестовыми данными.",
    },
]

app = FastAPI(
    title="Habit Architect — Study Sprints",
    description="Мини-приложение для планирования учебных спринтов, привычек и фокус-сессий.",
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(sprints_router)
app.include_router(sessions_router)
app.include_router(demo_router)
app.include_router(ui_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail

    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        payload = detail
    else:
        payload = ErrorResponse(
            code=ErrorCode.UNEXPECTED_ERROR,
            message=str(detail) if detail else "Unexpected error",
            details=None,
        ).model_dump()

    return JSONResponse(status_code=exc.status_code, content=payload)


@app.on_event("startup")
def on_startup() -> None:
    """Run startup routines."""
    init_db()


@app.get("/")
def read_root() -> dict[str, str]:
    """Root health endpoint."""
    return {"status": "ok"}
