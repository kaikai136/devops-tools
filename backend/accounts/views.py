import secrets
import time

from django.contrib.auth import authenticate, get_user_model, login, logout
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_login, require_staff
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


def user_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "featurePermissionCodes": user_feature_permission_codes(user),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


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

    user = authenticate(request, username=username, password=password)
    if user is None:
        record_login_log(request, username, LoginLog.STATUS_FAILED, "账号或密码错误")
        return Response({"error": "账号或密码错误"}, status=status.HTTP_400_BAD_REQUEST)
    if not user.is_active:
        record_login_log(request, username, LoginLog.STATUS_FAILED, "账号已停用", user)
        return Response({"error": "账号已被停用"}, status=status.HTTP_403_FORBIDDEN)

    login(request, user)
    request.session.set_expiry(60 * 60 * 24 * 14 if remember else 0)
    record_login_log(request, username, LoginLog.STATUS_SUCCESS, "登录成功", user)
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
    return Response({"user": user_payload(request.user)})


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
