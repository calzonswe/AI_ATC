from fastapi.testclient import TestClient


class TestWebSocket:
    def test_ping_pong(self, client: TestClient):
        with client.websocket_connect("/ws/v1/telemetry?client_id=test1") as ws:
            ws.send_json({"type": "ping"})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

    def test_unknown_message_type(self, client: TestClient):
        with client.websocket_connect("/ws/v1/telemetry?client_id=test2") as ws:
            ws.send_json({"type": "unknown_type"})
            resp = ws.receive_json()
            assert resp["type"] == "error"

    def test_invalid_json_returns_error(self, client: TestClient):
        with client.websocket_connect("/ws/v1/telemetry?client_id=test3") as ws:
            ws.send_text("not valid json")
            resp = ws.receive_json()
            assert resp["type"] == "error"

    def test_subscribe_channel(self, client: TestClient):
        with client.websocket_connect("/ws/v1/telemetry?client_id=test4") as ws:
            ws.send_json({"type": "subscribe", "channel": "kiax_twr"})
            resp = ws.receive_json()
            assert resp["type"] == "subscribed"
            assert resp["channel"] == "kiax_twr"

    def test_telemetry_ack(self, client: TestClient):
        with client.websocket_connect("/ws/v1/telemetry?client_id=test5") as ws:
            ws.send_json({
                "type": "telemetry",
                "data": {"callsign": "UAL123", "lat": 33.94, "lon": -118.41},
            })
            resp = ws.receive_json()
            assert resp["type"] == "telemetry_ack"
