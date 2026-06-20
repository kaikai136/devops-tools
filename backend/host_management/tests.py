from django.test import TestCase

from web_terminal.services import TerminalConnectionError

from .models import HostGroup, ManagedHost
from .probe import verify_host


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

        with self.patch_probe({"machine_name": "prod-api-01", "cpu": 4, "memory": 8, "os": "ubuntu"}):
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
