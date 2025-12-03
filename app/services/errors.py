from __future__ import annotations

from enum import Enum

from fastapi import HTTPException, status

from app.schemas import ErrorResponse


class ErrorCode(str, Enum):
    """Canonical API error identifiers."""

    SPRINT_NOT_FOUND = "SPRINT_NOT_FOUND"
    HABIT_NOT_FOUND = "HABIT_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SPRINT_ID_MISMATCH = "SPRINT_ID_MISMATCH"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


def build_error(
    *,
    code: ErrorCode,
    status_code: int,
    message: str,
    details: dict | None = None,
) -> HTTPException:
    """Return an HTTPException with a typed ErrorResponse payload."""

    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(code=code, message=message, details=details).model_dump(),
    )
