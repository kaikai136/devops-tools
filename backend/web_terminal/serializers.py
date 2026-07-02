from rest_framework import serializers

from .models import TerminalCommandAudit, TerminalQuickCommand


class TerminalQuickCommandSerializer(serializers.ModelSerializer):
    sortOrder = serializers.IntegerField(source="sort_order", required=False, min_value=0)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = TerminalQuickCommand
        fields = [
            "id",
            "name",
            "category",
            "command",
            "description",
            "enabled",
            "sortOrder",
            "createdAt",
            "updatedAt",
        ]

    def validate_name(self, value):
        name = str(value).strip()
        if not name:
            raise serializers.ValidationError("请输入命令名称")
        return name

    def validate_category(self, value):
        category = str(value).strip()
        if not category:
            raise serializers.ValidationError("请输入命令分类")
        return category

    def validate_command(self, value):
        command = str(value).strip()
        if not command:
            raise serializers.ValidationError("请输入命令内容")
        return command

    def validate_description(self, value):
        return str(value or "").strip()


class TerminalCommandAuditSerializer(serializers.ModelSerializer):
    riskLevel = serializers.CharField(source="risk_level")
    assetName = serializers.CharField(source="asset_name")
    ipAddress = serializers.SerializerMethodField()
    sessionId = serializers.UUIDField(source="session.session_id")
    hostId = serializers.IntegerField(source="host_id")
    executedAt = serializers.DateTimeField(source="executed_at")

    class Meta:
        model = TerminalCommandAudit
        fields = [
            "id",
            "username",
            "command",
            "output",
            "riskLevel",
            "assetName",
            "ipAddress",
            "sessionId",
            "hostId",
            "executedAt",
        ]

    def get_ipAddress(self, obj):
        return str(obj.ip_address) if obj.ip_address else ""
