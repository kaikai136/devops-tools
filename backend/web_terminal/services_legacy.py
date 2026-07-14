from __future__ import annotations

import base64
import re
import shlex
import stat
import time

from django.utils import timezone

from host_management.models import ManagedHost

from .models import TerminalSession

from .services.commands import (
    run_live_terminal_command,
    run_one_shot_ssh_command,
    run_one_shot_ssh_upload,
    run_session_command,
)
from .services.connections import (
    DEFAULT_TERMINAL_COLS,
    DEFAULT_TERMINAL_ROWS,
    LIVE_TERMINALS,
    LiveTerminalConnection,
    TerminalConnectionError,
    load_private_key,
    normalize_terminal_output,
    open_live_terminal,
    open_ssh_client,
    should_retry_ssh_connect_error,
)


REMOTE_FILE_STREAM_CHUNK_BYTES = 1024 * 1024
REMOTE_FILE_OWNER_PATTERN = re.compile(r"^[^\s:\x00-\x1f\x7f]+$")
REMOTE_FILE_OCTAL_MODE_PATTERN = re.compile(r"^[0-7]{3,4}$")
REMOTE_MONITOR_SAMPLE_INTERVAL_SECONDS = 1
TERMINAL_PROTOCOL_SSH = TerminalSession.PROTOCOL_SSH
TERMINAL_PROTOCOL_RDP = TerminalSession.PROTOCOL_RDP
REMOTE_MONITOR_COMMAND = r"""
set -eu
test -r /proc/stat
test -r /proc/meminfo
test -r /proc/net/dev
printf 'SECTION:system\n'
printf 'hostname=%s\n' "$(hostname 2>/dev/null || printf '-')"
printf 'arch=%s\n' "$(uname -m 2>/dev/null || printf '-')"
printf 'kernel=%s\n' "$(uname -sr 2>/dev/null || printf '-')"
if [ -r /etc/os-release ]; then
  . /etc/os-release
  printf 'os=%s\n' "${PRETTY_NAME:-${NAME:-Linux}}"
else
  printf 'os=%s\n' "$(uname -s 2>/dev/null || printf Linux)"
fi
printf 'uptime=%s\n' "$(cut -d' ' -f1 /proc/uptime 2>/dev/null || printf 0)"
printf 'SECTION:cpu1\n'
grep '^cpu' /proc/stat
printf 'SECTION:net1\n'
cat /proc/net/dev
printf 'SECTION:load\n'
cat /proc/loadavg
sleep 1
printf 'SECTION:cpu2\n'
grep '^cpu' /proc/stat
printf 'SECTION:net2\n'
cat /proc/net/dev
printf 'SECTION:mem\n'
cat /proc/meminfo
printf 'SECTION:df\n'
df -PT -B1 2>/dev/null
"""


def terminal_protocol_for_host(host: ManagedHost) -> str:
    if host.os == "windows" or host.system_type.lower() == "windows":
        return TERMINAL_PROTOCOL_RDP
    return TERMINAL_PROTOCOL_SSH


def guacamole_instruction(*elements) -> str:
    return ",".join(guacamole_element(element) for element in elements) + ";"


def guacamole_element(value) -> str:
    text = str(value)
    return f"{len(text)}.{text}"


def parse_guacamole_instruction(data: str) -> list[str]:
    elements: list[str] = []
    cursor = 0
    while cursor < len(data):
        length_end = data.find(".", cursor)
        if length_end < 0:
            raise TerminalConnectionError("Guacamole 指令不完整")
        try:
            length = int(data[cursor:length_end])
        except ValueError as error:
            raise TerminalConnectionError("Guacamole 指令长度无效") from error
        value_start = length_end + 1
        value_end = value_start + length
        if value_end >= len(data):
            raise TerminalConnectionError("Guacamole 指令不完整")
        elements.append(data[value_start:value_end])
        terminator = data[value_end]
        cursor = value_end + 1
        if terminator == ";":
            if cursor != len(data):
                raise TerminalConnectionError("Guacamole 指令包含多余数据")
            return elements
        if terminator != ",":
            raise TerminalConnectionError("Guacamole 指令分隔符无效")
    raise TerminalConnectionError("Guacamole 指令不完整")


def is_guacamole_internal_instruction(data: str) -> bool:
    try:
        elements = parse_guacamole_instruction(data)
    except TerminalConnectionError:
        return False
    return bool(elements) and elements[0] == ""


