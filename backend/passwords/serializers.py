from rest_framework import serializers

from .models import PasswordRecord


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
