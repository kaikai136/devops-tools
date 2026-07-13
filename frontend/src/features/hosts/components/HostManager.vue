<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { useAppContext } from '@app/context';
import { useColumnVisibility } from '@shared/composables/useColumnVisibility';
import {
  createQuickCommand,
  deleteQuickCommand,
  listQuickCommands,
  reorderQuickCommands,
  updateQuickCommand,
  type QuickCommand,
  type QuickCommandPayload,
} from '../../../services/quickCommands';
import { formatDateTime } from '../../../utils/datetime';
import AppIcon from '@shared/components/AppIcon.vue';
import HostEditorDialog from './HostEditorDialog.vue';
import HostGroupTree from './HostGroupTree.vue';
import HostMoveDialog from './HostMoveDialog.vue';
import HostTable from './HostTable.vue';
import type { HostMoveForm, ManagedHostForm } from '../composables/useHostEditor';
import HostToolbar, { type HostColumnKey } from './HostToolbar.vue';

interface HostQuickCommandDialogState {
  visible: boolean;
  mode: 'create' | 'edit';
  commandId: number | null;
  draft: QuickCommandPayload;
  saving: boolean;
  error: string;
}

const hostColumnOptions = [
  { key: 'group', label: '主机分组', width: 'minmax(100px, 0.8fr)', minWidth: 100 },
  { key: 'name', label: '节点', width: 'minmax(120px, 1fr)', minWidth: 120 },
  { key: 'ip', label: 'IP地址', width: 'minmax(150px, 1.1fr)', minWidth: 150 },
  { key: 'machine', label: '机器名称', width: 'minmax(110px, 0.8fr)', minWidth: 110 },
  { key: 'systemArch', label: '系统架构', width: 'minmax(96px, 0.65fr)', minWidth: 96 },
  { key: 'systemType', label: '系统类型', width: 'minmax(96px, 0.65fr)', minWidth: 96 },
  { key: 'config', label: '配置信息', width: 'minmax(130px, 0.9fr)', minWidth: 130 },
  { key: 'platformType', label: '平台类型', width: 'minmax(88px, 0.6fr)', minWidth: 88 },
  { key: 'user', label: '用户', width: 'minmax(80px, 0.65fr)', minWidth: 80 },
  { key: 'port', label: '端口', width: 'minmax(64px, 0.45fr)', minWidth: 64 },
  { key: 'createdAt', label: '创建时间', width: 'minmax(150px, 1fr)', minWidth: 150 },
  { key: 'updatedAt', label: '更新时间', width: 'minmax(150px, 1fr)', minWidth: 150 },
  { key: 'creator', label: '创建者', width: 'minmax(90px, 0.65fr)', minWidth: 90 },
  { key: 'remark', label: '备注', width: 'minmax(130px, 1fr)', minWidth: 130 },
  { key: 'status', label: '状态', width: 'minmax(86px, 0.65fr)', minWidth: 86 },
  { key: 'actions', label: '操作', width: 'minmax(132px, 0.8fr)', minWidth: 132 },
] as const;

const hostColumnStorageKey = 'ops-tool.host-manager.columns.v3';
const fallbackHostColumnKey: HostColumnKey = 'name';

const {
  activeTool,
  hostGroups,
  hostGroupRoot,
  flatHostGroups,
  hostGroupRows,
  hostGroupRootExpanded,
  selectedHostGroup,
  selectManagedGroup,
  isHostGroupExpanded,
  toggleHostGroupExpanded,
  openHostGroupMenu,
  closeHostGroupMenu,
  hostSearch,
  hostStatusFilter,
  hostSortKey,
  hostSortDirection,
  hostCredentials,
  managedHostStats,
  visibleManagedHosts,
  groupMoveHosts,
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
  openHostTransferDialog,
  setHostSort,
  hostSortMark,
  hostGroupName,
  openAddRootHostGroup,
  openAddHostGroup,
  openRenameHostGroup,
  toggleHostGroupRootExpanded,
  startHostGroupDrag,
  updateHostGroupDropTarget,
  clearHostGroupDropTarget,
  dropHostGroup,
  finishHostGroupDrag,
  saveHostGroupInlineEdit,
  saveRootHostGroup,
  cancelHostGroupInlineEdit,
  openWebTerminal,
  addManagedHost,
  verifyManagedHost,
  verifyVisibleManagedHosts,
  verifySelectedManagedHosts,
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
  canUsePageAction,
  canUseAnyPageAction,
  showToast,
} = useAppContext();

