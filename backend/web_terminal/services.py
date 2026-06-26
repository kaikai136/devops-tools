from __future__ import annotations

import base64
import io
import shlex
import stat
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
REMOTE_FILE_PREVIEW_MAX_BYTES = 65536
REMOTE_FILE_DOWNLOAD_MAX_BYTES = 20 * 1024 * 1024


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
        "verified": host.verified,
        "verifyStatus": host.verify_status,
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


def preview_remote_file(host: ManagedHost, path: str) -> dict:
    path = normalize_remote_file_path(path)
    attempts: list[dict] = []
    preview_readers = (
        ("SFTP protocol", read_remote_file_with_sftp),
        ("SCP (enhanced speed)", read_remote_file_with_scp_enhanced),
        ("SCP (normal speed)", read_remote_file_with_scp_normal),
    )

    for protocol, reader in preview_readers:
        try:
            content = reader(host, path)
            attempts.append({"protocol": protocol, "status": "success"})
            return {
                "path": path,
                "protocol": protocol,
                "attempts": attempts,
                "content": content,
            }
        except Exception as error:
            attempts.append({"protocol": protocol, "status": "failed", "error": str(error)})

    raise TerminalConnectionError("文件预览连接失败：" + "；".join(f"{item['protocol']} {item.get('error', '')}" for item in attempts))


def list_remote_directory(host: ManagedHost, path: str) -> dict:
    path = normalize_remote_file_path(path or ".")
    return run_remote_file_operation(
        "目录读取失败",
        (
            ("SFTP protocol", lambda: list_remote_directory_with_sftp(host, path)),
            ("SCP (enhanced speed)", lambda: list_remote_directory_with_scp_enhanced(host, path)),
            ("SCP (normal speed)", lambda: list_remote_directory_with_scp_normal(host, path)),
        ),
        path,
    )


def download_remote_file(host: ManagedHost, path: str) -> dict:
    path = normalize_remote_file_path(path)
    return run_remote_file_operation(
        "文件下载失败",
        (
            ("SFTP protocol", lambda: download_remote_file_with_sftp(host, path)),
            ("SCP (enhanced speed)", lambda: download_remote_file_with_scp_enhanced(host, path)),
            ("SCP (normal speed)", lambda: download_remote_file_with_scp_normal(host, path)),
        ),
        path,
    )


def upload_remote_file(host: ManagedHost, directory: str, filename: str, content_base64: str) -> dict:
    directory = normalize_remote_file_path(directory or ".")
    filename = normalize_remote_file_name(filename)
    try:
        data = base64.b64decode(content_base64 or "", validate=False)
    except Exception as error:
        raise TerminalConnectionError(f"上传文件内容解析失败：{error}")
    path = join_remote_path(directory, filename)
    return run_remote_file_operation(
        "文件上传失败",
        (
            ("SFTP protocol", lambda: upload_remote_file_with_sftp(host, path, data)),
            ("SCP (enhanced speed)", lambda: upload_remote_file_with_scp_enhanced(host, path, data)),
            ("SCP (normal speed)", lambda: upload_remote_file_with_scp_normal(host, path, data)),
        ),
        path,
    )


def run_remote_file_operation(label: str, operations, path: str) -> dict:
    attempts: list[dict] = []
    for protocol, operation in operations:
        try:
            payload = operation()
            attempts.append({"protocol": protocol, "status": "success"})
            payload.update({"path": path, "protocol": protocol, "attempts": attempts})
            return payload
        except Exception as error:
            attempts.append({"protocol": protocol, "status": "failed", "error": str(error)})
    raise TerminalConnectionError(label + "：" + "；".join(f"{item['protocol']} {item.get('error', '')}" for item in attempts))


def normalize_remote_file_path(path: str) -> str:
    path = str(path or "").strip()
    if not path:
        raise TerminalConnectionError("请选择要预览的文件")
    if "\x00" in path or "\n" in path or "\r" in path:
        raise TerminalConnectionError("文件路径不合法")
    return path


def normalize_remote_file_name(filename: str) -> str:
    filename = str(filename or "").strip().replace("\\", "/").split("/")[-1]
    if not filename or filename in {".", ".."} or "\x00" in filename:
        raise TerminalConnectionError("上传文件名不合法")
    return filename


