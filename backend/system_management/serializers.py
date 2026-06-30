import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from .models import LoginLog, SystemSetting

WATERMARK_SETTING_KEY = "watermark"
WATERMARK_ALLOWED_PAGES = {
    "dashboard",
    "ip",
    "ports",
    "subnet",
    "hosts",
    "accounts",
    "auth",
    "password",
    "loginLogs",
    "users",
    "roles",
    "systemSettings",
    "webTerminal",
}
from .services import (
    FEATURE_PERMISSION_CODE_BY_KEY,
    FEATURE_PERMISSION_CODES,
    PAGE_ACTION_PERMISSION_CODES,
    PAGE_ACTION_PERMISSION_META_BY_CODE,
    is_builtin_admin_user,
)


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
    isBuiltinAdmin = serializers.SerializerMethodField()
    canLogin = serializers.SerializerMethodField()
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
            "isBuiltinAdmin",
            "canLogin",
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

    def validate_password(self, value):
        password = str(value)
        if not password:
            return ""
        if len(password) < 8:
            raise serializers.ValidationError("密码至少需要 8 位")
        if not re.search(r"[a-z]", password):
            raise serializers.ValidationError("密码必须包含小写字母")
        if not re.search(r"[A-Z]", password):
            raise serializers.ValidationError("密码必须包含大写字母")
        if not re.search(r"\d", password):
            raise serializers.ValidationError("密码必须包含数字")
        return password

    def get_isBuiltinAdmin(self, obj):
        return is_builtin_admin_user(obj)

    def get_canLogin(self, obj):
        return bool(obj.is_active and obj.has_usable_password())

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

        if is_builtin_admin_user(instance):
            validated_data = {}
            groups = None
            password = ""

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
    featureKey = serializers.SerializerMethodField()
    actionKey = serializers.SerializerMethodField()
    permissionType = serializers.SerializerMethodField()
    isFeature = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ["id", "codename", "label", "featureKey", "actionKey", "permissionType", "isFeature"]

    def get_featureKey(self, obj):
        for feature_key, codename in FEATURE_PERMISSION_CODE_BY_KEY.items():
            if obj.codename == codename:
                return feature_key
        action_meta = PAGE_ACTION_PERMISSION_META_BY_CODE.get(obj.codename)
        if action_meta:
            return action_meta["feature_key"]
        return ""

    def get_actionKey(self, obj):
        action_meta = PAGE_ACTION_PERMISSION_META_BY_CODE.get(obj.codename)
        return action_meta["action_key"] if action_meta else ""

    def get_permissionType(self, obj):
        if obj.codename in FEATURE_PERMISSION_CODES:
            return "page"
        if obj.codename in PAGE_ACTION_PERMISSION_CODES:
            return "action"
        return "other"

    def get_isFeature(self, obj):
        return obj.codename in FEATURE_PERMISSION_CODES or obj.codename in PAGE_ACTION_PERMISSION_CODES


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

    def validate(self, attrs):
        key = attrs.get("key", getattr(self.instance, "key", ""))
        value = attrs.get("value", getattr(self.instance, "value", {}))
        if key == WATERMARK_SETTING_KEY:
            attrs["value"] = validate_watermark_value(value)
        return attrs


def validate_watermark_value(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError({"value": "水印配置格式无效"})

    enabled = bool(value.get("enabled", False))
    text = str(value.get("text", "")).strip()
    raw_pages = value.get("pages", [])
    if not isinstance(raw_pages, list):
        raise serializers.ValidationError({"value": "水印应用页面格式无效"})

    pages = []
    invalid_pages = []
    for page in raw_pages:
        page_key = str(page).strip()
        if not page_key:
            continue
        if page_key not in WATERMARK_ALLOWED_PAGES:
            invalid_pages.append(page_key)
            continue
        if page_key not in pages:
            pages.append(page_key)

    if invalid_pages:
        raise serializers.ValidationError({"value": f"水印应用页面无效：{invalid_pages[0]}"})
    if enabled and not text:
        raise serializers.ValidationError({"value": "开启水印时请输入水印文本"})

    return {"enabled": enabled, "text": text, "pages": pages}
