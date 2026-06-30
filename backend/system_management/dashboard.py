from __future__ import annotations

import shutil
import subprocess
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.db.models import Count, Sum
from django.utils import timezone

from host_management.models import HostCredential, HostGroup, ManagedHost

from .models import LoginLog

EGRESS_CACHE_KEY = "dashboard.egress_network.v1"
EGRESS_CACHE_SECONDS = 300


def build_dashboard_summary() -> dict:
    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)
    seven_days_start = today_start - timedelta(days=6)

    users = user_summary(month_start)
    assets = asset_summary(month_start)
    login = login_summary(today_start, seven_days_start)

    return {
        "cards": [
            {
                "key": "users",
                "label": "用户总数",
                "value": users["total"],
                "changeLabel": f"本月新增 {users['newThisMonth']}",
                "tone": "blue",
            },
            {
                "key": "assets",
                "label": "资产总数",
                "value": assets["total"],
                "changeLabel": f"已验证 {assets['verified']}",
                "tone": "green",
            },
            {
                "key": "sessions",
                "label": "在线会话",
                "value": login["onlineSessions"],
                "changeLabel": f"今日成功 {login['todaySuccess']}",
                "tone": "cyan",
            },
            {
                "key": "failed",
                "label": "今日失败登录",
                "value": login["todayFailed"],
                "changeLabel": f"近 7 天失败 {login['weekFailed']}",
                "tone": "red" if login["todayFailed"] else "slate",
            },
        ],
        "users": users,
        "assets": assets,
        "loginTrend": login["trend"],
        "assetDistribution": {
            "os": os_distribution(),
            "platform": platform_distribution(),
            "verification": verification_distribution(assets),
        },
        "recentLogins": recent_logins(),
        "groupRanking": group_ranking(),
        "egressNetwork": get_egress_network(),
        "generatedAt": now.isoformat(),
    }


def user_summary(month_start) -> dict:
    User = get_user_model()
    total = User.objects.count()
    active = User.objects.filter(is_active=True).count()
    staff = User.objects.filter(is_staff=True).count()
    new_this_month = User.objects.filter(date_joined__gte=month_start).count()
    can_login = User.objects.filter(is_active=True, password__isnull=False).exclude(password="").count()
    return {
        "total": total,
        "active": active,
        "disabled": total - active,
        "staff": staff,
        "newThisMonth": new_this_month,
        "canLogin": can_login,
    }


def asset_summary(month_start) -> dict:
    hosts = ManagedHost.objects.all()
    total = hosts.count()
    verified = hosts.filter(verified=True).count()
    failed = hosts.filter(verify_status="failed").count()
    unverified = total - verified
    totals = hosts.aggregate(cpu=Sum("cpu"), memory=Sum("memory"))
    public_ip_count = hosts.exclude(public_ip__isnull=True).exclude(public_ip="").count()
    return {
        "total": total,
        "verified": verified,
        "unverified": unverified,
        "failed": failed,
        "newThisMonth": hosts.filter(created_at__gte=month_start).count(),
        "groups": HostGroup.objects.count(),
        "credentials": HostCredential.objects.count(),
        "publicIpCount": public_ip_count,
        "cpuCores": totals["cpu"] or 0,
        "memoryGb": totals["memory"] or 0,
        "verificationRate": round((verified / total) * 100) if total else 0,
    }


def login_summary(today_start, seven_days_start) -> dict:
    logs = LoginLog.objects.all()
    today_logs = logs.filter(created_at__gte=today_start)
    week_logs = logs.filter(created_at__gte=seven_days_start)
    return {
        "todaySuccess": today_logs.filter(status=LoginLog.STATUS_SUCCESS).count(),
        "todayFailed": today_logs.filter(status=LoginLog.STATUS_FAILED).count(),
        "weekSuccess": week_logs.filter(status=LoginLog.STATUS_SUCCESS).count(),
        "weekFailed": week_logs.filter(status=LoginLog.STATUS_FAILED).count(),
        "onlineSessions": active_session_count(),
        "trend": login_trend(seven_days_start),
    }


