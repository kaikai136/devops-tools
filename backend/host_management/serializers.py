from rest_framework import serializers

from .models import HostCredential, HostGroup, ManagedHost


class ManagedHostSerializer(serializers.ModelSerializer):
    group = serializers.IntegerField(source="group_id")
    publicIp = serializers.IPAddressField(source="public_ip", required=False, allow_null=True)
    privateIp = serializers.IPAddressField(source="private_ip")
    port = serializers.IntegerField(required=False)
    loginUser = serializers.CharField(source="login_user", required=False, allow_blank=True)
    loginPassword = serializers.CharField(source="login_password", required=False, allow_blank=True)
    privateKeyName = serializers.CharField(source="private_key_name", required=False, allow_blank=True)
    privateKey = serializers.CharField(source="private_key", required=False, allow_blank=True)
    verifyStatus = serializers.CharField(source="verify_status", read_only=True)
    remark = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = ManagedHost
        fields = [
            "id",
            "name",
            "group",
            "publicIp",
            "privateIp",
            "port",
            "loginUser",
            "loginPassword",
            "privateKeyName",
            "privateKey",
            "remark",
            "cpu",
            "memory",
            "os",
            "verified",
            "verifyStatus",
        ]


class HostCredentialSerializer(serializers.ModelSerializer):
    privateKeyName = serializers.CharField(source="private_key_name", required=False, allow_blank=True)
    privateKey = serializers.CharField(source="private_key", required=False, allow_blank=True)

    class Meta:
        model = HostCredential
        fields = ["id", "name", "username", "password", "port", "privateKeyName", "privateKey", "remark"]


class HostGroupSerializer(serializers.ModelSerializer):
    key = serializers.IntegerField(source="id")
    label = serializers.CharField(source="name")
    count = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = HostGroup
        fields = ["key", "label", "count", "children"]

    def get_count(self, group: HostGroup) -> int:
        counts = self.context.get("counts", {})
        return counts.get(group.id, 0)

    def get_children(self, group: HostGroup) -> list[dict]:
        children = list(getattr(group, "_prefetched_children", []))
        return HostGroupSerializer(children, many=True, context=self.context).data
