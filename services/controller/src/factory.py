from __future__ import annotations

from typing import Any, Dict, List, Optional

from .approach import ApproachController
from .atis import AtisController
from .base import BaseController
from .center import CenterController
from .delivery import ClearanceDeliveryController
from .departure import DepartureController
from .ground import GroundController
from .models import ControllerPosition
from .tower import TowerController


class ControllerFactory:
    @staticmethod
    def create(
        position: ControllerPosition,
        callsign: str,
        frequency: float,
        sector_id: str,
        airport_icao: Optional[str] = None,
        runways: Optional[List[str]] = None,
        facility_name: Optional[str] = None,
    ) -> BaseController:
        if position == ControllerPosition.GROUND:
            if not airport_icao:
                raise ValueError("airport_icao required for GroundController")
            return GroundController(
                callsign=callsign,
                frequency=frequency,
                sector_id=sector_id,
                airport_icao=airport_icao,
            )
        elif position == ControllerPosition.TOWER:
            if not airport_icao:
                raise ValueError("airport_icao required for TowerController")
            return TowerController(
                callsign=callsign,
                frequency=frequency,
                sector_id=sector_id,
                airport_icao=airport_icao,
                runways=runways,
            )
        elif position == ControllerPosition.DEPARTURE:
            if not airport_icao:
                raise ValueError("airport_icao required for DepartureController")
            return DepartureController(
                callsign=callsign,
                frequency=frequency,
                sector_id=sector_id,
                airport_icao=airport_icao,
            )
        elif position == ControllerPosition.APPROACH:
            if not airport_icao:
                raise ValueError("airport_icao required for ApproachController")
            return ApproachController(
                callsign=callsign,
                frequency=frequency,
                sector_id=sector_id,
                airport_icao=airport_icao,
            )
        elif position == ControllerPosition.ATIS:
            if not airport_icao:
                raise ValueError("airport_icao required for AtisController")
            return AtisController(
                callsign=callsign,
                frequency=frequency,
                sector_id=sector_id,
                airport_icao=airport_icao,
            )
        elif position == ControllerPosition.CENTER:
            return CenterController(
                callsign=callsign,
                frequency=frequency,
                sector_id=sector_id,
                facility_name=facility_name or "Center",
            )
        elif position == ControllerPosition.DELIVERY:
            if not airport_icao:
                raise ValueError("airport_icao required for ClearanceDeliveryController")
            return ClearanceDeliveryController(
                callsign=callsign,
                frequency=frequency,
                sector_id=sector_id,
                airport_icao=airport_icao,
            )
        else:
            raise ValueError(f"Unknown controller position: {position}")

    @staticmethod
    def create_all_for_airport(
        icao: str,
        sector_id_prefix: str = "",
        frequencies: Optional[Dict[str, float]] = None,
        runways: Optional[List[str]] = None,
    ) -> Dict[ControllerPosition, BaseController]:
        freqs = frequencies or {}
        controllers: Dict[ControllerPosition, BaseController] = {}
        sid = sector_id_prefix or icao

        controllers[ControllerPosition.GROUND] = ControllerFactory.create(
            ControllerPosition.GROUND,
            callsign=f"{icao}_GND",
            frequency=freqs.get("ground", 121.8),
            sector_id=f"{sid}_GND",
            airport_icao=icao,
        )
        controllers[ControllerPosition.TOWER] = ControllerFactory.create(
            ControllerPosition.TOWER,
            callsign=f"{icao}_TWR",
            frequency=freqs.get("tower", 118.5),
            sector_id=f"{sid}_TWR",
            airport_icao=icao,
            runways=runways,
        )
        controllers[ControllerPosition.DEPARTURE] = ControllerFactory.create(
            ControllerPosition.DEPARTURE,
            callsign=f"{icao}_DEP",
            frequency=freqs.get("departure", 124.3),
            sector_id=f"{sid}_DEP",
            airport_icao=icao,
        )
        controllers[ControllerPosition.APPROACH] = ControllerFactory.create(
            ControllerPosition.APPROACH,
            callsign=f"{icao}_APP",
            frequency=freqs.get("approach", 119.7),
            sector_id=f"{sid}_APP",
            airport_icao=icao,
        )
        controllers[ControllerPosition.ATIS] = ControllerFactory.create(
            ControllerPosition.ATIS,
            callsign=f"{icao}_ATIS",
            frequency=freqs.get("atis", 128.425),
            sector_id=f"{sid}_ATIS",
            airport_icao=icao,
        )
        controllers[ControllerPosition.CENTER] = ControllerFactory.create(
            ControllerPosition.CENTER,
            callsign=f"{sid}_CTR",
            frequency=freqs.get("center", 135.5),
            sector_id=f"{sid}_CTR",
        )
        controllers[ControllerPosition.DELIVERY] = ControllerFactory.create(
            ControllerPosition.DELIVERY,
            callsign=f"{icao}_DEL",
            frequency=freqs.get("delivery", 121.95),
            sector_id=f"{sid}_DEL",
            airport_icao=icao,
        )
        return controllers

    @staticmethod
    def create_from_db_airports(
        airports: List[Dict[str, Any]],
    ) -> Dict[str, Dict[ControllerPosition, BaseController]]:
        result: Dict[str, Dict[ControllerPosition, BaseController]] = {}
        for ap in airports:
            icao = ap.get("icao_code", "")
            if not icao:
                continue
            runways_raw = ap.get("runways", [])
            runway_ids = [r.get("identifier", "") for r in runways_raw if r.get("identifier")]
            freqs_raw = ap.get("frequencies", [])
            freq_map: Dict[str, float] = {}
            for f in freqs_raw:
                ftype = f.get("type", "").lower()
                fmhz = f.get("frequency_mhz", 0.0)
                if ftype and fmhz > 0:
                    freq_map[ftype] = fmhz
            result[icao] = ControllerFactory.create_all_for_airport(
                icao,
                frequencies=freq_map,
                runways=runway_ids,
            )
        return result

    @staticmethod
    def create_from_db_controllers(
        db_controllers: List[Dict[str, Any]],
    ) -> Dict[str, BaseController]:
        result: Dict[str, BaseController] = {}
        for ctrl in db_controllers:
            cs = ctrl.get("callsign", "")
            freq = ctrl.get("frequency_mhz", 0.0)
            ctype = ctrl.get("type", "CENTER").upper()
            icao = ctrl.get("airport_icao")
            if not cs or freq <= 0:
                continue
            if ctype == "GROUND":
                if not icao:
                    continue
                result[cs] = GroundController(cs, freq, f"{icao}_GND", icao)
            elif ctype == "TOWER":
                if not icao:
                    continue
                result[cs] = TowerController(cs, freq, f"{icao}_TWR", icao)
            elif ctype == "DEPARTURE":
                if not icao:
                    continue
                result[cs] = DepartureController(cs, freq, f"{icao}_DEP", icao)
            elif ctype == "APPROACH":
                if not icao:
                    continue
                result[cs] = ApproachController(cs, freq, f"{icao}_APP", icao)
            elif ctype == "ATIS":
                if not icao:
                    continue
                result[cs] = AtisController(cs, freq, f"{icao}_ATIS", icao)
            elif ctype == "CENTER":
                result[cs] = CenterController(cs, freq, f"{cs}_CTR")
            elif ctype == "DELIVERY":
                if not icao:
                    continue
                result[cs] = ClearanceDeliveryController(cs, freq, f"{icao}_DEL", icao)
        return result
