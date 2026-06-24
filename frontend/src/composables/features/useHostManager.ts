import { computed, ref } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import type { HostCredential, HostGroup, ManagedHost } from '../../types';
import { readFileText } from '../../utils/files';
import { compareHosts, findGroup, flattenGroups, flattenVisibleGroups, type FlatHostGroup, type HostSortKey, type SortDirection } from './hostGroups';

type ConfirmFn = (title: string, message: string, actionText: string, action: () => Promise<void>) => void;
type HostStatusFilter = 'all' | 'verified' | 'unverified';
type HostOs = ManagedHost['os'];
type HostGroupDropPosition = 'before' | 'inside' | 'after';
export type HostTransferFormat = 'json' | 'excel';
type ExportRow = Record<string, string | number | boolean | null>;
type ExportColumn = {
  field: string;
  label: string;
  width: number;
};

type HostGroupRow =
  | { kind: 'root'; group: HostGroupRoot }
  | { kind: 'group'; group: FlatHostGroup }
  | { kind: 'editor'; editor: HostGroupInlineEdit };

type HostGroupMenuGroup = FlatHostGroup | HostGroupRoot;

interface HostGroupRoot {
  key: null;
  label: string;
  count: number;
  level: 0;
  children: FlatHostGroup[];
  isRoot: true;
}

