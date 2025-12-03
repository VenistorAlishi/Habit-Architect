from __future__ import annotations

from fastapi.testclient import TestClient


def test_demo_seed_endpoint_creates_sample_data(api_client: TestClient) -> None:
    response = api_client.post("/demo/seed")
    assert response.status_code == 200

    payload = response.json()
    assert "sprint_id" in payload
    assert isinstance(payload["sprint_id"], int)
    assert payload["habits"] == [
        "Morning math drills",
        "Evening recap notes",
    ]
    assert len(payload["sessions"]) == 6

    sprint_id = payload["sprint_id"]

    sprint_response = api_client.get(f"/sprints/{sprint_id}")
    assert sprint_response.status_code == 200
    sprint_data = sprint_response.json()
    assert sprint_data["title"] == "Deep Work Week"

    stats_response = api_client.get(f"/sprints/{sprint_id}/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["total_sessions"] == 6
    assert stats["done_sessions"] == 4
    assert stats["skipped_sessions"] == 2
