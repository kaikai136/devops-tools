from django.core.paginator import EmptyPage, Paginator
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_feature_permission
from operations.responses import bad_request

from ..gateway.assets import GatewayAssetError, resolve_gateway_host
from ..gateway.config import gateway_connection_info
from ..models import TerminalFileAudit
from ..serializers import TerminalFileAuditSerializer
from ..services import host_payload
from .common import parse_positive_int, session_audit_permission_required


@api_view(["GET"])
def ssh_gateway_connection_info(request):
    permission_error = require_feature_permission(request, "hosts", "terminal", "没有 SSH 网关权限")
    if permission_error:
        return permission_error

    host = None
    raw_host_id = request.query_params.get("host")
    if raw_host_id not in (None, "", "null"):
        try:
            host = resolve_gateway_host(request.user, int(raw_host_id))
        except (TypeError, ValueError, GatewayAssetError) as error:
            return bad_request(error)

    payload = gateway_connection_info(request.user.username, host_id=host.id if host else None, request=request)
    if host is not None:
        payload["host"] = host_payload(host)
    return Response(payload)


@api_view(["GET"])
@session_audit_permission_required
def terminal_file_audits(request):
    queryset = TerminalFileAudit.objects.select_related("session", "host", "user")
    operation = str(request.query_params.get("operation", "")).strip().lower()
    protocol = str(request.query_params.get("protocol", "")).strip().lower()
    status = str(request.query_params.get("status", "")).strip().lower()
    host = str(request.query_params.get("host", "")).strip()
    username = str(request.query_params.get("username", "")).strip()
    search = str(request.query_params.get("search", "")).strip()

    allowed_operations = {choice for choice, _label in TerminalFileAudit.OPERATION_CHOICES}
    allowed_statuses = {choice for choice, _label in TerminalFileAudit.STATUS_CHOICES}
    if operation in allowed_operations:
        queryset = queryset.filter(operation=operation)
    if protocol:
        queryset = queryset.filter(protocol=protocol[:20])
    if status in allowed_statuses:
        queryset = queryset.filter(status=status)
    if username:
        queryset = queryset.filter(username__icontains=username)
    if search:
        queryset = queryset.filter(path__icontains=search)
    if host:
        try:
            queryset = queryset.filter(host_id=int(host))
        except (TypeError, ValueError):
            return bad_request("主机筛选条件无效")

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
            "results": TerminalFileAuditSerializer(page.object_list, many=True).data,
        }
    )
