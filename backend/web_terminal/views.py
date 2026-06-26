from uuid import UUID

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from host_management.models import ManagedHost
from operations.responses import bad_request

from .models import TerminalSession
from .services import (
    TerminalConnectionError,
    create_terminal_session,
    download_remote_file,
    list_remote_directory,
    preview_remote_file,
    run_session_command,
    session_payload,
    terminal_tree_payload,
    upload_remote_file,
)


@api_view(["GET"])
def terminal_tree(_request):
    return Response(terminal_tree_payload())


@api_view(["POST"])
def terminal_sessions(request):
    host_id = request.data.get("host")
    try:
        host = ManagedHost.objects.get(id=int(host_id))
    except (TypeError, ValueError, ManagedHost.DoesNotExist):
        return bad_request("请选择要连接的主机")

    try:
        session, greeting = create_terminal_session(host)
    except TerminalConnectionError as error:
        return bad_request(error)

    return Response(session_payload(session, greeting), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def terminal_commands(request, session_id: UUID):
    try:
        session = TerminalSession.objects.select_related("host").get(session_id=session_id)
    except TerminalSession.DoesNotExist:
        return Response({"error": "终端会话不存在"}, status=status.HTTP_404_NOT_FOUND)

    command = str(request.data.get("command", "")).strip()
    if not command:
        return bad_request("请输入命令")
    return Response(run_session_command(session, command))


@api_view(["POST"])
def terminal_file_preview(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(preview_remote_file(host, str(request.data.get("path", ""))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_list(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(list_remote_directory(host, str(request.data.get("path", "."))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_download(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(download_remote_file(host, str(request.data.get("path", ""))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_upload(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(
            upload_remote_file(
                host,
                str(request.data.get("directory", ".")),
                str(request.data.get("filename", "")),
                str(request.data.get("contentBase64", "")),
            )
        )
    except TerminalConnectionError as error:
        return bad_request(error)
