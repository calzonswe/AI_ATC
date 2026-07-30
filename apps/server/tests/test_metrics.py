from fastapi.testclient import TestClient


class TestMetricsEndpoint:
    def test_metrics_returns_prometheus(self, client: TestClient):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "# HELP" in body
        assert "# TYPE" in body
        assert "atc_http_requests_total" in body

    def test_metrics_is_public(self, client: TestClient):
        resp = client.get("/metrics")
        assert resp.status_code == 200
