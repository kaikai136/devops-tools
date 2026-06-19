from django.db import models


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
        db_table = "operations_pinghistoryrecord"
        ordering = ["-created_at"]
