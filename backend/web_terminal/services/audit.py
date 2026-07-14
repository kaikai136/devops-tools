from __future__ import annotations

import re

from django.utils import timezone

from accounts.models import UserProfile
from host_management.models import ManagedHost

from ..models import TerminalCommandAudit, TerminalSession
from ..services_legacy import TERMINAL_PROTOCOL_RDP, greeting_for
from .connections import LIVE_TERMINALS, open_live_terminal
from .recordings import (
    append_session_recording_event,
    build_rdp_recording_file,
    initialize_session_recording,
    is_rdp_recording_enabled,
)


HIGH_RISK_COMMAND_PATTERN = re.compile(
    r"(^|\s)(rm\s+(-[^\s]*r[^\s]*f|-[^\s]*f[^\s]*r)|mkfs(\.|$)|dd\s+|shutdown\b|reboot\b|halt\b|poweroff\b|passwd\b|userdel\b|groupdel\b|visudo\b|iptables\b|firewall-cmd\b)",
    re.IGNORECASE,
)

MEDIUM_RISK_COMMAND_PATTERN = re.compile(
    r"(^|\s)(sudo\b|chmod\b|chown\b|systemctl\b|service\b|kubectl\s+(delete|apply|exec|scale|rollout)\b|docker\s+(rm|rmi|exec|compose)\b|apt(-get)?\s+(install|remove|purge)\b|yum\s+(install|remove|erase)\b|dnf\s+(install|remove|erase)\b)",
    re.IGNORECASE,
)

def classify_command_risk(command: str) -> str:
    normalized = re.sub(r"\s+", " ", command.strip())
    if not normalized:
        return TerminalCommandAudit.RISK_ACCEPT
    if HIGH_RISK_COMMAND_PATTERN.search(normalized):
        return TerminalCommandAudit.RISK_HIGH
    if MEDIUM_RISK_COMMAND_PATTERN.search(normalized):
        return TerminalCommandAudit.RISK_MEDIUM
    return TerminalCommandAudit.RISK_ACCEPT


def is_session_audit_enabled(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    try:
        return bool(user.profile.session_audit_enabled)
    except UserProfile.DoesNotExist:
        return True


def command_audit_payload(audit: TerminalCommandAudit) -> dict:
    return {
        "id": audit.id,
        "username": audit.username,
        "command": audit.command,
        "output": audit.output,
        "riskLevel": audit.risk_level,
        "assetName": audit.asset_name,
        "ipAddress": str(audit.ip_address) if audit.ip_address else "",
        "sessionId": str(audit.session.session_id),
        "hostId": audit.host_id,
        "executedAt": audit.executed_at.isoformat() if audit.executed_at else None,
    }


def create_command_audit(session: TerminalSession, command: str, user=None, output: str = "", executed_at=None) -> TerminalCommandAudit:
    executed_at = executed_at or timezone.now()
    host = session.host
    username = getattr(user, "username", "") if user and getattr(user, "is_authenticated", False) else ""
    return TerminalCommandAudit.objects.create(
        session=session,
        host=host,
        user=user if user and getattr(user, "is_authenticated", False) else None,
        username=username or "anonymous",
        command=command,
        output=output,
        risk_level=classify_command_risk(command),
        asset_name=host.name,
        ip_address=host.public_ip or host.private_ip or None,
        executed_at=executed_at,
    )


def append_audit_output(audit: TerminalCommandAudit | None, output: str) -> None:
    if not audit or not output:
        return
    audit.output = f"{audit.output}{output}"
    audit.save(update_fields=["output", "updated_at"])


def create_terminal_session(host: ManagedHost, user=None) -> tuple[TerminalSession, str]:
    connection = open_live_terminal(host)
    greeting = connection.read_available()
    audit_enabled = is_session_audit_enabled(user)
    session = TerminalSession.objects.create(
        host=host,
        transcript=f"connect {host.name}\n{greeting}\n" if audit_enabled else "",
    )
    if audit_enabled:
        initialize_session_recording(session)
    if audit_enabled and greeting:
        append_session_recording_event(session, "o", greeting)
        session.save(update_fields=["recording", "recording_last_event_at"])
    LIVE_TERMINALS[str(session.session_id)] = connection
    return session, greeting or greeting_for(host)


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
