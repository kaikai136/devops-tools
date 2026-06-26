from __future__ import annotations

import base64
import io
import re
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
REMOTE_FILE_DOWNLOAD_MAX_BYTES = 20 * 1024 * 1024
REMOTE_FILE_OWNER_PATTERN = re.compile(r"^[^\s:\x00-\x1f\x7f]+$")
REMOTE_FILE_OCTAL_MODE_PATTERN = re.compile(r"^[0-7]{3,4}$")


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


def upload_remote_file(host: ManagedHost, directory: str, filename: str, content_base64: str, relative_path: str = "") -> dict:
    directory = normalize_remote_file_path(directory or ".")
    upload_name = normalize_remote_relative_file_path(relative_path) if str(relative_path or "").strip() else normalize_remote_file_name(filename)
    try:
        data = base64.b64decode(content_base64 or "", validate=False)
    except Exception as error:
        raise TerminalConnectionError(f"上传文件内容解析失败：{error}")
    path = join_remote_path(directory, upload_name)
    return run_remote_file_operation(
        "文件上传失败",
        (
            ("SFTP protocol", lambda: upload_remote_file_with_sftp(host, path, data)),
            ("SCP (enhanced speed)", lambda: upload_remote_file_with_scp_enhanced(host, path, data)),
            ("SCP (normal speed)", lambda: upload_remote_file_with_scp_normal(host, path, data)),
        ),
        path,
    )


def create_remote_file(host: ManagedHost, directory: str, filename: str, octal_mode: str = "") -> dict:
    directory = normalize_remote_file_path(directory or ".")
    filename = normalize_remote_file_name(filename)
    octal_mode = normalize_remote_file_octal_mode(octal_mode) if str(octal_mode or "").strip() else ""
    path = join_remote_path(directory, filename)
    run_one_shot_ssh_command(host, f"if test -e {shlex.quote(path)}; then printf %s {shlex.quote('目标已存在')} >&2; exit 1; fi; : > {shlex.quote(path)}")
    if octal_mode:
        run_one_shot_ssh_command(host, f"chmod {octal_mode} {shlex.quote(path)}")
    return get_remote_file_properties(host, path)


def create_remote_directory(host: ManagedHost, directory: str, dirname: str, octal_mode: str = "") -> dict:
    directory = normalize_remote_file_path(directory or ".")
    dirname = normalize_remote_file_name(dirname)
    octal_mode = normalize_remote_file_octal_mode(octal_mode) if str(octal_mode or "").strip() else ""
    path = join_remote_path(directory, dirname)
    run_one_shot_ssh_command(host, f"if test -e {shlex.quote(path)}; then printf %s {shlex.quote('目标已存在')} >&2; exit 1; fi; mkdir {shlex.quote(path)}")
    if octal_mode:
        run_one_shot_ssh_command(host, f"chmod {octal_mode} {shlex.quote(path)}")
    return get_remote_file_properties(host, path)


def create_remote_symlink(host: ManagedHost, directory: str, link_name: str, target_path: str) -> dict:
    directory = normalize_remote_file_path(directory or ".")
    link_name = normalize_remote_file_name(link_name)
    target_path = normalize_remote_symlink_target(target_path)
    path = join_remote_path(directory, link_name)
    run_one_shot_ssh_command(host, f"if test -e {shlex.quote(path)}; then printf %s {shlex.quote('目标已存在')} >&2; exit 1; fi; ln -s {shlex.quote(target_path)} {shlex.quote(path)}")
    return get_remote_file_properties(host, path)


def rename_remote_file(host: ManagedHost, path: str, new_name: str) -> dict:
    path = normalize_remote_file_path(path)
    new_name = normalize_remote_file_name(new_name)
    current = get_remote_file_properties(host, path)
    target = join_remote_path(str(current.get("directory") or parent_remote_path(path)), new_name)
    if target == current.get("path"):
        return current
    command = f"if test -e {shlex.quote(target)}; then printf %s {shlex.quote('目标已存在')} >&2; exit 1; fi; mv {shlex.quote(str(current.get('path') or path))} {shlex.quote(target)}"
    run_one_shot_ssh_command(host, command)
    return get_remote_file_properties(host, target)


