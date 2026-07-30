from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_SRC = PROJECT_ROOT / "apps" / "server" / "src"
PARENT = SERVER_SRC.parent
os.chdir(str(SERVER_SRC))

if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))
if str(SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(SERVER_SRC))

E2E_DIR = Path(__file__).resolve().parent
if str(E2E_DIR) not in sys.path:
    sys.path.insert(0, str(E2E_DIR))

import pytest
from fastapi.testclient import TestClient
from flight_simulator import FlightTelemetryGenerator, PilotVoiceSimulator
from src.admin.metrics_collector import aircraft_store  # noqa: E402
from src.main import app  # noqa: E402
from src.settings import settings  # noqa: E402


@pytest.fixture(autouse=True)
def clear_aircraft_store():
    aircraft_store.clear()
    yield


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


@pytest.fixture
def flight_generator():
    return FlightTelemetryGenerator(callsign="SAS123", frames_per_phase=3)


@pytest.fixture
def voice_simulator():
    return PilotVoiceSimulator()
