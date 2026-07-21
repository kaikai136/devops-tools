import asyncio
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class SshGatewayServerTests(SimpleTestCase):
    def test_ensure_host_key_creates_and_reuses_private_key(self):
        from web_terminal.gateway.server import ensure_host_key

        key_path = Path(self._testMethodName + "-ssh-host-key")
        try:
            first = ensure_host_key(key_path)
            second = ensure_host_key(key_path)
            self.assertEqual(first, key_path)
            self.assertEqual(second, key_path)
            self.assertTrue(key_path.exists())
            self.assertGreater(key_path.stat().st_size, 0)
        finally:
            key_path.unlink(missing_ok=True)

    @override_settings(SSH_GATEWAY_BIND_HOST="127.0.0.1", SSH_GATEWAY_PORT=22022)
    def test_management_command_delegates_to_gateway_runner(self):
        with patch("web_terminal.management.commands.run_ssh_gateway.run_gateway_server") as runner:
            call_command("run_ssh_gateway")

        runner.assert_called_once()

    def test_gateway_runner_registers_shell_session_factory_with_sftp(self):
        from web_terminal.gateway.server import GatewaySFTPServer, gateway_stream_session, _run_gateway_server

        calls = {}

        class FakeServer:
            async def wait_closed(self):
                return None

        async def fake_create_server(*args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs
            return FakeServer()

        with patch("web_terminal.gateway.server.asyncssh.create_server", side_effect=fake_create_server):
            asyncio.run(_run_gateway_server("127.0.0.1", 2222, Path("host-key")))

        self.assertIs(calls["kwargs"]["session_factory"], gateway_stream_session)
        self.assertIs(calls["kwargs"]["sftp_factory"], GatewaySFTPServer)
        self.assertTrue(calls["kwargs"]["allow_scp"])
        self.assertFalse(calls["kwargs"]["line_editor"])
