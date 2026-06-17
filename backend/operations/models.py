from django.db import models


class PasswordRecord(models.Model):
    project_name = models.CharField(max_length=200, blank=True)
    password = models.CharField(max_length=200)
    length = models.PositiveSmallIntegerField(default=16)
    include_uppercase = models.BooleanField(default=True)
    include_lowercase = models.BooleanField(default=True)
    include_numbers = models.BooleanField(default=True)
    include_symbols = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PingHistoryRecord(models.Model):
    target = models.CharField(max_length=255)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    loss_rate = models.PositiveSmallIntegerField(default=0)
    average_response_time = models.PositiveIntegerField(null=True, blank=True)
    min_response_time = models.PositiveIntegerField(null=True, blank=True)
    max_response_time = models.PositiveIntegerField(null=True, blank=True)
    jitter = models.PositiveIntegerField(null=True, blank=True)
    total_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuthenticatorEntry(models.Model):
    ALGORITHM_CHOICES = [
        ("SHA1", "SHA-1"),
        ("SHA256", "SHA-256"),
        ("SHA512", "SHA-512"),
    ]

    issuer = models.CharField(max_length=200, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    secret = models.CharField(max_length=200)
    digits = models.PositiveSmallIntegerField(default=6)
    period = models.PositiveSmallIntegerField(default=30)
    algorithm = models.CharField(max_length=10, choices=ALGORITHM_CHOICES, default="SHA1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["issuer", "account_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "account_name", "secret", "digits", "period", "algorithm"],
                name="unique_authenticator_entry",
            )
        ]
