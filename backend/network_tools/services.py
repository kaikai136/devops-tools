import ipaddress
import platform
import re
import socket
import subprocess
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except OSError:
            return socket.gethostbyname(socket.gethostname())


def parse_network_segment(segment: str) -> str:
    parts = segment.strip().split(".")
    if len(parts) != 3:
        raise ValueError("请输入类似 192.168.1 的前三段地址")

    for part in parts:
        if not part.isdigit() or not 0 <= int(part) <= 255 or str(int(part)) != part:
            raise ValueError("每一段都必须是 0-255 之间的整数")

    return ".".join(parts)


def parse_ports(input_text: str) -> list[int]:
    ports: set[int] = set()
    tokens = [token.strip() for token in input_text.replace(",", " ").split() if token.strip()]
    if not tokens:
        raise ValueError("请至少输入一个端口")

    for token in tokens:
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = parse_port(start_text)
            end = parse_port(end_text)
            if start > end:
                raise ValueError(f"端口区间起始值不能大于结束值：{token}")
            ports.update(range(start, end + 1))
        else:
            ports.add(parse_port(token))

    return sorted(ports)


def parse_port(value: str) -> int:
    if not value.strip().isdigit():
        raise ValueError(f"无法识别端口：{value}")

    port = int(value)
    if port < 1 or port > 65535:
        raise ValueError("端口范围必须在 1 到 65535 之间")
    return port


def resolve_host(host: str) -> str:
    target = host.strip()
    if not target:
        raise ValueError("请输入目标主机")
    return socket.gethostbyname(target)


def is_private_ipv4(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).version == 4 and ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


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


def test_resolved_port(resolved: str, port: int, timeout_ms: int = 2000) -> dict:
    started = time.perf_counter()
    error_code = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(max(0.05, timeout_ms / 1000))
        try:
            error_code = sock.connect_ex((resolved, port))
            is_open = error_code == 0
        except OSError as error:
            error_code = getattr(error, "errno", -1) or -1
            is_open = False

    return {
        "host": resolved,
        "port": port,
        "is_open": is_open,
        "status": "open" if is_open else "closed",
        "error_code": error_code,
        "duration": round((time.perf_counter() - started) * 1000),
    }


def test_port(ip: str, port: int, timeout_ms: int = 2000) -> dict:
    try:
        resolved = resolve_host(ip)
    except Exception as error:
        target = ip.strip()
        if not target:
            raise
        return {
            "host": target,
            "port": port,
            "is_open": False,
            "duration": 0,
            "error": str(error),
        }

    return test_resolved_port(resolved, port, timeout_ms)


def detect_port_scan_false_positive(resolved: str, requested_ports: list[int], timeout_ms: int) -> str | None:
    if not is_private_ipv4(resolved):
        return None

    sentinel_ports = [65000, 65001, 65002, 65003, 65004]
    sentinel_ports = [port for port in sentinel_ports if port not in requested_ports][:3]
    if len(sentinel_ports) < 2:
        return None

    checks = [test_resolved_port(resolved, port, min(max(timeout_ms, 300), 800)) for port in sentinel_ports]
    open_sentinels = [check["port"] for check in checks if check["is_open"]]
    if len(open_sentinels) >= 2:
        return (
            f"目标 {resolved} 的异常高位端口 {', '.join(map(str, open_sentinels))} 也被判定为开放，"
            "当前网络可能被代理/TUN/防火墙接管，扫描结果不可信。请关闭系统代理/TUN 模式或切换到目标所在网卡后重试。"
        )

    return None


