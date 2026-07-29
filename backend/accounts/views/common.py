import base64
import io
import re
import time

import pyotp
import qrcode
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.models import UserProfile
from accounts.permissions import require_feature_permission
from system_management.models import SystemSetting
from system_management.services import user_feature_permission_codes

SLIDER_CHALLENGE_SESSION_KEY = "auth_slider_challenges"
SLIDER_TOKEN_SESSION_KEY = "auth_slider_tokens"
SLIDER_CHALLENGE_TTL_SECONDS = 120
SLIDER_TOKEN_TTL_SECONDS = 60
SLIDER_TRACK_WIDTH = 320
SLIDER_TARGET_MIN_X = 54
SLIDER_TARGET_MAX_X = 266
SLIDER_TOLERANCE = 8
SLIDER_MIN_ELAPSED_MS = 250
SLIDER_MAX_CHALLENGES = 5
TWO_FACTOR_PENDING_SESSION_KEY = "auth_2fa_pending"
TWO_FACTOR_SETUP_PENDING_SESSION_KEY = "auth_2fa_setup_pending"
TWO_FACTOR_PENDING_TTL_SECONDS = 300
DEFAULT_TWO_FACTOR_ISSUER = "运维船长"
SITE_IDENTITY_SETTING_KEY = "site_identity"
AVATAR_ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024
PROFILE_PERMISSION_MESSAGE = "没有个人中心操作权限"
DISABLED_LOGIN_ERROR = "用户已被禁用，请联系管理员解封"


def require_profile_permission(request, action_key: str | None = None):
    return require_feature_permission(request, "profile", action_key, PROFILE_PERMISSION_MESSAGE)


