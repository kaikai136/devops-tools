import platform
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .addressing import parse_network_segment, resolve_host


def ping_once(host: str, timeout_ms: int = 3000) -> dict:
    ip = resolve_host(host)
    system = platform.system().lower()
    timeout_ms = max(200, min(5000, int(timeout_ms)))
    timeout_seconds = max(1, int(round(timeout_ms / 1000)))
    command = (
        ["ping", "-n", "1", "-w", str(timeout_ms), ip]
        if system == "windows"
        else ["ping", "-c", "1", "-W", str(timeout_seconds), ip]
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, (timeout_ms / 1000) + 0.8),
        )
        output = f"{completed.stdout}\n{completed.stderr}".lower()
        is_online = completed.returncode == 0 and (
            "ttl=" in output
            or re.search(r"\bbytes\s+from\b", output) is not None
            or re.search(r"(已接收|received)\s*=\s*[1-9]", output) is not None
            or re.search(r"\b[1-9]\s+(packets?\s+)?received\b", output) is not None
        )
    except subprocess.TimeoutExpired:
        is_online = False
    duration = round((time.perf_counter() - started) * 1000)

    return {
        "ip": ip,
        "status": "online" if is_online else "timeout",
        "response_time": duration if is_online else None,
    }


def ping_with_retries(host: str, timeout_ms: int, retries: int) -> dict:
    best_result = {"ip": host, "status": "timeout", "response_time": None}
    for _ in range(max(1, min(4, int(retries)))):
        result = ping_once(host, timeout_ms)
        if result["status"] == "online":
            if best_result["response_time"] is None or (result["response_time"] or 0) < best_result["response_time"]:
                best_result = result
        elif best_result["status"] != "online":
            best_result = result
    return best_result


def scan_ip_range(
    network_segment: str,
    host_start: int = 1,
    host_end: int = 254,
    timeout_ms: int = 900,
    retries: int = 2,
    concurrency: int = 64,
) -> dict:
    segment = parse_network_segment(network_segment)
    host_start = max(1, min(254, int(host_start)))
    host_end = max(1, min(254, int(host_end)))
    if host_start > host_end:
        raise ValueError("起始主机号不能大于结束主机号")

    ips = [f"{segment}.{host}" for host in range(host_start, host_end + 1)]
    started = time.perf_counter()
    timeout_ms = max(300, min(3000, int(timeout_ms)))
    retries = max(1, min(4, int(retries)))
    concurrency = max(8, min(96, int(concurrency), len(ips)))
    results = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(ping_with_retries, ip, timeout_ms, retries): ip for ip in ips}
        for future in as_completed(future_map):
            ip = future_map[future]
            host_number = int(ip.rsplit(".", 1)[1])
            try:
                result = future.result()
            except Exception:
                result = {"ip": ip, "status": "timeout", "response_time": None}
            results.append(
                {
                    "host": host_number,
                    "ip": ip,
                    "status": "online" if result["status"] == "online" else "offline",
                    "response_time": result["response_time"],
                    "open_ports": [],
                    "scanned_ports": 0,
                }
            )

    results.sort(key=lambda item: item["host"])
    return {
        "results": results,
        "total_hosts": len(results),
        "active_hosts": sum(1 for item in results if item["status"] == "online"),
        "open_port_count": 0,
        "timeout_ms": timeout_ms,
        "retries": retries,
        "concurrency": concurrency,
        "duration": round((time.perf_counter() - started) * 1000),
    }


def calculate_ping_metrics(entries: list[dict]) -> dict:
    total = len(entries)
    success = [entry["response_time"] for entry in entries if entry["status"] == "online"]
    failure_count = total - len(success)
    response_times = [value for value in success if value is not None]
    jitter_values = [
        abs(response_times[index] - response_times[index - 1])
        for index in range(1, len(response_times))
    ]

    return {
        "success_count": len(response_times),
        "failure_count": failure_count,
        "loss_rate": round((failure_count / total) * 100) if total else 0,
        "average_response_time": round(sum(response_times) / len(response_times)) if response_times else None,
        "min_response_time": min(response_times) if response_times else None,
        "max_response_time": max(response_times) if response_times else None,
        "jitter": round(sum(jitter_values) / len(jitter_values)) if jitter_values else None,
        "total_count": total,
    }


def run_ping_session(host: str, count: int, timeout_ms: int, interval_ms: int) -> dict:
    details = []
    bounded_count = max(1, min(200, count))
    for sequence in range(1, bounded_count + 1):
        result = ping_once(host, timeout_ms)
        details.append(
            {
                "sequence": sequence,
                "target": host,
                "ip": result["ip"],
                "status": result["status"],
                "response_time": result["response_time"],
                "timestamp": round(time.time() * 1000),
            }
        )
        if sequence < bounded_count:
            time.sleep(max(100, interval_ms) / 1000)

    return {"details": details, "metrics": calculate_ping_metrics(details)}
