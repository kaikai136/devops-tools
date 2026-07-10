from django.conf import settings
from django.db import models


class ScanTask(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "排队中"),
        (STATUS_RUNNING, "扫描中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_FAILED, "失败"),
        (STATUS_CANCELED, "已取消"),
    ]

    name = models.CharField(max_length=180)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="security_scan_tasks", null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    cancel_requested = models.BooleanField(default=False)
    target_count = models.PositiveIntegerField(default=0)
    completed_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    critical_count = models.PositiveIntegerField(default=0)
    high_count = models.PositiveIntegerField(default=0)
    medium_count = models.PositiveIntegerField(default=0)
    low_count = models.PositiveIntegerField(default=0)
    info_count = models.PositiveIntegerField(default=0)
    scan_modules = models.JSONField(default=dict, blank=True)
    options = models.JSONField(default=dict, blank=True)
    vulnerability_source = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="secscan_task_status_idx"),
            models.Index(fields=["-created_at"], name="secscan_task_created_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class ScanTargetResult(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "等待中"),
        (STATUS_RUNNING, "扫描中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_FAILED, "失败"),
        (STATUS_SKIPPED, "已跳过"),
    ]

    task = models.ForeignKey(ScanTask, related_name="target_results", on_delete=models.CASCADE)
    host = models.ForeignKey("host_management.ManagedHost", related_name="security_scan_results", null=True, blank=True, on_delete=models.SET_NULL)
    host_name = models.CharField(max_length=160)
    host_ip = models.GenericIPAddressField(protocol="IPv4")
    host_port = models.PositiveIntegerField(default=22)
    login_user = models.CharField(max_length=120, blank=True)
    os = models.CharField(max_length=40, blank=True)
    system_type = models.CharField(max_length=120, blank=True)
    system_arch = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    system_info = models.JSONField(default=dict, blank=True)
    open_ports = models.JSONField(default=list, blank=True)
    package_count = models.PositiveIntegerField(default=0)
    skipped_modules = models.JSONField(default=list, blank=True)
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
        indexes = [
            models.Index(fields=["task", "status"], name="secscan_target_status_idx"),
            models.Index(fields=["host"], name="secscan_target_host_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.task_id}:{self.host_name}"


class ScanFinding(models.Model):
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
    CATEGORY_BASELINE = "baseline"
    CATEGORY_PORT = "port"
    CATEGORY_CVE = "cve"

    task = models.ForeignKey(ScanTask, related_name="findings", on_delete=models.CASCADE)
    target_result = models.ForeignKey(ScanTargetResult, related_name="findings", on_delete=models.CASCADE)
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
            models.Index(fields=["task", "category"], name="secscan_find_task_cat_idx"),
            models.Index(fields=["target_result"], name="secscan_find_target_idx"),
            models.Index(fields=["cve_id"], name="secscan_find_cve_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class VulnerabilityCache(models.Model):
    SOURCE_OSV_BATCH = "osv_batch"
    SOURCE_NVD = "nvd"
    SOURCE_CHOICES = [(SOURCE_OSV_BATCH, "OSV Batch"), (SOURCE_NVD, "NVD")]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    cache_key = models.CharField(max_length=320)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "cache_key"], name="unique_vulnerability_cache_key")]
        indexes = [models.Index(fields=["source", "cache_key"], name="secscan_cache_src_key_idx")]

    def __str__(self) -> str:
        return f"{self.source}:{self.cache_key}"


# Backward-compatible imports for code paths that may still reference the old
# names during deployment reloads. New code should use ScanTask/ScanTargetResult/ScanFinding.
SecurityScanTask = ScanTask
SecurityScanHostResult = ScanTargetResult
SecurityScanFinding = ScanFinding
