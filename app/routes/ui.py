from __future__ import annotations

from datetime import date, datetime, time as time_cls
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Habit, Session, SessionStatus, Sprint
from app.schemas import SprintStatus

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ui_router = APIRouter(
    prefix="/ui",
    tags=["UI"],
    include_in_schema=False,
)

_SESSION_FILTERS: dict[str, SessionStatus] = {
    "planned": SessionStatus.PLANNED,
    "done": SessionStatus.DONE,
    "skipped": SessionStatus.SKIPPED,
}


def _list_sprints_stmt() -> Select[tuple[Sprint]]:
    return select(Sprint).order_by(Sprint.start_date.desc())


def _sprint_overview(
    db: Session,
    sprint_id: int,
    habits_count: int,
) -> dict[str, Any]:
    stats_stmt = (
        select(
            func.count(Session.id).label("total_sessions"),
            func.sum(
                case((Session.status == SessionStatus.DONE, 1), else_=0)
            ).label("done_sessions"),
            func.sum(Session.planned_duration_min).label("total_planned"),
            func.sum(Session.actual_duration_min).label("total_actual"),
        )
        .where(Session.sprint_id == sprint_id)
    )
    total_sessions, done_sessions, total_planned, total_actual = db.execute(stats_stmt).one()

    done_sessions = done_sessions or 0
    total_sessions = total_sessions or 0
    completion_rate = None
    if total_sessions > 0:
        completion_rate = round((done_sessions / total_sessions) * 100, 1)

    return {
        "habits_count": habits_count,
        "sessions_count": total_sessions,
        "done_sessions": done_sessions,
        "completion_rate": completion_rate,
        "total_planned_minutes": total_planned or 0,
        "total_actual_minutes": total_actual,
    }


def _normalize_filter(value: str | None) -> str:
    if not value:
        return "all"
    value = value.lower()
    if value in ("all", *(_SESSION_FILTERS.keys())):
        return value
    return "all"


def _default_redirect(url: str, message: str | None = None, error: bool = False) -> RedirectResponse:
    suffix = ""
    if message:
        param = "error" if error else "msg"
        suffix = ("?" if "?" not in url else "&") + f"{param}={message}"
    return RedirectResponse(url + suffix, status_code=303)


@ui_router.get("/", response_class=HTMLResponse, name="sprints_page")
def sprints_page(
    request: Request,
    db: Session = Depends(get_db),
):
    sprints = db.execute(_list_sprints_stmt()).scalars().all()
    flash_msg = request.query_params.get("msg")
    flash_error = request.query_params.get("error")
    return templates.TemplateResponse(
        "sprints_list.html",
        {
            "request": request,
            "sprints": sprints,
            "flash_msg": flash_msg,
            "flash_error": flash_error,
        },
    )


@ui_router.post("/sprints", response_class=HTMLResponse)
def create_sprint_ui(
    request: Request,
    title: str = Form(...),
    goal_text: str = Form(...),
    start_date: date = Form(...),
    end_date: date = Form(...),
    db: Session = Depends(get_db),
):
    sprint = Sprint(
        title=title,
        goal_text=goal_text,
        start_date=start_date,
        end_date=end_date,
        status=SprintStatus.PLANNED,
    )
    db.add(sprint)
    db.commit()

    return RedirectResponse(
        request.url_for("sprints_page") + "?msg=Sprint+created",
        status_code=303,
    )


@ui_router.get("/sprints/{sprint_id}", response_class=HTMLResponse, name="sprint_detail_page")
def sprint_detail_page(
    request: Request,
    sprint_id: int,
    db: Session = Depends(get_db),
):
    sprint = db.get(Sprint, sprint_id)
    flash_msg = request.query_params.get("msg")
    flash_error = request.query_params.get("error")
    sessions_filter = _normalize_filter(request.query_params.get("filter"))

    if not sprint:
        return templates.TemplateResponse(
            "sprint_detail.html",
            {
                "request": request,
                "sprint": None,
                "habits": [],
                "overview": None,
                "sessions": [],
                "flash_msg": flash_msg,
                "flash_error": flash_error or "Sprint not found",
                "sessions_filter": sessions_filter,
            },
            status_code=404,
        )

    habits_stmt = (
        select(Habit)
        .where(Habit.sprint_id == sprint_id)
        .order_by(Habit.name.asc())
    )
    habits = db.execute(habits_stmt).scalars().all()

    sessions_stmt = (
        select(Session)
        .where(Session.sprint_id == sprint_id)
        .order_by(Session.planned_start.asc())
    )
    if sessions_filter in _SESSION_FILTERS:
        sessions_stmt = sessions_stmt.where(Session.status == _SESSION_FILTERS[sessions_filter])
    sessions = db.execute(sessions_stmt).scalars().all()

    overview = _sprint_overview(db, sprint_id, len(habits))

    return templates.TemplateResponse(
        "sprint_detail.html",
        {
            "request": request,
            "sprint": sprint,
            "habits": habits,
            "overview": overview,
            "sessions": sessions,
            "flash_msg": flash_msg,
            "flash_error": flash_error,
            "sessions_filter": sessions_filter,
        },
    )


