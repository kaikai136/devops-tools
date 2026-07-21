from __future__ import annotations

from dataclasses import dataclass

import pyotp
from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from accounts.permissions import has_feature_permission


class GatewayAuthError(Exception):
    pass


@dataclass(frozen=True)
class ParsedGatewayUsername:
    username: str
    host_id: int | None = None

    @property
    def direct_mode(self) -> bool:
        return self.host_id is not None


def parse_gateway_username(value: str) -> ParsedGatewayUsername:
    raw = str(value or "").strip()
    if not raw:
        raise GatewayAuthError("SSH 用户名不能为空")
    if "#" not in raw:
        return ParsedGatewayUsername(username=raw)

    username, host_token = raw.rsplit("#", 1)
    username = username.strip()
    if not username:
        raise GatewayAuthError("SSH 用户名不能为空")
    try:
        host_id = int(host_token)
    except (TypeError, ValueError):
        raise GatewayAuthError("直连主机 ID 无效")
    if host_id <= 0:
        raise GatewayAuthError("直连主机 ID 无效")
    return ParsedGatewayUsername(username=username, host_id=host_id)


def authenticate_platform_user(username: str, password: str, totp_code: str = ""):
    user = authenticate_platform_user_password(username, password)
    validate_platform_user_totp(user, totp_code)
    return user


def authenticate_platform_user_password(username: str, password: str):
    parsed = parse_gateway_username(username)
    User = get_user_model()
    try:
        user = User.objects.get(username=parsed.username)
    except User.DoesNotExist:
        raise GatewayAuthError("用户名或密码错误")

    if not user.check_password(password or ""):
        raise GatewayAuthError("用户名或密码错误")
    if not user.is_active:
        raise GatewayAuthError("账号已禁用")
    if not has_feature_permission(user, "hosts", "terminal"):
        raise GatewayAuthError("没有 SSH 网关权限")

    profile = user_profile(user)
    if profile and (profile.totp_required or profile.totp_reset_required):
        raise GatewayAuthError("请先在 Web 端完成双因素认证设置")
    return user


def validate_platform_user_totp(user, totp_code: str):
    profile = user_profile(user)
    if profile and profile.totp_enabled and not verify_totp(profile.totp_secret, totp_code):
        raise GatewayAuthError("验证码错误")
    return user


def user_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return None


def user_requires_totp(username: str) -> bool:
    parsed = parse_gateway_username(username)
    User = get_user_model()
    try:
        user = User.objects.get(username=parsed.username)
    except User.DoesNotExist:
        return False
    profile = user_profile(user)
    return user_has_totp_enabled(user)


def user_has_totp_enabled(user) -> bool:
    profile = user_profile(user)
    return bool(profile and profile.totp_enabled)


def verify_totp(secret: str, code: str) -> bool:
    token = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(token) != 6 or not secret:
        return False
    return pyotp.TOTP(secret).verify(token, valid_window=1)