def delete_remote_file(host: ManagedHost, path: str) -> dict:
    path = normalize_remote_file_path(path)
    current = get_remote_file_properties(host, path)
    current_path = str(current.get("path") or path)
    if current_path.rstrip("/") in {"", ".", "~", "/"}:
        raise TerminalConnectionError("不能删除根目录或当前目录")
    run_one_shot_ssh_command(host, f"rm -rf {shlex.quote(current_path)}")
    return {"deleted": True, "path": current_path, "directory": current.get("directory") or parent_remote_path(current_path)}


def get_remote_file_properties(host: ManagedHost, path: str) -> dict:
    path = normalize_remote_file_path(path)
    return run_remote_file_operation(
        "文件属性读取失败",
        (
            ("SFTP protocol", lambda: get_remote_file_properties_with_sftp(host, path)),
            ("SCP (normal speed)", lambda: get_remote_file_properties_with_stat(host, path)),
        ),
        path,
    )


def update_remote_file_properties(host: ManagedHost, path: str, owner: str, group: str, octal_mode: str, recursive: bool = False) -> dict:
    path = normalize_remote_file_path(path)
    owner = normalize_remote_file_owner(owner, "所有者")
    group = normalize_remote_file_owner(group, "组")
    octal_mode = normalize_remote_file_octal_mode(octal_mode)
    current = get_remote_file_properties(host, path)
    if recursive and current.get("type") != "directory":
        raise TerminalConnectionError("只有文件夹属性可以递归应用")

    quoted_path = shlex.quote(str(current.get("path") or path))
    recursive_flag = " -R" if recursive else ""
    run_one_shot_ssh_command(host, f"chmod{recursive_flag} {octal_mode} {quoted_path}")
    run_one_shot_ssh_command(host, f"chown{recursive_flag} {shlex.quote(owner + ':' + group)} {quoted_path}")
    updated = get_remote_file_properties(host, str(current.get("path") or path))
    updated["recursive"] = bool(recursive)
    return updated


def run_remote_file_operation(label: str, operations, path: str) -> dict:
    attempts: list[dict] = []
    for protocol, operation in operations:
        try:
            payload = operation()
            attempts.append({"protocol": protocol, "status": "success"})
            payload.setdefault("path", path)
            payload.update({"protocol": protocol, "attempts": attempts})
            return payload
        except Exception as error:
            attempts.append({"protocol": protocol, "status": "failed", "error": str(error)})
    raise TerminalConnectionError(label + "：" + "；".join(f"{item['protocol']} {item.get('error', '')}" for item in attempts))


def normalize_remote_file_path(path: str) -> str:
    path = str(path or "").strip()
    if not path:
        raise TerminalConnectionError("请选择文件")
    if "\x00" in path or "\n" in path or "\r" in path:
        raise TerminalConnectionError("文件路径不合法")
    return path


def normalize_remote_file_name(filename: str) -> str:
    filename = str(filename or "").strip().replace("\\", "/").split("/")[-1]
    if not filename or filename in {".", ".."} or "\x00" in filename:
        raise TerminalConnectionError("上传文件名不合法")
    return filename


