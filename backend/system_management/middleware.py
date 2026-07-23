from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import DatabaseError

from .services import record_operation_log


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_ACTION_BY_METHOD = {
    "POST": "新建",
    "PUT": "编辑",
    "PATCH": "更新",
    "DELETE": "删除",
}


@dataclass(frozen=True)
class AuditRule:
    prefix: str
    module: str
    actions: dict[str, str] | None = None


AUDIT_RULES = [
    AuditRule("/api/system/users/", "用户管理"),
    AuditRule("/api/system/roles/", "角色管理"),
    AuditRule("/api/system/settings/", "系统设置"),
    AuditRule("/api/profile/avatar/", "个人中心", {"POST": "上传头像"}),
    AuditRule("/api/profile/password/", "个人中心", {"POST": "修改密码"}),
    AuditRule("/api/profile/2fa/setup/", "个人中心", {"POST": "启用 2FA"}),
    AuditRule("/api/profile/2fa/confirm/", "个人中心", {"POST": "确认 2FA"}),
    AuditRule("/api/profile/2fa/disable/", "个人中心", {"POST": "关闭 2FA"}),
    AuditRule("/api/profile/", "个人中心", {"PUT": "编辑资料"}),
    AuditRule("/api/host-management/import/", "主机管理", {"POST": "导入恢复"}),
    AuditRule("/api/host-management/groups/", "主机分组"),
    AuditRule("/api/host-management/hosts/", "主机管理"),
    AuditRule("/api/host-management/accounts/", "账号管理"),
    AuditRule("/api/authenticators/", "双因子认证"),
    AuditRule("/api/passwords/generate/", "密码生成器", {"POST": "生成密码"}),
    AuditRule("/api/passwords/history/", "密码生成器", {"POST": "导入记录", "DELETE": "清空记录"}),
    AuditRule("/api/web-terminal/quick-commands/reorder/", "Web 终端", {"POST": "调整快捷命令排序"}),
    AuditRule("/api/web-terminal/quick-commands/", "Web 终端"),
    AuditRule("/api/web-terminal/hosts/", "Web 终端"),
    AuditRule("/api/security-scans/tasks/", "安全扫描", {"POST": "开始扫描", "DELETE": "删除任务"}),
    AuditRule("/api/bulk-execution/tasks/", "批量执行", {"POST": "创建任务", "DELETE": "删除任务"}),
]

EXCLUDED_PREFIXES = [
    "/api/auth/",
    "/api/system/login-logs/",
    "/api/system/operation-logs/",
]

TARGET_KEYS = [
    "username",
    "name",
    "label",
    "project_name",
    "projectName",
    "issuer",
    "account_name",
    "accountName",
    "key",
    "id",
]


class OperationLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._record_if_needed(request, response)
        return response

    def _record_if_needed(self, request, response) -> None:
        if request.method not in WRITE_METHODS:
            return
        if getattr(request, "_operation_log_recorded", False):
            return
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return
        if not 200 <= int(getattr(response, "status_code", 0) or 0) < 300:
            return

        path = request.path
        if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            return

        rule = self._match_rule(path)
        if not rule:
            return

        action = self._action_for_request(rule, request)
        target = self._target_from_response(response) or self._target_from_path(path)
        detail = f"{request.method} {path}"
        try:
            record_operation_log(request, rule.module, action, target, detail)
        except DatabaseError:
            return

    def _match_rule(self, path: str) -> AuditRule | None:
        return next((rule for rule in AUDIT_RULES if path.startswith(rule.prefix)), None)

    def _action_for_request(self, rule: AuditRule, request) -> str:
        path = request.path
        if "/2fa/enable/" in path:
            return "开启 2FA"
        if "/2fa/disable/" in path:
            return "关闭 2FA"
        if "/2fa/reset/" in path:
            return "重置 2FA"
        if "/users/" in path and path.startswith("/api/system/roles/"):
            return "调整权限用户"
        if "/verify/" in path and path.startswith("/api/host-management/hosts/"):
            return "验证主机"
        if path.startswith("/api/security-scans/tasks/") and "/cancel/" in path:
            return "取消扫描"
        if path.startswith("/api/security-scans/tasks/") and "/retry-failed/" in path:
            return "重试失败主机"
        if path.startswith("/api/bulk-execution/tasks/") and "/cancel/" in path:
            return "取消任务"
        if "/files/upload/" in path:
            return "上传文件"
        if "/files/create-file/" in path:
            return "新建文件"
        if "/files/create-directory/" in path:
            return "新建目录"
        if "/files/create-symlink/" in path:
            return "新建链接"
        if "/files/rename/" in path:
            return "重命名文件"
        if "/files/delete/" in path:
            return "删除文件"
        if "/files/properties/update/" in path:
            return "更新文件属性"
        if rule.actions and request.method in rule.actions:
            return rule.actions[request.method]
        return DEFAULT_ACTION_BY_METHOD.get(request.method, request.method)

    def _target_from_response(self, response) -> str:
        data = getattr(response, "data", None)
        return self._target_from_data(data)

    def _target_from_data(self, data: Any) -> str:
        if isinstance(data, list):
            return f"{len(data)} 条记录" if data else ""
        if not isinstance(data, dict):
            return ""

        for nested_key in ["user", "role", "group", "host", "credential", "command", "profile"]:
            nested_target = self._target_from_data(data.get(nested_key))
            if nested_target:
                return nested_target

        for key in TARGET_KEYS:
            value = data.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    def _target_from_path(self, path: str) -> str:
        parts = [part for part in path.strip("/").split("/") if part]
        if parts and parts[-1].isdigit():
            return f"ID: {parts[-1]}"
        for part in reversed(parts):
            if part.isdigit():
                return f"ID: {part}"
        return ""
