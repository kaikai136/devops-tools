from django.conf import settings
from django.db import models


def user_avatar_upload_path(instance, filename: str) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"avatars/user_{instance.user_id}.{suffix}"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to=user_avatar_upload_path, blank=True)
    totp_secret = models.CharField(max_length=64, blank=True)
    totp_pending_secret = models.CharField(max_length=64, blank=True)
    totp_enabled = models.BooleanField(default=False)
    totp_required = models.BooleanField(default=False)
    totp_reset_required = models.BooleanField(default=False)
    totp_confirmed_at = models.DateTimeField(null=True, blank=True)
    session_audit_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "用户资料"
        verbose_name_plural = "用户资料"

    def __str__(self) -> str:
        return f"{self.user.username} profile"

    @property
    def two_factor_status(self) -> str:
        if self.totp_required or self.totp_reset_required:
            return "required"
        if self.totp_enabled:
            return "enabled"
        return "disabled"
