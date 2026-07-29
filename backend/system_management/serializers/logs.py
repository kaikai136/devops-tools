from rest_framework import serializers

from ..models import LoginLog, OperationLog


class LoginLogSerializer(serializers.ModelSerializer):
    userDisplay = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    ipAddress = serializers.IPAddressField(source="ip_address", read_only=True)
    userAgent = serializers.CharField(source="user_agent", read_only=True)

    class Meta:
        model = LoginLog
        fields = ["id", "user", "userDisplay", "username", "ipAddress", "userAgent", "status", "message", "createdAt"]

    def get_userDisplay(self, obj):
        if not obj.user:
            return ""
        return obj.user.get_full_name() or obj.user.username


class OperationLogSerializer(serializers.ModelSerializer):
    userDisplay = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    ipAddress = serializers.IPAddressField(source="ip_address", read_only=True)
    userAgent = serializers.CharField(source="user_agent", read_only=True)

    class Meta:
        model = OperationLog
        fields = ["id", "user", "userDisplay", "username", "module", "action", "target", "detail", "ipAddress", "userAgent", "createdAt"]

    def get_userDisplay(self, obj):
        if not obj.user:
            return ""
        return obj.user.get_full_name() or obj.user.username
