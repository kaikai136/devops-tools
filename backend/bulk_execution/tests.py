import json
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from host_management.models import HostGroup, ManagedHost
from system_management.services import ensure_feature_permissions

from .models import BulkExecutionResult, BulkExecutionTask
from .services import create_bulk_execution_task, run_bulk_execution_task


class BulkExecutionApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ops", password="secret")
        self.group = HostGroup.objects.create(name="prod", sort_order=10)
        self.linux = ManagedHost.objects.create(
            name="linux-ok",
            group=self.group,
            private_ip="10.0.0.11",
            port=2222,
            login_user="root",
            login_password="secret",
            verified=True,
            verify_status="verified",
            os="ubuntu",
        )
        self.key_host = ManagedHost.objects.create(
            name="linux-key",
            group=self.group,
            private_ip="10.0.0.12",
            login_user="deploy",
            private_key="-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----",
            verified=True,
            verify_status="verified",
            os="centos",
        )
        self.windows = ManagedHost.objects.create(
            name="windows",
            group=self.group,
            private_ip="10.0.0.13",
            login_user="Administrator",
            login_password="secret",
            verified=True,
            verify_status="verified",
            os="windows",
        )
        self.unverified = ManagedHost.objects.create(
            name="unverified",
            group=self.group,
            private_ip="10.0.0.14",
            login_user="root",
            login_password="secret",
            verified=False,
            verify_status="unverified",
            os="ubuntu",
        )
        self.no_credential = ManagedHost.objects.create(
            name="no-credential",
            group=self.group,
            private_ip="10.0.0.15",
            login_user="root",
            verified=True,
            verify_status="verified",
            os="debian",
        )

    def grant(self, *codenames):
        ensure_feature_permissions()
        self.user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        self.user = get_user_model().objects.get(id=self.user.id)
        self.client.force_login(self.user)

    def test_targets_return_only_verified_linux_hosts_with_ssh_credentials(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")

        response = self.client.get("/api/bulk-execution/targets/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload], [self.linux.id, self.key_host.id])
        self.assertEqual(payload[0]["name"], "linux-ok")
        self.assertEqual(payload[0]["groupName"], "prod")
        self.assertEqual(payload[0]["privateIp"], "10.0.0.11")
        self.assertEqual(payload[0]["port"], 2222)
        self.assertEqual(payload[0]["loginUser"], "root")

    def test_target_tree_requires_execute_permission(self):
        self.grant("access_bulkExecution")

        response = self.client.get("/api/bulk-execution/target-tree/")

        self.assertEqual(response.status_code, 403)

    def test_target_tree_returns_only_executable_targets_with_group_counts(self):
        parent = HostGroup.objects.create(name="parent", sort_order=1)
        child = HostGroup.objects.create(name="child", parent=parent, sort_order=1)
        empty = HostGroup.objects.create(name="empty", sort_order=2)
        child_host = ManagedHost.objects.create(
            name="child-linux",
            group=child,
            private_ip="10.0.1.11",
            login_user="root",
            login_password="secret",
            verified=True,
            verify_status="verified",
            os="ubuntu",
        )
        ManagedHost.objects.create(
            name="child-windows",
            group=child,
            private_ip="10.0.1.12",
            login_user="Administrator",
            login_password="secret",
            verified=True,
            verify_status="verified",
            os="windows",
        )
        ManagedHost.objects.create(
            name="empty-unverified",
            group=empty,
            private_ip="10.0.1.13",
            login_user="root",
            login_password="secret",
            verified=False,
            verify_status="unverified",
            os="ubuntu",
        )
        self.grant("access_bulkExecution", "action_bulkExecution_execute")

        response = self.client.get("/api/bulk-execution/target-tree/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload["targets"]], [self.linux.id, self.key_host.id, child_host.id])
        self.assertNotIn(self.windows.id, [item["id"] for item in payload["targets"]])
        roots = {group["label"]: group for group in payload["groups"]}
        self.assertEqual(roots["prod"]["count"], 2)
        self.assertEqual(roots["parent"]["count"], 1)
        self.assertEqual(roots["parent"]["children"][0]["label"], "child")
        self.assertEqual(roots["parent"]["children"][0]["count"], 1)
        self.assertNotIn("empty", roots)

    def test_create_task_requires_execute_permission_and_snapshots_only_executable_targets(self):
        self.grant("access_bulkExecution")

        denied = self.client.post(
            "/api/bulk-execution/tasks/",
            data={"targetIds": [self.linux.id], "command": "uptime"},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        self.grant("access_bulkExecution", "action_bulkExecution_execute")
        with patch("bulk_execution.views.start_bulk_execution_task") as start_task:
            response = self.client.post(
                "/api/bulk-execution/tasks/",
                data={"targetIds": [self.linux.id, self.windows.id, self.no_credential.id], "command": "  uptime  ", "name": "check uptime"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)
        task = BulkExecutionTask.objects.get()
        self.assertEqual(task.name, "check uptime")
        self.assertEqual(task.command, "uptime")
        self.assertEqual(task.execution_type, BulkExecutionTask.EXECUTION_SHELL)
        self.assertEqual(task.created_by, self.user)
        self.assertEqual(task.target_count, 1)
        self.assertEqual(task.results.count(), 1)
        result = task.results.get()
        self.assertEqual(result.host, self.linux)
        self.assertEqual(result.host_name, "linux-ok")
        self.assertEqual(result.host_ip, "10.0.0.11")
        self.assertEqual(result.login_user, "root")
        start_task.assert_called_once_with(task.id)

    def test_create_task_requires_task_name(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")

        with patch("bulk_execution.views.start_bulk_execution_task") as start_task:
            response = self.client.post(
                "/api/bulk-execution/tasks/",
                data={"targetIds": [self.linux.id], "command": "uptime", "name": "  "},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(BulkExecutionTask.objects.exists())
        start_task.assert_not_called()

    def test_create_task_accepts_playbook_execution_type(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")
        playbook = "- hosts: all\n  tasks:\n    - ansible.builtin.ping:\n"

        with patch("bulk_execution.views.start_bulk_execution_task"):
            response = self.client.post(
                "/api/bulk-execution/tasks/",
                data={"targetIds": [self.linux.id], "command": playbook, "executionType": "playbook", "name": "ping playbook"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["executionType"], "playbook")
        task = BulkExecutionTask.objects.get(name="ping playbook")
        self.assertEqual(task.execution_type, BulkExecutionTask.EXECUTION_PLAYBOOK)

    def test_create_task_accepts_long_playbook_scripts(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")
        playbook = "- hosts: all\n  gather_facts: false\n  tasks:\n    - name: Long playbook\n      ansible.builtin.debug:\n        msg: '" + ("x" * 5000) + "'\n"

        with patch("bulk_execution.views.start_bulk_execution_task"):
            response = self.client.post(
                "/api/bulk-execution/tasks/",
                data={"targetIds": [self.linux.id], "command": playbook, "executionType": "playbook", "name": "long playbook"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)
        task = BulkExecutionTask.objects.get(name="long playbook")
        self.assertEqual(task.execution_type, BulkExecutionTask.EXECUTION_PLAYBOOK)
        self.assertEqual(task.command, playbook)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="bulk-upload-test-"))
    def test_create_file_upload_task_accepts_multipart_file_and_selected_targets(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")
        upload = SimpleUploadedFile("deploy.txt", b"hello from ops\n", content_type="text/plain")

        with patch("bulk_execution.views.start_bulk_execution_task") as start_task:
            response = self.client.post(
                "/api/bulk-execution/tasks/",
                data={
                    "targetIds": json.dumps([self.linux.id, self.windows.id]),
                    "remoteDirectory": "/tmp/",
                    "name": "deploy file",
                    "file": upload,
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["executionType"], "file_upload")
        self.assertEqual(payload["remoteDirectory"], "/tmp")
        self.assertEqual(payload["uploadFilename"], "deploy.txt")
        self.assertEqual(payload["uploadSize"], 15)
        task = BulkExecutionTask.objects.get(name="deploy file")
        self.assertEqual(task.execution_type, BulkExecutionTask.EXECUTION_FILE_UPLOAD)
        self.assertEqual(task.command, "Upload deploy.txt to /tmp/deploy.txt")
        self.assertEqual(task.remote_directory, "/tmp")
        self.assertEqual(task.upload_filename, "deploy.txt")
        self.assertEqual(task.upload_size, 15)
        self.assertTrue(task.upload_file)
        self.assertEqual(task.target_count, 1)
        self.assertEqual(task.results.get().host, self.linux)
        start_task.assert_called_once_with(task.id)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="bulk-upload-name-test-"))
    def test_create_file_upload_task_requires_task_name(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")
        upload = SimpleUploadedFile("deploy.txt", b"hello from ops\n", content_type="text/plain")

        with patch("bulk_execution.views.start_bulk_execution_task") as start_task:
            response = self.client.post(
                "/api/bulk-execution/tasks/",
                data={
                    "targetIds": json.dumps([self.linux.id]),
                    "remoteDirectory": "/tmp/",
                    "file": upload,
                    "name": " ",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(BulkExecutionTask.objects.exists())
        start_task.assert_not_called()

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="bulk-upload-multi-test-"))
    def test_create_file_upload_task_accepts_multiple_files_and_exposes_transfer_details(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute", "action_bulkExecution_refresh")
        deploy = SimpleUploadedFile("deploy.txt", b"deploy\n", content_type="text/plain")
        config = SimpleUploadedFile("config.yml", b"name: api\n", content_type="text/yaml")

        with patch("bulk_execution.views.start_bulk_execution_task") as start_task:
            response = self.client.post(
                "/api/bulk-execution/tasks/",
                data={
                    "executionType": "file_upload",
                    "targetIds": json.dumps([self.linux.id, self.windows.id]),
                    "remoteDirectory": "/opt/app/",
                    "name": "bundle upload",
                    "overwrite": "true",
                    "files": [deploy, config],
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["executionType"], "file_upload")
        self.assertEqual(payload["remoteDirectory"], "/opt/app")
        self.assertEqual(payload["uploadFilename"], "2 files")
        self.assertEqual(payload["uploadSize"], 17)
        task = BulkExecutionTask.objects.get()
        self.assertEqual(task.upload_files.count(), 2)
        self.assertEqual(task.transfer_items.count(), 2)
        self.assertEqual([item.filename for item in task.upload_files.order_by("id")], ["deploy.txt", "config.yml"])
        self.assertEqual([item.remote_path for item in task.upload_files.order_by("id")], ["/opt/app/deploy.txt", "/opt/app/config.yml"])
        start_task.assert_called_once_with(task.id)

        detail = self.client.get(f"/api/bulk-execution/tasks/{task.id}/")
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.json()
        self.assertEqual([item["filename"] for item in detail_payload["uploadFiles"]], ["deploy.txt", "config.yml"])
        self.assertEqual([item["remotePath"] for item in detail_payload["uploadFiles"]], ["/opt/app/deploy.txt", "/opt/app/config.yml"])
        self.assertEqual([item["remotePath"] for item in detail_payload["results"][0]["transfers"]], ["/opt/app/deploy.txt", "/opt/app/config.yml"])

    def test_upload_check_reports_connected_targets_unreachable_targets_and_duplicate_files(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")

        def fake_inspect(host, remote_directory, filenames):
            if host.id == self.key_host.id:
                return {"connected": False, "presentFiles": [], "error": "SSH connection failed"}
            self.assertEqual(remote_directory, "/opt/app")
            self.assertEqual(filenames, ["deploy.txt", "config.yml"])
            return {"connected": True, "presentFiles": ["deploy.txt"], "error": ""}

        with patch("bulk_execution.services.inspect_bulk_upload_target", side_effect=fake_inspect, create=True):
            response = self.client.post(
                "/api/bulk-execution/uploads/check/",
                data={
                    "targetIds": [self.linux.id, self.key_host.id, self.windows.id],
                    "remoteDirectory": "/opt/app/",
                    "filenames": ["deploy.txt", "config.yml"],
                    "totalSize": 16,
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([target["id"] for target in payload["connectedTargets"]], [self.linux.id])
        self.assertEqual([target["id"] for target in payload["unreachableTargets"]], [self.key_host.id])
        self.assertEqual(payload["unreachableTargets"][0]["error"], "SSH connection failed")
        self.assertEqual(payload["usableTargetIds"], [self.linux.id])
        self.assertEqual(
            payload["duplicateFiles"],
            [
                {
                    "targetId": self.linux.id,
                    "hostName": "linux-ok",
                    "hostIp": "10.0.0.11",
                    "filenames": ["deploy.txt"],
                }
            ],
        )

    def test_create_file_upload_task_requires_uploaded_file(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")

        response = self.client.post(
            "/api/bulk-execution/tasks/",
            data={"targetIds": json.dumps([self.linux.id]), "remoteDirectory": "/tmp/", "executionType": "file_upload"},
        )

        self.assertEqual(response.status_code, 400)

    def test_create_task_rejects_unknown_execution_type(self):
        self.grant("access_bulkExecution", "action_bulkExecution_execute")

        response = self.client.post(
            "/api/bulk-execution/tasks/",
            data={"targetIds": [self.linux.id], "command": "uptime", "executionType": "python", "name": "unknown execution"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_task_history_detail_cancel_and_delete_endpoints(self):
        self.grant(
            "access_bulkExecution",
            "action_bulkExecution_execute",
            "action_bulkExecution_refresh",
            "action_bulkExecution_cancel",
            "action_bulkExecution_delete",
        )
        with patch("bulk_execution.views.start_bulk_execution_task"):
            create = self.client.post(
                "/api/bulk-execution/tasks/",
                data={"targetIds": [self.linux.id], "command": "hostname", "name": "history detail"},
                content_type="application/json",
            )
        task_id = create.json()["id"]

        listing = self.client.get("/api/bulk-execution/tasks/?keyword=hostname&page=1&pageSize=10")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)

        detail = self.client.get(f"/api/bulk-execution/tasks/{task_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["results"][0]["status"], "pending")

        canceled = self.client.post(f"/api/bulk-execution/tasks/{task_id}/cancel/")
        self.assertEqual(canceled.status_code, 200)
        self.assertTrue(canceled.json()["cancelRequested"])
        self.assertEqual(canceled.json()["status"], "canceled")

        deleted = self.client.delete(f"/api/bulk-execution/tasks/{task_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(BulkExecutionTask.objects.filter(id=task_id).exists())


@override_settings(BULK_EXECUTION_FORKS=10, BULK_EXECUTION_TIMEOUT_SECONDS=300)
class BulkExecutionRunnerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="runner")
        self.group = HostGroup.objects.create(name="runner", sort_order=10)
        self.host = ManagedHost.objects.create(
            name="api-01",
            group=self.group,
            private_ip="10.1.0.10",
            port=22,
            login_user="root",
            login_password="secret",
            verified=True,
            verify_status="verified",
            os="ubuntu",
        )

    def test_runner_events_update_result_output_and_task_counts(self):
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "hostname", "name": "hostnames"})

        def fake_run(**kwargs):
            self.assertEqual(kwargs["module"], "ansible.builtin.shell")
            self.assertEqual(kwargs["module_args"], "hostname")
            self.assertEqual(kwargs["host_pattern"], "all")
            self.assertEqual(kwargs["forks"], 1)
            self.assertEqual(kwargs["timeout"], 300)
            self.assertFalse(kwargs["cancel_callback"]())
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
            kwargs["event_handler"](
                {
                    "event": "runner_on_ok",
                    "event_data": {"host": "host_1", "res": {"stdout": "api-01\n", "stderr": "", "rc": 0}},
                }
            )
            return SimpleNamespace(status="successful", rc=0)

        with patch("bulk_execution.services.run_ansible_shell", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        task.refresh_from_db()
        result = task.results.get()
        self.assertEqual(task.status, BulkExecutionTask.STATUS_COMPLETED)
        self.assertEqual(task.completed_count, 1)
        self.assertEqual(task.success_count, 1)
        self.assertEqual(task.failed_count, 0)
        self.assertEqual(result.status, BulkExecutionResult.STATUS_SUCCESS)
        self.assertEqual(result.stdout, "api-01\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.exit_code, 0)
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.finished_at)

    def test_playbook_task_runs_ansible_playbook_file(self):
        playbook = "- hosts: all\n  gather_facts: false\n  tasks:\n    - ansible.builtin.command: hostname\n"
        task = create_bulk_execution_task(
            self.user,
            {"targetIds": [self.host.id], "command": playbook, "name": "hostnames playbook", "executionType": "playbook"},
        )

        def fake_run(**kwargs):
            self.assertNotIn("module", kwargs)
            self.assertEqual(kwargs["playbook"], "playbook.yml")
            playbook_path = kwargs["private_data_dir"] + "/project/playbook.yml"
            with open(playbook_path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), playbook)
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
            kwargs["event_handler"](
                {"event": "runner_on_ok", "event_data": {"host": "host_1", "res": {"stdout": "api-01\n", "stderr": "", "rc": 0}}}
            )
            return SimpleNamespace(status="successful", rc=0)

        with patch("bulk_execution.services.run_ansible_playbook", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        task.refresh_from_db()
        self.assertEqual(task.status, BulkExecutionTask.STATUS_COMPLETED)
        self.assertIn("ok: [host_1]", task.results.get().stdout)
        self.assertIn("api-01", task.results.get().stdout)

    def test_playbook_task_records_ansible_style_log(self):
        playbook = "- hosts: all\n  gather_facts: false\n  tasks:\n    - name: Check hostname\n      ansible.builtin.command: hostname\n"
        task = create_bulk_execution_task(
            self.user,
            {"targetIds": [self.host.id], "command": playbook, "name": "ansible style log", "executionType": "playbook"},
        )

        def fake_run(**kwargs):
            kwargs["event_handler"]({"event": "playbook_on_play_start", "event_data": {"play": "all"}})
            kwargs["event_handler"]({"event": "playbook_on_task_start", "event_data": {"task": "Check hostname"}})
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
            kwargs["event_handler"](
                {
                    "event": "runner_on_ok",
                    "event_data": {"host": "host_1", "res": {"stdout": "api-01\n", "stderr": "", "rc": 0, "changed": False}},
                }
            )
            return SimpleNamespace(status="successful", rc=0)

        with patch("bulk_execution.services.run_ansible_playbook", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        result = task.results.get()
        self.assertIn("PLAY [all]", result.stdout)
        self.assertIn("TASK [Check hostname]", result.stdout)
        self.assertIn("ok: [host_1]", result.stdout)
        self.assertIn("api-01", result.stdout)
        self.assertEqual(result.stderr, "")

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="bulk-upload-runner-test-"))
    def test_file_upload_task_runs_ansible_copy_module(self):
        upload = SimpleUploadedFile("payload.txt", b"payload", content_type="text/plain")
        from .services import create_bulk_file_upload_task

        task = create_bulk_file_upload_task(
            self.user,
            {"targetIds": [self.host.id], "remoteDirectory": "/tmp/", "name": "upload payload"},
            upload,
        )

        def fake_run(**kwargs):
            self.assertEqual(kwargs["module"], "ansible.builtin.copy")
            self.assertIn("src=", kwargs["module_args"])
            self.assertIn("dest=/tmp/payload.txt", kwargs["module_args"])
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
            kwargs["event_handler"](
                {"event": "runner_on_ok", "event_data": {"host": "host_1", "res": {"stdout": "copied\n", "stderr": "", "rc": 0}}}
            )
            return SimpleNamespace(status="successful", rc=0)

        with patch("bulk_execution.services.run_ansible_shell", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        task.refresh_from_db()
        self.assertEqual(task.status, BulkExecutionTask.STATUS_COMPLETED)
        self.assertEqual(task.results.get().stdout, "copied\n")
        self.assertFalse(task.upload_file.storage.exists(task.upload_file.name))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="bulk-upload-runner-multi-test-"))
    def test_multi_file_upload_updates_transfer_items_and_aggregates_host_result(self):
        deploy = SimpleUploadedFile("deploy.txt", b"deploy\n", content_type="text/plain")
        config = SimpleUploadedFile("config.yml", b"name: api\n", content_type="text/yaml")
        from .services import create_bulk_file_upload_task

        task = create_bulk_file_upload_task(
            self.user,
            {"targetIds": [self.host.id], "remoteDirectory": "/srv/app", "overwrite": True, "name": "bundle upload"},
            [deploy, config],
        )
        calls = []

        def fake_run(**kwargs):
            calls.append(kwargs["module_args"])
            self.assertEqual(kwargs["module"], "ansible.builtin.copy")
            self.assertIn("force=yes", kwargs["module_args"])
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
            if "deploy.txt" in kwargs["module_args"]:
                kwargs["event_handler"](
                    {"event": "runner_on_ok", "event_data": {"host": "host_1", "res": {"stdout": "deploy copied\n", "stderr": "", "rc": 0}}}
                )
            else:
                kwargs["event_handler"](
                    {"event": "runner_on_ok", "event_data": {"host": "host_1", "res": {"stdout": "config copied\n", "stderr": "", "rc": 0}}}
                )
            return SimpleNamespace(status="successful", rc=0)

        with patch("bulk_execution.services.run_ansible_shell", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        task.refresh_from_db()
        result = task.results.get()
        transfers = list(result.transfers.order_by("id"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(task.status, BulkExecutionTask.STATUS_COMPLETED)
        self.assertEqual(result.status, BulkExecutionResult.STATUS_SUCCESS)
        self.assertEqual(result.stdout, "deploy copied\nconfig copied\n")
        self.assertEqual([transfer.status for transfer in transfers], ["success", "success"])
        self.assertEqual([transfer.remote_path for transfer in transfers], ["/srv/app/deploy.txt", "/srv/app/config.yml"])
        for upload_file in task.upload_files.all():
            self.assertFalse(upload_file.file.storage.exists(upload_file.file.name))

    def test_runner_failure_event_marks_task_failed(self):
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "false", "name": "nonzero failure"})

        def fake_run(**kwargs):
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
            kwargs["event_handler"](
                {
                    "event": "runner_on_failed",
                    "event_data": {"host": "host_1", "res": {"stdout": "", "stderr": "boom", "rc": 1, "msg": "non-zero"}},
                }
            )
            return SimpleNamespace(status="failed", rc=2)

        with patch("bulk_execution.services.run_ansible_shell", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        task.refresh_from_db()
        result = task.results.get()
        self.assertEqual(task.status, BulkExecutionTask.STATUS_FAILED)
        self.assertEqual(task.failed_count, 1)
        self.assertEqual(result.status, BulkExecutionResult.STATUS_FAILED)
        self.assertEqual(result.stderr, "boom")
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error, "non-zero")

    def test_polluted_host_is_retried_with_raw_module(self):
        host2 = ManagedHost.objects.create(
            name="api-02",
            group=self.group,
            private_ip="10.1.0.11",
            port=22,
            login_user="root",
            login_password="secret",
            verified=True,
            verify_status="verified",
            os="ubuntu",
        )
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id, host2.id], "command": "ls", "name": "polluted retry"})

        calls = []

        def fake_run(**kwargs):
            module = kwargs["module"]
            hosts = list(kwargs["inventory"]["all"]["hosts"].keys())
            calls.append((module, hosts))
            if module == "ansible.builtin.shell":
                kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
                kwargs["event_handler"](
                    {"event": "runner_on_ok", "event_data": {"host": "host_1", "res": {"stdout": "file-a\n", "stderr": "", "rc": 0}}}
                )
                kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_2"}})
                kwargs["event_handler"](
                    {
                        "event": "runner_on_failed",
                        "event_data": {
                            "host": "host_2",
                            "res": {"stdout": "", "stderr": "", "rc": 1, "msg": "MODULE FAILURE\nModule result deserialization failed: No start of json char found"},
                        },
                    }
                )
                return SimpleNamespace(status="failed", rc=2)
            # raw fallback should target only the polluted host
            self.assertEqual(module, "ansible.builtin.raw")
            self.assertEqual(hosts, ["host_2"])
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_2"}})
            kwargs["event_handler"](
                {"event": "runner_on_ok", "event_data": {"host": "host_2", "res": {"stdout": "file-b\n", "stderr": "", "rc": 0}}}
            )
            return SimpleNamespace(status="successful", rc=0)

        with patch("bulk_execution.services.run_ansible_shell", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        task.refresh_from_db()
        self.assertEqual([module for module, _ in calls], ["ansible.builtin.shell", "ansible.builtin.raw"])
        self.assertEqual(task.status, BulkExecutionTask.STATUS_COMPLETED)
        self.assertEqual(task.success_count, 2)
        self.assertEqual(task.failed_count, 0)
        clean = task.results.get(inventory_name="host_1")
        recovered = task.results.get(inventory_name="host_2")
        self.assertEqual(clean.status, BulkExecutionResult.STATUS_SUCCESS)
        self.assertEqual(clean.stdout, "file-a\n")
        self.assertEqual(recovered.status, BulkExecutionResult.STATUS_SUCCESS)
        self.assertEqual(recovered.stdout, "file-b\n")
        self.assertEqual(recovered.error, "")

    def test_genuine_command_failure_is_not_retried_with_raw(self):
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "false", "name": "genuine failure"})
        modules = []

        def fake_run(**kwargs):
            modules.append(kwargs["module"])
            kwargs["event_handler"]({"event": "runner_on_start", "event_data": {"host": "host_1"}})
            kwargs["event_handler"](
                {"event": "runner_on_failed", "event_data": {"host": "host_1", "res": {"stdout": "", "stderr": "boom", "rc": 1, "msg": "non-zero return code"}}}
            )
            return SimpleNamespace(status="failed", rc=2)

        with patch("bulk_execution.services.run_ansible_shell", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        # A real command failure has no module-pollution signature, so no raw retry happens.
        self.assertEqual(modules, ["ansible.builtin.shell"])
        task.refresh_from_db()
        self.assertEqual(task.status, BulkExecutionTask.STATUS_FAILED)
        self.assertEqual(task.results.get().status, BulkExecutionResult.STATUS_FAILED)

    def test_cancel_requested_callback_marks_unfinished_results_skipped(self):
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "sleep 60", "name": "cancel sleep"})
        task.cancel_requested = True
        task.status = BulkExecutionTask.STATUS_RUNNING
        task.started_at = timezone.now()
        task.save(update_fields=["cancel_requested", "status", "started_at"])

        def fake_run(**kwargs):
            self.assertTrue(kwargs["cancel_callback"]())
            return SimpleNamespace(status="canceled", rc=254)

        with patch("bulk_execution.services.run_ansible_shell", side_effect=fake_run):
            run_bulk_execution_task(task.id)

        task.refresh_from_db()
        result = task.results.get()
        self.assertEqual(task.status, BulkExecutionTask.STATUS_CANCELED)
        self.assertEqual(task.skipped_count, 1)
        self.assertEqual(result.status, BulkExecutionResult.STATUS_SKIPPED)
        self.assertIn("canceled", result.error.lower())

    def test_task_with_no_available_inventory_fails_instead_of_staying_running(self):
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "hostname", "name": "missing host"})
        self.host.delete()

        with patch("bulk_execution.services.run_ansible_shell") as runner:
            run_bulk_execution_task(task.id)

        runner.assert_not_called()
        task.refresh_from_db()
        result = task.results.get()
        self.assertEqual(task.status, BulkExecutionTask.STATUS_FAILED)
        self.assertEqual(task.error, "No available target host")
        self.assertEqual(task.skipped_count, 1)
        self.assertEqual(result.status, BulkExecutionResult.STATUS_SKIPPED)