def user_payload(user) -> dict:
    profile = get_user_profile(user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "displayName": user.first_name or user.username,
        "avatarUrl": avatar_url(profile),
        "twoFactorEnabled": profile.totp_enabled,
        "twoFactorRequired": profile.totp_required,
        "twoFactorResetRequired": profile.totp_reset_required,
        "twoFactorStatus": profile.two_factor_status,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "featurePermissionCodes": user_feature_permission_codes(user),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


def get_user_profile(user) -> UserProfile:
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def avatar_url(profile: UserProfile) -> str:
    if not profile.avatar:
        return ""
    return profile.avatar.url


def two_factor_issuer() -> str:
    try:
        value = SystemSetting.objects.filter(key=SITE_IDENTITY_SETTING_KEY).values_list("value", flat=True).first()
    except Exception:
        return DEFAULT_TWO_FACTOR_ISSUER
    if not isinstance(value, dict):
        return DEFAULT_TWO_FACTOR_ISSUER
    issuer = str(value.get("totpIssuer", "")).strip()
    return issuer or DEFAULT_TWO_FACTOR_ISSUER


def _now() -> float:
    return time.time()


def _session_dict(request, key: str) -> dict:
    value = request.session.get(key)
    return value if isinstance(value, dict) else {}


def _cleanup_slider_state(request, now: float | None = None) -> tuple[dict, dict]:
    current_time = _now() if now is None else now
    challenges = {
        key: value
        for key, value in _session_dict(request, SLIDER_CHALLENGE_SESSION_KEY).items()
        if isinstance(value, dict) and float(value.get("expiresAt", 0)) > current_time
    }
    tokens = {
        key: value
        for key, value in _session_dict(request, SLIDER_TOKEN_SESSION_KEY).items()
        if isinstance(value, dict) and float(value.get("expiresAt", 0)) > current_time
    }
    request.session[SLIDER_CHALLENGE_SESSION_KEY] = challenges
    request.session[SLIDER_TOKEN_SESSION_KEY] = tokens
    request.session.modified = True
    return challenges, tokens


def _consume_slider_token(request, slider_token: str) -> str | None:
    if not slider_token:
        return "请先完成滑块验证"

    _, tokens = _cleanup_slider_state(request)
    token_state = tokens.pop(slider_token, None)
    request.session[SLIDER_TOKEN_SESSION_KEY] = tokens
    request.session.modified = True
    if not token_state:
        return "滑块验证已失效，请重新验证"
    return None


def _get_user_with_matching_password(username: str, password: str):
    User = get_user_model()
    try:
        user = User._default_manager.get_by_natural_key(username)
    except User.DoesNotExist:
        return None
    return user if user.check_password(password) else None


def _set_pending_2fa_login(request, user, remember: bool) -> None:
    request.session[TWO_FACTOR_PENDING_SESSION_KEY] = {
        "userId": user.id,
        "username": user.username,
        "remember": remember,
        "expiresAt": _now() + TWO_FACTOR_PENDING_TTL_SECONDS,
    }
    request.session.modified = True


def _set_pending_2fa_setup(request, user, remember: bool, secret: str) -> None:
    request.session[TWO_FACTOR_SETUP_PENDING_SESSION_KEY] = {
        "userId": user.id,
        "username": user.username,
        "remember": remember,
        "secret": secret,
        "expiresAt": _now() + TWO_FACTOR_PENDING_TTL_SECONDS,
    }
    request.session.modified = True


def _pop_pending_2fa_login(request) -> dict | None:
    return _pop_pending_auth(request, TWO_FACTOR_PENDING_SESSION_KEY)


def _pop_pending_2fa_setup(request) -> dict | None:
    return _pop_pending_auth(request, TWO_FACTOR_SETUP_PENDING_SESSION_KEY)


def _pending_2fa_setup(request) -> dict | None:
    pending = request.session.get(TWO_FACTOR_SETUP_PENDING_SESSION_KEY)
    if not isinstance(pending, dict):
        return None
    if float(pending.get("expiresAt", 0)) <= _now():
        request.session.pop(TWO_FACTOR_SETUP_PENDING_SESSION_KEY, None)
        request.session.modified = True
        return None
    return pending


def _pop_pending_auth(request, key: str) -> dict | None:
    pending = request.session.get(key)
    request.session.pop(key, None)
    request.session.modified = True
    if not isinstance(pending, dict):
        return None
    if float(pending.get("expiresAt", 0)) <= _now():
        return None
    return pending


def _verify_totp(secret: str, code: str) -> bool:
    token = "".join(ch for ch in str(code) if ch.isdigit())
    if len(token) != 6 or not secret:
        return False
    return pyotp.TOTP(secret).verify(token, valid_window=1)


def _qr_data_url(uri: str) -> str:
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _two_factor_setup_payload(user, secret: str) -> dict:
    account_name = user.email or user.username
    uri = pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=two_factor_issuer())
    return {"secret": secret, "provisioningUri": uri, "qrDataUrl": _qr_data_url(uri)}


def _error_text(error: ValidationError) -> str:
    messages = getattr(error, "messages", None)
    if messages:
        return str(messages[0])
    return str(error)


def _validate_profile_password(password: str) -> str | None:
    if len(password) < 8:
        return "密码至少需要 8 位"
    if not re.search(r"[a-z]", password):
        return "密码必须包含小写字母"
    if not re.search(r"[A-Z]", password):
        return "密码必须包含大写字母"
    if not re.search(r"\d", password):
        return "密码必须包含数字"
    try:
        validate_password(password)
    except ValidationError as error:
        return _error_text(error)
    return None


def _profile_payload(user) -> dict:
    profile = get_user_profile(user)
    return {
        "user": user_payload(user),
        "profile": {
            "avatarUrl": avatar_url(profile),
            "twoFactorEnabled": profile.totp_enabled,
            "twoFactorRequired": profile.totp_required,
            "twoFactorResetRequired": profile.totp_reset_required,
            "twoFactorStatus": profile.two_factor_status,
            "twoFactorConfirmedAt": profile.totp_confirmed_at.isoformat() if profile.totp_confirmed_at else None,
            "updatedAt": profile.updated_at.isoformat() if profile.updated_at else None,
        },
    }
