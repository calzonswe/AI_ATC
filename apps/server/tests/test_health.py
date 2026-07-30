from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert data["service"] == "openatc-server"

    def test_health_is_public(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
