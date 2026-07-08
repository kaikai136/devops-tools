import uuid

from django.conf import settings
from django.db import models

from host_management.models import ManagedHost


class TerminalQuickCommand(models.Model):
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=80)
    command = models.TextField()
    description = models.CharField(max_length=255, blank=True)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "sort_order", "id"]
        indexes = [
            models.Index(fields=["category", "sort_order"]),
            models.Index(fields=["enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.category} / {self.name}"


class TerminalSession(models.Model):
    PROTOCOL_SSH = "ssh"
    PROTOCOL_RDP = "rdp"
    PROTOCOL_CHOICES = [
        (PROTOCOL_SSH, "SSH"),
        (PROTOCOL_RDP, "RDP"),
    ]

    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    host = models.ForeignKey(ManagedHost, related_name="terminal_sessions", on_delete=models.CASCADE)
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES, default=PROTOCOL_SSH)
    status = models.CharField(max_length=20, default="connected")
    transcript = models.TextField(blank=True)
    recording = models.TextField(blank=True)
    recording_file = models.CharField(max_length=500, blank=True)
    recording_enabled = models.BooleanField(default=False)
    recording_started_at = models.DateTimeField(null=True, blank=True)
    recording_last_event_at = models.DateTimeField(null=True, blank=True)
    recording_cols = models.PositiveSmallIntegerField(default=120)
    recording_rows = models.PositiveSmallIntegerField(default=36)
    recording_has_input = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    last_command_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.host.name} · {self.session_id}"


class TerminalCommandAudit(models.Model):
    RISK_ACCEPT = "accept"
    RISK_MEDIUM = "medium"
    RISK_HIGH = "high"
    RISK_CHOICES = [
        (RISK_ACCEPT, "接受"),
        (RISK_MEDIUM, "中风险"),
        (RISK_HIGH, "高风险"),
    ]

    session = models.ForeignKey(TerminalSession, related_name="command_audits", on_delete=models.CASCADE)
    host = models.ForeignKey(ManagedHost, related_name="terminal_command_audits", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="terminal_command_audits",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    username = models.CharField(max_length=150)
    command = models.TextField()
    output = models.TextField(blank=True)
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES, default=RISK_ACCEPT)
    asset_name = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    executed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-executed_at", "-id"]
        indexes = [
            models.Index(fields=["-executed_at", "-id"]),
            models.Index(fields=["risk_level", "-executed_at"]),
            models.Index(fields=["host", "-executed_at"]),
            models.Index(fields=["session", "-executed_at"]),
            models.Index(fields=["username"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} {self.command[:60]} {self.executed_at:%Y-%m-%d %H:%M:%S}"
