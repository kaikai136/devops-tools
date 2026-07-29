import socket
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from .addressing import is_private_ipv4, resolve_host


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
