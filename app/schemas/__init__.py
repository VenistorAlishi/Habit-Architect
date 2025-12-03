from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional



class SprintStatus(str, Enum):
    """Lifecycle states for a sprint."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    """Execution status for study sessions."""

    PLANNED = "planned"
    DONE = "done"
    SKIPPED = "skipped"


class ErrorResponse(BaseModel):
    """Uniform error contract returned by the API."""

    code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-friendly error description")
    details: dict | None = Field(
        default=None,
        description="Optional structured payload with extra context",
    )


class ORMModel(BaseModel):
    """Base model that can hydrate from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class SprintBase(ORMModel):
    title: str = Field(..., max_length=255, description="Short name for the sprint")
    goal_text: str = Field(..., description="Primary study goal for this sprint")
    start_date: date = Field(..., description="First day of the sprint (inclusive)")
    end_date: date = Field(..., description="Last day of the sprint (inclusive)")
    status: SprintStatus = Field(
        default=SprintStatus.PLANNED,
        description="Current lifecycle state",
    )


class SprintCreate(SprintBase):
    """Payload for creating a new sprint."""


class SprintRead(SprintBase):
    """Sprint representation returned to clients."""

    id: int
    created_at: datetime
    updated_at: datetime


class SprintStatusUpdate(ORMModel):
    """Payload to update the sprint status only."""

    status: SprintStatus = Field(..., description="New status to apply")


class HabitBase(ORMModel):
    sprint_id: int = Field(..., ge=1, description="Identifier of the parent sprint")
    name: str = Field(..., max_length=255, description="Name of the habit to track")
    description: str | None = Field(
        default=None,
        description="Optional details about the habit",
    )
    target_sessions_per_day: int = Field(
        ..., ge=1, description="How many focus sessions are planned per day",
    )


class HabitCreate(HabitBase):
    """Payload for creating a habit within a sprint."""


class HabitRead(HabitBase):
    """Habit representation returned to clients."""

    id: int
    created_at: datetime
    updated_at: datetime


class SessionBase(ORMModel):
    sprint_id: int = Field(..., ge=1, description="Sprint this session belongs to")
    habit_id: int | None = Field(
        default=None,
        ge=1,
        description="Optional habit identifier",
    )
    planned_start: datetime = Field(..., description="Planned start time")
    planned_duration_min: int = Field(
        ..., ge=1, description="Planned duration in minutes",
    )
    actual_start: datetime | None = Field(
        default=None,
        description="Actual start timestamp (if completed)",
    )
    actual_duration_min: int | None = Field(
        default=None,
        ge=1,
        description="Actual duration in minutes",
    )
    status: SessionStatus = Field(
        default=SessionStatus.PLANNED,
        description="Current execution status",
    )
    notes: str | None = Field(
        default=None,
        description="Optional reflections or blockers",
    )
    difficulty: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Self-reported difficulty (1 easy – 5 hard)",
    )
    mood: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Self-reported mood (1 low – 5 great)",
    )


class SessionCreate(SessionBase):
    """Payload for scheduling a new focus session."""


class SessionRead(SessionBase):
    """Session representation returned to clients."""

    id: int
    created_at: datetime


class SessionCompleteRequest(ORMModel):
    """Payload to mark a session as completed."""

    actual_start: datetime = Field(..., description="Actual start timestamp")
    actual_duration_min: int = Field(
        ..., ge=1, description="Actual duration in minutes",
    )
    notes: str | None = Field(
        default=None,
        description="Optional notes recorded after completion",
    )
    difficulty: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Difficulty rating between 1 and 5",
    )
    mood: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Mood rating between 1 and 5",
    )


class SessionSkipRequest(ORMModel):
    """Payload to optionally attach notes when skipping a session."""

    notes: str | None = Field(
        default=None,
        description="Reason for skipping the session",
    )

class SprintOverview(BaseModel):
    """Aggregated overview for a sprint (used in /sprints/overview)."""

    # читаем значение из sprint_id, но наружу поле называется id
    id: int = Field(..., alias="sprint_id")
    title: str
    status: SprintStatus

    habits_count: int
    sessions_count: int
    done_sessions: int

    completion_rate: Optional[float] = None
    total_planned_minutes: int
    total_actual_minutes: Optional[int] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,  # важно, чтобы работали и alias, и имя поля
    )