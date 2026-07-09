from rest_framework import serializers

from .models import SecurityScanFinding, SecurityScanHostResult, SecurityScanTask


def risk_counts(instance) -> dict:
    return {
        "critical": instance.critical_count,
        "high": instance.high_count,
        "medium": instance.medium_count,
        "low": instance.low_count,
        "info": instance.info_count,
    }


class SecurityScanTaskSerializer(serializers.ModelSerializer):
    targetCount = serializers.IntegerField(source="target_count", read_only=True)
    completedCount = serializers.IntegerField(source="completed_count", read_only=True)
    riskCounts = serializers.SerializerMethodField()
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    finishedAt = serializers.DateTimeField(source="finished_at", read_only=True)

    class Meta:
        model = SecurityScanTask
        fields = [
            "id",
            "name",
            "status",
            "targetCount",
            "completedCount",
            "riskCounts",
            "options",
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


class SecurityScanHostResultSerializer(serializers.ModelSerializer):
    hostName = serializers.CharField(source="host_name", read_only=True)
    hostIp = serializers.IPAddressField(source="host_ip", read_only=True)
    hostPort = serializers.IntegerField(source="host_port", read_only=True)
    loginUser = serializers.CharField(source="login_user", read_only=True)
    systemType = serializers.CharField(source="system_type", read_only=True)
    systemInfo = serializers.JSONField(source="system_info", read_only=True)
    openPorts = serializers.JSONField(source="open_ports", read_only=True)
    packageCount = serializers.IntegerField(source="package_count", read_only=True)
    riskCounts = serializers.SerializerMethodField()
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    finishedAt = serializers.DateTimeField(source="finished_at", read_only=True)

    class Meta:
        model = SecurityScanHostResult
        fields = [
            "id",
            "host",
            "hostName",
            "hostIp",
            "hostPort",
            "loginUser",
            "os",
            "systemType",
            "status",
            "systemInfo",
            "openPorts",
            "packageCount",
            "riskCounts",
            "error",
            "startedAt",
            "finishedAt",
        ]

    def get_riskCounts(self, instance):
        return risk_counts(instance)


class SecurityScanFindingSerializer(serializers.ModelSerializer):
    hostResult = serializers.IntegerField(source="host_result_id", read_only=True)
    hostName = serializers.CharField(source="host_result.host_name", read_only=True)
    hostIp = serializers.IPAddressField(source="host_result.host_ip", read_only=True)
    cveId = serializers.CharField(source="cve_id", read_only=True)
    packageName = serializers.CharField(source="package_name", read_only=True)
    currentVersion = serializers.CharField(source="current_version", read_only=True)
    fixedVersion = serializers.CharField(source="fixed_version", read_only=True)

    class Meta:
        model = SecurityScanFinding
        fields = [
            "id",
            "hostResult",
            "hostName",
            "hostIp",
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


class SecurityScanFindingSummarySerializer(serializers.ModelSerializer):
    hostResult = serializers.IntegerField(source="host_result_id", read_only=True)
    hostName = serializers.CharField(source="host_result.host_name", read_only=True)
    hostIp = serializers.IPAddressField(source="host_result.host_ip", read_only=True)
    cveId = serializers.CharField(source="cve_id", read_only=True)
    packageName = serializers.CharField(source="package_name", read_only=True)
    currentVersion = serializers.CharField(source="current_version", read_only=True)
    fixedVersion = serializers.CharField(source="fixed_version", read_only=True)

    class Meta:
        model = SecurityScanFinding
        fields = [
            "id",
            "hostResult",
            "hostName",
            "hostIp",
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


class SecurityScanTaskDetailSerializer(SecurityScanTaskSerializer):
    hostResults = serializers.SerializerMethodField()

    class Meta(SecurityScanTaskSerializer.Meta):
        fields = SecurityScanTaskSerializer.Meta.fields + ["hostResults"]

    def get_hostResults(self, instance):
        return SecurityScanHostResultSerializer(instance.host_results.all(), many=True).data


class SecurityScanTaskExportSerializer(SecurityScanTaskDetailSerializer):
    findings = serializers.SerializerMethodField()

    class Meta(SecurityScanTaskDetailSerializer.Meta):
        fields = SecurityScanTaskDetailSerializer.Meta.fields + ["findings"]

    def get_findings(self, instance):
        return SecurityScanFindingSerializer(instance.findings.select_related("host_result").all(), many=True).data
