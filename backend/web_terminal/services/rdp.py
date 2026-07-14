from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.utils import timezone

from host_management.models import ManagedHost

from ..models import TerminalSession
from .errors import TerminalConnectionError


TERMINAL_PROTOCOL_SSH = TerminalSession.PROTOCOL_SSH
TERMINAL_PROTOCOL_RDP = TerminalSession.PROTOCOL_RDP

__all__ = [
    "terminal_protocol_for_host",
    "greeting_for",
    "create_rdp_terminal_session",
    "is_rdp_recording_enabled",
    "build_rdp_recording_file",
    "build_rdp_connection_parameters",
    "clamp_rdp_dimension",
    "rdp_recording_root",
    "safe_recording_relative_path",
    "cleanup_expired_rdp_recordings",
    "prune_empty_recording_parents",
]


def terminal_protocol_for_host(host: ManagedHost) -> str:
    if host.os == "windows" or host.system_type.lower() == "windows":
        return TERMINAL_PROTOCOL_RDP
    return TERMINAL_PROTOCOL_SSH


def greeting_for(host: ManagedHost) -> str:
    target = host.public_ip or host.private_ip
    return "\n".join(
        [
            f"正在连接 {host.name} ({target}:{host.port})",
            f"登录用户：{host.login_user or '未配置'}",
            "连接已建立。输入命令后回车执行。",
        ]
    )


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


def create_rdp_terminal_session(host: ManagedHost, user=None) -> TerminalSession:
    recording_enabled = is_rdp_recording_enabled()
    session = TerminalSession.objects.create(
        host=host,
        protocol=TERMINAL_PROTOCOL_RDP,
        status="connected",
        transcript=f"connect-rdp {host.name}\n",
        recording_enabled=recording_enabled,
    )
    if recording_enabled:
        session.recording_file = build_rdp_recording_file(session)
        session.save(update_fields=["recording_file"])
    return session
