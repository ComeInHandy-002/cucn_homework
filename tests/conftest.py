from __future__ import annotations

import os
import sys
from pathlib import Path


TEST_DB = Path("test_safety_monitor.db").resolve()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB.as_posix()}")
os.environ.setdefault("MODEL_PATH", "models/test-missing-yolov8s.pt")
os.environ.setdefault("FALLBACK_SCENARIO", "no_ppe")

import pytest
from fastapi.testclient import TestClient

from app.auth import ensure_default_admin
from app.db.database import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
