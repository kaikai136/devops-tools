from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from .models import LoginLog, SystemSetting


class LoginLogSerializer(serializers.ModelSerializer):
    userDisplay = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    ipAddress = serializers.IPAddressField(source="ip_address", read_only=True)
    userAgent = serializers.CharField(source="user_agent", read_only=True)

    class Meta:
        model = LoginLog
        fields = ["id", "user", "userDisplay", "username", "ipAddress", "userAgent", "status", "message", "createdAt"]

    def get_userDisplay(self, obj):
        if not obj.user:
            return ""
        return obj.user.get_full_name() or obj.user.username


class SystemUserSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", required=False, allow_blank=True)
    isActive = serializers.BooleanField(source="is_active", required=False)
    isStaff = serializers.BooleanField(source="is_staff", required=False)
    isSuperuser = serializers.BooleanField(source="is_superuser", read_only=True)
    lastLogin = serializers.DateTimeField(source="last_login", read_only=True)
    dateJoined = serializers.DateTimeField(source="date_joined", read_only=True)
    roleIds = serializers.PrimaryKeyRelatedField(source="groups", queryset=Group.objects.all(), many=True, required=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "username",
            "email",
            "firstName",
            "isActive",
            "isStaff",
            "isSuperuser",
            "lastLogin",
            "dateJoined",
            "roleIds",
            "password",
        ]

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError("请输入用户名")

        queryset = get_user_model().objects.filter(username=username)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("用户名已存在")
        return username

    def validate(self, attrs):
        if self.instance is None and not str(attrs.get("password", "")).strip():
            raise serializers.ValidationError({"password": "请输入初始密码"})
        return attrs

    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        password = validated_data.pop("password", "")
        user = get_user_model().objects.create_user(password=password, **validated_data)
        user.groups.set(groups)
        return user

    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        password = str(validated_data.pop("password", "")).strip()

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if groups is not None:
            instance.groups.set(groups)
        return instance


class PermissionSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="name", read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "codename", "label"]


class RoleSerializer(serializers.ModelSerializer):
    permissionIds = serializers.PrimaryKeyRelatedField(source="permissions", queryset=Permission.objects.all(), many=True, required=False)

    class Meta:
        model = Group
        fields = ["id", "name", "permissionIds"]

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("请输入角色名称")

        queryset = Group.objects.filter(name=name)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("角色名称已存在")
        return name


class SystemSettingSerializer(serializers.ModelSerializer):
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = SystemSetting
        fields = ["id", "key", "label", "description", "value", "updatedAt"]

    def validate_key(self, value):
        key = value.strip()
        if not key:
            raise serializers.ValidationError("请输入设置键名")
        return key
