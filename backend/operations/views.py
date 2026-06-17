from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import AuthenticatorEntry, PasswordRecord, PingHistoryRecord
from .serializers import (
    AuthenticatorEntrySerializer,
    PasswordRecordSerializer,
    PingHistoryRecordSerializer,
)
from .services import (
    build_totp_uri,
    calculate_subnet,
    generate_password,
    generate_qr_data_url,
    generate_totp,
    get_local_ip,
    normalize_totp_algorithm,
    normalize_totp_secret,
    ping_once,
    run_ping_session,
    scan_ip_range,
    scan_ports,
    split_subnets,
    test_port,
)


def bad_request(error: Exception | str) -> Response:
    return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)


def user_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


def require_login(request):
    if not request.user.is_authenticated:
        return Response({"error": "请先登录"}, status=status.HTTP_401_UNAUTHORIZED)
    return None


def require_staff(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    if not request.user.is_staff:
        return Response({"error": "没有用户管理权限"}, status=status.HTTP_403_FORBIDDEN)
    return None


@api_view(["GET"])
def health(_request):
    return Response({"status": "ok"})


@api_view(["POST"])
def auth_login(request):
    username = str(request.data.get("account", request.data.get("username", ""))).strip()
    password = str(request.data.get("password", ""))
    remember = bool(request.data.get("remember", False))

    if not username or not password:
        return bad_request("请输入账号和密码")

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "账号或密码错误"}, status=status.HTTP_400_BAD_REQUEST)
    if not user.is_active:
        return Response({"error": "账号已被停用"}, status=status.HTTP_403_FORBIDDEN)

    login(request, user)
    request.session.set_expiry(60 * 60 * 24 * 14 if remember else 0)
    return Response({"user": user_payload(user)})


@api_view(["POST"])
def auth_logout(request):
    logout(request)
    return Response({"ok": True})


