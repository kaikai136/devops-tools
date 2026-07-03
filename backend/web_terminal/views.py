from datetime import datetime, time
from urllib.parse import quote
from uuid import UUID
from functools import wraps

from django.core.paginator import EmptyPage, Paginator
from rest_framework import status
from rest_framework.decorators import api_view
from django.db import transaction
from django.db.models import CharField, Max, Q
from django.db.models.functions import Cast
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.response import Response

from accounts.permissions import require_feature_permission, require_login
from host_management.models import ManagedHost
from operations.responses import bad_request, not_found, serializer_bad_request

from .models import TerminalCommandAudit, TerminalQuickCommand, TerminalSession
from .serializers import TerminalCommandAuditSerializer, TerminalQuickCommandSerializer
from .services import (
    TerminalConnectionError,
    asciicast_header,
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
    stream_remote_file_content,
    terminal_tree_payload,
    update_remote_file_properties,
    upload_remote_file,
)


def next_quick_command_sort_order(category: str) -> int:
    latest = TerminalQuickCommand.objects.filter(category=category).aggregate(value=Max("sort_order"))["value"]
    return int(latest or 0) + 10


def terminal_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        auth_error = require_login(request)
        if auth_error:
            return auth_error
        return view_func(request, *args, **kwargs)

    return wrapped


def quick_command_permission_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        permission_error = require_feature_permission(request, "hosts", "quick_commands", "没有快捷命令权限")
        if permission_error:
            return permission_error
        return view_func(request, *args, **kwargs)

    return wrapped


def session_audit_permission_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        permission_error = require_feature_permission(request, "hosts", "session_audit", "没有会话审计权限")
        if permission_error:
            return permission_error
        return view_func(request, *args, **kwargs)

    return wrapped


def quick_command_queryset():
    return TerminalQuickCommand.objects.all()


def parse_positive_int(value, default: int, minimum: int = 1, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def parse_audit_datetime(value: str, end_of_day: bool = False):
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        parsed_date = parse_date(raw)
        if parsed_date is None:
            return None
        parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


@api_view(["GET", "POST"])
@quick_command_permission_required
def terminal_quick_commands(request):
    if request.method == "GET":
        return Response(TerminalQuickCommandSerializer(quick_command_queryset(), many=True).data)

    payload = request.data.copy()
    category = str(payload.get("category", "")).strip()
    if "sortOrder" not in payload and category:
        payload["sortOrder"] = next_quick_command_sort_order(category)
    serializer = TerminalQuickCommandSerializer(data=payload)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(TerminalQuickCommandSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@quick_command_permission_required
def terminal_quick_command_detail(request, command_id: int):
    try:
        command = TerminalQuickCommand.objects.get(id=command_id)
    except TerminalQuickCommand.DoesNotExist:
        return not_found("快捷命令不存在")

    if request.method == "DELETE":
        command.delete()
        return Response({"deleted": True})

    payload = request.data.copy()
    serializer = TerminalQuickCommandSerializer(command, data=payload, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(TerminalQuickCommandSerializer(serializer.save()).data)


@api_view(["POST"])
@quick_command_permission_required
def terminal_quick_commands_reorder(request):
    ids = request.data.get("ids")
    if not isinstance(ids, list) or not ids:
        return bad_request("请提供快捷命令排序列表")

    try:
        command_ids = [int(command_id) for command_id in ids]
    except (TypeError, ValueError):
        return bad_request("快捷命令 ID 无效")

    commands = list(TerminalQuickCommand.objects.filter(id__in=command_ids))
    commands_by_id = {command.id: command for command in commands}
    missing_ids = [command_id for command_id in command_ids if command_id not in commands_by_id]
    if missing_ids:
        return bad_request(f"快捷命令不存在：{missing_ids[0]}")

    with transaction.atomic():
        for index, command_id in enumerate(command_ids, start=1):
            command = commands_by_id[command_id]
            command.sort_order = index * 10
            command.save(update_fields=["sort_order", "updated_at"])

    return Response(TerminalQuickCommandSerializer(quick_command_queryset(), many=True).data)


@api_view(["GET"])
@terminal_login_required
def terminal_tree(request):
    return Response(terminal_tree_payload())


@api_view(["POST"])
@terminal_login_required
def terminal_sessions(request):
    host_id = request.data.get("host")
    try:
        host = ManagedHost.objects.get(id=int(host_id))
    except (TypeError, ValueError, ManagedHost.DoesNotExist):
        return bad_request("请选择要连接的主机")

    try:
        session, greeting = create_terminal_session(host, user=request.user)
    except TerminalConnectionError as error:
        return bad_request(error)

    return Response(session_payload(session, greeting), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@terminal_login_required
def terminal_commands(request, session_id: UUID):
    try:
        session = TerminalSession.objects.select_related("host").get(session_id=session_id)
    except TerminalSession.DoesNotExist:
        return Response({"error": "终端会话不存在"}, status=status.HTTP_404_NOT_FOUND)

    command = str(request.data.get("command", "")).strip()
    if not command:
        return bad_request("请输入命令")
    return Response(run_session_command(session, command, user=request.user))


@api_view(["GET"])
@session_audit_permission_required
def session_audits(request):
    queryset = TerminalCommandAudit.objects.select_related("session", "host", "user")
    search = str(request.query_params.get("search", "")).strip()
    risk_level = str(request.query_params.get("riskLevel", "")).strip()
    host = str(request.query_params.get("host", "")).strip()
    date_from = parse_audit_datetime(str(request.query_params.get("dateFrom", "")).strip())
    date_to = parse_audit_datetime(str(request.query_params.get("dateTo", "")).strip(), end_of_day=True)

    if search:
        queryset = queryset.annotate(
            ip_address_text=Cast("ip_address", output_field=CharField()),
            session_id_text=Cast("session__session_id", output_field=CharField()),
        )
        queryset = queryset.filter(
            Q(username__icontains=search)
            | Q(command__icontains=search)
            | Q(output__icontains=search)
            | Q(asset_name__icontains=search)
            | Q(ip_address_text__icontains=search)
            | Q(session_id_text__icontains=search)
        )
    if risk_level in {TerminalCommandAudit.RISK_ACCEPT, TerminalCommandAudit.RISK_MEDIUM, TerminalCommandAudit.RISK_HIGH}:
        queryset = queryset.filter(risk_level=risk_level)
    if host:
        try:
            queryset = queryset.filter(host_id=int(host))
        except (TypeError, ValueError):
            return bad_request("主机筛选条件无效")
    if date_from:
        queryset = queryset.filter(executed_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(executed_at__lte=date_to)

    page_size = parse_positive_int(request.query_params.get("pageSize"), default=20, maximum=100)
    page_number = parse_positive_int(request.query_params.get("page"), default=1, maximum=1000000)
    paginator = Paginator(queryset, page_size)
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(paginator.num_pages or 1)

    return Response(
        {
            "count": paginator.count,
            "page": page.number,
            "pageSize": page_size,
            "results": TerminalCommandAuditSerializer(page.object_list, many=True).data,
        }
    )


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
