from django.conf import settings
from django.db import models


class SecurityScanTask(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "排队中"),
        (STATUS_RUNNING, "扫描中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_FAILED, "失败"),
    ]

    name = models.CharField(max_length=180)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="security_scan_tasks", null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    target_count = models.PositiveIntegerField(default=0)
    completed_count = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    high_count = models.PositiveIntegerField(default=0)
    medium_count = models.PositiveIntegerField(default=0)
    low_count = models.PositiveIntegerField(default=0)
    info_count = models.PositiveIntegerField(default=0)
    options = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.name


class SecurityScanHostResult(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "等待中"),
        (STATUS_RUNNING, "扫描中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_FAILED, "失败"),
    ]

    task = models.ForeignKey(SecurityScanTask, related_name="host_results", on_delete=models.CASCADE)
    host = models.ForeignKey("host_management.ManagedHost", related_name="security_scan_results", null=True, blank=True, on_delete=models.SET_NULL)
    host_name = models.CharField(max_length=160)
    host_ip = models.GenericIPAddressField(protocol="IPv4")
    host_port = models.PositiveIntegerField(default=22)
    login_user = models.CharField(max_length=120, blank=True)
    os = models.CharField(max_length=40, blank=True)
    system_type = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    system_info = models.JSONField(default=dict, blank=True)
    open_ports = models.JSONField(default=list, blank=True)
    package_count = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    high_count = models.PositiveIntegerField(default=0)
    medium_count = models.PositiveIntegerField(default=0)
    low_count = models.PositiveIntegerField(default=0)
    info_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.task_id}:{self.host_name}"


class SecurityScanFinding(models.Model):
    SEVERITY_CRITICAL = "critical"
    SEVERITY_HIGH = "high"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_LOW = "low"
    SEVERITY_INFO = "info"
    SEVERITY_CHOICES = [
        (SEVERITY_CRITICAL, "严重"),
        (SEVERITY_HIGH, "高危"),
        (SEVERITY_MEDIUM, "中危"),
        (SEVERITY_LOW, "低危"),
        (SEVERITY_INFO, "提示"),
    ]

    task = models.ForeignKey(SecurityScanTask, related_name="findings", on_delete=models.CASCADE)
    host_result = models.ForeignKey(SecurityScanHostResult, related_name="findings", on_delete=models.CASCADE)
    category = models.CharField(max_length=40)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=260)
    description = models.TextField(blank=True)
    evidence = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    cve_id = models.CharField(max_length=80, blank=True)
    package_name = models.CharField(max_length=160, blank=True)
    current_version = models.CharField(max_length=160, blank=True)
    fixed_version = models.CharField(max_length=160, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    service = models.CharField(max_length=120, blank=True)
    cvss = models.FloatField(null=True, blank=True)
    cwe = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=40, blank=True)
    references = models.JSONField(default=list, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["task", "severity"], name="secscan_find_task_sev_idx"),
            models.Index(fields=["cve_id"], name="secscan_find_cve_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class VulnerabilityCache(models.Model):
    SOURCE_OSV = "osv"
    SOURCE_NVD = "nvd"
    SOURCE_CHOICES = [(SOURCE_OSV, "OSV"), (SOURCE_NVD, "NVD")]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    cache_key = models.CharField(max_length=260)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "cache_key"], name="unique_vulnerability_cache_key")]
        indexes = [models.Index(fields=["source", "cache_key"], name="secscan_cache_src_key_idx")]

    def __str__(self) -> str:
        return f"{self.source}:{self.cache_key}"
