from importlib import import_module

from django.db import migrations
from django.test import SimpleTestCase, TestCase

from web_terminal.services import TerminalConnectionError

from .models import HostCredential, HostGroup, ManagedHost
from .probe import verify_host


class HostInitialMigrationTests(SimpleTestCase):
    def test_initial_migration_does_not_seed_demo_hosts(self):
        migration_module = import_module("host_management.migrations.0001_initial")

        seed_operations = [operation for operation in migration_module.Migration.operations if isinstance(operation, migrations.RunPython)]

        self.assertEqual(seed_operations, [])


class HostVerifyTests(TestCase):
    def setUp(self):
        self.group = HostGroup.objects.create(name="verify-tests", sort_order=10)

    def test_verify_host_updates_machine_config_on_success(self):
        host = ManagedHost.objects.create(
            name="success-host",
            group=self.group,
            private_ip="10.10.10.10",
            login_user="root",
            cpu=0,
            memory=0,
            verified=False,
        )

        with self.patch_probe(
            {
                "machine_name": "prod-api-01",
                "cpu": 4,
                "memory": 8,
                "os": "ubuntu",
                "system_arch": "x86_64",
                "system_type": "ubuntu",
            }
        ):
            updated, error = verify_host(host)

        self.assertIsNone(error)
        self.assertTrue(updated.verified)
        self.assertEqual(updated.verify_status, "verified")
        self.assertEqual(updated.machine_name, "prod-api-01")
        self.assertEqual(updated.cpu, 4)
        self.assertEqual(updated.memory, 8)
        self.assertEqual(updated.os, "ubuntu")

    def test_verify_host_clears_machine_config_on_failure(self):
        host = ManagedHost.objects.create(
            name="failed-host",
            group=self.group,
            private_ip="10.10.10.11",
            login_user="root",
            cpu=2,
            memory=4,
            machine_name="old-hostname",
            verified=True,
            verify_status="verified",
        )

        with self.patch_probe(TerminalConnectionError("ssh failed")):
            updated, error = verify_host(host)

        self.assertEqual(error, "ssh failed")
        self.assertFalse(updated.verified)
        self.assertEqual(updated.verify_status, "failed")
        self.assertEqual(updated.machine_name, "")
        self.assertEqual(updated.cpu, 0)
        self.assertEqual(updated.memory, 0)

    def patch_probe(self, result):
        from unittest.mock import patch

        if isinstance(result, Exception):
            return patch("host_management.probe.probe_host_info", side_effect=result)
        return patch("host_management.probe.probe_host_info", return_value=result)


class HostImportExportTests(TestCase):
    def test_export_host_management_payload(self):
        group = HostGroup.objects.create(name="prod", sort_order=10)
        HostCredential.objects.create(name="root账号", username="root", password="secret", port=22)
        ManagedHost.objects.create(name="api-01", group=group, private_ip="10.0.0.1", public_ip="1.1.1.1", login_user="root")

        response = self.client.get("/api/host-management/export/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 1)
        self.assertTrue(any(item["path"] == "prod" for item in payload["groups"]))
        self.assertTrue(any(item["privateIp"] == "10.0.0.1" for item in payload["hosts"]))
        self.assertTrue(any(item["name"] == "root账号" for item in payload["credentials"]))

    def test_import_host_management_payload(self):
        response = self.client.post(
            "/api/host-management/import/",
            data={
                "version": 1,
                "groups": [{"name": "prod", "path": "prod/zone-a", "sortOrder": 20}],
                "credentials": [{"name": "root账号", "username": "root", "password": "secret", "port": 22}],
                "hosts": [
                    {
                        "name": "api-01",
                        "groupPath": "prod/zone-a",
                        "privateIp": "10.0.0.2",
                        "publicIp": "1.1.1.2",
                        "port": 22,
                        "loginUser": "root",
                        "os": "centos",
                    }
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["imported"]["hosts"], 1)
        self.assertTrue(HostGroup.objects.filter(name="zone-a", parent__name="prod").exists())
        self.assertTrue(HostCredential.objects.filter(name="root账号", username="root").exists())
        self.assertTrue(ManagedHost.objects.filter(private_ip="10.0.0.2", group__name="zone-a").exists())
