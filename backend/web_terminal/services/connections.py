from __future__ import annotations

import io
import threading
import time

from host_management.models import ManagedHost

from .errors import TerminalConnectionError

class LiveTerminalConnection:
    def __init__(self, client, channel):
        self.client = client
        self.channel = channel
        self.lock = threading.Lock()

    def read_available(self, timeout: float = 4.0, idle_timeout: float = 0.35) -> str:
        return normalize_terminal_output(self.read_available_raw(timeout=timeout, idle_timeout=idle_timeout))

    def read_available_raw(self, timeout: float = 4.0, idle_timeout: float = 0.35) -> str:
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

        return b"".join(chunks).decode("utf-8", errors="replace")

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

DEFAULT_TERMINAL_COLS = 120
DEFAULT_TERMINAL_ROWS = 36
SSH_CONNECT_ATTEMPTS = 3
SSH_CONNECT_TIMEOUT = 15
SSH_BANNER_TIMEOUT = 30
SSH_AUTH_TIMEOUT = 20
SSH_RETRY_DELAY_SECONDS = 0.8


def open_live_terminal(host: ManagedHost, cols: int = 120, rows: int = 36) -> LiveTerminalConnection:
    client = open_ssh_client(host)
    try:
        channel = client.invoke_shell(term="xterm", width=cols, height=rows)
        channel.settimeout(0.0)
        return LiveTerminalConnection(client, channel)
    except Exception as error:
        client.close()
        raise TerminalConnectionError(f"SSH 会话创建失败：{error}")


def open_ssh_client(host: ManagedHost):
    if not host.login_user:
        raise TerminalConnectionError("主机未配置登录用户，请先在主机管理中补充用户或选择账号。")

    try:
        import paramiko
    except ImportError:
        raise TerminalConnectionError("后端未安装 paramiko，无法建立 SSH 连接。请安装 requirements.txt 后重启后端。")

    target = str(host.public_ip or host.private_ip)
    try:
        pkey = load_private_key(paramiko, host.private_key)
    except ValueError as error:
        raise TerminalConnectionError(str(error))

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
            return client
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


__all__ = [
    'DEFAULT_TERMINAL_COLS',
    'DEFAULT_TERMINAL_ROWS',
    'LIVE_TERMINALS',
    'LiveTerminalConnection',
    'TerminalConnectionError',
    'load_private_key',
    'normalize_terminal_output',
    'open_live_terminal',
    'open_ssh_client',
    'should_retry_ssh_connect_error',
]