def normalize_remote_relative_file_path(path: str) -> str:
    value = str(path or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or "\x00" in value or "\n" in value or "\r" in value:
        raise TerminalConnectionError("上传相对路径不合法")
    parts = [part for part in value.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        raise TerminalConnectionError("上传相对路径不合法")
    return "/".join(parts)


def normalize_remote_symlink_target(target_path: str) -> str:
    value = str(target_path or "").strip()
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise TerminalConnectionError("符号链接目标不合法")
    return value


def normalize_remote_file_owner(value: str, label: str) -> str:
    value = str(value or "").strip()
    if not value or not REMOTE_FILE_OWNER_PATTERN.fullmatch(value):
        raise TerminalConnectionError(f"{label}不合法")
    return value


def normalize_remote_file_octal_mode(value: str) -> str:
    value = str(value or "").strip()
    if not REMOTE_FILE_OCTAL_MODE_PATTERN.fullmatch(value):
        raise TerminalConnectionError("权限八进制不合法")
    return value.zfill(4)


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
            current_path = sftp.normalize(path)
            entries = []
            for item in sftp.listdir_attr(current_path):
                entries.append(
                    {
                        "name": item.filename,
                        "type": "directory" if stat.S_ISDIR(item.st_mode) else "file",
                        "modifiedAt": time.strftime("%Y/%m/%d %H:%M", time.localtime(item.st_mtime or 0)),
                        "size": item.st_size or 0,
                        "permissions": stat.filemode(item.st_mode),
                        "owner": str(getattr(item, "st_uid", "") or ""),
                        "group": str(getattr(item, "st_gid", "") or ""),
                        "path": join_remote_path(current_path, item.filename),
                    }
                )
            enrich_remote_entries_with_stat(client, current_path, entries)
        finally:
            sftp.close()
        entries.sort(key=remote_file_sort_key)
        return {"path": current_path, "entries": [parent_remote_entry(current_path), *entries]}
    finally:
        client.close()


def list_remote_directory_with_scp_enhanced(host: ManagedHost, path: str) -> dict:
    current_path = resolve_remote_directory_path(host, path)
    quoted_path = shlex.quote(current_path)
    command = f"find {quoted_path} -maxdepth 1 -mindepth 1 -printf '%f\\t%y\\t%TY/%Tm/%Td %TH:%TM\\t%s\\t%M\\t%u\\t%g\\n'"
    return {"path": current_path, "entries": parse_remote_find_entries(current_path, run_one_shot_ssh_command(host, command))}


def list_remote_directory_with_scp_normal(host: ManagedHost, path: str) -> dict:
    current_path = resolve_remote_directory_path(host, path)
    quoted_path = shlex.quote(current_path)
    command = f"ls -la --time-style=+%Y/%m/%d_%H:%M {quoted_path}"
    return {"path": current_path, "entries": parse_remote_ls_entries(current_path, run_one_shot_ssh_command(host, command))}


def get_remote_file_properties_with_sftp(host: ManagedHost, path: str) -> dict:
    client = open_ssh_client(host)
    try:
        sftp = client.open_sftp()
        try:
            current_path = sftp.normalize(path)
            attrs = sftp.stat(current_path)
        finally:
            sftp.close()
        try:
            stat_payload = parse_remote_stat_output(current_path, run_client_command(client, remote_stat_command(current_path)))
            stat_payload["path"] = current_path
            return stat_payload
        except Exception:
            return remote_file_properties_payload(current_path, attrs, resolve_remote_identity_names(client, attrs))
    finally:
        client.close()


def get_remote_file_properties_with_stat(host: ManagedHost, path: str) -> dict:
    current_path = resolve_remote_file_path(host, path)
    return parse_remote_stat_output(current_path, run_one_shot_ssh_command(host, remote_stat_command(current_path)))


def resolve_remote_directory_path(host: ManagedHost, path: str) -> str:
    quoted_path = shlex.quote(path)
    command = f"cd {quoted_path} && pwd -P"
    resolved = run_one_shot_ssh_command(host, command).strip().splitlines()
    current_path = resolved[-1].strip() if resolved else ""
    if not current_path.startswith("/"):
        raise TerminalConnectionError("远端目录路径解析失败")
    return current_path


def resolve_remote_file_path(host: ManagedHost, path: str) -> str:
    quoted_path = shlex.quote(path)
    command = "python3 -c " + shlex.quote("import os, sys; print(os.path.realpath(os.path.expanduser(sys.argv[1])))") + " " + quoted_path
    try:
        resolved = run_one_shot_ssh_command(host, command).strip().splitlines()
    except Exception:
        resolved = run_one_shot_ssh_command(host, f"readlink -f {quoted_path}").strip().splitlines()
    current_path = resolved[-1].strip() if resolved else ""
    if not current_path.startswith("/"):
        raise TerminalConnectionError("远端文件路径解析失败")
    return current_path


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


def parent_remote_entry(path: str) -> dict:
    return {
        "name": "..",
        "type": "directory",
        "modifiedAt": "",
        "size": 0,
        "permissions": "",
        "owner": "",
        "group": "",
        "path": parent_remote_path(path),
    }


def remote_stat_command(path: str) -> str:
    return "stat -c '%F\\t%s\\t%U\\t%G\\t%u\\t%g\\t%a\\t%A\\t%X\\t%Y\\t%f' " + shlex.quote(path)


def run_client_command(client, command: str, timeout: int = 20) -> str:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    stdin.close()
    output = stdout.read()
    error_output = stderr.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        raise TerminalConnectionError(error_output or f"远端命令退出码 {exit_code}")
    return output.decode("utf-8", errors="replace")


def parse_remote_stat_output(path: str, output: str) -> dict:
    line = next((item for item in output.splitlines() if item.strip()), "")
    parts = line.split("\t")
    if len(parts) < 11:
        raise TerminalConnectionError("远端属性返回格式不正确")
    file_type, size, owner, group, uid, gid, octal_mode, permissions, accessed_at, modified_at, mode_hex = parts[:11]
    mode = int(mode_hex, 16)
    entry_type = "directory" if stat.S_ISDIR(mode) or "directory" in file_type.lower() else "file"
    octal_mode = normalize_remote_file_octal_mode(octal_mode)
    owner = normalize_remote_stat_identity(owner, uid)
    group = normalize_remote_stat_identity(group, gid)
    return {
        "name": path.rstrip("/").split("/")[-1] or path,
        "path": path,
        "directory": parent_remote_path(path),
        "type": entry_type,
        "size": int(size or 0),
        "modifiedAt": format_remote_timestamp(float(modified_at or 0)),
        "accessedAt": format_remote_timestamp(float(accessed_at or 0)),
        "owner": owner,
        "group": group,
        "uid": int(uid or 0),
        "gid": int(gid or 0),
        "permissions": permissions,
        "mode": mode,
        "octalMode": octal_mode,
        "special": {
            "setuid": bool(mode & stat.S_ISUID),
            "setgid": bool(mode & stat.S_ISGID),
            "sticky": bool(mode & stat.S_ISVTX),
        },
    }


def remote_file_properties_payload(path: str, attrs, identities: dict | None = None) -> dict:
    mode = int(attrs.st_mode or 0)
    octal_mode = f"{mode & 0o7777:04o}"
    uid = int(getattr(attrs, "st_uid", 0) or 0)
    gid = int(getattr(attrs, "st_gid", 0) or 0)
    identities = identities or {}
    owner = normalize_remote_stat_identity(str(identities.get("owner", "")), str(uid))
    group = normalize_remote_stat_identity(str(identities.get("group", "")), str(gid))
    return {
        "name": path.rstrip("/").split("/")[-1] or path,
        "path": path,
        "directory": parent_remote_path(path),
        "type": "directory" if stat.S_ISDIR(mode) else "file",
        "size": int(attrs.st_size or 0),
        "modifiedAt": format_remote_timestamp(float(attrs.st_mtime or 0)),
        "accessedAt": format_remote_timestamp(float(attrs.st_atime or 0)),
        "owner": owner,
        "group": group,
        "uid": uid,
        "gid": gid,
        "permissions": stat.filemode(mode),
        "mode": mode,
        "octalMode": octal_mode,
        "special": {
            "setuid": bool(mode & stat.S_ISUID),
            "setgid": bool(mode & stat.S_ISGID),
            "sticky": bool(mode & stat.S_ISVTX),
        },
    }


def resolve_remote_identity_names(client, attrs) -> dict:
    uid = str(int(getattr(attrs, "st_uid", 0) or 0))
    gid = str(int(getattr(attrs, "st_gid", 0) or 0))
    return {
        "owner": resolve_remote_user_name(client, uid),
        "group": resolve_remote_group_name(client, gid),
    }


def resolve_remote_user_name(client, uid: str) -> str:
    return run_optional_client_command(client, f"getent passwd {shlex.quote(uid)} 2>/dev/null | cut -d: -f1") or run_optional_client_command(
        client,
        f"id -nu {shlex.quote(uid)} 2>/dev/null",
    )


def resolve_remote_group_name(client, gid: str) -> str:
    return run_optional_client_command(client, f"getent group {shlex.quote(gid)} 2>/dev/null | cut -d: -f1")


def run_optional_client_command(client, command: str, timeout: int = 10) -> str:
    try:
        output = run_client_command(client, command, timeout=timeout).strip().splitlines()
    except Exception:
        return ""
    return output[-1].strip() if output else ""


def normalize_remote_stat_identity(name: str, numeric_id: str) -> str:
    name = str(name or "").strip()
    numeric_id = str(numeric_id or "").strip()
    if not name or name.upper() in {"UNKNOWN", "NOBODY"}:
        return numeric_id
    return name


def format_remote_timestamp(value: float) -> str:
    return time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(value or 0))


def enrich_remote_entries_with_stat(client, path: str, entries: list[dict]) -> None:
    if not entries:
        return

    command = f"find {shlex.quote(path)} -maxdepth 1 -mindepth 1 -printf '%f\\t%M\\t%u\\t%g\\n'"
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=20)
        stdin.close()
        output = stdout.read().decode("utf-8", errors="replace")
        if stdout.channel.recv_exit_status() != 0:
            return
    except Exception:
        return

    metadata = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name, permissions, owner, group = parts[:4]
        metadata[name] = {"permissions": permissions, "owner": owner, "group": group}

    for entry in entries:
        entry.update(metadata.get(entry["name"], {}))


