from rest_framework import serializers

from .models import PingHistoryRecord


class PingHistoryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PingHistoryRecord
        fields = [
            "id",
            "target",
            "success_count",
            "failure_count",
            "loss_rate",
            "average_response_time",
            "min_response_time",
            "max_response_time",
            "jitter",
            "total_count",
            "created_at",
        ]
