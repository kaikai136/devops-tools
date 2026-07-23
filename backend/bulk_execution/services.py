from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import OperationalError, ProgrammingError, close_old_connections, transaction
from django.db.models import QuerySet
from django.utils import timezone

from host_management.models import ManagedHost

from .models import BulkExecutionResult, BulkExecutionTask

MAX_COMMAND_LENGTH = 4096
OUTPUT_LIMIT = 200_000
DEFAULT_MAX_TARGETS = 50
DEFAULT_FORKS = 10
DEFAULT_TIMEOUT_SECONDS = 300

# Signatures of an Ansible module-wrapper failure caused by the target host writing
# extra text to stdout on non-interactive login (e.g. a shell banner in ~/.bashrc),
# which corrupts the JSON the Python module returns. Hosts that fail with any of these
# are retried with the raw module, which runs the command directly over SSH without a
# Python wrapper and is therefore immune to stdout pollution.
MODULE_POLLUTION_SIGNATURES = (
    "No start of json char found",
    "Module result deserialization failed",
    "MODULE FAILURE",
    "Expecting value",
)

_interrupted_tasks_checked = False


def executable_targets_queryset() -> QuerySet[ManagedHost]:
    return (
        ManagedHost.objects.select_related("group", "created_by")
        .filter(verified=True, verify_status="verified")
        .exclude(os="windows")
        .exclude(login_user="")
    )


def has_ssh_credential(host: ManagedHost) -> bool:
    return bool(host.login_user and (host.login_password or host.private_key))


def list_executable_targets() -> list[ManagedHost]:
    return [host for host in executable_targets_queryset() if has_ssh_credential(host)]


