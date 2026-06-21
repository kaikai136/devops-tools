from django.contrib.auth import authenticate, get_user_model, login, logout
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request
from system_management.models import LoginLog
from system_management.services import ensure_builtin_admin, is_builtin_admin_user, record_login_log


def user_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


def require_login(request):
    if not request.user.is_authenticated:
        return Response({"error": "请先登录"}, status=status.HTTP_401_UNAUTHORIZED)
    return None


def require_staff(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    if not request.user.is_staff:
        return Response({"error": "没有用户管理权限"}, status=status.HTTP_403_FORBIDDEN)
    return None


@api_view(["POST"])
def auth_login(request):
    ensure_builtin_admin()
    username = str(request.data.get("account", request.data.get("username", ""))).strip()
    password = str(request.data.get("password", ""))
    remember = bool(request.data.get("remember", False))

    if not username or not password:
        return bad_request("请输入账号和密码")

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
    if password:
        user.set_password(password)
    user.save()
    if builtin_admin:
        user = ensure_builtin_admin()
    return Response(user_payload(user))
