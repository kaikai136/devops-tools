from __future__ import annotations

import io
import threading
import time

from django.utils import timezone

from host_management.models import HostGroup, ManagedHost
from host_management.services import build_group_tree

from .models import TerminalSession


class TerminalConnectionError(RuntimeError):
    pass


class LiveTerminalConnection:
    def __init__(self, client, channel):
        self.client = client
        self.channel = channel
        self.lock = threading.Lock()

    def read_available(self, timeout: float = 4.0, idle_timeout: float = 0.35) -> str:
        chunks: list[bytes] = []
        deadline = time.monotonic() + timeout
        last_data_at: float | None = None

        while time.monotonic() < deadline:
            if self.channel.recv_ready():
                chunks.append(self.channel.recv(65535))
                last_data_at = time.monotonic()
                continue

            if chunks and last_data_at and time.monotonic() - last_data_at >= idle_timeout:
                break
            if self.channel.closed or self.channel.exit_status_ready():
                break
            time.sleep(0.05)

        return normalize_terminal_output(b"".join(chunks).decode("utf-8", errors="replace"))

    def read_raw(self, max_bytes: int = 65535) -> str:
        if not self.channel.recv_ready():
            return ""
        return self.channel.recv(max_bytes).decode("utf-8", errors="replace")

    def send_data(self, data: str) -> None:
        with self.lock:
            if self.channel.closed:
                raise TerminalConnectionError("SSH 会话已关闭，请重新连接主机。")
            if data:
                self.channel.send(data)

    def send_command(self, command: str) -> str:
        self.send_data(command + "\n")
        return self.read_available(timeout=30.0)

    def resize(self, cols: int, rows: int) -> None:
        cols = max(1, min(cols, 300))
        rows = max(1, min(rows, 120))
        with self.lock:
            if not self.channel.closed:
                self.channel.resize_pty(width=cols, height=rows)

    def close(self) -> None:
        try:
            self.channel.close()
        finally:
            self.client.close()


LIVE_TERMINALS: dict[str, LiveTerminalConnection] = {}

SSH_CONNECT_ATTEMPTS = 3
SSH_CONNECT_TIMEOUT = 15
SSH_BANNER_TIMEOUT = 30
SSH_AUTH_TIMEOUT = 20
SSH_RETRY_DELAY_SECONDS = 0.8


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


def create_terminal_session(host: ManagedHost) -> tuple[TerminalSession, str]:
    connection = open_live_terminal(host)
    greeting = connection.read_available()
    session = TerminalSession.objects.create(
        host=host,
        transcript=f"connect {host.name}\n{greeting}\n",
    )
    LIVE_TERMINALS[str(session.session_id)] = connection
    return session, greeting or greeting_for(host)


def greeting_for(host: ManagedHost) -> str:
    target = host.public_ip or host.private_ip
    return "\n".join(
        [
            f"正在连接 {host.name} ({target}:{host.port})",
            f"登录用户：{host.login_user or '未配置'}",
            "连接已建立。输入命令后回车执行。",
        ]
    )


def run_session_command(session: TerminalSession, command: str) -> dict:
    command = command.strip()
    if not command:
        return {"command": command, "output": "", "exitCode": 0}
    if command.lower() in {"clear", "cls"}:
        return {"command": command, "output": "__CLEAR__", "exitCode": 0}

    output, exit_code = run_live_terminal_command(session, command)
    session.transcript += f"$ {command}\n{output}\n"
    session.last_command_at = timezone.now()
    update_fields = ["transcript", "last_command_at"]
    if command.lower() in {"exit", "logout"}:
        session.status = "closed"
        update_fields.append("status")
    session.save(update_fields=update_fields)
    return {"command": command, "output": output, "exitCode": exit_code}


def run_live_terminal_command(session: TerminalSession, command: str) -> tuple[str, int | None]:
    connection = LIVE_TERMINALS.get(str(session.session_id))
    if connection is None:
        return "SSH 会话已失效，请重新连接主机。", None

    try:
        output = connection.send_command(command)
        if command.lower() in {"exit", "logout"} or connection.channel.closed:
            connection.close()
            LIVE_TERMINALS.pop(str(session.session_id), None)
        return output.rstrip() or "命令已发送。", 0
    except Exception as error:
        LIVE_TERMINALS.pop(str(session.session_id), None)
        try:
            connection.close()
        except Exception:
            pass
        return f"SSH 连接或命令执行失败：{error}", None


def open_live_terminal(host: ManagedHost, cols: int = 120, rows: int = 36) -> LiveTerminalConnection:
    if not host.login_user:
        raise TerminalConnectionError("主机未配置登录用户，请先在主机管理中补充用户或选择账号。")

    try:
        import paramiko
    except ImportError:
        raise TerminalConnectionError("后端未安装 paramiko，无法建立 SSH 连接。请安装 requirements.txt 后重启后端。")

    target = str(host.public_ip or host.private_ip)
    pkey = load_private_key(paramiko, host.private_key)

    errors: list[str] = []
    for attempt in range(1, SSH_CONNECT_ATTEMPTS + 1):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=target,
                port=host.port,
                username=host.login_user,
                password=host.login_password or None,
                pkey=pkey,
                timeout=SSH_CONNECT_TIMEOUT,
                banner_timeout=SSH_BANNER_TIMEOUT,
                auth_timeout=SSH_AUTH_TIMEOUT,
                look_for_keys=False,
                allow_agent=False,
            )
            transport = client.get_transport()
            if transport is not None:
                transport.set_keepalive(30)
            channel = client.invoke_shell(term="xterm", width=cols, height=rows)
            channel.settimeout(0.0)
            return LiveTerminalConnection(client, channel)
        except Exception as error:
            errors.append(str(error))
            client.close()
            if attempt >= SSH_CONNECT_ATTEMPTS or not should_retry_ssh_connect_error(error):
                break
            time.sleep(SSH_RETRY_DELAY_SECONDS * attempt)

    last_error = errors[-1] if errors else "unknown error"
    raise TerminalConnectionError(f"SSH 连接失败：{last_error}")


def should_retry_ssh_connect_error(error: Exception) -> bool:
    message = str(error).lower()
    retry_markers = (
        "error reading ssh protocol banner",
        "error reading protocol banner",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
    )
    return any(marker in message for marker in retry_markers)


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


def normalize_terminal_output(output: str) -> str:
    return output.replace("\r\n", "\n").replace("\r", "\n").rstrip()
