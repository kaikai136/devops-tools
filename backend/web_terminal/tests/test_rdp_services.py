from __future__ import annotations

from datetime import datetime
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from web_terminal.consumers import RdpTerminalConsumer
from web_terminal.services import (
    TerminalConnectionError,
    build_rdp_connection_parameters,
    cleanup_expired_rdp_recordings,
    greeting_for,
    safe_recording_relative_path,
    terminal_protocol_for_host,
)


class RdpServiceCharacterizationTests(SimpleTestCase):
    def make_host(self, **overrides):
        values = {
            "name": "win-01",
            "private_ip": "10.0.0.9",
            "public_ip": None,
            "port": 3389,
            "login_user": "Administrator",
            "login_password": "rdp-secret",
            "os": "windows",
            "system_type": "Windows",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def make_session(self, **overrides):
        values = {
            "recording_enabled": False,
            "recording_file": "",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_terminal_protocol_and_greeting_preserve_current_host_mapping(self):
        windows = self.make_host()
        linux = self.make_host(
            name="linux-01",
            private_ip="10.0.0.8",
            port=22,
            login_user="root",
            os="centos",
            system_type="Linux",
        )
        public = self.make_host(public_ip="203.0.113.10", login_user="")

        self.assertEqual(terminal_protocol_for_host(windows), "rdp")
        self.assertEqual(terminal_protocol_for_host(linux), "ssh")
        self.assertEqual(
            greeting_for(public),
            "\u6b63\u5728\u8fde\u63a5 win-01 (203.0.113.10:3389)\n"
            "\u767b\u5f55\u7528\u6237\uff1a\u672a\u914d\u7f6e\n"
            "\u8fde\u63a5\u5df2\u5efa\u7acb\u3002\u8f93\u5165\u547d\u4ee4\u540e\u56de\u8f66\u6267\u884c\u3002",
        )

    def test_connection_parameters_preserve_exact_keys_defaults_and_dimension_clamping(self):
        params = build_rdp_connection_parameters(
            self.make_host(port=0),
            self.make_session(),
            width="invalid",
            height=99999,
        )

        self.assertEqual(
            params,
            {
                "hostname": "10.0.0.9",
                "port": "3389",
                "username": "Administrator",
                "password": "rdp-secret",
                "security": "any",
                "ignore-cert": "true",
                "width": "1280",
                "height": "7680",
            },
        )

    @override_settings(RDP_RECORDING_ROOT=Path("C:/recordings"))
    def test_connection_parameters_preserve_recording_mapping(self):
        params = build_rdp_connection_parameters(
            self.make_host(public_ip="203.0.113.10"),
            self.make_session(
                recording_enabled=True,
                recording_file="2026/07/session-123",
            ),
            width=319,
            height=720,
        )

        self.assertEqual(params["hostname"], "203.0.113.10")
        self.assertEqual(params["width"], "320")
        self.assertEqual(params["height"], "720")
        self.assertEqual(params["recording-path"], str(Path("C:/recordings") / "2026" / "07"))
        self.assertEqual(params["recording-name"], "session-123")
        self.assertEqual(params["create-recording-path"], "true")

    def test_safe_recording_path_preserves_current_validation_error(self):
        self.assertEqual(safe_recording_relative_path(r"2026\07\session.guac"), Path("2026/07/session.guac"))
        for value in ("../session.guac", "C:/absolute/session.guac"):
            with self.subTest(value=value):
                with self.assertRaisesMessage(TerminalConnectionError, "RDP \u5f55\u5c4f\u8def\u5f84\u65e0\u6548"):
                    safe_recording_relative_path(value)

    @override_settings(RDP_RECORDING_RETENTION_DAYS=30)
    def test_cleanup_preserves_file_deletion_session_clear_and_unsafe_skip_behavior(self):
        now = timezone.make_aware(datetime(2026, 7, 14, 12, 0, 0))
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "2026" / "05" / "expired.guac"
            target.parent.mkdir(parents=True)
            target.write_text("recording", encoding="utf-8")
            expired = SimpleNamespace(
                recording_file="2026/05/expired.guac",
                save=MagicMock(),
            )
            unsafe = SimpleNamespace(recording_file="../outside.guac", save=MagicMock())

            with patch("web_terminal.models.TerminalSession.objects.filter", return_value=[expired, unsafe]) as query:
                result = cleanup_expired_rdp_recordings(root=root, now=now)

        self.assertEqual(result, {"deleted": 1})
        self.assertFalse(target.exists())
        self.assertFalse((root / "2026").exists())
        self.assertEqual(expired.recording_file, "")
        expired.save.assert_called_once_with(update_fields=["recording_file"])
        self.assertEqual(unsafe.recording_file, "../outside.guac")
        unsafe.save.assert_not_called()
        query.assert_called_once_with(
            protocol="rdp",
            recording_file__gt="",
            created_at__lt=now - timezone.timedelta(days=30),
        )


    def test_rdp_module_supports_fresh_import_orders_without_legacy_module(self):
        environment = os.environ.copy()
        environment.setdefault("DJANGO_SETTINGS_MODULE", "ops_tool.settings")
        probes = (
            "import web_terminal.services.rdp; import web_terminal.services; assert 'web_terminal.services_legacy' not in sys.modules; print('rdp-first OK')",
            "import web_terminal.services; import web_terminal.services.rdp; assert 'web_terminal.services_legacy' not in sys.modules; print('facade-first OK')",
            "import web_terminal.services.payloads; import web_terminal.services.audit; assert 'web_terminal.services_legacy' not in sys.modules; print('dependents-first OK')",
        )

        for probe_source in probes:
            with self.subTest(probe_source=probe_source):
                probe = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import sys; import django; django.setup(); " + probe_source,
                    ],
                    capture_output=True,
                    text=True,
                    env=environment,
                    check=False,
                )
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertNotIn("web_terminal.services_legacy", probe.stdout)

    @override_settings(GUACD_HOST="127.0.0.1", GUACD_PORT=4822)
    def test_consumer_preserves_rdp_size_dpi_and_connect_parameter_order(self):
        socket = MagicMock()
        consumer = RdpTerminalConsumer()
        consumer.scope = {"query_string": b"width=1440&height=900"}
        consumer.session = self.make_session()
        args = ["args", "hostname", "port", "username", "password", "width", "height", "missing"]

        with patch("web_terminal.consumers.rdp.socket.create_connection", return_value=socket), patch(
            "web_terminal.consumers.rdp.read_guacamole_instruction",
            side_effect=["args", "ready"],
        ), patch(
            "web_terminal.consumers.rdp.parse_guacamole_instruction",
            side_effect=[args, ["ready", "connection-id"]],
        ):
            result = consumer._connect_guacd(self.make_host())

        self.assertIs(result, socket)
        self.assertEqual(
            [call.args[0].decode("utf-8") for call in socket.sendall.call_args_list],
            [
                "6.select,3.rdp;",
                "4.size,4.1440,3.900,2.96;",
                "5.audio;",
                "5.video;",
                "5.image,9.image/png,10.image/jpeg;",
                "7.connect,8.10.0.0.9,4.3389,13.Administrator,10.rdp-secret,4.1440,3.900,0.;",
            ],
        )
        self.assertEqual(socket.settimeout.call_args_list[0].args, (15,))
        self.assertEqual(socket.settimeout.call_args_list[-1].args, (1.0,))
