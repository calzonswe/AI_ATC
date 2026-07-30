from fastapi.testclient import TestClient
from src.auth.service import jwt_service
from src.settings import settings


class TestAuthLogin:
    def test_login_success(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": settings.auth_admin_username,
                "password": settings.auth_admin_password,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105

    def test_login_invalid_password(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": settings.auth_admin_username, "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_login_invalid_user(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "anything"},
        )
        assert resp.status_code == 401


class TestAuthRefresh:
    def test_refresh_success(self, client: TestClient):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": settings.auth_admin_username,
                "password": settings.auth_admin_password,
            },
        )
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token_here"},
        )
        assert resp.status_code == 401


class TestJWTService:
    def test_create_and_validate_access_token(self):
        token = jwt_service.create_access_token("testuser")
        payload = jwt_service.validate_access_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["type"] == "access"

    def test_create_and_validate_refresh_token(self):
        token = jwt_service.create_refresh_token("testuser")
        payload = jwt_service.validate_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["type"] == "refresh"

    def test_access_token_not_valid_as_refresh(self):
        token = jwt_service.create_access_token("testuser")
        payload = jwt_service.validate_refresh_token(token)
        assert payload is None

    def test_refresh_token_not_valid_as_access(self):
        token = jwt_service.create_refresh_token("testuser")
        payload = jwt_service.validate_access_token(token)
        assert payload is None

    def test_invalid_token_returns_none(self):
        assert jwt_service.validate_access_token("garbage") is None
        assert jwt_service.validate_refresh_token("garbage") is None
