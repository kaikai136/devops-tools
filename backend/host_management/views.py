from django.db import IntegrityError
from django.db.models import Max, Min
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request

from .models import HostCredential, HostGroup, ManagedHost
from .serializers import HostCredentialSerializer, HostGroupSerializer, ManagedHostSerializer
from .services import build_group_counts, build_group_tree


def host_payload(host: ManagedHost) -> dict:
    return ManagedHostSerializer(host).data


def groups_payload() -> list[dict]:
    tree = build_group_tree()
    return HostGroupSerializer(tree, many=True, context={"counts": build_group_counts(tree)}).data


def collect_descendant_ids(group: HostGroup) -> set[int]:
    ids = {group.id}
    for child in HostGroup.objects.filter(parent=group):
        ids.update(collect_descendant_ids(child))
    return ids


def next_group_sort_order(parent: HostGroup | None, insert: str, sort_after: object) -> int:
    siblings = HostGroup.objects.filter(parent=parent)
    if insert == "first":
        first_order = siblings.aggregate(value=Min("sort_order"))["value"]
        return (first_order - 10) if first_order is not None and first_order >= 10 else 10

    if sort_after not in (None, "", "null"):
        try:
            anchor = siblings.get(id=int(sort_after))
            return anchor.sort_order + 1
        except (TypeError, ValueError, HostGroup.DoesNotExist):
            pass

    last_order = siblings.aggregate(value=Max("sort_order"))["value"]
    return (last_order + 10) if last_order is not None else 10


def resolve_group_parent(parent_id) -> HostGroup | None:
    if parent_id in (None, "", "null"):
        return None
    try:
        return HostGroup.objects.get(id=int(parent_id))
    except (TypeError, ValueError, HostGroup.DoesNotExist):
        raise ValueError("父级分组不存在")


def reorder_group(group: HostGroup, parent: HostGroup | None, position: str, target_id) -> None:
    siblings = list(HostGroup.objects.filter(parent=parent).exclude(id=group.id).order_by("sort_order", "id"))
    insert_index = len(siblings)

    if target_id not in (None, "", "null"):
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            target_id = None
        for index, sibling in enumerate(siblings):
            if sibling.id == target_id:
                insert_index = index + (1 if position == "after" else 0)
                break
    elif position == "first":
        insert_index = 0

    siblings.insert(insert_index, group)
    for index, sibling in enumerate(siblings, start=1):
        if sibling.parent_id != (parent.id if parent else None) or sibling.sort_order != index * 10:
            sibling.parent = parent
            sibling.sort_order = index * 10
            sibling.save(update_fields=["parent", "sort_order"])


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
        return Response({"error": "分组不存在"}, status=status.HTTP_404_NOT_FOUND)

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
        return bad_request(next(iter(serializer.errors.values()))[0])

    try:
        host = serializer.save()
    except IntegrityError:
        return bad_request("内网 IP 已存在")
    return Response(host_payload(host), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def managed_host_detail(request, host_id: int):
    try:
        host = ManagedHost.objects.get(id=host_id)
    except ManagedHost.DoesNotExist:
        return Response({"error": "主机不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        host.delete()
        return Response({"deleted": True})

    serializer = ManagedHostSerializer(host, data=request.data, partial=True)
    if not serializer.is_valid():
        return bad_request(next(iter(serializer.errors.values()))[0])

    try:
        host = serializer.save()
    except IntegrityError:
        return bad_request("内网 IP 已存在")
    return Response(host_payload(host))


@api_view(["GET", "POST"])
def host_credentials(request):
    if request.method == "GET":
        credentials = HostCredential.objects.all()
        return Response(HostCredentialSerializer(credentials, many=True).data)

    serializer = HostCredentialSerializer(data=request.data)
    if not serializer.is_valid():
        return bad_request(next(iter(serializer.errors.values()))[0])

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
        return Response({"error": "账号不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        credential.delete()
        return Response({"deleted": True})

    serializer = HostCredentialSerializer(credential, data=request.data, partial=True)
    if not serializer.is_valid():
        return bad_request(next(iter(serializer.errors.values()))[0])

    try:
        credential = serializer.save()
    except IntegrityError:
        return bad_request("账号名称已存在")
    return Response(HostCredentialSerializer(credential).data)
