import base64
import io
import re
import secrets
import time

import pyotp
import qrcode
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.permissions import require_feature_permission, require_login, require_staff
from accounts.session_lock import is_session_locked, lock_session, unlock_session
from operations.responses import bad_request
from system_management.models import LoginLog
from system_management.services import ensure_builtin_admin, is_builtin_admin_user, record_login_log, user_feature_permission_codes

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
TWO_FACTOR_ISSUER = "运维船长"
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
    uri = pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=TWO_FACTOR_ISSUER)
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


@api_view(["GET"])
def slider_challenge(request):
    now = _now()
    challenges, _ = _cleanup_slider_state(request, now)
    challenge_id = secrets.token_urlsafe(18)
    target_x = SLIDER_TARGET_MIN_X + secrets.randbelow(SLIDER_TARGET_MAX_X - SLIDER_TARGET_MIN_X + 1)
    challenges[challenge_id] = {
        "targetX": target_x,
        "trackWidth": SLIDER_TRACK_WIDTH,
        "tolerance": SLIDER_TOLERANCE,
        "expiresAt": now + SLIDER_CHALLENGE_TTL_SECONDS,
    }
    if len(challenges) > SLIDER_MAX_CHALLENGES:
        challenges = dict(sorted(challenges.items(), key=lambda item: float(item[1].get("expiresAt", 0)))[-SLIDER_MAX_CHALLENGES:])

    request.session[SLIDER_CHALLENGE_SESSION_KEY] = challenges
    request.session.modified = True
    return Response(
        {
            "challengeId": challenge_id,
            "targetX": target_x,
            "trackWidth": SLIDER_TRACK_WIDTH,
            "tolerance": SLIDER_TOLERANCE,
            "expiresIn": SLIDER_CHALLENGE_TTL_SECONDS,
        }
    )


@api_view(["POST"])
def slider_verify(request):
    challenge_id = str(request.data.get("challengeId", ""))
    try:
        offset_x = float(request.data.get("offsetX"))
        elapsed_ms = int(request.data.get("elapsedMs", 0))
    except (TypeError, ValueError):
        return bad_request("滑块验证参数无效")

    challenges, tokens = _cleanup_slider_state(request)
    challenge = challenges.get(challenge_id)
    if not challenge:
        return bad_request("滑块验证已过期，请重试")
    if elapsed_ms < SLIDER_MIN_ELAPSED_MS:
        return bad_request("滑动过快，请重试")

    target_x = float(challenge.get("targetX", 0))
    tolerance = float(challenge.get("tolerance", SLIDER_TOLERANCE))
    if abs(offset_x - target_x) > tolerance:
        return bad_request("滑块位置不正确，请重试")

    slider_token = secrets.token_urlsafe(24)
    tokens[slider_token] = {"expiresAt": _now() + SLIDER_TOKEN_TTL_SECONDS}
    challenges.pop(challenge_id, None)
    request.session[SLIDER_CHALLENGE_SESSION_KEY] = challenges
    request.session[SLIDER_TOKEN_SESSION_KEY] = tokens
    request.session.modified = True
    return Response({"verified": True, "sliderToken": slider_token})


