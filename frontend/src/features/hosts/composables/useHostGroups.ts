import { computed, ref } from 'vue';

import * as hostApi from '@features/hosts/api/hosts';
import type { HostGroup, ManagedHost } from '@features/hosts/types';
import {
  findGroup,
  flattenGroups,
  flattenVisibleGroups,
  type FlatHostGroup,
} from '@features/hosts/utils/groups';
import type { HostManagerConfirm } from './useHostList';

export type HostGroupDropPosition = 'before' | 'inside' | 'after';

export type HostGroupRow =
  | { kind: 'root'; group: HostGroupRoot }
  | { kind: 'group'; group: FlatHostGroup }
  | { kind: 'editor'; editor: HostGroupInlineEdit };

export type HostGroupMenuGroup = FlatHostGroup | HostGroupRoot;

export interface HostGroupRoot {
  key: null;
  label: string;
  count: number;
  level: 0;
  children: FlatHostGroup[];
  isRoot: true;
}

export interface HostGroupInlineEdit {
  mode: 'create-root' | 'create-child' | 'rename' | 'rename-root';
  groupId: number | null;
  parent: number | null;
  after: number | null;
  level: number;
  name: string;
}

interface UseHostGroupsOptions {
  showToast: (title: string, message: string) => void;
  requestConfirm: HostManagerConfirm;
  getManagedHosts: () => ManagedHost[];
  replaceManagedHosts: (hosts: ManagedHost[]) => void;
  getManagedHostTotal: () => number;
}

