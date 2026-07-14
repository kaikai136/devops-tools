from types import SimpleNamespace
from typing import get_type_hints
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase

from host_management.models import ManagedHost

from .. import services
from ..services import connections as service_connections


class TerminalCommandCharacterizationTests(SimpleTestCase):
    def make_session(self, **overrides):
        values = {
            "session_id": "00000000-0000-0000-0000-000000000123",
            "recording_started_at": object(),
            "transcript": "existing\n",
            "status": "connected",
            "last_command_at": None,
            "save": MagicMock(),
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_one_shot_command_uses_thirty_second_timeout_and_exact_output(self):
        client = MagicMock()
        stdout = MagicMock()
        stdout.read.return_value = b"hello\r\n"
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = b""
        client.exec_command.return_value = (MagicMock(), stdout, stderr)

        with patch("web_terminal.services.open_ssh_client", return_value=client):
            result = services.run_one_shot_ssh_command(object(), "printf hello")

        self.assertEqual(result, "hello\r\n")
        client.exec_command.assert_called_once_with("printf hello", timeout=30)
        client.close.assert_called_once_with()

    def test_one_shot_command_translates_nonzero_exit_and_still_closes_client(self):
        client = MagicMock()
        stdout = MagicMock()
        stdout.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 7
        stderr = MagicMock()
        stderr.read.return_value = b" denied \n"
        client.exec_command.return_value = (MagicMock(), stdout, stderr)

        with patch("web_terminal.services.open_ssh_client", return_value=client):
            with self.assertRaises(services.TerminalConnectionError) as raised:
                services.run_one_shot_ssh_command(object(), "false")

        self.assertEqual(str(raised.exception), "denied")
        client.close.assert_called_once_with()

    def test_one_shot_upload_uses_sixty_second_timeout_and_shutdown_order(self):
        client = MagicMock()
        stdin = MagicMock()
        stdout = MagicMock()
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = b""
        client.exec_command.return_value = (stdin, stdout, stderr)
        calls = MagicMock()
        calls.attach_mock(stdin.write, "write")
        calls.attach_mock(stdin.channel.shutdown_write, "shutdown_write")
        calls.attach_mock(stderr.read, "read_error")
        calls.attach_mock(stdout.channel.recv_exit_status, "exit_status")

        with patch("web_terminal.services.open_ssh_client", return_value=client):
            result = services.run_one_shot_ssh_upload(object(), "cat > /tmp/data", b"payload")

        self.assertIsNone(result)
        client.exec_command.assert_called_once_with("cat > /tmp/data", timeout=60)
        self.assertEqual(
            calls.mock_calls,
            [call.write(b"payload"), call.shutdown_write(), call.read_error(), call.exit_status()],
        )
        client.close.assert_called_once_with()

    def test_live_command_returns_current_missing_session_tuple(self):
        session = self.make_session()
        service_connections.LIVE_TERMINALS.pop(str(session.session_id), None)

        self.assertEqual(
            services.run_live_terminal_command(session, "pwd"),
            ("SSH \u4f1a\u8bdd\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u8fde\u63a5\u4e3b\u673a\u3002", None),
        )

    def test_live_command_closes_and_removes_exited_connection(self):
        session = self.make_session()
        connection = MagicMock()
        connection.send_command.return_value = "done\n"
        connection.channel.closed = True
        service_connections.LIVE_TERMINALS[str(session.session_id)] = connection

        result = services.run_live_terminal_command(session, "exit")

        self.assertEqual(result, ("done", 0))
        connection.close.assert_called_once_with()
        self.assertNotIn(str(session.session_id), service_connections.LIVE_TERMINALS)

    def test_session_command_empty_input_returns_exact_dictionary_without_side_effects(self):
        session = self.make_session()

        with patch("web_terminal.services.is_session_audit_enabled") as audit_enabled:
            result = services.run_session_command(session, "   ", user=object())

        self.assertEqual(result, {"command": "", "output": "", "exitCode": 0})
        audit_enabled.assert_not_called()
        session.save.assert_not_called()

    def test_session_command_preserves_audit_recording_save_order_and_payload(self):
        session = self.make_session()
        user = object()
        audit = SimpleNamespace(id=37)
        now = object()
        ordered = MagicMock()

        with patch("web_terminal.services.is_session_audit_enabled", return_value=True) as audit_enabled, patch(
            "web_terminal.services.run_live_terminal_command", return_value=("ok\n", 0)
        ) as run_live, patch("web_terminal.services.create_command_audit", return_value=audit) as create_audit, patch(
            "web_terminal.services.append_session_recording_event"
        ) as append_event, patch("django.utils.timezone.now", return_value=now) as timezone_now:
            ordered.attach_mock(audit_enabled, "audit_enabled")
            ordered.attach_mock(run_live, "run_live")
            ordered.attach_mock(create_audit, "create_audit")
            ordered.attach_mock(append_event, "append_event")
            ordered.attach_mock(timezone_now, "timezone_now")
            ordered.attach_mock(session.save, "save")

            result = services.run_session_command(session, "  whoami  ", user=user)

        self.assertEqual(
            result,
            {"command": "whoami", "output": "ok\n", "exitCode": 0, "auditId": 37},
        )
        self.assertEqual(session.transcript, "existing\n$ whoami\nok\n\n")
        self.assertIs(session.last_command_at, now)
        self.assertEqual(
            ordered.mock_calls,
            [
                call.audit_enabled(user),
                call.run_live(session, "whoami"),
                call.create_audit(session, "whoami", user=user, output="ok\n"),
                call.append_event(session, "i", "whoami\r"),
                call.append_event(session, "o", "ok\n"),
                call.timezone_now(),
                call.save(
                    update_fields=[
                        "last_command_at",
                        "transcript",
                        "recording",
                        "recording_last_event_at",
                    ]
                ),
            ],
        )

    def test_clear_command_preserves_exact_payload_and_audit_call(self):
        session = self.make_session()
        user = object()
        audit = SimpleNamespace(id=41)

        with patch("web_terminal.services.is_session_audit_enabled", return_value=True), patch(
            "web_terminal.services.create_command_audit", return_value=audit
        ) as create_audit, patch("web_terminal.services.append_session_recording_event") as append_event:
            result = services.run_session_command(session, " clear ", user=user)

        self.assertEqual(
            result,
            {"command": "clear", "output": "__CLEAR__", "exitCode": 0, "auditId": 41},
        )
        create_audit.assert_called_once_with(session, "clear", user=user, output="")
        append_event.assert_called_once_with(session, "i", "clear\r")
        session.save.assert_called_once_with(
            update_fields=["last_command_at", "transcript", "recording", "recording_last_event_at"]
        )


    def test_one_shot_command_type_hints_resolve_managed_host(self):
        for function in (
            services.run_one_shot_ssh_command,
            services.run_one_shot_ssh_upload,
        ):
            with self.subTest(function=function.__name__):
                self.assertIs(get_type_hints(function)["host"], ManagedHost)

    def test_command_symbols_report_the_new_implementation_module(self):
        for name in (
            "run_session_command",
            "run_live_terminal_command",
            "run_one_shot_ssh_command",
            "run_one_shot_ssh_upload",
        ):
            with self.subTest(name=name):
                self.assertEqual(getattr(services, name).__module__, "web_terminal.services.commands")