@api_view(["POST"])
def auth_login(request):
    ensure_builtin_admin()
    username = str(request.data.get("account", request.data.get("username", ""))).strip()
    password = str(request.data.get("password", ""))
    remember = bool(request.data.get("remember", False))
    slider_token = str(request.data.get("sliderToken", ""))

    if not username or not password:
        return bad_request("请输入账号和密码")
    slider_error = _consume_slider_token(request, slider_token)
    if slider_error:
        return bad_request(slider_error)

    matched_user = _get_user_with_matching_password(username, password)
    if matched_user is not None and not matched_user.is_active:
        record_login_log(request, username, LoginLog.STATUS_FAILED, "账号已停用", matched_user)
        return Response({"error": DISABLED_LOGIN_ERROR}, status=status.HTTP_403_FORBIDDEN)

    user = authenticate(request, username=username, password=password)
    if user is None:
        record_login_log(request, username, LoginLog.STATUS_FAILED, "账号或密码错误")
        return Response({"error": "账号或密码错误"}, status=status.HTTP_400_BAD_REQUEST)
    if not user.is_active:
        record_login_log(request, username, LoginLog.STATUS_FAILED, "账号已停用", user)
        return Response({"error": DISABLED_LOGIN_ERROR}, status=status.HTTP_403_FORBIDDEN)

    profile = get_user_profile(user)
    if profile.totp_required or profile.totp_reset_required:
        secret = pyotp.random_base32()
        profile.totp_pending_secret = secret
        profile.save(update_fields=["totp_pending_secret", "updated_at"])
        _set_pending_2fa_setup(request, user, remember, secret)
        return Response(
            {
                "twoFactorSetupRequired": True,
                "challengeId": secrets.token_urlsafe(18),
                "account": user.username,
                "displayName": user.first_name or user.username,
                "expiresIn": TWO_FACTOR_PENDING_TTL_SECONDS,
                **_two_factor_setup_payload(user, secret),
            }
        )

    if profile.totp_enabled:
        _set_pending_2fa_login(request, user, remember)
        return Response(
            {
                "twoFactorRequired": True,
                "challengeId": secrets.token_urlsafe(18),
                "account": user.username,
                "displayName": user.first_name or user.username,
                "expiresIn": TWO_FACTOR_PENDING_TTL_SECONDS,
            }
        )

    login(request, user)
    unlock_session(request)
    request.session.set_expiry(60 * 60 * 24 * 14 if remember else 0)
    record_login_log(request, username, LoginLog.STATUS_SUCCESS, "登录成功", user)
    return Response({"user": user_payload(user)})


@api_view(["POST"])
def auth_login_2fa_setup(request):
    pending = _pending_2fa_setup(request)
    if not pending:
        return Response({"error": "双因素绑定已过期，请重新登录"}, status=status.HTTP_400_BAD_REQUEST)

    User = get_user_model()
    try:
        user = User.objects.get(id=pending.get("userId"))
    except User.DoesNotExist:
        _pop_pending_2fa_setup(request)
        return Response({"error": "登录用户不存在，请重新登录"}, status=status.HTTP_400_BAD_REQUEST)

    if not user.is_active:
        _pop_pending_2fa_setup(request)
        record_login_log(request, pending.get("username", user.username), LoginLog.STATUS_FAILED, "账号已停用", user)
        return Response({"error": DISABLED_LOGIN_ERROR}, status=status.HTTP_403_FORBIDDEN)

    secret = str(pending.get("secret", ""))
    profile = get_user_profile(user)
    if not secret or secret != profile.totp_pending_secret:
        _pop_pending_2fa_setup(request)
        return Response({"error": "双因素绑定状态无效，请重新登录"}, status=status.HTTP_400_BAD_REQUEST)
    if not _verify_totp(secret, str(request.data.get("code", ""))):
        return Response({"error": "验证码错误，请确认设备时间是否准确"}, status=status.HTTP_400_BAD_REQUEST)

    _pop_pending_2fa_setup(request)
    profile.totp_secret = secret
    profile.totp_pending_secret = ""
    profile.totp_enabled = True
    profile.totp_required = False
    profile.totp_reset_required = False
    profile.totp_confirmed_at = timezone.now()
    profile.save(
        update_fields=[
            "totp_secret",
            "totp_pending_secret",
            "totp_enabled",
            "totp_required",
            "totp_reset_required",
            "totp_confirmed_at",
            "updated_at",
        ]
    )
    login(request, user)
    unlock_session(request)
    request.session.set_expiry(60 * 60 * 24 * 14 if bool(pending.get("remember")) else 0)
    record_login_log(request, user.username, LoginLog.STATUS_SUCCESS, "登录成功", user)
    return Response({"user": user_payload(user)})


