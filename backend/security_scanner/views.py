from django.http import HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_feature_permission
from operations.responses import bad_request, not_found

from .models import SecurityScanFinding, SecurityScanTask
from .runner import mark_interrupted_tasks, start_security_scan_task
from .serializers import SecurityScanFindingSummarySerializer, SecurityScanTaskDetailSerializer, SecurityScanTaskSerializer
from .services import create_security_scan_task, export_task_csv, export_task_json, list_scannable_hosts

DEFAULT_FINDINGS_PAGE_SIZE = 50
MAX_FINDINGS_PAGE_SIZE = 200


def security_scan_permission(request, action_key: str | None = None):
    return require_feature_permission(request, "securityScan", action_key, "No security scan permission")


@api_view(["GET"])
def scan_hosts(request):
    auth_error = security_scan_permission(request)
    if auth_error:
        return auth_error
    hosts = list_scannable_hosts()
    return Response(
        [
            {
                "id": host.id,
                "name": host.name,
                "group": host.group_id,
                "groupName": host.group.name if host.group_id and host.group else "",
                "privateIp": host.private_ip,
                "port": host.port,
                "loginUser": host.login_user,
                "os": host.os,
                "systemType": host.system_type,
                "systemArch": host.system_arch,
                "verified": host.verified,
            }
            for host in hosts
        ]
    )


@api_view(["GET", "POST"])
def scan_tasks(request):
    if request.method == "GET":
        auth_error = security_scan_permission(request, "refresh")
        if auth_error:
            return auth_error
        mark_interrupted_tasks()
        queryset = SecurityScanTask.objects.select_related("created_by").all()
        status_filter = str(request.query_params.get("status", "")).strip()
        keyword = str(request.query_params.get("keyword", "")).strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        return Response(SecurityScanTaskSerializer(queryset[:100], many=True).data)

    auth_error = security_scan_permission(request, "scan")
    if auth_error:
        return auth_error
    try:
        task = create_security_scan_task(request.user, request.data if isinstance(request.data, dict) else {})
    except (TypeError, ValueError) as error:
        return bad_request(error)
    start_security_scan_task(task.id)
    task.refresh_from_db()
    return Response(SecurityScanTaskSerializer(task).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
def scan_task_detail(request, task_id: int):
    action = "delete" if request.method == "DELETE" else "refresh"
    auth_error = security_scan_permission(request, action)
    if auth_error:
        return auth_error
    try:
        task = SecurityScanTask.objects.select_related("created_by").prefetch_related("host_results").get(id=task_id)
    except SecurityScanTask.DoesNotExist:
        return not_found("Security scan task not found")
    if request.method == "DELETE":
        task.delete()
        return Response({"deleted": True})
    return Response(SecurityScanTaskDetailSerializer(task).data)


@api_view(["GET"])
def scan_task_findings(request, task_id: int):
    auth_error = security_scan_permission(request, "refresh")
    if auth_error:
        return auth_error
    if not SecurityScanTask.objects.filter(id=task_id).exists():
        return not_found("Security scan task not found")

    try:
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = max(1, min(MAX_FINDINGS_PAGE_SIZE, int(request.query_params.get("pageSize", DEFAULT_FINDINGS_PAGE_SIZE))))
    except (TypeError, ValueError):
        return bad_request("Invalid pagination parameters")

    queryset = SecurityScanFinding.objects.select_related("host_result").filter(task_id=task_id).order_by("id")
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    results = list(queryset[start:end])
    return Response(
        {
            "results": SecurityScanFindingSummarySerializer(results, many=True).data,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasNext": end < total,
        }
    )


@api_view(["GET"])
def scan_task_export(request, task_id: int):
    auth_error = security_scan_permission(request, "export")
    if auth_error:
        return auth_error
    try:
        task = SecurityScanTask.objects.prefetch_related("host_results", "findings").get(id=task_id)
    except SecurityScanTask.DoesNotExist:
        return not_found("Security scan task not found")
    export_format = str(request.query_params.get("format", "csv")).lower()
    if export_format == "json":
        response = JsonResponse(export_task_json(task), json_dumps_params={"ensure_ascii": False, "indent": 2})
        response["Content-Disposition"] = f'attachment; filename="security-scan-{task.id}.json"'
        return response
    if export_format != "csv":
        return bad_request("Unsupported export format")
    response = HttpResponse(export_task_csv(task), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="security-scan-{task.id}.csv"'
    return response
