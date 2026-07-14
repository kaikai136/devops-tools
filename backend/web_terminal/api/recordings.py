from uuid import UUID

from django.http import HttpResponse, StreamingHttpResponse
from rest_framework.decorators import api_view

from operations.responses import not_found

from ..models import TerminalSession
from ..services import (
    TerminalConnectionError,
    asciicast_header,
    rdp_recording_root,
    safe_recording_relative_path,
)
from .common import session_audit_permission_required


@api_view(["GET"])
@session_audit_permission_required
def terminal_session_recording(request, session_id: UUID):
    try:
        session = TerminalSession.objects.get(session_id=session_id)
    except TerminalSession.DoesNotExist:
        return not_found("终端会话不存在")

    recording = session.recording or f"{asciicast_header(session.recording_cols, session.recording_rows)}\n"
    response = HttpResponse(recording, content_type="application/x-asciicast; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="{session.session_id}.cast"'
    return response


@api_view(["GET"])
@session_audit_permission_required
def terminal_rdp_recording(request, session_id: UUID):
    try:
        session = TerminalSession.objects.get(session_id=session_id, protocol=TerminalSession.PROTOCOL_RDP)
    except TerminalSession.DoesNotExist:
        return not_found("远程桌面会话不存在")
    if not session.recording_enabled or not session.recording_file:
        return not_found("远程桌面录屏不存在")
    try:
        relative_path = safe_recording_relative_path(session.recording_file)
    except TerminalConnectionError:
        return not_found("远程桌面录屏不存在")
    root = rdp_recording_root().resolve()
    file_path = (root / relative_path).resolve()
    try:
        file_path.relative_to(root)
    except ValueError:
        return not_found("远程桌面录屏不存在")
    if not file_path.is_file():
        return not_found("远程桌面录屏不存在")
    response = StreamingHttpResponse(file_path.open("rb"), content_type="application/octet-stream")
    response["Content-Disposition"] = f'inline; filename="{session.session_id}.guac"'
    return response
