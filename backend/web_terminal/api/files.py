from urllib.parse import quote

from django.http import HttpResponse, StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from host_management.models import ManagedHost
from operations.responses import bad_request

from ..services import (
    TerminalConnectionError,
    create_remote_directory,
    create_remote_file,
    create_remote_symlink,
    delete_remote_file,
    download_remote_file,
    get_remote_file_properties,
    list_remote_directory,
    rename_remote_file,
    stream_remote_file_content,
    update_remote_file_properties,
    upload_remote_file,
)
from .common import terminal_login_required


@api_view(["POST"])
@terminal_login_required
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
@terminal_login_required
def terminal_file_download_list(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(list_remote_directory(host, str(request.data.get("path", "."))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["POST"])
@terminal_login_required
def terminal_file_download(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        return Response(download_remote_file(host, str(request.data.get("path", ""))))
    except TerminalConnectionError as error:
        return bad_request(error)


@api_view(["GET"])
@terminal_login_required
def terminal_file_download_attachment(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    try:
        payload = stream_remote_file_content(
            host,
            str(request.query_params.get("path", "")),
            str(request.query_params.get("protocol", "auto")),
        )
        filename = str(payload.get("filename") or "download")
        content = payload.get("content") or b""
    except TerminalConnectionError as error:
        return bad_request(error)
    except Exception:
        return bad_request("文件下载失败")

    response_class = StreamingHttpResponse if not isinstance(content, (bytes, bytearray)) else HttpResponse
    response = response_class(content, content_type="application/octet-stream")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    if "size" in payload:
        response["Content-Length"] = str(int(payload.get("size") or 0))
    else:
        response["Content-Length"] = str(len(content))
    return response


@api_view(["POST"])
@terminal_login_required
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
@terminal_login_required
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
@terminal_login_required
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
@terminal_login_required
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
@terminal_login_required
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
@terminal_login_required
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
@terminal_login_required
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
@terminal_login_required
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
