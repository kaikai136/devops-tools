from __future__ import annotations

import math

from django.utils import timezone

from web_terminal.services import TerminalConnectionError, open_ssh_client

from .models import ManagedHost


CPU_COMMAND = "getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || grep -c '^processor' /proc/cpuinfo 2>/dev/null"
MEMORY_COMMAND = "awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null"
OS_COMMAND = ". /etc/os-release 2>/dev/null && printf '%s' \"${ID:-}\" || uname -s"
MACHINE_NAME_COMMAND = "hostname -f 2>/dev/null || hostname 2>/dev/null || uname -n"
SYSTEM_ARCH_COMMAND = "uname -m 2>/dev/null"
SYSTEM_TYPE_COMMAND = ". /etc/os-release 2>/dev/null && printf '%s' \"${ID:-}\" || uname -s"


def verify_host(host: ManagedHost) -> tuple[ManagedHost, str | None]:
    now = timezone.now()
    try:
        info = probe_host_info(host)
    except TerminalConnectionError as error:
        host.verified = False
        host.verify_status = "failed"
        host.cpu = 0
        host.memory = 0
        host.machine_name = ""
        host.updated_at = now
        host.save(update_fields=["verified", "verify_status", "cpu", "memory", "machine_name", "updated_at"])
        return host, str(error)

    host.machine_name = info["machine_name"]
    host.cpu = info["cpu"]
    host.memory = info["memory"]
    host.os = info["os"]
    host.system_arch = info["system_arch"]
    host.system_type = info["system_type"]
    host.verified = True
    host.verify_status = "verified"
    host.updated_at = now
    host.save(update_fields=["machine_name", "cpu", "memory", "os", "system_arch", "system_type", "verified", "verify_status", "updated_at"])
    return host, None


def probe_host_info(host: ManagedHost) -> dict:
    client = open_ssh_client(host)
    try:
        cpu = parse_positive_int(run_probe_command(client, CPU_COMMAND))
        memory = parse_memory_gb(run_probe_command(client, MEMORY_COMMAND))
        if cpu <= 0 or memory <= 0:
            raise TerminalConnectionError("无法识别机器 CPU 或内存信息")
        return {
            "machine_name": parse_machine_name(run_probe_command(client, MACHINE_NAME_COMMAND)),
            "system_arch": parse_machine_arch(run_probe_command(client, SYSTEM_ARCH_COMMAND)),
            "system_type": parse_system_type(run_probe_command(client, SYSTEM_TYPE_COMMAND)),
            "cpu": cpu,
            "memory": memory,
            "os": parse_os(run_probe_command(client, OS_COMMAND)),
        }
    except Exception as error:
        raise TerminalConnectionError(f"获取机器信息失败：{error}")
    finally:
        client.close()


def run_probe_command(client, command: str) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=12)
    exit_code = stdout.channel.recv_exit_status()
    output = stdout.read().decode("utf-8", errors="replace").strip()
    error_output = stderr.read().decode("utf-8", errors="replace").strip()
    if exit_code != 0 and not output:
        raise TerminalConnectionError(error_output or f"命令执行失败：{command}")
    return output


def parse_positive_int(value: str) -> int:
    try:
        number = int(value.strip().splitlines()[0])
    except (IndexError, TypeError, ValueError):
        return 0
    return max(number, 0)


def parse_memory_gb(value: str) -> int:
    memory_kb = parse_positive_int(value)
    if memory_kb <= 0:
        return 0
    return max(1, math.ceil(memory_kb / 1024 / 1024))


def parse_machine_name(value: str) -> str:
    try:
        name = value.strip().splitlines()[0].strip()
    except IndexError:
        return ""
    return name[:160]


def parse_machine_arch(value: str) -> str:
    try:
        arch = value.strip().splitlines()[0].strip()
    except IndexError:
        return ""
    return arch[:80]


def parse_system_type(value: str) -> str:
    try:
        system_type = value.strip().splitlines()[0].strip().lower()
    except IndexError:
        return ""
    return system_type[:80]


def parse_os(value: str) -> str:
    normalized = value.strip().lower()
    if "ubuntu" in normalized:
        return "ubuntu"
    if "debian" in normalized:
        return "debian"
    return "centos"
