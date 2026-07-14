import subprocess
import sys
import textwrap
from pathlib import Path

from django.test import SimpleTestCase

from .. import services


class RemoteFileParserIsolationTests(SimpleTestCase):
    def test_file_parsers_load_without_connection_or_django_model_modules(self):
        backend_dir = Path(__file__).resolve().parents[2]
        probe = textwrap.dedent(
            f"""
            import importlib
            import sys
            from pathlib import Path
            from types import ModuleType

            backend_dir = Path({str(backend_dir)!r})
            web_terminal = ModuleType("web_terminal")
            web_terminal.__path__ = [str(backend_dir / "web_terminal")]
            services = ModuleType("web_terminal.services")
            services.__path__ = [str(backend_dir / "web_terminal" / "services")]
            sys.modules["web_terminal"] = web_terminal
            sys.modules["web_terminal.services"] = services

            module = importlib.import_module("web_terminal.services.file_parsers")
            assert module.TerminalConnectionError.__module__ == "web_terminal.services.errors"
            assert "web_terminal.services.connections" not in sys.modules
            assert "host_management.models" not in sys.modules
            print("isolated parser import OK")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("isolated parser import OK", result.stdout)


class RemoteFileParserCharacterizationTests(SimpleTestCase):
    def test_find_entries_skip_malformed_lines_and_sort_naturally(self):
        output = (
            "dir\td\t2026/07/14 10:00:00\t0\tdrwxr-xr-x\troot\troot\n"
            "file10\tf\t2026/07/14 10:01:00\t10\t-rw-r--r--\tapp\tapp\n"
            "malformed\n"
            "file2\tf\t2026/07/14 10:02:00\t2\t-rw-------\tapp\tapp\n"
        )

        self.assertEqual(
            services.parse_remote_find_entries("/srv", output),
            [
                {
                    "name": "..", "type": "directory", "modifiedAt": "", "size": 0,
                    "permissions": "", "owner": "", "group": "", "path": "/",
                },
                {
                    "name": "dir", "type": "directory", "modifiedAt": "2026/07/14 10:00",
                    "size": 0, "permissions": "drwxr-xr-x", "owner": "root",
                    "group": "root", "path": "/srv/dir",
                },
                {
                    "name": "file2", "type": "file", "modifiedAt": "2026/07/14 10:02",
                    "size": 2, "permissions": "-rw-------", "owner": "app",
                    "group": "app", "path": "/srv/file2",
                },
                {
                    "name": "file10", "type": "file", "modifiedAt": "2026/07/14 10:01",
                    "size": 10, "permissions": "-rw-r--r--", "owner": "app",
                    "group": "app", "path": "/srv/file10",
                },
            ],
        )

    def test_normalizers_preserve_current_values_and_errors(self):
        valid_cases = [
            (services.normalize_remote_file_path, " /srv/app ", "/srv/app"),
            (services.normalize_remote_file_name, "folder\\report.txt", "report.txt"),
            (services.normalize_remote_relative_file_path, "a\\b/c.txt", "a/b/c.txt"),
            (services.normalize_remote_file_octal_mode, "755", "0755"),
        ]
        for function, value, expected in valid_cases:
            with self.subTest(function=function.__name__, value=value):
                self.assertEqual(function(value), expected)

        invalid_cases = [
            (services.normalize_remote_file_path, "bad\npath"),
            (services.normalize_remote_file_name, ".."),
            (services.normalize_remote_relative_file_path, "../secret"),
            (services.normalize_remote_file_octal_mode, "888"),
        ]
        for function, value in invalid_cases:
            with self.subTest(function=function.__name__, value=value):
                with self.assertRaises(services.TerminalConnectionError):
                    function(value)
