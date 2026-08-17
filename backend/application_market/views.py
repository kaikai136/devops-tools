from __future__ import annotations

import json

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_feature_permission
from operations.responses import bad_request, get_object_or_error, paginate_queryset
from system_management.services import record_operation_log

from .models import ApplicationInstallation, ApplicationSource, ApplicationTask
from .serializers import ApplicationInstallationSerializer, ApplicationSourceSerializer, ApplicationTaskSerializer
from .services import catalog, plans, runner, sources, targets

ACTION_PERMISSION = {
    "install": "install",
    "update": "update",
    "uninstall": "uninstall",
    "start": "start",
    "stop": "stop",
    "restart": "restart",
}


def market_permission(request, action_key: str | None = None):
    return require_feature_permission(request, "applicationMarket", action_key, "没有应用市场权限")


@api_view(["GET"])
def catalog_view(request):
    auth_error = market_permission(request, "view")
    if auth_error:
        return auth_error
    target_key = str(request.query_params.get("target", "")).strip() or None
    apps = catalog.load_catalog(target_key=target_key)
    keyword = str(request.query_params.get("keyword", "")).strip().lower()
    category = str(request.query_params.get("category", "")).strip()
    source = str(request.query_params.get("source", "")).strip()
    status_filter = str(request.query_params.get("status", "")).strip()
    if keyword:
        apps = [app for app in apps if keyword in app["name"].lower() or keyword in app["description"].lower() or keyword in app["appId"].lower()]
    if category:
        apps = [app for app in apps if app["category"] == category]
    if source:
        apps = [app for app in apps if app["source"] == source]
    if status_filter:
        apps = [app for app in apps if app["status"] == status_filter]
    return Response({"apps": apps, "categories": sorted({app["category"] for app in catalog.load_catalog()}), "sources": sorted({app["source"] for app in catalog.load_catalog()})})


@api_view(["GET"])
def app_detail(request, app_id: str):
    auth_error = market_permission(request, "view")
    if auth_error:
        return auth_error
    try:
        return Response(catalog.get_app(app_id))
    except ValueError as error:
        return bad_request(error)


@api_view(["GET"])
def target_list(request):
    auth_error = market_permission(request, "view")
    if auth_error:
        return auth_error
    return Response({"targets": targets.list_targets()})


@api_view(["GET"])
def installed_list(request):
    auth_error = market_permission(request, "view")
    if auth_error:
        return auth_error
    target_key = str(request.query_params.get("target", "")).strip()
    queryset = ApplicationInstallation.objects.all()
    if target_key:
        queryset = queryset.filter(target_key=target_key)
    return Response({"installed": ApplicationInstallationSerializer(queryset, many=True).data})


@api_view(["POST"])
def preview(request):
    action = str(request.data.get("action") or "install")
    auth_error = market_permission(request, ACTION_PERMISSION.get(action, "install"))
    if auth_error:
        return auth_error
    try:
        payload = plans.preview_plan(
            str(request.data.get("appId") or request.data.get("app_id") or ""),
            str(request.data.get("target") or "local"),
            action,
            request.data.get("config") if isinstance(request.data.get("config"), dict) else {},
        )
        return Response(payload)
    except (TypeError, ValueError) as error:
        return bad_request(error)


@api_view(["GET", "POST"])
def tasks_view(request):
    if request.method == "GET":
        auth_error = market_permission(request, "view_tasks")
        if auth_error:
            return auth_error
        queryset = ApplicationTask.objects.select_related("created_by", "target_host").all()
        keyword = str(request.query_params.get("keyword", "")).strip()
        status_filter = str(request.query_params.get("status", "")).strip()
        if keyword:
            queryset = queryset.filter(Q(app_name__icontains=keyword) | Q(app_id__icontains=keyword) | Q(target_key__icontains=keyword))
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return Response(paginate_queryset(queryset, request, serializer=ApplicationTaskSerializer))

    action = str(request.data.get("action") or "install")
    auth_error = market_permission(request, ACTION_PERMISSION.get(action, "install"))
    if auth_error:
        return auth_error
    try:
        plan = plans.build_plan(
            str(request.data.get("appId") or request.data.get("app_id") or ""),
            str(request.data.get("target") or "local"),
            action,
            request.data.get("config") if isinstance(request.data.get("config"), dict) else {},
        )
        plans.assert_digest(plan, str(request.data.get("planDigest") or request.data.get("plan_digest") or ""))
        task = ApplicationTask.objects.create(
            app_id=plan["appId"],
            app_name=plan["appName"],
            action=plan["action"],
            target_key=plan["target"],
            target_type=plan["targetType"],
            target_host_id=plan["targetHostId"],
            version=plan["version"],
            config=plan["config"],
            plan=json.dumps(plan, ensure_ascii=False, sort_keys=True),
            plan_digest=plans.digest_plan(plan),
            log_output="Application task queued with confirmed preview plan.",
            created_by=request.user if request.user.is_authenticated else None,
        )
    except (TypeError, ValueError) as error:
        return bad_request(error)
    record_operation_log(request, "应用市场", f"{task.action} 应用", task.app_id, f"{task.target_key} {task.app_name}")
    runner.start_application_task(task.id)
    task.refresh_from_db()
    return Response(ApplicationTaskSerializer(task).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def task_detail(request, task_id: int):
    auth_error = market_permission(request, "view_tasks")
    if auth_error:
        return auth_error
    task, error = get_object_or_error(ApplicationTask, id=task_id, error_message="应用市场任务不存在")
    if error:
        return error
    return Response(ApplicationTaskSerializer(task).data)


@api_view(["POST"])
def task_cancel(request, task_id: int):
    auth_error = market_permission(request, "stop")
    if auth_error:
        return auth_error
    task, error = get_object_or_error(ApplicationTask, id=task_id, error_message="应用市场任务不存在")
    if error:
        return error
    if task.status not in {ApplicationTask.STATUS_QUEUED, ApplicationTask.STATUS_RUNNING}:
        return bad_request("Only queued or running tasks can be canceled")
    task.cancel_requested = True
    if task.status == ApplicationTask.STATUS_QUEUED:
        task.status = ApplicationTask.STATUS_CANCELED
    task.save(update_fields=["cancel_requested", "status"])
    return Response({"cancelRequested": True, "status": task.status})


@api_view(["GET"])
def source_list(request):
    auth_error = market_permission(request, "manage_sources")
    if auth_error:
        return auth_error
    return Response({"sources": ApplicationSourceSerializer(ApplicationSource.objects.all(), many=True).data})


@api_view(["POST"])
def source_sync(request):
    auth_error = market_permission(request, "manage_sources")
    if auth_error:
        return auth_error
    result = sources.sync_enabled_remote_sources()
    record_operation_log(request, "应用市场", "同步应用源", "application sources", json.dumps(result, ensure_ascii=False))
    return Response({"results": result})


@api_view(["PUT"])
def source_detail(request, source_id: int):
    auth_error = market_permission(request, "manage_sources")
    if auth_error:
        return auth_error
    source, error = get_object_or_error(ApplicationSource, id=source_id, error_message="应用源不存在")
    if error:
        return error
    if "enabled" in request.data:
        source.enabled = bool(request.data.get("enabled"))
    if "name" in request.data:
        source.name = str(request.data.get("name") or source.name).strip()[:120] or source.name
    if "url" in request.data:
        source.url = str(request.data.get("url") or "").strip()
    source.save(update_fields=["enabled", "name", "url", "updated_at"])
    return Response(ApplicationSourceSerializer(source).data)
