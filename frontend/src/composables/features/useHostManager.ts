import { computed, ref } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import type { HostCredential, HostGroup, ManagedHost } from '../../types';

type ConfirmFn = (title: string, message: string, actionText: string, action: () => Promise<void>) => void;
type HostStatusFilter = 'all' | 'verified' | 'unverified';
type HostOs = ManagedHost['os'];
type FlatHostGroup = HostGroup & { level: number };
type HostGroupDropPosition = 'before' | 'inside' | 'after';
type HostSortKey = 'name' | 'ip';
type SortDirection = 'asc' | 'desc';

type HostGroupRow =
  | { kind: 'group'; group: FlatHostGroup }
  | { kind: 'editor'; editor: HostGroupInlineEdit };

interface HostGroupInlineEdit {
  mode: 'create-root' | 'create-child' | 'rename';
  groupId: number | null;
  parent: number | null;
  after: number | null;
  level: number;
  name: string;
}

interface ManagedHostForm {
  name: string;
  group: number | null;
  credential: number | null;
  publicIp: string;
  privateIp: string;
  port: number;
  loginUser: string;
  loginPassword: string;
  privateKeyName: string;
  privateKey: string;
  remark: string;
  cpu: number;
  memory: number;
  os: HostOs;
  verified: boolean;
}

interface HostMoveForm {
  hostId: number | null;
  targetGroup: number | null;
}

