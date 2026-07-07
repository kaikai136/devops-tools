from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings


class FrontendServingTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.frontend_dist = Path(self.temp_dir.name)
        (self.frontend_dist / "index.html").write_text(
            "<!doctype html><html><body><div id=\"app\"></div></body></html>",
            encoding="utf-8",
        )
        (self.frontend_dist / "terminal.html").write_text(
            "<!doctype html><html><body><div id=\"terminal-app\"></div></body></html>",
            encoding="utf-8",
        )
        self.banner_bytes = b"\x89PNG\r\n\x1a\nbrand"
        (self.frontend_dist / "captain-banner.png").write_bytes(self.banner_bytes)
        self.static_root = self.frontend_dist / "static-root"
        self.static_root.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_root_serves_frontend_index(self):
        with override_settings(FRONTEND_DIST_DIR=self.frontend_dist, STATIC_ROOT=self.static_root):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b'id="app"', b"".join(response.streaming_content))

    def test_terminal_html_serves_terminal_entry_with_querystring(self):
        with override_settings(FRONTEND_DIST_DIR=self.frontend_dist, STATIC_ROOT=self.static_root):
            response = self.client.get("/terminal.html?hostId=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="terminal-app"', b"".join(response.streaming_content))

    def test_frontend_route_falls_back_to_index(self):
        with override_settings(FRONTEND_DIST_DIR=self.frontend_dist, STATIC_ROOT=self.static_root):
            response = self.client.get("/hosts")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="app"', b"".join(response.streaming_content))

    def test_root_level_frontend_asset_serves_file(self):
        with override_settings(FRONTEND_DIST_DIR=self.frontend_dist, STATIC_ROOT=self.static_root):
            response = self.client.get("/captain-banner.png")

        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
            self.assertEqual(b"".join(response.streaming_content), self.banner_bytes)
        finally:
            response.close()

    def test_missing_frontend_dist_returns_not_found(self):
        with override_settings(FRONTEND_DIST_DIR=self.frontend_dist / "missing", STATIC_ROOT=self.static_root):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 404)