@api_view(["POST"])
def auth_login_2fa(request):
    pending = _pop_pending_2fa_login(request)
    if not pending:
        return Response({"error": "二次验证已过期，请重新登录"}, status=status.HTTP_400_BAD_REQUEST)

    User = get_user_model()
    try:
        user = User.objects.get(id=pending.get("userId"))
    except User.DoesNotExist:
        return Response({"error": "登录用户不存在，请重新登录"}, status=status.HTTP_400_BAD_REQUEST)

    if not user.is_active:
        record_login_log(request, pending.get("username", user.username), LoginLog.STATUS_FAILED, "账号已停用", user)
        return Response({"error": DISABLED_LOGIN_ERROR}, status=status.HTTP_403_FORBIDDEN)

    profile = get_user_profile(user)
    if not profile.totp_enabled or not _verify_totp(profile.totp_secret, str(request.data.get("code", ""))):
        record_login_log(request, pending.get("username", user.username), LoginLog.STATUS_FAILED, "双因素验证码错误", user)
        return Response({"error": "验证码错误，请重新登录后再试"}, status=status.HTTP_400_BAD_REQUEST)

    login(request, user)
    unlock_session(request)
    request.session.set_expiry(60 * 60 * 24 * 14 if bool(pending.get("remember")) else 0)
    record_login_log(request, user.username, LoginLog.STATUS_SUCCESS, "登录成功", user)
    return Response({"user": user_payload(user)})


@api_view(["POST"])
def auth_logout(request):
    logout(request)
    return Response({"ok": True})


