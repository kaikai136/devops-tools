from rest_framework import serializers

from .models import CompanyDevice


class CompanyDeviceSerializer(serializers.ModelSerializer):
    name = serializers.CharField(error_messages={"blank": "请输入资产名称", "required": "请输入资产名称"})
    category = serializers.ChoiceField(
        choices=CompanyDevice.CATEGORY_CHOICES,
        default=CompanyDevice.CATEGORY_FIXED,
        error_messages={"invalid_choice": "资产类别只能选择固定资产或耗材"},
    )
    status = serializers.ChoiceField(
        choices=CompanyDevice.STATUS_CHOICES,
        default=CompanyDevice.STATUS_USING,
        error_messages={"invalid_choice": "资产状态只能选择使用中、闲置、维修或报废"},
    )
    purchaseTime = serializers.DateField(source="purchase_time", required=False, allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()

    class Meta:
        model = CompanyDevice
        fields = [
            "id",
            "name",
            "category",
            "code",
            "spec",
            "status",
            "user",
            "brand",
            "purchaseTime",
            "remark",
            "createdAt",
            "updatedAt",
            "createdBy",
        ]

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("请输入资产名称")
        return name

    def validate_category(self, value: str) -> str:
        return value.strip() or CompanyDevice.CATEGORY_FIXED

    def validate_code(self, value: str) -> str:
        return value.strip()

    def validate_spec(self, value: str) -> str:
        return value.strip()

    def validate_user(self, value: str) -> str:
        return value.strip()

    def validate_brand(self, value: str) -> str:
        return value.strip()

    def validate_remark(self, value: str) -> str:
        return value.strip()

    def get_createdBy(self, device: CompanyDevice) -> str:
        return device.created_by.username if device.created_by_id and device.created_by else "system"
