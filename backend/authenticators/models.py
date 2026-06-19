from django.db import models


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
        db_table = "operations_authenticatorentry"
        ordering = ["issuer", "account_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "account_name", "secret", "digits", "period", "algorithm"],
                name="unique_authenticator_entry",
            )
        ]
