from collections import defaultdict

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
