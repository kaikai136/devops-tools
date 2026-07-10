from rest_framework import serializers

from .models import ScanFinding, ScanTargetResult, ScanTask


def risk_counts(instance) -> dict:
    return {
        "critical": instance.critical_count,
        "high": instance.high_count,
        "medium": instance.medium_count,
        "low": instance.low_count,
        "info": instance.info_count,
    }


class ScanTaskSerializer(serializers.ModelSerializer):
    targetCount = serializers.IntegerField(source="target_count", read_only=True)
    completedCount = serializers.IntegerField(source="completed_count", read_only=True)
    failedCount = serializers.IntegerField(source="failed_count", read_only=True)
    cancelRequested = serializers.BooleanField(source="cancel_requested", read_only=True)
    riskCounts = serializers.SerializerMethodField()
    scanModules = serializers.JSONField(source="scan_modules", read_only=True)
    vulnerabilitySource = serializers.JSONField(source="vulnerability_source", read_only=True)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    finishedAt = serializers.DateTimeField(source="finished_at", read_only=True)

    class Meta:
        model = ScanTask
        fields = [
            "id",
            "name",
            "status",
            "cancelRequested",
            "targetCount",
            "completedCount",
            "failedCount",
            "riskCounts",
            "scanModules",
            "options",
            "vulnerabilitySource",
            "error",
            "createdBy",
            "createdAt",
            "startedAt",
            "finishedAt",
        ]

    def get_riskCounts(self, instance):
        return risk_counts(instance)

    def get_createdBy(self, instance):
        return instance.created_by.username if instance.created_by_id and instance.created_by else "system"


class ScanTargetResultSerializer(serializers.ModelSerializer):
    hostName = serializers.CharField(source="host_name", read_only=True)
    hostIp = serializers.IPAddressField(source="host_ip", read_only=True)
    hostPort = serializers.IntegerField(source="host_port", read_only=True)
    loginUser = serializers.CharField(source="login_user", read_only=True)
    systemType = serializers.CharField(source="system_type", read_only=True)
    systemArch = serializers.CharField(source="system_arch", read_only=True)
    systemInfo = serializers.JSONField(source="system_info", read_only=True)
    openPorts = serializers.JSONField(source="open_ports", read_only=True)
    packageCount = serializers.IntegerField(source="package_count", read_only=True)
    skippedModules = serializers.JSONField(source="skipped_modules", read_only=True)
    riskCounts = serializers.SerializerMethodField()
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    finishedAt = serializers.DateTimeField(source="finished_at", read_only=True)

    class Meta:
        model = ScanTargetResult
        fields = [
            "id",
            "host",
            "hostName",
            "hostIp",
            "hostPort",
            "loginUser",
            "os",
            "systemType",
            "systemArch",
            "status",
            "systemInfo",
            "openPorts",
            "packageCount",
            "skippedModules",
            "riskCounts",
            "error",
            "startedAt",
            "finishedAt",
        ]

    def get_riskCounts(self, instance):
        return risk_counts(instance)


class ScanFindingSerializer(serializers.ModelSerializer):
    targetResult = serializers.IntegerField(source="target_result_id", read_only=True)
    targetName = serializers.CharField(source="target_result.host_name", read_only=True)
    targetIp = serializers.IPAddressField(source="target_result.host_ip", read_only=True)
    cveId = serializers.CharField(source="cve_id", read_only=True)
    packageName = serializers.CharField(source="package_name", read_only=True)
    currentVersion = serializers.CharField(source="current_version", read_only=True)
    fixedVersion = serializers.CharField(source="fixed_version", read_only=True)

    class Meta:
        model = ScanFinding
        fields = [
            "id",
            "targetResult",
            "targetName",
            "targetIp",
            "category",
            "severity",
            "title",
            "description",
            "evidence",
            "recommendation",
            "cveId",
            "packageName",
            "currentVersion",
            "fixedVersion",
            "port",
            "service",
            "cvss",
            "cwe",
            "source",
            "references",
            "raw",
        ]


class ScanFindingSummarySerializer(serializers.ModelSerializer):
    targetResult = serializers.IntegerField(source="target_result_id", read_only=True)
    targetName = serializers.CharField(source="target_result.host_name", read_only=True)
    targetIp = serializers.IPAddressField(source="target_result.host_ip", read_only=True)
    cveId = serializers.CharField(source="cve_id", read_only=True)
    packageName = serializers.CharField(source="package_name", read_only=True)
    currentVersion = serializers.CharField(source="current_version", read_only=True)
    fixedVersion = serializers.CharField(source="fixed_version", read_only=True)

    class Meta:
        model = ScanFinding
        fields = [
            "id",
            "targetResult",
            "targetName",
            "targetIp",
            "category",
            "severity",
            "title",
            "recommendation",
            "cveId",
            "packageName",
            "currentVersion",
            "fixedVersion",
            "port",
            "service",
            "cvss",
            "cwe",
            "source",
        ]


class ScanTaskDetailSerializer(ScanTaskSerializer):
    targetResults = serializers.SerializerMethodField()

    class Meta(ScanTaskSerializer.Meta):
        fields = ScanTaskSerializer.Meta.fields + ["targetResults"]

    def get_targetResults(self, instance):
        return ScanTargetResultSerializer(instance.target_results.all(), many=True).data


class ScanTaskExportSerializer(ScanTaskDetailSerializer):
    findings = serializers.SerializerMethodField()

    class Meta(ScanTaskDetailSerializer.Meta):
        fields = ScanTaskDetailSerializer.Meta.fields + ["findings"]

    def get_findings(self, instance):
        return ScanFindingSerializer(instance.findings.select_related("target_result").all(), many=True).data
