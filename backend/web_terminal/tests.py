from django.test import SimpleTestCase
from unittest.mock import patch

from .consumers import CWD_MARKER_END, CWD_MARKER_START, strip_cwd_markers, strip_cwd_markers_with_pending
from .services import (
    TerminalConnectionError,
    create_remote_directory,
    create_remote_file,
    create_remote_symlink,
    normalize_remote_relative_file_path,
    normalize_remote_symlink_target,
    normalize_remote_file_octal_mode,
    normalize_remote_file_owner,
    parse_remote_stat_output,
    remote_file_properties_payload,
)


class RemoteFilePropertiesTests(SimpleTestCase):
    def test_strip_cwd_markers_extracts_path_and_keeps_visible_output(self):
        output, paths = strip_cwd_markers(f"before{CWD_MARKER_START}/opt{CWD_MARKER_END}after")

        self.assertEqual(output, "beforeafter")
        self.assertEqual(paths, ["/opt"])

    def test_strip_cwd_markers_supports_multiple_paths(self):
        output, paths = strip_cwd_markers(
            f"{CWD_MARKER_START}/root{CWD_MARKER_END}prompt{CWD_MARKER_START}/opt/app{CWD_MARKER_END}"
        )

        self.assertEqual(output, "prompt")
        self.assertEqual(paths, ["/root", "/opt/app"])

    def test_strip_cwd_markers_leaves_regular_output_unchanged(self):
        output, paths = strip_cwd_markers("regular terminal output\r\n")

        self.assertEqual(output, "regular terminal output\r\n")
        self.assertEqual(paths, [])

    def test_strip_cwd_markers_keeps_partial_marker_pending(self):
        output, paths, pending = strip_cwd_markers_with_pending(f"prompt{CWD_MARKER_START}/op")

        self.assertEqual(output, "prompt")
        self.assertEqual(paths, [])
        self.assertEqual(pending, f"{CWD_MARKER_START}/op")

        output, paths, pending = strip_cwd_markers_with_pending(pending + f"t{CWD_MARKER_END}next")
        self.assertEqual(output, "next")
        self.assertEqual(paths, ["/opt"])
        self.assertEqual(pending, "")

    def test_sftp_properties_payload_uses_resolved_owner_group_names(self):
        attrs = type(
            "Attrs",
            (),
            {
                "st_mode": 0o40755,
                "st_uid": 0,
                "st_gid": 0,
                "st_size": 8192,
                "st_mtime": 1782446272,
                "st_atime": 1781151803,
            },
        )()

        payload = remote_file_properties_payload("/etc", attrs, {"owner": "root", "group": "root"})

        self.assertEqual(payload["owner"], "root")
        self.assertEqual(payload["group"], "root")
        self.assertEqual(payload["uid"], 0)
        self.assertEqual(payload["gid"], 0)

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

    def test_relative_upload_path_validation(self):
        self.assertEqual(normalize_remote_relative_file_path("folder\\child/file.txt"), "folder/child/file.txt")
        for value in ["", "/tmp/file.txt", "../file.txt", "folder/../file.txt", "bad\nfile.txt", "bad\x00file.txt"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_relative_file_path(value)

    def test_symlink_target_validation(self):
        self.assertEqual(normalize_remote_symlink_target("/var/log/app.log"), "/var/log/app.log")
        for value in ["", "bad\npath", "bad\x00path"]:
            with self.subTest(value=value):
                with self.assertRaises(TerminalConnectionError):
                    normalize_remote_symlink_target(value)

    def test_create_remote_file_builds_safe_command(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new.txt"},
        ):
            payload = create_remote_file(object(), "/data", "new.txt")

        self.assertEqual(payload["path"], "/data/new.txt")
        self.assertIn("test -e /data/new.txt", run_command.call_args.args[1])
        self.assertIn(": > /data/new.txt", run_command.call_args.args[1])

    def test_create_remote_file_applies_requested_mode(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new.txt"},
        ):
            payload = create_remote_file(object(), "/data", "new.txt", "0644")

        self.assertEqual(payload["path"], "/data/new.txt")
        self.assertEqual(run_command.call_count, 2)
        self.assertIn(": > /data/new.txt", run_command.call_args_list[0].args[1])
        self.assertIn("chmod 0644 /data/new.txt", run_command.call_args_list[1].args[1])

    def test_create_remote_file_rejects_invalid_mode(self):
        with self.assertRaises(TerminalConnectionError):
            create_remote_file(object(), "/data", "new.txt", "999")

    def test_create_remote_directory_builds_safe_command(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new-folder"},
        ):
            payload = create_remote_directory(object(), "/data", "new-folder")

        self.assertEqual(payload["path"], "/data/new-folder")
        self.assertIn("mkdir /data/new-folder", run_command.call_args.args[1])

    def test_create_remote_directory_applies_requested_mode(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/new-folder"},
        ):
            payload = create_remote_directory(object(), "/data", "new-folder", "0755")

        self.assertEqual(payload["path"], "/data/new-folder")
        self.assertEqual(run_command.call_count, 2)
        self.assertIn("mkdir /data/new-folder", run_command.call_args_list[0].args[1])
        self.assertIn("chmod 0755 /data/new-folder", run_command.call_args_list[1].args[1])

    def test_create_remote_directory_rejects_invalid_mode(self):
        with self.assertRaises(TerminalConnectionError):
            create_remote_directory(object(), "/data", "new-folder", "12345")

    def test_create_remote_symlink_builds_safe_command(self):
        with patch("web_terminal.services.run_one_shot_ssh_command") as run_command, patch(
            "web_terminal.services.get_remote_file_properties",
            return_value={"path": "/data/app-link"},
        ):
            payload = create_remote_symlink(object(), "/data", "app-link", "/opt/app")

        self.assertEqual(payload["path"], "/data/app-link")
        self.assertIn("ln -s /opt/app /data/app-link", run_command.call_args.args[1])