def read_guacamole_instruction(source, *, max_chars: int = 1024 * 1024) -> str:
    chunks: list[str] = []
    total = 0
    while total < max_chars:
        data = source.recv(8192)
        if not data:
            raise TerminalConnectionError("guacd 连接已关闭")
        text = data.decode("utf-8", errors="replace")
        chunks.append(text)
        total += len(text)
        combined = "".join(chunks)
        terminator = find_guacamole_instruction_end(combined)
        if terminator >= 0:
            return combined[:terminator]
    raise TerminalConnectionError("guacd 指令过大")


def find_guacamole_instruction_end(data: str) -> int:
    cursor = 0
    while cursor < len(data):
        length_end = data.find(".", cursor)
        if length_end < 0:
            return -1
        try:
            length = int(data[cursor:length_end])
        except ValueError as error:
            raise TerminalConnectionError("Guacamole 指令长度无效") from error
        value_end = length_end + 1 + length
        if value_end >= len(data):
            return -1
        terminator = data[value_end]
        cursor = value_end + 1
        if terminator == ";":
            return cursor
        if terminator != ",":
            raise TerminalConnectionError("Guacamole 指令分隔符无效")
    return -1


def greeting_for(host: ManagedHost) -> str:
    target = host.public_ip or host.private_ip
    return "\n".join(
        [
            f"正在连接 {host.name} ({target}:{host.port})",
            f"登录用户：{host.login_user or '未配置'}",
            "连接已建立。输入命令后回车执行。",
        ]
    )






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


def get_remote_resource_monitor(host: ManagedHost) -> dict:
    try:
        output = run_one_shot_ssh_command(host, REMOTE_MONITOR_COMMAND)
        return parse_remote_resource_monitor_output(output)
    except TerminalConnectionError as error:
        message = str(error)
        if "No such file" in message or "can't open" in message or "test:" in message or "远端命令退出码" in message:
            raise TerminalConnectionError("当前主机不支持资源监控")
        raise


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


def download_remote_file_content(host: ManagedHost, path: str) -> dict:
    path = normalize_remote_file_path(path)
    payload = run_remote_file_operation(
        "文件下载失败",
        (
            ("SFTP protocol", lambda: download_remote_file_content_with_sftp(host, path)),
            ("SCP (enhanced speed)", lambda: download_remote_file_content_with_scp_enhanced(host, path)),
            ("SCP (normal speed)", lambda: download_remote_file_content_with_scp_normal(host, path)),
        ),
        path,
    )
    return {"filename": path.rstrip("/").split("/")[-1] or "download", "content": payload["content"]}


def stream_remote_file_content(host: ManagedHost, path: str, protocol: str = "auto") -> dict:
    path = normalize_remote_file_path(path)
    protocol = normalize_remote_download_protocol(protocol)
    if protocol == "sftp":
        payload = stream_remote_file_content_with_sftp(host, path)
        payload.setdefault("path", path)
        payload.setdefault("protocol", "SFTP protocol")
        return payload
    if protocol == "scp":
        payload = stream_remote_file_content_with_scp(host, path)
        payload.setdefault("path", path)
        payload.setdefault("protocol", "SCP command")
        return payload
    try:
        payload = stream_remote_file_content_with_scp(host, path)
        payload.setdefault("path", path)
        payload.setdefault("protocol", "SCP command")
        return payload
    except Exception:
        payload = stream_remote_file_content_with_sftp(host, path)
        payload.setdefault("path", path)
        payload.setdefault("protocol", "SFTP protocol")
        return payload


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


def normalize_remote_download_protocol(protocol: str) -> str:
    value = str(protocol or "auto").strip().lower()
    if value in {"", "auto"}:
        return "auto"
    if value in {"sftp", "scp"}:
        return value
    raise TerminalConnectionError("下载方式不合法")


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


