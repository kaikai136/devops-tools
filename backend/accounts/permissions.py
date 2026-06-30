from rest_framework import status
from rest_framework.response import Response


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


def has_feature_permission(user, feature_key: str, action_key: str | None = None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions

    ensure_feature_permissions()
    page_code = FEATURE_PERMISSION_CODE_BY_KEY.get(feature_key)
    if not page_code or not user.has_perm(f"system_management.{page_code}"):
        return False

    if not action_key:
        return True

    action_code = PAGE_ACTION_PERMISSION_CODE_BY_KEY.get((feature_key, action_key))
    return bool(action_code and user.has_perm(f"system_management.{action_code}"))


def require_feature_permission(request, feature_key: str, action_key: str | None = None, error_message: str = "没有操作权限"):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    if has_feature_permission(request.user, feature_key, action_key):
        return None
    return Response({"error": error_message}, status=status.HTTP_403_FORBIDDEN)
