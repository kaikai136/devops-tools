from __future__ import annotations

from django.utils import timezone

from host_management.models import ManagedHost

from ..models import TerminalSession
from .connections import LIVE_TERMINALS, open_ssh_client
from .errors import TerminalConnectionError


def run_session_command(session: TerminalSession, command: str, user=None) -> dict:
    from .audit import create_command_audit, is_session_audit_enabled

    from .recordings import append_session_recording_event

    command = command.strip()
    if not command:
        return {"command": command, "output": "", "exitCode": 0}
    audit_enabled = is_session_audit_enabled(user) and bool(session.recording_started_at)
    if command.lower() in {"clear", "cls"}:
        audit = create_command_audit(session, command, user=user, output="") if audit_enabled else None
        if audit_enabled:
            append_session_recording_event(session, "i", command + "\r")
            session.transcript += f"$ {command}\n"
        session.last_command_at = timezone.now()
        update_fields = ["last_command_at"]
        if audit_enabled:
            update_fields.extend(["transcript", "recording", "recording_last_event_at"])
        session.save(update_fields=update_fields)
        payload = {"command": command, "output": "__CLEAR__", "exitCode": 0}
        if audit:
            payload["auditId"] = audit.id
        return payload

    output, exit_code = run_live_terminal_command(session, command)
    audit = create_command_audit(session, command, user=user, output=output) if audit_enabled else None
    if audit_enabled:
        append_session_recording_event(session, "i", command + "\r")
        append_session_recording_event(session, "o", output)
        session.transcript += f"$ {command}\n{output}\n"
    session.last_command_at = timezone.now()
    update_fields = ["last_command_at"]
    if audit_enabled:
        update_fields.extend(["transcript", "recording", "recording_last_event_at"])
    if command.lower() in {"exit", "logout"}:
        session.status = "closed"
        update_fields.append("status")
        if audit_enabled:
            append_session_recording_event(session, "x", 0 if exit_code == 0 else 1)
    session.save(update_fields=update_fields)
    payload = {"command": command, "output": output, "exitCode": exit_code}
    if audit:
        payload["auditId"] = audit.id
    return payload


def run_live_terminal_command(session: TerminalSession, command: str) -> tuple[str, int | None]:
    connection = LIVE_TERMINALS.get(str(session.session_id))
    if connection is None:
        return "SSH 会话已失效，请重新连接主机。", None

    try:
        output = connection.send_command(command)
        if command.lower() in {"exit", "logout"} or connection.channel.closed:
            connection.close()
            LIVE_TERMINALS.pop(str(session.session_id), None)
        return output.rstrip() or "命令已发送。", 0
    except Exception as error:
        LIVE_TERMINALS.pop(str(session.session_id), None)
        try:
            connection.close()
        except Exception:
            pass
        return f"SSH 连接或命令执行失败：{error}", None


def run_one_shot_ssh_command(host: ManagedHost, command: str) -> str:
    client = open_ssh_client(host)
    try:
        _, stdout, stderr = client.exec_command(command, timeout=30)
        output = stdout.read()
        error_output = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise TerminalConnectionError(error_output or f"远端命令退出码 {exit_code}")
        return output.decode("utf-8", errors="replace")
    finally:
        client.close()


def run_one_shot_ssh_upload(host: ManagedHost, command: str, data: bytes) -> None:
    client = open_ssh_client(host)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=60)
        stdin.write(data)
        stdin.channel.shutdown_write()
        error_output = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise TerminalConnectionError(error_output or f"远端命令退出码 {exit_code}")
    finally:
        client.close()


__all__ = [
    'run_session_command',
    'run_live_terminal_command',
    'run_one_shot_ssh_command',
    'run_one_shot_ssh_upload',
]
