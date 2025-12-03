from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Habit, Session as SessionModel, SessionStatus, Sprint
from app.schemas import (
    ErrorResponse,
    HabitCreate,
    HabitRead,
    SessionCompleteRequest,
    SessionCreate,
    SessionRead,
    SessionSkipRequest,
    SprintCreate,
    SprintOverview,
    SprintRead,
    SprintStatus,
    SprintStatusUpdate,
)
from app.services.errors import ErrorCode, build_error

sprints_router = APIRouter(prefix="/sprints")
sessions_router = APIRouter(prefix="/sessions")


def _not_found_error(code: ErrorCode, entity: str, entity_id: int) -> HTTPException:
    return build_error(
        code=code,
        status_code=status.HTTP_404_NOT_FOUND,
        message=f"{entity} {entity_id} not found",
        details={"id": entity_id},
    )


def _get_sprint_or_404(sprint_id: int, db: Session) -> Sprint:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise _not_found_error(ErrorCode.SPRINT_NOT_FOUND, "Sprint", sprint_id)
    return sprint


def _get_session_or_404(session_id: int, db: Session) -> SessionModel:
    session = db.get(SessionModel, session_id)
    if not session:
        raise _not_found_error(ErrorCode.SESSION_NOT_FOUND, "Session", session_id)
    return session


@sprints_router.get(
    "",
    response_model=list[SprintRead],
    summary="Список спринтов",
    description="Возвращает все спринты пользователя в порядке создания.",
    tags=["Sprints"],
)
def list_sprints(db: Session = Depends(get_db)) -> list[Sprint]:
    sprints = db.execute(select(Sprint)).scalars().all()
    return sprints


@sprints_router.post(
    "",
    response_model=SprintRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать спринт",
    description="Создаёт новый учебный спринт с датами, статусом и целевым текстом.",
    tags=["Sprints"],
)
def create_sprint(
    payload: SprintCreate,
    db: Session = Depends(get_db),
) -> Sprint:
    sprint = Sprint(**payload.model_dump())
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


@sprints_router.get(
    "/overview",
    response_model=list[SprintOverview],
    summary="Сводная статистика по спринтам",
    description="Возвращает агрегированную статистику по каждому спринту: количество привычек, сессий, выполненных сессий и суммарное время.",
    tags=["Sprints"],
)
def list_sprint_overview(db: Session = Depends(get_db)) -> list[SprintOverview]:
    habit_counts_subquery = (
        select(
            Habit.sprint_id.label("sprint_id"),
            func.count(Habit.id).label("habits_count"),
        )
        .group_by(Habit.sprint_id)
        .subquery()
    )

    session_stats_subquery = (
        select(
            SessionModel.sprint_id.label("sprint_id"),
            func.count(SessionModel.id).label("sessions_count"),
            func.sum(
                case((SessionModel.status == SessionStatus.DONE, 1), else_=0)
            ).label("done_sessions"),
            func.sum(SessionModel.planned_duration_min).label("total_planned_minutes"),
            func.sum(SessionModel.actual_duration_min).label("total_actual_minutes"),
        )
        .group_by(SessionModel.sprint_id)
        .subquery()
    )

    stmt = (
        select(
            Sprint.id.label("sprint_id"),
            Sprint.title,
            Sprint.status,
            Sprint.start_date,
            Sprint.end_date,
            func.coalesce(habit_counts_subquery.c.habits_count, 0).label("habits_count"),
            func.coalesce(session_stats_subquery.c.sessions_count, 0).label(
                "sessions_count"
            ),
            func.coalesce(session_stats_subquery.c.done_sessions, 0).label("done_sessions"),
            func.coalesce(
                session_stats_subquery.c.total_planned_minutes,
                0,
            ).label("total_planned_minutes"),
            session_stats_subquery.c.total_actual_minutes.label("total_actual_minutes"),
        )
        .outerjoin(
            habit_counts_subquery,
            habit_counts_subquery.c.sprint_id == Sprint.id,
        )
        .outerjoin(
            session_stats_subquery,
            session_stats_subquery.c.sprint_id == Sprint.id,
        )
        .order_by(Sprint.id)
    )

    results = db.execute(stmt).all()

    overview_items: list[SprintOverview] = []
    for row in results:
        sessions_count = row.sessions_count or 0
        done_sessions = row.done_sessions or 0
        completion_rate = (
            float(done_sessions) / float(sessions_count)
            if sessions_count
            else None
        )

        overview_items.append(
            SprintOverview(
                sprint_id=row.sprint_id,
                title=row.title,
                status=row.status,
                start_date=row.start_date,
                end_date=row.end_date,
                habits_count=row.habits_count or 0,
                sessions_count=sessions_count,
                done_sessions=done_sessions,
                completion_rate=completion_rate,
                total_planned_minutes=row.total_planned_minutes or 0,
                total_actual_minutes=row.total_actual_minutes,
            )
        )

    return overview_items


