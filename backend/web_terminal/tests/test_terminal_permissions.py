from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from host_management.models import HostGroup, ManagedHost
from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions
from web_terminal.models import TerminalSession


def grant_terminal_permission(user):
    role = Group.objects.create(name=f"terminal-permission-{user.id}")
    role.permissions.add(
        Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["hosts"]),
        Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("hosts", "terminal")]),
    )
    user.groups.add(role)


class TerminalPermissionApiTests(TestCase):
    def setUp(self):
        ensure_feature_permissions()
        self.user = get_user_model().objects.create_user(username="terminal-user", password="pass")
        self.group = HostGroup.objects.create(name="terminal-permission-tests")
        self.host = ManagedHost.objects.create(name="terminal-host", group=self.group, private_ip="10.0.0.8", login_user="root")
        self.session = TerminalSession.objects.create(host=self.host, transcript="")
        self.client.force_login(self.user)

    def test_terminal_tree_requires_hosts_terminal_permission(self):
        response = self.client.get("/api/web-terminal/tree/")

        self.assertEqual(response.status_code, 403)

    def test_terminal_tree_allows_hosts_terminal_permission(self):
        grant_terminal_permission(self.user)

        response = self.client.get("/api/web-terminal/tree/")

        self.assertEqual(response.status_code, 200)

    def test_terminal_session_creation_requires_hosts_terminal_permission_before_connecting(self):
        with patch("web_terminal.api.sessions.create_terminal_session") as create_session:
            response = self.client.post(
                "/api/web-terminal/sessions/",
                data={"host": self.host.id},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        create_session.assert_not_called()

    def test_terminal_commands_require_hosts_terminal_permission(self):
        with patch("web_terminal.api.sessions.run_session_command") as run_command:
            response = self.client.post(
                f"/api/web-terminal/sessions/{self.session.session_id}/commands/",
                data={"command": "whoami"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        run_command.assert_not_called()

    def test_terminal_monitor_requires_hosts_terminal_permission(self):
        with patch("web_terminal.api.monitoring.get_remote_resource_monitor") as monitor:
            response = self.client.post(
                f"/api/web-terminal/hosts/{self.host.id}/monitor/",
                data={},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        monitor.assert_not_called()

    def test_terminal_file_list_requires_hosts_terminal_permission(self):
        with patch("web_terminal.api.files.list_remote_directory") as list_directory:
            response = self.client.post(
                f"/api/web-terminal/hosts/{self.host.id}/files/list/",
                data={"path": "."},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        list_directory.assert_not_called()
