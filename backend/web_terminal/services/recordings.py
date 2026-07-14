from __future__ import annotations

from django.utils import timezone

from ..models import TerminalSession
from .connections import DEFAULT_TERMINAL_COLS, DEFAULT_TERMINAL_ROWS


ASCIICAST_VERSION = 3


def asciicast_header(cols: int = DEFAULT_TERMINAL_COLS, rows: int = DEFAULT_TERMINAL_ROWS) -> str:
    return json_dumps(
        {
            "version": ASCIICAST_VERSION,
            "term": {
                "cols": int(cols or DEFAULT_TERMINAL_COLS),
                "rows": int(rows or DEFAULT_TERMINAL_ROWS),
                "type": "xterm-256color",
            },
        }
    )


def asciicast_event(previous_event_at, event_type: str, data, event_at=None) -> tuple[str, object]:
    event_at = event_at or timezone.now()
    interval = max(0.0, (event_at - previous_event_at).total_seconds()) if previous_event_at else 0.0
    return json_dumps([round(interval, 6), event_type, data]), event_at


def json_dumps(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def initialize_session_recording(session: TerminalSession, cols: int = DEFAULT_TERMINAL_COLS, rows: int = DEFAULT_TERMINAL_ROWS) -> None:
    started_at = timezone.now()
    session.recording_started_at = started_at
    session.recording_last_event_at = started_at
    session.recording_cols = max(1, min(int(cols or DEFAULT_TERMINAL_COLS), 300))
    session.recording_rows = max(1, min(int(rows or DEFAULT_TERMINAL_ROWS), 120))
    session.recording_has_input = True
    session.recording = asciicast_header(session.recording_cols, session.recording_rows) + "\n"
    session.save(update_fields=["recording_started_at", "recording_last_event_at", "recording_cols", "recording_rows", "recording_has_input", "recording"])


def append_session_recording_event(session: TerminalSession, event_type: str, data) -> None:
    if not session.recording_started_at:
        initialize_session_recording(session)
    event, event_at = asciicast_event(session.recording_last_event_at or session.recording_started_at, event_type, data)
    session.recording += event + "\n"
    session.recording_last_event_at = event_at


def save_session_recording(session: TerminalSession, events: list[str], update_fields: list[str] | None = None) -> None:
    if events:
        session.recording += "".join(events)
        fields = list(update_fields or [])
        fields.append("recording")
        fields.append("recording_last_event_at")
        session.save(update_fields=list(dict.fromkeys(fields)))
    elif update_fields:
        session.save(update_fields=update_fields)
