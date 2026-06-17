from rest_framework import serializers

from .models import AuthenticatorEntry, PasswordRecord, PingHistoryRecord


class PasswordRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PasswordRecord
        fields = [
            "id",
            "project_name",
            "password",
            "length",
            "include_uppercase",
            "include_lowercase",
            "include_numbers",
            "include_symbols",
            "created_at",
        ]


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


class AuthenticatorEntrySerializer(serializers.ModelSerializer):
    algorithm_label = serializers.CharField(source="get_algorithm_display", read_only=True)

    class Meta:
        model = AuthenticatorEntry
        fields = [
            "id",
            "issuer",
            "account_name",
            "secret",
            "digits",
            "period",
            "algorithm",
            "algorithm_label",
            "created_at",
        ]
