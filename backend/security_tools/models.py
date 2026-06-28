from django.conf import settings
from django.db import models

from host_management.models import ManagedHost
from web_terminal.models import TerminalSession


class SecurityCommandRule(models.Model):
    MATCH_TYPE_COMMAND = "command"
    MATCH_TYPE_REGEX = "regex"
    MATCH_TYPE_CHOICES = [
        (MATCH_TYPE_COMMAND, "Command"),
        (MATCH_TYPE_REGEX, "Regex"),
    ]

    ACTION_BLOCK = "block"
    ACTION_WARN = "warn"
    ACTION_CHOICES = [
        (ACTION_BLOCK, "Block"),
        (ACTION_WARN, "Warn"),
    ]

    name = models.CharField(max_length=120)
    match_type = models.CharField(max_length=20, choices=MATCH_TYPE_CHOICES, default=MATCH_TYPE_COMMAND)
    content = models.TextField()
    ignore_case = models.BooleanField(default=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_BLOCK)
    enabled = models.BooleanField(default=True)
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["enabled", "id"]),
            models.Index(fields=["match_type"]),
        ]

    def __str__(self) -> str:
        return self.name


class SecurityCommandRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    host = models.ForeignKey(ManagedHost, null=True, blank=True, on_delete=models.SET_NULL)
    session = models.ForeignKey(TerminalSession, null=True, blank=True, on_delete=models.SET_NULL)
    rule = models.ForeignKey(SecurityCommandRule, null=True, blank=True, on_delete=models.SET_NULL)
    rule_name = models.CharField(max_length=120, blank=True)
    command = models.TextField()
    action = models.CharField(max_length=20, choices=SecurityCommandRule.ACTION_CHOICES)
    blocked = models.BooleanField(default=False)
    message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["blocked"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        return f"{self.rule_name or 'security rule'}: {self.command[:80]}"