const hostColumnSettingsOpen = ref(false);
const hostMoreActionsOpen = ref(false);
const fullscreen = ref(false);
const hostPage = ref(1);
const hostPageSize = ref(10);
const hostQuickCommandManagerOpen = ref(false);
const hostQuickCommands = ref<QuickCommand[]>([]);
const hostQuickCommandCategory = ref('all');
const hostQuickCommandSearch = ref('');
const isHostQuickCommandLoading = ref(false);
const hostQuickCommandError = ref('');
const hostQuickCommandDialog = ref<HostQuickCommandDialogState>({
  visible: false,
  mode: 'create',
  commandId: null,
  draft: createHostQuickCommandDraft(),
  saving: false,
  error: '',
});
const canUseHostList = computed(() =>
  canUsePageAction('hosts', 'create') ||
  canUsePageAction('hosts', 'edit') ||
  canUsePageAction('hosts', 'delete') ||
  canUsePageAction('hosts', 'verify') ||
  canUsePageAction('hosts', 'move') ||
  canUsePageAction('hosts', 'filter') ||
  canUsePageAction('hosts', 'group') ||
  canUsePageAction('hosts', 'import') ||
  canUsePageAction('hosts', 'export') ||
  canUsePageAction('hosts', 'terminal') ||
  canUsePageAction('hosts', 'quick_commands')
);
const {
  visibility: hostColumnVisibility,
  visibleColumns: visibleHostTableColumns,
  allColumnsVisible: allHostColumnsVisible,
  someColumnsVisible: someHostColumnsVisible,
  isColumnVisible: isHostColumnVisible,
  isOnlyVisibleColumn: isOnlyVisibleHostColumn,
  updateColumnVisibility: updateHostColumnVisibility,
  toggleAllColumns: toggleAllHostColumns,
  resetColumns: resetHostColumns,
} = useColumnVisibility(hostColumnOptions, {
  storageKey: hostColumnStorageKey,
  fallbackKey: fallbackHostColumnKey,
});
const hostTableStyle = computed<Record<string, string>>(() => {
  const columns = visibleHostTableColumns.value;
  const minimumWidth = columns.reduce((total, column) => total + (column.minWidth ?? 0), 0) + columns.length * 12 + 238;
  const actionsVisible = columns.some((column) => column.key === 'actions');
  const templateColumns = columns.map((column) => {
    if (column.key === 'status') return 'var(--host-status-column-width)';
    if (column.key === 'actions') return 'var(--host-actions-column-width)';
    return column.width;
  });

  return {
    '--host-table-columns': `var(--host-select-column-width) ${templateColumns.join(' ') || 'minmax(180px, 1fr)'}`,
    '--host-table-min-width': `${Math.max(760, minimumWidth)}px`,
    '--host-select-column-width': '38px',
    '--host-status-column-width': '86px',
    '--host-actions-column-width': '132px',
    '--host-status-sticky-right': actionsVisible ? 'calc(var(--host-actions-column-width) + 12px)' : '0px',
  };
});
const hostTotalPages = computed(() => Math.max(1, Math.ceil(visibleManagedHosts.value.length / hostPageSize.value)));
const paginatedManagedHosts = computed(() => {
  const start = (hostPage.value - 1) * hostPageSize.value;
  return visibleManagedHosts.value.slice(start, start + hostPageSize.value);
});
const visibleHostIds = computed(() => paginatedManagedHosts.value.map((host) => host.id));
const allVisibleHostsSelected = computed(() => visibleHostIds.value.length > 0 && visibleHostIds.value.every((id) => selectedManagedHostIds.value.has(id)));
const someVisibleHostsSelected = computed(() => visibleHostIds.value.some((id) => selectedManagedHostIds.value.has(id)));
const selectedManagedHostCount = computed(() => selectedManagedHostIds.value.size);
const canUseHostAnyAction = computed(() => canUseHostList.value);
const canUseHostMoreActions = computed(() =>
  canUsePageAction('hosts', 'verify') ||
  canUsePageAction('hosts', 'filter') ||
  canUsePageAction('hosts', 'move') ||
  canUsePageAction('hosts', 'delete')
);
const canUseHostRowActions = computed(() =>
  canUsePageAction('hosts', 'edit') ||
  canUsePageAction('hosts', 'verify') ||
  canUsePageAction('hosts', 'delete')
);
const hostPageStart = computed(() => (visibleManagedHosts.value.length ? (hostPage.value - 1) * hostPageSize.value + 1 : 0));
const hostPageEnd = computed(() => Math.min(hostPage.value * hostPageSize.value, visibleManagedHosts.value.length));
const hostPageNumbers = computed(() => {
  const total = hostTotalPages.value;
  const current = hostPage.value;
  const from = Math.max(1, current - 2);
  const to = Math.min(total, current + 2);
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
});
const hostQuickCommandCategories = computed(() => {
  const categories = hostQuickCommands.value.map((command) => command.category).filter(Boolean);
  return [...new Set(categories)].sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'));
});
const filteredHostQuickCommands = computed(() => {
  const query = hostQuickCommandSearch.value.trim().toLowerCase();
  return hostQuickCommands.value.filter((command) => {
    const matchesCategory = hostQuickCommandCategory.value === 'all' || command.category === hostQuickCommandCategory.value;
    if (!matchesCategory) return false;
    if (!query) return true;
    return [command.name, command.category, command.command, command.description]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});

watch([visibleManagedHosts, hostPageSize], () => {
  if (hostPage.value > hostTotalPages.value) {
    hostPage.value = hostTotalPages.value;
  }
});

watch([hostSearch, selectedHostGroup, hostStatusFilter, hostSortKey, hostSortDirection], () => {
  hostPage.value = 1;
});

function updateHostMoveFormField(field: keyof HostMoveForm, value: number | null) {
  hostMoveForm.value[field] = value;
}

function updateHostFormField(field: keyof ManagedHostForm, value: ManagedHostForm[keyof ManagedHostForm]) {
  (hostForm.value[field] as ManagedHostForm[keyof ManagedHostForm]) = value;
}

function updateHostGroupInlineName(value: string) {
  if (hostGroupInlineEdit.value) hostGroupInlineEdit.value.name = value;
}

function toggleAllVisibleHosts(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const next = new Set(selectedManagedHostIds.value);
  visibleHostIds.value.forEach((id) => {
    if (checked) {
      next.add(id);
    } else {
      next.delete(id);
    }
  });
  selectedManagedHostIds.value = next;
}

function toggleHostSelected(hostId: number, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const next = new Set(selectedManagedHostIds.value);
  if (checked) {
    next.add(hostId);
  } else {
    next.delete(hostId);
  }
  selectedManagedHostIds.value = next;
}

function clearSelectedManagedHosts() {
  selectedManagedHostIds.value = new Set();
}

function setHostPage(page: number) {
  hostPage.value = Math.min(Math.max(1, page), hostTotalPages.value);
}

function closeHostMenus() {
  closeHostGroupMenu();
  closeHostColumnSettings();
  closeHostMoreActions();
}

function toggleHostColumnSettings() {
  closeHostGroupMenu();
  closeHostMoreActions();
  hostColumnSettingsOpen.value = !hostColumnSettingsOpen.value;
}

function closeHostColumnSettings() {
  hostColumnSettingsOpen.value = false;
}

function toggleHostMoreActions() {
  closeHostGroupMenu();
  closeHostColumnSettings();
  hostMoreActionsOpen.value = !hostMoreActionsOpen.value;
}

function closeHostMoreActions() {
  hostMoreActionsOpen.value = false;
}

function createHostQuickCommandDraft(command?: QuickCommand | null): QuickCommandPayload {
  return {
    name: command?.name ?? '',
    category: command?.category ?? hostQuickCommands.value[0]?.category ?? 'Linux',
    command: command?.command ?? '',
    description: command?.description ?? '',
    enabled: command?.enabled ?? true,
    sortOrder: command?.sortOrder ?? 0,
  };
}

function sortHostQuickCommands(commands: QuickCommand[]) {
  return [...commands].sort(
    (left, right) =>
      left.category.localeCompare(right.category, 'zh-Hans-CN') ||
      left.sortOrder - right.sortOrder ||
      left.id - right.id,
  );
}

async function loadHostQuickCommands() {
  isHostQuickCommandLoading.value = true;
  hostQuickCommandError.value = '';
  try {
    hostQuickCommands.value = await listQuickCommands();
    if (
      hostQuickCommandCategory.value !== 'all' &&
      !hostQuickCommands.value.some((command) => command.category === hostQuickCommandCategory.value)
    ) {
      hostQuickCommandCategory.value = 'all';
    }
  } catch (error) {
    hostQuickCommandError.value = error instanceof Error ? error.message : '快捷命令加载失败';
  } finally {
    isHostQuickCommandLoading.value = false;
  }
}

async function openHostQuickCommandManager() {
  closeHostMenus();
  hostQuickCommandManagerOpen.value = true;
  if (!hostQuickCommands.value.length && !isHostQuickCommandLoading.value) {
    await loadHostQuickCommands();
  }
}

function closeHostQuickCommandManager() {
  if (hostQuickCommandDialog.value.saving) return;
  hostQuickCommandManagerOpen.value = false;
  closeHostQuickCommandDialog();
}

function openHostQuickCommandDialog(command: QuickCommand | null = null) {
  hostQuickCommandDialog.value = {
    visible: true,
    mode: command ? 'edit' : 'create',
    commandId: command?.id ?? null,
    draft: createHostQuickCommandDraft(command),
    saving: false,
    error: '',
  };
}

function closeHostQuickCommandDialog() {
  if (hostQuickCommandDialog.value.saving) return;
  hostQuickCommandDialog.value = {
    visible: false,
    mode: 'create',
    commandId: null,
    draft: createHostQuickCommandDraft(),
    saving: false,
    error: '',
  };
}

function hostQuickCommandPayload(draft: QuickCommandPayload): QuickCommandPayload {
  return {
    name: draft.name.trim(),
    category: draft.category.trim(),
    command: draft.command.trim(),
    description: draft.description.trim(),
    enabled: draft.enabled,
    sortOrder: draft.sortOrder,
  };
}

async function saveHostQuickCommandDialog() {
  const dialog = hostQuickCommandDialog.value;
  if (!dialog.visible || dialog.saving) return;
  const payload = hostQuickCommandPayload(dialog.draft);
  if (!payload.name || !payload.category || !payload.command) {
    hostQuickCommandDialog.value = { ...dialog, error: '请填写名称、分类和命令内容' };
    return;
  }

  hostQuickCommandDialog.value = { ...dialog, saving: true, error: '' };
  try {
    const saved =
      dialog.mode === 'edit' && dialog.commandId
        ? await updateQuickCommand(dialog.commandId, payload)
        : await createQuickCommand(payload);
    const nextCommands =
      dialog.mode === 'edit'
        ? hostQuickCommands.value.map((command) => (command.id === saved.id ? saved : command))
        : [...hostQuickCommands.value, saved];
    hostQuickCommands.value = sortHostQuickCommands(nextCommands);
    hostQuickCommandCategory.value = saved.category;
    closeHostQuickCommandDialog();
    showToast('保存成功', `快捷命令「${saved.name}」已保存。`);
  } catch (error) {
    hostQuickCommandDialog.value = {
      ...dialog,
      saving: false,
      error: error instanceof Error ? error.message : '快捷命令保存失败',
    };
  }
}

async function toggleHostQuickCommand(command: QuickCommand) {
  try {
    const saved = await updateQuickCommand(command.id, {
      name: command.name,
      category: command.category,
      command: command.command,
      description: command.description,
      enabled: !command.enabled,
      sortOrder: command.sortOrder,
    });
    hostQuickCommands.value = hostQuickCommands.value.map((item) => (item.id === saved.id ? saved : item));
  } catch (error) {
    hostQuickCommandError.value = error instanceof Error ? error.message : '快捷命令状态更新失败';
  }
}

async function moveHostQuickCommand(command: QuickCommand, direction: -1 | 1) {
  const visibleCommands = filteredHostQuickCommands.value;
  const visibleIndex = visibleCommands.findIndex((item) => item.id === command.id);
  const target = visibleCommands[visibleIndex + direction];
  if (!target) return;

  const nextCommands = [...hostQuickCommands.value];
  const sourceIndex = nextCommands.findIndex((item) => item.id === command.id);
  const targetIndex = nextCommands.findIndex((item) => item.id === target.id);
  if (sourceIndex === -1 || targetIndex === -1) return;

  [nextCommands[sourceIndex], nextCommands[targetIndex]] = [nextCommands[targetIndex], nextCommands[sourceIndex]];
  await saveHostQuickCommandOrder(nextCommands);
}

async function saveHostQuickCommandOrder(nextCommands: QuickCommand[]) {
  const previousCommands = hostQuickCommands.value;
  hostQuickCommands.value = nextCommands.map((command, index) => ({ ...command, sortOrder: (index + 1) * 10 }));
  try {
    hostQuickCommands.value = await reorderQuickCommands(hostQuickCommands.value.map((command) => command.id));
  } catch (error) {
    hostQuickCommands.value = previousCommands;
    hostQuickCommandError.value = error instanceof Error ? error.message : '快捷命令排序保存失败';
  }
}

async function removeHostQuickCommand(command: QuickCommand) {
  if (!window.confirm(`删除快捷命令「${command.name}」？`)) return;
  try {
    await deleteQuickCommand(command.id);
    hostQuickCommands.value = hostQuickCommands.value.filter((item) => item.id !== command.id);
    showToast('删除成功', `快捷命令「${command.name}」已删除。`);
  } catch (error) {
    hostQuickCommandError.value = error instanceof Error ? error.message : '快捷命令删除失败';
  }
}

function toggleFullscreen() {
  closeHostMenus();
  fullscreen.value = !fullscreen.value;
}

function setHostStatusFilter(filter: 'all' | 'unverified') {
  hostStatusFilter.value = filter;
  closeHostMoreActions();
}

async function runVerifySelectedHosts() {
  closeHostMoreActions();
  await verifySelectedManagedHosts();
}

function runMoveSelectedHosts() {
  closeHostMoreActions();
  openMoveSelectedHostsDialog();
}

function runDeleteSelectedHosts() {
  closeHostMoreActions();
  deleteSelectedManagedHosts();
}

function formatHostDate(value: string | null | undefined) {
  return formatDateTime(value, '-');
}

function hostPlatformType(value: string | null | undefined) {
  const type = String(value || '').toLowerCase();
  return type === 'windows' ? 'windows' : 'linux';
}
</script>

<template>
  <section v-if="activeTool === 'hosts'" class="host-manager-page" :class="{ fullscreen }" @click="closeHostMenus">
    <template v-if="canUseHostAnyAction">
    <HostGroupTree
      v-if="canUseHostList"
      :groups="hostGroups"
      :root="hostGroupRoot"
      :rows="hostGroupRows"
      :root-expanded="hostGroupRootExpanded"
      :selected-group="selectedHostGroup"
      :inline-edit="hostGroupInlineEdit"
      :menu="hostGroupMenu"
      :dragged-group-id="draggedHostGroupId"
      :drop-target="hostGroupDropTarget"
      :can-manage-groups="canUsePageAction('hosts', 'group')"
      :can-create-hosts="canUsePageAction('hosts', 'create')"
      :can-move-hosts="canUsePageAction('hosts', 'move')"
      :can-delete-hosts="canUsePageAction('hosts', 'delete')"
      :show-group-action-divider="canUseAnyPageAction('hosts', ['create', 'move', 'delete'])"
      :is-group-expanded="isHostGroupExpanded"
      @add-root="openAddRootHostGroup"
      @select-group="selectManagedGroup"
      @toggle-root="toggleHostGroupRootExpanded"
      @toggle-group="toggleHostGroupExpanded"
      @open-menu="openHostGroupMenu"
      @update-inline-name="updateHostGroupInlineName"
      @save-inline-edit="saveHostGroupInlineEdit"
      @cancel-inline-edit="cancelHostGroupInlineEdit"
      @drag-start="startHostGroupDrag"
      @drag-over="updateHostGroupDropTarget"
      @drag-leave="clearHostGroupDropTarget"
      @drop="dropHostGroup"
      @drag-end="finishHostGroupDrag"
      @add-child="openAddHostGroup"
      @rename="openRenameHostGroup"
      @add-host="addManagedHost"
      @move-host="openMoveHostDialog"
      @delete-hosts="deleteManagedHostsInGroup"
      @delete-group="deleteHostGroup"
    />

    <article v-if="canUseHostList" class="panel host-table-panel">
      <HostToolbar
        :search="hostSearch"
        :status-filter="hostStatusFilter"
        :selected-count="selectedManagedHostCount"
        :more-actions-open="hostMoreActionsOpen"
        :column-settings-open="hostColumnSettingsOpen"
        :fullscreen="fullscreen"
        :columns="hostColumnOptions"
        :column-visibility="hostColumnVisibility"
        :all-columns-visible="allHostColumnsVisible"
        :some-columns-visible="someHostColumnsVisible"
        :is-only-visible-column="isOnlyVisibleHostColumn"
        :can-create="canUsePageAction('hosts', 'create')"
        :can-manage-quick-commands="canUsePageAction('hosts', 'quick_commands')"
        :can-use-more-actions="canUseHostMoreActions"
        :can-verify="canUsePageAction('hosts', 'verify')"
        :can-filter="canUsePageAction('hosts', 'filter')"
        :can-move="canUsePageAction('hosts', 'move')"
        :can-delete="canUsePageAction('hosts', 'delete')"
        :show-more-actions-divider="canUseAnyPageAction('hosts', ['verify', 'filter']) && canUseAnyPageAction('hosts', ['move', 'delete'])"
        :can-export="canUsePageAction('hosts', 'export')"
        @update:search="hostSearch = $event"
        @create="addManagedHost()"
        @open-quick-commands="openHostQuickCommandManager"
        @toggle-more-actions="toggleHostMoreActions"
        @status-filter="setHostStatusFilter"
        @verify-selected="runVerifySelectedHosts"
        @move-selected="runMoveSelectedHosts"
        @delete-selected="runDeleteSelectedHosts"
        @export="openHostTransferDialog('export')"
        @refresh="loadHostManagement"
        @toggle-column-settings="toggleHostColumnSettings"
        @toggle-all-columns="toggleAllHostColumns"
        @reset-columns="resetHostColumns"
        @update-column="updateHostColumnVisibility"
        @toggle-fullscreen="toggleFullscreen"
      />
      <HostTable
        :hosts="paginatedManagedHosts"
        :visible-host-count="visibleManagedHosts.length"
        :selected-ids="selectedManagedHostIds"
        :visible-ids="visibleHostIds"
        :all-visible-selected="allVisibleHostsSelected"
        :some-visible-selected="someVisibleHostsSelected"
        :table-style="hostTableStyle"
        :sort-key="hostSortKey"
        :sort-direction="hostSortDirection"
        :page="hostPage"
        :page-size="hostPageSize"
        :total-pages="hostTotalPages"
        :page-numbers="hostPageNumbers"
        :page-start="hostPageStart"
        :page-end="hostPageEnd"
        :selected-count="selectedManagedHostCount"
        :stats="managedHostStats"
        :loading="isLoadingHosts"
        :verifying-ids="verifyingHostIds"
        :can-open-terminal="canUsePageAction('hosts', 'terminal')"
        :can-edit="canUsePageAction('hosts', 'edit')"
        :can-verify="canUsePageAction('hosts', 'verify')"
        :can-move="canUsePageAction('hosts', 'move')"
        :can-delete="canUsePageAction('hosts', 'delete')"
        :can-use-row-actions="canUseHostRowActions"
        :is-column-visible="isHostColumnVisible"
        :group-name="hostGroupName"
        :sort-mark="hostSortMark"
        :format-date="formatHostDate"
        :platform-type="hostPlatformType"
        @toggle-all-visible="toggleAllVisibleHosts"
        @toggle-host="toggleHostSelected"
        @sort="setHostSort"
        @open-terminal="openWebTerminal"
        @edit="editManagedHost"
        @verify="verifyManagedHost"
        @delete="deleteManagedHost"
        @page-change="setHostPage"
        @page-size-change="hostPageSize = $event"
        @clear-selection="clearSelectedManagedHosts"
        @verify-selected="runVerifySelectedHosts"
        @move-selected="runMoveSelectedHosts"
        @delete-selected="runDeleteSelectedHosts"
      />
    </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>

    <div v-if="hostQuickCommandManagerOpen" class="modal-backdrop" @click.self="closeHostQuickCommandManager">
      <article class="host-quick-command-modal" @click.stop>
        <header class="host-quick-command-head">
          <div>
            <strong><AppIcon name="zap" :size="16" />快捷命令</strong>
            <span>管理 Web 终端中可用的快捷命令模板</span>
          </div>
          <button type="button" title="关闭" aria-label="关闭" @click="closeHostQuickCommandManager">
            <AppIcon name="x" :size="16" />
          </button>
        </header>
        <div class="host-quick-command-layout">
          <aside class="host-quick-command-categories">
            <button
              type="button"
              :class="{ active: hostQuickCommandCategory === 'all' }"
              @click="hostQuickCommandCategory = 'all'"
            >
              全部
              <span>{{ hostQuickCommands.length }}</span>
            </button>
            <button
              v-for="category in hostQuickCommandCategories"
              :key="category"
              type="button"
              :class="{ active: hostQuickCommandCategory === category }"
              @click="hostQuickCommandCategory = category"
            >
              {{ category }}
              <span>{{ hostQuickCommands.filter((command) => command.category === category).length }}</span>
            </button>
          </aside>
          <section class="host-quick-command-content">
            <div class="host-quick-command-toolbar">
              <label>
                <AppIcon name="search" :size="14" />
                <input v-model="hostQuickCommandSearch" type="search" placeholder="搜索名称、分类或命令" />
              </label>
              <span>{{ filteredHostQuickCommands.length }} 条</span>
              <button type="button" title="刷新" aria-label="刷新" :disabled="isHostQuickCommandLoading" @click="loadHostQuickCommands">
                <AppIcon name="refresh" :size="15" />
              </button>
              <button class="primary" type="button" @click="openHostQuickCommandDialog()">
                <AppIcon name="plus" :size="15" />
                新增
              </button>
            </div>
            <p v-if="hostQuickCommandError" class="host-quick-command-error">{{ hostQuickCommandError }}</p>
            <div class="host-quick-command-list">
              <p v-if="isHostQuickCommandLoading" class="host-quick-command-empty">加载中...</p>
              <p v-else-if="!filteredHostQuickCommands.length" class="host-quick-command-empty">暂无快捷命令</p>
              <template v-else>
                <article
                  v-for="(command, index) in filteredHostQuickCommands"
                  :key="command.id"
                  class="host-quick-command-item"
                  :class="{ disabled: !command.enabled }"
                >
                  <div class="host-quick-command-info">
                    <div>
                      <strong>{{ command.name }}</strong>
                      <span>{{ command.category }}</span>
                      <em>{{ command.enabled ? '启用' : '禁用' }}</em>
                    </div>
                    <code>{{ command.command }}</code>
                    <p v-if="command.description">{{ command.description }}</p>
                  </div>
                  <div class="host-quick-command-actions">
                    <button
                      type="button"
                      :title="command.enabled ? '禁用' : '启用'"
                      :aria-label="command.enabled ? '禁用' : '启用'"
                      @click="toggleHostQuickCommand(command)"
                    >
                      <AppIcon :name="command.enabled ? 'eye' : 'eyeOff'" :size="14" />
                    </button>
                    <button
                      class="move-up"
                      type="button"
                      title="上移"
                      aria-label="上移"
                      :disabled="index === 0"
                      @click="moveHostQuickCommand(command, -1)"
                    >
                      <AppIcon name="chevronDown" :size="14" />
                    </button>
                    <button
                      type="button"
                      title="下移"
                      aria-label="下移"
                      :disabled="index === filteredHostQuickCommands.length - 1"
                      @click="moveHostQuickCommand(command, 1)"
                    >
                      <AppIcon name="chevronDown" :size="14" />
                    </button>
                    <button type="button" title="编辑" aria-label="编辑" @click="openHostQuickCommandDialog(command)">
                      <AppIcon name="edit" :size="14" />
                    </button>
                    <button type="button" title="删除" aria-label="删除" @click="removeHostQuickCommand(command)">
                      <AppIcon name="trash" :size="14" />
                    </button>
                  </div>
                </article>
              </template>
            </div>
          </section>
        </div>
      </article>
    </div>

    <div v-if="hostQuickCommandDialog.visible" class="modal-backdrop host-quick-command-dialog-backdrop" @click.self="closeHostQuickCommandDialog">
      <form class="host-form-modal host-quick-command-form" @submit.prevent="saveHostQuickCommandDialog">
        <button class="modal-close" type="button" :disabled="hostQuickCommandDialog.saving" @click="closeHostQuickCommandDialog">
          <AppIcon name="x" :size="16" />
        </button>
        <h2>{{ hostQuickCommandDialog.mode === 'edit' ? '编辑快捷命令' : '新增快捷命令' }}</h2>
        <p v-if="hostQuickCommandDialog.error" class="host-quick-command-error">{{ hostQuickCommandDialog.error }}</p>
        <label>
          <span>名称</span>
          <input v-model="hostQuickCommandDialog.draft.name" autofocus :disabled="hostQuickCommandDialog.saving" />
        </label>
        <label>
          <span>分类</span>
          <input v-model="hostQuickCommandDialog.draft.category" list="host-quick-command-category-options" :disabled="hostQuickCommandDialog.saving" />
          <datalist id="host-quick-command-category-options">
            <option v-for="category in hostQuickCommandCategories" :key="category" :value="category"></option>
          </datalist>
        </label>
        <label>
          <span>命令</span>
          <textarea v-model="hostQuickCommandDialog.draft.command" rows="4" :disabled="hostQuickCommandDialog.saving"></textarea>
        </label>
        <label>
          <span>说明</span>
          <input v-model="hostQuickCommandDialog.draft.description" :disabled="hostQuickCommandDialog.saving" />
        </label>
        <label class="host-quick-command-enabled">
          <input v-model="hostQuickCommandDialog.draft.enabled" type="checkbox" :disabled="hostQuickCommandDialog.saving" />
          <span>启用</span>
        </label>
        <div class="host-form-actions">
          <button type="button" :disabled="hostQuickCommandDialog.saving" @click="closeHostQuickCommandDialog">取消</button>
          <button class="primary" type="submit" :disabled="hostQuickCommandDialog.saving">
            {{ hostQuickCommandDialog.saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </form>
    </div>

    <HostEditorDialog
      :dialog="hostDialog"
      :form="hostForm"
      :errors="hostFormErrors"
      :root="hostGroupRoot"
      :groups="flatHostGroups"
      :credentials="hostCredentials"
      @close="hostDialog = null"
      @submit="saveManagedHost"
      @update-form-field="updateHostFormField"
      @apply-credential="applyCredentialToHostForm"
      @upload-private-key="uploadHostPrivateKey"
    />

    <HostMoveDialog
      :open="hostMoveDialogOpen"
      :mode="hostMoveMode"
      :form="hostMoveForm"
      :hosts="groupMoveHosts"
      :root="hostGroupRoot"
      :groups="flatHostGroups"
      :selected-count="selectedManagedHostCount"
      @close="hostMoveDialogOpen = false"
      @submit="saveMoveManagedHost"
      @update-form-field="updateHostMoveFormField"
    />
  </section>
</template>
