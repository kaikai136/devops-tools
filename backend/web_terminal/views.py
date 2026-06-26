from uuid import UUID

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from host_management.models import ManagedHost
from operations.responses import bad_request

from .models import TerminalSession
from .services import (
    TerminalConnectionError,
    create_remote_directory,
    create_remote_file,
    create_remote_symlink,
    create_terminal_session,
    delete_remote_file,
    download_remote_file,
    get_remote_file_properties,
    get_remote_resource_monitor,
    list_remote_directory,
    rename_remote_file,
    run_session_command,
    session_payload,
    terminal_tree_payload,
    update_remote_file_properties,
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
def terminal_monitor(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(get_remote_resource_monitor(host))
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
                str(request.data.get("relativePath", "")),
            )
        )
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_create_file(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "涓绘満涓嶅瓨鍦?"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(
            create_remote_file(
                host,
                str(request.data.get("directory", ".")),
                str(request.data.get("filename", "")),
                str(request.data.get("octalMode", "")),
            )
        )
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_create_directory(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "涓绘満涓嶅瓨鍦?"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(
            create_remote_directory(
                host,
                str(request.data.get("directory", ".")),
                str(request.data.get("dirname", "")),
                str(request.data.get("octalMode", "")),
            )
        )
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_create_symlink(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "涓绘満涓嶅瓨鍦?"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(
            create_remote_symlink(
                host,
                str(request.data.get("directory", ".")),
                str(request.data.get("linkName", "")),
                str(request.data.get("targetPath", "")),
            )
        )
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_rename(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "涓绘満涓嶅瓨鍦?"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(rename_remote_file(host, str(request.data.get("path", "")), str(request.data.get("newName", ""))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_delete(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "涓绘満涓嶅瓨鍦?"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(delete_remote_file(host, str(request.data.get("path", ""))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_properties(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(get_remote_file_properties(host, str(request.data.get("path", ""))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
def terminal_file_properties_update(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(
            update_remote_file_properties(
                host,
                str(request.data.get("path", "")),
                str(request.data.get("owner", "")),
                str(request.data.get("group", "")),
                str(request.data.get("octalMode", "")),
                bool(request.data.get("recursive", False)),
            )
        )
    except TerminalConnectionError as error:
        return bad_request(error)
