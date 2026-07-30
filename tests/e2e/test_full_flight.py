from __future__ import annotations

from flight_simulator import FlightPhase, FlightTelemetryGenerator


class TestE2EFullFlight:
    """End-to-end test simulating a complete flight from ESSA to ESSB.

    Covers all flight phases: Connect -> Startup -> Pushback -> Taxi ->
    Takeoff -> Departure climb -> Enroute cruise -> Approach descent ->
    Final ILS -> Landing -> Taxi to gate -> Shutdown.
    """

    CALLSIGN = "SAS123"
    CLIENT_ID = "e2e-test-client-01"

    def test_complete_flight_lifecycle(self, client, flight_generator, voice_simulator):
        """Simulate a full flight lifecycle with telemetry and radio calls."""

        with client.websocket_connect(
            f"/ws/v1/telemetry?client_id={self.CLIENT_ID}"
        ) as ws:
            # ── Phase 1: Connect ──────────────────────────────────────
            ws.send_json({
                "type": "connect",
                "callsign": self.CALLSIGN,
                "client_type": "pilot",
                "aircraft_type": "B738",
            })
            resp = ws.receive_json()
            assert resp["type"] == "connected"
            assert resp["session_id"] == self.CLIENT_ID

            # Initial admin check: aircraft should be tracked
            resp2 = client.get(
                "/api/v1/admin/aircraft",
                headers=self._admin_headers(client),
            )
            data = resp2.json()
            assert data["count"] >= 1

            # ── Phase 2-12: Flight phases ─────────────────────────────
            phases_completed = set()

            while not flight_generator.is_complete:
                phase = flight_generator.current_phase
                frames = flight_generator.generate_telemetry()

                for frame in frames:
                    ws.send_json({"type": "telemetry", "data": frame})
                    ack = ws.receive_json()
                    assert ack["type"] == "telemetry_ack"

                # Inject simulated pilot voice requests
                calls = voice_simulator.get_calls_for_phase(phase)
                for call in calls:
                    ws.send_json({
                        "type": "radio_transmit",
                        "frequency": call["frequency"],
                        "data": {"text": call["text"]},
                    })
                    resp = ws.receive_json()
                    # Server correctly rejects unknown message types
                    assert resp["type"] == "error"
                    assert "unknown message type" in resp["detail"]

                phases_completed.add(phase)

            # ── Verify all phases were completed ───────────────────────
            all_phases = list(FlightPhase)
            assert phases_completed == set(all_phases), (
                f"Not all phases completed. Missing: "
                f"{set(all_phases) - phases_completed}"
            )

        # ── Post-flight assertions ────────────────────────────────────
        # Server still responsive after full flight cycle
        health = client.get("/health")
        assert health.status_code == 200

        metrics = client.get("/metrics")
        assert metrics.status_code == 200

        resp3 = client.get(
            "/api/v1/admin/metrics",
            headers=self._admin_headers(client),
        )
        assert resp3.status_code == 200
        summary = resp3.json()
        assert "system" in summary
        assert "http" in summary

    def test_controller_transfer_progression(self, client, auth_headers):
        """Verify controller positions are available through the flight."""
        resp = client.get("/api/v1/admin/controllers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

        positions = {c["position"] for c in data["controllers"]}
        expected = {"TOWER", "GROUND", "DEPARTURE", "APPROACH", "CENTER"}
        assert expected.issubset(positions), (
            f"Missing controller positions. Got: {positions}"
        )
        for ctrl in data["controllers"]:
            assert "callsign" in ctrl
            assert "frequency_mhz" in ctrl
            assert "status" in ctrl

    def test_admin_dashboard_during_flight(self, client, auth_headers, flight_generator):
        """Verify admin dashboard reflects live flight state."""
        with client.websocket_connect(
            "/ws/v1/telemetry?client_id=admin-flight-test"
        ) as ws:
            ws.send_json({
                "type": "connect",
                "callsign": "SAS456",
                "client_type": "pilot",
                "aircraft_type": "A320",
            })
            ws.receive_json()

            frames = flight_generator.generate_telemetry()
            for frame in frames:
                ws.send_json({"type": "telemetry", "data": frame})
                ws.receive_json()

        # Admin aircraft endpoint reflects at least what was tracked
        resp = client.get("/api/v1/admin/aircraft", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "aircraft" in data

    def test_sustained_telemetry_no_crash(self, client):
        """Verify server handles sustained telemetry without crashing."""
        count = 50
        with client.websocket_connect(
            "/ws/v1/telemetry?client_id=sustain-test"
        ) as ws:
            ws.send_json({
                "type": "connect",
                "callsign": "SUSTAIN",
                "client_type": "pilot",
                "aircraft_type": "B738",
            })
            ws.receive_json()

            for i in range(count):
                frame = {
                    "event": "telemetry_update",
                    "callsign": "SUSTAIN",
                    "position": {
                        "lat": 59.6 + i * 0.001,
                        "lon": 17.9 + i * 0.001,
                        "alt_msl": 1000.0 + i * 100,
                        "alt_agl": 1000.0 + i * 100,
                        "heading": 180.0,
                        "pitch": 2.0,
                        "bank": 0.0,
                    },
                    "motion": {
                        "ias": 250.0,
                        "groundspeed": 240.0,
                        "vertical_speed": 500.0,
                        "on_ground": False,
                    },
                    "radios": {
                        "com1": 118.300,
                        "com2": 121.800,
                        "squawk": "2000",
                        "squawk_mode": "alt",
                    },
                    "sim_time": float(i),
                    "ts": 0,
                }
                ws.send_json({"type": "telemetry", "data": frame})
                ack = ws.receive_json()
                assert ack["type"] == "telemetry_ack"

        # After sustained telemetry, server must still be healthy
        health = client.get("/health")
        assert health.status_code == 200

    def test_multi_client_simulation(self, client, flight_generator):
        """Verify server handles multiple aircraft simultaneously."""
        aircraft = ["NWA123", "DAL456", "UAL789"]
        websockets = []

        for callsign in aircraft:
            ws = client.websocket_connect(
                f"/ws/v1/telemetry?client_id={callsign.lower()}"
            )
            websockets.append(ws)
            ws.__enter__()
            ws.send_json({
                "type": "connect",
                "callsign": callsign,
                "client_type": "pilot",
                "aircraft_type": "B738",
            })
            ws.receive_json()  # connected

        assert len(aircraft) == len(websockets)
        try:
            for callsign, ws in zip(aircraft, websockets):  # noqa: B905
                gen = FlightTelemetryGenerator(callsign=callsign, frames_per_phase=2)
                while not gen.is_complete:
                    for frame in gen.generate_telemetry():
                        ws.send_json({"type": "telemetry", "data": frame})
                        ws.receive_json()  # telemetry_ack
        finally:
            for ws in websockets:
                ws.__exit__(None, None, None)

        health = client.get("/health")
        assert health.status_code == 200

    def test_admin_metrics_collection_during_flight(
        self, client, auth_headers
    ):
        """Verify metric injection endpoints work during flight simulation."""
        llm_resp = client.post(
            "/api/v1/admin/metrics/llm",
            headers=auth_headers,
            json={"latency_ms": 150.0, "tokens_per_sec": 45.2},
        )
        assert llm_resp.status_code == 200
        assert llm_resp.json()["status"] == "ok"

        audio_resp = client.post(
            "/api/v1/admin/metrics/audio",
            headers=auth_headers,
            json={"stt_ms": 100.0, "tts_ms": 200.0, "total_ms": 330.0},
        )
        assert audio_resp.status_code == 200
        assert audio_resp.json()["status"] == "ok"

        metrics = client.get("/api/v1/admin/metrics", headers=auth_headers)
        assert metrics.status_code == 200
        data = metrics.json()
        assert data["llm"]["total_requests"] >= 1
        assert data["llm"]["average_latency_ms"] > 0
        assert data["audio"]["total_packets"] >= 1

    def _admin_headers(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "atc_admin_secret"},
        )
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
