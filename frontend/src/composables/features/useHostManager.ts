import { computed, ref, watch } from 'vue';

import * as hostApi from '../../features/hosts/api/hosts';
import type {
  EncryptedHostBackup,
  HostCredential,
  HostExportColumnKey,
  HostExportColumnOption,
  HostExportOptions,
  HostExportScope,
  HostGroup,
  HostManagementExport,
  HostTransferFormat,
  ManagedHost,
} from '../../features/hosts/types';
import { buildHostExportPayload, buildXlsxWorkbook, hostExportColumnOptions, parseExcelWorkbook } from '../../features/hosts/utils/export';
import { compareHosts, findGroup, flattenGroups, flattenVisibleGroups, type FlatHostGroup, type HostSortKey, type SortDirection } from '../../features/hosts/utils/groups';
import { readFileText } from '../../utils/files';

export { hostExportColumnOptions } from '../../features/hosts/utils/export';
export type { HostExportColumnKey, HostExportColumnOption, HostExportOptions, HostExportScope, HostTransferFormat } from '../../features/hosts/types';

type ConfirmFn = (title: string, message: string, actionText: string, action: () => Promise<void>) => void;
type HostStatusFilter = 'all' | 'verified' | 'unverified';
type HostOs = ManagedHost['os'] | '';
type HostGroupDropPosition = 'before' | 'inside' | 'after';

const selectableHostOsValues: readonly ManagedHost['os'][] = ['centos', 'windows'];
const SSH_DEFAULT_PORT = 22;
const RDP_DEFAULT_PORT = 3389;
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

type HostFormErrors = Partial<Record<'group' | 'name' | 'privateIp' | 'os' | 'port', string>>;

interface HostMoveForm {
  hostId: number | null;
  targetGroup: number | null;
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
  const hostFormErrors = ref<HostFormErrors>({});
  const hostMoveDialogOpen = ref(false);
  const hostMoveMode = ref<'single' | 'selected'>('single');
  const hostMoveForm = ref<HostMoveForm>({ hostId: null, targetGroup: null });
  const hostMoveSourceGroup = ref<number | null>(null);
  const draggedHostGroupId = ref<number | null>(null);
  const hostGroupDropTarget = ref<{ key: number; position: HostGroupDropPosition } | null>(null);
  const verifyingHostIds = ref<Set<number>>(new Set());
  const selectedManagedHostIds = ref<Set<number>>(new Set());

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

  watch(
    hostForm,
    () => {
      if (Object.keys(hostFormErrors.value).length) validateHostForm();
    },
    { deep: true },
  );
  watch(
    () => hostForm.value.os,
    (nextOs) => {
      if (hostDialog.value?.mode !== 'create') return;
      hostForm.value.port = defaultPortForHostOs(nextOs);
    },
  );

