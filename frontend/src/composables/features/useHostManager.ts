import { computed, ref, watch } from 'vue';

import * as hostApi from '../../services/hostManagement';
import type { HostManagementExport } from '../../services/hostManagement';
import type { HostCredential, HostGroup, ManagedHost } from '../../types';
import { readFileText } from '../../utils/files';
import { compareHosts, findGroup, flattenGroups, flattenVisibleGroups, type FlatHostGroup, type HostSortKey, type SortDirection } from './hostGroups';

type ConfirmFn = (title: string, message: string, actionText: string, action: () => Promise<void>) => void;
type HostStatusFilter = 'all' | 'verified' | 'unverified';
type HostOs = ManagedHost['os'] | '';
type HostGroupDropPosition = 'before' | 'inside' | 'after';
export type HostTransferFormat = 'json' | 'excel';
export type HostExportScope = 'all' | 'selected';
export type HostExportColumnKey =
  | 'group'
  | 'name'
  | 'ip'
  | 'machine'
  | 'systemArch'
  | 'systemType'
  | 'config'
  | 'platformType'
  | 'user'
  | 'port'
  | 'createdAt'
  | 'updatedAt'
  | 'creator'
  | 'remark'
  | 'status';
type ExportRow = Record<string, string | number | boolean | null>;
type ExportColumn = {
  field: string;
  label: string;
  width: number;
};
export type HostExportColumnOption = ExportColumn & { field: HostExportColumnKey };

const selectableHostOsValues: readonly ManagedHost['os'][] = ['centos', 'windows'];
const SSH_DEFAULT_PORT = 22;
const RDP_DEFAULT_PORT = 3389;

export const hostExportColumnOptions: readonly HostExportColumnOption[] = [
  { field: 'group', label: '主机分组', width: 18 },
  { field: 'name', label: '节点', width: 22 },
  { field: 'ip', label: 'IP地址', width: 24 },
  { field: 'machine', label: '机器名称', width: 24 },
  { field: 'systemArch', label: '系统架构', width: 16 },
  { field: 'systemType', label: '系统类型', width: 16 },
  { field: 'config', label: '配置信息', width: 18 },
  { field: 'platformType', label: '平台类型', width: 16 },
  { field: 'user', label: '用户', width: 16 },
  { field: 'port', label: '端口', width: 10 },
  { field: 'createdAt', label: '创建时间', width: 22 },
  { field: 'updatedAt', label: '更新时间', width: 22 },
  { field: 'creator', label: '创建者', width: 16 },
  { field: 'remark', label: '备注', width: 28 },
  { field: 'status', label: '状态', width: 14 },
] as const;

export interface HostExportOptions {
  scope?: HostExportScope;
  selectedIds?: number[];
  columns?: HostExportColumnKey[];
}

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

interface EncryptedHostBackup {
  version: 2;
  encrypted: true;
  algorithm: 'AES-GCM';
  kdf: 'PBKDF2-SHA-256';
  keyMode?: 'app-managed';
  iterations: number;
  salt: string;
  iv: string;
  data: string;
  createdAt: string;
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
      const payload = buildHostExportPayload(sourceHosts, columns);
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

  function buildHostExportPayload(hosts: ManagedHost[], columns: readonly HostExportColumnOption[]): HostManagementExport {
    return {
      version: 1,
      groups: [],
      credentials: [],
      hosts: hosts.map((host) =>
        columns.reduce<ExportRow>((row, column) => {
          row[column.field] = formatHostExportValue(host, column.field);
          return row;
        }, {}),
      ),
    };
  }