interface HostGroupInlineEdit {
  mode: 'create-root' | 'create-child' | 'rename' | 'rename-root';
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

interface HostVerifyResponse {
  host: ManagedHost;
  verified: boolean;
  error: string | null;
}

interface HostManagementExport {
  version: number;
  groups: ExportRow[];
  hosts: ExportRow[];
  credentials: ExportRow[];
}

interface HostManagementImportResponse {
  imported: {
    groups: number;
    hosts: number;
    credentials: number;
  };
}

export function useHostManager({
  showToast,
  requestConfirm,
  currentUsername = () => null,
}: {
  showToast: (title: string, message: string) => void;
  requestConfirm: ConfirmFn;
  currentUsername?: () => string | null | undefined;
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
  const hostGroupRootLabel = ref(readHostGroupRootLabel());
  const hostGroupRootExpanded = ref(true);
  const isLoadingHosts = ref(false);
  const hostGroupInlineEdit = ref<HostGroupInlineEdit | null>(null);
  const rootHostGroupDialogOpen = ref(false);
  const rootHostGroupName = ref('');
  const rootHostGroupSortAfter = ref<number | null>(null);
  const isSavingHostGroup = ref(false);
  const hostGroupMenu = ref<{ group: HostGroupMenuGroup; x: number; y: number } | null>(null);
  const hostDialog = ref<{ mode: 'create' | 'edit'; hostId: number | null } | null>(null);
  const hostForm = ref<ManagedHostForm>(emptyHostForm());
  const hostMoveDialogOpen = ref(false);
  const hostMoveForm = ref<HostMoveForm>({ hostId: null, targetGroup: null });
  const hostMoveSourceGroup = ref<number | null>(null);
  const draggedHostGroupId = ref<number | null>(null);
  const hostGroupDropTarget = ref<{ key: number; position: HostGroupDropPosition } | null>(null);
  const verifyingHostIds = ref<Set<number>>(new Set());

  const flatHostGroups = computed(() => flattenGroups(hostGroups.value, 1));
  const visibleHostGroups = computed(() => flattenVisibleGroups(hostGroups.value, collapsedHostGroups.value, 1));
  const hostGroupRoot = computed<HostGroupRoot>(() => ({
    key: null,
    label: hostGroupRootLabel.value,
    count: managedHostStats.value.total,
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

  const visibleManagedHosts = computed(() => {
    const query = hostSearch.value.trim().toLowerCase();
    const selectedKeys = selectedHostGroup.value ? groupIdsFor(selectedHostGroup.value) : new Set<number>();
    const filtered = managedHosts.value.filter((host) => {
      const groupMatched = selectedKeys.size ? selectedKeys.has(host.group) : true;
      const statusMatched =
        hostStatusFilter.value === 'all' ||
        (hostStatusFilter.value === 'verified' && host.verified) ||
        (hostStatusFilter.value === 'unverified' && !host.verified);
      const searchMatched =
        !query ||
        [host.name, host.machineName, host.systemArch, host.systemType, host.publicIp, host.privateIp, host.creator, host.platformType]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      return groupMatched && statusMatched && searchMatched;
    });

    return [...filtered].sort((left, right) => compareHosts(left, right, hostSortKey.value, hostSortDirection.value));
  });

  const groupMoveHosts = computed(() => {
    if (hostMoveSourceGroup.value === null) return managedHosts.value;
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

  async function exportHostManagement(format: HostTransferFormat = 'json') {
    try {
      const payload = await apiGet<HostManagementExport>('/api/host-management/export/');
      const date = new Date().toISOString().slice(0, 10);
      if (format === 'excel') {
        downloadFile(`\ufeff${buildExcelWorkbook(payload)}`, `host-management-${date}.xls`, 'application/vnd.ms-excel;charset=utf-8');
      } else {
        downloadFile(JSON.stringify(payload, null, 2), `host-management-${date}.json`, 'application/json;charset=utf-8');
      }
      showToast('导出成功', `已导出 ${payload.hosts.length} 台主机、${payload.groups.length} 个分组。`);
    } catch (error) {
      showToast('导出失败', (error as Error).message);
    }
  }

  async function importHostManagement(event: Event, format: HostTransferFormat = 'json') {
    try {
      const text = await readFileText(event);
      if (!text) return;
      const payload = format === 'excel' ? parseExcelWorkbook(text) : JSON.parse(text);
      const result = await apiPost<HostManagementImportResponse>('/api/host-management/import/', payload);
      await loadHostManagement();
      showToast(
        '导入成功',
        `已处理 ${result.imported.hosts} 台主机、${result.imported.groups} 个分组、${result.imported.credentials} 个账号。`,
      );
    } catch (error) {
      showToast('导入失败', (error as Error).message);
    }
  }

  function selectManagedGroup(key: number | null) {
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
          ? await apiPut<{ groups: HostGroup[] }>(`/api/host-management/groups/${edit.groupId}/`, { name })
          : await apiPost<{ group: HostGroup; groups: HostGroup[] }>('/api/host-management/groups/', {
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
      const result = await apiPost<{ group: HostGroup; groups: HostGroup[] }>('/api/host-management/groups/', {
        name,
        parent: null,
        sort_after: rootHostGroupSortAfter.value,
      });
      hostGroups.value = result.groups;
      selectedHostGroup.value = result.group.key;
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

  async function verifyManagedHost(host: ManagedHost) {
    if (verifyingHostIds.value.has(host.id)) return null;

    setHostVerifying(host.id, true);
    try {
      const result = await apiPost<HostVerifyResponse>(`/api/host-management/hosts/${host.id}/verify/`, {});
      replaceHost(result.host);
      if (result.verified) {
        showToast('验证完成', `${result.host.name} 已获取机器配置。`);
      } else {
        showToast('验证失败', `${result.host.name} 连接失败，配置信息已清空。${result.error ? ` ${result.error}` : ''}`);
      }
      return result.host;
    } catch (error) {
      const failedHost = { ...host, verified: false, verifyStatus: 'failed' as const, cpu: 0, memory: 0 };
      replaceHost(failedHost);
      showToast('验证失败', `${host.name} 连接失败，配置信息已清空。${(error as Error).message}`);
      return failedHost;
    } finally {
      setHostVerifying(host.id, false);
    }
  }

  async function verifyVisibleManagedHosts() {
    const hosts = [...visibleManagedHosts.value];
    for (const host of hosts) {
      await verifyManagedHost(host);
    }
  }

  function setHostVerifying(hostId: number, active: boolean) {
    verifyingHostIds.value = setWithValue(verifyingHostIds.value, hostId, active);
  }

  function openWebTerminal(host?: ManagedHost) {
    const params = new URLSearchParams();
    if (host) {
      params.set('host', String(host.id));
    } else if (selectedHostGroup.value) {
      params.set('group', String(selectedHostGroup.value));
    }
    const url = `/terminal.html${params.toString() ? `?${params.toString()}` : ''}`;
    const target = window.open(url, '_blank', 'noopener,noreferrer');
    if (!target) {
      showToast('Web 终端', '浏览器阻止了新窗口，请允许弹窗后重试。');
    }
  }

  function addManagedHost(group = selectedHostGroup.value ?? flatHostGroups.value[0]?.key ?? null) {
    closeHostGroupMenu();
    const targetGroup = group ?? flatHostGroups.value[0]?.key ?? null;
    hostForm.value = emptyHostForm(targetGroup, managedHosts.value.length + 10);
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
    delete (payload as Partial<ManagedHostForm>).verified;
    const mode = hostDialog.value?.mode ?? 'create';
    const creator = currentUsername()?.trim();
    if (mode === 'create' && creator) {
      (payload as typeof payload & { creator: string }).creator = creator;
    }
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
    const sourceHosts = group.key === null ? managedHosts.value : managedHosts.value.filter((host) => groupIdsFor(group.key).has(host.group));
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
    const ids = group.key === null ? null : groupIdsFor(group.key);
    const hosts = ids === null ? managedHosts.value : managedHosts.value.filter((host) => ids.has(host.group));
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
    if (group.key === null) {
      showToast('无法删除根分组', 'DEFAULT 是分组列表的根级。');
      return;
    }
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
    hostGroupRoot,
    flatHostGroups,
    visibleHostGroups,
    hostGroupRows,
    hostGroupRootExpanded,
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
    verifyingHostIds,
    loadHostManagement,
    exportHostManagement,
    importHostManagement,
    selectManagedGroup,
    setHostSort,
    hostSortMark,
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
    verifyManagedHost,
    verifyVisibleManagedHosts,
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

function setWithValue<T>(source: Set<T>, value: T, active: boolean) {
  const next = new Set(source);
  if (active) {
    next.add(value);
  } else {
    next.delete(value);
  }
  return next;
}

function createdGroupKey(result: { groups: HostGroup[] } | { group: HostGroup; groups: HostGroup[] }) {
  return 'group' in result ? result.group.key : null;
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

const exportSheets: Array<{ key: keyof HostManagementExport; title: string; columns: ExportColumn[] }> = [
  {
    key: 'hosts',
    title: '主机清单',
    columns: [{ field: 'name', label: '名称', width: 34 }],
  },
];

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildExcelWorkbook(payload: HostManagementExport) {
  const sheets = exportSheets
    .map((sheet) => {
      const rows = payload[sheet.key] as ExportRow[];
      const colgroup = sheet.columns.map((column) => `<col style="width:${column.width * 8}px">`).join('');
      const header = sheet.columns.map((column) => `<th data-field="${escapeHtml(column.field)}">${escapeHtml(column.label)}</th>`).join('');
      const body = rows
        .map((row) => `<tr>${sheet.columns.map((column) => `<td>${escapeHtml(formatExportCell(column.field, row[column.field]))}</td>`).join('')}</tr>`)
        .join('');
      return `<table id="sheet-${sheet.key}" data-sheet="${sheet.key}"><caption>${sheet.title}</caption><colgroup>${colgroup}</colgroup><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
    })
    .join('<br>');

  return `<!doctype html><html><head><meta charset="utf-8"><style>body{font-family:"Microsoft YaHei",Arial,sans-serif;color:#1f2937}table{border-collapse:collapse;margin-bottom:28px;table-layout:fixed}caption{font-size:18px;font-weight:700;text-align:left;padding:12px 0 10px;color:#0f172a}th,td{border:1px solid #d9e2ef;padding:8px 10px;mso-number-format:"\\@";white-space:pre-wrap;vertical-align:middle}th{background:#eef4ff;color:#173252;font-weight:700;text-align:center}td{background:#fff}tbody tr:nth-child(even) td{background:#f8fbff}</style></head><body>${sheets}</body></html>`;
}

function parseExcelWorkbook(text: string): HostManagementExport {
  const document = new DOMParser().parseFromString(text, 'text/html');
  return {
    version: 1,
    groups: parseExcelSheet(document, 'groups'),
    hosts: parseExcelSheet(document, 'hosts'),
    credentials: parseExcelSheet(document, 'credentials'),
  };
}

function parseExcelSheet(document: Document, key: string): ExportRow[] {
  const table = document.querySelector(`#sheet-${key}, table[data-sheet="${key}"]`);
  if (!table) return [];
  const rows = Array.from(table.querySelectorAll('tr'));
  const headers = Array.from(rows.shift()?.querySelectorAll('th,td') ?? []).map((cell) =>
    resolveExportField(cell.getAttribute('data-field') || normalizeCell(cell.textContent)),
  );
  if (!headers.length) return [];

  return rows
    .map((row) => {
      const cells = Array.from(row.querySelectorAll('td,th'));
      return headers.reduce<ExportRow>((result, field, index) => {
        if (field) result[field] = parseExportCell(field, normalizeCell(cells[index]?.textContent));
        return result;
      }, {});
    })
    .filter((row) => Object.values(row).some((value) => value !== ''));
}

function parseExportCell(field: string, value: string): string | number | boolean {
  if (['sortOrder', 'port', 'cpu', 'memory'].includes(field)) return Number.parseInt(value || '0', 10);
  if (field === 'verified') return ['true', '1', 'yes', '是', '已验证', 'verified'].includes(value.toLowerCase());
  return value;
}

function resolveExportField(value: string) {
  const normalized = normalizeCell(value);
  return excelHeaderAliases[normalized] ?? exportSheets.flatMap((sheet) => sheet.columns).find((column) => column.label === normalized || column.field === normalized)?.field ?? normalized;
}

const excelHeaderAliases: Record<string, string> = {
  名称: 'name',
  节点: 'name',
  机器别名: 'name',
  账号名称: 'name',
  分组名称: 'name',
  分组路径: 'path',
  上级路径: 'parentPath',
  排序: 'sortOrder',
  主机分组: 'groupPath',
  '公网 IP': 'publicIp',
  '内网 IP': 'privateIp',
  端口: 'port',
  机器名称: 'machineName',
  CPU: 'cpu',
  '内存(GB)': 'memory',
  系统: 'os',
  验证状态: 'verified',
  备注: 'remark',
  密钥文件名: 'privateKeyName',
};

function formatExportCell(field: string, value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) return '';
  if (field === 'verified') return value ? '已验证' : '未验证';
  return String(value);
}

function normalizeCell(value: string | null | undefined) {
  return (value ?? '').replace(/\u00a0/g, ' ').trim();
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] ?? char);
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
