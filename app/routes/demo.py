from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Habit, Session as SessionModel, SessionStatus, Sprint
from app.schemas import HabitCreate, SessionCreate, SprintCreate, SprintStatus

# Demo-only router for seeding data during live presentations.
demo_router = APIRouter(prefix="/demo")


@demo_router.post(
    "/seed",
    summary="Сбросить БД и наполнить демо-данными",
    description=(
        "DEMO ONLY — очищает текущие данные и добавляет один пример спринта с привычками"
        " и сессиями для быстрой демонстрации интерфейса."
    ),
    tags=["Demo"],
)
def seed_demo(db: Session = Depends(get_db)) -> dict:
    """Reset the database with a curated sprint, habits, and sessions."""
    db.query(SessionModel).delete()
    db.query(Habit).delete()
    db.query(Sprint).delete()

    sprint_data = SprintCreate(
        title="Deep Work Week",
        goal_text="Solidify DS & Algorithms fundamentals",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=6),
        status=SprintStatus.ACTIVE,
    )
    sprint = Sprint(**sprint_data.model_dump())
    db.add(sprint)
    db.flush()

    habits_payload = [
        HabitCreate(
            sprint_id=sprint.id,
            name="Morning math drills",
            description="80 minutes focused problem solving",
            target_sessions_per_day=2,
        ),
        HabitCreate(
            sprint_id=sprint.id,
            name="Evening recap notes",
            description="Summaries of key takeaways",
            target_sessions_per_day=1,
        ),
    ]

    habits: list[Habit] = []
    for payload in habits_payload:
        habit = Habit(**payload.model_dump())
        db.add(habit)
        habits.append(habit)
    db.flush()

    base_start = datetime.combine(sprint.start_date, datetime.min.time()).replace(hour=9)
    sessions_payload: list[SessionCreate] = []
    for offset in range(6):
        sessions_payload.append(
            SessionCreate(
                sprint_id=sprint.id,
                habit_id=habits[0].id,
                planned_start=base_start + timedelta(days=offset),
                planned_duration_min=60 if offset % 2 == 0 else 45,
                status=SessionStatus.DONE if offset % 3 != 0 else SessionStatus.SKIPPED,
                actual_start=(base_start + timedelta(days=offset, hours=offset % 3))
                if offset % 3 != 0
                else None,
                actual_duration_min=55 if offset % 3 != 0 else None,
                notes="Felt productive" if offset % 3 != 0 else "Needed rest",
                difficulty=4 if offset % 2 == 0 else 3,
                mood=3 + (offset % 2),
            )
        )

    sessions: list[SessionModel] = []
    for payload in sessions_payload:
        session = SessionModel(**payload.model_dump())
        db.add(session)
        sessions.append(session)

    db.commit()

    return {
        "sprint_id": sprint.id,
        "habits": [habit.name for habit in habits],
        "sessions": [
            {
                "id": session.id,
                "status": session.status,
                "planned_duration": session.planned_duration_min,
            }
            for session in sessions
        ],
    }
