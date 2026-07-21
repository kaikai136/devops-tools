from django.test import RequestFactory, TestCase, override_settings


class SshGatewayConfigTests(TestCase):
    @override_settings(
        SSH_GATEWAY_ENABLED=True,
        SSH_GATEWAY_BIND_HOST="127.0.0.1",
        SSH_GATEWAY_PORT=22022,
        SSH_GATEWAY_PUBLIC_HOST="ops.example.com",
        SSH_GATEWAY_PUBLIC_PORT=2022,
        SSH_GATEWAY_HOST_KEY_PATH="/tmp/test-gateway-key",
    )
    def test_connection_info_uses_deploy_time_public_port_and_host(self):
        from web_terminal.gateway.config import gateway_connection_info

        payload = gateway_connection_info("operator", host_id=37)

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["listen"]["host"], "127.0.0.1")
        self.assertEqual(payload["listen"]["port"], 22022)
        self.assertEqual(payload["public"]["host"], "ops.example.com")
        self.assertEqual(payload["public"]["port"], 2022)
        self.assertEqual(payload["commands"]["sshMenu"], "ssh -p 2022 operator@ops.example.com")
        self.assertEqual(payload["commands"]["sshDirect"], "ssh -p 2022 operator#37@ops.example.com")
        self.assertEqual(payload["commands"]["sftpMenu"], "sftp -P 2022 operator@ops.example.com")
        self.assertEqual(payload["commands"]["sftpDirect"], "sftp -P 2022 operator#37@ops.example.com")
        self.assertEqual(payload["commands"]["scpUpload"], "scp -P 2022 ./local-file operator#37@ops.example.com:/tmp/")
        self.assertEqual(payload["commands"]["scpDownload"], "scp -P 2022 operator#37@ops.example.com:/tmp/remote-file ./")

    @override_settings(
        SSH_GATEWAY_ENABLED=False,
        SSH_GATEWAY_PUBLIC_HOST="",
        SSH_GATEWAY_PUBLIC_PORT=2222,
        SSH_GATEWAY_PORT=2222,
    )
    def test_connection_info_falls_back_to_request_host_without_port(self):
        from web_terminal.gateway.config import gateway_connection_info

        request = RequestFactory().get("/api/web-terminal/ssh-gateway/connection-info/", HTTP_HOST="127.0.0.1:8001")
        payload = gateway_connection_info("admin", request=request)

        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["public"]["host"], "127.0.0.1")
        self.assertEqual(payload["public"]["port"], 2222)
        self.assertEqual(payload["commands"]["sshMenu"], "ssh -p 2222 admin@127.0.0.1")
