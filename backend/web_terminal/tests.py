from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, SimpleTestCase, TestCase
from unittest.mock import patch

from accounts.models import UserProfile
from host_management.models import HostGroup, ManagedHost
from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions

from . import views
from .consumers import (
    CWD_HOOK_ECHO_OFF,
    CWD_HOOK_ECHO_ON,
    CWD_HOOK_INSTALL_SCRIPT,
    CWD_HOOK_SCRIPT,
    CWD_MARKER_END,
    CWD_MARKER_START,
    TerminalConsumer,
    command_buffer_after_input,
    filter_changed_cwd_paths,
    strip_cwd_markers,
    strip_cwd_hook_install_echo,
    strip_cwd_markers_with_pending,
)
from .services import (
    TerminalConnectionError,
    classify_command_risk,
    create_remote_directory,
    create_remote_file,
    create_remote_symlink,
    initialize_session_recording,
    parse_monitor_disks,
    parse_monitor_memory,
    parse_monitor_network,
    parse_monitor_network_rates,
    parse_remote_resource_monitor_output,
    normalize_remote_relative_file_path,
    normalize_remote_symlink_target,
    normalize_remote_file_octal_mode,
    normalize_remote_file_owner,
    parse_remote_stat_output,
    remote_file_properties_payload,
)
from .models import TerminalCommandAudit, TerminalQuickCommand, TerminalSession