def join_remote_path(directory: str, filename: str) -> str:
    if filename == "..":
        return parent_remote_path(directory)
    if directory in {"", "."}:
        return filename
    if directory == "/":
        return f"/{filename}"
    if directory == "~":
        return f"~/{filename}"
    return f"{directory.rstrip('/')}/{filename}"


def list_remote_directory_with_sftp(host: ManagedHost, path: str) -> dict:
    client = open_ssh_client(host)
    try:
        sftp = client.open_sftp()
        try:
            entries = []
            for item in sftp.listdir_attr(path):
                entries.append(
                    {
                        "name": item.filename,
                        "type": "directory" if stat.S_ISDIR(item.st_mode) else "file",
                        "modifiedAt": time.strftime("%Y/%m/%d", time.localtime(item.st_mtime or 0)),
                        "size": item.st_size or 0,
                        "path": join_remote_path(path, item.filename),
                    }
                )
        finally:
            sftp.close()
        entries.sort(key=lambda entry: (entry["type"] != "directory", entry["name"].lower()))
        return {"entries": [{"name": "..", "type": "directory", "modifiedAt": "", "size": 0, "path": parent_remote_path(path)}, *entries]}
    finally:
        client.close()


def list_remote_directory_with_scp_enhanced(host: ManagedHost, path: str) -> dict:
    quoted_path = shlex.quote(path)
    command = f"find {quoted_path} -maxdepth 1 -mindepth 1 -printf '%f\\t%y\\t%TY/%Tm/%Td\\t%s\\n'"
    return {"entries": parse_remote_find_entries(path, run_one_shot_ssh_command(host, command))}


def list_remote_directory_with_scp_normal(host: ManagedHost, path: str) -> dict:
    quoted_path = shlex.quote(path)
    command = f"ls -la --time-style=+%Y/%m/%d {quoted_path}"
    return {"entries": parse_remote_ls_entries(path, run_one_shot_ssh_command(host, command))}


def parent_remote_path(path: str) -> str:
    clean = path.rstrip("/")
    if clean in {"", "."}:
        return "."
    if clean in {"~", "/"}:
        return clean
    if clean.startswith("~/") and "/" not in clean[2:]:
        return "~"
    if "/" not in clean:
        return "."
    parent = clean.rsplit("/", 1)[0]
    return parent or "/"


def parse_remote_find_entries(path: str, output: str) -> list[dict]:
    entries = [{"name": "..", "type": "directory", "modifiedAt": "", "size": 0, "path": parent_remote_path(path)}]
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name, kind, modified_at, size = parts[:4]
        entry_type = "directory" if kind == "d" else "file"
        entries.append({"name": name, "type": entry_type, "modifiedAt": modified_at, "size": int(size or 0), "path": join_remote_path(path, name)})
    entries[1:] = sorted(entries[1:], key=lambda entry: (entry["type"] != "directory", entry["name"].lower()))
    return entries


def parse_remote_ls_entries(path: str, output: str) -> list[dict]:
    entries = [{"name": "..", "type": "directory", "modifiedAt": "", "size": 0, "path": parent_remote_path(path)}]
    for line in output.splitlines():
        if not line or line.startswith("total "):
            continue
        parts = line.split(maxsplit=6)
        if len(parts) < 7:
            continue
        mode, size, modified_at, name = parts[0], parts[4], parts[5], parts[6]
        if name in {".", ".."}:
            continue
        entry_type = "directory" if mode.startswith("d") else "file"
        entries.append({"name": name, "type": entry_type, "modifiedAt": modified_at, "size": int(size or 0), "path": join_remote_path(path, name)})
    entries[1:] = sorted(entries[1:], key=lambda entry: (entry["type"] != "directory", entry["name"].lower()))
    return entries


def read_remote_file_with_sftp(host: ManagedHost, path: str) -> str:
    client = open_ssh_client(host)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(path, "rb") as remote_file:
                data = remote_file.read(REMOTE_FILE_PREVIEW_MAX_BYTES + 1)
        finally:
            sftp.close()
        return decode_remote_file_preview(data)
    finally:
        client.close()


def read_remote_file_with_scp_enhanced(host: ManagedHost, path: str) -> str:
    quoted_path = shlex.quote(path)
    command = f"dd if={quoted_path} bs={REMOTE_FILE_PREVIEW_MAX_BYTES} count=1 2>/dev/null | base64 | tr -d '\\n'"
    output = run_one_shot_ssh_command(host, command)
    if not output.strip():
        raise TerminalConnectionError("远端未返回文件内容")
    return decode_remote_file_preview(base64.b64decode(output.strip(), validate=False))