@sprints_router.get(
    "/{sprint_id}",
    response_model=SprintRead,
    summary="Получить спринт по ID",
    description="Возвращает данные одного спринта. 404, если спринт не найден.",
    tags=["Sprints"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Sprint not found",
        }
    },
)
def get_sprint(
    sprint_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> Sprint:
    return _get_sprint_or_404(sprint_id, db)


@sprints_router.patch(
    "/{sprint_id}/status",
    response_model=SprintRead,
    summary="Обновить статус спринта",
    description="Меняет статус спринта (planned/active/completed/cancelled).",
    tags=["Sprints"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Sprint not found",
        }
    },
)
def update_sprint_status(
    sprint_id: Annotated[int, Path(gt=0)],
    payload: SprintStatusUpdate,
    db: Session = Depends(get_db),
) -> Sprint:
    sprint = _get_sprint_or_404(sprint_id, db)

    sprint.status = payload.status
    db.commit()
    db.refresh(sprint)
    return sprint


@sprints_router.post(
    "/{sprint_id}/habits",
    response_model=HabitRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать привычку для спринта",
    description="Создаёт новую привычку внутри выбранного спринта.",
    tags=["Habits"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Sprint not found",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "sprint_id mismatch",
        },
    },
)
def create_habit(
    sprint_id: Annotated[int, Path(gt=0)],
    payload: HabitCreate,
    db: Session = Depends(get_db),
) -> Habit:
    _get_sprint_or_404(sprint_id, db)

    if payload.sprint_id != sprint_id:
        raise build_error(
            code=ErrorCode.SPRINT_ID_MISMATCH,
            status_code=status.HTTP_400_BAD_REQUEST,
            message="sprint_id mismatch",
            details={"path_sprint_id": sprint_id, "body_sprint_id": payload.sprint_id},
        )

    habit = Habit(**payload.model_dump())
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


@sprints_router.get(
    "/{sprint_id}/habits",
    response_model=list[HabitRead],
    summary="Список привычек спринта",
    description="Возвращает все привычки, связанные с указанным спринтом.",
    tags=["Habits"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Sprint not found",
        }
    },
)
def list_habits(
    sprint_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> list[Habit]:
    _get_sprint_or_404(sprint_id, db)

    habits = db.execute(select(Habit).where(Habit.sprint_id == sprint_id)).scalars().all()
    return habits


@sprints_router.post(
    "/{sprint_id}/sessions",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Запланировать сессию",
    description="Добавляет новую учебную сессию в рамках спринта.",
    tags=["Sessions"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Sprint not found",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "sprint_id mismatch",
        },
    },
)
def create_session(
    sprint_id: Annotated[int, Path(gt=0)],
    payload: SessionCreate,
    db: Session = Depends(get_db),
) -> SessionModel:
    _get_sprint_or_404(sprint_id, db)

    if payload.sprint_id != sprint_id:
        raise build_error(
            code=ErrorCode.SPRINT_ID_MISMATCH,
            status_code=status.HTTP_400_BAD_REQUEST,
            message="sprint_id mismatch",
            details={"path_sprint_id": sprint_id, "body_sprint_id": payload.sprint_id},
        )

    session = SessionModel(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@sessions_router.patch(
    "/{session_id}/complete",
    response_model=SessionRead,
    summary="Отметить сессию выполненной",
    description="Фиксирует факт проведения сессии и позволяет указать фактическую продолжительность, заметки, сложность и настроение.",
    tags=["Sessions"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Session not found",
        }
    },
)
def complete_session(
    session_id: Annotated[int, Path(gt=0)],
    payload: SessionCompleteRequest,
    db: Session = Depends(get_db),
) -> SessionModel:
    session = _get_session_or_404(session_id, db)

    session.status = SessionStatus.DONE
    session.actual_start = payload.actual_start
    session.actual_duration_min = payload.actual_duration_min
    session.notes = payload.notes
    session.difficulty = payload.difficulty
    session.mood = payload.mood

    db.commit()
    db.refresh(session)
    return session