def bulk_execution_settings() -> dict[str, int | bool]:
    return {
        "maxTargets": int(getattr(settings, "BULK_EXECUTION_MAX_TARGETS", DEFAULT_MAX_TARGETS)),
        "forks": int(getattr(settings, "BULK_EXECUTION_FORKS", DEFAULT_FORKS)),
        "timeoutSeconds": int(getattr(settings, "BULK_EXECUTION_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        "runAsync": bool(getattr(settings, "BULK_EXECUTION_RUN_ASYNC", True)),
    }


def create_bulk_execution_task(user, payload: dict) -> BulkExecutionTask:
    target_ids = payload.get("targetIds") or payload.get("target_ids") or payload.get("hostIds") or []
    if not isinstance(target_ids, list) or not target_ids:
        raise ValueError("Please select Linux SSH hosts")
    config = bulk_execution_settings()
    if len(target_ids) > int(config["maxTargets"]):
        raise ValueError(f"Select at most {config['maxTargets']} hosts")
    try:
        target_ids = [int(item) for item in target_ids]
    except (TypeError, ValueError):
        raise ValueError("Invalid host selection")

    command = str(payload.get("command", "")).strip()
    if not command:
        raise ValueError("Please enter a command")
    if len(command) > MAX_COMMAND_LENGTH:
        raise ValueError(f"Command cannot exceed {MAX_COMMAND_LENGTH} characters")

    hosts_by_id = {host.id: host for host in list_executable_targets() if host.id in set(target_ids)}
    hosts = [hosts_by_id[target_id] for target_id in target_ids if target_id in hosts_by_id]
    if not hosts:
        raise ValueError("No executable Linux SSH hosts selected")

    with transaction.atomic():
        task = BulkExecutionTask.objects.create(
            name=str(payload.get("name", "")).strip() or f"Bulk execution {timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}",
            command=command,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            target_count=len(hosts),
        )
        for index, host in enumerate(hosts, start=1):
            BulkExecutionResult.objects.create(
                task=task,
                host=host,
                inventory_name=f"host_{index}",
                host_name=host.name,
                host_ip=host.private_ip,
                host_port=host.port,
                login_user=host.login_user,
                os=host.os,
                system_type=host.system_type,
                system_arch=host.system_arch,
            )
    return task


def start_bulk_execution_task(task_id: int) -> None:
    if not bool(getattr(settings, "BULK_EXECUTION_RUN_ASYNC", True)):
        run_bulk_execution_task(task_id)
        return
    thread = threading.Thread(target=_run_task_safely, args=(task_id,), name=f"bulk-execution-{task_id}", daemon=True)
    thread.start()


def _run_task_safely(task_id: int) -> None:
    close_old_connections()
    try:
        run_bulk_execution_task(task_id)
    except Exception as error:
        BulkExecutionTask.objects.filter(id=task_id).update(status=BulkExecutionTask.STATUS_FAILED, error=str(error), finished_at=timezone.now())
    finally:
        close_old_connections()


def mark_interrupted_tasks() -> None:
    global _interrupted_tasks_checked
    if _interrupted_tasks_checked:
        return
    try:
        now = timezone.now()
        running_tasks = list(BulkExecutionTask.objects.filter(status=BulkExecutionTask.STATUS_RUNNING))
        BulkExecutionTask.objects.filter(id__in=[task.id for task in running_tasks]).update(
            status=BulkExecutionTask.STATUS_FAILED,
            error="Service restarted while the task was running",
            finished_at=now,
        )
        BulkExecutionResult.objects.filter(task_id__in=[task.id for task in running_tasks], status=BulkExecutionResult.STATUS_RUNNING).update(
            status=BulkExecutionResult.STATUS_FAILED,
            error="Service restarted while the task was running",
            finished_at=now,
        )
    except (OperationalError, ProgrammingError):
        return
    _interrupted_tasks_checked = True


def run_bulk_execution_task(task_id: int) -> None:
    task = BulkExecutionTask.objects.prefetch_related("results").get(id=task_id)
    task.status = BulkExecutionTask.STATUS_RUNNING
    task.started_at = task.started_at or timezone.now()
    task.finished_at = None
    task.error = ""
    task.save(update_fields=["status", "started_at", "finished_at", "error"])

    results = list(task.results.select_related("host").all())
    result_by_inventory = {result.inventory_name: result for result in results}
    config = bulk_execution_settings()

    try:
        with tempfile.TemporaryDirectory(prefix=f"bulk-execution-{task.id}-") as temp_dir:
            inventory = build_runner_inventory(results, Path(temp_dir))
            if not inventory["all"]["hosts"]:
                task.status = BulkExecutionTask.STATUS_FAILED
                task.error = "No available target host"
                mark_unfinished_results(task, BulkExecutionResult.STATUS_SKIPPED, task.error)
                return
            runner_result = run_command_module(
                task, result_by_inventory, temp_dir, inventory, config, module="ansible.builtin.shell"
            )
            task.refresh_from_db(fields=["cancel_requested"])
            canceled = bool(task.cancel_requested) or getattr(runner_result, "status", "") == "canceled"
            if not canceled:
                # Fallback: hosts whose shell module output was polluted (e.g. a login banner
                # on stdout) fail JSON deserialization. Re-run just those with the raw module,
                # which runs the command directly over SSH without a Python wrapper.
                retry_polluted_results_with_raw(task, result_by_inventory, temp_dir, inventory, config)
        if canceled:
            mark_unfinished_results(task, BulkExecutionResult.STATUS_SKIPPED, "Task canceled")
            task.status = BulkExecutionTask.STATUS_CANCELED
        else:
            mark_unfinished_results(task, BulkExecutionResult.STATUS_FAILED, "No result returned by Ansible")
            task.status = final_task_status(task)
    except Exception as error:
        task.status = BulkExecutionTask.STATUS_FAILED
        task.error = str(error)
        mark_unfinished_results(task, BulkExecutionResult.STATUS_FAILED, str(error))
    finally:
        task.finished_at = timezone.now()
        refresh_task_counts(task)
        task.save(update_fields=["status", "error", "finished_at", "completed_count", "success_count", "failed_count", "skipped_count"])


def run_command_module(task, result_by_inventory, temp_dir, inventory, config, *, module):
    return run_ansible_shell(
        private_data_dir=temp_dir,
        inventory=inventory,
        module=module,
        module_args=task.command,
        host_pattern="all",
        forks=max(1, min(len(inventory["all"]["hosts"]), int(config["forks"]))),
        timeout=int(config["timeoutSeconds"]),
        quiet=True,
        envvars={"ANSIBLE_HOST_KEY_CHECKING": "False"},
        event_handler=lambda event: handle_runner_event(task.id, result_by_inventory, event),
        cancel_callback=lambda: is_cancel_requested(task.id),
    )


def polluted_inventory_names(task: BulkExecutionTask) -> list[str]:
    names: list[str] = []
    # Query directly instead of task.results.all(): the task was loaded with
    # prefetch_related("results"), so task.results.all() would return the stale
    # (pre-run) cache rather than the statuses the event handler just saved.
    failed = BulkExecutionResult.objects.filter(task_id=task.id, status=BulkExecutionResult.STATUS_FAILED)
    for result in failed:
        blob = "\n".join((result.error or "", result.stderr or "", result.stdout or ""))
        if any(signature in blob for signature in MODULE_POLLUTION_SIGNATURES):
            names.append(result.inventory_name)
    return names


def retry_polluted_results_with_raw(task, result_by_inventory, temp_dir, inventory, config) -> None:
    names = polluted_inventory_names(task)
    all_hosts = inventory["all"]["hosts"]
    sub_hosts = {name: all_hosts[name] for name in names if name in all_hosts}
    if not sub_hosts:
        return
    sub_inventory = {"all": {"hosts": sub_hosts}}
    # handle_runner_event overwrites these results (clears the old error on runner_on_start,
    # records the raw stdout/rc on completion), so the earlier module failure is replaced.
    run_command_module(task, result_by_inventory, temp_dir, sub_inventory, config, module="ansible.builtin.raw")


def run_ansible_shell(**kwargs):
    try:
        import ansible_runner
    except ImportError as error:
        raise RuntimeError("ansible-runner is not installed") from error
    return ansible_runner.run(**kwargs)


def build_runner_inventory(results: list[BulkExecutionResult], temp_dir: Path) -> dict[str, Any]:
    hosts: dict[str, dict[str, Any]] = {}
    key_dir = temp_dir / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        host = result.host
        if host is None:
            mark_result(result, BulkExecutionResult.STATUS_SKIPPED, error="Host no longer exists")
            continue
        variables: dict[str, Any] = {
            "ansible_host": str(host.public_ip or host.private_ip),
            "ansible_user": host.login_user,
            "ansible_port": int(host.port or 22),
            "ansible_connection": "ssh",
            "ansible_ssh_common_args": "-o StrictHostKeyChecking=no",
        }
        if host.login_password:
            variables["ansible_password"] = host.login_password
        if host.private_key:
            key_path = key_dir / f"{result.inventory_name}.key"
            key_path.write_text(host.private_key.strip() + "\n", encoding="utf-8")
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
            variables["ansible_ssh_private_key_file"] = str(key_path)
        hosts[result.inventory_name] = variables
    return {"all": {"hosts": hosts}}


def is_cancel_requested(task_id: int) -> bool:
    return bool(BulkExecutionTask.objects.filter(id=task_id, cancel_requested=True).exists())


def handle_runner_event(task_id: int, result_by_inventory: dict[str, BulkExecutionResult], event: dict[str, Any]) -> bool:
    event_name = str(event.get("event", ""))
    event_data = event.get("event_data") if isinstance(event.get("event_data"), dict) else {}
    result = result_by_inventory.get(str(event_data.get("host", "")))
    if result is None:
        return True

    if event_name == "runner_on_start":
        result.status = BulkExecutionResult.STATUS_RUNNING
        result.started_at = result.started_at or timezone.now()
        result.finished_at = None
        result.error = ""
        result.save(update_fields=["status", "started_at", "finished_at", "error"])
        return True

    if event_name in {"runner_on_ok", "runner_on_failed", "runner_on_unreachable", "runner_on_skipped"}:
        res = event_data.get("res") if isinstance(event_data.get("res"), dict) else {}
        if event_name == "runner_on_ok":
            status = BulkExecutionResult.STATUS_SUCCESS
        elif event_name == "runner_on_skipped":
            status = BulkExecutionResult.STATUS_SKIPPED
        else:
            status = BulkExecutionResult.STATUS_FAILED
        stdout, stdout_truncated = truncate_output(str(res.get("stdout", "") or ""))
        stderr, stderr_truncated = truncate_output(str(res.get("stderr", "") or ""))
        result.status = status
        result.stdout = stdout
        result.stderr = stderr
        result.exit_code = safe_int(res.get("rc"))
        result.output_truncated = stdout_truncated or stderr_truncated
        result.error = result_error(event_name, res)
        result.started_at = result.started_at or timezone.now()
        result.finished_at = timezone.now()
        result.save(
            update_fields=[
                "status",
                "stdout",
                "stderr",
                "exit_code",
                "output_truncated",
                "error",
                "started_at",
                "finished_at",
            ]
        )
        refresh_task_counts(BulkExecutionTask.objects.get(id=task_id))
    return True


def result_error(event_name: str, result_payload: dict[str, Any]) -> str:
    if event_name == "runner_on_ok":
        return ""
    return str(result_payload.get("msg") or result_payload.get("stderr") or result_payload.get("exception") or event_name)


def safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def truncate_output(value: str) -> tuple[str, bool]:
    if len(value) <= OUTPUT_LIMIT:
        return value, False
    return value[:OUTPUT_LIMIT], True


def mark_result(result: BulkExecutionResult, status: str, error: str = "") -> None:
    result.status = status
    result.error = error
    result.started_at = result.started_at or timezone.now()
    result.finished_at = timezone.now()
    result.save(update_fields=["status", "error", "started_at", "finished_at"])


def mark_unfinished_results(task: BulkExecutionTask, status: str, error: str) -> None:
    now = timezone.now()
    task.results.filter(status__in=[BulkExecutionResult.STATUS_PENDING, BulkExecutionResult.STATUS_RUNNING]).update(
        status=status,
        error=error,
        started_at=now,
        finished_at=now,
    )


def final_task_status(task: BulkExecutionTask) -> str:
    if task.results.filter(status=BulkExecutionResult.STATUS_FAILED).exists():
        return BulkExecutionTask.STATUS_FAILED
    return BulkExecutionTask.STATUS_COMPLETED


def refresh_task_counts(task: BulkExecutionTask) -> None:
    task.refresh_from_db(fields=["id"])
    task.completed_count = task.results.filter(
        status__in=[BulkExecutionResult.STATUS_SUCCESS, BulkExecutionResult.STATUS_FAILED, BulkExecutionResult.STATUS_SKIPPED]
    ).count()
    task.success_count = task.results.filter(status=BulkExecutionResult.STATUS_SUCCESS).count()
    task.failed_count = task.results.filter(status=BulkExecutionResult.STATUS_FAILED).count()
    task.skipped_count = task.results.filter(status=BulkExecutionResult.STATUS_SKIPPED).count()
    task.save(update_fields=["completed_count", "success_count", "failed_count", "skipped_count"])
