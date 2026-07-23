from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
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
        self.assertEqual(task.created_by, self.user)
        self.assertEqual(task.target_count, 1)
        self.assertEqual(task.results.count(), 1)
        result = task.results.get()
        self.assertEqual(result.host, self.linux)
        self.assertEqual(result.host_name, "linux-ok")
        self.assertEqual(result.host_ip, "10.0.0.11")
        self.assertEqual(result.login_user, "root")
        start_task.assert_called_once_with(task.id)

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
                data={"targetIds": [self.linux.id], "command": "hostname"},
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

    def test_runner_failure_event_marks_task_failed(self):
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "false"})

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
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id, host2.id], "command": "ls"})

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
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "false"})
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
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "sleep 60"})
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
        task = create_bulk_execution_task(self.user, {"targetIds": [self.host.id], "command": "hostname"})
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
