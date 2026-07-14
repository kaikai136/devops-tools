from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.utils import timezone

from host_management.models import ManagedHost

from ..models import TerminalSession
from ..services_legacy import TERMINAL_PROTOCOL_RDP
from .connections import DEFAULT_TERMINAL_COLS, DEFAULT_TERMINAL_ROWS
from .errors import TerminalConnectionError


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


def is_rdp_recording_enabled() -> bool:
    from system_management.models import SystemSetting

    try:
        setting = SystemSetting.objects.get(key="rdp_recording")
    except SystemSetting.DoesNotExist:
        return bool(getattr(settings, "RDP_RECORDING_DEFAULT_ENABLED", False))

    value = setting.value if isinstance(setting.value, dict) else {}
    if "enabled" in value:
        return bool(value["enabled"])
    return bool(getattr(settings, "RDP_RECORDING_DEFAULT_ENABLED", False))


def build_rdp_recording_file(session: TerminalSession) -> str:
    created_at = session.created_at or timezone.now()
    return f"{created_at:%Y/%m}/{session.session_id}"


def build_rdp_connection_parameters(host: ManagedHost, session: TerminalSession, *, width: int = 1280, height: int = 720) -> dict[str, str]:
    target = str(host.public_ip or host.private_ip)
    params = {
        "hostname": target,
        "port": str(host.port or 3389),
        "username": host.login_user,
        "password": host.login_password,
        "security": "any",
        "ignore-cert": "true",
        "width": str(clamp_rdp_dimension(width, default=1280)),
        "height": str(clamp_rdp_dimension(height, default=720)),
    }
    if session.recording_enabled and session.recording_file:
        recording_relative = safe_recording_relative_path(session.recording_file)
        recording_path = rdp_recording_root() / recording_relative.parent
        params.update(
            {
                "recording-path": str(recording_path),
                "recording-name": recording_relative.name,
                "create-recording-path": "true",
            }
        )
    return params


def clamp_rdp_dimension(value: int, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(320, min(number, 7680))


def rdp_recording_root() -> Path:
    return Path(getattr(settings, "RDP_RECORDING_ROOT", Path(settings.BASE_DIR) / "rdp_recordings"))


def safe_recording_relative_path(value: str) -> Path:
    normalized = Path(str(value).replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise TerminalConnectionError("RDP 录屏路径无效")
    return normalized


def cleanup_expired_rdp_recordings(*, root: Path | None = None, now=None) -> dict[str, int]:
    root = Path(root or rdp_recording_root())
    now = now or timezone.now()
    retention_days = int(getattr(settings, "RDP_RECORDING_RETENTION_DAYS", 30))
    cutoff = now - timezone.timedelta(days=max(retention_days, 1))
    sessions = TerminalSession.objects.filter(
        protocol=TERMINAL_PROTOCOL_RDP,
        recording_file__gt="",
        created_at__lt=cutoff,
    )
    deleted = 0
    for session in sessions:
        try:
            relative_path = safe_recording_relative_path(session.recording_file)
        except TerminalConnectionError:
            continue
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            continue
        if target.is_file():
            target.unlink()
            prune_empty_recording_parents(target.parent, root)
            deleted += 1
        session.recording_file = ""
        session.save(update_fields=["recording_file"])
    return {"deleted": deleted}


def prune_empty_recording_parents(directory: Path, root: Path) -> None:
    root = root.resolve()
    current = directory.resolve()
    while current != root:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
