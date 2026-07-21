from django.test import TestCase

from .models import HostGroup, ManagedHost


class HostTableImportTests(TestCase):
    def test_import_host_table_payload_uses_defaults_and_skips_duplicates(self):
        group = HostGroup.objects.create(name="default", sort_order=10)
        existing = ManagedHost.objects.create(
            name="host-keep",
            group=group,
            private_ip="10.0.0.9",
            port=2200,
            remark="keep me",
            os="centos",
            verified=True,
            verify_status="verified",
            machine_name="existing-machine",
            cpu=8,
            memory=16,
        )

        response = self.client.post(
            "/api/host-management/import/",
            data={
                "version": 1,
                "importMode": "host-table",
                "groups": [],
                "credentials": [],
                "hosts": [
                    {
                        "groupPath": "",
                        "name": "host-new",
                        "privateIp": "10.0.0.10",
                        "platformType": "",
                        "port": "",
                        "remark": "",
                        "machineName": "must-not-import",
                        "systemArch": "must-not-import",
                        "systemType": "must-not-import",
                        "cpu": 64,
                        "memory": 128,
                        "verified": True,
                        "verifyStatus": "verified",
                    },
                    {
                        "groupPath": "default",
                        "name": "host-keep",
                        "privateIp": "10.0.0.9",
                        "platformType": "windows",
                        "port": 3389,
                        "remark": "should not overwrite",
                    },
                    {"groupPath": "default", "name": "", "privateIp": "10.0.0.11"},
                    {"groupPath": "default", "name": "host-no-ip", "privateIp": ""},
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["imported"]["hosts"], 1)
        self.assertEqual(payload["skipped"]["hosts"], 3)

        new_host = ManagedHost.objects.get(name="host-new")
        self.assertEqual(new_host.group.name, "default")
        self.assertEqual(str(new_host.private_ip), "10.0.0.10")
        self.assertEqual(new_host.port, 22)
        self.assertEqual(new_host.os, "centos")
        self.assertFalse(new_host.verified)
        self.assertEqual(new_host.verify_status, "unverified")
        self.assertEqual(new_host.machine_name, "")
        self.assertEqual(new_host.system_arch, "")
        self.assertEqual(new_host.system_type, "")
        self.assertEqual(new_host.cpu, 2)
        self.assertEqual(new_host.memory, 4)

        existing.refresh_from_db()
        self.assertEqual(existing.port, 2200)
        self.assertEqual(existing.remark, "keep me")
        self.assertEqual(existing.os, "centos")
        self.assertTrue(existing.verified)
        self.assertEqual(existing.machine_name, "existing-machine")

    def test_import_host_table_payload_defaults_invalid_port(self):
        response = self.client.post(
            "/api/host-management/import/",
            data={
                "version": 1,
                "importMode": "host-table",
                "groups": [],
                "credentials": [],
                "hosts": [
                    {
                        "groupPath": "default",
                        "name": "host-invalid-port",
                        "privateIp": "10.0.0.20",
                        "platformType": "linux",
                        "port": "ssh",
                    }
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["imported"]["hosts"], 1)
        self.assertEqual(ManagedHost.objects.get(name="host-invalid-port").port, 22)
