from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from io import StringIO

from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from host_management.models import ManagedHost
from network_tools.services import parse_ports, scan_ports
from system_management.models import SystemSetting
from web_terminal.services import run_one_shot_ssh_command

from .models import ScanFinding, ScanTargetResult, ScanTask, VulnerabilityCache

DEFAULT_SECURITY_SCAN_PORTS = "21,22,23,25,53,80,110,139,143,443,445,3306,3389,5432,5900,6379,8080,8443,27017"
MAX_SCAN_TARGETS = 50
MAX_SCAN_PORTS = 256
SECURITY_SCAN_SETTING_KEY = "security_scan"
NVD_DISCLAIMER = "NVD 数据仅用于漏洞信息补充，不代表 NVD 官方背书。"

DEFAULT_SCAN_MODULES = {"baseline": True, "ports": True, "cve": False}

PORT_RISK_RULES = {
    21: ("medium", "FTP 服务开放", "FTP 明文传输可能泄露凭据，建议改用 SFTP/FTPS。"),
    23: ("high", "Telnet 服务开放", "Telnet 明文传输风险较高，建议关闭并改用 SSH。"),
    3306: ("medium", "MySQL 服务开放", "数据库端口暴露会增加暴力破解和未授权访问风险。"),
    3389: ("medium", "RDP 服务开放", "RDP 暴露会增加暴力破解风险，请限制来源。"),
    5432: ("medium", "PostgreSQL 服务开放", "数据库端口暴露会增加暴力破解和未授权访问风险。"),
    5900: ("high", "VNC 服务开放", "VNC 暴露可能被暴力破解或利用弱口令访问。"),
    6379: ("high", "Redis 服务开放", "Redis 暴露可能导致未授权访问和数据泄露。"),
    27017: ("high", "MongoDB 服务开放", "MongoDB 暴露可能导致未授权访问和数据泄露。"),
    445: ("medium", "SMB 服务开放", "SMB 暴露会增加横向移动和漏洞利用风险。"),
}


def security_scan_settings() -> dict:
    setting = SystemSetting.objects.filter(key=SECURITY_SCAN_SETTING_KEY).first()
    value = setting.value if setting and isinstance(setting.value, dict) else {}
    return {
        "onlineCveEnabled": bool(value.get("onlineCveEnabled", False)),
        "nvdApiKeyConfigured": bool(os.environ.get("NVD_API_KEY", "").strip()),
        "sources": ["OSV", "NVD"] if value.get("onlineCveEnabled", False) else [],
    }


def scannable_targets_queryset() -> QuerySet[ManagedHost]:
    return ManagedHost.objects.select_related("group", "created_by").filter(verified=True, verify_status="verified").exclude(os="windows").exclude(login_user="")


def has_ssh_credential(host: ManagedHost) -> bool:
    return bool(host.login_user and (host.login_password or host.private_key))


def list_scannable_targets() -> list[ManagedHost]:
    return [host for host in scannable_targets_queryset() if has_ssh_credential(host)]


def normalize_scan_modules(payload: dict) -> dict:
    raw_modules = payload.get("scanModules") or payload.get("scan_modules") or {}
    if not isinstance(raw_modules, dict):
        raw_modules = {}
    modules = {
        "baseline": bool(raw_modules.get("baseline", DEFAULT_SCAN_MODULES["baseline"])),
        "ports": bool(raw_modules.get("ports", raw_modules.get("portScan", DEFAULT_SCAN_MODULES["ports"]))),
        "cve": bool(raw_modules.get("cve", DEFAULT_SCAN_MODULES["cve"])),
    }
    if not any(modules.values()):
        raise ValueError("请至少选择一个扫描模块")
    return modules


def normalize_scan_options(payload: dict) -> dict:
    ports_input = str(payload.get("portsInput") or payload.get("ports_input") or DEFAULT_SECURITY_SCAN_PORTS).strip()
    ports = parse_ports(ports_input)
    if len(ports) > MAX_SCAN_PORTS:
        raise ValueError(f"单台主机最多扫描 {MAX_SCAN_PORTS} 个端口")
    return {
        "portsInput": ports_input,
        "portTimeoutMs": 2000,
        "portConcurrency": 50,
    }


