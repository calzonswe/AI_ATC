from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List


class EventType(Enum):
    AIRCRAFT_ENTERED_SECTOR = "aircraft_entered_sector"
    AIRCRAFT_LEFT_SECTOR = "aircraft_left_sector"
    AIRCRAFT_POSITION_UPDATED = "aircraft_position_updated"
    AIRCRAFT_STATE_CHANGED = "aircraft_state_changed"
    AIRCRAFT_ENTERED_AIRSPACE = "aircraft_entered_airspace"
    AIRCRAFT_LEFT_AIRSPACE = "aircraft_left_airspace"
    RUNWAY_STATE_CHANGED = "runway_state_changed"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    WEATHER_UPDATED = "weather_updated"


@dataclass
class Event:
    type: EventType
    data: dict
    source: str = ""


EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._wildcard_handlers: List[EventHandler] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._wildcard_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    def publish(self, event_type: EventType, data: dict, source: str = "") -> None:
        event = Event(type=event_type, data=data, source=source)
        for handler in self._wildcard_handlers:
            handler(event)
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                handler(event)
