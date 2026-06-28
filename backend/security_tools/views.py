from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_login
from operations.responses import bad_request, not_found, serializer_bad_request

from .models import SecurityCommandRecord, SecurityCommandRule
from .serializers import SecurityCommandRecordSerializer, SecurityCommandRuleSerializer


@api_view(["GET", "POST"])
def command_rules(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error

    if request.method == "GET":
        rules = SecurityCommandRule.objects.all().order_by("id")
        return Response(SecurityCommandRuleSerializer(rules, many=True).data)

    serializer = SecurityCommandRuleSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    rule = serializer.save()
    return Response(SecurityCommandRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def command_rule_detail(request, rule_id: int):
    auth_error = require_login(request)
    if auth_error:
        return auth_error

    try:
        rule = SecurityCommandRule.objects.get(id=rule_id)
    except SecurityCommandRule.DoesNotExist:
        return not_found("命令规则不存在")

    if request.method == "DELETE":
        rule.delete()
        return Response({"deleted": True})

    serializer = SecurityCommandRuleSerializer(rule, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(SecurityCommandRuleSerializer(serializer.save()).data)


@api_view(["POST"])
def command_rule_toggle(request, rule_id: int):
    auth_error = require_login(request)
    if auth_error:
        return auth_error

    try:
        rule = SecurityCommandRule.objects.get(id=rule_id)
    except SecurityCommandRule.DoesNotExist:
        return not_found("命令规则不存在")

    enabled = request.data.get("enabled")
    rule.enabled = (not rule.enabled) if enabled is None else bool(enabled)
    rule.save(update_fields=["enabled", "updated_at"])
    return Response(SecurityCommandRuleSerializer(rule).data)


@api_view(["GET"])
def command_records(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error

    try:
        limit = min(max(int(request.GET.get("limit", 100)), 1), 500)
    except (TypeError, ValueError):
        return bad_request("记录数量无效")

    records = SecurityCommandRecord.objects.select_related("user", "host", "session").all()[:limit]
    return Response(SecurityCommandRecordSerializer(records, many=True).data)