def read_remote_file_with_scp_normal(host: ManagedHost, path: str) -> str:
    quoted_path = shlex.quote(path)
    command = f"dd if={quoted_path} bs={REMOTE_FILE_PREVIEW_MAX_BYTES} count=1 2>/dev/null"
    return decode_remote_file_preview(run_one_shot_ssh_command(host, command).encode("utf-8", errors="replace"))


def download_remote_file_with_sftp(host: ManagedHost, path: str) -> dict:
    client = open_ssh_client(host)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(path, "rb") as remote_file:
                data = remote_file.read(REMOTE_FILE_DOWNLOAD_MAX_BYTES + 1)
        finally:
            sftp.close()
        return encode_remote_download(path, data)
    finally:
        client.close()


def download_remote_file_with_scp_enhanced(host: ManagedHost, path: str) -> dict:
    quoted_path = shlex.quote(path)
    command = f"dd if={quoted_path} bs={REMOTE_FILE_DOWNLOAD_MAX_BYTES} count=1 2>/dev/null | base64 | tr -d '\\n'"
    output = run_one_shot_ssh_command(host, command)
    if not output.strip():
        raise TerminalConnectionError("远端未返回文件内容")
    return encode_remote_download(path, base64.b64decode(output.strip(), validate=False))


def download_remote_file_with_scp_normal(host: ManagedHost, path: str) -> dict:
    quoted_path = shlex.quote(path)
    command = f"base64 {quoted_path} | tr -d '\\n'"
    output = run_one_shot_ssh_command(host, command)
    if not output.strip():
        raise TerminalConnectionError("远端未返回文件内容")
    return encode_remote_download(path, base64.b64decode(output.strip(), validate=False))


def upload_remote_file_with_sftp(host: ManagedHost, path: str, data: bytes) -> dict:
    client = open_ssh_client(host)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(path, "wb") as remote_file:
                remote_file.write(data)
        finally:
            sftp.close()
        return {"size": len(data)}
    finally:
        client.close()


def upload_remote_file_with_scp_enhanced(host: ManagedHost, path: str, data: bytes) -> dict:
    encoded = base64.b64encode(data)
    quoted_path = shlex.quote(path)
    run_one_shot_ssh_upload(host, f"base64 -d > {quoted_path}", encoded)
    return {"size": len(data)}


def upload_remote_file_with_scp_normal(host: ManagedHost, path: str, data: bytes) -> dict:
    quoted_path = shlex.quote(path)
    run_one_shot_ssh_upload(host, f"cat > {quoted_path}", data)
    return {"size": len(data)}


def encode_remote_download(path: str, data: bytes) -> dict:
    if len(data) > REMOTE_FILE_DOWNLOAD_MAX_BYTES:
        raise TerminalConnectionError("文件超过 20 MB，暂不支持浏览器直接下载")
    filename = path.rstrip("/").split("/")[-1] or "download"
    return {"filename": filename, "contentBase64": base64.b64encode(data).decode("ascii"), "size": len(data)}


def run_one_shot_ssh_command(host: ManagedHost, command: str) -> str:
    client = open_ssh_client(host)
    try:
        _, stdout, stderr = client.exec_command(command, timeout=30)
        output = stdout.read()
        error_output = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise TerminalConnectionError(error_output or f"远端命令退出码 {exit_code}")
        return output.decode("utf-8", errors="replace")
    finally:
        client.close()


def run_one_shot_ssh_upload(host: ManagedHost, command: str, data: bytes) -> None:
    client = open_ssh_client(host)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=60)
        stdin.write(data)
        stdin.channel.shutdown_write()
        error_output = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise TerminalConnectionError(error_output or f"远端命令退出码 {exit_code}")
    finally:
        client.close()


def decode_remote_file_preview(data: bytes) -> str:
    truncated = len(data) > REMOTE_FILE_PREVIEW_MAX_BYTES
    content = data[:REMOTE_FILE_PREVIEW_MAX_BYTES].decode("utf-8", errors="replace")
    if truncated:
        content += "\n\n... 文件较大，已截取前 64 KB"
    return normalize_terminal_output(content)


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
