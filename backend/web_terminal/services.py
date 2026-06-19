from __future__ import annotations

import io

from django.utils import timezone

from host_management.models import HostGroup, ManagedHost
from host_management.services import build_group_tree

from .models import TerminalSession


def host_payload(host: ManagedHost) -> dict:
    return {
        "id": host.id,
        "name": host.name,
        "group": host.group_id,
        "privateIp": str(host.private_ip),
        "publicIp": str(host.public_ip) if host.public_ip else "",
        "port": host.port,
        "loginUser": host.login_user,
        "remark": host.remark,
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


def create_terminal_session(host: ManagedHost) -> TerminalSession:
    return TerminalSession.objects.create(host=host, transcript=f"connect {host.name}\n")


def greeting_for(host: ManagedHost) -> str:
    target = host.public_ip or host.private_ip
    return "\n".join(
        [
            f"正在连接 {host.name} ({target}:{host.port})",
            f"登录用户：{host.login_user or '未配置'}",
            "连接已创建。输入命令后回车执行。",
        ]
    )


def run_session_command(session: TerminalSession, command: str) -> dict:
    command = command.strip()
    if not command:
        return {"command": command, "output": "", "exitCode": 0}
    if command.lower() in {"clear", "cls"}:
        return {"command": command, "output": "__CLEAR__", "exitCode": 0}

    output, exit_code = run_ssh_command(session.host, command)
    session.transcript += f"$ {command}\n{output}\n"
    session.last_command_at = timezone.now()
    session.save(update_fields=["transcript", "last_command_at"])
    return {"command": command, "output": output, "exitCode": exit_code}


def run_ssh_command(host: ManagedHost, command: str) -> tuple[str, int | None]:
    if not host.login_user:
        return "主机未配置登录用户，请先在主机管理中补充用户或选择账号。", None

    try:
        import paramiko
    except ImportError:
        return "后端未安装 paramiko，无法建立 SSH 连接。请安装 requirements.txt 后重启后端。", None

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    target = str(host.public_ip or host.private_ip)

    try:
        pkey = load_private_key(paramiko, host.private_key)
        client.connect(
            hostname=target,
            port=host.port,
            username=host.login_user,
            password=host.login_password or None,
            pkey=pkey,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )
        _stdin, stdout, stderr = client.exec_command(command, timeout=30)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        return (output + error).rstrip() or f"命令已执行，退出码 {exit_code}", exit_code
    except Exception as error:
        return f"SSH 连接或命令执行失败：{error}", None
    finally:
        client.close()


def load_private_key(paramiko, private_key: str):
    if not private_key.strip():
        return None

    errors = []
    for key_class in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
        try:
            return key_class.from_private_key(io.StringIO(private_key))
        except Exception as error:
            errors.append(str(error))
    raise ValueError(f"私钥解析失败：{errors[-1] if errors else '未知错误'}")
