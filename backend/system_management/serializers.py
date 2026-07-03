import re
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from .models import LoginLog, OperationLog, SystemSetting

SITE_IDENTITY_SETTING_KEY = "site_identity"
DASHBOARD_HERO_SETTING_KEY = "dashboard_hero"
LAYOUT_FOOTER_SETTING_KEY = "layout_footer"
LOGIN_CONTENT_SETTING_KEY = "login_content"
WATERMARK_SETTING_KEY = "watermark"
DISPLAY_SETTING_KEYS = {
    SITE_IDENTITY_SETTING_KEY,
    DASHBOARD_HERO_SETTING_KEY,
    LAYOUT_FOOTER_SETTING_KEY,
    LOGIN_CONTENT_SETTING_KEY,
    WATERMARK_SETTING_KEY,
}
PUBLIC_DISPLAY_SETTING_KEYS = {
    SITE_IDENTITY_SETTING_KEY,
    LOGIN_CONTENT_SETTING_KEY,
}
DEFAULT_SITE_IDENTITY = {
    "appName": "运维船长",
    "appShortName": "CAPTAIN",
    "appSubtitle": "Secure Console",
    "browserTitle": "运维船长",
    "logoText": "CAPTAIN",
    "logoImageUrl": "/captain-banner.png",
    "iconUrl": "/ops-captain-icon.png",
    "totpIssuer": "运维船长",
}
DEFAULT_DASHBOARD_HERO = {
    "badgeTemplate": "{appShortName} OPS",
    "line1Template": "{greeting}，{displayName}",
    "line2Template": "一路向前，莫问前程！！！",
    "descriptionTemplate": "这里汇总系统账号、资产与网络出口状态，帮助你快速判断今天的运维态势。",
    "font": "Fira Code",
    "fontSize": 24,
    "fontWeight": 900,
    "letterSpacing": "normal",
    "durationMs": 5000,
    "pauseMs": 1000,
    "color": "#9B5CFF",
    "backgroundColor": "#00000000",
    "centered": False,
    "verticalCentered": True,
    "multiline": False,
    "repeat": True,
    "random": False,
    "width": 620,
    "height": 64,
}
DEFAULT_LAYOUT_FOOTER = {
    "enabled": True,
    "textTemplate": "© Copyright {year} {appName} All rights reserved.",
    "linkText": "",
    "linkUrl": "",
    "fontSize": 12,
    "color": "#0B5CFF",
}
DEFAULT_LOGIN_CONTENT = {
    "badgeTemplate": "{appName} · {appSubtitle}",
    "title": "欢迎回来",
    "description": "登录管理平台，继续处理网络、主机和系统管理任务。",
    "copyrightTemplate": "© {year} {appName} Team",
}
DEFAULT_WATERMARK_TEXT = "{username}"
FONT_WEIGHT_CHOICES = {400, 500, 600, 700, 800, 900}
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
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
    "operationLogs",
    "users",
    "roles",
    "profile",
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


class OperationLogSerializer(serializers.ModelSerializer):
    userDisplay = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    ipAddress = serializers.IPAddressField(source="ip_address", read_only=True)
    userAgent = serializers.CharField(source="user_agent", read_only=True)

    class Meta:
        model = OperationLog
        fields = ["id", "user", "userDisplay", "username", "module", "action", "target", "detail", "ipAddress", "userAgent", "createdAt"]

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
        if key == SITE_IDENTITY_SETTING_KEY:
            attrs["value"] = validate_site_identity_value(value)
        elif key == DASHBOARD_HERO_SETTING_KEY:
            attrs["value"] = validate_dashboard_hero_value(value)
        elif key == LAYOUT_FOOTER_SETTING_KEY:
            attrs["value"] = validate_layout_footer_value(value)
        elif key == LOGIN_CONTENT_SETTING_KEY:
            attrs["value"] = validate_login_content_value(value)
        elif key == WATERMARK_SETTING_KEY:
            attrs["value"] = validate_watermark_value(value)
        return attrs