def parse_remote_find_entries(path: str, output: str) -> list[dict]:
    entries = [parent_remote_entry(path)]
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        name, kind, modified_at, size, permissions, owner, group = parts[:7]
        modified_at = modified_at[:16]
        entry_type = "directory" if kind == "d" else "file"
        entries.append(
            {
                "name": name,
                "type": entry_type,
                "modifiedAt": modified_at,
                "size": int(size or 0),
                "permissions": permissions,
                "owner": owner,
                "group": group,
                "path": join_remote_path(path, name),
            }
        )
    entries[1:] = sorted(entries[1:], key=remote_file_sort_key)
    return entries


def parse_remote_ls_entries(path: str, output: str) -> list[dict]:
    entries = [parent_remote_entry(path)]
    for line in output.splitlines():
        if not line or line.startswith("total "):
            continue
        parts = line.split(maxsplit=6)
        if len(parts) < 7:
            continue
        mode, owner, group, size, modified_at, name = parts[0], parts[2], parts[3], parts[4], parts[5].replace("_", " "), parts[6]
        if name in {".", ".."}:
            continue
        entry_type = "directory" if mode.startswith("d") else "file"
        entries.append(
            {
                "name": name,
                "type": entry_type,
                "modifiedAt": modified_at,
                "size": int(size or 0),
                "permissions": mode,
                "owner": owner,
                "group": group,
                "path": join_remote_path(path, name),
            }
        )
    entries[1:] = sorted(entries[1:], key=remote_file_sort_key)
    return entries


