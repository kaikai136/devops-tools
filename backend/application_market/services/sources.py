from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.utils import timezone

from application_market.models import ApplicationDefinition, ApplicationSource

DISALLOWED_KEYS = {"script", "command", "shell", "installScript", "uninstallScript", "function", "exec", "args"}
SAFE_APP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,118}[a-z0-9]$")
SAFE_CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,78}[a-z0-9]$")
MAX_REMOTE_BYTES = 512_000


def reject_disallowed_keys(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in DISALLOWED_KEYS:
                raise ValueError(f"Remote app contains disallowed field: {key}")
            reject_disallowed_keys(item)
    elif isinstance(value, list):
        for item in value:
            reject_disallowed_keys(item)


def require_text(value, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Missing application field: {field}")
    return text[:max_length]


def normalize_config_schema(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]{0,63}$", key):
            raise ValueError("Invalid config field key")
        field_type = str(item.get("type", "text")).strip()
        if field_type not in {"text", "number", "password", "select", "boolean"}:
            raise ValueError("Invalid config field type")
        normalized.append(
            {
                "key": key,
                "label": str(item.get("label") or key)[:80],
                "type": field_type,
                "required": bool(item.get("required", False)),
                "default": item.get("default"),
                "min": item.get("min"),
                "max": item.get("max"),
                "options": item.get("options") if isinstance(item.get("options"), list) else [],
            }
        )
    return normalized


def normalize_app_definition(raw: dict, *, source: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Application definition must be an object")
    reject_disallowed_keys(raw)
    app_id = require_text(raw.get("appId") or raw.get("id"), "appId", 120).lower()
    category = require_text(raw.get("category"), "category", 80).lower()
    if not SAFE_APP_ID_RE.match(app_id):
        raise ValueError("Invalid application id")
    if not SAFE_CATEGORY_RE.match(category):
        raise ValueError("Invalid application category")
    install_mode = str(raw.get("installMode") or raw.get("install_mode") or "compose").strip()
    if install_mode != "compose":
        raise ValueError("Only compose applications are supported")
    requirements = raw.get("requirements") if isinstance(raw.get("requirements"), dict) else {}
    manifest = raw.get("manifest") if isinstance(raw.get("manifest"), dict) else {}
    if not isinstance(manifest.get("compose", {}), dict):
        raise ValueError("Invalid compose manifest")
    capabilities = raw.get("capabilities") if isinstance(raw.get("capabilities"), list) else ["install"]
    capabilities = [str(item) for item in capabilities if str(item) in {"install", "update", "uninstall", "start", "stop", "restart"}]
    return {
        "appId": app_id,
        "name": require_text(raw.get("name"), "name", 160),
        "category": category,
        "description": str(raw.get("description") or "")[:1000],
        "icon": str(raw.get("icon") or "")[:200],
        "version": str(raw.get("version") or "1.0.0")[:80],
        "source": source,
        "installMode": install_mode,
        "requirements": requirements,
        "configSchema": normalize_config_schema(raw.get("configSchema") or raw.get("config_schema") or []),
        "manifest": manifest,
        "capabilities": capabilities or ["install"],
    }


def normalize_remote_catalog(payload) -> list[dict]:
    items = payload.get("apps") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("Remote catalog must be a list or an object with apps")
    seen = set()
    normalized = []
    for item in items:
        app = normalize_app_definition(item, source="remote")
        if app["appId"] in seen:
            raise ValueError("Duplicate application id in remote catalog")
        seen.add(app["appId"])
        normalized.append(app)
    return normalized


def fetch_remote_json(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only HTTP/HTTPS remote sources are supported")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read(MAX_REMOTE_BYTES + 1)
    if len(data) > MAX_REMOTE_BYTES:
        raise ValueError("Remote catalog is too large")
    return json.loads(data.decode("utf-8"))


def checksum_definition(app: dict) -> str:
    encoded = json.dumps(app, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sync_remote_source(source: ApplicationSource) -> dict:
    if not source.url:
        raise ValueError("Remote source URL is required")
    try:
        payload = fetch_remote_json(source.url)
        apps = normalize_remote_catalog(payload)
        source.cached_payload = apps
        source.last_error = ""
        source.last_synced_at = timezone.now()
        source.save(update_fields=["cached_payload", "last_error", "last_synced_at", "updated_at"])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        source.last_error = str(error)
        source.save(update_fields=["last_error", "updated_at"])
        apps = normalize_remote_catalog(source.cached_payload or [])
    upsert_remote_definitions(apps, source_name=source.name)
    return {"synced": len(apps), "source": source.name, "error": source.last_error}


def sync_enabled_remote_sources() -> list[dict]:
    return [sync_remote_source(source) for source in ApplicationSource.objects.filter(enabled=True, source_type=ApplicationSource.SOURCE_REMOTE)]


def upsert_remote_definitions(apps: list[dict], *, source_name: str) -> None:
    for app in apps:
        ApplicationDefinition.objects.update_or_create(
            source=source_name,
            app_id=app["appId"],
            defaults={
                "name": app["name"],
                "category": app["category"],
                "description": app["description"],
                "icon": app["icon"],
                "version": app["version"],
                "install_mode": app["installMode"],
                "requirements": app["requirements"],
                "config_schema": app["configSchema"],
                "manifest": app["manifest"],
                "capabilities": app["capabilities"],
                "checksum": checksum_definition(app),
                "enabled": True,
            },
        )