@ui_router.post("/sprints/{sprint_id}/habits", name="create_habit_ui")
def create_habit_ui(
    request: Request,
    sprint_id: int,
    name: str = Form(...),
    description: str | None = Form(None),
    target_sessions_per_day: int = Form(...),
    db: Session = Depends(get_db),
):
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        return _default_redirect(
            request.url_for("sprints_page"),
            "Sprint+not+found",
            error=True,
        )

    clean_name = name.strip()
    if not clean_name or target_sessions_per_day <= 0:
        return _default_redirect(
            request.url_for("sprint_detail_page", sprint_id=sprint_id),
            "Unable+to+create+habit",
            error=True,
        )

    habit = Habit(
        sprint_id=sprint_id,
        name=clean_name,
        description=description.strip() if description else None,
        target_sessions_per_day=target_sessions_per_day,
    )
    try:
        db.add(habit)
        db.commit()
    except Exception:
        db.rollback()
        return _default_redirect(
            request.url_for("sprint_detail_page", sprint_id=sprint_id),
            "Unable+to+create+habit",
            error=True,
        )

    return _default_redirect(
        request.url_for("sprint_detail_page", sprint_id=sprint_id),
        "Habit+created",
    )


@ui_router.post("/habits/{habit_id}/delete", name="delete_habit_ui")
def delete_habit_ui(
    request: Request,
    habit_id: int,
    db: Session = Depends(get_db),
):
    habit = db.get(Habit, habit_id)
    if not habit:
        return _default_redirect(
            request.url_for("sprints_page"),
            "Habit+not+found",
            error=True,
        )

    sprint_id = habit.sprint_id
    try:
        sessions_stmt = select(Session).where(Session.habit_id == habit_id)
        for session in db.execute(sessions_stmt).scalars():
            db.delete(session)
        db.delete(habit)
        db.commit()
    except Exception:
        db.rollback()
        return _default_redirect(
            request.url_for("sprint_detail_page", sprint_id=sprint_id),
            "Unable+to+delete+habit",
            error=True,
        )

    return _default_redirect(
        request.url_for("sprint_detail_page", sprint_id=sprint_id),
        "Habit+deleted",
    )


@ui_router.post("/sprints/{sprint_id}/sessions/plan", name="plan_session_ui")
def plan_session_ui(
    request: Request,
    sprint_id: int,
    habit_id: str | None = Form(None),
    planned_start_date: date = Form(...),
    planned_start_time: str | None = Form(None),
    planned_duration_min: int = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    sprint = db.get(Sprint, sprint_id)
    if not sprint or planned_duration_min <= 0:
        return _default_redirect(
            request.url_for("sprint_detail_page", sprint_id=sprint_id),
            "Unable+to+plan+session",
            error=True,
        )

    habit_obj: Habit | None = None
    habit_id_value: int | None = None
    if habit_id:
        try:
            habit_id_value = int(habit_id)
        except ValueError:
            habit_id_value = None
        if habit_id_value:
            habit_obj = db.get(Habit, habit_id_value)
            if not habit_obj or habit_obj.sprint_id != sprint_id:
                return _default_redirect(
                    request.url_for("sprint_detail_page", sprint_id=sprint_id),
                    "Invalid+habit+selected",
                    error=True,
                )

    try:
        start_time = time_cls.fromisoformat(planned_start_time) if planned_start_time else time_cls(9, 0)
    except ValueError:
        start_time = time_cls(9, 0)

    planned_start = datetime.combine(planned_start_date, start_time)

    session = Session(
        sprint_id=sprint_id,
        habit_id=habit_obj.id if habit_obj else None,
        planned_start=planned_start,
        planned_duration_min=planned_duration_min,
        status=SessionStatus.PLANNED,
        notes=notes.strip() if notes else None,
    )

    try:
        db.add(session)
        db.commit()
    except Exception:
        db.rollback()
        return _default_redirect(
            request.url_for("sprint_detail_page", sprint_id=sprint_id),
            "Unable+to+plan+session",
            error=True,
        )

    return _default_redirect(
        request.url_for("sprint_detail_page", sprint_id=sprint_id),
        "Session+planned",
    )


@ui_router.post("/sessions/{session_id}/complete", name="complete_session_ui")
def complete_session_ui(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
):
    session = db.get(Session, session_id)
    if not session:
        return _default_redirect(
            request.url_for("sprints_page"),
            "Unable+to+update+session",
            error=True,
        )

    try:
        session.status = SessionStatus.DONE
        if session.actual_start is None:
            session.actual_start = datetime.utcnow()
        if session.actual_duration_min is None:
            session.actual_duration_min = session.planned_duration_min
        db.add(session)
        db.commit()
    except Exception:
        db.rollback()
        return _default_redirect(
            request.url_for("sprint_detail_page", sprint_id=session.sprint_id),
            "Unable+to+update+session",
            error=True,
        )

    return _default_redirect(
        request.url_for("sprint_detail_page", sprint_id=session.sprint_id),
        "Session+updated",
    )


@ui_router.post("/sessions/{session_id}/skip", name="skip_session_ui")
def skip_session_ui(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
):
    session = db.get(Session, session_id)
    if not session:
        return _default_redirect(
            request.url_for("sprints_page"),
            "Unable+to+update+session",
            error=True,
        )

    try:
        session.status = SessionStatus.SKIPPED
        db.add(session)
        db.commit()
    except Exception:
        db.rollback()
        return _default_redirect(
            request.url_for("sprint_detail_page", sprint_id=session.sprint_id),
            "Unable+to+update+session",
            error=True,
        )

    return _default_redirect(
        request.url_for("sprint_detail_page", sprint_id=session.sprint_id),
        "Session+updated",
    )
