from django.conf import settings
from django.db import models


class ApplicationSource(models.Model):
    SOURCE_BUILTIN = "builtin"
    SOURCE_REMOTE = "remote"
    SOURCE_CHOICES = [
        (SOURCE_BUILTIN, "Builtin"),
        (SOURCE_REMOTE, "Remote"),
    ]

    name = models.CharField(max_length=120)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_REMOTE)
    url = models.URLField(blank=True)
    enabled = models.BooleanField(default=True)
    cached_payload = models.JSONField(default=list, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ApplicationDefinition(models.Model):
    app_id = models.CharField(max_length=120)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=200, blank=True)
    version = models.CharField(max_length=80, default="1.0.0")
    source = models.CharField(max_length=80, default="remote")
    install_mode = models.CharField(max_length=40, default="compose")
    requirements = models.JSONField(default=dict, blank=True)
    config_schema = models.JSONField(default=list, blank=True)
    manifest = models.JSONField(default=dict, blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source", "category", "name"]
        constraints = [
            models.UniqueConstraint(fields=["source", "app_id"], name="unique_market_definition_source_app"),
        ]

    def __str__(self):
        return f"{self.source}:{self.app_id}"


class ApplicationInstallation(models.Model):
    TARGET_LOCAL = "local"
    TARGET_MANAGED_HOST = "managed_host"
    TARGET_CHOICES = [
        (TARGET_LOCAL, "Local"),
        (TARGET_MANAGED_HOST, "Managed host"),
    ]

    app_id = models.CharField(max_length=120)
    target_key = models.CharField(max_length=80)
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_host = models.ForeignKey("host_management.ManagedHost", null=True, blank=True, related_name="application_installations", on_delete=models.CASCADE)
    version = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=40, default="unknown")
    containers = models.JSONField(default=list, blank=True)
    ports = models.JSONField(default=list, blank=True)
    images = models.JSONField(default=list, blank=True)
    last_probed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_key", "app_id"]
        constraints = [
            models.UniqueConstraint(fields=["target_key", "app_id"], name="unique_market_installation_target_app"),
        ]

    def __str__(self):
        return f"{self.target_key}:{self.app_id}"


class ApplicationTask(models.Model):
    ACTION_INSTALL = "install"
    ACTION_UPDATE = "update"
    ACTION_UNINSTALL = "uninstall"
    ACTION_START = "start"
    ACTION_STOP = "stop"
    ACTION_RESTART = "restart"
    ACTION_CHOICES = [
        (ACTION_INSTALL, "Install"),
        (ACTION_UPDATE, "Update"),
        (ACTION_UNINSTALL, "Uninstall"),
        (ACTION_START, "Start"),
        (ACTION_STOP, "Stop"),
        (ACTION_RESTART, "Restart"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    STATUS_UNKNOWN = "unknown"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_UNKNOWN, "Unknown"),
    ]

    app_id = models.CharField(max_length=120)
    app_name = models.CharField(max_length=160)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_key = models.CharField(max_length=80)
    target_type = models.CharField(max_length=20, choices=ApplicationInstallation.TARGET_CHOICES)
    target_host = models.ForeignKey("host_management.ManagedHost", null=True, blank=True, related_name="application_tasks", on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    cancel_requested = models.BooleanField(default=False)
    version = models.CharField(max_length=80, blank=True)
    config = models.JSONField(default=dict, blank=True)
    plan = models.TextField(blank=True)
    plan_digest = models.CharField(max_length=128, blank=True)
    log_output = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="application_market_tasks", on_delete=models.SET_NULL)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="market_task_status_idx"),
            models.Index(fields=["target_key", "app_id"], name="market_task_target_app_idx"),
        ]

    def __str__(self):
        return f"{self.action} {self.app_id} on {self.target_key}"
