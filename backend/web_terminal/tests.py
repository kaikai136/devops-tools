from django.test import SimpleTestCase

from .services import (
    TerminalConnectionError,
    normalize_remote_file_octal_mode,
    normalize_remote_file_owner,
    parse_remote_stat_output,
)


class RemoteFilePropertiesTests(SimpleTestCase):
    def test_parse_remote_stat_output_returns_permission_details(self):
        payload = parse_remote_stat_output(
            "/root/.bash_profile",
            "regular file\t176\troot\troot\t0\t0\t644\t-rw-r--r--\t1782446272\t1685180888\t81a4\n",
        )

        self.assertEqual(payload["name"], ".bash_profile")
        self.assertEqual(payload["directory"], "/root")
        self.assertEqual(payload["type"], "file")
        self.assertEqual(payload["size"], 176)
        self.assertEqual(payload["owner"], "root")
        self.assertEqual(payload["group"], "root")
        self.assertEqual(payload["octalMode"], "0644")
        self.assertEqual(payload["permissions"], "-rw-r--r--")
        self.assertEqual(payload["special"], {"setuid": False, "setgid": False, "sticky": False})

    def test_parse_remote_stat_output_supports_directory_and_special_bits(self):
        payload = parse_remote_stat_output(
            "/root/download_test",
            "directory\t4096\troot\troot\t0\t0\t1775\tdrwxrwxr-t\t1782446272\t1685180888\t43fd\n",
        )

        self.assertEqual(payload["type"], "directory")
        self.assertEqual(payload["octalMode"], "1775")
        self.assertTrue(payload["special"]["sticky"])

    def test_parse_remote_stat_output_falls_back_to_numeric_owner_group(self):
        payload = parse_remote_stat_output(
            "/root/webssh",
            "directory\t51\t\t\t0\t0\t755\tdrwxr-xr-x\t1782446272\t1685180888\t41ed\n",
        )

        self.assertEqual(payload["owner"], "0")
        self.assertEqual(payload["group"], "0")

    def test_owner_validation_rejects_risky_values(self):
        for value in ["", "root wheel", "root:wheel", "bad\nname", "bad\x00name"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_file_owner(value, "所有者")

    def test_octal_mode_validation(self):
        self.assertEqual(normalize_remote_file_octal_mode("644"), "0644")
        self.assertEqual(normalize_remote_file_octal_mode("1775"), "1775")
        for value in ["88", "999", "abcdef", "12345", "64a"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_file_octal_mode(value)