def create_scan_task(user, payload: dict) -> ScanTask:
    target_ids = payload.get("targetIds") or payload.get("target_ids") or payload.get("hostIds") or []
    if not isinstance(target_ids, list) or not target_ids:
        raise ValueError("请选择要扫描的 Linux SSH 主机")
    if len(target_ids) > MAX_SCAN_TARGETS:
        raise ValueError(f"每次最多选择 {MAX_SCAN_TARGETS} 台主机")
    target_ids = [int(item) for item in target_ids]
    options = normalize_scan_options(payload)
    modules = normalize_scan_modules(payload)
    source = security_scan_settings()
    hosts_by_id = {host.id: host for host in list_scannable_targets() if host.id in set(target_ids)}
    hosts = [hosts_by_id[target_id] for target_id in target_ids if target_id in hosts_by_id]
    if not hosts:
        raise ValueError("没有可扫描的 Linux SSH 主机")

    task = ScanTask.objects.create(
        name=str(payload.get("name", "")).strip() or f"安全巡检 {timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}",
        created_by=user if getattr(user, "is_authenticated", False) else None,
        target_count=len(hosts),
        scan_modules=modules,
        options=options,
        vulnerability_source=source,
    )
    for host in hosts:
        ScanTargetResult.objects.create(
            task=task,
            host=host,
            host_name=host.name,
            host_ip=host.private_ip,
            host_port=host.port,
            login_user=host.login_user,
            os=host.os,
            system_type=host.system_type,
            system_arch=host.system_arch,
        )
    return task


def run_scan_task(task_id: int, retry_target_ids: list[int] | None = None) -> None:
    task = ScanTask.objects.get(id=task_id)
    task.status = ScanTask.STATUS_RUNNING
    task.started_at = task.started_at or timezone.now()
    task.finished_at = None
    task.error = ""
    task.cancel_requested = False if retry_target_ids else task.cancel_requested
    task.save(update_fields=["status", "started_at", "finished_at", "error", "cancel_requested"])
    queryset = task.target_results.select_related("host").all()
    if retry_target_ids is not None:
        queryset = queryset.filter(id__in=retry_target_ids)
    try:
        for target_result in queryset:
            task.refresh_from_db(fields=["cancel_requested", "status"])
            if task.cancel_requested:
                mark_target_skipped(target_result, "任务已取消，跳过后续主机")
                continue
            scan_target_result(target_result)
            refresh_task_counts(task)
        task.refresh_from_db(fields=["cancel_requested"])
        task.status = ScanTask.STATUS_CANCELED if task.cancel_requested else final_task_status(task)
    except Exception as error:
        task.status = ScanTask.STATUS_FAILED
        task.error = str(error)
    finally:
        task.finished_at = timezone.now()
        refresh_task_counts(task)
        task.save(update_fields=["status", "error", "finished_at", "completed_count", "failed_count", "critical_count", "high_count", "medium_count", "low_count", "info_count"])


def final_task_status(task: ScanTask) -> str:
    failed = task.target_results.filter(status=ScanTargetResult.STATUS_FAILED).exists()
    pending = task.target_results.filter(status__in=[ScanTargetResult.STATUS_PENDING, ScanTargetResult.STATUS_RUNNING]).exists()
    if pending:
        return ScanTask.STATUS_RUNNING
    return ScanTask.STATUS_FAILED if failed else ScanTask.STATUS_COMPLETED


