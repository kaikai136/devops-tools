from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from io import StringIO

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from host_management.models import ManagedHost
from network_tools.services import parse_ports, scan_ports
from web_terminal.services import run_one_shot_ssh_command

from .models import SecurityScanFinding, SecurityScanHostResult, SecurityScanTask, VulnerabilityCache

DEFAULT_SECURITY_SCAN_PORTS = "21,22,23,25,53,80,110,139,143,443,445,3306,5432,5900,6379,8080,8443,27017"
MAX_SCAN_HOSTS = 50
MAX_SCAN_PORTS = 256
NVD_DISCLAIMER = "NVD 数据不代表 NVD 官方背书。"

PORT_RISK_RULES = {
    21: ("medium", "FTP 服务开放", "FTP 明文传输可能泄露凭据，建议改用 SFTP/FTPS。"),
    23: ("high", "Telnet 服务开放", "Telnet 明文传输风险较高，建议关闭并改用 SSH。"),
    3306: ("medium", "MySQL 服务开放", "数据库端口暴露会增加暴力破解和未授权访问风险。"),
    5432: ("medium", "PostgreSQL 服务开放", "数据库端口暴露会增加暴力破解和未授权访问风险。"),
    5900: ("high", "VNC 服务开放", "VNC 暴露可能被暴力破解或利用弱口令访问。"),
    6379: ("high", "Redis 服务开放", "Redis 暴露可能导致未授权访问和数据泄露。"),
    27017: ("high", "MongoDB 服务开放", "MongoDB 暴露可能导致未授权访问和数据泄露。"),
    445: ("medium", "SMB 服务开放", "SMB 暴露会增加横向移动和漏洞利用风险。"),
    3389: ("medium", "RDP 服务开放", "RDP 暴露会增加暴力破解风险。"),
}


def scannable_hosts_queryset() -> QuerySet[ManagedHost]:
    return ManagedHost.objects.select_related("group", "created_by").filter(verified=True, verify_status="verified").exclude(os="windows").exclude(login_user="")


def has_ssh_credential(host: ManagedHost) -> bool:
    return bool(host.login_user and (host.login_password or host.private_key))


def list_scannable_hosts() -> list[ManagedHost]:
    return [host for host in scannable_hosts_queryset() if has_ssh_credential(host)]


def normalize_scan_options(payload: dict) -> dict:
    ports_input = str(payload.get("portsInput") or payload.get("ports_input") or DEFAULT_SECURITY_SCAN_PORTS).strip()
    ports = parse_ports(ports_input)
    if len(ports) > MAX_SCAN_PORTS:
        raise ValueError(f"单台主机最多扫描 {MAX_SCAN_PORTS} 个端口")
    return {
        "portsInput": ports_input,
        "enableBaseline": bool(payload.get("enableBaseline", True)),
        "enablePortScan": bool(payload.get("enablePortScan", True)),
        "enableCveScan": bool(payload.get("enableCveScan", True)),
    }


def create_security_scan_task(user, payload: dict) -> SecurityScanTask:
    host_ids = payload.get("hostIds") or payload.get("host_ids") or []
    if not isinstance(host_ids, list) or not host_ids:
        raise ValueError("请选择要扫描的 Linux 主机")
    if len(host_ids) > MAX_SCAN_HOSTS:
        raise ValueError(f"每次最多选择 {MAX_SCAN_HOSTS} 台主机")
    options = normalize_scan_options(payload)
    hosts_by_id = {host.id: host for host in list_scannable_hosts() if host.id in set(int(item) for item in host_ids)}
    hosts = [hosts_by_id.get(int(host_id)) for host_id in host_ids if int(host_id) in hosts_by_id]
    if not hosts:
        raise ValueError("没有可扫描的 Linux 主机")

    task = SecurityScanTask.objects.create(
        name=str(payload.get("name", "")).strip() or f"安全扫描 {timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}",
        created_by=user if getattr(user, "is_authenticated", False) else None,
        target_count=len(hosts),
        options=options,
    )
    for host in hosts:
        SecurityScanHostResult.objects.create(
            task=task,
            host=host,
            host_name=host.name,
            host_ip=host.private_ip,
            host_port=host.port,
            login_user=host.login_user,
            os=host.os,
            system_type=host.system_type,
        )
    return task


def run_security_scan_task(task_id: int) -> None:
    task = SecurityScanTask.objects.get(id=task_id)
    task.status = SecurityScanTask.STATUS_RUNNING
    task.started_at = timezone.now()
    task.error = ""
    task.save(update_fields=["status", "started_at", "error"])
    try:
        for host_result in task.host_results.select_related("host").all():
            scan_host_result(host_result)
            refresh_task_counts(task)
        task.status = SecurityScanTask.STATUS_COMPLETED
    except Exception as error:
        task.status = SecurityScanTask.STATUS_FAILED
        task.error = str(error)
    finally:
        task.finished_at = timezone.now()
        refresh_task_counts(task)
        task.save(update_fields=["status", "error", "finished_at", "completed_count", "critical_count", "high_count", "medium_count", "low_count", "info_count"])


