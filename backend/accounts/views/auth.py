import secrets

import pyotp
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_login
from accounts.session_lock import is_session_locked, lock_session, unlock_session
from operations.responses import bad_request
from system_management.models import LoginLog
from system_management.services import ensure_builtin_admin, record_login_log

from .common import (
    DISABLED_LOGIN_ERROR,
    SLIDER_CHALLENGE_SESSION_KEY,
    SLIDER_CHALLENGE_TTL_SECONDS,
    SLIDER_MAX_CHALLENGES,
    SLIDER_MIN_ELAPSED_MS,
    SLIDER_TARGET_MAX_X,
    SLIDER_TARGET_MIN_X,
    SLIDER_TOKEN_SESSION_KEY,
    SLIDER_TOKEN_TTL_SECONDS,
    SLIDER_TOLERANCE,
    SLIDER_TRACK_WIDTH,
    TWO_FACTOR_PENDING_TTL_SECONDS,
    _cleanup_slider_state,
    _consume_slider_token,
    _get_user_with_matching_password,
    _now,
    _pending_2fa_setup,
    _pop_pending_2fa_login,
    _pop_pending_2fa_setup,
    _set_pending_2fa_login,
    _set_pending_2fa_setup,
    _two_factor_setup_payload,
    _verify_totp,
    get_user_profile,
    user_payload,
)


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