export function useHostGroups({
  showToast,
  requestConfirm,
  getManagedHosts,
  replaceManagedHosts,
  getManagedHostTotal,
}: UseHostGroupsOptions) {
  const selectedHostGroup = ref<number | null>(null);
  const hostGroups = ref<HostGroup[]>([]);
  const collapsedHostGroups = ref<Set<number>>(new Set());
  const hostGroupRootLabel = ref(readHostGroupRootLabel());
  const hostGroupRootExpanded = ref(true);
  const hostGroupInlineEdit = ref<HostGroupInlineEdit | null>(null);
  const rootHostGroupDialogOpen = ref(false);
  const rootHostGroupName = ref('');
  const rootHostGroupSortAfter = ref<number | null>(null);
  const isSavingHostGroup = ref(false);
  const hostGroupMenu = ref<{ group: HostGroupMenuGroup; x: number; y: number } | null>(null);
  const draggedHostGroupId = ref<number | null>(null);
  const hostGroupDropTarget = ref<{ key: number; position: HostGroupDropPosition } | null>(null);

  const flatHostGroups = computed(() => flattenGroups(hostGroups.value, 1));
  const visibleHostGroups = computed(() => flattenVisibleGroups(hostGroups.value, collapsedHostGroups.value, 1));
  const hostGroupRoot = computed<HostGroupRoot>(() => ({
    key: null,
    label: hostGroupRootLabel.value,
    count: getManagedHostTotal(),
    level: 0,
    children: flatHostGroups.value,
    isRoot: true,
  }));

  const hostGroupRows = computed<HostGroupRow[]>(() => {
    const rows: HostGroupRow[] = [{ kind: 'root', group: hostGroupRoot.value }];
    const edit = hostGroupInlineEdit.value;
    let inserted = false;

    if (edit?.mode === 'rename-root') {
      rows[0] = { kind: 'editor', editor: edit };
    }

    if (hostGroupRootExpanded.value) {
      if (edit && edit.mode !== 'rename' && edit.mode !== 'rename-root' && edit.parent === null && edit.after === null) {
        rows.push({ kind: 'editor', editor: edit });
        inserted = true;
      }
      for (const group of visibleHostGroups.value) {
        rows.push({ kind: 'group', group });
        if (edit && edit.mode !== 'rename' && edit.after === group.key) {
          rows.push({ kind: 'editor', editor: edit });
          inserted = true;
        }
      }
    }

    if (edit && edit.mode !== 'rename' && edit.mode !== 'rename-root' && !inserted) {
      rows.push({ kind: 'editor', editor: edit });
    }

    return rows;
  });

  function selectManagedGroup(key: number | null) {
    selectedHostGroup.value = key;
  }

  function hostGroupName(groupKey: number) {
    return findGroup(hostGroups.value, groupKey)?.label ?? '未分组';
  }

  function isHostGroupExpanded(group: HostGroup) {
    return !collapsedHostGroups.value.has(group.key);
  }

  function toggleHostGroupExpanded(group: HostGroup) {
    if (!group.children?.length) return;
    const next = new Set(collapsedHostGroups.value);
    if (next.has(group.key)) {
      next.delete(group.key);
    } else {
      next.add(group.key);
    }
    collapsedHostGroups.value = next;
  }

  function toggleHostGroupRootExpanded() {
    hostGroupRootExpanded.value = !hostGroupRootExpanded.value;
  }

  function startHostGroupDrag(group: FlatHostGroup, event: DragEvent) {
    closeHostGroupMenu();
    draggedHostGroupId.value = group.key;
    hostGroupDropTarget.value = null;
    event.dataTransfer?.setData('text/plain', String(group.key));
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }

  function updateHostGroupDropTarget(group: FlatHostGroup, event: DragEvent) {
    if (!draggedHostGroupId.value || draggedHostGroupId.value === group.key) return;
    if (groupIdsFor(draggedHostGroupId.value).has(group.key)) {
      hostGroupDropTarget.value = null;
      return;
    }
    event.preventDefault();
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const offset = event.clientY - rect.top;
    const zone = rect.height / 3;
    const position: HostGroupDropPosition = offset < zone ? 'before' : offset > rect.height - zone ? 'after' : 'inside';
    hostGroupDropTarget.value = { key: group.key, position };
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
  }

  function clearHostGroupDropTarget() {
    hostGroupDropTarget.value = null;
  }

  async function dropHostGroup(group: FlatHostGroup, event: DragEvent) {
    event.preventDefault();
    const draggedId = draggedHostGroupId.value;
    const drop = hostGroupDropTarget.value;
    draggedHostGroupId.value = null;
    hostGroupDropTarget.value = null;
    if (!draggedId || !drop || draggedId === group.key) return;

    const dragged = flatHostGroups.value.find((item) => item.key === draggedId);
    if (!dragged) return;

    const parent = drop.position === 'inside' ? group.key : parentKeyFor(group.key);
    const target = drop.position === 'inside' ? null : group.key;
    const position = drop.position === 'inside' ? 'first' : drop.position;

    try {
      const result = await hostApi.updateHostGroup(draggedId, {
        name: dragged.label,
        parent,
        target,
        position,
      });
      hostGroups.value = result.groups;
      selectedHostGroup.value = draggedId;
      if (drop.position === 'inside') {
        const next = new Set(collapsedHostGroups.value);
        next.delete(group.key);
        collapsedHostGroups.value = next;
      }
      pruneCollapsedHostGroups(result.groups);
    } catch (error) {
      showToast('移动失败', (error as Error).message);
    }
  }

  function finishHostGroupDrag() {
    draggedHostGroupId.value = null;
    hostGroupDropTarget.value = null;
  }

  function openHostGroupMenu(group: HostGroupMenuGroup, event: MouseEvent) {
    event.preventDefault();
    selectedHostGroup.value = group.key;
    hostGroupMenu.value = {
      group,
      x: Math.min(event.clientX, window.innerWidth - 190),
      y: Math.min(event.clientY, window.innerHeight - 260),
    };
  }

  function closeHostGroupMenu() {
    hostGroupMenu.value = null;
  }

  function openAddRootHostGroup(anchor = hostGroupMenu.value?.group) {
    closeHostGroupMenu();
    const selected = selectedHostGroup.value ? flatHostGroups.value.find((group) => group.key === selectedHostGroup.value) : undefined;
    const siblingAnchor = anchor && !isHostGroupRoot(anchor) ? anchor : selected;
    hostGroupRootExpanded.value = true;
    hostGroupInlineEdit.value = {
      mode: 'create-root',
      groupId: null,
      parent: siblingAnchor ? parentKeyFor(siblingAnchor.key) : null,
      after: siblingAnchor?.key ?? null,
      level: siblingAnchor?.level ?? 1,
      name: '',
    };
  }

  function openAddHostGroup(parent: number | null = selectedHostGroup.value) {
    closeHostGroupMenu();
    const anchor = parent ? flatHostGroups.value.find((group) => group.key === parent) : undefined;
    hostGroupRootExpanded.value = true;
    if (parent) {
      const next = new Set(collapsedHostGroups.value);
      next.delete(parent);
      collapsedHostGroups.value = next;
    }
    hostGroupInlineEdit.value = {
      mode: 'create-child',
      groupId: null,
      parent,
      after: anchor?.key ?? null,
      level: (anchor?.level ?? 0) + 1,
      name: '',
    };
  }

  function openRenameHostGroup(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
    if (isHostGroupRoot(group)) {
      hostGroupInlineEdit.value = {
        mode: 'rename-root',
        groupId: null,
        parent: null,
        after: null,
        level: 0,
        name: group.label,
      };
      return;
    }
    hostGroupInlineEdit.value = {
      mode: 'rename',
      groupId: group.key,
      parent: null,
      after: null,
      level: group.level,
      name: group.label,
    };
  }

  async function saveHostGroupInlineEdit() {
    const edit = hostGroupInlineEdit.value;
    if (!edit || isSavingHostGroup.value) return;

    const name = edit.name.trim();
    if (!name) {
      cancelHostGroupInlineEdit();
      return;
    }

    if (edit.mode === 'rename-root') {
      hostGroupRootLabel.value = name;
      writeHostGroupRootLabel(name);
      hostGroupInlineEdit.value = null;
      showToast('操作成功', '根分组已重命名。');
      return;
    }

    isSavingHostGroup.value = true;
    try {
      const result =
        edit.mode === 'rename' && edit.groupId
          ? await hostApi.updateHostGroup(edit.groupId, { name })
          : await hostApi.createHostGroup({
              name,
              parent: edit.parent,
              sort_after: edit.mode === 'create-root' ? edit.after : null,
              insert: edit.mode === 'create-child' ? 'first' : '',
            });

      hostGroups.value = result.groups;
      const target = edit.mode === 'rename' ? edit.groupId : createdGroupKey(result);
      if (target) selectedHostGroup.value = target;
      hostGroupInlineEdit.value = null;
      showToast('操作成功', edit.mode === 'rename' ? '分组已重命名。' : '分组已添加。');
    } catch (error) {
      showToast('保存失败', (error as Error).message);
    } finally {
      isSavingHostGroup.value = false;
    }
  }

  async function saveRootHostGroup() {
    const name = rootHostGroupName.value.trim();
    if (!name) {
      showToast('保存失败', '请输入分组名称。');
      return;
    }

    try {
      const result = await hostApi.createHostGroup({
        name,
        parent: null,
        sort_after: rootHostGroupSortAfter.value,
      });
      hostGroups.value = result.groups;
      if (result.group) selectedHostGroup.value = result.group.key;
      hostGroupRootExpanded.value = true;
      rootHostGroupDialogOpen.value = false;
      showToast('操作成功', '分组已添加。');
    } catch (error) {
      showToast('保存失败', (error as Error).message);
    }
  }

  function cancelHostGroupInlineEdit() {
    hostGroupInlineEdit.value = null;
  }

  async function ensureDefaultHostGroup() {
    const existingGroup = flatHostGroups.value[0]?.key ?? null;
    if (existingGroup) return existingGroup;

    const result = await hostApi.createHostGroup({
      name: 'default',
      parent: null,
    });
    hostGroups.value = result.groups;
    hostGroupRootExpanded.value = true;
    const targetGroup = createdGroupKey(result) ?? flatHostGroups.value[0]?.key ?? null;
    if (targetGroup) selectedHostGroup.value = targetGroup;
    return targetGroup;
  }

  function deleteManagedHostsInGroup(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
    const ids = group.key === null ? null : groupIdsFor(group.key);
    const managedHosts = getManagedHosts();
    const hosts = ids === null ? managedHosts : managedHosts.filter((host) => ids.has(host.group));
    if (!hosts.length) {
      showToast('无需删除', '该分组下没有主机。');
      return;
    }
    requestConfirm('删除主机', `确定删除「${group.label}」下的 ${hosts.length} 台主机吗？`, '确定删除', async () => {
      await Promise.all(hosts.map((host) => hostApi.deleteManagedHost(host.id)));
      replaceManagedHosts(getManagedHosts().filter((host) => !hosts.some((item) => item.id === host.id)));
      await refreshGroupsOnly();
      showToast('操作成功', '分组下的主机已删除。');
    });
  }

  function deleteHostGroup(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
    if (group.key === null) {
      showToast('无法删除根分组', 'DEFAULT 是分组列表的根级。');
      return;
    }
    if (group.count > 0) {
      showToast('无法删除分组', '请先删除该分组下所有的机器。');
      return;
    }
    requestConfirm('删除分组', `确定删除分组「${group.label}」吗？`, '确定删除', async () => {
      const result = await hostApi.deleteHostGroup(group.key);
      hostGroups.value = result.groups;
      selectedHostGroup.value = null;
      showToast('操作成功', '分组已删除。');
    });
  }

  async function refreshGroupsOnly() {
    hostGroups.value = await hostApi.listHostGroups();
    pruneCollapsedHostGroups(hostGroups.value);
  }

  function replaceHostGroups(groups: HostGroup[]) {
    hostGroups.value = groups;
  }

  function groupIdsFor(groupKey: number): Set<number> {
    const selected = findGroup(hostGroups.value, groupKey);
    const ids = new Set<number>();
    const collect = (group?: HostGroup) => {
      if (!group) return;
      ids.add(group.key);
      group.children?.forEach(collect);
    };
    collect(selected);
    return ids;
  }

  function parentKeyFor(groupKey: number): number | null {
    const findParent = (groups: HostGroup[], parent: number | null = null): number | null | undefined => {
      for (const group of groups) {
        if (group.key === groupKey) return parent;
        const found = findParent(group.children ?? [], group.key);
        if (found !== undefined) return found;
      }
      return undefined;
    };
    return findParent(hostGroups.value) ?? null;
  }

  function pruneCollapsedHostGroups(groups: HostGroup[]) {
    const available = new Set(flattenGroups(groups).map((group) => group.key));
    collapsedHostGroups.value = new Set([...collapsedHostGroups.value].filter((key) => available.has(key)));
  }

  return {
    selectedHostGroup,
    hostGroups,
    hostGroupRoot,
    flatHostGroups,
    visibleHostGroups,
    hostGroupRows,
    hostGroupRootExpanded,
    hostGroupInlineEdit,
    rootHostGroupDialogOpen,
    rootHostGroupName,
    rootHostGroupSortAfter,
    hostGroupMenu,
    draggedHostGroupId,
    hostGroupDropTarget,
    selectManagedGroup,
    hostGroupName,
    isHostGroupExpanded,
    toggleHostGroupExpanded,
    toggleHostGroupRootExpanded,
    startHostGroupDrag,
    updateHostGroupDropTarget,
    clearHostGroupDropTarget,
    dropHostGroup,
    finishHostGroupDrag,
    openHostGroupMenu,
    closeHostGroupMenu,
    openAddRootHostGroup,
    openAddHostGroup,
    openRenameHostGroup,
    saveHostGroupInlineEdit,
    saveRootHostGroup,
    cancelHostGroupInlineEdit,
    ensureDefaultHostGroup,
    deleteManagedHostsInGroup,
    deleteHostGroup,
    refreshGroupsOnly,
    replaceHostGroups,
    groupIdsFor,
    pruneCollapsedHostGroups,
  };
}

function createdGroupKey(result: { groups: HostGroup[] } | { group: HostGroup; groups: HostGroup[] }) {
  return 'group' in result ? result.group.key : null;
}

function isHostGroupRoot(group: HostGroupMenuGroup): group is HostGroupRoot {
  return 'isRoot' in group;
}

function readHostGroupRootLabel() {
  if (typeof window === 'undefined') return 'DEFAULT';
  return window.localStorage.getItem('ops-tool.host-manager.root-label') || 'DEFAULT';
}

function writeHostGroupRootLabel(label: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem('ops-tool.host-manager.root-label', label);
}
