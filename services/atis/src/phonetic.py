from __future__ import annotations

from models import PHONETIC_CODES


def next_code(current: str | None = None) -> str:
    if current is None:
        return "Alpha"
    try:
        idx = PHONETIC_CODES.index(current)
        return PHONETIC_CODES[(idx + 1) % len(PHONETIC_CODES)]
    except ValueError:
        return "Alpha"
