from __future__ import annotations

import json
import threading

from django.utils import timezone

from application_market.models import ApplicationInstallation, ApplicationTask

from .targets import run_target_command


def start_application_task(task_id: int) -> None:
    thread = threading.Thread(target=run_application_task, args=(task_id,), name=f"app-market-{task_id}", daemon=True)
    thread.start()


def run_application_task(task_id: int) -> None:
    task = ApplicationTask.objects.get(id=task_id)
    if task.cancel_requested:
        task.status = ApplicationTask.STATUS_CANCELED
        task.finished_at = timezone.now()
        task.save(update_fields=["status", "finished_at"])
        return
    task.status = ApplicationTask.STATUS_RUNNING
    task.started_at = timezone.now()
    task.save(update_fields=["status", "started_at"])
    try:
        plan = json.loads(task.plan or "{}")
        code, stdout, stderr = run_target_command(task.target_key, plan.get("command", ""))
        task.log_output = (stdout + ("\n" + stderr if stderr else ""))[:200000]
        if code != 0:
            task.status = ApplicationTask.STATUS_FAILED
            task.error = stderr or stdout or "Application task failed"
        else:
            task.status = ApplicationTask.STATUS_SUCCESS
            update_installation_from_plan(task, plan)
    except Exception as error:
        task.status = ApplicationTask.STATUS_UNKNOWN
        task.error = str(error)
    finally:
        task.finished_at = timezone.now()
        task.save(update_fields=["status", "log_output", "error", "finished_at"])


def update_installation_from_plan(task: ApplicationTask, plan: dict) -> None:
    if task.action == ApplicationTask.ACTION_UNINSTALL:
        ApplicationInstallation.objects.filter(target_key=task.target_key, app_id=task.app_id).delete()
        return
    status = "running" if task.action in {ApplicationTask.ACTION_INSTALL, ApplicationTask.ACTION_UPDATE, ApplicationTask.ACTION_START, ApplicationTask.ACTION_RESTART} else "stopped"
    summary = plan.get("summary", {})
    ApplicationInstallation.objects.update_or_create(
        target_key=task.target_key,
        app_id=task.app_id,
        defaults={
            "target_type": task.target_type,
            "target_host": task.target_host,
            "version": task.version,
            "status": status,
            "containers": summary.get("containers", []),
            "ports": summary.get("ports", []),
            "images": summary.get("images", []),
            "last_probed_at": timezone.now(),
        },
    )
