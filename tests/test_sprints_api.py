from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient


def _create_sprint(api_client: TestClient) -> dict:
    payload = {
        "title": "Focus Sprint",
        "goal_text": "Practice algorithms",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=4)).isoformat(),
        "status": "planned",
    }
    response = api_client.post("/sprints", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_habit(api_client: TestClient, sprint_id: int, name: str, target: int) -> dict:
    payload = {
        "sprint_id": sprint_id,
        "name": name,
        "description": f"Habit {name}",
        "target_sessions_per_day": target,
    }
    response = api_client.post(f"/sprints/{sprint_id}/habits", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_session(
    api_client: TestClient,
    sprint_id: int,
    habit_id: int,
    start: datetime,
    planned_minutes: int,
    status: str,
    actual_minutes: int | None = None,
) -> dict:
    payload = {
        "sprint_id": sprint_id,
        "habit_id": habit_id,
        "planned_start": start.isoformat(),
        "planned_duration_min": planned_minutes,
        "status": status,
        "actual_start": start.isoformat() if actual_minutes else None,
        "actual_duration_min": actual_minutes,
    }
    response = api_client.post(f"/sprints/{sprint_id}/sessions", json=payload)
    assert response.status_code == 201
    return response.json()


def test_list_sprints(api_client: TestClient) -> None:
    created = _create_sprint(api_client)

    response = api_client.get("/sprints")
    assert response.status_code == 200
    sprints = response.json()
    assert isinstance(sprints, list)
    assert any(sprint["id"] == created["id"] for sprint in sprints)


def test_sprint_overview_endpoint(api_client: TestClient) -> None:
    sprint = _create_sprint(api_client)
    habit1 = _create_habit(api_client, sprint_id=sprint["id"], name="AM", target=1)
    habit2 = _create_habit(api_client, sprint_id=sprint["id"], name="PM", target=1)

    base_start = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
    _create_session(
        api_client,
        sprint_id=sprint["id"],
        habit_id=habit1["id"],
        start=base_start,
        planned_minutes=50,
        status="done",
        actual_minutes=45,
    )
    _create_session(
        api_client,
        sprint_id=sprint["id"],
        habit_id=habit1["id"],
        start=base_start + timedelta(hours=1),
        planned_minutes=40,
        status="planned",
    )
    _create_session(
        api_client,
        sprint_id=sprint["id"],
        habit_id=habit2["id"],
        start=base_start + timedelta(hours=2),
        planned_minutes=30,
        status="skipped",
    )

    response = api_client.get("/sprints/overview")
    assert response.status_code == 200
    overview = response.json()

    assert len(overview) == 1
    sprint_overview = overview[0]
    assert sprint_overview["sprint_id"] == sprint["id"]
    assert sprint_overview["title"] == sprint["title"]
    assert sprint_overview["status"] == sprint["status"]
    assert sprint_overview["habits_count"] == 2
    assert sprint_overview["sessions_count"] == 3
    assert sprint_overview["done_sessions"] == 1
    assert sprint_overview["total_planned_minutes"] == 120
    assert sprint_overview["total_actual_minutes"] == 45
    assert sprint_overview["completion_rate"] == pytest.approx(1 / 3, rel=1e-6)
