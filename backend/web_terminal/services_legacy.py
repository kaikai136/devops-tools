from __future__ import annotations

from django.utils import timezone

from .models import TerminalSession


TERMINAL_PROTOCOL_SSH = TerminalSession.PROTOCOL_SSH
TERMINAL_PROTOCOL_RDP = TerminalSession.PROTOCOL_RDP


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


# Delayed until legacy definitions exist so either import order remains valid.
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
from .services.file_parsers import (
    REMOTE_FILE_OWNER_PATTERN,
    REMOTE_FILE_OCTAL_MODE_PATTERN,
    normalize_remote_file_path,
    normalize_remote_file_name,
    normalize_remote_relative_file_path,
    normalize_remote_download_protocol,
    normalize_remote_symlink_target,
    normalize_remote_file_owner,
    normalize_remote_file_octal_mode,
    join_remote_path,
    parent_remote_path,
    parent_remote_entry,
    remote_stat_command,
    parse_remote_stat_output,
    remote_file_properties_payload,
    normalize_remote_stat_identity,
    format_remote_timestamp,
    parse_remote_find_entries,
    parse_remote_ls_entries,
    remote_file_sort_key,
    remote_file_sort_rank,
    natural_sort_key,
)
from .services.monitoring import (
    REMOTE_MONITOR_SAMPLE_INTERVAL_SECONDS,
    REMOTE_MONITOR_COMMAND,
    get_remote_resource_monitor,
    parse_remote_resource_monitor_output,
    split_monitor_sections,
    parse_monitor_key_values,
    parse_monitor_cpu_line,
    calculate_monitor_cpu_usage,
    parse_monitor_load,
    detect_monitor_cpu_cores,
    parse_monitor_memory,
    parse_monitor_network,
    parse_monitor_network_rates,
    parse_monitor_disks,
    parse_monitor_int,
    parse_monitor_float,
)
from .services.files import (
    REMOTE_FILE_STREAM_CHUNK_BYTES,
    list_remote_directory,
    download_remote_file,
    download_remote_file_content,
    stream_remote_file_content,
    upload_remote_file,
    create_remote_file,
    create_remote_directory,
    create_remote_symlink,
    rename_remote_file,
    delete_remote_file,
    get_remote_file_properties,
    update_remote_file_properties,
    run_remote_file_operation,
    list_remote_directory_with_sftp,
    list_remote_directory_with_scp_enhanced,
    list_remote_directory_with_scp_normal,
    get_remote_file_properties_with_sftp,
    get_remote_file_properties_with_stat,
    resolve_remote_directory_path,
    resolve_remote_file_path,
    run_client_command,
    resolve_remote_identity_names,
    resolve_remote_user_name,
    resolve_remote_group_name,
    run_optional_client_command,
    enrich_remote_entries_with_stat,
    download_remote_file_with_sftp,
    download_remote_file_content_with_sftp,
    stream_remote_file_content_with_sftp,
    stream_remote_file_content_with_scp,
    download_remote_file_with_scp_enhanced,
    download_remote_file_content_with_scp_enhanced,
    download_remote_file_with_scp_normal,
    download_remote_file_content_with_scp_normal,
    upload_remote_file_with_sftp,
    ensure_remote_sftp_directory,
    upload_remote_file_with_scp_enhanced,
    upload_remote_file_with_scp_normal,
    encode_remote_download,
)
