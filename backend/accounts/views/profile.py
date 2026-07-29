import pyotp
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from operations.responses import bad_request

from .common import (
    AVATAR_ALLOWED_CONTENT_TYPES,
    AVATAR_MAX_BYTES,
    _profile_payload,
    _two_factor_setup_payload,
    _validate_profile_password,
    _verify_totp,
    get_user_profile,
    require_profile_permission,
    user_payload,
)


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
