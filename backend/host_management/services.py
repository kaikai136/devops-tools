from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Max, Min

from .models import HostGroup, ManagedHost


def build_group_tree() -> list[HostGroup]:
    groups = list(HostGroup.objects.all())
    children_by_parent: dict[int | None, list[HostGroup]] = defaultdict(list)
    for group in groups:
        children_by_parent[group.parent_id].append(group)
        group._prefetched_children = []

    for group in groups:
        group._prefetched_children = children_by_parent[group.id]

    return children_by_parent[None]


def descendant_ids(group: HostGroup) -> set[int]:
    ids = {group.id}
    for child in getattr(group, "_prefetched_children", []):
        ids.update(descendant_ids(child))
    return ids


def build_group_counts(tree: list[HostGroup]) -> dict[int, int]:
    direct_counts: dict[int, int] = defaultdict(int)
    for item in ManagedHost.objects.values("group_id"):
        direct_counts[item["group_id"]] += 1

    counts: dict[int, int] = {}

    def visit(group: HostGroup) -> int:
        total = direct_counts[group.id]
        for child in getattr(group, "_prefetched_children", []):
            total += visit(child)
        counts[group.id] = total
        return total

    for group in tree:
        visit(group)
    return counts


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


def resolve_creator(value):
    username = str(value or "").strip()
    if not username or username == "system":
        return None
    return get_user_model().objects.filter(username=username).first()


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


def sync_verify_status(host: ManagedHost) -> ManagedHost:
    expected_status = "verified" if host.verified else "unverified"
    if host.verify_status != expected_status:
        host.verify_status = expected_status
        host.save(update_fields=["verify_status"])
    return host