def scan_target_result(target_result: ScanTargetResult) -> None:
    host = target_result.host
    if host is None:
        mark_target_failed(target_result, "主机已不存在")
        return
    target_result.status = ScanTargetResult.STATUS_RUNNING
    target_result.started_at = timezone.now()
    target_result.finished_at = None
    target_result.error = ""
    target_result.skipped_modules = []
    target_result.save(update_fields=["status", "started_at", "finished_at", "error", "skipped_modules"])
    task = target_result.task
    modules = task.scan_modules or DEFAULT_SCAN_MODULES
    try:
        system_info = collect_system_info(host)
        target_result.system_info = system_info
        packages = []
        if modules.get("baseline", True):
            create_baseline_findings(target_result, host, system_info)
        if modules.get("ports", True):
            create_port_findings(target_result, host, task.options.get("portsInput", DEFAULT_SECURITY_SCAN_PORTS))
        if modules.get("cve", False):
            if not (task.vulnerability_source or {}).get("onlineCveEnabled"):
                target_result.skipped_modules = sorted(set([*target_result.skipped_modules, "cve"]))
            else:
                packages = collect_packages(host, system_info)
                create_cve_findings(target_result, packages, system_info)
        target_result.package_count = len(packages)
        target_result.status = ScanTargetResult.STATUS_COMPLETED
    except Exception as error:
        target_result.status = ScanTargetResult.STATUS_FAILED
        target_result.error = str(error)
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_BASELINE,
            severity=ScanFinding.SEVERITY_HIGH,
            title="SSH 安全扫描失败",
            description="无法通过 SSH 完成主机安全扫描。",
            evidence=str(error),
            recommendation="请检查主机网络、SSH 服务、账号密码或密钥配置。",
            source="baseline",
        )
    finally:
        target_result.finished_at = timezone.now()
        refresh_target_counts(target_result)
        target_result.save(
            update_fields=[
                "status",
                "system_info",
                "open_ports",
                "package_count",
                "skipped_modules",
                "error",
                "finished_at",
                "critical_count",
                "high_count",
                "medium_count",
                "low_count",
                "info_count",
            ]
        )


def mark_target_failed(target_result: ScanTargetResult, message: str) -> None:
    target_result.status = ScanTargetResult.STATUS_FAILED
    target_result.error = message
    target_result.finished_at = timezone.now()
    target_result.save(update_fields=["status", "error", "finished_at"])


def mark_target_skipped(target_result: ScanTargetResult, message: str) -> None:
    if target_result.status in {ScanTargetResult.STATUS_COMPLETED, ScanTargetResult.STATUS_FAILED}:
        return
    target_result.status = ScanTargetResult.STATUS_SKIPPED
    target_result.error = message
    target_result.finished_at = timezone.now()
    target_result.save(update_fields=["status", "error", "finished_at"])


def prepare_failed_targets_for_retry(task: ScanTask) -> list[int]:
    failed_targets = list(task.target_results.filter(status=ScanTargetResult.STATUS_FAILED))
    if not failed_targets:
        raise ValueError("当前任务没有失败主机可重试")
    failed_ids = [target.id for target in failed_targets]
    ScanFinding.objects.filter(target_result_id__in=failed_ids).delete()
    ScanTargetResult.objects.filter(id__in=failed_ids).update(
        status=ScanTargetResult.STATUS_PENDING,
        error="",
        system_info={},
        open_ports=[],
        package_count=0,
        skipped_modules=[],
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        info_count=0,
        started_at=None,
        finished_at=None,
    )
    task.cancel_requested = False
    task.status = ScanTask.STATUS_QUEUED
    task.finished_at = None
    task.error = ""
    task.save(update_fields=["cancel_requested", "status", "finished_at", "error"])
    refresh_task_counts(task)
    return failed_ids


def run_remote_command(host: ManagedHost, command: str) -> str:
    return run_one_shot_ssh_command(host, command)


def collect_system_info(host: ManagedHost) -> dict:
    output = run_remote_command(
        host,
        "if [ -r /etc/os-release ]; then cat /etc/os-release; fi; printf '\\n__UNAME__\\n'; uname -a 2>/dev/null || true",
    )
    system_info = parse_os_release(output)
    system_info["kernel"] = output.split("__UNAME__", 1)[1].strip() if "__UNAME__" in output else ""
    return system_info


def parse_os_release(output: str) -> dict:
    release_part = output.split("__UNAME__", 1)[0]
    result = {}
    for line in release_part.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip().lower()] = value.strip().strip('"')
    return {
        "id": result.get("id", ""),
        "versionId": result.get("version_id", ""),
        "prettyName": result.get("pretty_name", ""),
    }


