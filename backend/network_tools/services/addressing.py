import ipaddress
import socket


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
