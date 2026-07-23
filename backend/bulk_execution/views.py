from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_feature_permission
from operations.responses import bad_request, bounded_int, not_found

from .models import BulkExecutionResult, BulkExecutionTask
from .serializers import BulkExecutionTaskDetailSerializer, BulkExecutionTaskSerializer
from .services import create_bulk_execution_task, list_executable_targets, mark_interrupted_tasks, refresh_task_counts, start_bulk_execution_task


def bulk_execution_permission(request, action_key: str | None = None):
    return require_feature_permission(request, "bulkExecution", action_key, "No bulk execution permission")


@api_view(["GET"])
def targets(request):
    auth_error = bulk_execution_permission(request, "execute")
    if auth_error:
        return auth_error
    hosts = list_executable_targets()
    return Response(
        [
            {
                "id": host.id,
                "name": host.name,
                "group": host.group_id,
                "groupName": host.group.name if host.group_id and host.group else "",
                "privateIp": host.private_ip,
                "publicIp": host.public_ip,
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
def tasks(request):
    if request.method == "GET":
        auth_error = bulk_execution_permission(request, "refresh")
        if auth_error:
            return auth_error
        mark_interrupted_tasks()
        queryset = BulkExecutionTask.objects.select_related("created_by").all()
        status_filter = str(request.query_params.get("status", "")).strip()
        keyword = str(request.query_params.get("keyword", "")).strip()
        host = str(request.query_params.get("host", "")).strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(command__icontains=keyword))
        if host:
            try:
                queryset = queryset.filter(results__host_id=int(host)).distinct()
            except (TypeError, ValueError):
                return bad_request("Invalid host filter")
        return paginated_tasks_response(queryset, request)

    auth_error = bulk_execution_permission(request, "execute")
    if auth_error:
        return auth_error
    try:
        task = create_bulk_execution_task(request.user, request.data if isinstance(request.data, dict) else {})
    except (TypeError, ValueError) as error:
        return bad_request(error)
    start_bulk_execution_task(task.id)
    task.refresh_from_db()
    return Response(BulkExecutionTaskSerializer(task).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
def task_detail(request, task_id: int):
    action = "delete" if request.method == "DELETE" else "refresh"
    auth_error = bulk_execution_permission(request, action)
    if auth_error:
        return auth_error
    try:
        task = BulkExecutionTask.objects.select_related("created_by").prefetch_related("results").get(id=task_id)
    except BulkExecutionTask.DoesNotExist:
        return not_found("Bulk execution task not found")
    if request.method == "DELETE":
        task.delete()
        return Response({"deleted": True})
    refresh_task_counts(task)
    task.refresh_from_db()
    return Response(BulkExecutionTaskDetailSerializer(task).data)


@api_view(["POST"])
def task_cancel(request, task_id: int):
    auth_error = bulk_execution_permission(request, "cancel")
    if auth_error:
        return auth_error
    try:
        task = BulkExecutionTask.objects.get(id=task_id)
    except BulkExecutionTask.DoesNotExist:
        return not_found("Bulk execution task not found")
    if task.status not in {BulkExecutionTask.STATUS_QUEUED, BulkExecutionTask.STATUS_RUNNING}:
        return bad_request("Only queued or running tasks can be canceled")
    task.cancel_requested = True
    if task.status == BulkExecutionTask.STATUS_QUEUED:
        now = timezone.now()
        task.status = BulkExecutionTask.STATUS_CANCELED
        task.finished_at = task.finished_at or now
        task.results.filter(status__in=[BulkExecutionResult.STATUS_PENDING, BulkExecutionResult.STATUS_RUNNING]).update(
            status=BulkExecutionResult.STATUS_SKIPPED,
            error="Task canceled",
            finished_at=now,
        )
        refresh_task_counts(task)
        task.save(update_fields=["cancel_requested", "status", "finished_at", "completed_count", "success_count", "failed_count", "skipped_count"])
    else:
        task.save(update_fields=["cancel_requested"])
    return Response({"cancelRequested": True, "status": task.status})


def paginated_tasks_response(queryset, request):
    page_size = bounded_int(request.query_params.get("pageSize"), default=20, minimum=1, maximum=100)
    page_number = bounded_int(request.query_params.get("page"), default=1, minimum=1, maximum=1000000)
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
            "results": BulkExecutionTaskSerializer(page.object_list, many=True).data,
        }
    )