  async function loadHostManagement() {
    isLoadingHosts.value = true;
    try {
      const [groups, hosts, credentials] = await Promise.all([
        hostApi.listHostGroups(),
        hostApi.listManagedHosts(),
        loadHostCredentials(),
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

  async function loadHostCredentials() {
    const credentials = await hostApi.listHostCredentials();
    hostCredentials.value = credentials;
    return credentials;
  }

  function replaceHostCredential(credential: HostCredential) {
    const index = hostCredentials.value.findIndex((item) => item.id === credential.id);
    if (index >= 0) {
      hostCredentials.value.splice(index, 1, credential);
    } else {
      hostCredentials.value.push(credential);
    }
  }

  function removeHostCredential(credentialId: number) {
    hostCredentials.value = hostCredentials.value.filter((item) => item.id !== credentialId);
  }

  async function exportHostManagement(format: HostTransferFormat = 'json', options: HostExportOptions = {}) {
    try {
      const selectedIds = new Set(options.selectedIds ?? []);
      const sourceHosts =
        options.scope === 'selected'
          ? visibleManagedHosts.value.filter((host) => selectedIds.has(host.id))
          : visibleManagedHosts.value;
      if (options.scope === 'selected' && !sourceHosts.length) {
        showToast('导出失败', '请先在主机列表中选择需要导出的机器。');
        return false;
      }
      const columns = hostExportColumnOptions.filter((column) => (options.columns?.length ? options.columns.includes(column.field) : true));
      if (!columns.length) {
        showToast('导出失败', '请至少选择一个需要导出的数据列。');
        return false;
      }
      const payload = buildHostExportPayload(sourceHosts, columns, hostGroupName);
      const date = new Date().toISOString().slice(0, 10);
      if (format === 'excel') {
        downloadFile(buildXlsxWorkbook(payload, columns), `host-management-${date}.xlsx`, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      } else {
        downloadFile(JSON.stringify(payload, null, 2), `host-management-${date}.json`, 'application/json;charset=utf-8');
      }
      showToast('导出成功', `已导出 ${payload.hosts.length} 台主机。`);
      return true;
    } catch (error) {
      showToast('导出失败', (error as Error).message);
      return false;
    }
  }

  async function backupHostManagement() {
    try {
      const payload = await hostApi.exportHostManagementBackup();
      const encryptedPayload = await encryptHostBackup(payload);
      const date = new Date().toISOString().slice(0, 10);
      downloadFile(JSON.stringify(encryptedPayload, null, 2), `host-management-backup-${date}.enc.json`, 'application/json;charset=utf-8');
      showToast('备份成功', `已备份 ${payload.hosts.length} 台主机、${payload.groups.length} 个分组、${payload.credentials.length} 个账号。`);
      return true;
    } catch (error) {
      showToast('备份失败', (error as Error).message);
      return false;
    }
  }

  async function importHostManagement(event: Event, format: HostTransferFormat = 'json') {
    try {
      const text = await readFileText(event);
      if (!text) return;
      const parsed = format === 'excel' ? parseExcelWorkbook(text) : JSON.parse(text);
      const payload = isEncryptedHostBackup(parsed) ? await decryptHostBackup(parsed) : parsed;
      const result = await hostApi.importHostManagementBackup(payload);
      await loadHostManagement();
      showToast(
        '恢复成功',
        `已处理 ${result.imported.hosts} 台主机、${result.imported.groups} 个分组、${result.imported.credentials} 个账号。`,
      );
    } catch (error) {
      showToast('恢复失败', (error as Error).message);
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

  async function verifyManagedHost(host: ManagedHost) {
    if (verifyingHostIds.value.has(host.id)) return null;

    setHostVerifying(host.id, true);
    try {
      const result = await hostApi.verifyManagedHost(host.id);
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

  async function verifySelectedManagedHosts() {
    const hosts = managedHosts.value.filter((host) => selectedManagedHostIds.value.has(host.id));
    if (!hosts.length) {
      showToast('验证失败', '请先选择需要验证的主机。');
      return;
    }
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

  async function addManagedHost(group = selectedHostGroup.value ?? flatHostGroups.value[0]?.key ?? null) {
    closeHostGroupMenu();
    try {
      await loadHostCredentials();
    } catch (error) {
      showToast('账号加载失败', (error as Error).message);
    }
    let targetGroup = group ?? flatHostGroups.value[0]?.key ?? null;
    if (!targetGroup) {
      try {
        targetGroup = await ensureDefaultHostGroup();
      } catch (error) {
        showToast('分组创建失败', (error as Error).message);
        return;
      }
    }
    if (!targetGroup) {
      showToast('分组创建失败', '未返回默认分组。');
      return;
    }
    hostForm.value = emptyHostForm(targetGroup, managedHosts.value.length + 10);
    hostFormErrors.value = {};
    hostDialog.value = { mode: 'create', hostId: null };
  }

  function editManagedHost(host: ManagedHost) {
    hostForm.value = {
      name: host.name,
      group: host.group,
      credential: null,
      publicIp: host.publicIp ?? '',
      privateIp: host.privateIp,
      port: host.port ?? SSH_DEFAULT_PORT,
      loginUser: host.loginUser ?? '',
      loginPassword: host.loginPassword ?? '',
      privateKeyName: host.privateKeyName ?? '',
      privateKey: host.privateKey ?? '',
      remark: host.remark ?? '',
      cpu: host.cpu,
      memory: host.memory,
      os: isSelectableHostOs(host.os) ? host.os : '',
      verified: host.verified,
    };
    hostFormErrors.value = {};
    hostDialog.value = { mode: 'edit', hostId: host.id };
  }

  function validateHostForm() {
    const errors: HostFormErrors = {};
    const privateIp = hostForm.value.privateIp.trim();
    const port = Number(hostForm.value.port);

    if (!hostForm.value.group) {
      errors.group = '请选择主机分组。';
    }
    if (!hostForm.value.name.trim() || !hostForm.value.privateIp.trim()) {
      if (!hostForm.value.name.trim()) errors.name = '请输入节点名称。';
      if (!privateIp) errors.privateIp = '请输入主机 IP。';
    } else if (!isIPv4Address(privateIp)) {
      errors.privateIp = '请输入正确的主机 IP。';
    }
    if (!isSelectableHostOs(hostForm.value.os)) {
      errors.os = '请选择平台类型。';
    }
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      errors.port = '端口范围为 1-65535。';
    }

    hostFormErrors.value = errors;
    return !Object.keys(errors).length;
  }

  async function saveManagedHost() {
    if (!validateHostForm()) {
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
        ? await hostApi.updateManagedHost(hostDialog.value.hostId, payload)
        : await hostApi.createManagedHost(payload);

    replaceHost(saved);
    selectedHostGroup.value = saved.group;
    hostSearch.value = '';
    hostStatusFilter.value = 'all';
    hostFormErrors.value = {};
    hostDialog.value = null;
    await refreshGroupsOnly();
    showToast('操作成功', mode === 'edit' ? '主机已更新。' : '主机已添加。');
  }

  function applyCredentialToHostForm() {
    const credential = hostCredentials.value.find((item) => item.id === hostForm.value.credential);
    if (!credential) return;
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
    hostMoveMode.value = 'single';
    hostMoveSourceGroup.value = group.key;
    const sourceHosts = group.key === null ? managedHosts.value : managedHosts.value.filter((host) => groupIdsFor(group.key).has(host.group));
    hostMoveForm.value = {
      hostId: sourceHosts[0]?.id ?? null,
      targetGroup: flatHostGroups.value.find((item) => item.key !== group.key)?.key ?? null,
    };
    hostMoveDialogOpen.value = true;
  }

  function openMoveSelectedHostsDialog() {
    const selectedHosts = managedHosts.value.filter((host) => selectedManagedHostIds.value.has(host.id));
    if (!selectedHosts.length) {
      showToast('更新失败', '请先选择需要更新的主机。');
      return;
    }
    hostMoveMode.value = 'selected';
    hostMoveSourceGroup.value = null;
    const currentGroup = selectedHosts[0]?.group ?? null;
    hostMoveForm.value = {
      hostId: null,
      targetGroup: flatHostGroups.value.find((item) => item.key !== currentGroup)?.key ?? currentGroup,
    };
    hostMoveDialogOpen.value = true;
  }

  async function saveMoveManagedHost() {
    if (hostMoveMode.value === 'selected') {
      const targetGroup = hostMoveForm.value.targetGroup;
      const hosts = managedHosts.value.filter((item) => selectedManagedHostIds.value.has(item.id));
      if (!targetGroup || !hosts.length) {
        showToast('更新失败', '请选择主机和目标分组。');
        return;
      }
      const updatedHosts = await Promise.all(hosts.map((host) => hostApi.updateManagedHost(host.id, { group: targetGroup })));
      updatedHosts.forEach(replaceHost);
      selectedHostGroup.value = targetGroup;
      hostMoveDialogOpen.value = false;
      selectedManagedHostIds.value = new Set();
      await refreshGroupsOnly();
      showToast('操作成功', `已更新 ${updatedHosts.length} 台主机的分组。`);
      return;
    }

    const host = managedHosts.value.find((item) => item.id === hostMoveForm.value.hostId);
    if (!host || !hostMoveForm.value.targetGroup) {
      showToast('移动失败', '请选择主机和目标分组。');
      return;
    }
    const updated = await hostApi.updateManagedHost(host.id, { group: hostMoveForm.value.targetGroup });
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

  function deleteSelectedManagedHosts() {
    const hosts = managedHosts.value.filter((host) => selectedManagedHostIds.value.has(host.id));
    if (!hosts.length) {
      showToast('删除失败', '请先选择需要删除的主机。');
      return;
    }
    requestConfirm('删除所选主机', `确定删除所选 ${hosts.length} 台主机吗？`, '确定删除', async () => {
      await Promise.all(hosts.map((host) => hostApi.deleteManagedHost(host.id)));
      const deletedIds = new Set(hosts.map((host) => host.id));
      managedHosts.value = managedHosts.value.filter((host) => !deletedIds.has(host.id));
      selectedManagedHostIds.value = new Set();
      await refreshGroupsOnly();
      showToast('操作成功', `已删除 ${hosts.length} 台主机。`);
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
      await Promise.all(hosts.map((host) => hostApi.deleteManagedHost(host.id)));
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
      const result = await hostApi.deleteHostGroup(group.key);
      hostGroups.value = result.groups;
      selectedHostGroup.value = null;
      showToast('操作成功', '分组已删除。');
    });
  }

  async function deleteHostById(hostId: number) {
    await hostApi.deleteManagedHost(hostId);
    managedHosts.value = managedHosts.value.filter((item) => item.id !== hostId);
    await refreshGroupsOnly();
  }

  async function refreshGroupsOnly() {
    hostGroups.value = await hostApi.listHostGroups();
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
    managedHosts,
    hostGroupRoot,
    flatHostGroups,
    visibleHostGroups,
    hostGroupRows,
    hostGroupRootExpanded,
    visibleManagedHosts,
    groupMoveHosts,
    managedHostStats,
    isLoadingHosts,
    hostGroupInlineEdit,
    rootHostGroupDialogOpen,
    rootHostGroupName,
    rootHostGroupSortAfter,
    hostGroupMenu,
    hostDialog,
    hostForm,
    hostFormErrors,
    hostMoveDialogOpen,
    hostMoveMode,
    hostMoveForm,
    draggedHostGroupId,
    hostGroupDropTarget,
    verifyingHostIds,
    selectedManagedHostIds,
    loadHostManagement,
    loadHostCredentials,
    replaceHostCredential,
    removeHostCredential,
    backupHostManagement,
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
    verifySelectedManagedHosts,
    openWebTerminal,
    addManagedHost,
    editManagedHost,
    saveManagedHost,
    applyCredentialToHostForm,
    uploadHostPrivateKey,
    openMoveHostDialog,
    openMoveSelectedHostsDialog,
    saveMoveManagedHost,
    deleteManagedHost,
    deleteSelectedManagedHosts,
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

function isIPv4Address(value: string) {
  const parts = value.split('.');
  return (
    parts.length === 4 &&
    parts.every((part) => {
      if (!/^\d{1,3}$/.test(part)) return false;
      const octet = Number(part);
      return octet >= 0 && octet <= 255;
    })
  );
}

function isSelectableHostOs(value: HostOs) {
  return selectableHostOsValues.some((option) => option === value);
}

function defaultPortForHostOs(value: HostOs) {
  return value === 'windows' ? RDP_DEFAULT_PORT : SSH_DEFAULT_PORT;
}

function emptyHostForm(group: number | null = null, sequence = 10): ManagedHostForm {
  return {
    name: `host-${sequence}`,
    group,
    credential: null,
    publicIp: '',
    privateIp: '',
    port: SSH_DEFAULT_PORT,
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

function downloadFile(content: BlobPart, filename: string, type: string) {
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

const hostBackupKeyMaterial = 'django-vue.host-management.backup.v1';

async function encryptHostBackup(payload: HostManagementExport): Promise<EncryptedHostBackup> {
  const cryptoApi = getCryptoApi();
  const salt = cryptoApi.getRandomValues(new Uint8Array(16));
  const iv = cryptoApi.getRandomValues(new Uint8Array(12));
  const iterations = 210000;
  const key = await deriveBackupKey(salt, iterations);
  const plainText = new TextEncoder().encode(JSON.stringify(payload));
  const cipherText = new Uint8Array(await cryptoApi.subtle.encrypt({ name: 'AES-GCM', iv }, key, plainText));
  return {
    version: 2,
    encrypted: true,
    algorithm: 'AES-GCM',
    kdf: 'PBKDF2-SHA-256',
    keyMode: 'app-managed',
    iterations,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    data: bytesToBase64(cipherText),
    createdAt: new Date().toISOString(),
  };
}

async function decryptHostBackup(backup: EncryptedHostBackup): Promise<HostManagementExport> {
  const cryptoApi = getCryptoApi();
  const salt = base64ToBytes(backup.salt);
  const iv = base64ToBytes(backup.iv);
  const cipherText = base64ToBytes(backup.data);
  const key = await deriveBackupKey(salt, backup.iterations);
  try {
    const plainText = await cryptoApi.subtle.decrypt({ name: 'AES-GCM', iv }, key, cipherText);
    return JSON.parse(new TextDecoder().decode(plainText));
  } catch {
    throw new Error('备份文件解密失败，请使用当前系统生成的加密备份文件。');
  }
}

async function deriveBackupKey(salt: Uint8Array, iterations: number) {
  const cryptoApi = getCryptoApi();
  const baseKey = await cryptoApi.subtle.importKey('raw', new TextEncoder().encode(hostBackupKeyMaterial), 'PBKDF2', false, ['deriveKey']);
  const saltBuffer = new ArrayBuffer(salt.byteLength);
  new Uint8Array(saltBuffer).set(salt);
  return cryptoApi.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt: saltBuffer, iterations },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

function getCryptoApi() {
  const cryptoApi = globalThis.crypto;
  if (!cryptoApi?.subtle) throw new Error('当前浏览器环境不支持安全加密接口。');
  return cryptoApi;
}

function isEncryptedHostBackup(value: unknown): value is EncryptedHostBackup {
  if (!value || typeof value !== 'object') return false;
  const backup = value as Partial<EncryptedHostBackup>;
  return backup.encrypted === true && backup.algorithm === 'AES-GCM' && backup.kdf === 'PBKDF2-SHA-256' && typeof backup.data === 'string';
}

function bytesToBase64(bytes: Uint8Array) {
  let binary = '';
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

function base64ToBytes(value: string) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
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