class RemoteFilePropertiesTests(SimpleTestCase):
    monitor_output = """SECTION:system
hostname=VM-0-23-centos
arch=x86_64
kernel=Linux 5.10
os=CentOS Linux 7
uptime=39450240.00
SECTION:cpu1
cpu  100 0 50 850 0 0 0 0 0 0
cpu0 50 0 20 430 0 0 0 0 0 0
cpu1 50 0 30 420 0 0 0 0 0 0
SECTION:load
0.13 0.06 0.06 1/123 456
SECTION:cpu2
cpu  120 0 60 920 0 0 0 0 0 0
cpu0 60 0 25 465 0 0 0 0 0 0
cpu1 60 0 35 455 0 0 0 0 0 0
SECTION:mem
MemTotal:        7780432 kB
MemFree:         6800000 kB
MemAvailable:   6800000 kB
Buffers:          100000 kB
Cached:           600000 kB
SReclaimable:      50000 kB
SECTION:net1
Inter-|   Receive                                                |  Transmit
 eth0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0
 lo: 1 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0
SECTION:net2
Inter-|   Receive                                                |  Transmit
 eth0: 7800 0 0 0 0 0 0 0 5200 0 0 0 0 0 0 0
SECTION:df
Filesystem Type 1B-blocks Used Available Use% Mounted on
/dev/vda1 ext4 42949672960 10737418240 32212254720 25% /
tmpfs tmpfs 1000 1 999 1% /run
/dev/vdb1 xfs 107374182400 53687091200 53687091200 50% /data
"""

    def test_strip_cwd_markers_extracts_path_and_keeps_visible_output(self):
        output, paths = strip_cwd_markers(f"before{CWD_MARKER_START}/opt{CWD_MARKER_END}after")

        self.assertEqual(output, "beforeafter")
        self.assertEqual(paths, ["/opt"])

    def test_strip_cwd_markers_supports_multiple_paths(self):
        output, paths = strip_cwd_markers(
            f"{CWD_MARKER_START}/root{CWD_MARKER_END}prompt{CWD_MARKER_START}/opt/app{CWD_MARKER_END}"
        )

        self.assertEqual(output, "prompt")
        self.assertEqual(paths, ["/root", "/opt/app"])

    def test_strip_cwd_markers_leaves_regular_output_unchanged(self):
        output, paths = strip_cwd_markers("regular terminal output\r\n")

        self.assertEqual(output, "regular terminal output\r\n")
        self.assertEqual(paths, [])

    def test_strip_cwd_markers_keeps_partial_marker_pending(self):
        output, paths, pending = strip_cwd_markers_with_pending(f"prompt{CWD_MARKER_START}/op")

        self.assertEqual(output, "prompt")
        self.assertEqual(paths, [])
        self.assertEqual(pending, f"{CWD_MARKER_START}/op")

        output, paths, pending = strip_cwd_markers_with_pending(pending + f"t{CWD_MARKER_END}next")
        self.assertEqual(output, "next")
        self.assertEqual(paths, ["/opt"])
        self.assertEqual(pending, "")

    def test_filter_changed_cwd_paths_ignores_repeated_paths(self):
        paths, current_path = filter_changed_cwd_paths(["/root", "/root", "/opt", "/opt"], "/root")

        self.assertEqual(paths, ["/opt"])
        self.assertEqual(current_path, "/opt")

    def test_cwd_hook_emits_only_when_pwd_changes(self):
        self.assertIn('if [ "$PWD" != "$__captain_last_cwd" ]; then', CWD_HOOK_SCRIPT)
        self.assertNotIn("\n__captain_emit_cwd\n", CWD_HOOK_SCRIPT)

    def test_install_cwd_hook_uses_single_line_script_and_drains_only_install_output(self):
        class FakeConnection:
            def __init__(self):
                self.sent = []
                self.read_count = 0

            def send_data(self, data):
                self.sent.append(data)

            def read_available_raw(self, timeout=4.0, idle_timeout=0.35):
                self.read_count += 1
                return "root@host:~# "

        consumer = TerminalConsumer()
        consumer.connection = FakeConnection()
        consumer.suppress_internal_echo_until = 0.0

        consumer._install_cwd_hook()

        self.assertEqual(consumer.connection.sent, [CWD_HOOK_ECHO_OFF, CWD_HOOK_INSTALL_SCRIPT, CWD_HOOK_ECHO_ON])
        self.assertEqual(consumer.connection.read_count, 3)
        self.assertNotIn("\nif ", CWD_HOOK_INSTALL_SCRIPT)
        self.assertGreater(consumer.suppress_internal_echo_until, 0)

    def test_send_initial_output_preserves_remote_login_banner(self):
        class FakeConnection:
            def read_available_raw(self, timeout=4.0, idle_timeout=0.35):
                return "Welcome to Ubuntu 24.04 LTS\r\nLast login: Sat Jun 27 01:14:16 2026\r\nroot@vm:~# "

        sent_messages = []
        consumer = TerminalConsumer()
        consumer.connection = FakeConnection()
        consumer.pending_output = ""
        consumer.current_cwd = ""
        consumer.transcript_chunks = []
        consumer.send = lambda text_data=None, bytes_data=None, close=False: sent_messages.append(text_data)

        consumer._send_initial_output()

        self.assertIn("Welcome to Ubuntu 24.04 LTS", sent_messages[0])
        self.assertIn("Last login", sent_messages[0])
        self.assertIn("Welcome to Ubuntu 24.04 LTS", consumer.transcript_chunks[0])

    def test_strip_cwd_hook_install_echo_removes_internal_script(self):
        output = f"prompt\r\n{CWD_HOOK_ECHO_OFF}{CWD_HOOK_SCRIPT}{CWD_HOOK_ECHO_ON}ready\r\n"

        self.assertEqual(strip_cwd_hook_install_echo(output), "prompt\r\nready\r\n")

    def test_parse_remote_resource_monitor_output(self):
        payload = parse_remote_resource_monitor_output(self.monitor_output)

        self.assertEqual(payload["system"]["hostname"], "VM-0-23-centos")
        self.assertEqual(payload["system"]["arch"], "x86_64")
        self.assertEqual(payload["cpu"]["cores"], 2)
        self.assertEqual(payload["cpu"]["load1"], 0.13)
        self.assertEqual(payload["cpu"]["usagePercent"], 30.0)
        self.assertEqual(payload["memory"]["totalBytes"], 7780432 * 1024)
        self.assertEqual(payload["network"][0]["name"], "eth0")
        self.assertEqual(payload["network"][0]["rxBytesPerSecond"], 6800.0)
        self.assertEqual(len(payload["disks"]), 2)
        self.assertEqual(payload["disks"][1]["mountpoint"], "/data")

    def test_parse_monitor_memory_uses_available_memory(self):
        payload = parse_monitor_memory("MemTotal: 1000 kB\nMemAvailable: 250 kB\nCached: 100 kB\n")

        self.assertEqual(payload["totalBytes"], 1000 * 1024)
        self.assertEqual(payload["usedBytes"], 750 * 1024)
        self.assertEqual(payload["usagePercent"], 75.0)

    def test_parse_monitor_network_rates(self):
        first = parse_monitor_network("eth0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0")
        second = parse_monitor_network("eth0: 4072 0 0 0 0 0 0 0 6096 0 0 0 0 0 0 0")
        rates = parse_monitor_network_rates(first, second, 1)

        self.assertEqual(rates, [{"name": "eth0", "rxBytesPerSecond": 3072.0, "txBytesPerSecond": 4096.0}])

    def test_parse_monitor_disks_filters_virtual_filesystems(self):
        disks = parse_monitor_disks(
            "Filesystem Type 1B-blocks Used Available Use% Mounted on\n"
            "tmpfs tmpfs 1024 0 1024 0% /run\n"
            "/dev/vda1 ext4 2048 1024 1024 50% /\n"
        )

        self.assertEqual(len(disks), 1)
        self.assertEqual(disks[0]["filesystem"], "/dev/vda1")

    def test_sftp_properties_payload_uses_resolved_owner_group_names(self):
        attrs = type(
            "Attrs",
            (),
            {
                "st_mode": 0o40755,
                "st_uid": 0,
                "st_gid": 0,
                "st_size": 8192,
                "st_mtime": 1782446272,
                "st_atime": 1781151803,
            },
        )()

        payload = remote_file_properties_payload("/etc", attrs, {"owner": "root", "group": "root"})

        self.assertEqual(payload["owner"], "root")
        self.assertEqual(payload["group"], "root")
        self.assertEqual(payload["uid"], 0)
        self.assertEqual(payload["gid"], 0)

    def test_parse_remote_stat_output_returns_permission_details(self):
        payload = parse_remote_stat_output(
            "/root/.bash_profile",
            "regular file\t176\troot\troot\t0\t0\t644\t-rw-r--r--\t1782446272\t1685180888\t81a4\n",
        )

        self.assertEqual(payload["name"], ".bash_profile")
        self.assertEqual(payload["directory"], "/root")
        self.assertEqual(payload["type"], "file")
        self.assertEqual(payload["size"], 176)
        self.assertEqual(payload["owner"], "root")
        self.assertEqual(payload["group"], "root")
        self.assertEqual(payload["octalMode"], "0644")
        self.assertEqual(payload["permissions"], "-rw-r--r--")
        self.assertEqual(payload["special"], {"setuid": False, "setgid": False, "sticky": False})

    def test_parse_remote_stat_output_supports_directory_and_special_bits(self):
        payload = parse_remote_stat_output(
            "/root/download_test",
            "directory\t4096\troot\troot\t0\t0\t1775\tdrwxrwxr-t\t1782446272\t1685180888\t43fd\n",
        )

        self.assertEqual(payload["type"], "directory")
        self.assertEqual(payload["octalMode"], "1775")
        self.assertTrue(payload["special"]["sticky"])

    def test_parse_remote_stat_output_falls_back_to_numeric_owner_group(self):
        payload = parse_remote_stat_output(
            "/root/webssh",
            "directory\t51\t\t\t0\t0\t755\tdrwxr-xr-x\t1782446272\t1685180888\t41ed\n",
        )

        self.assertEqual(payload["owner"], "0")
        self.assertEqual(payload["group"], "0")

    def test_owner_validation_rejects_risky_values(self):
        for value in ["", "root wheel", "root:wheel", "bad\nname", "bad\x00name"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_file_owner(value, "所有者")

    def test_octal_mode_validation(self):
        self.assertEqual(normalize_remote_file_octal_mode("644"), "0644")
        self.assertEqual(normalize_remote_file_octal_mode("1775"), "1775")
        for value in ["88", "999", "abcdef", "12345", "64a"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_file_octal_mode(value)

    def test_relative_upload_path_validation(self):
        self.assertEqual(normalize_remote_relative_file_path("folder\\child/file.txt"), "folder/child/file.txt")
        for value in ["", "/tmp/file.txt", "../file.txt", "folder/../file.txt", "bad\nfile.txt", "bad\x00file.txt"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_relative_file_path(value)

    def test_symlink_target_validation(self):
        self.assertEqual(normalize_remote_symlink_target("/var/log/app.log"), "/var/log/app.log")
        for value in ["", "bad\npath", "bad\x00path"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_symlink_target(value)

    def test_create_remote_file_builds_safe_command(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new.txt"},
        ):
            payload = create_remote_file(object(), "/data", "new.txt")

        self.assertEqual(payload["path"], "/data/new.txt")
        self.assertIn("test -e /data/new.txt", run_command.call_args.args[1])
        self.assertIn(": > /data/new.txt", run_command.call_args.args[1])

    def test_create_remote_file_applies_requested_mode(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new.txt"},
        ):
            payload = create_remote_file(object(), "/data", "new.txt", "0644")

        self.assertEqual(payload["path"], "/data/new.txt")
        self.assertEqual(run_command.call_count, 2)
        self.assertIn(": > /data/new.txt", run_command.call_args_list[0].args[1])
        self.assertIn("chmod 0644 /data/new.txt", run_command.call_args_list[1].args[1])

    def test_create_remote_file_rejects_invalid_mode(self):
        with self.assertRaises(TerminalConnectionError):
            create_remote_file(object(), "/data", "new.txt", "999")

    def test_create_remote_directory_builds_safe_command(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new-folder"},
        ):
            payload = create_remote_directory(object(), "/data", "new-folder")

        self.assertEqual(payload["path"], "/data/new-folder")
        self.assertIn("mkdir /data/new-folder", run_command.call_args.args[1])

    def test_create_remote_directory_applies_requested_mode(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new-folder"},
        ):
            payload = create_remote_directory(object(), "/data", "new-folder", "0755")

        self.assertEqual(payload["path"], "/data/new-folder")
        self.assertEqual(run_command.call_count, 2)
        self.assertIn("mkdir /data/new-folder", run_command.call_args_list[0].args[1])
        self.assertIn("chmod 0755 /data/new-folder", run_command.call_args_list[1].args[1])

    def test_create_remote_directory_rejects_invalid_mode(self):
        with self.assertRaises(TerminalConnectionError):
            create_remote_directory(object(), "/data", "new-folder", "12345")

    def test_create_remote_symlink_builds_safe_command(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/app-link"},
        ):
            payload = create_remote_symlink(object(), "/data", "app-link", "/opt/app")

        self.assertEqual(payload["path"], "/data/app-link")
        self.assertIn("ln -s /opt/app /data/app-link", run_command.call_args.args[1])


class TerminalMonitorViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(username="monitor-operator", password="pass")
        self.group = HostGroup.objects.create(name="monitor-tests")

    def authenticated_request(self, request):
        request.user = self.user
        return request

    def test_terminal_monitor_returns_not_found_for_missing_host(self):
        request = self.authenticated_request(
            self.factory.post("/api/web-terminal/hosts/999/monitor/", data={}, content_type="application/json")
        )

        response = views.terminal_monitor(request, 999)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "主机不存在")

    def test_terminal_monitor_returns_bad_request_on_probe_failure(self):
        host = ManagedHost.objects.create(
            name="monitor-host",
            group=self.group,
            private_ip="10.0.0.5",
            login_user="root",
        )
        request = self.authenticated_request(
            self.factory.post(f"/api/web-terminal/hosts/{host.id}/monitor/", data={}, content_type="application/json")
        )

        with patch("web_terminal.views.get_remote_resource_monitor", side_effect=TerminalConnectionError("当前主机不支持资源监控")):
            response = views.terminal_monitor(request, host.id)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "当前主机不支持资源监控")


class TerminalFileDownloadAttachmentTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(username="download-operator", password="pass")
        self.group = HostGroup.objects.create(name="download-tests")

    def authenticated_request(self, request):
        request.user = self.user
        return request

    def test_terminal_file_download_attachment_returns_raw_file(self):
        host = ManagedHost.objects.create(
            name="download-host",
            group=self.group,
            private_ip="10.0.0.6",
            login_user="root",
        )
        request = self.authenticated_request(
            self.factory.get(f"/api/web-terminal/hosts/{host.id}/files/download/raw/?path=/tmp/config.toml&protocol=scp")
        )

        with patch(
            "web_terminal.views.stream_remote_file_content",
            return_value={"filename": "config.toml", "content": b"port=22"},
        ) as mocked_download:
            response = views.terminal_file_download_attachment(request, host.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"port=22")
        self.assertIn("config.toml", response["Content-Disposition"])
        mocked_download.assert_called_once_with(host, "/tmp/config.toml", "scp")


class TerminalAuthApiTests(TestCase):
    def test_terminal_tree_requires_login(self):
        response = self.client.get("/api/web-terminal/tree/")

        self.assertEqual(response.status_code, 401)


class TerminalSessionAuditTests(TestCase):
    def setUp(self):
        ensure_feature_permissions()
        self.user = get_user_model().objects.create_user(username="audit-operator", password="pass")
        role = Group.objects.create(name="session-audit-operator")
        role.permissions.add(
            Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["hosts"]),
            Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("hosts", "session_audit")]),
        )
        self.user.groups.add(role)
        self.client.force_login(self.user)
        self.group = HostGroup.objects.create(name="audit-tests")
        self.host = ManagedHost.objects.create(name="audit-host", group=self.group, private_ip="10.0.0.8", login_user="root")
        self.session = TerminalSession.objects.create(host=self.host, transcript="")
        initialize_session_recording(self.session)

    def test_classify_command_risk(self):
        self.assertEqual(classify_command_risk("rm -rf /tmp/data"), TerminalCommandAudit.RISK_HIGH)
        self.assertEqual(classify_command_risk("sudo systemctl restart nginx"), TerminalCommandAudit.RISK_MEDIUM)
        self.assertEqual(classify_command_risk("ls -la"), TerminalCommandAudit.RISK_ACCEPT)

    def test_command_buffer_splits_submitted_commands(self):
        buffer, commands = command_buffer_after_input("", "uptime\rwhoami")
        self.assertEqual(buffer, "whoami")
        self.assertEqual(commands, ["uptime"])

        buffer, commands = command_buffer_after_input(buffer, "\x7fi\n")
        self.assertEqual(buffer, "")
        self.assertEqual(commands, ["whoami"])

        buffer, commands = command_buffer_after_input("ls", "\x1b[A -la\r")
        self.assertEqual(buffer, "")
        self.assertEqual(commands, ["ls -la"])

    def test_rest_command_creates_audit_and_recording(self):
        with patch("web_terminal.services.run_live_terminal_command", return_value=("ok\n", 0)):
            response = self.client.post(
                f"/api/web-terminal/sessions/{self.session.session_id}/commands/",
                data={"command": "whoami"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        audit = TerminalCommandAudit.objects.get(id=response.json()["auditId"])
        self.assertEqual(audit.username, self.user.username)
        self.assertEqual(audit.command, "whoami")
        self.assertEqual(audit.output, "ok\n")
        self.session.refresh_from_db()
        self.assertIn('"version":3', self.session.recording)
        self.assertIn('"i","whoami\\r"', self.session.recording)
        self.assertIn('"o","ok\\n"', self.session.recording)

    def test_rest_command_skips_audit_when_user_session_audit_disabled(self):
        UserProfile.objects.create(user=self.user, session_audit_enabled=False)
        initial_recording = self.session.recording

        with patch("web_terminal.services.run_live_terminal_command", return_value=("ok\n", 0)):
            response = self.client.post(
                f"/api/web-terminal/sessions/{self.session.session_id}/commands/",
                data={"command": "whoami"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("auditId", response.json())
        self.assertFalse(TerminalCommandAudit.objects.exists())
        self.session.refresh_from_db()
        self.assertEqual(self.session.recording, initial_recording)

    def test_session_audit_list_requires_permission(self):
        viewer = get_user_model().objects.create_user(username="viewer", password="pass")
        self.client.force_login(viewer)

        response = self.client.get("/api/web-terminal/session-audits/")

        self.assertEqual(response.status_code, 403)

    def test_session_audit_list_filters_and_paginates(self):
        TerminalCommandAudit.objects.create(
            session=self.session,
            host=self.host,
            user=self.user,
            username=self.user.username,
            command="rm -rf /tmp/cache",
            output="",
            risk_level=TerminalCommandAudit.RISK_HIGH,
            asset_name=self.host.name,
            ip_address=self.host.private_ip,
            executed_at=self.session.created_at,
        )

        response = self.client.get("/api/web-terminal/session-audits/?search=cache&riskLevel=high&page=1&pageSize=10")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["command"], "rm -rf /tmp/cache")
        self.assertEqual(payload["results"][0]["riskLevel"], "high")

    def test_recording_endpoint_returns_asciicast(self):
        self.session.recording += '[0.1,"o","hello"]\n'
        self.session.save(update_fields=["recording"])

        response = self.client.get(f"/api/web-terminal/sessions/{self.session.session_id}/recording.cast")

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/x-asciicast", response["Content-Type"])
        self.assertTrue(response.content.decode("utf-8").startswith('{"version":3'))


class TerminalQuickCommandApiTests(TestCase):
    def setUp(self):
        ensure_feature_permissions()
        self.user = get_user_model().objects.create_user(username="operator", password="pass")
        role = Group.objects.create(name="quick-command-operator")
        role.permissions.add(
            Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["hosts"]),
            Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("hosts", "quick_commands")]),
        )
        self.user.groups.add(role)
        self.client.force_login(self.user)
        TerminalQuickCommand.objects.all().delete()

    def test_quick_command_list_requires_login(self):
        self.client.logout()

        response = self.client.get("/api/web-terminal/quick-commands/")

        self.assertEqual(response.status_code, 401)

    def test_quick_command_list_requires_permission(self):
        viewer = get_user_model().objects.create_user(username="viewer", password="pass")
        self.client.force_login(viewer)

        response = self.client.get("/api/web-terminal/quick-commands/")

        self.assertEqual(response.status_code, 403)

    def test_quick_command_list_orders_by_category_sort_and_id(self):
        third = TerminalQuickCommand.objects.create(category="Linux", name="third", command="whoami", sort_order=30)
        first = TerminalQuickCommand.objects.create(category="Docker", name="first", command="docker ps", sort_order=20)
        second = TerminalQuickCommand.objects.create(category="Docker", name="second", command="docker images", sort_order=20)

        response = self.client.get("/api/web-terminal/quick-commands/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [first.id, second.id, third.id])

    def test_create_quick_command_trims_required_fields_and_sets_next_sort_order(self):
        TerminalQuickCommand.objects.create(category="Linux", name="existing", command="uptime", sort_order=40)

        response = self.client.post(
            "/api/web-terminal/quick-commands/",
            data={"category": " Linux ", "name": "  查看进程  ", "command": " ps aux ", "description": "  desc  "},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["category"], "Linux")
        self.assertEqual(payload["name"], "查看进程")
        self.assertEqual(payload["command"], "ps aux")
        self.assertEqual(payload["description"], "desc")
        self.assertEqual(payload["sortOrder"], 50)

    def test_create_quick_command_rejects_missing_required_fields(self):
        response = self.client.post(
            "/api/web-terminal/quick-commands/",
            data={"category": "Linux", "name": "", "command": " "},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_update_and_delete_quick_command(self):
        command = TerminalQuickCommand.objects.create(category="Linux", name="old", command="uptime", enabled=True)

        update_response = self.client.put(
            f"/api/web-terminal/quick-commands/{command.id}/",
            data={"name": "new", "category": "Linux", "command": "free -h", "enabled": False, "sortOrder": 7},
            content_type="application/json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["name"], "new")
        self.assertFalse(update_response.json()["enabled"])
        self.assertEqual(update_response.json()["sortOrder"], 7)

        delete_response = self.client.delete(f"/api/web-terminal/quick-commands/{command.id}/")

        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(TerminalQuickCommand.objects.filter(id=command.id).exists())

    def test_quick_command_detail_returns_not_found(self):
        response = self.client.delete("/api/web-terminal/quick-commands/999/")

        self.assertEqual(response.status_code, 404)

    def test_reorder_updates_sort_order_and_rejects_missing_ids(self):
        first = TerminalQuickCommand.objects.create(category="Linux", name="first", command="one", sort_order=10)
        second = TerminalQuickCommand.objects.create(category="Linux", name="second", command="two", sort_order=20)

        response = self.client.post(
            "/api/web-terminal/quick-commands/reorder/",
            data={"ids": [second.id, first.id]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(second.sort_order, 10)
        self.assertEqual(first.sort_order, 20)

        missing_response = self.client.post(
            "/api/web-terminal/quick-commands/reorder/",
            data={"ids": [first.id, 999]},
            content_type="application/json",
        )

        self.assertEqual(missing_response.status_code, 400)