def parse_remote_resource_monitor_output(output: str) -> dict:
    sections = split_monitor_sections(output)
    required_sections = {"system", "cpu1", "cpu2", "load", "mem", "net1", "net2", "df"}
    if not required_sections.issubset(sections):
        raise TerminalConnectionError("当前主机不支持资源监控")

    system = parse_monitor_key_values(sections["system"])
    cpu1 = parse_monitor_cpu_line(sections["cpu1"])
    cpu2 = parse_monitor_cpu_line(sections["cpu2"])
    network1 = parse_monitor_network(sections["net1"])
    network2 = parse_monitor_network(sections["net2"])

    return {
        "system": {
            "hostname": system.get("hostname", "-") or "-",
            "arch": system.get("arch", "-") or "-",
            "os": system.get("os", system.get("kernel", "Linux")) or "Linux",
            "kernel": system.get("kernel", "-") or "-",
            "uptimeSeconds": parse_monitor_float(system.get("uptime", "0")),
        },
        "cpu": {
            "usagePercent": calculate_monitor_cpu_usage(cpu1, cpu2),
            "cores": detect_monitor_cpu_cores(sections["cpu2"]),
            **parse_monitor_load(sections["load"]),
        },
        "memory": parse_monitor_memory(sections["mem"]),
        "network": parse_monitor_network_rates(network1, network2, REMOTE_MONITOR_SAMPLE_INTERVAL_SECONDS),
        "disks": parse_monitor_disks(sections["df"]),
    }


