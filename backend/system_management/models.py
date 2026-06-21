from django.conf import settings
from django.db import models


class LoginLog(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="login_logs", null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["username"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.username} {self.status} {self.created_at:%Y-%m-%d %H:%M:%S}"


class SystemSetting(models.Model):
    key = models.CharField(max_length=120, unique=True)
    value = models.JSONField(default=dict, blank=True)
    label = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key