def collect_packages(host: ManagedHost, system_info: dict) -> list[dict]:
    os_id = str(system_info.get("id", "")).lower()
    if os_id in {"ubuntu", "debian"}:
        output = run_remote_command(host, "dpkg-query -W -f='${Package}\\t${Version}\\n' 2>/dev/null || true")
        return parse_package_lines(output)
    output = run_remote_command(host, "rpm -qa --qf '%{NAME}\\t%{VERSION}-%{RELEASE}\\n' 2>/dev/null || true")
    return parse_package_lines(output)


def parse_package_lines(output: str) -> list[dict]:
    packages = []
    for line in output.splitlines():
        if "\t" not in line:
            continue
        name, version = line.split("\t", 1)
        name = name.strip()
        version = version.strip()
        if name and version:
            packages.append({"name": name, "version": version})
    return packages


def create_baseline_findings(target_result: ScanTargetResult, host: ManagedHost, system_info: dict) -> None:
    if not system_info.get("id"):
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_BASELINE,
            severity=ScanFinding.SEVERITY_MEDIUM,
            title="系统版本无法识别",
            description="无法从 /etc/os-release 识别系统版本。",
            evidence=json.dumps(system_info, ensure_ascii=False),
            recommendation="请确认目标主机为受支持的 Linux 发行版。",
            source="baseline",
        )
    sshd_config = run_remote_command(host, "sshd -T 2>/dev/null | grep -E '^(permitrootlogin|passwordauthentication) ' || true")
    config = dict(line.split(None, 1) for line in sshd_config.splitlines() if " " in line)
    if config.get("permitrootlogin", "").lower() in {"yes", "without-password", "prohibit-password"}:
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_BASELINE,
            severity=ScanFinding.SEVERITY_HIGH,
            title="SSH 允许 root 登录",
            evidence=sshd_config,
            recommendation="建议关闭 PermitRootLogin，并使用普通账号加 sudo 提权。",
            source="baseline",
        )
    if config.get("passwordauthentication", "").lower() == "yes":
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_BASELINE,
            severity=ScanFinding.SEVERITY_MEDIUM,
            title="SSH 开启密码登录",
            evidence=sshd_config,
            recommendation="建议使用密钥登录并关闭 PasswordAuthentication。",
            source="baseline",
        )
    firewall = run_remote_command(host, "ufw status 2>/dev/null || firewall-cmd --state 2>/dev/null || systemctl is-active firewalld 2>/dev/null || true")
    if "inactive" in firewall.lower() or "not running" in firewall.lower() or firewall.strip() in {"", "unknown"}:
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_BASELINE,
            severity=ScanFinding.SEVERITY_MEDIUM,
            title="防火墙未启用或状态未知",
            evidence=firewall,
            recommendation="建议启用 ufw/firewalld 并限制管理端口来源。",
            source="baseline",
        )
    sudoers = run_remote_command(host, 'grep -R "NOPASSWD" /etc/sudoers /etc/sudoers.d 2>/dev/null || true')
    if sudoers.strip():
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_BASELINE,
            severity=ScanFinding.SEVERITY_MEDIUM,
            title="存在免密 sudo 配置",
            evidence=sudoers[:2000],
            recommendation="请确认 NOPASSWD 授权是否必要，并限制到最小命令范围。",
            source="baseline",
        )


def create_port_findings(target_result: ScanTargetResult, host: ManagedHost, ports_input: str) -> None:
    result = scan_ports(host.private_ip, ports_input, timeout_ms=2000, concurrency=50)
    open_details = result.get("open_details", [])
    target_result.open_ports = open_details
    if result.get("error"):
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_PORT,
            severity=ScanFinding.SEVERITY_INFO,
            title="端口扫描结果不可信",
            evidence=str(result["error"]),
            recommendation="请调整扫描网络环境后重试。",
            source="port",
        )
        return
    for detail in open_details:
        port = int(detail.get("port", 0))
        service = str(detail.get("service", "未知"))
        if port in PORT_RISK_RULES:
            severity, title, recommendation = PORT_RISK_RULES[port]
        elif port in {22, 80, 443, 8080, 8443}:
            severity, title, recommendation = "info", f"{service} 服务开放", "请确认该服务需要对当前网络开放，并配置访问控制。"
        else:
            severity, title, recommendation = "low", f"{service} 端口开放", "请确认端口暴露符合安全策略。"
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_PORT,
            severity=severity,
            title=title,
            evidence=f"{host.private_ip}:{port} open ({service})",
            recommendation=recommendation,
            port=port,
            service=service,
            source="port",
        )


