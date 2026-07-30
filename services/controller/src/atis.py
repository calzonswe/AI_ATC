from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .base import BaseController
from .models import AtisBroadcast, AtisState, ControllerState as CtrlState


class AtisController(BaseController):
    _broadcast: Optional[AtisBroadcast]
    _update_interval_s: float

    def __init__(
        self,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: str,
        update_interval_s: float = 30.0,
    ):
        super().__init__(callsign, frequency, sector_id, airport_icao=airport_icao)
        self._broadcast: Optional[AtisBroadcast] = None
        self._update_interval_s = update_interval_s
        self._last_update_s: float = 0.0
        self._state = CtrlState.ACTIVE
        self._atis_state = AtisState.IDLE

    @property
    def broadcast(self) -> Optional[AtisBroadcast]:
        return self._broadcast

    def update_broadcast(
        self,
        identifier: str,
        metar: str,
        runways_in_use: Optional[List[str]] = None,
        approach_in_use: str = "",
        notices: Optional[List[str]] = None,
    ) -> AtisBroadcast:
        self._broadcast = AtisBroadcast(
            airport_icao=self.airport_icao or "",
            identifier=identifier,
            frequency_mhz=self.frequency,
            timestamp_s=time.time(),
            metar=metar,
            runways_in_use=runways_in_use or [],
            approach_in_use=approach_in_use,
            notices=notices or [],
        )
        self._last_update_s = time.time()
        self._atis_state = AtisState.BROADCASTING
        self.log_status_change(
            "ATIS", None, f"BROADCAST_{identifier}",
            command_type="atis_update",
        )
        self._issue_command(
            "atis_broadcast",
            "ATIS",
            identifier=identifier,
            metar=metar,
            runways=runways_in_use or [],
            instruction=f"ATIS {identifier}: {metar}",
        )
        return self._broadcast

    def get_broadcast_text(self) -> str:
        if not self._broadcast:
            return ""
        parts = [
            f"{self.airport_icao} ATIS {self._broadcast.identifier}",
            self._broadcast.metar,
        ]
        if self._broadcast.runways_in_use:
            parts.append(f"Runways in use: {', '.join(self._broadcast.runways_in_use)}")
        if self._broadcast.approach_in_use:
            parts.append(f"Approach: {self._broadcast.approach_in_use}")
        for notice in self._broadcast.notices:
            parts.append(notice)
        return ". ".join(parts)

    def is_stale(self, max_age_s: float = 120.0) -> bool:
        if not self._broadcast:
            return True
        return (time.time() - self._last_update_s) > max_age_s

    def process(self, dt: float, context: Dict[str, Any]) -> None:
        pass
