from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseController
from .models import ControllerPosition
from .vector_store import VectorStore


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class PromptContext:
    controller: BaseController
    aircraft_state: Dict[str, dict] = field(default_factory=dict)
    weather: Dict[str, dict] = field(default_factory=dict)
    airports: Dict[str, dict] = field(default_factory=dict)
    sectors: List[dict] = field(default_factory=list)
    conflicts: List[dict] = field(default_factory=list)
    navigation: Optional[dict] = None
    local_procedures: Optional[dict] = None


@dataclass
class RadioCallPrompt:
    system_prompt: str
    context_prompt: str
    full_prompt: str
    estimated_tokens: int


@dataclass
class IssuedClearance:
    type: str
    route: Optional[List[str]] = None
    hold_short: Optional[str] = None
    altitude_ft: Optional[int] = None
    heading_deg: Optional[float] = None
    speed_kn: Optional[int] = None
    runway: Optional[str] = None
    sid: Optional[str] = None
    star: Optional[str] = None
    approach: Optional[str] = None
    frequency: Optional[float] = None
    squawk: Optional[str] = None


@dataclass
class LlmOutput:
    readback_correct: bool
    phraseology_text: str
    issued_clearance: Optional[IssuedClearance] = None


# ──────────────────────────────────────────────
# ICAO Phraseology Templates
# ──────────────────────────────────────────────

ICAO_SYSTEM_PROMPTS: Dict[ControllerPosition, str] = {
    ControllerPosition.GROUND: (
        "You are an ATC Ground Controller. Use ICAO standard phraseology.\n"
        "Rules:\n"
        "- Prefix all instructions with the aircraft callsign.\n"
        "- Use 'START-UP APPROVED', 'PUSHBACK APPROVED [direction]', "
        "'TAXI TO RUNWAY [runway] VIA [route]'.\n"
        "- Use 'HOLD SHORT OF RUNWAY [runway]'.\n"
        "- Use 'CONTACT TOWER [frequency]' for handoff.\n"
        "- Readback must be confirmed with 'READBACK CORRECT' or "
        "'READBACK INCORRECT, [correction]'.\n"
        "- Respond to pilot readback: correct it if wrong, "
        "or confirm with '<callsign>, READBACK CORRECT'."
    ),
    ControllerPosition.TOWER: (
        "You are an ATC Tower Controller. Use ICAO standard phraseology.\n"
        "Rules:\n"
        "- Use 'LINE UP AND WAIT RUNWAY [runway]'.\n"
        "- Use 'CLEARED FOR TAKEOFF RUNWAY [runway] [wind]'.\n"
        "- Use 'CLEARED TO LAND RUNWAY [runway]'.\n"
        "- Use 'GO AROUND' for missed approach.\n"
        "- Use 'CONTACT DEPARTURE [frequency]' for departing handoff.\n"
        "- Use 'CONTACT GROUND [frequency]' after landing.\n"
        "- Readback must be confirmed with 'READBACK CORRECT' or "
        "'READBACK INCORRECT, [correction]'."
    ),
    ControllerPosition.DEPARTURE: (
        "You are an ATC Departure Controller. Use ICAO standard phraseology.\n"
        "Rules:\n"
        "- Use 'CLIMB VIA SID [name]' or 'CLIMB TO [altitude]'.\n"
        "- Use 'TURN LEFT/RIGHT HEADING [degrees]' for radar vectors.\n"
        "- Use 'CONTACT CENTER [frequency]' for handoff.\n"
        "- Readback must be confirmed with 'READBACK CORRECT'."
    ),
    ControllerPosition.APPROACH: (
        "You are an ATC Approach Controller. Use ICAO standard phraseology.\n"
        "Rules:\n"
        "- Use 'FLY HEADING [degrees]' for radar vectors.\n"
        "- Use 'DESCEND TO [altitude]'.\n"
        "- Use 'CLEARED ILS APPROACH RUNWAY [runway]'.\n"
        "- Use 'HOLD AT [fix] [altitude]' with expected approach time.\n"
        "- Use 'CONTACT TOWER [frequency]' for handoff.\n"
        "- Readback must be confirmed with 'READBACK CORRECT'."
    ),
    ControllerPosition.CENTER: (
        "You are an ATC Area/Enroute Controller. Use ICAO standard phraseology.\n"
        "Rules:\n"
        "- Use 'CLIMB TO [altitude]' or 'DESCEND TO [altitude]'.\n"
        "- Use 'MAINTAIN [altitude]'.\n"
        "- Use 'CONTACT [next_controller] [frequency]' for handoff.\n"
        "- Readback must be confirmed with 'READBACK CORRECT'."
    ),
    ControllerPosition.ATIS: (
        "You are an ATIS broadcast system. Use ICAO standard phraseology.\n"
        "Rules:\n"
        "- Format: '[airport] ATIS [identifier] [time] [wind] [visibility] "
        "[weather] [clouds] [temperature/dewpoint] [QNH] [runways] "
        "[approach] [notices]. ADVISE ON INITIAL CONTACT YOU HAVE [identifier]'.\n"
        "- Do not expect or respond to readback (one-way broadcast).\n"
        "- Keep concise and use standard METAR abbreviations."
    ),
    ControllerPosition.DELIVERY: (
        "You are a Clearance Delivery Controller. Use ICAO standard phraseology.\n"
        "Rules:\n"
        "- Use CRAFT format: 'CLEARED TO [destination] VIA [SID] DEPARTURE, "
        "CLIMB TO [altitude] FT, DEPARTURE FREQUENCY [freq], SQUAWK [code]'.\n"
        "- Use 'REQUEST READBACK' after issuing clearance.\n"
        "- Use 'READBACK CORRECT' to confirm, "
        "'READBACK INCORRECT, SAY AGAIN CLEARANCE' to reject.\n"
        "- Use 'HOLD AT [fix] [altitude] [direction] TURNS' for holding.\n"
        "- Use 'MISSED APPROACH [point], CLIMB TO [altitude], "
        "CONTACT [controller] [freq]' for missed approach.\n"
        "- Use 'CONTACT GROUND [freq]' after readback verified.\n"
        "- Readback must contain destination, SID, altitude, and squawk."
    ),
}