@sessions_router.patch(
    "/{session_id}/skip",
    response_model=SessionRead,
    summary="Пропустить сессию",
    description="Помечает сессию как пропущенную. Можно добавить краткие заметки.",
    tags=["Sessions"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Session not found",
        }
    },
)
def skip_session(
    session_id: Annotated[int, Path(gt=0)],
    payload: SessionSkipRequest | None = None,
    db: Session = Depends(get_db),
) -> SessionModel:
    session = _get_session_or_404(session_id, db)

    session.status = SessionStatus.SKIPPED
    if payload and payload.notes is not None:
        session.notes = payload.notes

    db.commit()
    db.refresh(session)
    return session


@sprints_router.get(
    "/{sprint_id}/stats",
    summary="Подробная статистика спринта",
    description="Возвращает подробную статистику по сессиям спринта (выполненные, пропущенные, суммарное время, средние метрики)",
    tags=["Sprints"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Sprint not found",
        }
    },
)
def sprint_stats(
    sprint_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> dict:
    _get_sprint_or_404(sprint_id, db)

    total_sessions_expr = func.count(SessionModel.id).label("total_sessions")
    done_sessions_expr = func.sum(
        case((SessionModel.status == SessionStatus.DONE, 1), else_=0)
    ).label("done_sessions")
    skipped_sessions_expr = func.sum(
        case((SessionModel.status == SessionStatus.SKIPPED, 1), else_=0)
    ).label("skipped_sessions")
    total_planned_minutes_expr = func.sum(SessionModel.planned_duration_min).label(
        "total_planned_minutes"
    )
    total_actual_minutes_expr = func.sum(SessionModel.actual_duration_min).label(
        "total_actual_minutes"
    )
    avg_difficulty_expr = func.avg(
        case(
            (SessionModel.status == SessionStatus.DONE, SessionModel.difficulty),
            else_=None,
        )
    ).label("avg_difficulty")
    avg_mood_expr = func.avg(
        case(
            (SessionModel.status == SessionStatus.DONE, SessionModel.mood),
            else_=None,
        )
    ).label("avg_mood")

    stmt = (
        select(
            total_sessions_expr,
            done_sessions_expr,
            skipped_sessions_expr,
            total_planned_minutes_expr,
            total_actual_minutes_expr,
            avg_difficulty_expr,
            avg_mood_expr,
        ).where(SessionModel.sprint_id == sprint_id)
    )

    result = db.execute(stmt).one()

    total_sessions = result.total_sessions or 0
    done_sessions = result.done_sessions or 0
    skipped_sessions = result.skipped_sessions or 0
    total_planned_minutes = result.total_planned_minutes or 0
    total_actual_minutes = result.total_actual_minutes or 0
    avg_difficulty = float(result.avg_difficulty) if result.avg_difficulty is not None else None
    avg_mood = float(result.avg_mood) if result.avg_mood is not None else None
    completion_rate = (done_sessions / total_sessions) if total_sessions else 0

    return {
        "sprint_id": sprint_id,
        "total_sessions": total_sessions,
        "done_sessions": done_sessions,
        "skipped_sessions": skipped_sessions,
        "completion_rate": completion_rate,
        "total_planned_minutes": total_planned_minutes,
        "total_actual_minutes": total_actual_minutes,
        "avg_difficulty": avg_difficulty,
        "avg_mood": avg_mood,
    }
