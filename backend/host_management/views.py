from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request, not_found, serializer_bad_request

from .models import HostCredential, HostGroup, ManagedHost
from .probe import verify_host
from .serializers import HostCredentialSerializer, HostGroupSerializer, ManagedHostSerializer
from .services import build_group_counts, build_group_tree, collect_descendant_ids, next_group_sort_order, reorder_group, resolve_group_parent, sync_verify_status


def host_payload(host: ManagedHost) -> dict:
    return ManagedHostSerializer(host).data


def groups_payload() -> list[dict]:
    tree = build_group_tree()
    return HostGroupSerializer(tree, many=True, context={"counts": build_group_counts(tree)}).data


def group_path(group: HostGroup) -> str:
    names = [group.name]
    parent = group.parent
    while parent:
        names.append(parent.name)
        parent = parent.parent
    return "/".join(reversed(names))


def export_payload() -> dict:
    groups = HostGroup.objects.select_related("parent").order_by("sort_order", "id")
    hosts = ManagedHost.objects.select_related("group", "created_by").order_by("id")
    credentials = HostCredential.objects.order_by("id")
    return {
        "version": 1,
        "groups": [
            {
                "name": group.name,
                "path": group_path(group),
                "parentPath": group_path(group.parent) if group.parent else "",
                "sortOrder": group.sort_order,
            }
            for group in groups
        ],
        "hosts": [
            {
                "name": host.name,
                "groupPath": group_path(host.group),
                "publicIp": str(host.public_ip) if host.public_ip else "",
                "privateIp": str(host.private_ip),
                "port": host.port,
                "loginUser": host.login_user,
                "loginPassword": host.login_password,
                "privateKeyName": host.private_key_name,
                "privateKey": host.private_key,
                "remark": host.remark,
                "machineName": host.machine_name,
                "cpu": host.cpu,
                "memory": host.memory,
                "os": host.os,
                "creator": host.created_by.username if host.created_by_id and host.created_by else "system",
                "createdAt": host.created_at.isoformat() if host.created_at else None,
                "verified": host.verified,
                "verifyStatus": host.verify_status,
            }
            for host in hosts
        ],
        "credentials": [
            {
                "name": credential.name,
                "username": credential.username,
                "password": credential.password,
                "port": credential.port,
                "privateKeyName": credential.private_key_name,
                "privateKey": credential.private_key,
                "remark": credential.remark,
            }
            for credential in credentials
        ],
    }


def ensure_group_by_path(path: str) -> HostGroup:
    names = [name.strip() for name in str(path).split("/") if name.strip()]
    if not names:
        raise ValueError("分组路径不能为空")

    parent = None
    group = None
    for name in names:
        group, _created = HostGroup.objects.get_or_create(
            parent=parent,
            name=name,
            defaults={"sort_order": next_group_sort_order(parent, "", None)},
        )
        parent = group
    return group


@api_view(["GET", "POST"])
def host_groups(request):
    if request.method == "GET":
        return Response(groups_payload())

    name = str(request.data.get("name", "")).strip()
    if not name:
        return bad_request("请输入分组名称")

    try:
        parent = resolve_group_parent(request.data.get("parent"))
    except ValueError as error:
        return bad_request(error)

    if HostGroup.objects.filter(parent=parent, name=name).exists():
        return bad_request("同级分组名称已存在")

    try:
        group = HostGroup.objects.create(
            name=name,
            parent=parent,
            sort_order=next_group_sort_order(parent, str(request.data.get("insert", "")), request.data.get("sort_after")),
        )
    except IntegrityError:
        return bad_request("同级分组名称已存在")

    return Response(
        {"group": HostGroupSerializer(group, context={"counts": {group.id: 0}}).data, "groups": groups_payload()},
        status=status.HTTP_201_CREATED,
    )


@api_view(["PUT", "DELETE"])
def host_group_detail(request, group_id: int):
    try:
        group = HostGroup.objects.get(id=group_id)
    except HostGroup.DoesNotExist:
        return not_found("分组不存在")

    if request.method == "PUT":
        name = str(request.data.get("name", group.name)).strip()
        if not name:
            return bad_request("请输入分组名称")

        parent = group.parent
        moving = "parent" in request.data or "target" in request.data or "position" in request.data
        if moving:
            try:
                parent = resolve_group_parent(request.data.get("parent"))
            except ValueError as error:
                return bad_request(error)
            if parent and parent.id in collect_descendant_ids(group):
                return bad_request("不能移动到自身或子分组下")

        if HostGroup.objects.exclude(id=group.id).filter(parent=parent, name=name).exists():
            return bad_request("同级分组名称已存在")

        group.name = name
        if moving:
            group.parent = parent
            group.save(update_fields=["name", "parent"])
            reorder_group(
                group,
                parent,
                str(request.data.get("position", "after")),
                request.data.get("target"),
            )
        else:
            group.save(update_fields=["name"])

        return Response({"group": HostGroupSerializer(group, context={"counts": {group.id: group.hosts.count()}}).data, "groups": groups_payload()})

    if ManagedHost.objects.filter(group_id__in=collect_descendant_ids(group)).exists():
        return bad_request("请先删除该分组下所有的机器。")
    group.delete()
    return Response({"deleted": True, "groups": groups_payload()})


@api_view(["GET", "POST"])
def managed_hosts(request):
    if request.method == "GET":
        hosts = ManagedHost.objects.select_related("group", "created_by").all()
        return Response(ManagedHostSerializer(hosts, many=True).data)

    serializer = ManagedHostSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)

    try:
        creator = request.user if request.user.is_authenticated else None
        host = serializer.save(created_by=creator)
    except IntegrityError:
        return bad_request("内网 IP 已存在")
    sync_verify_status(host)
    return Response(host_payload(host), status=status.HTTP_201_CREATED)


