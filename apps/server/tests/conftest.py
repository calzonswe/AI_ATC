import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
PARENT = SRC.parent

# Add both parent (for src package) and src itself to sys.path
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.settings import settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.auth_admin_username,
            "password": settings.auth_admin_password,
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
