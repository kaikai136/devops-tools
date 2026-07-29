from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_staff
from operations.responses import bad_request, get_object_or_error
from system_management.services import ensure_builtin_admin, is_builtin_admin_user

from .common import user_payload


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
    user, error = get_object_or_error(User, id=user_id, error_message="用户不存在")
    if error:
        return error

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
