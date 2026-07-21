import asyncio
import inspect
import socket
import threading
import time
from unittest.mock import patch

import asyncssh
import paramiko
import pyotp
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TransactionTestCase

from accounts.models import UserProfile
from host_management.models import HostGroup, ManagedHost
from system_management.services import FEATURE_PERMISSION_CODE_BY_KEY, PAGE_ACTION_PERMISSION_CODE_BY_KEY, ensure_feature_permissions


async def call_in_event_loop(method, *args):
    value = method(*args)
    if inspect.isawaitable(value):
        return await value
    return value


def free_tcp_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class SshGatewayAuthAndAssetTests(TransactionTestCase):
    def setUp(self):
        ensure_feature_permissions()
        self.permission = Permission.objects.get(codename=PAGE_ACTION_PERMISSION_CODE_BY_KEY[("hosts", "terminal")])
        self.page_permission = Permission.objects.get(codename=FEATURE_PERMISSION_CODE_BY_KEY["hosts"])
        self.user = get_user_model().objects.create_user(username="operator", password="UserPass123")
        self.user.user_permissions.add(self.page_permission, self.permission)

    def test_parse_gateway_username_supports_menu_and_direct_modes(self):
        from web_terminal.gateway.auth import parse_gateway_username

        self.assertEqual(parse_gateway_username("operator").username, "operator")
        parsed = parse_gateway_username("operator#42")
        self.assertEqual(parsed.username, "operator")
        self.assertEqual(parsed.host_id, 42)
        self.assertTrue(parsed.direct_mode)

    def test_authenticate_platform_user_requires_password_permission_and_totp(self):
        from web_terminal.gateway.auth import GatewayAuthError, authenticate_platform_user

        secret = pyotp.random_base32()
        UserProfile.objects.create(user=self.user, totp_secret=secret, totp_enabled=True)

        with self.assertRaisesMessage(GatewayAuthError, "验证码"):
            authenticate_platform_user("operator", "UserPass123")

        authenticated = authenticate_platform_user("operator", "UserPass123", totp_code=pyotp.TOTP(secret).now())
        self.assertEqual(authenticated.id, self.user.id)

        self.user.user_permissions.clear()
        with self.assertRaisesMessage(GatewayAuthError, "SSH 网关权限"):
            authenticate_platform_user("operator", "UserPass123", totp_code=pyotp.TOTP(secret).now())

    def test_keyboard_interactive_prompt_skips_totp_when_two_factor_disabled(self):
        from web_terminal.gateway.server import GatewaySSHServer

        UserProfile.objects.create(user=self.user, totp_secret=pyotp.random_base32(), totp_enabled=False)
        server = GatewaySSHServer()

        challenge = server.get_kbdint_challenge("operator", "", "")
        prompts = challenge[3]

        self.assertEqual(prompts, [("Password: ", False)])
        self.assertTrue(asyncio.run(call_in_event_loop(server.validate_kbdint_response, "operator", ["UserPass123"])))
        self.assertEqual(server.user.id, self.user.id)

    def test_keyboard_interactive_prompts_totp_after_valid_password_when_enabled(self):
        from web_terminal.gateway.server import GatewaySSHServer

        secret = pyotp.random_base32()
        UserProfile.objects.create(user=self.user, totp_secret=secret, totp_enabled=True)
        server = GatewaySSHServer()

        initial_challenge = server.get_kbdint_challenge("operator", "", "")
        next_challenge = asyncio.run(call_in_event_loop(server.validate_kbdint_response, "operator", ["UserPass123"]))

        self.assertEqual(initial_challenge[3], [("Password: ", False)])
        self.assertEqual(next_challenge[3], [("Verification code: ", False)])
        self.assertTrue(asyncio.run(call_in_event_loop(server.validate_kbdint_response, "operator", [pyotp.TOTP(secret).now()])))
        self.assertEqual(server.user.id, self.user.id)

    def test_password_auth_validation_runs_inside_async_event_loop(self):
        from web_terminal.gateway.server import GatewaySSHServer

        server = GatewaySSHServer()

        self.assertTrue(asyncio.run(call_in_event_loop(server.validate_password, "operator", "UserPass123")))
        self.assertEqual(server.user.id, self.user.id)

    def test_shell_session_menu_starts_inside_async_event_loop(self):
        from web_terminal.gateway.auth import parse_gateway_username
        from web_terminal.gateway.server import GatewayShellSession

        class FakeChannel:
            def __init__(self):
                self.output = []

            def write(self, data):
                self.output.append(data)

        async def run_session():
            channel = FakeChannel()
            session = GatewayShellSession(user=self.user, parsed_username=parse_gateway_username("operator"))
            session.connection_made(channel)
            self.assertTrue(session.shell_requested())
            self.assertEqual(channel.output, [])
            session.session_started()
            for _attempt in range(20):
                if channel.output:
                    return "".join(channel.output)
                await asyncio.sleep(0.05)
            return ""

        output = asyncio.run(run_session())

        self.assertIn("asset> ", output)

    def test_gateway_host_selector_supports_index_id_name_and_ip(self):
        from web_terminal.gateway.assets import resolve_gateway_host_selector

        group = HostGroup.objects.create(name="default")
        ManagedHost.objects.create(name="win-01", group=group, private_ip="10.0.0.7", os="windows", login_user="Administrator")
        linux = ManagedHost.objects.create(name="host-10", group=group, private_ip="192.168.142.30", login_user="root")

        self.assertEqual(resolve_gateway_host_selector(self.user, "1").id, linux.id)
        self.assertEqual(resolve_gateway_host_selector(self.user, str(linux.id)).id, linux.id)
        self.assertEqual(resolve_gateway_host_selector(self.user, "host-10").id, linux.id)
        self.assertEqual(resolve_gateway_host_selector(self.user, "192.168.142.30").id, linux.id)
        self.assertEqual(resolve_gateway_host_selector(self.user, "192.168.142.30:22").id, linux.id)

    def test_menu_invalid_selector_keeps_gateway_session_open(self):
        from web_terminal.gateway.auth import parse_gateway_username
        from web_terminal.gateway.server import GatewayShellSession

        class FakeChannel:
            def __init__(self):
                self.output = []
                self.closed = False

            def write(self, data):
                self.output.append(data)

            def exit(self, exit_code):
                self.closed = True

            def close(self):
                self.closed = True

        channel = FakeChannel()
        session = GatewayShellSession(user=self.user, parsed_username=parse_gateway_username("operator"))
        session.connection_made(channel)
        session._handle_menu_input("does-not-exist\n")

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and "asset> " not in "".join(channel.output):
            time.sleep(0.05)

        output = "".join(channel.output)
        self.assertIn("连接失败", output)
        self.assertIn("asset> ", output)
        self.assertFalse(channel.closed)

    def test_gateway_accepts_paramiko_shell_after_keyboard_interactive_auth(self):
        from web_terminal.gateway.server import GatewaySFTPServer, GatewaySSHServer, gateway_stream_session

        port = free_tcp_port()
        ready = threading.Event()
        holder = {}
        loop = asyncio.new_event_loop()

        async def run_server():
            server = await asyncssh.create_server(
                GatewaySSHServer,
                "127.0.0.1",
                port,
                server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
                session_factory=gateway_stream_session,
                sftp_factory=GatewaySFTPServer,
                allow_scp=True,
                line_editor=False,
            )
            holder["server"] = server
            ready.set()
            await server.wait_closed()

        def server_thread():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_server())

        thread = threading.Thread(target=server_thread, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(timeout=5), "SSH gateway test server did not start")

        transport = paramiko.Transport(("127.0.0.1", port))
        try:
            transport.start_client(timeout=5)

            def keyboard_interactive(_title, _instructions, prompts):
                return ["UserPass123" for _prompt, _echo in prompts]

            transport.auth_interactive("operator", keyboard_interactive)
            self.assertTrue(transport.is_authenticated())

            channel = transport.open_session(timeout=5)
            channel.get_pty(term="xterm", width=100, height=30)
            channel.invoke_shell()

            output = ""
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and "asset> " not in output:
                if channel.recv_ready():
                    output += channel.recv(4096).decode("utf-8", "replace")
                    continue
                time.sleep(0.05)

            self.assertIn("asset> ", output)
            channel.close()

            sftp = paramiko.SFTPClient.from_transport(transport)
            try:
                self.assertEqual(sftp.listdir("/"), ["hosts"])
                self.assertEqual(sftp.listdir("/hosts"), [])
            finally:
                sftp.close()
        finally:
            transport.close()
            server = holder.get("server")
            if server is not None:
                loop.call_soon_threadsafe(server.close)
            thread.join(timeout=5)
            loop.close()

    def test_gateway_target_shell_input_runs_outside_async_event_loop(self):
        from web_terminal.gateway.server import GatewaySFTPServer, GatewaySSHServer, gateway_stream_session

        group = HostGroup.objects.create(name="default")
        host = ManagedHost.objects.create(name="api-01", group=group, private_ip="10.0.0.8", login_user="root")

        class FakeTargetChannel:
            closed = False

            def exit_status_ready(self):
                return False

        class FakeLiveConnection:
            def __init__(self):
                self.channel = FakeTargetChannel()
                self.sent = []

            def read_available_raw(self, timeout=0, idle_timeout=0):
                return "target$ "

            def read_raw(self):
                time.sleep(0.03)
                return ""

            def send_data(self, data):
                self.sent.append(data)

            def resize(self, cols, rows):
                pass

            def close(self):
                self.channel.closed = True

        fake_connection = FakeLiveConnection()
        port = free_tcp_port()
        ready = threading.Event()
        holder = {}
        loop = asyncio.new_event_loop()

        async def run_server():
            server = await asyncssh.create_server(
                GatewaySSHServer,
                "127.0.0.1",
                port,
                server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
                session_factory=gateway_stream_session,
                sftp_factory=GatewaySFTPServer,
                allow_scp=True,
                line_editor=False,
            )
            holder["server"] = server
            ready.set()
            await server.wait_closed()

        def server_thread():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_server())

        with patch("web_terminal.gateway.server.open_live_terminal", return_value=fake_connection):
            thread = threading.Thread(target=server_thread, daemon=True)
            thread.start()
            self.assertTrue(ready.wait(timeout=5), "SSH gateway test server did not start")

            transport = paramiko.Transport(("127.0.0.1", port))
            sftp = None
            try:
                transport.start_client(timeout=5)

                def keyboard_interactive(_title, _instructions, prompts):
                    return ["UserPass123" for _prompt, _echo in prompts]

                transport.auth_interactive("operator", keyboard_interactive)
                channel = transport.open_session(timeout=5)
                channel.get_pty(term="xterm", width=100, height=30)
                channel.invoke_shell()

                output = ""
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and "asset> " not in output:
                    if channel.recv_ready():
                        output += channel.recv(4096).decode("utf-8", "replace")
                        continue
                    time.sleep(0.05)
                self.assertIn("asset> ", output)

                channel.send(f"{host.id}\n")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and "target$ " not in output:
                    if channel.recv_ready():
                        output += channel.recv(4096).decode("utf-8", "replace")
                        continue
                    time.sleep(0.05)
                self.assertIn("target$ ", output)

                channel.send("la\r")
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not fake_connection.sent:
                    if channel.recv_ready():
                        output += channel.recv(4096).decode("utf-8", "replace")
                    time.sleep(0.05)

                self.assertEqual(len(fake_connection.sent), 1)
                self.assertEqual(fake_connection.sent[0].strip(), "la")
                self.assertNotIn("SSH gateway input failed", output)
                self.assertFalse(channel.closed)

                channel.send("cd /op\t")
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and len(fake_connection.sent) < 2:
                    if channel.recv_ready():
                        output += channel.recv(4096).decode("utf-8", "replace")
                    time.sleep(0.05)

                self.assertEqual(fake_connection.sent[-1], "cd /op\t")
            finally:
                transport.close()
                time.sleep(0.2)
                server = holder.get("server")
                if server is not None:
                    loop.call_soon_threadsafe(server.close)
                thread.join(timeout=5)
                loop.close()

    def test_menu_mode_returns_to_asset_menu_when_target_shell_exits(self):
        from web_terminal.gateway.server import GatewaySFTPServer, GatewaySSHServer, gateway_stream_session

        group = HostGroup.objects.create(name="default")
        host = ManagedHost.objects.create(name="api-01", group=group, private_ip="10.0.0.8", login_user="root")

        class FakeTargetChannel:
            def __init__(self):
                self.closed = False

            def exit_status_ready(self):
                return False

        class FakeLiveConnection:
            def __init__(self):
                self.channel = FakeTargetChannel()
                self.sent = []
                self.logout_pending = False

            def read_available_raw(self, timeout=0, idle_timeout=0):
                return "target$ "

            def read_raw(self):
                if self.logout_pending:
                    self.logout_pending = False
                    self.channel.closed = True
                    return "logout\r\n"
                time.sleep(0.03)
                return ""

            def send_data(self, data):
                self.sent.append(data)
                if data.strip() == "exit":
                    self.logout_pending = True

            def resize(self, cols, rows):
                pass

            def close(self):
                self.channel.closed = True

        fake_connection = FakeLiveConnection()
        port = free_tcp_port()
        ready = threading.Event()
        holder = {}
        loop = asyncio.new_event_loop()

        async def run_server():
            server = await asyncssh.create_server(
                GatewaySSHServer,
                "127.0.0.1",
                port,
                server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
                session_factory=gateway_stream_session,
                sftp_factory=GatewaySFTPServer,
                allow_scp=True,
                line_editor=False,
            )
            holder["server"] = server
            ready.set()
            await server.wait_closed()

        def server_thread():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_server())

        with patch("web_terminal.gateway.server.open_live_terminal", return_value=fake_connection):
            thread = threading.Thread(target=server_thread, daemon=True)
            thread.start()
            self.assertTrue(ready.wait(timeout=5), "SSH gateway test server did not start")

            transport = paramiko.Transport(("127.0.0.1", port))
            try:
                transport.start_client(timeout=5)

                def keyboard_interactive(_title, _instructions, prompts):
                    return ["UserPass123" for _prompt, _echo in prompts]

                transport.auth_interactive("operator", keyboard_interactive)
                channel = transport.open_session(timeout=5)
                channel.get_pty(term="xterm", width=100, height=30)
                channel.invoke_shell()

                output = ""
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and "asset> " not in output:
                    if channel.recv_ready():
                        output += channel.recv(4096).decode("utf-8", "replace")
                        continue
                    time.sleep(0.05)
                self.assertIn("asset> ", output)

                channel.send(f"{host.id}\n")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and "target$ " not in output:
                    if channel.recv_ready():
                        output += channel.recv(4096).decode("utf-8", "replace")
                        continue
                    time.sleep(0.05)
                self.assertIn("target$ ", output)

                sftp = paramiko.SFTPClient.from_transport(transport)
                self.assertEqual(sftp.listdir("/"), ["hosts"])

                output = ""
                channel.send("exit\n")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and "asset> " not in output:
                    if channel.recv_ready():
                        output += channel.recv(4096).decode("utf-8", "replace")
                        continue
                    time.sleep(0.05)

                self.assertIn("SSH 会话已关闭", output)
                self.assertIn("asset> ", output)
                self.assertFalse(channel.closed)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not sftp.get_channel().closed:
                    time.sleep(0.05)
                self.assertTrue(sftp.get_channel().closed)
            finally:
                try:
                    if sftp is not None:
                        sftp.close()
                except Exception:
                    pass
                transport.close()
                time.sleep(0.2)
                server = holder.get("server")
                if server is not None:
                    loop.call_soon_threadsafe(server.close)
                thread.join(timeout=5)
                loop.close()

    def test_resolve_gateway_host_rejects_windows_hosts(self):
        from web_terminal.gateway.assets import GatewayAssetError, resolve_gateway_host

        group = HostGroup.objects.create(name="default")
        linux = ManagedHost.objects.create(name="api-01", group=group, private_ip="10.0.0.8", login_user="root")
        windows = ManagedHost.objects.create(name="win-01", group=group, private_ip="10.0.0.9", os="windows", login_user="Administrator")

        self.assertEqual(resolve_gateway_host(self.user, linux.id).id, linux.id)
        with self.assertRaisesMessage(GatewayAssetError, "Windows"):
            resolve_gateway_host(self.user, windows.id)