# ──────────────────────────────────────────────
# PromptEngine
# ──────────────────────────────────────────────

class PromptEngine:
    def __init__(self, max_tokens: int = 2048,
                 vector_store: Optional[VectorStore] = None):
        self.max_tokens = max_tokens
        self._chars_per_token = 4.0
        self._vector_store = vector_store

    def build_system_prompt(self, position: ControllerPosition) -> str:
        return ICAO_SYSTEM_PROMPTS.get(
            position,
            "You are an ATC Controller. Use ICAO standard phraseology.",
        )

    def build_radio_call_prompt(self, context: PromptContext) -> RadioCallPrompt:
        if self._vector_store and not context.local_procedures:
            enriched = self._enrich_from_vector_store(context)
            if enriched:
                context.local_procedures = enriched
        system = self.build_system_prompt(self._get_position(context.controller))
        context_str = self._build_context(context)
        full = f"{system}\n\n=== CURRENT SITUATION ===\n{context_str}"

        est = self._estimate_tokens(full)
        if est > self.max_tokens:
            context_str = self.minimize_tokens(context_str, self.max_tokens - self._estimate_tokens(system) - 50)
            full = f"{system}\n\n=== CURRENT SITUATION ===\n{context_str}"
            est = self._estimate_tokens(full)

        return RadioCallPrompt(
            system_prompt=system,
            context_prompt=context_str,
            full_prompt=full,
            estimated_tokens=est,
        )

    def minimize_tokens(self, text: str, target_tokens: int = 512) -> str:
        target_chars = int(target_tokens * self._chars_per_token)
        if len(text) <= target_chars:
            return text

        lines = text.split("\n")
        kept: List[str] = []
        for line in lines:
            stripped = self._strip_empties(line)
            if stripped:
                kept.append(stripped)

        result = "\n".join(kept)
        if len(result) <= target_chars:
            return result

        # Abbreviate keys
        abbrev = {
            "callsign": "cs",
            "aircraft": "ac",
            "position": "pos",
            "altitude": "alt",
            "groundspeed": "gs",
            "vertical_speed": "vs",
            "airport": "ap",
            "runway": "rwy",
            "frequency": "freq",
            "departure": "dep",
            "arrival": "arr",
            "heading": "hdg",
            "temperature": "temp",
            "visibility": "vis",
            "precipitation": "precip",
            "thunderstorm": "ts",
            "identifier": "id",
        }
        for long, short in abbrev.items():
            result = result.replace(long, short)

        if len(result) <= target_chars:
            return result

        # Drop non-essential sections
        sections = result.split("\n\n")
        priority_order = ["AIRPORT", "AIRCRAFT", "CONFLICT", "WEATHER", "NAVIGATION"]
        prioritized: List[str] = []
        other: List[str] = []
        for sec in sections:
            matched = False
            for pri in priority_order:
                if sec.startswith(pri) or sec.startswith(pri.lower()):
                    prioritized.append(sec)
                    matched = True
                    break
            if not matched:
                other.append(sec)

        # Keep aircraft only for controlled ones, trim details
        trimmed: List[str] = []
        remaining = target_chars
        for sec in prioritized:
            if len("\n\n".join(trimmed + [sec])) <= remaining:
                trimmed.append(sec)

        # Fill remaining space with other sections
        for sec in other:
            if len("\n\n".join(trimmed + [sec])) <= remaining:
                trimmed.append(sec)

        result = "\n\n".join(trimmed)

        if len(result) > target_chars:
            result = result[:target_chars]

        return result

    def parse_llm_response(self, response: str) -> LlmOutput:
        cleaned = response.strip()

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(1)
        else:
            # Try to find JSON object directly
            brace_start = cleaned.find("{")
            brace_end = cleaned.rfind("}")
            if brace_start != -1 and brace_end != -1:
                cleaned = cleaned[brace_start : brace_end + 1]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return LlmOutput(
                readback_correct=False,
                phraseology_text=cleaned,
            )

        readback = data.get("readback_correct", False)
        if not isinstance(readback, bool):
            readback = str(readback).lower() in ("true", "1", "yes")

        phraseology = data.get("phraseology_text", "")
        if not isinstance(phraseology, str):
            phraseology = str(phraseology)

        clearance_data = data.get("issued_clearance")
        clearance: Optional[IssuedClearance] = None
        if isinstance(clearance_data, dict):
            try:
                clearance = IssuedClearance(
                    type=clearance_data.get("type", ""),
                    route=clearance_data.get("route"),
                    hold_short=clearance_data.get("hold_short"),
                    altitude_ft=clearance_data.get("altitude_ft"),
                    heading_deg=clearance_data.get("heading_deg"),
                    speed_kn=clearance_data.get("speed_kn"),
                    runway=clearance_data.get("runway"),
                    sid=clearance_data.get("sid"),
                    star=clearance_data.get("star"),
                    approach=clearance_data.get("approach"),
                    frequency=clearance_data.get("frequency"),
                    squawk=clearance_data.get("squawk"),
                )
            except (TypeError, ValueError):
                pass

        return LlmOutput(
            readback_correct=readback,
            phraseology_text=phraseology,
            issued_clearance=clearance,
        )

    def format_llm_request(self, context: PromptContext) -> Dict[str, Any]:
        prompt = self.build_radio_call_prompt(context)
        return {
            "model": "",
            "prompt": prompt.full_prompt,
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "readback_correct": {"type": "boolean"},
                    "phraseology_text": {"type": "string"},
                    "issued_clearance": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "route": {"type": "array", "items": {"type": "string"}},
                            "hold_short": {"type": "string"},
                            "altitude_ft": {"type": "integer"},
                            "heading_deg": {"type": "number"},
                            "speed_kn": {"type": "integer"},
                            "runway": {"type": "string"},
                            "sid": {"type": "string"},
                            "star": {"type": "string"},
                            "approach": {"type": "string"},
                            "frequency": {"type": "number"},
                            "squawk": {"type": "string"},
                        },
                        "required": ["type"],
                    },
                },
                "required": ["readback_correct", "phraseology_text"],
            },
        }

    def validate_output(self, output: LlmOutput) -> List[str]:
        errors: List[str] = []
        if not output.phraseology_text:
            errors.append("phraseology_text is empty")
        if output.issued_clearance:
            if not output.issued_clearance.type:
                errors.append("issued_clearance.type is empty")
        return errors

    # ── Private helpers ──

    def _enrich_from_vector_store(self, context: PromptContext) -> Optional[dict]:
        store = self._vector_store
        if not store:
            return None
        controller = context.controller
        airport = controller.airport_icao or ""
        pos = self._get_position(controller)
        pos_value = pos.value.upper() if pos else ""

        default_queries = {
            "GROUND": "taxi pushback hold start-up",
            "TOWER": "takeoff landing line up go around",
            "DEPARTURE": "departure SID climb radar vector",
            "APPROACH": "approach ILS holding descend vector",
            "CENTER": "enroute climb descent handoff",
            "DELIVERY": "clearance CRAFT delivery readback",
            "ATIS": "ATIS broadcast weather information",
        }
        query = default_queries.get(pos_value, "ATC procedures")

        procedures_text = store.format_procedures_for_prompt(
            airport_icao=airport,
            controller_position=pos_value,
            query=query,
            limit=3,
        )
        if not procedures_text:
            return None

        return {
            "source": "vector_rag",
            "airport": airport,
            "position": pos_value,
            "procedures": procedures_text,
        }

    @staticmethod
    def _get_position(controller: BaseController) -> ControllerPosition:
        cs = controller.callsign.upper()
        for pos, suffix in {
            ControllerPosition.GROUND: "_GND",
            ControllerPosition.TOWER: "_TWR",
            ControllerPosition.DEPARTURE: "_DEP",
            ControllerPosition.APPROACH: "_APP",
            ControllerPosition.CENTER: "_CTR",
            ControllerPosition.ATIS: "_ATIS",
        }.items():
            if suffix in cs:
                return pos
        return ControllerPosition.CENTER

    def _build_context(self, ctx: PromptContext) -> str:
        parts: List[str] = []

        # Controller info
        ctrl = ctx.controller
        parts.append(f"CONTROLLER: {ctrl.callsign} | Freq: {ctrl.frequency} | "
                      f"Sector: {ctrl.sector_id} | Airport: {ctrl.airport_icao or 'N/A'}")

        # Aircraft
        ac_list = self._format_aircraft(ctx)
        if ac_list:
            parts.append("AIRCRAFT:\n" + "\n".join(ac_list))

        # Weather
        wx_list = self._format_weather(ctx)
        if wx_list:
            parts.append("WEATHER:\n" + "\n".join(wx_list))

        # Airports
        ap_list = self._format_airports(ctx)
        if ap_list:
            parts.append("AIRPORTS:\n" + "\n".join(ap_list))

        # Conflicts
        if ctx.conflicts:
            parts.append("CONFLICTS:\n" + "\n".join(self._format_conflicts(ctx)))

        # Sectors
        if ctx.sectors:
            parts.append("SECTORS:\n" + "\n".join(self._format_sectors(ctx)))

        # Navigation
        if ctx.navigation:
            nav_text = self._format_navigation(ctx.navigation)
            if nav_text:
                parts.append(f"NAVIGATION:\n{nav_text}")

        # Local procedures
        if ctx.local_procedures:
            proc_text = json.dumps(ctx.local_procedures, indent=1)
            parts.append(f"LOCAL PROCEDURES:\n{proc_text}")

        return "\n\n".join(parts)

    def _format_aircraft(self, ctx: PromptContext) -> List[str]:
        lines: List[str] = []
        controlled = set(ctx.controller.controlled_aircraft)
        for cs, data in ctx.aircraft_state.items():
            pos = data.get("position", {})
            motion = data.get("motion", {})
            fp = data.get("flight_plan", {})
            state = data.get("state", "unknown")
            tag = " *" if cs in controlled else ""
            fp_str = f"Dep={fp.get('departure','?')} Arr={fp.get('arrival','?')}"
            if fp.get("origin"):
                fp_str += (
                    f" Route={fp.get('origin','?')}->{fp.get('destination','?')}"
                    f" {fp.get('route','')}"
                    f" Cruise={fp.get('cruise_altitude','?')}"
                )
            line = (
                f"  [{cs}]{tag} State={state} "
                f"Pos=({pos.get('lat', '?')}, {pos.get('lon', '?')}) "
                f"Alt={pos.get('alt_msl', '?')}ft "
                f"GS={motion.get('groundspeed', '?')}kn "
                f"VS={motion.get('vertical_speed', '?')}fpm "
                f"{fp_str}"
            )
            lines.append(line)
        return lines

    @staticmethod
    def _format_weather(ctx: PromptContext) -> List[str]:
        lines: List[str] = []
        for icao, data in ctx.weather.items():
            wind = data.get("wind", {})
            clouds = data.get("clouds", [])
            cloud_str = " ".join(
                f"{c.get('coverage', '')} {c.get('altitude_ft', '')}"
                for c in (clouds or [])
            )
            line = (
                f"  {icao}: Wind {wind.get('direction', '?')}/"
                f"{wind.get('speed_kn', '?')}kt "
                f"Vis={data.get('visibility_m', '?')}m "
                f"QNH={data.get('qnh_hpa', '?')}hPa "
                f"Temp={data.get('temperature_c', '?')}C "
                f"Clouds={cloud_str or 'SKC'}"
            )
            lines.append(line)
        return lines

    @staticmethod
    def _format_airports(ctx: PromptContext) -> List[str]:
        lines: List[str] = []
        for icao, data in ctx.airports.items():
            rwys = data.get("runways", {})
            rwy_lines = []
            for rid, rdata in rwys.items():
                flags = []
                if rdata.get("active_for_departure"):
                    flags.append("DEP")
                if rdata.get("active_for_arrival"):
                    flags.append("ARR")
                flag_str = f" [{','.join(flags)}]" if flags else ""
                rwy_lines.append(f"    {rid}{flag_str}")
            rwy_block = "\n".join(rwy_lines) if rwy_lines else "    (none)"
            line = (
                f"  {icao}: Elev={data.get('elevation_ft', '?')}ft "
                f"DepRwy={data.get('active_runway_dep', '?')} "
                f"ArrRwy={data.get('active_runway_arr', '?')}\n"
                f"    Runways:\n{rwy_block}"
            )
            lines.append(line)
        return lines

    @staticmethod
    def _format_conflicts(ctx: PromptContext) -> List[str]:
        lines: List[str] = []
        for c in ctx.conflicts:
            line = (
                f"  {c.get('aircraft_a', '?')} vs {c.get('aircraft_b', '?')}: "
                f"Lateral={c.get('lateral_distance_nm', '?')}nm "
                f"Vertical={c.get('vertical_distance_ft', '?')}ft "
                f"Time={c.get('time_to_conflict_s', '?')}s "
                f"Severity={c.get('severity', '?')}"
            )
            lines.append(line)
        return lines

    @staticmethod
    def _format_sectors(ctx: PromptContext) -> List[str]:
        lines: List[str] = []
        for s in ctx.sectors:
            ac = ", ".join(s.get("aircraft_callsigns", [])) or "(none)"
            line = (
                f"  Sector {s.get('sector_id', '?')}: "
                f"Ctrl={s.get('controller_callsign', '?')} "
                f"Freq={s.get('frequency_mhz', '?')} "
                f"Aircraft=[{ac}]"
            )
            lines.append(line)
        return lines

    @staticmethod
    def _format_navigation(nav: dict) -> str:
        parts: List[str] = []
        for key, value in nav.items():
            parts.append(f"  {key}: {json.dumps(value, default=str)}")
        return "\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text) / self._chars_per_token) + 1

    @staticmethod
    def _strip_empties(line: str) -> str:
        return re.sub(r'\b(null|none|undefined|nan)\b', '', line, flags=re.IGNORECASE).strip()