def create_cve_findings(target_result: ScanTargetResult, packages: list[dict], system_info: dict) -> None:
    ecosystem = osv_ecosystem(system_info)
    if not ecosystem:
        add_finding(
            target_result,
            category=ScanFinding.CATEGORY_CVE,
            severity=ScanFinding.SEVERITY_MEDIUM,
            title="系统发行版不支持 CVE 匹配",
            description="当前系统无法映射到 OSV 支持的 Linux 生态。",
            evidence=json.dumps(system_info, ensure_ascii=False),
            recommendation="请确认系统版本，或后续接入对应发行版漏洞源。",
            source="osv",
        )
        return
    vulnerabilities_by_package = query_osv_batch(ecosystem, packages, target_result=target_result)
    for package in packages:
        for vulnerability in vulnerabilities_by_package.get(package["name"], []):
            cve_id = primary_cve_id(vulnerability)
            nvd = fetch_nvd_cve(cve_id) if cve_id else {}
            cvss = nvd.get("cvss")
            add_finding(
                target_result,
                category=ScanFinding.CATEGORY_CVE,
                severity=severity_from_cvss(cvss),
                title=vulnerability.get("summary") or cve_id or vulnerability.get("id") or f"{package['name']} 存在漏洞",
                description=nvd.get("description") or vulnerability.get("details", ""),
                evidence=f"{package['name']} {package['version']}",
                recommendation="请评估影响并升级到修复版本。" if fixed_version_from_osv(vulnerability) else "请评估影响并关注发行版安全公告。",
                cve_id=cve_id,
                package_name=package["name"],
                current_version=package["version"],
                fixed_version=fixed_version_from_osv(vulnerability),
                cvss=cvss,
                cwe=nvd.get("cwe", ""),
                source="osv+nvd" if nvd else "osv",
                references=merge_references(vulnerability, nvd),
                raw={"osv": vulnerability, "nvd": nvd, "disclaimer": NVD_DISCLAIMER},
            )


def osv_ecosystem(system_info: dict) -> str:
    os_id = str(system_info.get("id", "")).lower()
    version = str(system_info.get("versionId", "")).split(".", 1)[0]
    if os_id == "ubuntu" and version:
        return f"Ubuntu:{version}.04" if version in {"18", "20", "22", "24"} else "Ubuntu"
    if os_id == "debian":
        return "Debian"
    if os_id in {"centos", "rhel", "rocky", "almalinux", "fedora"}:
        return "Red Hat"
    return ""


def query_osv_batch(ecosystem: str, packages: list[dict], target_result: ScanTargetResult | None = None) -> dict[str, list[dict]]:
    if not packages:
        return {}
    cache_key = batch_cache_key(ecosystem, packages)
    cached = VulnerabilityCache.objects.filter(source=VulnerabilityCache.SOURCE_OSV_BATCH, cache_key=cache_key).first()
    if cached and cached.payload:
        return cached.payload.get("vulnerabilitiesByPackage", {})
    payload = {
        "queries": [
            {"version": package["version"], "package": {"name": package["name"], "ecosystem": ecosystem}}
            for package in packages
        ]
    }
    response = post_json("https://api.osv.dev/v1/querybatch", payload)
    if response.get("_error"):
        VulnerabilityCache.objects.update_or_create(
            source=VulnerabilityCache.SOURCE_OSV_BATCH,
            cache_key=cache_key,
            defaults={"payload": {}, "error": str(response["_error"])},
        )
        if target_result:
            add_finding(
                target_result,
                category=ScanFinding.CATEGORY_CVE,
                severity=ScanFinding.SEVERITY_INFO,
                title="OSV 漏洞源查询失败",
                description="OSV 批量查询失败，已保留其他扫描结果。",
                evidence=str(response["_error"]),
                recommendation="请稍后重试，或检查服务器访问 https://api.osv.dev 的网络连通性。",
                source="osv",
            )
        return {}
    results = response.get("results") or []
    grouped: dict[str, list[dict]] = {}
    for package, result in zip(packages, results):
        grouped[package["name"]] = result.get("vulns") or []
    VulnerabilityCache.objects.update_or_create(
        source=VulnerabilityCache.SOURCE_OSV_BATCH,
        cache_key=cache_key,
        defaults={"payload": {"vulnerabilitiesByPackage": grouped}, "error": ""},
    )
    return grouped


