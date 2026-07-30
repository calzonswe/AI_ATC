from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..routes.metrics import (
    active_websocket_connections,
    http_requests_total,
)


class MetricsCollector:
    def __init__(self, max_samples: int = 300):
        self._max_samples = max_samples
        self._llm_latencies: deque = deque(maxlen=max_samples)
        self._llm_tokens_per_sec: deque = deque(maxlen=max_samples)
        self._audio_stt_latencies: deque = deque(maxlen=max_samples)
        self._audio_tts_latencies: deque = deque(maxlen=max_samples)
        self._audio_pipeline_latencies: deque = deque(maxlen=max_samples)
        self._llm_requests_total: int = 0
        self._audio_packets_total: int = 0
        self._start_time: float = time.time()

    def record_llm_request(self, latency_ms: float, tokens_per_sec: float) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._llm_latencies.append({"t": now, "v": latency_ms})
        self._llm_tokens_per_sec.append({"t": now, "v": tokens_per_sec})
        self._llm_requests_total += 1

    def record_audio_pipeline(
        self, stt_ms: float, tts_ms: float, total_ms: float
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._audio_stt_latencies.append({"t": now, "v": stt_ms})
        self._audio_tts_latencies.append({"t": now, "v": tts_ms})
        self._audio_pipeline_latencies.append({"t": now, "v": total_ms})
        self._audio_packets_total += 1

    def get_llm_metrics(self) -> Dict[str, Any]:
        recent = list(self._llm_latencies)
        avg_latency = (
            sum(d["v"] for d in recent) / len(recent) if recent else 0.0
        )
        recent_tps = list(self._llm_tokens_per_sec)
        avg_tps = (
            sum(d["v"] for d in recent_tps) / len(recent_tps) if recent_tps else 0.0
        )
        return {
            "total_requests": self._llm_requests_total,
            "average_latency_ms": round(avg_latency, 1),
            "average_tokens_per_sec": round(avg_tps, 1),
            "latency_samples": recent[-60:] if recent else [],
            "tps_samples": recent_tps[-60:] if recent_tps else [],
            "model": "qwen3:30b",
            "connected": True,
        }

    def get_audio_metrics(self) -> Dict[str, Any]:
        recent_stt = list(self._audio_stt_latencies)
        recent_tts = list(self._audio_tts_latencies)
        recent_total = list(self._audio_pipeline_latencies)
        avg_stt = (
            sum(d["v"] for d in recent_stt) / len(recent_stt) if recent_stt else 0.0
        )
        avg_tts = (
            sum(d["v"] for d in recent_tts) / len(recent_tts) if recent_tts else 0.0
        )
        avg_total = (
            sum(d["v"] for d in recent_total) / len(recent_total) if recent_total else 0.0
        )
        return {
            "total_packets": self._audio_packets_total,
            "average_stt_ms": round(avg_stt, 1),
            "average_tts_ms": round(avg_tts, 1),
            "average_total_ms": round(avg_total, 1),
            "stt_samples": recent_stt[-60:] if recent_stt else [],
            "tts_samples": recent_tts[-60:] if recent_tts else [],
            "pipeline_samples": recent_total[-60:] if recent_total else [],
        }

    def get_system_metrics(self) -> Dict[str, Any]:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        uptime_s = time.time() - self._start_time

        ollama_healthy = self._check_ollama_health()

        return {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024 ** 3), 1),
            "memory_total_gb": round(mem.total / (1024 ** 3), 1),
            "uptime_seconds": round(uptime_s, 1),
            "ollama_connected": ollama_healthy,
            "ollama_url": os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            "active_websocket_connections": self._gauge_value(active_websocket_connections),
        }

    def get_http_metrics(self) -> Dict[str, Any]:
        total = 0
        try:
            for sample in http_requests_total.collect()[0].samples:
                total += int(sample.value)
        except Exception:
            pass
        return {"total_requests": total}

    def get_summary(self) -> Dict[str, Any]:
        llm = self.get_llm_metrics()
        audio = self.get_audio_metrics()
        system = self.get_system_metrics()
        http = self.get_http_metrics()
        return {
            "llm": llm,
            "audio": audio,
            "system": system,
            "http": http,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _check_ollama_health(self) -> bool:
        try:
            import httpx
            url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
            r = httpx.get(f"{url}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _gauge_value(gauge) -> int:
        try:
            return int(gauge.collect()[0].samples[0].value)
        except Exception:
            return 0


class AircraftStore:
    def __init__(self, stale_timeout_s: float = 30.0):
        self._aircraft: Dict[str, dict] = {}
        self._stale_timeout = stale_timeout_s

    def update(self, callsign: str, data: dict) -> None:
        data["last_seen"] = time.time()
        self._aircraft[callsign] = data

    def remove(self, callsign: str) -> None:
        self._aircraft.pop(callsign, None)

    def get_active(self) -> List[dict]:
        now = time.time()
        active = []
        stale_keys = []
        for cs, data in self._aircraft.items():
            if now - data.get("last_seen", 0) > self._stale_timeout:
                stale_keys.append(cs)
                continue
            entry = {
                "callsign": cs,
                "position": data.get("position", {}),
                "motion": data.get("motion", {}),
                "radios": data.get("radios", {}),
                "last_seen_ago_s": round(now - data.get("last_seen", now), 1),
            }
            active.append(entry)
        for cs in stale_keys:
            del self._aircraft[cs]
        return sorted(active, key=lambda a: a["callsign"])

    @property
    def active_count(self) -> int:
        return len(self.get_active())

    def clear(self) -> None:
        self._aircraft.clear()


metrics_collector = MetricsCollector()
aircraft_store = AircraftStore()
