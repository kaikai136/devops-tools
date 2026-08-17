from rest_framework import serializers

from .models import ApplicationInstallation, ApplicationSource, ApplicationTask


class ApplicationSourceSerializer(serializers.ModelSerializer):
    sourceType = serializers.CharField(source="source_type", read_only=True)
    lastSyncedAt = serializers.DateTimeField(source="last_synced_at", read_only=True)
    lastError = serializers.CharField(source="last_error", read_only=True)

    class Meta:
        model = ApplicationSource
        fields = ["id", "name", "sourceType", "url", "enabled", "lastSyncedAt", "lastError"]


class ApplicationInstallationSerializer(serializers.ModelSerializer):
    targetKey = serializers.CharField(source="target_key", read_only=True)
    targetType = serializers.CharField(source="target_type", read_only=True)
    targetHost = serializers.IntegerField(source="target_host_id", read_only=True)
    appId = serializers.CharField(source="app_id", read_only=True)
    lastProbedAt = serializers.DateTimeField(source="last_probed_at", read_only=True)

    class Meta:
        model = ApplicationInstallation
        fields = ["id", "appId", "targetKey", "targetType", "targetHost", "version", "status", "containers", "ports", "images", "lastProbedAt"]


class ApplicationTaskSerializer(serializers.ModelSerializer):
    appId = serializers.CharField(source="app_id", read_only=True)
    appName = serializers.CharField(source="app_name", read_only=True)
    targetKey = serializers.CharField(source="target_key", read_only=True)
    targetType = serializers.CharField(source="target_type", read_only=True)
    targetHost = serializers.IntegerField(source="target_host_id", read_only=True)
    cancelRequested = serializers.BooleanField(source="cancel_requested", read_only=True)
    planDigest = serializers.CharField(source="plan_digest", read_only=True)
    logOutput = serializers.CharField(source="log_output", read_only=True)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    finishedAt = serializers.DateTimeField(source="finished_at", read_only=True)

    class Meta:
        model = ApplicationTask
        fields = [
            "id",
            "appId",
            "appName",
            "action",
            "targetKey",
            "targetType",
            "targetHost",
            "status",
            "cancelRequested",
            "version",
            "config",
            "planDigest",
            "logOutput",
            "error",
            "createdBy",
            "createdAt",
            "startedAt",
            "finishedAt",
        ]

    def get_createdBy(self, instance):
        return instance.created_by.username if instance.created_by_id and instance.created_by else "system"