@api_view(["GET"])
def host_management_export(_request):
    return Response(export_payload())


@api_view(["POST"])
def host_management_import(request):
    payload = request.data if isinstance(request.data, dict) else {}
    groups = payload.get("groups", [])
    hosts = payload.get("hosts", [])
    credentials = payload.get("credentials", [])

    if not isinstance(groups, list) or not isinstance(hosts, list) or not isinstance(credentials, list):
        return bad_request("导入文件格式不正确")

    imported = {"groups": 0, "hosts": 0, "credentials": 0}
    try:
        with transaction.atomic():
            for item in sorted(groups, key=lambda value: len(str(value.get("path", value.get("name", ""))).split("/"))):
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path") or item.get("name") or "").strip()
                if not path:
                    continue
                group = ensure_group_by_path(path)
                sort_order = item.get("sortOrder")
                if isinstance(sort_order, int) and group.sort_order != sort_order:
                    group.sort_order = sort_order
                    group.save(update_fields=["sort_order"])
                imported["groups"] += 1

            for item in credentials:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                defaults = {}
                if "username" in item:
                    username = str(item.get("username", "")).strip()
                    if username:
                        defaults["username"] = username
                if "password" in item:
                    defaults["password"] = str(item.get("password", ""))
                if "port" in item:
                    defaults["port"] = int(item.get("port") or 22)
                if "privateKeyName" in item:
                    defaults["private_key_name"] = str(item.get("privateKeyName", ""))
                if "privateKey" in item:
                    defaults["private_key"] = str(item.get("privateKey", ""))
                if "remark" in item:
                    defaults["remark"] = str(item.get("remark", ""))
                if not defaults:
                    continue
                if "username" not in defaults and not HostCredential.objects.filter(name=name).exists():
                    continue
                HostCredential.objects.update_or_create(
                    name=name,
                    defaults=defaults,
                )
                imported["credentials"] += 1

            for item in hosts:
                if not isinstance(item, dict):
                    continue
                private_ip = str(item.get("privateIp", "")).strip()
                name = str(item.get("name", "")).strip()
                group_path_value = str(item.get("groupPath") or item.get("group") or "默认分组").strip()
                if not private_ip or not name:
                    continue
                group = ensure_group_by_path(group_path_value)
                defaults = {
                    "name": name,
                    "group": group,
                }
                optional_fields = {
                    "publicIp": ("public_ip", lambda value: str(value or "") or None),
                    "port": ("port", lambda value: int(value or 22)),
                    "loginUser": ("login_user", lambda value: str(value or "")),
                    "loginPassword": ("login_password", lambda value: str(value or "")),
                    "privateKeyName": ("private_key_name", lambda value: str(value or "")),
                    "privateKey": ("private_key", lambda value: str(value or "")),
                    "remark": ("remark", lambda value: str(value or "")),
                    "machineName": ("machine_name", lambda value: str(value or "")),
                    "cpu": ("cpu", lambda value: int(value or 0)),
                    "memory": ("memory", lambda value: int(value or 0)),
                    "os": ("os", lambda value: str(value or "centos")),
                    "verified": ("verified", lambda value: bool(value)),
                    "verifyStatus": (
                        "verify_status",
                        lambda value: str(value or ("verified" if item.get("verified") else "unverified")),
                    ),
                }
                for source, (target, converter) in optional_fields.items():
                    if source in item:
                        defaults[target] = converter(item.get(source))
                ManagedHost.objects.update_or_create(
                    private_ip=private_ip,
                    defaults=defaults,
                )
                imported["hosts"] += 1
    except (TypeError, ValueError, IntegrityError) as error:
        return bad_request(str(error))

    return Response({"imported": imported, "groups": groups_payload(), "hosts": ManagedHostSerializer(ManagedHost.objects.select_related("group", "created_by").all(), many=True).data})


@api_view(["PUT", "DELETE"])
def managed_host_detail(request, host_id: int):
    try:
        host = ManagedHost.objects.select_related("created_by").get(id=host_id)
    except ManagedHost.DoesNotExist:
        return not_found("主机不存在")

    if request.method == "DELETE":
        host.delete()
        return Response({"deleted": True})

    serializer = ManagedHostSerializer(host, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)

    try:
        host = serializer.save()
    except IntegrityError:
        return bad_request("内网 IP 已存在")
    if "verified" in request.data:
        sync_verify_status(host)
    return Response(host_payload(host))


@api_view(["POST"])
def managed_host_verify(_request, host_id: int):
    try:
        host = ManagedHost.objects.select_related("created_by").get(id=host_id)
    except ManagedHost.DoesNotExist:
        return not_found("主机不存在")

    host, error = verify_host(host)
    return Response({"host": host_payload(host), "verified": host.verified, "error": error})


@api_view(["GET", "POST"])
def host_credentials(request):
    if request.method == "GET":
        credentials = HostCredential.objects.all()
        return Response(HostCredentialSerializer(credentials, many=True).data)

    serializer = HostCredentialSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)

    try:
        credential = serializer.save()
    except IntegrityError:
        return bad_request("账号名称已存在")
    return Response(HostCredentialSerializer(credential).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def host_credential_detail(request, credential_id: int):
    try:
        credential = HostCredential.objects.get(id=credential_id)
    except HostCredential.DoesNotExist:
        return not_found("账号不存在")

    if request.method == "DELETE":
        credential.delete()
        return Response({"deleted": True})

    serializer = HostCredentialSerializer(credential, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)

    try:
        credential = serializer.save()
    except IntegrityError:
        return bad_request("账号名称已存在")
    return Response(HostCredentialSerializer(credential).data)
