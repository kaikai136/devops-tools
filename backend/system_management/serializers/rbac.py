import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from ..services import (
    FEATURE_PERMISSION_CODE_BY_KEY,
    FEATURE_PERMISSION_CODES,
    PAGE_ACTION_PERMISSION_CODES,
    PAGE_ACTION_PERMISSION_META_BY_CODE,
    is_builtin_admin_user,
)


class SystemUserSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", required=False, allow_blank=True)
    isActive = serializers.BooleanField(source="is_active", required=False)
    isStaff = serializers.BooleanField(source="is_staff", required=False)
    isSuperuser = serializers.BooleanField(source="is_superuser", read_only=True)
    isBuiltinAdmin = serializers.SerializerMethodField()
    canLogin = serializers.SerializerMethodField()
    twoFactorEnabled = serializers.SerializerMethodField()
    twoFactorRequired = serializers.SerializerMethodField()
    twoFactorResetRequired = serializers.SerializerMethodField()
    twoFactorStatus = serializers.SerializerMethodField()
    sessionAuditEnabled = serializers.SerializerMethodField()
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
            "twoFactorEnabled",
            "twoFactorRequired",
            "twoFactorResetRequired",
            "twoFactorStatus",
            "sessionAuditEnabled",
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

    def get_twoFactorEnabled(self, obj):
        profile = self._profile(obj)
        return bool(profile and profile.totp_enabled)

    def get_twoFactorRequired(self, obj):
        profile = self._profile(obj)
        return bool(profile and profile.totp_required)

    def get_twoFactorResetRequired(self, obj):
        profile = self._profile(obj)
        return bool(profile and profile.totp_reset_required)

    def get_twoFactorStatus(self, obj):
        profile = self._profile(obj)
        return profile.two_factor_status if profile else "disabled"

    def get_sessionAuditEnabled(self, obj):
        profile = self._profile(obj)
        return True if profile is None else bool(profile.session_audit_enabled)

    def _profile(self, obj):
        try:
            return obj.profile
        except obj._meta.model.profile.RelatedObjectDoesNotExist:
            return None

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
    userCount = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "permissionIds", "userCount"]

    def get_userCount(self, obj):
        return getattr(obj, "user_count", obj.user_set.count())

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


class RoleOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]