  function formatHostExportValue(host: ManagedHost, field: HostExportColumnKey): string | number | boolean | null {
    if (field === 'group') return hostGroupName(host.group);
    if (field === 'ip') return [host.publicIp, host.privateIp].filter(Boolean).join('\n');
    if (field === 'machine') return host.verified ? host.machineName || '' : '';
    if (field === 'config') return host.verified && host.cpu > 0 && host.memory > 0 ? `${host.cpu}核 ${host.memory}GB` : '';
    if (field === 'platformType') return host.platformType || (host.os === 'windows' ? 'windows' : 'linux');
    if (field === 'user') return host.loginUser || '';
    if (field === 'status') return host.verified ? '已验证' : host.verifyStatus === 'failed' ? '验证失败' : '未验证';
    if (field === 'createdAt') return host.createdAt || '';
    if (field === 'updatedAt') return host.updatedAt || '';
    if (field === 'creator') return host.creator || '';
    if (field === 'remark') return host.remark || '';
    if (field === 'port') return host.port || 22;
    if (field === 'systemArch') return host.systemArch || '';
    if (field === 'systemType') return host.systemType || '';
    return host.name;
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

const exportSheets: Array<{ key: keyof HostManagementExport; title: string; columns: ExportColumn[] }> = [
  {
    key: 'hosts',
    title: '主机清单',
    columns: [{ field: 'name', label: '名称', width: 34 }],
  },
];

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

function buildXlsxWorkbook(payload: HostManagementExport, hostColumns: readonly ExportColumn[] = exportSheets[0].columns) {
  const rows = payload.hosts;
  const worksheet = buildXlsxWorksheet(rows, hostColumns);
  return createZip([
    { name: '[Content_Types].xml', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>`) },
    { name: '_rels/.rels', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`) },
    { name: 'xl/workbook.xml', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="主机清单" sheetId="1" r:id="rId1"/></sheets></workbook>`) },
    { name: 'xl/_rels/workbook.xml.rels', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`) },
    { name: 'xl/styles.xml', content: stringToBytes(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Microsoft YaHei"/></font><font><b/><sz val="11"/><name val="Microsoft YaHei"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="49" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`) },
    { name: 'xl/worksheets/sheet1.xml', content: stringToBytes(worksheet) },
  ]);
}

function buildXlsxWorksheet(rows: ExportRow[], columns: readonly ExportColumn[]) {
  const columnXml = columns.map((column, index) => `<col min="${index + 1}" max="${index + 1}" width="${Math.max(10, column.width)}" customWidth="1"/>`).join('');
  const header = `<row r="1">${columns.map((column, index) => buildXlsxCell(1, index + 1, column.label, 1)).join('')}</row>`;
  const body = rows
    .map((row, rowIndex) => {
      const excelRow = rowIndex + 2;
      return `<row r="${excelRow}">${columns.map((column, columnIndex) => buildXlsxCell(excelRow, columnIndex + 1, formatExportCell(column.field, row[column.field]))).join('')}</row>`;
    })
    .join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols>${columnXml}</cols><sheetData>${header}${body}</sheetData></worksheet>`;
}

function buildXlsxCell(row: number, column: number, value: string, style = 0) {
  const ref = `${columnName(column)}${row}`;
  return `<c r="${ref}" t="inlineStr"${style ? ` s="${style}"` : ''}><is><t>${escapeXml(value)}</t></is></c>`;
}

function columnName(index: number) {
  let name = '';
  let current = index;
  while (current > 0) {
    current -= 1;
    name = String.fromCharCode(65 + (current % 26)) + name;
    current = Math.floor(current / 26);
  }
  return name;
}

function createZip(files: Array<{ name: string; content: Uint8Array }>) {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;

  for (const file of files) {
    const name = stringToBytes(file.name);
    const crc = crc32(file.content);
    const localHeader = concatBytes([
      uint32(0x04034b50),
      uint16(20),
      uint16(0),
      uint16(0),
      uint16(0),
      uint16(0),
      uint32(crc),
      uint32(file.content.length),
      uint32(file.content.length),
      uint16(name.length),
      uint16(0),
      name,
    ]);
    localParts.push(localHeader, file.content);

    centralParts.push(
      concatBytes([
        uint32(0x02014b50),
        uint16(20),
        uint16(20),
        uint16(0),
        uint16(0),
        uint16(0),
        uint16(0),
        uint32(crc),
        uint32(file.content.length),
        uint32(file.content.length),
        uint16(name.length),
        uint16(0),
        uint16(0),
        uint16(0),
        uint16(0),
        uint32(0),
        uint32(offset),
        name,
      ]),
    );

    offset += localHeader.length + file.content.length;
  }

  const centralOffset = offset;
  const centralDirectory = concatBytes(centralParts);
  const endRecord = concatBytes([
    uint32(0x06054b50),
    uint16(0),
    uint16(0),
    uint16(files.length),
    uint16(files.length),
    uint32(centralDirectory.length),
    uint32(centralOffset),
    uint16(0),
  ]);

  return concatBytes([...localParts, centralDirectory, endRecord]);
}

function stringToBytes(value: string) {
  return new TextEncoder().encode(value);
}

function concatBytes(parts: Uint8Array[]) {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

function uint16(value: number) {
  const bytes = new Uint8Array(2);
  const view = new DataView(bytes.buffer);
  view.setUint16(0, value, true);
  return bytes;
}

function uint32(value: number) {
  const bytes = new Uint8Array(4);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, value >>> 0, true);
  return bytes;
}

function crc32(bytes: Uint8Array) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let index = 0; index < 8; index += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function buildExcelWorkbook(payload: HostManagementExport, hostColumns: readonly ExportColumn[] = exportSheets[0].columns) {
  const sheetsConfig: Array<{ key: keyof HostManagementExport; title: string; columns: readonly ExportColumn[] }> = [
    { key: 'hosts', title: '主机清单', columns: hostColumns },
  ];
  const sheets = sheetsConfig
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

function escapeXml(value: string) {
  return value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f&<>"']/g, (char) => {
    if (char === '&') return '&amp;';
    if (char === '<') return '&lt;';
    if (char === '>') return '&gt;';
    if (char === '"') return '&quot;';
    if (char === "'") return '&apos;';
    return '';
  });
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
