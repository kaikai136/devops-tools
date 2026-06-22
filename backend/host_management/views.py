from django.db import IntegrityError
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
        hosts = ManagedHost.objects.select_related("group").all()
        return Response(ManagedHostSerializer(hosts, many=True).data)

    serializer = ManagedHostSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)

    try:
        host = serializer.save()
    except IntegrityError:
        return bad_request("内网 IP 已存在")
    sync_verify_status(host)
    return Response(host_payload(host), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def managed_host_detail(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
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
        host = ManagedHost.objects.get(id=host_id)
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
