import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase

from .. import services


class TerminalConnectionCharacterizationTests(SimpleTestCase):
    def make_host(self, **overrides):
        values = {
            "login_user": "root",
            "login_password": "secret",
            "private_key": "",
            "public_ip": "203.0.113.10",
            "private_ip": "10.0.0.8",
            "port": 2222,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def fake_paramiko(self, client_factory):
        return SimpleNamespace(
            SSHClient=client_factory,
            AutoAddPolicy=MagicMock(return_value="auto-add-policy"),
            RSAKey=MagicMock(),
            Ed25519Key=MagicMock(),
            ECDSAKey=MagicMock(),
            DSSKey=MagicMock(),
        )

    def test_open_ssh_client_uses_current_paramiko_timeouts_and_keepalive(self):
        client = MagicMock()
        transport = client.get_transport.return_value
        client_factory = MagicMock(return_value=client)
        paramiko = self.fake_paramiko(client_factory)
        host = self.make_host()

        with patch.dict(sys.modules, {"paramiko": paramiko}):
            result = services.open_ssh_client(host)

        self.assertIs(result, client)
        client.set_missing_host_key_policy.assert_called_once_with("auto-add-policy")
        client.connect.assert_called_once_with(
            hostname="203.0.113.10",
            port=2222,
            username="root",
            password="secret",
            pkey=None,
            timeout=15,
            banner_timeout=30,
            auth_timeout=20,
            look_for_keys=False,
            allow_agent=False,
        )
        transport.set_keepalive.assert_called_once_with(30)

    def test_open_ssh_client_retries_retryable_errors_and_translates_last_error(self):
        clients = [MagicMock(), MagicMock(), MagicMock()]
        clients[0].connect.side_effect = TimeoutError("timed out once")
        clients[1].connect.side_effect = ConnectionResetError("connection reset twice")
        clients[2].connect.side_effect = RuntimeError("permission denied")
        paramiko = self.fake_paramiko(MagicMock(side_effect=clients))

        with patch.dict(sys.modules, {"paramiko": paramiko}), patch("time.sleep") as sleep:
            with self.assertRaises(services.TerminalConnectionError) as raised:
                services.open_ssh_client(self.make_host())

        self.assertEqual(str(raised.exception), "SSH \u8fde\u63a5\u5931\u8d25\uff1apermission denied")
        self.assertEqual(sleep.call_args_list, [call(0.8), call(1.6)])
        for client in clients:
            client.close.assert_called_once_with()

    def test_open_live_terminal_uses_current_shell_parameters_and_zero_timeout(self):
        client = MagicMock()
        channel = client.invoke_shell.return_value

        with patch("web_terminal.services.open_ssh_client", return_value=client):
            connection = services.open_live_terminal(self.make_host(), cols=132, rows=48)

        self.assertIsInstance(connection, services.LiveTerminalConnection)
        self.assertIs(connection.client, client)
        self.assertIs(connection.channel, channel)
        client.invoke_shell.assert_called_once_with(term="xterm", width=132, height=48)
        channel.settimeout.assert_called_once_with(0.0)

    def test_open_live_terminal_closes_client_and_translates_shell_error(self):
        client = MagicMock()
        client.invoke_shell.side_effect = RuntimeError("channel unavailable")

        with patch("web_terminal.services.open_ssh_client", return_value=client):
            with self.assertRaises(services.TerminalConnectionError) as raised:
                services.open_live_terminal(self.make_host())

        self.assertEqual(str(raised.exception), "SSH \u4f1a\u8bdd\u521b\u5efa\u5931\u8d25\uff1achannel unavailable")
        client.close.assert_called_once_with()

    def test_live_connection_command_uses_thirty_second_read_timeout(self):
        channel = MagicMock(closed=False)
        connection = services.LiveTerminalConnection(MagicMock(), channel)

        with patch.object(connection, "read_available", return_value="result") as read_available:
            result = connection.send_command("whoami")

        self.assertEqual(result, "result")
        channel.send.assert_called_once_with("whoami\n")
        read_available.assert_called_once_with(timeout=30.0)

    def test_live_connection_normalizes_output_and_translates_closed_send(self):
        channel = MagicMock(closed=False)
        connection = services.LiveTerminalConnection(MagicMock(), channel)

        with patch.object(connection, "read_available_raw", return_value="a\r\nb\rc\n"):
            self.assertEqual(connection.read_available(), "a\nb\nc")

        channel.closed = True
        with self.assertRaises(services.TerminalConnectionError) as raised:
            connection.send_data("pwd")
        self.assertEqual(str(raised.exception), "SSH \u4f1a\u8bdd\u5df2\u5173\u95ed\uff0c\u8bf7\u91cd\u65b0\u8fde\u63a5\u4e3b\u673a\u3002")


    def test_connections_can_be_imported_before_services_package(self):
        environment = os.environ.copy()
        environment.setdefault("DJANGO_SETTINGS_MODULE", "ops_tool.settings")
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import django; "
                    "django.setup(); "
                    "import web_terminal.services.connections; "
                    "print('connections import OK')"
                ),
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )

        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertIn("connections import OK", probe.stdout)

    def test_connection_symbols_report_the_new_implementation_module(self):
        self.assertEqual(
            services.TerminalConnectionError.__module__,
            "web_terminal.services.errors",
        )
        for name in (
            "LiveTerminalConnection",
            "open_live_terminal",
            "open_ssh_client",
            "should_retry_ssh_connect_error",
            "load_private_key",
            "normalize_terminal_output",
        ):
            with self.subTest(name=name):
                self.assertEqual(getattr(services, name).__module__, "web_terminal.services.connections")