def login_trend(start_date) -> list[dict]:
    trend = []
    for offset in range(7):
        day_start = start_date + timedelta(days=offset)
        day_end = day_start + timedelta(days=1)
        day_logs = LoginLog.objects.filter(created_at__gte=day_start, created_at__lt=day_end)
        trend.append(
            {
                "date": day_start.strftime("%m-%d"),
                "success": day_logs.filter(status=LoginLog.STATUS_SUCCESS).count(),
                "failed": day_logs.filter(status=LoginLog.STATUS_FAILED).count(),
            }
        )
    return trend


def active_session_count() -> int:
    now = timezone.now()
    count = 0
    for session in Session.objects.filter(expire_date__gt=now):
        try:
            decoded = session.get_decoded()
        except Exception:
            continue
        if decoded.get("_auth_user_id"):
            count += 1
    return count


def os_distribution() -> list[dict]:
    return [
        {"label": item["os"] or "unknown", "value": item["count"]}
        for item in ManagedHost.objects.values("os").annotate(count=Count("id")).order_by("-count", "os")
    ]


def platform_distribution() -> list[dict]:
    linux = ManagedHost.objects.exclude(os="windows").count()
    windows = ManagedHost.objects.filter(os="windows").count()
    return [{"label": "Linux", "value": linux}, {"label": "Windows", "value": windows}]


def verification_distribution(assets: dict) -> list[dict]:
    return [
        {"label": "已验证", "value": assets["verified"]},
        {"label": "未验证", "value": max(assets["unverified"] - assets["failed"], 0)},
        {"label": "验证失败", "value": assets["failed"]},
    ]


def recent_logins() -> list[dict]:
    logs = LoginLog.objects.select_related("user").order_by("-created_at", "-id")[:6]
    return [
        {
            "id": log.id,
            "username": log.username,
            "userDisplay": log.user.get_full_name() or log.user.username if log.user_id and log.user else "",
            "ipAddress": str(log.ip_address) if log.ip_address else "",
            "status": log.status,
            "message": log.message,
            "createdAt": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


def group_ranking() -> list[dict]:
    rows = HostGroup.objects.annotate(hostCount=Count("hosts")).filter(hostCount__gt=0).order_by("-hostCount", "sort_order", "id")[:6]
    return [{"id": group.id, "label": group.name, "value": group.hostCount} for group in rows]


def get_egress_network() -> dict:
    cached = cache.get(EGRESS_CACHE_KEY)
    if cached:
        return cached

    checked_at = timezone.localtime().isoformat()
    base = {
        "ip": "",
        "location": "",
        "isp": "",
        "url": "",
        "raw": "",
        "checkedAt": checked_at,
        "status": "error",
        "error": "",
    }
    curl_bin = shutil.which("curl") or shutil.which("curl.exe") or "curl"
    try:
        completed = subprocess.run(
            [curl_bin, "-sS", "--max-time", "6", "cip.cc"],
            capture_output=True,
            text=True,
            timeout=8,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        payload = {**base, "error": str(error)}
        cache.set(EGRESS_CACHE_KEY, payload, EGRESS_CACHE_SECONDS)
        return payload

    raw = (completed.stdout or "").strip()
    if completed.returncode != 0:
        error = (completed.stderr or raw or f"curl exited with {completed.returncode}").strip()
        payload = {**base, "raw": raw, "error": error}
        cache.set(EGRESS_CACHE_KEY, payload, EGRESS_CACHE_SECONDS)
        return payload

    parsed = parse_cip_output(raw)
    payload = {**base, **parsed, "raw": raw, "status": "ok" if parsed.get("ip") else "error"}
    if not parsed.get("ip"):
        payload["error"] = "未能从 cip.cc 响应中解析出口 IP"
    cache.set(EGRESS_CACHE_KEY, payload, EGRESS_CACHE_SECONDS)
    return payload


def parse_cip_output(raw: str) -> dict:
    parsed = {"ip": "", "location": "", "isp": "", "url": ""}
    key_map = {
        "IP": "ip",
        "地址": "location",
        "运营商": "isp",
        "URL": "url",
    }
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip()
        target = key_map.get(normalized_key)
        if target:
            parsed[target] = value.strip()
    return parsed
