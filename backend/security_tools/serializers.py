from rest_framework import serializers

from .models import SecurityCommandRecord, SecurityCommandRule
from .services import validate_regex_lines


class SecurityCommandRuleSerializer(serializers.ModelSerializer):
    matchType = serializers.ChoiceField(source="match_type", choices=SecurityCommandRule.MATCH_TYPE_CHOICES, required=False)
    ignoreCase = serializers.BooleanField(source="ignore_case", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = SecurityCommandRule
        fields = [
            "id",
            "name",
            "matchType",
            "content",
            "ignoreCase",
            "action",
            "enabled",
            "remark",
            "createdAt",
            "updatedAt",
        ]

    def validate_name(self, value):
        name = str(value or "").strip()
        if not name:
            raise serializers.ValidationError("请输入规则名称")
        return name

    def validate_content(self, value):
        content = str(value or "").strip()
        if not content:
            raise serializers.ValidationError("请输入命令内容")
        return content

    def validate_remark(self, value):
        return str(value or "").strip()

    def validate(self, attrs):
        match_type = attrs.get("match_type", getattr(self.instance, "match_type", SecurityCommandRule.MATCH_TYPE_COMMAND))
        content = attrs.get("content", getattr(self.instance, "content", ""))
        ignore_case = attrs.get("ignore_case", getattr(self.instance, "ignore_case", True))
        if match_type == SecurityCommandRule.MATCH_TYPE_REGEX:
            try:
                validate_regex_lines(content, ignore_case)
            except Exception as error:
                raise serializers.ValidationError({"content": f"正则表达式无效：{error}"}) from error
        return attrs


class SecurityCommandRecordSerializer(serializers.ModelSerializer):
    userName = serializers.SerializerMethodField()
    hostName = serializers.CharField(source="host.name", read_only=True, default="")
    hostIp = serializers.SerializerMethodField()
    sessionId = serializers.SerializerMethodField()
    ruleName = serializers.CharField(source="rule_name", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = SecurityCommandRecord
        fields = [
            "id",
            "userName",
            "hostName",
            "hostIp",
            "sessionId",
            "ruleName",
            "command",
            "action",
            "blocked",
            "message",
            "createdAt",
        ]

    def get_userName(self, obj):
        if not obj.user_id or not obj.user:
            return ""
        return obj.user.get_username()

    def get_hostIp(self, obj):
        if not obj.host_id or not obj.host:
            return ""
        return obj.host.public_ip or obj.host.private_ip

    def get_sessionId(self, obj):
        if not obj.session_id or not obj.session:
            return ""
        return str(obj.session.session_id)
