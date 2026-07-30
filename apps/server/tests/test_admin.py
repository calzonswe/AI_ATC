from __future__ import annotations

from fastapi.testclient import TestClient
from src.admin.metrics_collector import aircraft_store


class TestAdminDashboard:
    def test_dashboard_page_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/admin/dashboard")
        assert resp.status_code == 401

    def test_dashboard_page_returns_html(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "OpenATC Admin Dashboard" in resp.text

    def test_static_css_accessible(self, client: TestClient):
        resp = client.get("/admin/static/admin.css")
        assert resp.status_code == 200
        ct = resp.headers["content-type"]
        assert "text/css" in ct or "stylesheet" in ct

    def test_static_js_accessible(self, client: TestClient):
        resp = client.get("/admin/static/admin.js")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "javascript" in ct or ct.startswith("text/")


class TestAdminMetrics:
    def test_metrics_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/admin/metrics")
        assert resp.status_code == 401

    def test_metrics_returns_summary(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/admin/metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data
        assert "audio" in data
        assert "system" in data
        assert "http" in data
        assert "timestamp" in data

    def test_metrics_llm_section(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/admin/metrics", headers=auth_headers)
        data = resp.json()
        llm = data["llm"]
        assert "total_requests" in llm
        assert "average_latency_ms" in llm
        assert "average_tokens_per_sec" in llm
        assert "model" in llm
        assert llm["model"] == "qwen3:30b"

    def test_metrics_audio_section(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/admin/metrics", headers=auth_headers)
        data = resp.json()
        audio = data["audio"]
        assert "total_packets" in audio
        assert "average_stt_ms" in audio
        assert "average_tts_ms" in audio
        assert "average_total_ms" in audio

    def test_metrics_system_section(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/admin/metrics", headers=auth_headers)
        data = resp.json()
        system = data["system"]
        assert "cpu_percent" in system
        assert "memory_percent" in system
        assert "ollama_connected" in system
        assert "uptime_seconds" in system


class TestAdminAircraft:
    def test_aircraft_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/admin/aircraft")
        assert resp.status_code == 401

    def test_aircraft_empty_initially(self, client: TestClient, auth_headers):
        aircraft_store.clear()
        resp = client.get("/api/v1/admin/aircraft", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["aircraft"] == []

    def test_aircraft_with_data(self, client: TestClient, auth_headers):
        aircraft_store.clear()
        aircraft_store.update("SAS123", {
            "callsign": "SAS123",
            "position": {"lat": 59.65, "lon": 17.92, "alt_msl_ft": 35000, "heading_mag": 180},
            "motion": {"groundspeed_kn": 450, "on_ground": False},
            "radios": {"com1_freq_mhz": 118.300, "transponder_code": "2000"},
        })
        resp = client.get("/api/v1/admin/aircraft", headers=auth_headers)
        data = resp.json()
        assert data["count"] == 1
        assert data["aircraft"][0]["callsign"] == "SAS123"
        assert data["aircraft"][0]["position"]["lat"] == 59.65
        aircraft_store.clear()


class TestAdminControllers:
    def test_controllers_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/admin/controllers")
        assert resp.status_code == 401

    def test_controllers_returns_list(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/admin/controllers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert "websocket_connections" in data
        for ctrl in data["controllers"]:
            assert "callsign" in ctrl
            assert "position" in ctrl
            assert "frequency_mhz" in ctrl
            assert "status" in ctrl

    def test_controllers_has_tower(self, client: TestClient, auth_headers):
        resp = client.get("/api/v1/admin/controllers", headers=auth_headers)
        data = resp.json()
        positions = {c["position"] for c in data["controllers"]}
        assert "TOWER" in positions
        assert "GROUND" in positions
        assert "DEPARTURE" in positions


class TestAdminMetricsInjection:
    def test_record_llm_metric(self, client: TestClient, auth_headers):
        resp = client.post(
            "/api/v1/admin/metrics/llm",
            headers=auth_headers,
            json={"latency_ms": 250.0, "tokens_per_sec": 35.2},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # Verify it was recorded
        metrics = client.get("/api/v1/admin/metrics", headers=auth_headers).json()
        assert metrics["llm"]["total_requests"] >= 1

    def test_record_audio_metric(self, client: TestClient, auth_headers):
        resp = client.post(
            "/api/v1/admin/metrics/audio",
            headers=auth_headers,
            json={"stt_ms": 120.0, "tts_ms": 180.0, "total_ms": 350.0},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        metrics = client.get("/api/v1/admin/metrics", headers=auth_headers).json()
        assert metrics["audio"]["total_packets"] >= 1


class TestAdminSSE:
    def test_sse_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/admin/events")
        assert resp.status_code == 401

    def test_sse_endpoint_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/admin/events")
        assert resp.status_code == 401


class TestAircraftStore:
    def test_clear_and_update(self):
        aircraft_store.clear()
        assert aircraft_store.active_count == 0
        aircraft_store.update("TEST01", {"type": "test"})
        assert aircraft_store.active_count == 1
        aircraft_store.remove("TEST01")
        assert aircraft_store.active_count == 0

    def test_stale_aircraft_removed(self):
        from src.admin.metrics_collector import AircraftStore
        store = AircraftStore(stale_timeout_s=0.001)
        store.update("STALE", {"data": "old"})
        import time
        time.sleep(0.005)
        assert len(store.get_active()) == 0
