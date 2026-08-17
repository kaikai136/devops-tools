from __future__ import annotations

import json
import platform
import shutil
import subprocess

from host_management.models import ManagedHost
from web_terminal.services.commands import run_one_shot_ssh_command

LOCAL_TARGET_KEY = "local"


def parse_target_key(value: str) -> tuple[str, ManagedHost | None]:
    target = str(value or LOCAL_TARGET_KEY).strip()
    if target == LOCAL_TARGET_KEY:
        return LOCAL_TARGET_KEY, None
    if target.startswith("host:"):
        host_id = int(target.split(":", 1)[1])
        return target, ManagedHost.objects.get(id=host_id)
    raise ValueError("Invalid target")


def list_targets() -> list[dict]:
    items = [target_payload(LOCAL_TARGET_KEY, None)]
    for host in ManagedHost.objects.select_related("group").all():
        items.append(target_payload(f"host:{host.id}", host))
    return items


def target_payload(target_key: str, host: ManagedHost | None) -> dict:
    if host is None:
        return {
            "id": LOCAL_TARGET_KEY,
            "type": "local",
            "name": "Current host",
            "ip": "127.0.0.1",
            "os": "linux" if platform.system().lower() != "windows" else "windows",
            "supported": platform.system().lower() != "windows",
        }
    return {
        "id": target_key,
        "type": "managed_host",
        "hostId": host.id,
        "name": host.name,
        "ip": str(host.private_ip),
        "os": host.os,
        "supported": host.os != "windows" and host.verified and host.verify_status == "verified" and bool(host.login_user),
    }


def run_local_command(command: str) -> tuple[int, str, str]:
    completed = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=30)
    return completed.returncode, completed.stdout, completed.stderr


def run_target_command(target_key: str, command: str) -> tuple[int, str, str]:
    key, host = parse_target_key(target_key)
    if key == LOCAL_TARGET_KEY:
        return run_local_command(command)
    assert host is not None
    try:
        return 0, run_one_shot_ssh_command(host, command), ""
    except Exception as error:
        return 1, "", str(error)


def probe_target(target_key: str) -> dict:
    key, host = parse_target_key(target_key)
    payload = target_payload(key, host)
    if payload["os"] == "windows":
        payload.update({"docker": False, "compose": False, "supported": False, "reason": "Windows hosts are not supported by Docker application market"})
        return payload
    docker_code, docker_out, docker_err = run_target_command(target_key, "docker --version")
    compose_code, compose_out, _ = run_target_command(target_key, "docker compose version --short")
    ps_code, ps_out, _ = run_target_command(target_key, "docker ps --format '{{json .}}'")
    containers = []
    if ps_code == 0:
        for line in ps_out.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            containers.append({"name": item.get("Names", ""), "image": item.get("Image", ""), "status": item.get("Status", ""), "ports": item.get("Ports", "")})
    payload.update(
        {
            "docker": docker_code == 0,
            "dockerVersion": (docker_out or docker_err).strip(),
            "compose": compose_code == 0,
            "composeVersion": compose_out.strip(),
            "diskFree": shutil.disk_usage(".").free if key == LOCAL_TARGET_KEY else None,
            "containers": containers,
            "ports": [item["ports"] for item in containers if item.get("ports")],
            "supported": docker_code == 0 and compose_code == 0,
        }
    )
    return payload
