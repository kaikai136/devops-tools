import type { HostGroup, ManagedHost } from '../types';

export type FlatHostGroup = HostGroup & { level: number };
export type HostSortKey = 'name' | 'ip' | 'createdAt' | 'updatedAt' | 'creator' | 'platformType' | 'systemArch' | 'systemType';
export type SortDirection = 'asc' | 'desc';

export function compareHosts(left: ManagedHost, right: ManagedHost, key: HostSortKey, direction: SortDirection) {
  const multiplier = direction === 'asc' ? 1 : -1;
  let result = 0;
  if (key === 'ip') {
    result = ipToNumber(left.privateIp) - ipToNumber(right.privateIp);
  } else if (key === 'createdAt' || key === 'updatedAt') {
    result = dateToNumber(left[key]) - dateToNumber(right[key]);
  } else if (key === 'creator' || key === 'platformType' || key === 'systemArch' || key === 'systemType') {
    result = String(left[key] || '').localeCompare(String(right[key] || ''), 'zh-CN', { numeric: true, sensitivity: 'base' });
  } else {
    result = left.name.localeCompare(right.name, 'zh-CN', { numeric: true, sensitivity: 'base' });
  }
  return result * multiplier;
}

export function flattenGroups(groups: HostGroup[], level = 0): FlatHostGroup[] {
  return groups.flatMap((group) => [
    { ...group, level },
    ...flattenGroups(group.children ?? [], level + 1),
  ]);
}

export function flattenVisibleGroups(groups: HostGroup[], collapsed: Set<number>, level = 0): FlatHostGroup[] {
  return groups.flatMap((group) => [
    { ...group, level },
    ...(collapsed.has(group.key) ? [] : flattenVisibleGroups(group.children ?? [], collapsed, level + 1)),
  ]);
}

export function findGroup(groups: HostGroup[], key: number): HostGroup | undefined {
  for (const group of groups) {
    if (group.key === key) return group;
    const child = findGroup(group.children ?? [], key);
    if (child) return child;
  }
  return undefined;
}

function ipToNumber(ip: string) {
  const parts = ip.split('.').map((part) => Number(part));
  if (parts.length !== 4 || parts.some((part) => Number.isNaN(part))) return Number.MAX_SAFE_INTEGER;
  return parts.reduce((value, part) => value * 256 + part, 0);
}

function dateToNumber(value: string | null | undefined) {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}
