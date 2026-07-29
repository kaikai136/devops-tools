from functools import wraps
from urllib.parse import quote

from django.http import HttpResponse, StreamingHttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request, get_object_or_error
from host_management.models import ManagedHost

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
from .common import terminal_permission_required


def with_terminal_host(view_func):
    """按 ``host_id`` 解析 ManagedHost 并统一处理终端异常。

    替代每个文件视图开头重复的「取 host → 404 / 捕获 TerminalConnectionError」样板。
    被包装的视图签名为 ``view(request, host, ...)``,直接拿到已解析的 host 实例。
    """

    @wraps(view_func)
    def wrapped(request, host_id: int, *args, **kwargs):
        host, error = get_object_or_error(ManagedHost, id=host_id, error_message="主机不存在")
        if error:
            return error
        try:
            return view_func(request, host, *args, **kwargs)
        except TerminalConnectionError as connection_error:
            return bad_request(connection_error)

    return wrapped


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_list(request, host):
    return Response(list_remote_directory(host, str(request.data.get("path", "."))))


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_download_list(request, host):
    return Response(list_remote_directory(host, str(request.data.get("path", "."))))


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_download(request, host):
    return Response(download_remote_file(host, str(request.data.get("path", ""))))


@api_view(["GET"])
@terminal_permission_required
@with_terminal_host
def terminal_file_download_attachment(request, host):
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
@terminal_permission_required
@with_terminal_host
def terminal_file_upload(request, host):
    return Response(
        upload_remote_file(
            host,
            str(request.data.get("directory", ".")),
            str(request.data.get("filename", "")),
            str(request.data.get("contentBase64", "")),
            str(request.data.get("relativePath", "")),
        )
    )


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_create_file(request, host):
    return Response(
        create_remote_file(
            host,
            str(request.data.get("directory", ".")),
            str(request.data.get("filename", "")),
            str(request.data.get("octalMode", "")),
        )
    )


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_create_directory(request, host):
    return Response(
        create_remote_directory(
            host,
            str(request.data.get("directory", ".")),
            str(request.data.get("dirname", "")),
            str(request.data.get("octalMode", "")),
        )
    )


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_create_symlink(request, host):
    return Response(
        create_remote_symlink(
            host,
            str(request.data.get("directory", ".")),
            str(request.data.get("linkName", "")),
            str(request.data.get("targetPath", "")),
        )
    )


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_rename(request, host):
    return Response(rename_remote_file(host, str(request.data.get("path", "")), str(request.data.get("newName", ""))))


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_delete(request, host):
    return Response(delete_remote_file(host, str(request.data.get("path", ""))))


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_properties(request, host):
    return Response(get_remote_file_properties(host, str(request.data.get("path", ""))))


@api_view(["POST"])
@terminal_permission_required
@with_terminal_host
def terminal_file_properties_update(request, host):
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
