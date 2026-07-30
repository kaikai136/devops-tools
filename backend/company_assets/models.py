from django.conf import settings
from django.db import models


class CompanyDevice(models.Model):
    STATUS_USING = "using"
    STATUS_IDLE = "idle"
    STATUS_REPAIR = "repair"
    STATUS_CHOICES = [
        (STATUS_USING, "使用中"),
        (STATUS_IDLE, "闲置"),
        (STATUS_REPAIR, "维修中"),
    ]

    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, default="固定资产")
    code = models.CharField(max_length=120, blank=True)
    spec = models.CharField(max_length=260, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_USING)
    user = models.CharField(max_length=120, blank=True)
    brand = models.CharField(max_length=120, blank=True)
    purchase_time = models.DateField(null=True, blank=True)
    remark = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="company_devices",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["category"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return self.name