def batch_cache_key(ecosystem: str, packages: list[dict]) -> str:
    parts = [f"{package['name']}@{package['version']}" for package in packages]
    return f"{ecosystem}:" + "|".join(parts)[:280]


def fetch_nvd_cve(cve_id: str) -> dict:
    cached = VulnerabilityCache.objects.filter(source=VulnerabilityCache.SOURCE_NVD, cache_key=cve_id).first()
    if cached and cached.payload:
        return cached.payload
    query = urllib.parse.urlencode({"cveId": cve_id})
    request = urllib.request.Request(f"https://services.nvd.nist.gov/rest/json/cves/2.0?{query}")
    api_key = os.environ.get("NVD_API_KEY", "").strip()
    if api_key:
        request.add_header("apiKey", api_key)
    data = request_json(request)
    if data.get("_error"):
        VulnerabilityCache.objects.update_or_create(
            source=VulnerabilityCache.SOURCE_NVD,
            cache_key=cve_id,
            defaults={"payload": {}, "error": str(data["_error"])},
        )
        return {}
    normalized = normalize_nvd_payload(data)
    VulnerabilityCache.objects.update_or_create(
        source=VulnerabilityCache.SOURCE_NVD,
        cache_key=cve_id,
        defaults={"payload": normalized, "error": ""},
    )
    time.sleep(0.7 if api_key else 6.1)
    return normalized


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    return request_json(request)


def request_json(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return {"_error": str(error)}


def normalize_nvd_payload(payload: dict) -> dict:
    vulnerabilities = payload.get("vulnerabilities") or []
    if not vulnerabilities:
        return {}
    cve = vulnerabilities[0].get("cve", {})
    metrics = cve.get("metrics", {})
    cvss = None
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key) or []
        if entries:
            cvss = entries[0].get("cvssData", {}).get("baseScore")
            break
    descriptions = cve.get("descriptions") or []
    weaknesses = cve.get("weaknesses") or []
    refs = cve.get("references", {}).get("referenceData", [])
    return {
        "cvss": cvss,
        "description": next((item.get("value", "") for item in descriptions if item.get("lang") in {"zh", "en"}), ""),
        "cwe": next((desc.get("value", "") for weakness in weaknesses for desc in weakness.get("description", []) if desc.get("value")), ""),
        "references": [item.get("url") for item in refs if item.get("url")],
        "disclaimer": NVD_DISCLAIMER,
    }


def primary_cve_id(vulnerability: dict) -> str:
    candidates = [vulnerability.get("id", "")]
    candidates.extend(vulnerability.get("aliases") or [])
    return next((item for item in candidates if str(item).startswith("CVE-")), str(vulnerability.get("id", "")))


def fixed_version_from_osv(vulnerability: dict) -> str:
    for affected in vulnerability.get("affected", []) or []:
        for range_item in affected.get("ranges", []) or []:
            for event in range_item.get("events", []) or []:
                if event.get("fixed"):
                    return str(event["fixed"])
    return ""


def merge_references(vulnerability: dict, nvd: dict) -> list[str]:
    refs = [item.get("url") for item in vulnerability.get("references", []) if item.get("url")]
    refs.extend(nvd.get("references") or [])
    return list(dict.fromkeys(refs))


def severity_from_cvss(score) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return ScanFinding.SEVERITY_MEDIUM
    if value >= 9:
        return ScanFinding.SEVERITY_CRITICAL
    if value >= 7:
        return ScanFinding.SEVERITY_HIGH
    if value >= 4:
        return ScanFinding.SEVERITY_MEDIUM
    return ScanFinding.SEVERITY_LOW


