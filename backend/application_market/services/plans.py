from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
import shlex

from django.conf import settings

from application_market.models import ApplicationInstallation

from .catalog import get_app
from . import targets

SENSITIVE_RE = re.compile(r"(password|secret|token|key)", re.IGNORECASE)
MARKET_APP_ROOT = "/opt/devops-tools/apps"


def sanitize_config(config: dict, schema: list[dict]) -> dict:
    output = {}
    raw = config if isinstance(config, dict) else {}
    for field in schema:
        key = field["key"]
        value = raw.get(key, field.get("default"))
        if field.get("required") and (value is None or value == ""):
            raise ValueError(f"Missing required config: {key}")
        if field["type"] == "number":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid number config: {key}")
            if field.get("min") is not None and value < int(field["min"]):
                raise ValueError(f"Config value too small: {key}")
            if field.get("max") is not None and value > int(field["max"]):
                raise ValueError(f"Config value too large: {key}")
        elif field["type"] == "boolean":
            value = bool(value)
        else:
            value = str(value or "")
        output[key] = value
    return output


def redact_config(config: dict) -> dict:
    return {key: ("******" if SENSITIVE_RE.search(key) else value) for key, value in config.items()}


def interpolate(value, config: dict):
    if isinstance(value, str):
        for key, item in config.items():
            value = value.replace("${" + key + "}", str(item))
        return value
    if isinstance(value, list):
        return [interpolate(item, config) for item in value]
    if isinstance(value, dict):
        return {key: interpolate(item, config) for key, item in value.items()}
    return value


def market_app_directory(app_id: str) -> str:
    return f"{MARKET_APP_ROOT}/{app_id}"


def action_to_command(action: str, app: dict) -> str:
    project = app["appId"]
    app_dir = market_app_directory(project)
    compose_path = f"{app_dir}/docker-compose.json"
    compose_payload = json.dumps(app["manifest"].get("compose", {}), ensure_ascii=False, sort_keys=True)
    if action in {"install", "update"}:
        return (
            f"mkdir -p {shlex.quote(app_dir)} && "
            f"printf %s {shlex.quote(compose_payload)} > {shlex.quote(compose_path)} && "
            f"docker compose -f {shlex.quote(compose_path)} -p {shlex.quote('opstool-' + project)} up -d"
        )
    if action == "uninstall":
        return f"docker compose -f {shlex.quote(compose_path)} -p {shlex.quote('opstool-' + project)} down"
    if action in {"start", "stop", "restart"}:
        return f"docker compose -f {shlex.quote(compose_path)} -p {shlex.quote('opstool-' + project)} {action}"
    raise ValueError("Unsupported application action")


def canonical_plan(plan: dict) -> str:
    return json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_plan(plan: dict) -> str:
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), canonical_plan(plan).encode("utf-8"), hashlib.sha256).hexdigest()


def build_plan(app_id: str, target_key: str, action: str, config: dict | None = None) -> dict:
    app = get_app(app_id)
    if action not in app["capabilities"]:
        raise ValueError("Application action is not supported")
    key, host = targets.parse_target_key(target_key)
    probe = targets.probe_target(key)
    if probe.get("os") == "windows":
        raise ValueError("Windows hosts are not supported by Docker application market")
    if not probe.get("supported"):
        raise ValueError("Target does not satisfy Docker/Compose requirements")
    normalized_config = sanitize_config(config or {}, app["configSchema"])
    manifest = interpolate(copy.deepcopy(app["manifest"]), normalized_config)
    plan = {
        "appId": app["appId"],
        "appName": app["name"],
        "version": app["version"],
        "action": action,
        "target": key,
        "targetType": ApplicationInstallation.TARGET_LOCAL if host is None else ApplicationInstallation.TARGET_MANAGED_HOST,
        "targetHostId": host.id if host else None,
        "config": redact_config(normalized_config),
        "manifest": manifest,
        "command": action_to_command(action, {**app, "manifest": manifest}),
        "summary": {
            "containers": manifest.get("containers", []),
            "images": manifest.get("images", []),
            "ports": manifest.get("ports", []),
            "directories": [market_app_directory(app["appId"])],
        },
        "warnings": ["Administrator confirmation is required before execution."],
    }
    return plan


def preview_plan(app_id: str, target_key: str, action: str, config: dict | None = None) -> dict:
    plan = build_plan(app_id, target_key, action, config)
    return {**plan, "planDigest": digest_plan(plan)}


def assert_digest(plan: dict, digest: str) -> None:
    if not digest or not hmac.compare_digest(digest_plan(plan), str(digest)):
        raise ValueError("Application plan has changed; please preview again")
