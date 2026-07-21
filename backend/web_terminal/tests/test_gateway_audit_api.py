from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings

from host_management.models import HostGroup, ManagedHost
from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions
from web_terminal.models import TerminalSession


class SshGatewayAuditApiTests(TestCase):
    def setUp(self):
        ensure_feature_permissions()
        self.user = get_user_model().objects.create_user(username="operator", password="UserPass123")
        self.user.user_permissions.add(Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["hosts"]))
        for key in [("hosts", "terminal"), ("hosts", "session_audit")]:
            self.user.user_permissions.add(Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[key]))
        self.client.force_login(self.user)
        group = HostGroup.objects.create(name="gateway")
        self.host = ManagedHost.objects.create(name="api-01", group=group, private_ip="10.0.0.8", login_user="root")

    def test_record_file_audit_persists_gateway_file_operation(self):
        from web_terminal.gateway.audit import record_file_audit
        from web_terminal.models import TerminalFileAudit

        session = TerminalSession.objects.create(host=self.host, user=self.user, username=self.user.username, entrypoint="ssh_gateway")
        audit = record_file_audit(
            operation="write",
            host=self.host,
            user=self.user,
            session=session,
            path="/tmp/upload.txt",
            size=12,
            protocol="sftp",
            status="success",
        )

        saved = TerminalFileAudit.objects.get(id=audit.id)
        self.assertEqual(saved.username, "operator")
        self.assertEqual(saved.operation, "write")
        self.assertEqual(saved.path, "/tmp/upload.txt")
        self.assertEqual(saved.size, 12)
        self.assertEqual(saved.session_id, session.id)

    @override_settings(SSH_GATEWAY_PUBLIC_HOST="ops.example.com", SSH_GATEWAY_PUBLIC_PORT=22022)
    def test_connection_info_api_returns_commands_for_authenticated_user(self):
        response = self.client.get(f"/api/web-terminal/ssh-gateway/connection-info/?host={self.host.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["commands"]["sshDirect"], f"ssh -p 22022 operator#{self.host.id}@ops.example.com")
        self.assertEqual(payload["host"]["id"], self.host.id)

    def test_file_audits_api_filters_by_operation_and_host(self):
        from web_terminal.gateway.audit import record_file_audit

        other = ManagedHost.objects.create(name="api-02", group=self.host.group, private_ip="10.0.0.9", login_user="root")
        record_file_audit(operation="read", host=self.host, user=self.user, path="/etc/hosts", protocol="scp")
        record_file_audit(operation="write", host=other, user=self.user, path="/tmp/x", protocol="sftp")

        response = self.client.get(f"/api/web-terminal/file-audits/?operation=read&host={self.host.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["operation"], "read")
        self.assertEqual(payload["results"][0]["path"], "/etc/hosts")