def scan_host_result(host_result: SecurityScanHostResult) -> None:
    host = host_result.host
    if host is None:
        mark_host_failed(host_result, "主机已不存在")
        return
    host_result.status = SecurityScanHostResult.STATUS_RUNNING
    host_result.started_at = timezone.now()
    host_result.error = ""
    host_result.save(update_fields=["status", "started_at", "error"])
    options = host_result.task.options
    try:
        system_info = collect_system_info(host)
        host_result.system_info = system_info
        packages = []
        if options.get("enableBaseline", True):
            create_baseline_findings(host_result, host, system_info)
        if options.get("enablePortScan", True):
            create_port_findings(host_result, host, options.get("portsInput", DEFAULT_SECURITY_SCAN_PORTS))
        if options.get("enableCveScan", True):
            packages = collect_packages(host, system_info)
            create_cve_findings(host_result, packages, system_info)
        host_result.package_count = len(packages)
        host_result.status = SecurityScanHostResult.STATUS_COMPLETED
    except Exception as error:
        host_result.status = SecurityScanHostResult.STATUS_FAILED
        host_result.error = str(error)
        add_finding(
            host_result,
            category="baseline",
            severity="high",
            title="SSH 安全扫描失败",
            description="无法通过 SSH 完成主机安全扫描。",
            evidence=str(error),
            recommendation="请检查主机网络、SSH 服务、账号密码或密钥配置。",
            source="baseline",
        )
    finally:
        host_result.finished_at = timezone.now()
        refresh_host_counts(host_result)
        host_result.save(
            update_fields=[
                "status",
                "system_info",
                "open_ports",
                "package_count",
                "error",
                "finished_at",
                "critical_count",
                "high_count",
                "medium_count",
                "low_count",
                "info_count",
            ]
        )


def mark_host_failed(host_result: SecurityScanHostResult, message: str) -> None:
    host_result.status = SecurityScanHostResult.STATUS_FAILED
    host_result.error = message
    host_result.finished_at = timezone.now()
    host_result.save(update_fields=["status", "error", "finished_at"])


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
        return parse_dpkg_packages(output)
    output = run_remote_command(host, "rpm -qa --qf '%{NAME}\\t%{VERSION}-%{RELEASE}\\n' 2>/dev/null || true")
    packages = parse_dpkg_packages(output)
    if not packages:
        add_system_unavailable_finding = getattr(collect_packages, "_add_finding", None)
        if add_system_unavailable_finding:
            add_system_unavailable_finding()
    return packages


def parse_dpkg_packages(output: str) -> list[dict]:
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


def create_baseline_findings(host_result: SecurityScanHostResult, host: ManagedHost, system_info: dict) -> None:
    if not system_info.get("id"):
        add_finding(
            host_result,
            category="baseline",
            severity="medium",
            title="系统版本无法识别",
            description="无法从 /etc/os-release 识别系统版本。",
            evidence=json.dumps(system_info, ensure_ascii=False),
            recommendation="请确认目标主机为受支持的 Linux 发行版。",
            source="baseline",
        )
    sshd_config = run_remote_command(host, "sshd -T 2>/dev/null | grep -E '^(permitrootlogin|passwordauthentication) ' || true")
    config = dict(line.split(None, 1) for line in sshd_config.splitlines() if " " in line)
    if config.get("permitrootlogin", "").lower() in {"yes", "without-password", "prohibit-password"}:
        add_finding(host_result, category="baseline", severity="high", title="SSH 允许 root 登录", evidence=sshd_config, recommendation="建议关闭 PermitRootLogin。", source="baseline")
    if config.get("passwordauthentication", "").lower() == "yes":
        add_finding(host_result, category="baseline", severity="medium", title="SSH 开启密码登录", evidence=sshd_config, recommendation="建议使用密钥登录并关闭 PasswordAuthentication。", source="baseline")
    firewall = run_remote_command(host, "ufw status 2>/dev/null || firewall-cmd --state 2>/dev/null || systemctl is-active firewalld 2>/dev/null || true")
    if "inactive" in firewall.lower() or "not running" in firewall.lower() or firewall.strip() in {"", "unknown"}:
        add_finding(host_result, category="baseline", severity="medium", title="防火墙未启用或状态未知", evidence=firewall, recommendation="建议启用 ufw/firewalld 并限制管理端口来源。", source="baseline")
    sudoers = run_remote_command(host, "grep -R \"NOPASSWD\" /etc/sudoers /etc/sudoers.d 2>/dev/null || true")
    if sudoers.strip():
        add_finding(host_result, category="baseline", severity="medium", title="存在免密 sudo 配置", evidence=sudoers[:2000], recommendation="请确认 NOPASSWD 授权是否必要，并限制到最小命令范围。", source="baseline")


