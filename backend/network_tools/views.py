from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request

from .models import PingHistoryRecord
from .services import (
    calculate_subnet,
    get_local_ip,
    run_ping_session,
    scan_ip_range,
    scan_ports,
    split_subnets,
    test_port,
)


@api_view(["GET"])
def local_ip(_request):
    try:
        return Response({"ip": get_local_ip()})
    except Exception as error:
        return bad_request(error)


@api_view(["POST"])
def ip_scan(request):
    try:
        network_segment = request.data.get("network_segment", request.data.get("network", ""))
        return Response(
            scan_ip_range(
                network_segment,
                int(request.data.get("host_start", 1)),
                int(request.data.get("host_end", 254)),
                int(request.data.get("timeout_ms", 900)),
                int(request.data.get("retries", 2)),
                int(request.data.get("concurrency", 64)),
            )
        )
    except Exception as error:
        return bad_request(error)


@api_view(["POST"])
def port_scan(request):
    try:
        ports_input = request.data.get("ports_input", request.data.get("ports", "1-1024"))
        return Response(
            scan_ports(
                request.data.get("host", ""),
                ports_input,
                int(request.data.get("timeout_ms", 2000)),
                int(request.data.get("concurrency", 50)),
            )
        )
    except Exception as error:
        return bad_request(error)


@api_view(["POST"])
def quick_port_test(request):
    try:
        return Response(
            test_port(
                request.data.get("host", ""),
                int(request.data.get("port", 80)),
                int(request.data.get("timeout_ms", 2000)),
            )
        )
    except Exception as error:
        return bad_request(error)


@api_view(["POST"])
def ping(request):
    try:
        target = request.data.get("host", "")
        count = int(request.data.get("count", 4))
        timeout_ms = int(request.data.get("timeout_ms", 3000))
        interval_ms = int(request.data.get("interval_ms", 1000))
        session = run_ping_session(target, count, timeout_ms, interval_ms)
        PingHistoryRecord.objects.create(target=target, **session["metrics"])
        return Response(session)
    except Exception as error:
        return bad_request(error)


@api_view(["POST"])
def subnet_calculate(request):
    try:
        result = calculate_subnet(
            request.data.get("input", "192.168.1.0/24"),
            int(request.data.get("prefix", 24)),
        )
        target_prefix = request.data.get("target_prefix")
        if target_prefix is not None:
            result["subnets"] = split_subnets(result["normalized_input"], int(target_prefix))
        return Response(result)
    except Exception as error:
        return bad_request(error)
