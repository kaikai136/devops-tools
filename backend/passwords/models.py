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
        db_table = "operations_passwordrecord"
        ordering = ["-created_at"]
