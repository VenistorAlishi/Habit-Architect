from fastapi.testclient import TestClient

import os
import sys

# add project root to sys.path so "app" can be imported
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.main import app


client = TestClient(app)


def test_read_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
