from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SprintStatus(str, Enum):
    """Possible lifecycle states for a sprint."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    """Execution status for study sessions."""

    PLANNED = "planned"
    DONE = "done"
    SKIPPED = "skipped"


class Sprint(Base):
    """Sprint model representing a short-term study goal."""

    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[SprintStatus] = mapped_column(
        SqlEnum(SprintStatus, name="sprint_status"),
        default=SprintStatus.PLANNED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    habits: Mapped[list["Habit"]] = relationship(
        back_populates="sprint",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="sprint",
        cascade="all, delete-orphan",
    )


class Habit(Base):
    """Habit tracked within a sprint."""

    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sprint_id: Mapped[int] = mapped_column(
        ForeignKey("sprints.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_sessions_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    sprint: Mapped[Sprint] = relationship(back_populates="habits")
    sessions: Mapped[list["Session"]] = relationship(back_populates="habit")


class Session(Base):
    """Individual focus session planned within a sprint or habit."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        CheckConstraint("mood BETWEEN 1 AND 5", name="mood_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sprint_id: Mapped[int] = mapped_column(
        ForeignKey("sprints.id", ondelete="CASCADE"),
        nullable=False,
    )
    habit_id: Mapped[int | None] = mapped_column(
        ForeignKey("habits.id", ondelete="SET NULL"),
        nullable=True,
    )
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    planned_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    actual_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        SqlEnum(SessionStatus, name="session_status"),
        default=SessionStatus.PLANNED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        nullable=False,
    )

    sprint: Mapped[Sprint] = relationship(back_populates="sessions")
    habit: Mapped[Habit | None] = relationship(back_populates="sessions")
