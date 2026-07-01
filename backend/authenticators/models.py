from django.db import models
from django.conf import settings


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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="authenticator_entries")

    class Meta:
        db_table = "operations_authenticatorentry"
        ordering = ["issuer", "account_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "issuer", "account_name", "secret", "digits", "period", "algorithm"],
                name="unique_authenticator_entry",
            )
        ]
