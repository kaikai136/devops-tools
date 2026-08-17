from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from application_market.models import ApplicationDefinition, ApplicationInstallation

from .sources import normalize_app_definition

BUILTIN_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "builtin_catalog.json"


@lru_cache(maxsize=1)
def builtin_catalog() -> list[dict]:
    payload = json.loads(BUILTIN_CATALOG_PATH.read_text(encoding="utf-8"))
    return [normalize_app_definition(item, source="builtin") for item in payload]


def remote_catalog() -> list[dict]:
    apps = []
    for definition in ApplicationDefinition.objects.filter(enabled=True).exclude(source="builtin"):
        apps.append(
            normalize_app_definition(
                {
                    "appId": definition.app_id,
                    "name": definition.name,
                    "category": definition.category,
                    "description": definition.description,
                    "icon": definition.icon,
                    "version": definition.version,
                    "source": definition.source,
                    "installMode": definition.install_mode,
                    "requirements": definition.requirements,
                    "configSchema": definition.config_schema,
                    "manifest": definition.manifest,
                    "capabilities": definition.capabilities,
                },
                source=definition.source,
            )
        )
    return apps


def load_catalog(target_key: str | None = None) -> list[dict]:
    merged: dict[str, dict] = {}
    for app in remote_catalog():
        merged.setdefault(app["appId"], app)
    for app in builtin_catalog():
        merged[app["appId"]] = app

    installed = {}
    if target_key:
        installed = {
            item.app_id: item
            for item in ApplicationInstallation.objects.filter(target_key=target_key)
        }

    apps = []
    for app in sorted(merged.values(), key=lambda item: (item["category"], item["name"])):
        installation = installed.get(app["appId"])
        payload = app.copy()
        payload["installed"] = bool(installation)
        payload["status"] = installation.status if installation else "not_installed"
        apps.append(payload)
    return apps


def get_app(app_id: str) -> dict:
    for app in load_catalog():
        if app["appId"] == app_id:
            return app
    raise ValueError("Application not found")