@api_view(["GET"])
def auth_me(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    return Response({"user": user_payload(request.user), "locked": is_session_locked(request)})


@api_view(["POST"])
def auth_lock(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    lock_session(request)
    return Response({"locked": True})


@api_view(["POST"])
def auth_unlock(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    if not request.user.is_active:
        return Response({"error": DISABLED_LOGIN_ERROR}, status=status.HTTP_403_FORBIDDEN)
    password = str(request.data.get("password", ""))
    if not password or not request.user.check_password(password):
        return bad_request("锁屏密码不正确")
    unlock_session(request)
    return Response({"locked": False, "user": user_payload(request.user)})


@api_view(["GET", "PUT"])
def profile(request):
    auth_error = require_profile_permission(request, "edit" if request.method == "PUT" else None)
    if auth_error:
        return auth_error

    user = request.user
    if request.method == "GET":
        return Response(_profile_payload(user))

    username = str(request.data.get("username", user.username)).strip()
    first_name = str(request.data.get("first_name", request.data.get("displayName", user.first_name))).strip()
    email = str(request.data.get("email", user.email)).strip()
    if not username:
        return bad_request("请输入用户名")

    User = get_user_model()
    if User.objects.exclude(id=user.id).filter(username=username).exists():
        return bad_request("用户名已存在")

    user.username = username
    user.first_name = first_name
    user.email = email
    try:
        user.save(update_fields=["username", "first_name", "email"])
    except IntegrityError:
        return bad_request("用户名已存在")
    return Response(_profile_payload(user))


@api_view(["POST"])
@parser_classes([MultiPartParser])
def profile_avatar(request):
    auth_error = require_profile_permission(request, "avatar")
    if auth_error:
        return auth_error

    avatar = request.FILES.get("avatar")
    if not avatar:
        return bad_request("请选择头像文件")
    if avatar.size > AVATAR_MAX_BYTES:
        return bad_request("头像大小不能超过 2MB")

    content_type = getattr(avatar, "content_type", "")
    suffix = AVATAR_ALLOWED_CONTENT_TYPES.get(content_type)
    if not suffix:
        return bad_request("头像仅支持 JPG、PNG 或 WebP 图片")

    profile = get_user_profile(request.user)
    if profile.avatar:
        profile.avatar.delete(save=False)
    content = ContentFile(avatar.read())
    profile.avatar.save(f"user_{request.user.id}.{suffix}", content, save=True)
    return Response(_profile_payload(request.user))


@api_view(["POST"])
def profile_password(request):
    auth_error = require_profile_permission(request, "password")
    if auth_error:
        return auth_error

    current_password = str(request.data.get("currentPassword", ""))
    new_password = str(request.data.get("newPassword", ""))
    confirm_password = str(request.data.get("confirmPassword", ""))
    if not request.user.check_password(current_password):
        return bad_request("当前密码不正确")
    if new_password != confirm_password:
        return bad_request("两次输入的新密码不一致")
    password_error = _validate_profile_password(new_password)
    if password_error:
        return bad_request(password_error)

    request.user.set_password(new_password)
    request.user.save(update_fields=["password"])
    update_session_auth_hash(request, request.user)
    return Response({"ok": True, "user": user_payload(request.user)})


@api_view(["POST"])
def profile_2fa_setup(request):
    auth_error = require_profile_permission(request, "2fa_enable")
    if auth_error:
        return auth_error

    profile = get_user_profile(request.user)
    if profile.totp_enabled:
        return bad_request("双因素认证已启用")

    secret = pyotp.random_base32()
    profile.totp_secret = secret
    profile.totp_pending_secret = ""
    profile.totp_confirmed_at = None
    profile.totp_required = False
    profile.totp_reset_required = False
    profile.save(update_fields=["totp_secret", "totp_pending_secret", "totp_confirmed_at", "totp_required", "totp_reset_required", "updated_at"])
    return Response(_two_factor_setup_payload(request.user, secret))


@api_view(["POST"])
def profile_2fa_confirm(request):
    auth_error = require_profile_permission(request, "2fa_enable")
    if auth_error:
        return auth_error

    profile = get_user_profile(request.user)
    if not profile.totp_secret:
        return bad_request("请先生成双因素认证密钥")
    if not _verify_totp(profile.totp_secret, str(request.data.get("code", ""))):
        return bad_request("验证码错误，请确认设备时间是否准确")

    profile.totp_enabled = True
    profile.totp_required = False
    profile.totp_reset_required = False
    profile.totp_pending_secret = ""
    profile.totp_confirmed_at = timezone.now()
    profile.save(update_fields=["totp_enabled", "totp_required", "totp_reset_required", "totp_pending_secret", "totp_confirmed_at", "updated_at"])
    return Response(_profile_payload(request.user))


@api_view(["POST"])
def profile_2fa_disable(request):
    auth_error = require_profile_permission(request, "2fa_disable")
    if auth_error:
        return auth_error

    profile = get_user_profile(request.user)
    if not profile.totp_enabled:
        return bad_request("双因素认证未启用")
    password = str(request.data.get("password", ""))
    if not request.user.check_password(password):
        return bad_request("当前密码不正确")
    if not _verify_totp(profile.totp_secret, str(request.data.get("code", ""))):
        return bad_request("验证码错误")

    profile.totp_enabled = False
    profile.totp_secret = ""
    profile.totp_pending_secret = ""
    profile.totp_required = False
    profile.totp_reset_required = False
    profile.totp_confirmed_at = None
    profile.save(update_fields=["totp_enabled", "totp_secret", "totp_pending_secret", "totp_required", "totp_reset_required", "totp_confirmed_at", "updated_at"])
    return Response(_profile_payload(request.user))


@api_view(["GET", "POST"])
def users(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    User = get_user_model()
    ensure_builtin_admin()
    if request.method == "GET":
        data = [user_payload(user) for user in User.objects.order_by("id")]
        return Response(data)

    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", "")).strip()
    if not username:
        return bad_request("请输入用户名")
    if not password:
        return bad_request("请输入初始密码")
    if User.objects.filter(username=username).exists():
        return bad_request("用户名已存在")

    user = User.objects.create_user(
        username=username,
        password=password,
        email=str(request.data.get("email", "")).strip(),
        first_name=str(request.data.get("first_name", "")).strip(),
        is_staff=bool(request.data.get("is_staff", False)),
        is_active=bool(request.data.get("is_active", True)),
    )
    return Response(user_payload(user), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def user_detail(request, user_id: int):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        if user.id == request.user.id:
            return bad_request("不能删除当前登录用户")
        if is_builtin_admin_user(user):
            return bad_request("内置管理员不允许删除")
        user.delete()
        return Response({"deleted": True})

    username = str(request.data.get("username", user.username)).strip()
    if not username:
        return bad_request("请输入用户名")
    if User.objects.exclude(id=user.id).filter(username=username).exists():
        return bad_request("用户名已存在")

    builtin_admin = is_builtin_admin_user(user)
    if not builtin_admin:
        user.username = username
        user.email = str(request.data.get("email", user.email)).strip()
        user.first_name = str(request.data.get("first_name", user.first_name)).strip()
        user.is_active = bool(request.data.get("is_active", user.is_active))
        user.is_staff = bool(request.data.get("is_staff", user.is_staff))
    password = str(request.data.get("password", "")).strip()
    if password and not builtin_admin:
        user.set_password(password)
    user.save()
    if builtin_admin:
        user = ensure_builtin_admin()
    return Response(user_payload(user))
