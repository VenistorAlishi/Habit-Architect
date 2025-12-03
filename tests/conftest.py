from __future__ import annotations

from typing import Iterator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import engine, init_db   # ИМПОРТИРУЕМ ПОСЛЕ ПРАВКИ sys.path
from app.main import app


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "habit_architect.db"


@pytest.fixture()
def api_client() -> Iterator[TestClient]:
    """Provide a clean FastAPI TestClient with a freshly initialized DB."""
    engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()

    init_db()

    with TestClient(app) as client:
        yield client