def split_monitor_sections(output: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_section = ""

    for line in output.splitlines():
        if line.startswith("SECTION:"):
            current_section = line.split(":", 1)[1].strip()
            sections.setdefault(current_section, [])
            continue
        if current_section:
            sections[current_section].append(line)

    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def parse_monitor_key_values(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_monitor_cpu_line(output: str) -> list[int]:
    line = next((item for item in output.splitlines() if item.startswith("cpu ")), "")
    parts = line.split()
    if len(parts) < 5:
        raise TerminalConnectionError("CPU 数据解析失败")
    return [parse_monitor_int(value) for value in parts[1:]]


def calculate_monitor_cpu_usage(previous: list[int], current: list[int]) -> float:
    previous_idle = previous[3] + (previous[4] if len(previous) > 4 else 0)
    current_idle = current[3] + (current[4] if len(current) > 4 else 0)
    previous_total = sum(previous)
    current_total = sum(current)
    total_delta = current_total - previous_total
    idle_delta = current_idle - previous_idle
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)


def parse_monitor_load(output: str) -> dict:
    values = output.strip().split()
    return {
        "load1": parse_monitor_float(values[0]) if len(values) > 0 else 0.0,
        "load5": parse_monitor_float(values[1]) if len(values) > 1 else 0.0,
        "load15": parse_monitor_float(values[2]) if len(values) > 2 else 0.0,
    }


def detect_monitor_cpu_cores(output: str) -> int:
    return max(1, len([line for line in output.splitlines() if line.startswith("cpu") and not line.startswith("cpu ")]))


def parse_monitor_memory(output: str) -> dict:
    values: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.replace(":", "").split()
        if len(parts) >= 2:
            values[parts[0]] = parse_monitor_int(parts[1]) * 1024

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    free = values.get("MemFree", 0)
    buffers = values.get("Buffers", 0)
    cached = values.get("Cached", 0) + values.get("SReclaimable", 0)
    if total <= 0:
        raise TerminalConnectionError("内存数据解析失败")
    if available <= 0:
        available = free + buffers + cached
    used = max(0, total - available)

    return {
        "totalBytes": total,
        "usedBytes": used,
        "availableBytes": available,
        "cacheBytes": cached,
        "usagePercent": round(used / total * 100, 1),
    }


def parse_monitor_network(output: str) -> dict[str, dict[str, int]]:
    interfaces: dict[str, dict[str, int]] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        interface = name.strip()
        if interface == "lo":
            continue
        values = data.split()
        if len(values) < 16:
            continue
        interfaces[interface] = {
            "rxBytes": parse_monitor_int(values[0]),
            "txBytes": parse_monitor_int(values[8]),
        }
    return interfaces


def parse_monitor_network_rates(previous: dict[str, dict[str, int]], current: dict[str, dict[str, int]], interval_seconds: int) -> list[dict]:
    interfaces: list[dict] = []
    interval = max(1, interval_seconds)
    for name in sorted(current.keys(), key=natural_sort_key):
        current_values = current[name]
        previous_values = previous.get(name, current_values)
        rx_rate = max(0, current_values["rxBytes"] - previous_values["rxBytes"]) / interval
        tx_rate = max(0, current_values["txBytes"] - previous_values["txBytes"]) / interval
        interfaces.append(
            {
                "name": name,
                "rxBytesPerSecond": round(rx_rate, 1),
                "txBytesPerSecond": round(tx_rate, 1),
            }
        )
    return interfaces


def parse_monitor_disks(output: str) -> list[dict]:
    disks: list[dict] = []
    ignored_types = {"tmpfs", "devtmpfs", "overlay", "squashfs"}

    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 7:
            continue
        filesystem, file_type, total, used, available, percent, mountpoint = parts[:7]
        if file_type in ignored_types:
            continue
        total_bytes = parse_monitor_int(total)
        if total_bytes <= 0:
            continue
        disks.append(
            {
                "filesystem": filesystem,
                "type": file_type,
                "mountpoint": mountpoint,
                "totalBytes": total_bytes,
                "usedBytes": parse_monitor_int(used),
                "availableBytes": parse_monitor_int(available),
                "usagePercent": round(parse_monitor_float(percent.rstrip("%")), 1),
            }
        )

    return disks


def parse_monitor_int(value: str) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def parse_monitor_float(value: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


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
    payload = download_remote_file_content_with_sftp(host, path)
    return encode_remote_download(path, payload["content"])


def download_remote_file_content_with_sftp(host: ManagedHost, path: str) -> dict:
    client = open_ssh_client(host)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(path, "rb") as remote_file:
                data = remote_file.read()
        finally:
            sftp.close()
        return {"content": data}
    finally:
        client.close()


def stream_remote_file_content_with_sftp(host: ManagedHost, path: str) -> dict:
    client = open_ssh_client(host)
    sftp = None
    remote_file = None
    try:
        sftp = client.open_sftp()
        attrs = sftp.stat(path)
        remote_file = sftp.open(path, "rb")
    except Exception:
        if remote_file is not None:
            remote_file.close()
        if sftp is not None:
            sftp.close()
        client.close()
        raise

    def chunks():
        try:
            while True:
                chunk = remote_file.read(REMOTE_FILE_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                yield chunk
        finally:
            remote_file.close()
            sftp.close()
            client.close()

    return {
        "filename": path.rstrip("/").split("/")[-1] or "download",
        "content": chunks(),
        "size": int(getattr(attrs, "st_size", 0) or 0),
    }


def stream_remote_file_content_with_scp(host: ManagedHost, path: str) -> dict:
    client = open_ssh_client(host)
    quoted_path = shlex.quote(path)
    command = f"stat -c %s -- {quoted_path} 2>/dev/null; cat -- {quoted_path}"
    try:
        _, stdout, stderr = client.exec_command(command, timeout=30)
    except Exception:
        client.close()
        raise
    size_line = stdout.readline().strip()
    try:
        size = int(size_line or "0")
    except ValueError:
        size = 0

    def chunks():
        try:
            while True:
                chunk = stdout.read(REMOTE_FILE_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                yield chunk
            error_output = stderr.read().decode("utf-8", errors="replace").strip()
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                raise TerminalConnectionError(error_output or f"远端下载命令退出码 {exit_code}")
        finally:
            client.close()

    return {
        "filename": path.rstrip("/").split("/")[-1] or "download",
        "content": chunks(),
        "size": size,
    }


def download_remote_file_with_scp_enhanced(host: ManagedHost, path: str) -> dict:
    payload = download_remote_file_content_with_scp_enhanced(host, path)
    return encode_remote_download(path, payload["content"])


def download_remote_file_content_with_scp_enhanced(host: ManagedHost, path: str) -> dict:
    quoted_path = shlex.quote(path)
    command = f"base64 {quoted_path} | tr -d '\\n'"
    output = run_one_shot_ssh_command(host, command)
    return {"content": base64.b64decode(output.strip(), validate=False)}


def download_remote_file_with_scp_normal(host: ManagedHost, path: str) -> dict:
    payload = download_remote_file_content_with_scp_normal(host, path)
    return encode_remote_download(path, payload["content"])


def download_remote_file_content_with_scp_normal(host: ManagedHost, path: str) -> dict:
    quoted_path = shlex.quote(path)
    command = f"base64 {quoted_path} | tr -d '\\n'"
    output = run_one_shot_ssh_command(host, command)
    return {"content": base64.b64decode(output.strip(), validate=False)}


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
    filename = path.rstrip("/").split("/")[-1] or "download"
    return {"filename": filename, "contentBase64": base64.b64encode(data).decode("ascii"), "size": len(data)}
