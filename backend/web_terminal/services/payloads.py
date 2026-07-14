from __future__ import annotations

from host_management.models import HostGroup, ManagedHost
from host_management.services import build_group_tree

from ..models import TerminalSession
from .rdp import terminal_protocol_for_host


def host_payload(host: ManagedHost) -> dict:
    platform_type = "windows" if host.os == "windows" or host.system_type.lower() == "windows" else "linux"
    return {
        "id": host.id,
        "name": host.name,
        "group": host.group_id,
        "privateIp": str(host.private_ip),
        "publicIp": str(host.public_ip) if host.public_ip else "",
        "port": host.port,
        "loginUser": host.login_user,
        "remark": host.remark,
        "verified": host.verified,
        "verifyStatus": host.verify_status,
        "os": host.os,
        "platformType": platform_type,
        "terminalProtocol": terminal_protocol_for_host(host),
    }


def group_payload(group: HostGroup, hosts_by_group: dict[int, list[ManagedHost]]) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "hosts": [host_payload(host) for host in hosts_by_group.get(group.id, [])],
        "children": [group_payload(child, hosts_by_group) for child in getattr(group, "_prefetched_children", [])],
    }


def terminal_tree_payload() -> list[dict]:
    groups = build_group_tree()
    hosts_by_group: dict[int, list[ManagedHost]] = {}
    for host in ManagedHost.objects.select_related("group").order_by("name", "id"):
        hosts_by_group.setdefault(host.group_id, []).append(host)
    return [group_payload(group, hosts_by_group) for group in groups]


def session_payload(session: TerminalSession, greeting: str = "") -> dict:
    return {
        "id": str(session.session_id),
        "host": host_payload(session.host),
        "status": session.status,
        "greeting": greeting,
        "createdAt": session.created_at.isoformat() if session.created_at else None,
    }
