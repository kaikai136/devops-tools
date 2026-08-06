from __future__ import annotations

import json
import os
import shlex
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import OperationalError, ProgrammingError, close_old_connections, transaction
from django.db.models import QuerySet
from django.utils import timezone

from host_management.models import ManagedHost
from web_terminal.services.commands import run_one_shot_ssh_command
from web_terminal.services.file_parsers import join_remote_path, normalize_remote_file_name, normalize_remote_file_path

from .models import BulkExecutionResult, BulkExecutionTask, BulkExecutionTransferItem, BulkExecutionUploadFile

MAX_COMMAND_LENGTH = 200000
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

    execution_type = str(payload.get("executionType") or payload.get("execution_type") or BulkExecutionTask.EXECUTION_SHELL).strip()
    if execution_type not in {BulkExecutionTask.EXECUTION_SHELL, BulkExecutionTask.EXECUTION_PLAYBOOK}:
        raise ValueError("Unsupported execution type")

    task_name = require_task_name(payload)
    raw_command = str(payload.get("command", ""))
    if not raw_command.strip():
        raise ValueError("Please enter a command")
    if len(raw_command) > MAX_COMMAND_LENGTH:
        raise ValueError(f"Command cannot exceed {MAX_COMMAND_LENGTH} characters")
    command = raw_command if execution_type == BulkExecutionTask.EXECUTION_PLAYBOOK else raw_command.strip()

    hosts_by_id = {host.id: host for host in list_executable_targets() if host.id in set(target_ids)}
    hosts = [hosts_by_id[target_id] for target_id in target_ids if target_id in hosts_by_id]
    if not hosts:
        raise ValueError("No executable Linux SSH hosts selected")

    with transaction.atomic():
        task = BulkExecutionTask.objects.create(
            name=task_name,
            command=command,
            execution_type=execution_type,
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


def create_bulk_file_upload_task(user, payload: dict, uploaded_file) -> BulkExecutionTask:
    uploaded_files = normalize_uploaded_files(uploaded_file)
    if not uploaded_files:
        raise ValueError("Please select a file to upload")

    target_ids = parse_target_ids(payload.get("targetIds") or payload.get("target_ids") or payload.get("hostIds") or [])
    config = bulk_execution_settings()
    if len(target_ids) > int(config["maxTargets"]):
        raise ValueError(f"Select at most {config['maxTargets']} hosts")

    remote_directory = normalize_remote_directory(str(payload.get("remoteDirectory") or payload.get("remote_directory") or "/tmp/"))
    hosts = executable_hosts_for_target_ids(target_ids)
    if not hosts:
        raise ValueError("No executable Linux SSH hosts selected")

    overwrite = parse_bool(payload.get("overwrite") or payload.get("uploadOverwrite") or payload.get("upload_overwrite"))
    task_name = require_task_name(payload)
    uploaded_specs = []
    stored_names: list[str] = []
    try:
        for item in uploaded_files:
            filename = normalize_remote_file_name(getattr(item, "name", ""))
            if any(spec["filename"] == filename for spec in uploaded_specs):
                raise ValueError(f"Duplicate upload filename: {filename}")
            remote_path = join_remote_path(remote_directory, filename)
            stored_name = default_storage.save(f"bulk_execution_uploads/{uuid.uuid4().hex}_{filename}", item)
            stored_names.append(stored_name)
            uploaded_specs.append(
                {
                    "filename": filename,
                    "remote_path": remote_path,
                    "stored_name": stored_name,
                    "size": int(getattr(item, "size", 0) or default_storage.size(stored_name)),
                }
            )
        total_size = sum(spec["size"] for spec in uploaded_specs)
        summary_filename = uploaded_specs[0]["filename"] if len(uploaded_specs) == 1 else f"{len(uploaded_specs)} files"
        summary_file = uploaded_specs[0]["stored_name"] if len(uploaded_specs) == 1 else ""
        command_target = uploaded_specs[0]["remote_path"] if len(uploaded_specs) == 1 else remote_directory

        with transaction.atomic():
            task = BulkExecutionTask.objects.create(
                name=task_name,
                command=f"Upload {summary_filename} to {command_target}",
                execution_type=BulkExecutionTask.EXECUTION_FILE_UPLOAD,
                remote_directory=remote_directory,
                upload_file=summary_file,
                upload_filename=summary_filename,
                upload_size=total_size,
                upload_overwrite=overwrite,
                created_by=user if getattr(user, "is_authenticated", False) else None,
                target_count=len(hosts),
            )
            for spec in uploaded_specs:
                BulkExecutionUploadFile.objects.create(
                    task=task,
                    file=spec["stored_name"],
                    filename=spec["filename"],
                    remote_path=spec["remote_path"],
                    size=spec["size"],
                )
            create_results_for_hosts(task, hosts)
            create_transfer_items_for_uploads(task)
    except Exception:
        for stored_name in stored_names:
            if stored_name and default_storage.exists(stored_name):
                default_storage.delete(stored_name)
        raise
    return task


def require_task_name(payload: dict) -> str:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Please enter a task name")
    return name


def normalize_uploaded_files(uploaded_file) -> list:
    if uploaded_file is None:
        return []
    if isinstance(uploaded_file, (list, tuple)):
        return [item for item in uploaded_file if item is not None]
    return [uploaded_file]


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_target_ids(value) -> list[int]:
    if isinstance(value, str):
        import json

        try:
            value = json.loads(value)
        except ValueError:
            value = [item for item in value.split(",") if item.strip()]
    if not isinstance(value, list) or not value:
        raise ValueError("Please select Linux SSH hosts")
    try:
        return [int(item) for item in value]
    except (TypeError, ValueError):
        raise ValueError("Invalid host selection")


def executable_hosts_for_target_ids(target_ids: list[int]) -> list[ManagedHost]:
    hosts_by_id = {host.id: host for host in list_executable_targets() if host.id in set(target_ids)}
    return [hosts_by_id[target_id] for target_id in target_ids if target_id in hosts_by_id]


def create_results_for_hosts(task: BulkExecutionTask, hosts: list[ManagedHost]) -> None:
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


def create_transfer_items_for_uploads(task: BulkExecutionTask) -> None:
    upload_files = list(task.upload_files.all())
    if not upload_files:
        return
    results = list(task.results.all())
    for result in results:
        for upload_file in upload_files:
            BulkExecutionTransferItem.objects.create(
                task=task,
                result=result,
                upload_file=upload_file,
                remote_path=upload_file.remote_path,
                size=upload_file.size,
            )


def normalize_remote_directory(value: str) -> str:
    directory = normalize_remote_file_path(value or "/tmp/")
    if directory != "/" and directory.endswith("/"):
        directory = directory.rstrip("/")
    return directory


def check_bulk_file_upload_targets(payload: dict) -> dict:
    target_ids = parse_target_ids(payload.get("targetIds") or payload.get("target_ids") or payload.get("hostIds") or [])
    filenames_value = payload.get("filenames") or payload.get("names") or []
    if not isinstance(filenames_value, list) or not filenames_value:
        raise ValueError("Please select files to upload")
    filenames = [normalize_remote_file_name(str(name)) for name in filenames_value]
    remote_directory = normalize_remote_directory(str(payload.get("remoteDirectory") or payload.get("remote_directory") or "/tmp/"))
    hosts = executable_hosts_for_target_ids(target_ids)

    connected_targets = []
    unreachable_targets = []
    duplicate_files = []
    usable_target_ids = []
    for host in hosts:
        inspected = inspect_bulk_upload_target(host, remote_directory, filenames)
        if not inspected.get("connected"):
            unreachable_targets.append(target_payload(host, error=str(inspected.get("error") or "Connection failed")))
            continue
        connected_targets.append(target_payload(host))
        usable_target_ids.append(host.id)
        present_files = [str(item) for item in inspected.get("presentFiles", []) if str(item).strip()]
        if present_files:
            duplicate_files.append(
                {
                    "targetId": host.id,
                    "hostName": host.name,
                    "hostIp": str(host.private_ip),
                    "filenames": present_files,
                }
            )
    return {
        "connectedTargets": connected_targets,
        "unreachableTargets": unreachable_targets,
        "duplicateFiles": duplicate_files,
        "usableTargetIds": usable_target_ids,
    }


def target_payload(host: ManagedHost, *, error: str = "") -> dict:
    payload = {
        "id": host.id,
        "name": host.name,
        "group": host.group_id,
        "groupName": host.group.name if host.group_id and host.group else "",
        "privateIp": host.private_ip,
        "publicIp": host.public_ip,
        "port": host.port,
        "loginUser": host.login_user,
        "os": host.os,
        "systemType": host.system_type,
        "systemArch": host.system_arch,
        "verified": host.verified,
    }
    if error:
        payload["error"] = error
    return payload


def inspect_bulk_upload_target(host: ManagedHost, remote_directory: str, filenames: list[str]) -> dict:
    checks = []
    for filename in filenames:
        remote_path = join_remote_path(remote_directory, filename)
        checks.append(f"if test -e {shlex.quote(remote_path)}; then printf '%s\\n' {shlex.quote(filename)}; fi")
    command = "; ".join(checks) if checks else "true"
    try:
        output = run_one_shot_ssh_command(host, command)
    except Exception as error:
        return {"connected": False, "presentFiles": [], "error": str(error)}
    present = [line.strip() for line in output.splitlines() if line.strip()]
    return {"connected": True, "presentFiles": present, "error": ""}


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
    task.log_output = ""
    task.log_output_truncated = False
    task.save(update_fields=["status", "started_at", "finished_at", "error", "log_output", "log_output_truncated"])

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
            if task.execution_type == BulkExecutionTask.EXECUTION_PLAYBOOK:
                runner_result = run_playbook(task, result_by_inventory, temp_dir, inventory, config)
            elif task.execution_type == BulkExecutionTask.EXECUTION_FILE_UPLOAD:
                runner_result = run_file_upload(task, result_by_inventory, temp_dir, inventory, config)
            else:
                runner_result = run_command_module(
                    task, result_by_inventory, temp_dir, inventory, config, module="ansible.builtin.shell"
                )
            task.refresh_from_db(fields=["cancel_requested"])
            canceled = bool(task.cancel_requested) or getattr(runner_result, "status", "") == "canceled"
            if not canceled and task.execution_type == BulkExecutionTask.EXECUTION_SHELL:
                # Fallback: hosts whose shell module output was polluted (e.g. a login banner
                # on stdout) fail JSON deserialization. Re-run just those with the raw module,
                # which runs the command directly over SSH without a Python wrapper.
                retry_polluted_results_with_raw(task, result_by_inventory, temp_dir, inventory, config)
        if canceled:
            mark_unfinished_transfers(task, BulkExecutionTransferItem.STATUS_SKIPPED, "Task canceled")
            mark_unfinished_results(task, BulkExecutionResult.STATUS_SKIPPED, "Task canceled")
            task.status = BulkExecutionTask.STATUS_CANCELED
        else:
            mark_unfinished_transfers(task, BulkExecutionTransferItem.STATUS_FAILED, "No result returned by Ansible")
            mark_unfinished_results(task, BulkExecutionResult.STATUS_FAILED, "No result returned by Ansible")
            task.status = final_task_status(task)
    except Exception as error:
        task.status = BulkExecutionTask.STATUS_FAILED
        task.error = str(error)
        mark_unfinished_transfers(task, BulkExecutionTransferItem.STATUS_FAILED, str(error))
        mark_unfinished_results(task, BulkExecutionResult.STATUS_FAILED, str(error))
    finally:
        task.finished_at = timezone.now()
        refresh_task_counts(task)
        task.save(update_fields=["status", "error", "finished_at", "completed_count", "success_count", "failed_count", "skipped_count"])
        cleanup_upload_file(task)


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


def run_playbook(task, result_by_inventory, temp_dir, inventory, config):
    project_dir = Path(temp_dir) / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    playbook_path = project_dir / "playbook.yml"
    playbook_path.write_text(task.command, encoding="utf-8")
    event_context: dict[str, Any] = {"current_play": "", "current_task": "", "host_headers": {}}
    return run_ansible_playbook(
        private_data_dir=temp_dir,
        inventory=inventory,
        playbook="playbook.yml",
        forks=max(1, min(len(inventory["all"]["hosts"]), int(config["forks"]))),
        timeout=int(config["timeoutSeconds"]),
        quiet=True,
        envvars={"ANSIBLE_HOST_KEY_CHECKING": "False"},
        event_handler=lambda event: handle_playbook_event(task.id, result_by_inventory, event_context, event),
        cancel_callback=lambda: is_cancel_requested(task.id),
    )


def run_file_upload(task, result_by_inventory, temp_dir, inventory, config):
    upload_files = list(task.upload_files.all())
    if not upload_files and not task.upload_file:
        raise RuntimeError("No upload file attached to task")
    if not upload_files:
        filename = normalize_remote_file_name(task.upload_filename)
        remote_directory = normalize_remote_directory(task.remote_directory or "/tmp/")
        upload_files = [
            BulkExecutionUploadFile.objects.create(
                task=task,
                file=task.upload_file.name,
                filename=filename,
                remote_path=join_remote_path(remote_directory, filename),
                size=task.upload_size,
            )
        ]
        create_transfer_items_for_uploads(task)

    runner_result = None
    canceled = False
    for upload_file in upload_files:
        if is_cancel_requested(task.id):
            canceled = True
            break
        runner_result = run_upload_file_item(task, upload_file, result_by_inventory, temp_dir, inventory, config)
        if getattr(runner_result, "status", "") == "canceled":
            canceled = True
            break
    if canceled:
        mark_unfinished_transfers(task, BulkExecutionTransferItem.STATUS_SKIPPED, "Task canceled")
        return runner_result
    aggregate_file_upload_results(task)
    return runner_result


def run_upload_file_item(task, upload_file: BulkExecutionUploadFile, result_by_inventory, temp_dir, inventory, config):
    source_path = upload_file.file.path
    force = "yes" if task.upload_overwrite else "no"
    return run_ansible_shell(
        private_data_dir=temp_dir,
        inventory=inventory,
        module="ansible.builtin.copy",
        module_args=f"src={shlex.quote(source_path)} dest={shlex.quote(upload_file.remote_path)} force={force}",
        host_pattern="all",
        forks=max(1, min(len(inventory["all"]["hosts"]), int(config["forks"]))),
        timeout=int(config["timeoutSeconds"]),
        quiet=True,
        envvars={"ANSIBLE_HOST_KEY_CHECKING": "False"},
        event_handler=lambda event: handle_file_upload_event(task.id, result_by_inventory, upload_file, event),
        cancel_callback=lambda: is_cancel_requested(task.id),
    )


def handle_file_upload_event(task_id: int, result_by_inventory: dict[str, BulkExecutionResult], upload_file: BulkExecutionUploadFile, event: dict[str, Any]) -> bool:
    event_name = str(event.get("event", ""))
    event_data = event.get("event_data") if isinstance(event.get("event_data"), dict) else {}
    result = result_by_inventory.get(str(event_data.get("host", "")))
    if result is None:
        return True

    transfer = BulkExecutionTransferItem.objects.filter(result=result, upload_file=upload_file).first()
    if transfer is None:
        return True

    if event_name == "runner_on_start":
        transfer.status = BulkExecutionTransferItem.STATUS_RUNNING
        transfer.started_at = transfer.started_at or timezone.now()
        transfer.finished_at = None
        transfer.error = ""
        transfer.save(update_fields=["status", "started_at", "finished_at", "error"])
        result.status = BulkExecutionResult.STATUS_RUNNING
        result.started_at = result.started_at or timezone.now()
        result.finished_at = None
        result.error = ""
        result.save(update_fields=["status", "started_at", "finished_at", "error"])
        return True

    if event_name in {"runner_on_ok", "runner_on_failed", "runner_on_unreachable", "runner_on_skipped"}:
        res = event_data.get("res") if isinstance(event_data.get("res"), dict) else {}
        if event_name == "runner_on_ok":
            status = BulkExecutionTransferItem.STATUS_SUCCESS
        elif event_name == "runner_on_skipped":
            status = BulkExecutionTransferItem.STATUS_SKIPPED
        else:
            status = BulkExecutionTransferItem.STATUS_FAILED
        stdout, stdout_truncated = truncate_output(str(res.get("stdout", "") or ""))
        stderr, stderr_truncated = truncate_output(str(res.get("stderr", "") or ""))
        transfer.status = status
        transfer.stdout = stdout
        transfer.stderr = stderr
        transfer.error = result_error(event_name, res)
        transfer.started_at = transfer.started_at or timezone.now()
        transfer.finished_at = timezone.now()
        transfer.save(update_fields=["status", "stdout", "stderr", "error", "started_at", "finished_at"])

        if stdout:
            result.stdout = append_output(result.stdout, stdout)
        if stderr:
            result.stderr = append_output(result.stderr, stderr)
        result.output_truncated = result.output_truncated or stdout_truncated or stderr_truncated
        if transfer.error:
            result.error = transfer.error
        result.save(update_fields=["stdout", "stderr", "output_truncated", "error"])
        refresh_task_counts(BulkExecutionTask.objects.get(id=task_id))
    return True


def append_output(current: str, addition: str) -> str:
    if not current:
        return addition
    separator = "" if current.endswith("\n") or addition.startswith("\n") else "\n"
    return current + separator + addition


def aggregate_file_upload_results(task: BulkExecutionTask) -> None:
    for result in task.results.prefetch_related("transfers").all():
        transfers = list(result.transfers.all())
        if not transfers:
            continue
        if any(transfer.status == BulkExecutionTransferItem.STATUS_FAILED for transfer in transfers):
            result.status = BulkExecutionResult.STATUS_FAILED
            failed = next(transfer for transfer in transfers if transfer.status == BulkExecutionTransferItem.STATUS_FAILED)
            result.error = failed.error
        elif all(transfer.status == BulkExecutionTransferItem.STATUS_SUCCESS for transfer in transfers):
            result.status = BulkExecutionResult.STATUS_SUCCESS
            result.error = ""
        elif all(transfer.status == BulkExecutionTransferItem.STATUS_SKIPPED for transfer in transfers):
            result.status = BulkExecutionResult.STATUS_SKIPPED
            result.error = result.error or "Task canceled"
        else:
            result.status = BulkExecutionResult.STATUS_FAILED
            result.error = result.error or "Some upload transfers did not finish"
        result.started_at = result.started_at or timezone.now()
        result.finished_at = timezone.now()
        result.save(update_fields=["status", "error", "started_at", "finished_at"])


def cleanup_upload_file(task: BulkExecutionTask) -> None:
    if task.execution_type != BulkExecutionTask.EXECUTION_FILE_UPLOAD or not task.upload_file:
        if task.execution_type == BulkExecutionTask.EXECUTION_FILE_UPLOAD:
            cleanup_upload_files(task)
        return
    cleanup_upload_files(task)


def cleanup_upload_files(task: BulkExecutionTask) -> None:
    names = set()
    if task.upload_file:
        names.add(task.upload_file.name)
    for upload_file in task.upload_files.all():
        if upload_file.file:
            names.add(upload_file.file.name)
    try:
        storage = task.upload_file.storage if task.upload_file else default_storage
        for name in names:
            if name and storage.exists(name):
                storage.delete(name)
    except Exception:
        pass


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


def run_ansible_playbook(**kwargs):
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


def handle_playbook_event(task_id: int, result_by_inventory: dict[str, BulkExecutionResult], context: dict[str, Any], event: dict[str, Any]) -> bool:
    event_name = str(event.get("event", ""))
    event_data = event.get("event_data") if isinstance(event.get("event_data"), dict) else {}

    if event_name == "playbook_on_play_start":
        context["current_play"] = event_label(event_data, "play", "name", default="all")
        context["current_task"] = ""
        append_playbook_task_log(task_id, context, f"{ansible_banner('PLAY', context['current_play'])}\n")
        return True

    if event_name == "playbook_on_task_start":
        context["current_task"] = event_label(event_data, "task", "name", "task_action", default="task")
        append_playbook_task_log(task_id, context, f"{ansible_banner('TASK', context['current_task'])}\n")
        return True

    if event_name == "playbook_on_stats":
        append_playbook_recap(task_id, context, result_by_inventory, event_data)
        return True

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

        event_output = format_playbook_event_output(context, event_name, event_data, result, res)
        append_playbook_task_log(task_id, context, format_playbook_task_output(event_name, result, res))
        stdout, stdout_truncated = append_limited_output(result.stdout, event_output)
        stderr, stderr_truncated = truncate_output(str(res.get("stderr", "") or ""))
        result.status = status
        result.stdout = stdout
        result.stderr = stderr
        result.exit_code = safe_int(res.get("rc"))
        result.output_truncated = result.output_truncated or stdout_truncated or stderr_truncated
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


def append_playbook_task_log(task_id: int, context: dict[str, Any], addition: str) -> None:
    if not addition:
        return
    output, truncated = append_limited_output(str(context.get("log_output") or ""), addition)
    context["log_output"] = output
    context["log_output_truncated"] = bool(context.get("log_output_truncated")) or truncated
    BulkExecutionTask.objects.filter(id=task_id).update(
        log_output=output,
        log_output_truncated=context["log_output_truncated"],
    )


def append_playbook_recap(
    task_id: int,
    context: dict[str, Any],
    result_by_inventory: dict[str, BulkExecutionResult],
    stats: dict[str, Any],
) -> None:
    if context.get("recap_emitted"):
        return
    lines = [f"PLAY RECAP {'*' * 65}"]
    for inventory_name, result in result_by_inventory.items():
        label = str(result.host_ip or inventory_name)
        lines.append(
            f"{label:<15} : "
            f"ok={recap_count(stats, 'ok', inventory_name)} "
            f"changed={recap_count(stats, 'changed', inventory_name)} "
            f"unreachable={recap_count(stats, 'dark', inventory_name) or recap_count(stats, 'unreachable', inventory_name)} "
            f"failed={recap_count(stats, 'failures', inventory_name)} "
            f"skipped={recap_count(stats, 'skipped', inventory_name)} "
            f"rescued={recap_count(stats, 'rescued', inventory_name)} "
            f"ignored={recap_count(stats, 'ignored', inventory_name)}"
        )
    append_playbook_task_log(task_id, context, "\n".join(lines) + "\n")
    context["recap_emitted"] = True


def recap_count(stats: dict[str, Any], key: str, inventory_name: str) -> int:
    values = stats.get(key)
    if not isinstance(values, dict):
        return 0
    return safe_int(values.get(inventory_name)) or 0


def format_playbook_task_output(event_name: str, result: BulkExecutionResult, res: dict[str, Any]) -> str:
    lines = [ansible_result_line(event_name, str(result.host_ip or result.inventory_name), res)]
    command_stdout = str(res.get("stdout", "") or "").rstrip("\n")
    if command_stdout:
        lines.append(command_stdout)
    return "\n".join(lines).rstrip() + "\n"


def event_label(event_data: dict[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = event_data.get(key)
        if value:
            return str(value)
    return default


def format_playbook_event_output(context: dict[str, Any], event_name: str, event_data: dict[str, Any], result: BulkExecutionResult, res: dict[str, Any]) -> str:
    lines: list[str] = []
    play = event_label(event_data, "play", default=str(context.get("current_play") or "all"))
    task = event_label(event_data, "task", default=str(context.get("current_task") or "task"))
    headers = context.setdefault("host_headers", {}).setdefault(result.inventory_name, {"play": "", "task": ""})

    if play and headers.get("play") != play:
        lines.append(ansible_banner("PLAY", play))
        headers["play"] = play
        headers["task"] = ""
    if task and headers.get("task") != task:
        lines.append(ansible_banner("TASK", task))
        headers["task"] = task

    lines.append(ansible_result_line(event_name, result.inventory_name, res))
    command_stdout = str(res.get("stdout", "") or "").rstrip("\n")
    if command_stdout:
        lines.append(command_stdout)
    return "\n".join(lines).rstrip() + "\n"


def ansible_banner(kind: str, label: str) -> str:
    title = f"{kind} [{label}] "
    return title + ("*" * max(0, 72 - len(title)))


def ansible_result_line(event_name: str, inventory_name: str, res: dict[str, Any]) -> str:
    if event_name == "runner_on_ok":
        state = "changed" if res.get("changed") else "ok"
        return f"{state}: [{inventory_name}]"
    if event_name == "runner_on_skipped":
        return f"skipping: [{inventory_name}]" + ansible_result_payload(res)
    if event_name == "runner_on_unreachable":
        return f"fatal: [{inventory_name}]: UNREACHABLE!" + ansible_result_payload(res)
    return f"fatal: [{inventory_name}]: FAILED!" + ansible_result_payload(res)


def ansible_result_payload(res: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in res.items()
        if key not in {"stdout", "stdout_lines"} and value not in ("", None, [], {})
    }
    if not payload:
        return ""
    return " => " + json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def append_limited_output(current: str, addition: str) -> tuple[str, bool]:
    if not addition:
        return current, False
    return truncate_output(append_output(current, addition))


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


def mark_unfinished_transfers(task: BulkExecutionTask, status: str, error: str) -> None:
    if task.execution_type != BulkExecutionTask.EXECUTION_FILE_UPLOAD:
        return
    now = timezone.now()
    task.transfer_items.filter(status__in=[BulkExecutionTransferItem.STATUS_PENDING, BulkExecutionTransferItem.STATUS_RUNNING]).update(
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
