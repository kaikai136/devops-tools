from rest_framework import serializers

from .models import AuthenticatorEntry


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
