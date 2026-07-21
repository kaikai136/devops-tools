from __future__ import annotations

from accounts.permissions import has_feature_permission
from host_management.models import ManagedHost

from ..models import TerminalSession
from ..services.rdp import terminal_protocol_for_host


class GatewayAssetError(Exception):
    pass


def gateway_host_queryset(user):
    if not has_feature_permission(user, "hosts", "terminal"):
        return ManagedHost.objects.none()
    return ManagedHost.objects.select_related("group").order_by("group__name", "name", "id")


def resolve_gateway_host(user, host_id: int) -> ManagedHost:
    if not has_feature_permission(user, "hosts", "terminal"):
        raise GatewayAssetError("没有 SSH 网关权限")
    try:
        host = ManagedHost.objects.select_related("group").get(id=int(host_id))
    except (TypeError, ValueError, ManagedHost.DoesNotExist):
        raise GatewayAssetError("主机不存在")
    if terminal_protocol_for_host(host) != TerminalSession.PROTOCOL_SSH:
        raise GatewayAssetError("Windows/RDP 主机暂不支持 SSH 网关")
    if not host.login_user:
        raise GatewayAssetError("主机未配置 SSH 登录用户")
    return host


def resolve_gateway_host_selector(user, selector: str) -> ManagedHost:
    value = str(selector or "").strip()
    if not value:
        raise GatewayAssetError("请输入有效主机 ID、名称或 IP")

    hosts = gateway_host_tree(user)
    lowered = value.lower()
    if lowered.count(":") == 1:
        host_token, port_token = lowered.rsplit(":", 1)
    else:
        host_token, port_token = lowered, ""

    if value.isdigit():
        number = int(value)
        if 1 <= number <= len(hosts):
            return resolve_gateway_host(user, hosts[number - 1].id)
        for host in hosts:
            if host.id == number:
                return resolve_gateway_host(user, host.id)
        raise GatewayAssetError("主机不存在")

    for index, host in enumerate(hosts, start=1):
        ip = str(host.public_ip or host.private_ip or "")
        candidates = {
            host.name.lower(),
            ip.lower(),
            f"{ip}:{host.port}".lower(),
            f"{index}-{host.name}".lower(),
            f"{host.id}-{host.name}".lower(),
        }
        if lowered in candidates:
            return resolve_gateway_host(user, host.id)
        if port_token and host_token == ip.lower() and port_token == str(host.port):
            return resolve_gateway_host(user, host.id)

    raise GatewayAssetError("主机不存在")


def gateway_host_tree(user) -> list[ManagedHost]:
    return [host for host in gateway_host_queryset(user) if terminal_protocol_for_host(host) == TerminalSession.PROTOCOL_SSH]


def gateway_menu_text(user) -> str:
    hosts = gateway_host_tree(user)
    lines = [
        "\r\n可连接资产",
        "输入主机 ID 后回车连接，输入 q 退出。",
        "",
    ]
    if not hosts:
        lines.append("暂无可连接 SSH 主机。")
    for index, host in enumerate(hosts, start=1):
        group_name = host.group.name if host.group_id and host.group else "default"
        ip = host.public_ip or host.private_ip
        lines.append(f"{index:>4}  {host.name}  {ip}:{host.port}  {host.login_user}  [{group_name}]")
    lines.append("")
    lines.append("asset> ")
    return "\r\n".join(lines)