def scan_ports(host: str, ports_input: str, timeout_ms: int = 2000, concurrency: int = 50) -> dict:
    ports = parse_ports(ports_input)
    started = time.perf_counter()
    timeout_ms = max(100, min(5000, int(timeout_ms)))
    concurrency = max(1, min(512, int(concurrency), len(ports)))

    try:
        resolved = resolve_host(host)
    except Exception as error:
        target = host.strip()
        if not target:
            raise
        return {
            "host": target,
            "open_ports": [],
            "scanned_ports": len(ports),
            "duration": round((time.perf_counter() - started) * 1000),
            "error": str(error),
        }

    false_positive_error = detect_port_scan_false_positive(resolved, ports, timeout_ms)
    if false_positive_error:
        return {
            "host": resolved,
            "open_ports": [],
            "open_details": [],
            "scanned_ports": 0,
            "total_ports": len(ports),
            "timeout_ms": timeout_ms,
            "concurrency": concurrency,
            "duration": round((time.perf_counter() - started) * 1000),
            "error": false_positive_error,
        }

    open_ports: list[int] = []
    open_details: list[dict] = []
    scanned_count = 0
    port_iter = iter(ports)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        pending = set()
        for _ in range(concurrency):
            try:
                pending.add(executor.submit(test_resolved_port, resolved, next(port_iter), timeout_ms))
            except StopIteration:
                break

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                scanned_count += 1
                result = future.result()
                if result["is_open"]:
                    open_ports.append(result["port"])
                    open_details.append(
                        {
                            "port": result["port"],
                            "duration": result["duration"],
                            "service": guess_port_service(result["port"]),
                        }
                    )
                try:
                    pending.add(executor.submit(test_resolved_port, resolved, next(port_iter), timeout_ms))
                except StopIteration:
                    pass

    open_ports.sort()
    open_details.sort(key=lambda item: item["port"])
    return {
        "host": resolved,
        "open_ports": open_ports,
        "open_details": open_details,
        "scanned_ports": scanned_count,
        "total_ports": len(ports),
        "timeout_ms": timeout_ms,
        "concurrency": concurrency,
        "duration": round((time.perf_counter() - started) * 1000),
    }


def guess_port_service(port: int) -> str:
    services = {
        20: "FTP Data",
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        135: "RPC",
        139: "NetBIOS",
        143: "IMAP",
        443: "HTTPS",
        445: "SMB",
        465: "SMTPS",
        587: "SMTP",
        993: "IMAPS",
        995: "POP3S",
        1433: "SQL Server",
        1521: "Oracle",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        5900: "VNC",
        6379: "Redis",
        8000: "HTTP Alt",
        8080: "HTTP Proxy",
        8443: "HTTPS Alt",
        27017: "MongoDB",
    }
    return services.get(port, "未知")


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


def calculate_subnet(input_text: str, fallback_prefix: int = 24) -> dict:
    text = input_text.strip()
    if "/" not in text:
        text = f"{text}/{fallback_prefix}"

    interface = ipaddress.ip_interface(text)
    network = interface.network
    ip = interface.ip
    hosts = list(network.hosts()) if network.num_addresses <= 65536 else []
    first_host = hosts[0] if hosts else network.network_address
    last_host = hosts[-1] if hosts else network.broadcast_address

    return {
        "normalized_input": f"{ip}/{network.prefixlen}",
        "ip": str(ip),
        "prefix": network.prefixlen,
        "mask": str(network.netmask),
        "network": str(network.network_address),
        "broadcast": str(network.broadcast_address),
        "first_host": str(first_host),
        "last_host": str(last_host),
        "address_count": network.num_addresses,
        "usable_host_count": max(network.num_addresses - 2, 0) if network.prefixlen < 31 else network.num_addresses,
        "is_private": ip.is_private,
        "is_loopback": ip.is_loopback,
        "is_multicast": ip.is_multicast,
        "binary": {
            "ip": format(int(ip), "032b"),
            "mask": format(int(network.netmask), "032b"),
            "network": format(int(network.network_address), "032b"),
            "broadcast": format(int(network.broadcast_address), "032b"),
        },
    }


def split_subnets(input_text: str, target_prefix: int, limit: int = 64) -> list[dict]:
    network = ipaddress.ip_network(input_text, strict=False)
    subnets = list(network.subnets(new_prefix=target_prefix))[:limit]
    results = []
    for index, subnet in enumerate(subnets):
        hosts = list(subnet.hosts()) if subnet.num_addresses <= 65536 else []
        first_host = hosts[0] if hosts else subnet.network_address
        last_host = hosts[-1] if hosts else subnet.broadcast_address
        results.append(
            {
                "index": index + 1,
                "network": str(subnet.network_address),
                "cidr": str(subnet),
                "first_host": str(first_host),
                "last_host": str(last_host),
                "gateway": str(first_host),
                "broadcast": str(subnet.broadcast_address),
                "usable_host_count": max(subnet.num_addresses - 2, 0) if subnet.prefixlen < 31 else subnet.num_addresses,
            }
        )
    return results