def remote_file_sort_key(entry: dict):
    name = str(entry.get("name", ""))
    return (remote_file_sort_rank(entry, name), natural_sort_key(name))


def remote_file_sort_rank(entry: dict, name: str) -> int:
    if name.startswith("."):
        return 0
    if entry.get("type") == "directory":
        return 1
    return 2


def natural_sort_key(value: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


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
            ensure_remote_sftp_directory(sftp, parent_remote_path(path))
            with sftp.open(path, "wb") as remote_file:
                remote_file.write(data)
        finally:
            sftp.close()
        return {"size": len(data)}
    finally:
        client.close()


def ensure_remote_sftp_directory(sftp, directory: str) -> None:
    directory = str(directory or "").strip()
    if directory in {"", ".", "/", "~"}:
        return
    current = "/" if directory.startswith("/") else ""
    for part in [item for item in directory.split("/") if item]:
        current = f"{current.rstrip('/')}/{part}" if current else part
        try:
            sftp.stat(current)
        except Exception:
            sftp.mkdir(current)


def upload_remote_file_with_scp_enhanced(host: ManagedHost, path: str, data: bytes) -> dict:
    encoded = base64.b64encode(data)
    quoted_path = shlex.quote(path)
    quoted_parent = shlex.quote(parent_remote_path(path))
    run_one_shot_ssh_upload(host, f"mkdir -p {quoted_parent} && base64 -d > {quoted_path}", encoded)
    return {"size": len(data)}


def upload_remote_file_with_scp_normal(host: ManagedHost, path: str, data: bytes) -> dict:
    quoted_path = shlex.quote(path)
    quoted_parent = shlex.quote(parent_remote_path(path))
    run_one_shot_ssh_upload(host, f"mkdir -p {quoted_parent} && cat > {quoted_path}", data)
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
