from __future__ import annotations

import re
import shlex
import stat
import time

from .errors import TerminalConnectionError


REMOTE_FILE_OWNER_PATTERN = re.compile(r"^[^\s:\x00-\x1f\x7f]+$")

REMOTE_FILE_OCTAL_MODE_PATTERN = re.compile(r"^[0-7]{3,4}$")

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

def normalize_remote_stat_identity(name: str, numeric_id: str) -> str:
    name = str(name or "").strip()
    numeric_id = str(numeric_id or "").strip()
    if not name or name.upper() in {"UNKNOWN", "NOBODY"}:
        return numeric_id
    return name

def format_remote_timestamp(value: float) -> str:
    return time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(value or 0))

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

__all__ = [
    'normalize_remote_file_path',
    'normalize_remote_file_name',
    'normalize_remote_relative_file_path',
    'normalize_remote_download_protocol',
    'normalize_remote_symlink_target',
    'normalize_remote_file_owner',
    'normalize_remote_file_octal_mode',
    'join_remote_path',
    'parent_remote_path',
    'parent_remote_entry',
    'remote_stat_command',
    'parse_remote_stat_output',
    'remote_file_properties_payload',
    'normalize_remote_stat_identity',
    'format_remote_timestamp',
    'parse_remote_find_entries',
    'parse_remote_ls_entries',
    'remote_file_sort_key',
    'remote_file_sort_rank',
    'natural_sort_key',
]
