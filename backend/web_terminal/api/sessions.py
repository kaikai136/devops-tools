from uuid import UUID

from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.db.models import CharField, Max, Q
from django.db.models.functions import Cast
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from host_management.models import ManagedHost
from operations.responses import bad_request, not_found, serializer_bad_request

from ..models import TerminalCommandAudit, TerminalQuickCommand, TerminalSession
from ..serializers import TerminalCommandAuditSerializer, TerminalQuickCommandSerializer
from ..services import (
    TerminalConnectionError,
    create_terminal_session,
    run_session_command,
    session_payload,
    terminal_tree_payload,
)
from .common import (
    parse_audit_datetime,
    parse_positive_int,
    quick_command_permission_required,
    session_audit_permission_required,
    terminal_login_required,
)


def next_quick_command_sort_order(category: str) -> int:
    latest = TerminalQuickCommand.objects.filter(category=category).aggregate(value=Max("sort_order"))["value"]
    return int(latest or 0) + 10


def quick_command_queryset():
    return TerminalQuickCommand.objects.all()


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
