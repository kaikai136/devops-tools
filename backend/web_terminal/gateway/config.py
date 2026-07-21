from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class SshGatewayConfig:
    enabled: bool
    bind_host: str
    port: int
    public_host: str
    public_port: int
    host_key_path: Path


def gateway_config(request=None) -> SshGatewayConfig:
    public_host = str(getattr(settings, "SSH_GATEWAY_PUBLIC_HOST", "") or "").strip()
    if not public_host and request is not None:
        public_host = request_host_without_port(request)
    return SshGatewayConfig(
        enabled=bool(getattr(settings, "SSH_GATEWAY_ENABLED", True)),
        bind_host=str(getattr(settings, "SSH_GATEWAY_BIND_HOST", "0.0.0.0") or "0.0.0.0"),
        port=positive_port(getattr(settings, "SSH_GATEWAY_PORT", 2222), 2222),
        public_host=public_host or "127.0.0.1",
        public_port=positive_port(
            getattr(settings, "SSH_GATEWAY_PUBLIC_PORT", getattr(settings, "SSH_GATEWAY_PORT", 2222)),
            2222,
        ),
        host_key_path=Path(getattr(settings, "SSH_GATEWAY_HOST_KEY_PATH", Path(settings.BASE_DIR) / "data" / "ssh-gateway-host-key")),
    )


def gateway_connection_info(username: str, host_id: int | None = None, request=None) -> dict:
    config = gateway_config(request=request)
    username = shell_token(username)
    host_part = f"{username}#{int(host_id)}" if host_id else username
    public_target = f"{config.public_host}"
    return {
        "enabled": config.enabled,
        "listen": {"host": config.bind_host, "port": config.port},
        "public": {"host": config.public_host, "port": config.public_port},
        "hostKeyPath": str(config.host_key_path),
        "commands": {
            "sshMenu": f"ssh -p {config.public_port} {username}@{public_target}",
            "sshDirect": f"ssh -p {config.public_port} {host_part}@{public_target}",
            "sftpMenu": f"sftp -P {config.public_port} {username}@{public_target}",
            "sftpDirect": f"sftp -P {config.public_port} {host_part}@{public_target}",
            "scpUpload": f"scp -P {config.public_port} ./local-file {host_part}@{public_target}:/tmp/",
            "scpDownload": f"scp -P {config.public_port} {host_part}@{public_target}:/tmp/remote-file ./",
        },
    }


def positive_port(value, default: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    return port if 1 <= port <= 65535 else default


def request_host_without_port(request) -> str:
    host = request.get_host().strip()
    if host.startswith("[") and "]" in host:
        return host[1 : host.index("]")]
    return host.rsplit(":", 1)[0] if ":" in host else host


def shell_token(value: str) -> str:
    return str(value or "").strip().replace(" ", "")
