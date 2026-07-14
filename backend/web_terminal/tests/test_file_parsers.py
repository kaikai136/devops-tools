from django.test import SimpleTestCase

from .. import services


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
