from __future__ import annotations

import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from host_management.models import ManagedHost
from web_terminal.consumers import RdpTerminalConsumer, TerminalConsumer
from web_terminal.consumers.protocol import (
    command_buffer_after_input,
    filter_changed_cwd_paths,
    split_complete_guacamole_messages,
    strip_cwd_markers_with_pending,
)
from web_terminal.consumers.rdp import RdpTerminalConsumer as RdpConsumerModuleExport
from web_terminal.consumers.ssh import TerminalConsumer as TerminalConsumerModuleExport
from web_terminal.services import TerminalConnectionError, guacamole_instruction


class ConsumerPublicContractTests(SimpleTestCase):
    def test_package_reexports_consumer_classes(self):
        self.assertIs(TerminalConsumer, TerminalConsumerModuleExport)
        self.assertIs(RdpTerminalConsumer, RdpConsumerModuleExport)


class ConsumerProtocolTests(SimpleTestCase):
    def test_cwd_marker_parser_preserves_incomplete_marker(self):
        marker = "\x1b]1337;CaptainCwd="

        cleaned, paths, pending = strip_cwd_markers_with_pending(
            f"before{marker}/srv/app\x07after{marker}/srv/pending"
        )

        self.assertEqual(cleaned, "beforeafter")
        self.assertEqual(paths, ["/srv/app"])
        self.assertEqual(pending, f"{marker}/srv/pending")

    def test_changed_cwd_filter_deduplicates_only_current_path(self):
        changed, current = filter_changed_cwd_paths(
            ["/srv", "/srv", "/srv/app", "/srv"],
            "/srv",
        )

        self.assertEqual(changed, ["/srv/app", "/srv"])
        self.assertEqual(current, "/srv")

    def test_command_buffer_dispatches_lines_and_control_keys(self):
        buffer, commands = command_buffer_after_input("ec", "ho ok\rnext\x7f!\n\x03")

        self.assertEqual(buffer, "")
        self.assertEqual(commands, ["echo ok", "nex!", "^C"])

    def test_guacamole_splitter_preserves_incomplete_instruction(self):
        first = guacamole_instruction("sync", "1")
        second = guacamole_instruction("size", "1280", "720")

        messages, pending = split_complete_guacamole_messages(first + second + "4.test")

        self.assertEqual(messages, [first, second])
        self.assertEqual(pending, "4.test")


class TerminalConsumerContractTests(SimpleTestCase):
    def _consumer(self, *, authenticated: bool = True) -> TerminalConsumer:
        consumer = TerminalConsumer()
        session = Mock(session_key="session-key")
        session.exists.return_value = True
        user = SimpleNamespace(is_authenticated=authenticated, is_staff=authenticated, is_superuser=False)
        consumer.scope = {
            "user": user,
            "session": session,
            "url_route": {"kwargs": {"host_id": 7}},
        }
        consumer.accept = Mock()
        consumer.send = Mock()
        consumer.close = Mock()
        return consumer

    def test_connect_accepts_then_rejects_unauthenticated_user(self):
        consumer = self._consumer(authenticated=False)

        consumer.connect()

        consumer.accept.assert_called_once_with()
        consumer.close.assert_called_once_with()
        payload = json.loads(consumer.send.call_args.kwargs["text_data"])
        self.assertEqual(payload, {"type": "error", "message": "请先登录"})

    @patch("web_terminal.consumers.ssh.has_feature_permission", return_value=False)
    @patch("web_terminal.consumers.ssh.ManagedHost.objects.get")
    def test_connect_rejects_user_without_terminal_permission(self, get_host, has_permission):
        consumer = self._consumer()

        consumer.connect()

        has_permission.assert_called_once_with(consumer.scope["user"], "hosts", "terminal")
        get_host.assert_not_called()
        consumer.close.assert_called_once_with(code=4403)
        payload = json.loads(consumer.send.call_args.kwargs["text_data"])
        self.assertEqual(payload, {"type": "error", "message": "没有 Web 终端权限"})

    @patch("web_terminal.consumers.ssh.threading.Thread")
    @patch("web_terminal.consumers.ssh.open_live_terminal")
    @patch("web_terminal.consumers.ssh.ManagedHost.objects.get")
    def test_connect_accepts_opens_host_and_sends_ready_payload(
        self,
        get_host,
        open_terminal,
        thread_class,
    ):
        host = SimpleNamespace(id=7, name="server-7")
        connection = Mock()
        get_host.return_value = host
        open_terminal.return_value = connection
        consumer = self._consumer()
        consumer._create_audit_session = Mock()
        consumer._send_initial_output = Mock()
        consumer._install_cwd_hook = Mock()

        consumer.connect()

        consumer.accept.assert_called_once_with()
        get_host.assert_called_once_with(id=7)
        open_terminal.assert_called_once_with(host)
        payload = json.loads(consumer.send.call_args.kwargs["text_data"])
        self.assertEqual(payload, {"type": "ready"})
        thread_class.return_value.start.assert_called_once_with()

    def test_receive_dispatches_input_and_resize_messages(self):
        consumer = self._consumer()
        consumer.connection = Mock()
        consumer._record_input = Mock()
        consumer._record_resize = Mock()

        consumer.receive(text_data=json.dumps({"type": "input", "data": "ls\r"}))
        consumer.receive(text_data=json.dumps({"type": "resize", "cols": 132, "rows": 43}))

        consumer._record_input.assert_called_once_with("ls\r")
        consumer.connection.send_data.assert_called_once_with("ls\r")
        consumer._record_resize.assert_called_once_with(132, 43)
        consumer.connection.resize.assert_called_once_with(132, 43)

    def test_outbound_events_keep_serialized_json_keys(self):
        consumer = self._consumer()

        consumer.terminal_output({"data": "hello"})
        consumer.terminal_cwd({"path": "/srv/app"})
        consumer.terminal_closed({"reason": "done"})

        payloads = [json.loads(call.kwargs["text_data"]) for call in consumer.send.call_args_list]
        self.assertEqual(
            payloads,
            [
                {"type": "output", "data": "hello"},
                {"type": "cwd", "path": "/srv/app"},
                {"type": "closed", "reason": "done"},
            ],
        )
        consumer.close.assert_called_once_with()