def create_port_findings(host_result: SecurityScanHostResult, host: ManagedHost, ports_input: str) -> None:
    result = scan_ports(host.private_ip, ports_input, timeout_ms=2000, concurrency=50)
    open_details = result.get("open_details", [])
    host_result.open_ports = open_details
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
            host_result,
            category="port",
            severity=severity,
            title=title,
            evidence=f"{host.private_ip}:{port} open ({service})",
            recommendation=recommendation,
            port=port,
            service=service,
            source="port",
        )


def create_cve_findings(host_result: SecurityScanHostResult, packages: list[dict], system_info: dict) -> None:
    ecosystem = osv_ecosystem(system_info)
    if not ecosystem:
        add_finding(
            host_result,
            category="cve",
            severity="medium",
            title="系统发行版不支持 CVE 匹配",
            description="当前系统无法映射到 OSV 支持的 Linux 生态。",
            evidence=json.dumps(system_info, ensure_ascii=False),
            recommendation="请确认系统版本，或后续接入对应发行版漏洞源。",
            source="osv",
        )
        return
    for package in packages:
        vulnerabilities = query_osv_vulnerabilities(ecosystem, package["name"], package["version"], host_result=host_result)
        for vulnerability in vulnerabilities:
            cve_id = primary_cve_id(vulnerability)
            nvd = fetch_nvd_cve(cve_id) if cve_id else {}
            cvss = nvd.get("cvss")
            severity = severity_from_cvss(cvss)
            references = merge_references(vulnerability, nvd)
            add_finding(
                host_result,
                category="cve",
                severity=severity,
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
                references=references,
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


def query_osv_vulnerabilities(ecosystem: str, package_name: str, version: str, host_result: SecurityScanHostResult | None = None) -> list[dict]:
    cache_key = f"{ecosystem}:{package_name}:{version}"
    cached = VulnerabilityCache.objects.filter(source=VulnerabilityCache.SOURCE_OSV, cache_key=cache_key).first()
    if cached and cached.payload:
        return cached.payload.get("vulns", [])
    payload = {"version": version, "package": {"name": package_name, "ecosystem": ecosystem}}
    response = post_json("https://api.osv.dev/v1/query", payload)
    if response.get("_error"):
        VulnerabilityCache.objects.update_or_create(
            source=VulnerabilityCache.SOURCE_OSV,
            cache_key=cache_key,
            defaults={"payload": {}, "error": str(response["_error"])},
        )
        if host_result:
            add_finding(
                host_result,
                category="cve",
                severity="info",
                title="OSV 漏洞源查询失败",
                description="该软件包的 OSV 查询失败，已保留其他扫描结果。",
                evidence=f"{package_name} {version}: {response['_error']}",
                recommendation="请稍后重试，或检查服务器访问 https://api.osv.dev 的网络连通性。",
                package_name=package_name,
                current_version=version,
                source="osv",
            )
        return []
    VulnerabilityCache.objects.update_or_create(
        source=VulnerabilityCache.SOURCE_OSV,
        cache_key=cache_key,
        defaults={"payload": response, "error": ""},
    )
    return response.get("vulns", [])


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
        "description": next((item.get("value", "") for item in descriptions if item.get("lang") == "zh" or item.get("lang") == "en"), ""),
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
        return "medium"
    if value >= 9:
        return "critical"
    if value >= 7:
        return "high"
    if value >= 4:
        return "medium"
    return "low"


def add_finding(host_result: SecurityScanHostResult, **kwargs) -> SecurityScanFinding:
    return SecurityScanFinding.objects.create(task=host_result.task, host_result=host_result, **kwargs)


def refresh_host_counts(host_result: SecurityScanHostResult) -> None:
    counts = finding_counts(host_result.findings.all())
    for key, value in counts.items():
        setattr(host_result, f"{key}_count", value)


def refresh_task_counts(task: SecurityScanTask) -> None:
    findings = task.findings.all()
    counts = finding_counts(findings)
    for key, value in counts.items():
        setattr(task, f"{key}_count", value)
    task.completed_count = task.host_results.filter(status__in=[SecurityScanHostResult.STATUS_COMPLETED, SecurityScanHostResult.STATUS_FAILED]).count()
    task.save(update_fields=["completed_count", "critical_count", "high_count", "medium_count", "low_count", "info_count"])


def finding_counts(queryset) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for severity in queryset.values_list("severity", flat=True):
        if severity in counts:
            counts[severity] += 1
    return counts


def export_task_json(task: SecurityScanTask) -> dict:
    from .serializers import SecurityScanTaskExportSerializer

    return {"disclaimer": NVD_DISCLAIMER, "task": SecurityScanTaskExportSerializer(task).data}


def export_task_csv(task: SecurityScanTask) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["任务", "主机", "IP", "严重级别", "分类", "标题", "CVE", "包名", "当前版本", "修复版本", "端口", "服务", "CVSS", "建议", "来源"])
    for finding in task.findings.select_related("host_result").all():
        writer.writerow(
            [
                task.name,
                finding.host_result.host_name,
                finding.host_result.host_ip,
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