@api_view(["GET"])
def auth_me(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    return Response({"user": user_payload(request.user)})


@api_view(["GET", "POST"])
def users(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    User = get_user_model()
    if request.method == "GET":
        data = [user_payload(user) for user in User.objects.order_by("id")]
        return Response(data)

    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", "")).strip()
    if not username:
        return bad_request("请输入用户名")
    if not password:
        return bad_request("请输入初始密码")
    if User.objects.filter(username=username).exists():
        return bad_request("用户名已存在")

    user = User.objects.create_user(
        username=username,
        password=password,
        email=str(request.data.get("email", "")).strip(),
        first_name=str(request.data.get("first_name", "")).strip(),
        is_staff=bool(request.data.get("is_staff", False)),
        is_active=bool(request.data.get("is_active", True)),
    )
    return Response(user_payload(user), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def user_detail(request, user_id: int):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        if user.id == request.user.id:
            return bad_request("不能删除当前登录用户")
        user.delete()
        return Response({"deleted": True})

    username = str(request.data.get("username", user.username)).strip()
    if not username:
        return bad_request("请输入用户名")
    if User.objects.exclude(id=user.id).filter(username=username).exists():
        return bad_request("用户名已存在")

    user.username = username
    user.email = str(request.data.get("email", user.email)).strip()
    user.first_name = str(request.data.get("first_name", user.first_name)).strip()
    user.is_active = bool(request.data.get("is_active", user.is_active))
    user.is_staff = bool(request.data.get("is_staff", user.is_staff))
    password = str(request.data.get("password", "")).strip()
    if password:
        user.set_password(password)
    user.save()
    return Response(user_payload(user))


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


@api_view(["POST"])
def password_generate(request):
    try:
        password = generate_password(
            int(request.data.get("length", 16)),
            bool(request.data.get("include_uppercase", True)),
            bool(request.data.get("include_lowercase", True)),
            bool(request.data.get("include_numbers", True)),
            bool(request.data.get("include_symbols", False)),
        )
        record = PasswordRecord.objects.create(
            project_name=request.data.get("project_name", "").strip(),
            password=password,
            length=len(password),
            include_uppercase=bool(request.data.get("include_uppercase", True)),
            include_lowercase=bool(request.data.get("include_lowercase", True)),
            include_numbers=bool(request.data.get("include_numbers", True)),
            include_symbols=bool(request.data.get("include_symbols", False)),
        )
        return Response(PasswordRecordSerializer(record).data)
    except Exception as error:
        return bad_request(error)


@api_view(["GET", "POST", "DELETE"])
def password_history(_request):
    if _request.method == "DELETE":
        PasswordRecord.objects.all().delete()
        return Response({"deleted": True})
    if _request.method == "POST":
        records = _request.data.get("records", _request.data)
        if not isinstance(records, list):
            return bad_request("导入数据必须是密码记录数组")

        created = []
        for item in records:
            if not isinstance(item, dict):
                return bad_request("每条密码记录必须是对象")
            password = str(item.get("password", "")).strip()
            if not password:
                return bad_request("密码不能为空")
            record = PasswordRecord.objects.create(
                project_name=str(item.get("project_name", "")).strip(),
                password=password,
                length=int(item.get("length") or len(password)),
                include_uppercase=bool(item.get("include_uppercase", True)),
                include_lowercase=bool(item.get("include_lowercase", True)),
                include_numbers=bool(item.get("include_numbers", True)),
                include_symbols=bool(item.get("include_symbols", False)),
            )
            created.append(record)
        return Response(PasswordRecordSerializer(created, many=True).data, status=status.HTTP_201_CREATED)
    return Response(PasswordRecordSerializer(PasswordRecord.objects.all()[:16], many=True).data)


@api_view(["DELETE"])
def password_history_item(_request, record_id: int):
    PasswordRecord.objects.filter(id=record_id).delete()
    return Response({"deleted": True})


@api_view(["GET", "POST", "DELETE"])
def authenticators(request):
    if request.method == "GET":
        entries = AuthenticatorEntry.objects.all()
        data = AuthenticatorEntrySerializer(entries, many=True).data
        for item, entry in zip(data, entries, strict=False):
            item["totp"] = generate_totp(entry)
        return Response(data)

    if request.method == "DELETE":
        AuthenticatorEntry.objects.all().delete()
        return Response({"deleted": True})

    try:
        entry = AuthenticatorEntry.objects.create(
            issuer=request.data.get("issuer", "").strip(),
            account_name=request.data.get("account_name", "").strip(),
            secret=normalize_totp_secret(request.data.get("secret", "")),
            digits=max(6, min(8, int(request.data.get("digits", 6)))),
            period=max(15, min(60, int(request.data.get("period", 30)))),
            algorithm=normalize_totp_algorithm(request.data.get("algorithm", "SHA1")),
        )
        return Response(AuthenticatorEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
    except IntegrityError:
        return bad_request("该双因子认证条目已经存在")
    except Exception as error:
        return bad_request(error)


@api_view(["PUT", "DELETE"])
def authenticator_detail(request, entry_id: int):
    try:
        entry = AuthenticatorEntry.objects.get(id=entry_id)
    except AuthenticatorEntry.DoesNotExist:
        return Response({"error": "条目不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        entry.delete()
        return Response({"deleted": True})

    try:
        entry.issuer = request.data.get("issuer", entry.issuer).strip()
        entry.account_name = request.data.get("account_name", entry.account_name).strip()
        entry.secret = normalize_totp_secret(request.data.get("secret", entry.secret))
        entry.digits = max(6, min(8, int(request.data.get("digits", entry.digits))))
        entry.period = max(15, min(60, int(request.data.get("period", entry.period))))
        entry.algorithm = normalize_totp_algorithm(request.data.get("algorithm", entry.algorithm))
        entry.save()
        return Response(AuthenticatorEntrySerializer(entry).data)
    except IntegrityError:
        return bad_request("该双因子认证条目已经存在")
    except Exception as error:
        return bad_request(error)


@api_view(["GET"])
def authenticator_code(_request, entry_id: int):
    try:
        entry = AuthenticatorEntry.objects.get(id=entry_id)
        return Response(generate_totp(entry))
    except AuthenticatorEntry.DoesNotExist:
        return Response({"error": "条目不存在"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as error:
        return bad_request(error)


@api_view(["GET"])
def authenticator_qrcode(_request, entry_id: int):
    try:
        entry = AuthenticatorEntry.objects.get(id=entry_id)
        uri = build_totp_uri(entry)
        return Response({"uri": uri, "data_url": generate_qr_data_url(uri)})
    except AuthenticatorEntry.DoesNotExist:
        return Response({"error": "条目不存在"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as error:
        return bad_request(error)
