from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings

from host_management.models import HostGroup, ManagedHost
from security_scanner.models import SecurityScanFinding, SecurityScanHostResult, SecurityScanTask
from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions


def grant_security_scan_permissions(user, *actions):
    ensure_feature_permissions()
    role = Group.objects.create(name=f"security-scan-permissions-{user.id}-{Group.objects.count()}")
    permissions = [Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["securityScan"])]
    permissions.extend(Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("securityScan", action)]) for action in actions)
    role.permissions.add(*permissions)
    user.groups.add(role)


@override_settings(SECURITY_SCAN_RUN_ASYNC=False)
class SecurityScannerApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operator", password="UserPass123")
        self.viewer = get_user_model().objects.create_user(username="viewer", password="UserPass123")
        grant_security_scan_permissions(self.user, "scan", "export", "delete", "refresh")
        self.group = HostGroup.objects.create(name="default")
        self.linux_host = ManagedHost.objects.create(
            name="linux-1",
            group=self.group,
            private_ip="10.0.0.10",
            port=22,
            login_user="root",
            login_password="secret",
            os="ubuntu",
            system_type="ubuntu",
            verified=True,
            verify_status="verified",
        )
        self.windows_host = ManagedHost.objects.create(
            name="windows-1",
            group=self.group,
            private_ip="10.0.0.20",
            port=3389,
            login_user="administrator",
            login_password="secret",
            os="windows",
            system_type="windows",
            verified=True,
            verify_status="verified",
        )
        self.unverified_host = ManagedHost.objects.create(
            name="linux-unverified",
            group=self.group,
            private_ip="10.0.0.30",
            port=22,
            login_user="root",
            login_password="secret",
            os="ubuntu",
            verified=False,
            verify_status="unverified",
        )
        self.client.force_login(self.user)

    def test_scan_hosts_require_permission(self):
        self.client.force_login(self.viewer)

        response = self.client.get("/api/security-scans/hosts/")

        self.assertEqual(response.status_code, 403)

    def test_scan_hosts_include_only_verified_linux_ssh_targets(self):
        response = self.client.get("/api/security-scans/hosts/")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()]
        self.assertEqual(names, ["linux-1"])

    @patch("security_scanner.views.start_security_scan_task")
    def test_create_task_persists_history_and_starts_runner(self, start_task):
        response = self.client.post(
            "/api/security-scans/tasks/",
            data={
                "hostIds": [self.linux_host.id],
                "portsInput": "22,80",
                "enableBaseline": True,
                "enablePortScan": True,
                "enableCveScan": True,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["targetCount"], 1)
        start_task.assert_called_once_with(payload["id"])

    @patch("security_scanner.services.fetch_nvd_cve")
    @patch("security_scanner.services.query_osv_vulnerabilities")
    @patch("security_scanner.services.scan_ports")
    @patch("security_scanner.services.run_remote_command")
    def test_synchronous_task_execution_creates_cve_finding(self, run_command, scan_ports, query_osv, fetch_nvd):
        def command_output(_host, command):
            if "os-release" in command:
                return "ID=ubuntu\nVERSION_ID=22.04\nPRETTY_NAME=Ubuntu 22.04\n"
            if "dpkg-query" in command:
                return "openssl\t1.1.1f-1ubuntu2\n"
            if "ss -tulpen" in command:
                return "tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:((\"sshd\",pid=1,fd=3))\n"
            if "sshd -T" in command:
                return "permitrootlogin yes\npasswordauthentication yes\n"
            if "ufw status" in command:
                return "Status: inactive\n"
            return ""

        run_command.side_effect = command_output
        scan_ports.return_value = {"open_details": [{"port": 22, "service": "SSH", "duration": 12}], "open_ports": [22]}
        query_osv.return_value = [
            {
                "id": "CVE-2024-0001",
                "summary": "OpenSSL test vulnerability",
                "details": "A test vulnerability",
                "affected": [{"ranges": [{"events": [{"fixed": "1.1.1f-1ubuntu3"}]}]}],
                "references": [{"url": "https://example.test/CVE-2024-0001"}],
            }
        ]
        fetch_nvd.return_value = {"cvss": 9.8, "cwe": "CWE-79", "description": "NVD description", "references": ["https://nvd.test/ref"]}

        response = self.client.post(
            "/api/security-scans/tasks/",
            data={
                "hostIds": [self.linux_host.id],
                "portsInput": "22",
                "enableBaseline": True,
                "enablePortScan": True,
                "enableCveScan": True,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        detail = self.client.get(f"/api/security-scans/tasks/{response.json()['id']}/").json()
        self.assertEqual(detail["status"], "completed")
        self.assertEqual(detail["riskCounts"]["critical"], 1)
        findings = self.client.get(f"/api/security-scans/tasks/{response.json()['id']}/findings/").json()["results"]
        cve_finding = next(item for item in findings if item["cveId"] == "CVE-2024-0001")
        self.assertEqual(cve_finding["severity"], "critical")
        self.assertEqual(cve_finding["packageName"], "openssl")
        self.assertEqual(cve_finding["fixedVersion"], "1.1.1f-1ubuntu3")

    @patch("security_scanner.views.start_security_scan_task")
    def test_export_and_delete_task(self, _start_task):
        create_response = self.client.post(
            "/api/security-scans/tasks/",
            data={"hostIds": [self.linux_host.id], "portsInput": "22"},
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        task_id = create_response.json()["id"]
        self.assertTrue(SecurityScanTask.objects.filter(id=task_id).exists())

        csv_response = self.client.get(f"/api/security-scans/tasks/{task_id}/export/?format=csv")
        json_response = self.client.get(f"/api/security-scans/tasks/{task_id}/export/?format=json")
        delete_response = self.client.delete(f"/api/security-scans/tasks/{task_id}/")

        self.assertEqual(csv_response.status_code, 200, csv_response.content.decode("utf-8", errors="replace"))
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(self.client.get(f"/api/security-scans/tasks/{task_id}/").status_code, 404)

    def test_task_detail_does_not_embed_all_findings(self):
        task, _host_result = self.create_task_with_findings(3)

        response = self.client.get(f"/api/security-scans/tasks/{task.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("hostResults", payload)
        self.assertNotIn("findings", payload)

    def test_task_findings_are_paginated_and_compact(self):
        task, _host_result = self.create_task_with_findings(3)

        response = self.client.get(f"/api/security-scans/tasks/{task.id}/findings/?page=1&pageSize=2")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["pageSize"], 2)
        self.assertTrue(payload["hasNext"])
        self.assertEqual(len(payload["results"]), 2)
        self.assertNotIn("raw", payload["results"][0])
        self.assertNotIn("description", payload["results"][0])
        self.assertEqual(payload["results"][0]["hostName"], self.linux_host.name)

    def test_json_export_still_includes_full_findings(self):
        task, _host_result = self.create_task_with_findings(1)

        response = self.client.get(f"/api/security-scans/tasks/{task.id}/export/?format=json")

        self.assertEqual(response.status_code, 200)
        finding = response.json()["task"]["findings"][0]
        self.assertEqual(finding["description"], "heavy description" * 100)
        self.assertIn("raw", finding)

    def create_task_with_findings(self, count):
        task = SecurityScanTask.objects.create(
            name="large security scan",
            created_by=self.user,
            status=SecurityScanTask.STATUS_COMPLETED,
            target_count=1,
            completed_count=1,
            high_count=count,
        )
        host_result = SecurityScanHostResult.objects.create(
            task=task,
            host=self.linux_host,
            host_name=self.linux_host.name,
            host_ip=self.linux_host.private_ip,
            host_port=self.linux_host.port,
            login_user=self.linux_host.login_user,
            os=self.linux_host.os,
            system_type=self.linux_host.system_type,
            status=SecurityScanHostResult.STATUS_COMPLETED,
            high_count=count,
        )
        for index in range(count):
            SecurityScanFinding.objects.create(
                task=task,
                host_result=host_result,
                category="cve",
                severity="high",
                title=f"Finding {index}",
                description="heavy description" * 100,
                evidence="heavy evidence" * 100,
                recommendation="Upgrade the affected package.",
                cve_id=f"CVE-2026-{index:04d}",
                package_name="openssl",
                current_version="1.0",
                fixed_version="1.1",
                source="test",
                references=["https://example.test/finding"],
                raw={"large": "payload" * 100},
            )
        return task, host_result