def _require_setting_object(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise serializers.ValidationError({"value": f"{label}配置格式无效"})
    return value


def _clean_text(value, fallback: str, max_length: int = 160) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return fallback
    return text[:max_length]


def _clean_optional_text(value, max_length: int = 160) -> str:
    return str(value if value is not None else "").strip()[:max_length]


def _clean_url(value, fallback: str = "", *, allow_blank: bool = False) -> str:
    url = str(value if value is not None else "").strip()
    if not url:
        if allow_blank:
            return ""
        return fallback
    if url.startswith("/") and not url.startswith("//"):
        return url[:500]
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url[:500]
    raise serializers.ValidationError({"value": "URL 仅支持相对路径或 http/https 地址"})


def _clean_color(value, fallback: str) -> str:
    color = str(value if value is not None else "").strip()
    if not color:
        return fallback
    if not HEX_COLOR_RE.fullmatch(color):
        raise serializers.ValidationError({"value": "颜色值必须是 #RRGGBB 格式"})
    return color.upper()


def _clean_svg_color(value, fallback: str, *, allow_alpha: bool = False) -> str:
    color = str(value if value is not None else "").strip()
    if not color:
        return fallback
    pattern = r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$" if allow_alpha else r"^#[0-9A-Fa-f]{6}$"
    if not re.fullmatch(pattern, color):
        raise serializers.ValidationError({"value": "SVG 颜色值必须是 #RRGGBB 或 #RRGGBBAA 格式"})
    return color.upper()


def _clean_letter_spacing(value, fallback: str) -> str:
    spacing = str(value if value is not None else "").strip() or fallback
    if not re.fullmatch(r"[A-Za-z0-9 ._%+-]{1,40}", spacing):
        raise serializers.ValidationError({"value": "字间距格式无效"})
    return spacing


def _clean_int(value, fallback: int, *, minimum: int, maximum: int, field_label: str) -> int:
    if value is None or value == "":
        return fallback
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError({"value": f"{field_label}必须是数字"})
    if number < minimum or number > maximum:
        raise serializers.ValidationError({"value": f"{field_label}必须在 {minimum}-{maximum} 之间"})
    return number


def _clean_font_weight(value, fallback: int) -> int:
    weight = _clean_int(value, fallback, minimum=400, maximum=900, field_label="字重")
    if weight not in FONT_WEIGHT_CHOICES:
        raise serializers.ValidationError({"value": "字重仅支持 400/500/600/700/800/900"})
    return weight


def validate_site_identity_value(value):
    raw = _require_setting_object(value, "品牌变量")
    defaults = DEFAULT_SITE_IDENTITY
    return {
        "appName": _clean_text(raw.get("appName"), defaults["appName"], 80),
        "appShortName": _clean_text(raw.get("appShortName"), defaults["appShortName"], 32),
        "appSubtitle": _clean_text(raw.get("appSubtitle"), defaults["appSubtitle"], 80),
        "browserTitle": _clean_text(raw.get("browserTitle"), defaults["browserTitle"], 80),
        "logoText": _clean_text(raw.get("logoText"), defaults["logoText"], 32),
        "logoImageUrl": _clean_url(raw.get("logoImageUrl"), defaults["logoImageUrl"]),
        "iconUrl": _clean_url(raw.get("iconUrl"), defaults["iconUrl"]),
        "totpIssuer": _clean_text(raw.get("totpIssuer"), defaults["totpIssuer"], 80),
    }


def validate_dashboard_hero_value(value):
    raw = _require_setting_object(value, "仪表盘动态文字")
    defaults = DEFAULT_DASHBOARD_HERO
    return {
        "badgeTemplate": _clean_text(raw.get("badgeTemplate"), defaults["badgeTemplate"], 160),
        "line1Template": _clean_text(raw.get("line1Template"), defaults["line1Template"], 160),
        "line2Template": _clean_text(raw.get("line2Template"), defaults["line2Template"], 160),
        "descriptionTemplate": _clean_text(raw.get("descriptionTemplate"), defaults["descriptionTemplate"], 260),
        "font": _clean_text(raw.get("font"), defaults["font"], 80),
        "fontSize": _clean_int(raw.get("fontSize"), defaults["fontSize"], minimum=16, maximum=36, field_label="动态文字字号"),
        "fontWeight": _clean_font_weight(raw.get("fontWeight"), defaults["fontWeight"]),
        "letterSpacing": _clean_letter_spacing(raw.get("letterSpacing"), defaults["letterSpacing"]),
        "durationMs": _clean_int(raw.get("durationMs"), defaults["durationMs"], minimum=100, maximum=30000, field_label="每行持续时间"),
        "pauseMs": _clean_int(raw.get("pauseMs"), defaults["pauseMs"], minimum=0, maximum=10000, field_label="停顿时间"),
        "color": _clean_svg_color(raw.get("color"), defaults["color"]),
        "backgroundColor": _clean_svg_color(raw.get("backgroundColor"), defaults["backgroundColor"], allow_alpha=True),
        "centered": bool(raw.get("centered", defaults["centered"])),
        "verticalCentered": bool(raw.get("verticalCentered", defaults["verticalCentered"])),
        "multiline": bool(raw.get("multiline", defaults["multiline"])),
        "repeat": bool(raw.get("repeat", defaults["repeat"])),
        "random": bool(raw.get("random", defaults["random"])),
        "width": _clean_int(raw.get("width"), defaults["width"], minimum=160, maximum=1600, field_label="SVG 宽度"),
        "height": _clean_int(raw.get("height"), defaults["height"], minimum=30, maximum=420, field_label="SVG 高度"),
    }


def validate_layout_footer_value(value):
    raw = _require_setting_object(value, "页脚")
    defaults = DEFAULT_LAYOUT_FOOTER
    return {
        "enabled": bool(raw.get("enabled", defaults["enabled"])),
        "textTemplate": _clean_text(raw.get("textTemplate"), defaults["textTemplate"], 220),
        "linkText": _clean_optional_text(raw.get("linkText"), 80),
        "linkUrl": _clean_url(raw.get("linkUrl"), "", allow_blank=True),
        "fontSize": _clean_int(raw.get("fontSize"), defaults["fontSize"], minimum=10, maximum=18, field_label="页脚字号"),
        "color": _clean_color(raw.get("color"), defaults["color"]),
    }


def validate_login_content_value(value):
    raw = _require_setting_object(value, "登录页文案")
    defaults = DEFAULT_LOGIN_CONTENT
    return {
        "badgeTemplate": _clean_text(raw.get("badgeTemplate"), defaults["badgeTemplate"], 160),
        "title": _clean_text(raw.get("title"), defaults["title"], 80),
        "description": _clean_text(raw.get("description"), defaults["description"], 260),
        "copyrightTemplate": _clean_text(raw.get("copyrightTemplate"), defaults["copyrightTemplate"], 160),
    }


def validate_watermark_value(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError({"value": "水印配置格式无效"})

    enabled = bool(value.get("enabled", False))
    text = str(value.get("text", DEFAULT_WATERMARK_TEXT)).strip() or DEFAULT_WATERMARK_TEXT
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
