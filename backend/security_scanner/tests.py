from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings

from host_management.models import HostGroup, ManagedHost
from security_scanner.models import ScanFinding, ScanTargetResult, ScanTask, VulnerabilityCache
from system_management.models import SystemSetting
from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions


def grant_security_scan_permissions(user, *actions):
    ensure_feature_permissions()
    role = Group.objects.create(name=f"security-scan-permissions-{user.id}-{Group.objects.count()}")
    permissions = [Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["securityScan"])]
    permissions.extend(Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("securityScan", action)]) for action in actions)
    role.permissions.add(*permissions)
    user.groups.add(role)


@override_settings(SECURITY_SCAN_RUN_ASYNC=False)
class SecurityScannerRedesignApiTests(TestCase):
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
            system_arch="x86_64",
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
        self.client.force_login(self.user)

    def test_targets_require_security_scan_permission(self):
        self.client.force_login(self.viewer)

        response = self.client.get("/api/security-scans/targets/")

        self.assertEqual(response.status_code, 403)

    def test_targets_include_only_verified_linux_ssh_hosts(self):
        response = self.client.get("/api/security-scans/targets/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.json()], ["linux-1"])
        self.assertEqual(response.json()[0]["privateIp"], "10.0.0.10")

    @patch("security_scanner.views.start_security_scan_task")
    def test_create_task_persists_targets_and_uses_new_contract(self, start_task):
        response = self.client.post(
            "/api/security-scans/tasks/",
            data={
                "targetIds": [self.linux_host.id],
                "portsInput": "22,80",
                "scanModules": {"baseline": True, "ports": True, "cve": False},
                "name": "巡检一",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["name"], "巡检一")
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["targetCount"], 1)
        self.assertEqual(payload["scanModules"], {"baseline": True, "ports": True, "cve": False})
        start_task.assert_called_once_with(payload["id"], retry_target_ids=None)
        target = ScanTargetResult.objects.get(task_id=payload["id"])
        self.assertEqual(target.host_name, "linux-1")
        self.assertEqual(target.status, ScanTargetResult.STATUS_PENDING)

    @patch("security_scanner.services.post_json")
    @patch("security_scanner.services.fetch_nvd_cve")
    @patch("security_scanner.services.scan_ports")
    @patch("security_scanner.services.run_remote_command")
    def test_run_scan_respects_cve_setting_and_caches_vulnerabilities(self, run_command, scan_ports, fetch_nvd, post_json):
        SystemSetting.objects.create(key="security_scan", value={"onlineCveEnabled": True})

        def command_output(_host, command):
            if "os-release" in command:
                return "ID=ubuntu\nVERSION_ID=22.04\nPRETTY_NAME=Ubuntu 22.04\n__UNAME__\nLinux test 6.8\n"
            if "dpkg-query" in command:
                return "openssl\t1.1.1f-1ubuntu2\n"
            if "sshd -T" in command:
                return "permitrootlogin yes\npasswordauthentication yes\n"
            if "ufw status" in command:
                return "Status: inactive\n"
            if "NOPASSWD" in command:
                return ""
            return ""

        run_command.side_effect = command_output
        scan_ports.return_value = {"open_details": [{"port": 22, "service": "SSH", "duration": 12}], "open_ports": [22]}
        post_json.return_value = {
            "results": [
                {
                    "package": {"name": "openssl"},
                    "vulns": [
                        {
                            "id": "CVE-2024-0001",
                            "summary": "OpenSSL test vulnerability",
                            "details": "A test vulnerability",
                            "affected": [{"ranges": [{"events": [{"fixed": "1.1.1f-1ubuntu3"}]}]}],
                            "references": [{"url": "https://example.test/CVE-2024-0001"}],
                        }
                    ],
                }
            ]
        }
        fetch_nvd.return_value = {"cvss": 9.8, "cwe": "CWE-79", "description": "NVD description", "references": ["https://nvd.test/ref"]}

        response = self.client.post(
            "/api/security-scans/tasks/",
            data={
                "targetIds": [self.linux_host.id],
                "portsInput": "22",
                "scanModules": {"baseline": True, "ports": True, "cve": True},
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        detail = self.client.get(f"/api/security-scans/tasks/{response.json()['id']}/").json()
        self.assertEqual(detail["status"], "completed")
        self.assertEqual(detail["riskCounts"]["critical"], 1)
        self.assertTrue(detail["vulnerabilitySource"]["onlineCveEnabled"])
        cve_finding = ScanFinding.objects.get(task_id=response.json()["id"], cve_id="CVE-2024-0001")
        self.assertEqual(cve_finding.severity, "critical")
        self.assertEqual(cve_finding.package_name, "openssl")
        self.assertTrue(VulnerabilityCache.objects.filter(source=VulnerabilityCache.SOURCE_OSV_BATCH).exists())

    @patch("security_scanner.services.post_json")
    @patch("security_scanner.services.scan_ports")
    @patch("security_scanner.services.run_remote_command")
    def test_cve_module_is_skipped_when_online_source_is_disabled(self, run_command, scan_ports, post_json):
        def command_output(_host, command):
            if "os-release" in command:
                return "ID=ubuntu\nVERSION_ID=22.04\nPRETTY_NAME=Ubuntu 22.04\n__UNAME__\nLinux test 6.8\n"
            if "sshd -T" in command:
                return ""
            if "ufw status" in command:
                return "Status: active\n"
            if "NOPASSWD" in command:
                return ""
            return ""

        run_command.side_effect = command_output
        scan_ports.return_value = {"open_details": [], "open_ports": []}

        response = self.client.post(
            "/api/security-scans/tasks/",
            data={"targetIds": [self.linux_host.id], "portsInput": "22", "scanModules": {"baseline": True, "ports": True, "cve": True}},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        post_json.assert_not_called()
        target = ScanTargetResult.objects.get(task_id=response.json()["id"])
        self.assertIn("cve", target.skipped_modules)

    @patch("security_scanner.views.start_security_scan_task")
    def test_cancel_and_retry_failed_targets(self, start_task):
        task = ScanTask.objects.create(name="running", created_by=self.user, status=ScanTask.STATUS_RUNNING, target_count=2)
        failed_target = ScanTargetResult.objects.create(
            task=task,
            host=self.linux_host,
            host_name="linux-1",
            host_ip="10.0.0.10",
            host_port=22,
            login_user="root",
            status=ScanTargetResult.STATUS_FAILED,
            error="ssh failed",
        )
        ScanTargetResult.objects.create(task=task, host_name="linux-2", host_ip="10.0.0.11", host_port=22, status=ScanTargetResult.STATUS_COMPLETED)

        cancel_response = self.client.post(f"/api/security-scans/tasks/{task.id}/cancel/")
        retry_response = self.client.post(f"/api/security-scans/tasks/{task.id}/retry-failed/")

        self.assertEqual(cancel_response.status_code, 200)
        self.assertTrue(cancel_response.json()["cancelRequested"])
        self.assertEqual(retry_response.status_code, 200)
        start_task.assert_called_once_with(task.id, retry_target_ids=[failed_target.id])
        failed_target.refresh_from_db()
        self.assertEqual(failed_target.status, ScanTargetResult.STATUS_PENDING)

    def test_findings_filtering_and_exports(self):
        task = ScanTask.objects.create(name="report", created_by=self.user, status=ScanTask.STATUS_COMPLETED, target_count=1, completed_count=1, high_count=1)
        target = ScanTargetResult.objects.create(
            task=task,
            host=self.linux_host,
            host_name="linux-1",
            host_ip="10.0.0.10",
            host_port=22,
            login_user="root",
            status=ScanTargetResult.STATUS_COMPLETED,
            high_count=1,
        )
        ScanFinding.objects.create(
            task=task,
            target_result=target,
            category="baseline",
            severity="high",
            title="SSH 允许 root 登录",
            description="root login",
            evidence="permitrootlogin yes",
            recommendation="关闭 PermitRootLogin",
            source="baseline",
        )

        findings_response = self.client.get(f"/api/security-scans/tasks/{task.id}/findings/?severity=high&keyword=root")
        csv_response = self.client.get(f"/api/security-scans/tasks/{task.id}/export/?format=csv")
        json_response = self.client.get(f"/api/security-scans/tasks/{task.id}/export/?format=json")

        self.assertEqual(findings_response.status_code, 200)
        self.assertEqual(findings_response.json()["total"], 1)
        self.assertEqual(findings_response.json()["results"][0]["targetName"], "linux-1")
        self.assertEqual(csv_response.status_code, 200)
        self.assertTrue(csv_response.content.decode("utf-8").startswith("\ufeff"))
        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(json_response.json()["task"]["findings"][0]["title"], "SSH 允许 root 登录")
