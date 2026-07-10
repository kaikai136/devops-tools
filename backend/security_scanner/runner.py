from __future__ import annotations

import threading

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.utils import timezone

from .models import ScanTask

_interrupted_tasks_checked = False


def mark_interrupted_tasks():
    global _interrupted_tasks_checked
    if _interrupted_tasks_checked:
        return
    try:
        ScanTask.objects.filter(status=ScanTask.STATUS_RUNNING).update(
            status=ScanTask.STATUS_FAILED,
            error="服务重启导致任务中断",
            finished_at=timezone.now(),
        )
    except (OperationalError, ProgrammingError):
        return
    _interrupted_tasks_checked = True


def start_security_scan_task(task_id: int, retry_target_ids: list[int] | None = None) -> None:
    if not getattr(settings, "SECURITY_SCAN_RUN_ASYNC", True):
        from .services import run_scan_task

        run_scan_task(task_id, retry_target_ids=retry_target_ids)
        return
    thread = threading.Thread(target=_run_task_safely, args=(task_id, retry_target_ids), name=f"security-scan-{task_id}", daemon=True)
    thread.start()


def _run_task_safely(task_id: int, retry_target_ids: list[int] | None = None) -> None:
    from .services import run_scan_task

    try:
        run_scan_task(task_id, retry_target_ids=retry_target_ids)
    except Exception as error:
        ScanTask.objects.filter(id=task_id).update(
            status=ScanTask.STATUS_FAILED,
            error=str(error),
            finished_at=timezone.now(),
        )