class RdpTerminalConsumerContractTests(SimpleTestCase):
    def _consumer(self, *, authenticated: bool = True) -> RdpTerminalConsumer:
        consumer = RdpTerminalConsumer()
        session = Mock(session_key="session-key")
        session.exists.return_value = True
        user = SimpleNamespace(is_authenticated=authenticated, is_staff=authenticated, is_superuser=False)
        consumer.scope = {
            "user": user,
            "session": session,
            "url_route": {"kwargs": {"host_id": 9}},
            "query_string": b"width=1440&height=900",
        }
        consumer.accept = Mock()
        consumer.send = Mock()
        consumer.close = Mock()
        return consumer

    def test_connect_accepts_guacamole_then_closes_unauthenticated_user(self):
        consumer = self._consumer(authenticated=False)

        consumer.connect()

        consumer.accept.assert_called_once_with(subprotocol="guacamole")
        consumer.close.assert_called_once_with(code=4401)

    @patch("web_terminal.consumers.rdp.has_feature_permission", return_value=False)
    @patch("web_terminal.consumers.rdp.ManagedHost.objects.get")
    def test_connect_rejects_user_without_terminal_permission(self, get_host, has_permission):
        consumer = self._consumer()

        consumer.connect()

        has_permission.assert_called_once_with(consumer.scope["user"], "hosts", "terminal")
        get_host.assert_not_called()
        consumer.close.assert_called_once_with(code=4403)

    @patch("web_terminal.consumers.rdp.create_rdp_terminal_session")
    @patch("web_terminal.consumers.rdp.terminal_protocol_for_host")
    @patch("web_terminal.consumers.rdp.ManagedHost.objects.get")
    def test_connect_uses_not_found_and_connection_error_close_codes(
        self,
        get_host,
        protocol_for_host,
        create_session,
    ):
        get_host.side_effect = ManagedHost.DoesNotExist
        missing = self._consumer()

        missing.connect()

        missing.close.assert_called_once_with(code=4404)

        host = SimpleNamespace(id=9)
        get_host.side_effect = None
        get_host.return_value = host
        protocol_for_host.return_value = "rdp"
        create_session.return_value = SimpleNamespace(session_id="session-9")
        failed = self._consumer()
        failed._connect_guacd = Mock(side_effect=TerminalConnectionError("gateway down"))
        failed._mark_session_error = Mock()

        failed.connect()

        failed._mark_session_error.assert_called_once_with("gateway down")
        failed.close.assert_called_once_with(code=4500)

    def test_receive_echoes_internal_messages_and_forwards_client_input(self):
        consumer = self._consumer()
        consumer.guacd_socket = Mock()
        internal = guacamole_instruction("", "session-9")
        keyboard = guacamole_instruction("key", "65", "1")

        consumer.receive(text_data=internal)
        consumer.receive(text_data=keyboard)

        consumer.send.assert_called_once_with(text_data=internal)
        consumer.guacd_socket.sendall.assert_called_once_with(keyboard.encode("utf-8"))

    def test_receive_socket_error_marks_session_and_closes_with_1011(self):
        consumer = self._consumer()
        consumer.guacd_socket = Mock()
        consumer.guacd_socket.sendall.side_effect = OSError("socket closed")
        consumer._mark_session_error = Mock()

        consumer.receive(text_data=guacamole_instruction("key", "65", "1"))

        consumer._mark_session_error.assert_called_once_with("socket closed")
        consumer.close.assert_called_once_with(code=1011)