def add_finding(target_result: ScanTargetResult, **kwargs) -> ScanFinding:
    return ScanFinding.objects.create(task=target_result.task, target_result=target_result, **kwargs)


def refresh_target_counts(target_result: ScanTargetResult) -> None:
    counts = finding_counts(target_result.findings.all())
    for key, value in counts.items():
        setattr(target_result, f"{key}_count", value)


def refresh_task_counts(task: ScanTask) -> None:
    task.refresh_from_db(fields=["id"])
    counts = finding_counts(task.findings.all())
    for key, value in counts.items():
        setattr(task, f"{key}_count", value)
    task.completed_count = task.target_results.filter(status__in=[ScanTargetResult.STATUS_COMPLETED, ScanTargetResult.STATUS_FAILED, ScanTargetResult.STATUS_SKIPPED]).count()
    task.failed_count = task.target_results.filter(status=ScanTargetResult.STATUS_FAILED).count()
    task.save(update_fields=["completed_count", "failed_count", "critical_count", "high_count", "medium_count", "low_count", "info_count"])


def finding_counts(queryset) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for severity in queryset.values_list("severity", flat=True):
        if severity in counts:
            counts[severity] += 1
    return counts


def summary_payload() -> dict:
    source = security_scan_settings()
    aggregate = ScanTask.objects.aggregate(
        critical=Sum("critical_count"),
        high=Sum("high_count"),
        medium=Sum("medium_count"),
        low=Sum("low_count"),
        info=Sum("info_count"),
    )
    return {
        "riskCounts": {key: int(aggregate.get(key) or 0) for key in ["critical", "high", "medium", "low", "info"]},
        "taskCounts": {
            "total": ScanTask.objects.count(),
            "running": ScanTask.objects.filter(status__in=[ScanTask.STATUS_QUEUED, ScanTask.STATUS_RUNNING]).count(),
            "failed": ScanTask.objects.filter(status=ScanTask.STATUS_FAILED).count(),
        },
        "failedTargetCount": ScanTargetResult.objects.filter(status=ScanTargetResult.STATUS_FAILED).count(),
        "latestTaskId": ScanTask.objects.order_by("-created_at", "-id").values_list("id", flat=True).first(),
        "vulnerabilitySource": source,
    }


def filter_findings(task_id: int, params) -> QuerySet[ScanFinding]:
    queryset = ScanFinding.objects.select_related("target_result").filter(task_id=task_id).order_by("id")
    severity = str(params.get("severity", "")).strip()
    category = str(params.get("category", "")).strip()
    host_id = str(params.get("hostId", "") or params.get("host", "")).strip()
    keyword = str(params.get("keyword", "")).strip()
    if severity:
        queryset = queryset.filter(severity=severity)
    if category:
        queryset = queryset.filter(category=category)
    if host_id:
        queryset = queryset.filter(target_result_id=int(host_id))
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword)
            | Q(recommendation__icontains=keyword)
            | Q(cve_id__icontains=keyword)
            | Q(package_name__icontains=keyword)
            | Q(target_result__host_name__icontains=keyword)
            | Q(target_result__host_ip__icontains=keyword)
        )
    return queryset


def export_task_json(task: ScanTask) -> dict:
    from .serializers import ScanTaskExportSerializer

    return {"disclaimer": NVD_DISCLAIMER, "task": ScanTaskExportSerializer(task).data}


def export_task_csv(task: ScanTask) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["任务", "主机", "IP", "严重级别", "分类", "标题", "CVE", "包名", "当前版本", "修复版本", "端口", "服务", "CVSS", "建议", "来源"])
    for finding in task.findings.select_related("target_result").all():
        writer.writerow(
            [
                task.name,
                finding.target_result.host_name,
                finding.target_result.host_ip,
                finding.severity,
                finding.category,
                finding.title,
                finding.cve_id,
                finding.package_name,
                finding.current_version,
                finding.fixed_version,
                finding.port or "",
                finding.service,
                finding.cvss if finding.cvss is not None else "",
                finding.recommendation,
                finding.source,
            ]
        )
    writer.writerow([])
    writer.writerow([NVD_DISCLAIMER])
    return "\ufeff" + output.getvalue()