export function useHostManager({
  showToast,
  requestConfirm,
}: {
  showToast: (title: string, message: string) => void;
  requestConfirm: ConfirmFn;
}) {
  const hostSearch = ref('');
  const selectedHostGroup = ref<number | null>(null);
  const hostStatusFilter = ref<HostStatusFilter>('all');
  const hostSortKey = ref<HostSortKey>('name');
  const hostSortDirection = ref<SortDirection>('asc');
  const hostGroups = ref<HostGroup[]>([]);
  const managedHosts = ref<ManagedHost[]>([]);
  const hostCredentials = ref<HostCredential[]>([]);
  const collapsedHostGroups = ref<Set<number>>(new Set());
  const isLoadingHosts = ref(false);
  const hostGroupInlineEdit = ref<HostGroupInlineEdit | null>(null);
  const rootHostGroupDialogOpen = ref(false);
  const rootHostGroupName = ref('');
  const rootHostGroupSortAfter = ref<number | null>(null);
  const isSavingHostGroup = ref(false);
  const hostGroupMenu = ref<{ group: FlatHostGroup; x: number; y: number } | null>(null);
  const hostDialog = ref<{ mode: 'create' | 'edit'; hostId: number | null } | null>(null);
  const hostForm = ref<ManagedHostForm>(emptyHostForm());
  const hostMoveDialogOpen = ref(false);
  const hostMoveForm = ref<HostMoveForm>({ hostId: null, targetGroup: null });
  const hostMoveSourceGroup = ref<number | null>(null);
  const draggedHostGroupId = ref<number | null>(null);
  const hostGroupDropTarget = ref<{ key: number; position: HostGroupDropPosition } | null>(null);

  const flatHostGroups = computed(() => flattenGroups(hostGroups.value));
  const visibleHostGroups = computed(() => flattenVisibleGroups(hostGroups.value, collapsedHostGroups.value));

  const hostGroupRows = computed<HostGroupRow[]>(() => {
    const rows: HostGroupRow[] = [];
    const edit = hostGroupInlineEdit.value;
    let inserted = false;

    for (const group of visibleHostGroups.value) {
      rows.push({ kind: 'group', group });
      if (edit && edit.mode !== 'rename' && edit.after === group.key) {
        rows.push({ kind: 'editor', editor: edit });
        inserted = true;
      }
    }

    if (edit && edit.mode !== 'rename' && !inserted) {
      rows.push({ kind: 'editor', editor: edit });
    }

    return rows;
  });

  const visibleManagedHosts = computed(() => {
    const query = hostSearch.value.trim().toLowerCase();
    const selectedKeys = selectedHostGroup.value ? groupIdsFor(selectedHostGroup.value) : new Set<number>();
    const filtered = managedHosts.value.filter((host) => {
      const groupMatched = selectedKeys.size ? selectedKeys.has(host.group) : true;
      const statusMatched =
        hostStatusFilter.value === 'all' ||
        (hostStatusFilter.value === 'verified' && host.verified) ||
        (hostStatusFilter.value === 'unverified' && !host.verified);
      const searchMatched = !query || [host.name, host.publicIp, host.privateIp].filter(Boolean).some((value) => String(value).toLowerCase().includes(query));
      return groupMatched && statusMatched && searchMatched;
    });

    return [...filtered].sort((left, right) => compareHosts(left, right, hostSortKey.value, hostSortDirection.value));
  });

  const groupMoveHosts = computed(() => {
    if (!hostMoveSourceGroup.value) return [];
    const ids = groupIdsFor(hostMoveSourceGroup.value);
    return managedHosts.value.filter((host) => ids.has(host.group));
  });

  const managedHostStats = computed(() => ({
    total: managedHosts.value.length,
    verified: managedHosts.value.filter((host) => host.verified).length,
    unverified: managedHosts.value.filter((host) => !host.verified).length,
  }));

  const hostPrivateIpExists = computed(() => {
    const privateIp = hostForm.value.privateIp.trim();
    if (!privateIp) return false;
    const editingId = hostDialog.value?.hostId;
    return managedHosts.value.some((host) => host.privateIp === privateIp && host.id !== editingId);
  });

  async function loadHostManagement() {
    isLoadingHosts.value = true;
    try {
      const [groups, hosts, credentials] = await Promise.all([
        apiGet<HostGroup[]>('/api/host-management/groups/'),
        apiGet<ManagedHost[]>('/api/host-management/hosts/'),
        apiGet<HostCredential[]>('/api/host-management/accounts/'),
      ]);
      hostGroups.value = groups;
      managedHosts.value = hosts;
      hostCredentials.value = credentials;
      pruneCollapsedHostGroups(groups);
      if (selectedHostGroup.value && !findGroup(groups, selectedHostGroup.value)) selectedHostGroup.value = null;
    } catch (error) {
      showToast('加载失败', (error as Error).message);
    } finally {
      isLoadingHosts.value = false;
    }
  }

  function selectManagedGroup(key: number) {
    selectedHostGroup.value = key;
  }

  function setHostSort(key: HostSortKey) {
    if (hostSortKey.value === key) {
      hostSortDirection.value = hostSortDirection.value === 'asc' ? 'desc' : 'asc';
    } else {
      hostSortKey.value = key;
      hostSortDirection.value = 'asc';
    }
  }

  function hostSortMark(key: HostSortKey) {
    if (hostSortKey.value !== key) return '↕';
    return hostSortDirection.value === 'asc' ? '↑' : '↓';
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
    if (!dragged || groupIdsFor(draggedId).has(group.key)) return;

    const parent = drop.position === 'inside' ? group.key : parentKeyFor(group.key);
    const target = drop.position === 'inside' ? null : group.key;
    const position = drop.position === 'inside' ? 'first' : drop.position;

    try {
      const result = await apiPut<{ groups: HostGroup[] }>(`/api/host-management/groups/${draggedId}/`, {
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

  function openHostGroupMenu(group: FlatHostGroup, event: MouseEvent) {
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
    hostGroupInlineEdit.value = null;
    rootHostGroupName.value = '';
    rootHostGroupSortAfter.value = anchor ? rootGroupKeyFor(anchor) : null;
    rootHostGroupDialogOpen.value = true;
  }

  function rootGroupKeyFor(anchor: FlatHostGroup): number {
    if (anchor.level === 0) return anchor.key;

    const groups = flatHostGroups.value;
    const index = groups.findIndex((group) => group.key === anchor.key);
    for (let cursor = index; cursor >= 0; cursor -= 1) {
      if (groups[cursor]?.level === 0) return groups[cursor].key;
    }
    return anchor.key;
  }

  function openAddHostGroup(parent: number | null = selectedHostGroup.value) {
    closeHostGroupMenu();
    if (parent) {
      const next = new Set(collapsedHostGroups.value);
      next.delete(parent);
      collapsedHostGroups.value = next;
    }
    const parentGroup = parent ? flatHostGroups.value.find((group) => group.key === parent) : undefined;
    hostGroupInlineEdit.value = {
      mode: 'create-child',
      groupId: null,
      parent,
      after: parent,
      level: (parentGroup?.level ?? -1) + 1,
      name: '',
    };
  }

  function openRenameHostGroup(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
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

    isSavingHostGroup.value = true;
    try {
      const result =
        edit.mode === 'rename' && edit.groupId
          ? await apiPut<{ groups: HostGroup[] }>(`/api/host-management/groups/${edit.groupId}/`, { name })
          : await apiPost<{ group: HostGroup; groups: HostGroup[] }>('/api/host-management/groups/', {
              name,
              parent: edit.parent,
              sort_after: edit.mode === 'create-root' ? edit.after : null,
              insert: edit.mode === 'create-child' ? 'first' : '',
            });

      hostGroups.value = result.groups;
      const target = edit.mode === 'rename'
        ? edit.groupId
        : 'group' in result
          ? result.group.key
          : null;
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
      const result = await apiPost<{ group: HostGroup; groups: HostGroup[] }>('/api/host-management/groups/', {
        name,
        parent: null,
        sort_after: rootHostGroupSortAfter.value,
      });
      hostGroups.value = result.groups;
      selectedHostGroup.value = result.group.key;
      rootHostGroupDialogOpen.value = false;
      showToast('操作成功', '根分组已添加。');
    } catch (error) {
      showToast('保存失败', (error as Error).message);
    }
  }

  function cancelHostGroupInlineEdit() {
    hostGroupInlineEdit.value = null;
  }

  async function verifyManagedHost(host: ManagedHost) {
    const updated = await apiPut<ManagedHost>(`/api/host-management/hosts/${host.id}/`, { verified: true });
    replaceHost(updated);
    showToast('验证完成', `${updated.name} 已标记为已验证。`);
  }

  function openWebTerminal(host?: ManagedHost) {
    showToast('Web 终端', host ? `正在打开 ${host.name} 的 Web 终端入口。` : '请选择主机后打开 Web 终端。');
  }

  function addManagedHost(group = selectedHostGroup.value ?? flatHostGroups.value[0]?.key ?? null) {
    closeHostGroupMenu();
    hostForm.value = emptyHostForm(group, managedHosts.value.length + 10);
    hostDialog.value = { mode: 'create', hostId: null };
  }

  function editManagedHost(host: ManagedHost) {
    hostForm.value = {
      name: host.name,
      group: host.group,
      credential: null,
      publicIp: host.publicIp ?? '',
      privateIp: host.privateIp,
      port: host.port ?? 22,
      loginUser: host.loginUser ?? '',
      loginPassword: host.loginPassword ?? '',
      privateKeyName: host.privateKeyName ?? '',
      privateKey: host.privateKey ?? '',
      remark: host.remark ?? '',
      cpu: host.cpu,
      memory: host.memory,
      os: host.os,
      verified: host.verified,
    };
    hostDialog.value = { mode: 'edit', hostId: host.id };
  }

  async function saveManagedHost() {
    if (!hostForm.value.group) {
      showToast('保存失败', '请选择分组。');
      return;
    }
    if (!hostForm.value.name.trim() || !hostForm.value.privateIp.trim()) {
      showToast('保存失败', '请输入主机名称和内网 IP。');
      return;
    }

    if (hostPrivateIpExists.value) {
      showToast('保存失败', 'IP 已存在，请重新输入。');
      return;
    }

    const payload = {
      ...hostForm.value,
      name: hostForm.value.name.trim(),
      publicIp: hostForm.value.publicIp.trim() || null,
      privateIp: hostForm.value.privateIp.trim(),
      loginUser: hostForm.value.loginUser.trim(),
      loginPassword: hostForm.value.loginPassword.trim(),
      privateKeyName: hostForm.value.privateKeyName.trim(),
      privateKey: hostForm.value.privateKey.trim(),
      remark: hostForm.value.remark.trim(),
    };
    delete (payload as Partial<ManagedHostForm>).credential;
    const mode = hostDialog.value?.mode ?? 'create';
    const saved =
      mode === 'edit' && hostDialog.value?.hostId
        ? await apiPut<ManagedHost>(`/api/host-management/hosts/${hostDialog.value.hostId}/`, payload)
        : await apiPost<ManagedHost>('/api/host-management/hosts/', payload);

    replaceHost(saved);
    selectedHostGroup.value = saved.group;
    hostSearch.value = '';
    hostStatusFilter.value = 'all';
    hostDialog.value = null;
    await refreshGroupsOnly();
    showToast('操作成功', mode === 'edit' ? '主机已更新。' : '主机已添加。');
  }

  function applyCredentialToHostForm() {
    const credential = hostCredentials.value.find((item) => item.id === hostForm.value.credential);
    if (!credential) return;
    hostForm.value.port = credential.port || 22;
    hostForm.value.loginUser = credential.username;
    hostForm.value.loginPassword = credential.password;
    hostForm.value.privateKeyName = credential.privateKeyName;
    hostForm.value.privateKey = credential.privateKey;
  }

  async function uploadHostPrivateKey(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    hostForm.value.privateKeyName = file.name;
    hostForm.value.privateKey = await file.text();
    input.value = '';
  }

  function openMoveHostDialog(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
    hostMoveSourceGroup.value = group.key;
    const sourceHosts = managedHosts.value.filter((host) => groupIdsFor(group.key).has(host.group));
    hostMoveForm.value = {
      hostId: sourceHosts[0]?.id ?? null,
      targetGroup: flatHostGroups.value.find((item) => item.key !== group.key)?.key ?? null,
    };
    hostMoveDialogOpen.value = true;
  }

  async function saveMoveManagedHost() {
    const host = managedHosts.value.find((item) => item.id === hostMoveForm.value.hostId);
    if (!host || !hostMoveForm.value.targetGroup) {
      showToast('移动失败', '请选择主机和目标分组。');
      return;
    }
    const updated = await apiPut<ManagedHost>(`/api/host-management/hosts/${host.id}/`, { group: hostMoveForm.value.targetGroup });
    replaceHost(updated);
    selectedHostGroup.value = updated.group;
    hostMoveDialogOpen.value = false;
    await refreshGroupsOnly();
    showToast('操作成功', `${updated.name} 已移动到目标分组。`);
  }

  function deleteManagedHost(host: ManagedHost) {
    requestConfirm('删除主机', `确定删除主机「${host.name}」吗？`, '确定删除', async () => {
      await deleteHostById(host.id);
      showToast('操作成功', '主机已删除。');
    });
  }

  function deleteManagedHostsInGroup(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
    const ids = groupIdsFor(group.key);
    const hosts = managedHosts.value.filter((host) => ids.has(host.group));
    if (!hosts.length) {
      showToast('无需删除', '该分组下没有主机。');
      return;
    }
    requestConfirm('删除主机', `确定删除「${group.label}」下的 ${hosts.length} 台主机吗？`, '确定删除', async () => {
      await Promise.all(hosts.map((host) => apiDelete(`/api/host-management/hosts/${host.id}/`)));
      managedHosts.value = managedHosts.value.filter((host) => !hosts.some((item) => item.id === host.id));
      await refreshGroupsOnly();
      showToast('操作成功', '分组下的主机已删除。');
    });
  }

  function deleteHostGroup(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
    if (group.count > 0) {
      showToast('无法删除分组', '请先删除该分组下所有的机器。');
      return;
    }
    requestConfirm('删除分组', `确定删除分组「${group.label}」吗？`, '确定删除', async () => {
      const result = await apiDelete<{ groups: HostGroup[] }>(`/api/host-management/groups/${group.key}/`);
      hostGroups.value = result.groups;
      selectedHostGroup.value = null;
      showToast('操作成功', '分组已删除。');
    });
  }

  async function deleteHostById(hostId: number) {
    await apiDelete(`/api/host-management/hosts/${hostId}/`);
    managedHosts.value = managedHosts.value.filter((item) => item.id !== hostId);
    await refreshGroupsOnly();
  }

  async function refreshGroupsOnly() {
    hostGroups.value = await apiGet<HostGroup[]>('/api/host-management/groups/');
    pruneCollapsedHostGroups(hostGroups.value);
  }

  function replaceHost(host: ManagedHost) {
    const index = managedHosts.value.findIndex((item) => item.id === host.id);
    if (index >= 0) {
      managedHosts.value.splice(index, 1, host);
    } else {
      managedHosts.value = [host, ...managedHosts.value];
    }
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
    hostSearch,
    selectedHostGroup,
    hostStatusFilter,
    hostSortKey,
    hostSortDirection,
    hostGroups,
    hostCredentials,
    flatHostGroups,
    visibleHostGroups,
    hostGroupRows,
    visibleManagedHosts,
    groupMoveHosts,
    managedHostStats,
    hostPrivateIpExists,
    isLoadingHosts,
    hostGroupInlineEdit,
    rootHostGroupDialogOpen,
    rootHostGroupName,
    rootHostGroupSortAfter,
    hostGroupMenu,
    hostDialog,
    hostForm,
    hostMoveDialogOpen,
    hostMoveForm,
    draggedHostGroupId,
    hostGroupDropTarget,
    loadHostManagement,
    selectManagedGroup,
    setHostSort,
    hostSortMark,
    hostGroupName,
    isHostGroupExpanded,
    toggleHostGroupExpanded,
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
    verifyManagedHost,
    openWebTerminal,
    addManagedHost,
    editManagedHost,
    saveManagedHost,
    applyCredentialToHostForm,
    uploadHostPrivateKey,
    openMoveHostDialog,
    saveMoveManagedHost,
    deleteManagedHost,
    deleteManagedHostsInGroup,
    deleteHostGroup,
  };
}

function emptyHostForm(group: number | null = null, sequence = 10): ManagedHostForm {
  return {
    name: `host-${sequence}`,
    group,
    credential: null,
    publicIp: '',
    privateIp: '',
    port: 22,
    loginUser: '',
    loginPassword: '',
    privateKeyName: '',
    privateKey: '',
    remark: '',
    cpu: 2,
    memory: 4,
    os: 'centos',
    verified: false,
  };
}

function compareHosts(left: ManagedHost, right: ManagedHost, key: HostSortKey, direction: SortDirection) {
  const multiplier = direction === 'asc' ? 1 : -1;
  const result =
    key === 'ip'
      ? ipToNumber(left.privateIp) - ipToNumber(right.privateIp)
      : left.name.localeCompare(right.name, 'zh-CN', { numeric: true, sensitivity: 'base' });
  return result * multiplier;
}

function ipToNumber(ip: string) {
  const parts = ip.split('.').map((part) => Number(part));
  if (parts.length !== 4 || parts.some((part) => Number.isNaN(part))) return Number.MAX_SAFE_INTEGER;
  return parts.reduce((value, part) => value * 256 + part, 0);
}

function flattenGroups(groups: HostGroup[], level = 0): FlatHostGroup[] {
  return groups.flatMap((group) => [
    { ...group, level },
    ...flattenGroups(group.children ?? [], level + 1),
  ]);
}

function flattenVisibleGroups(groups: HostGroup[], collapsed: Set<number>, level = 0): FlatHostGroup[] {
  return groups.flatMap((group) => [
    { ...group, level },
    ...(collapsed.has(group.key) ? [] : flattenVisibleGroups(group.children ?? [], collapsed, level + 1)),
  ]);
}

function findGroup(groups: HostGroup[], key: number): HostGroup | undefined {
  for (const group of groups) {
    if (group.key === key) return group;
    const child = findGroup(group.children ?? [], key);
    if (child) return child;
  }
  return undefined;
}
