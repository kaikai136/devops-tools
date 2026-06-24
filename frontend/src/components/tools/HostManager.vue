<script setup lang="ts">
import { computed, ref } from 'vue';

import { useAppContext } from '../../appContext';
import { useColumnVisibility } from '../../composables/useColumnVisibility';
import { formatDateTime } from '../../utils/datetime';
import AppIcon from '../common/AppIcon.vue';

const hostColumnOptions = [
  { key: 'group', label: '主机分组', width: 'minmax(100px, 0.8fr)', minWidth: 100 },
  { key: 'name', label: '节点', width: 'minmax(120px, 1fr)', minWidth: 120 },
  { key: 'ip', label: 'IP地址', width: 'minmax(150px, 1.1fr)', minWidth: 150 },
  { key: 'config', label: '配置信息', width: 'minmax(130px, 0.9fr)', minWidth: 130 },
  { key: 'machine', label: '机器名称', width: 'minmax(110px, 0.8fr)', minWidth: 110 },
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

type HostColumnKey = (typeof hostColumnOptions)[number]['key'];

const hostColumnStorageKey = 'ops-tool.host-manager.columns.v2';
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
  hostPrivateIpExists,
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
  editManagedHost,
  saveManagedHost,
  applyCredentialToHostForm,
  uploadHostPrivateKey,
  openMoveHostDialog,
  saveMoveManagedHost,
  deleteManagedHost,
  deleteManagedHostsInGroup,
  deleteHostGroup,
} = useAppContext();

const hostColumnSettingsOpen = ref(false);
const selectedHostIds = ref<Set<number>>(new Set());
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
  const minimumWidth = columns.reduce((total, column) => total + column.minWidth, 0) + columns.length * 12 + 238;
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
const visibleHostIds = computed(() => visibleManagedHosts.value.map((host) => host.id));
const allVisibleHostsSelected = computed(() => visibleHostIds.value.length > 0 && visibleHostIds.value.every((id) => selectedHostIds.value.has(id)));
const someVisibleHostsSelected = computed(() => visibleHostIds.value.some((id) => selectedHostIds.value.has(id)));

function toggleAllVisibleHosts(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const next = new Set(selectedHostIds.value);
  visibleHostIds.value.forEach((id) => {
    if (checked) {
      next.add(id);
    } else {
      next.delete(id);
    }
  });
  selectedHostIds.value = next;
}

function toggleHostSelected(hostId: number, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const next = new Set(selectedHostIds.value);
  if (checked) {
    next.add(hostId);
  } else {
    next.delete(hostId);
  }
  selectedHostIds.value = next;
}

function closeHostMenus() {
  closeHostGroupMenu();
  closeHostColumnSettings();
}

function toggleHostColumnSettings() {
  closeHostGroupMenu();
  hostColumnSettingsOpen.value = !hostColumnSettingsOpen.value;
}

function closeHostColumnSettings() {
  hostColumnSettingsOpen.value = false;
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
  <section v-if="activeTool === 'hosts'" class="host-manager-page" @click="closeHostMenus">
    <article class="panel host-groups-panel">
      <div class="host-group-head">
        <h2>分组列表</h2>
        <button class="group-add-button" type="button" title="添加分组" aria-label="添加分组" @click.stop="openAddRootHostGroup()"><AppIcon name="plus" :size="16" /></button>
      </div>
      <div class="host-group-list">
        <template v-for="row in hostGroupRows" :key="row.kind === 'root' ? 'group-root' : row.kind === 'group' ? `group-${row.group.key}` : `editor-${row.editor.mode}-${row.editor.after ?? 'end'}`">
          <button
            v-if="row.kind === 'root'"
            class="host-group-row host-group-root"
            :class="{ active: selectedHostGroup === null }"
            type="button"
            @click.stop="selectManagedGroup(null)"
            @dblclick.stop="toggleHostGroupRootExpanded"
            @contextmenu="openHostGroupMenu(row.group, $event)"
          >
            <span class="folder-caret expandable" role="button" @click.stop="toggleHostGroupRootExpanded">
              <AppIcon :name="hostGroupRootExpanded ? 'chevronDown' : 'chevronRight'" :size="15" />
            </span>
            <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
            <strong>{{ row.group.label }}</strong>
            <em>{{ row.group.count }}</em>
          </button>
          <template v-else-if="row.kind === 'group'">
            <div
              v-if="hostGroupInlineEdit?.mode === 'rename' && hostGroupInlineEdit.groupId === row.group.key"
              class="host-group-row editing"
              :style="{ paddingLeft: `${10 + row.group.level * 26}px` }"
              @click.stop
            >
              <span
                class="folder-caret"
                :class="{ expandable: row.group.children?.length }"
                role="button"
                @click.stop="toggleHostGroupExpanded(row.group)"
              ><AppIcon v-if="row.group.children?.length" :name="isHostGroupExpanded(row.group) ? 'chevronDown' : 'chevronRight'" :size="15" /></span>
              <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
              <input
                v-model="hostGroupInlineEdit.name"
                class="host-group-inline-input"
                autofocus
                @blur="saveHostGroupInlineEdit"
                @keydown.enter.prevent="saveHostGroupInlineEdit"
                @keydown.esc.prevent="cancelHostGroupInlineEdit"
              />
              <em>{{ row.group.count }}</em>
            </div>
            <button
              v-else
              class="host-group-row"
              :class="{
                active: selectedHostGroup === row.group.key,
                dragging: draggedHostGroupId === row.group.key,
                'drop-before': hostGroupDropTarget?.key === row.group.key && hostGroupDropTarget.position === 'before',
                'drop-inside': hostGroupDropTarget?.key === row.group.key && hostGroupDropTarget.position === 'inside',
                'drop-after': hostGroupDropTarget?.key === row.group.key && hostGroupDropTarget.position === 'after',
              }"
              :style="{ paddingLeft: `${10 + row.group.level * 26}px` }"
              type="button"
              draggable="true"
              @click.stop="selectManagedGroup(row.group.key)"
              @dblclick.stop="toggleHostGroupExpanded(row.group)"
              @contextmenu="openHostGroupMenu(row.group, $event)"
              @dragstart="startHostGroupDrag(row.group, $event)"
              @dragover="updateHostGroupDropTarget(row.group, $event)"
              @dragleave="clearHostGroupDropTarget"
              @drop="dropHostGroup(row.group, $event)"
              @dragend="finishHostGroupDrag"
            >
              <span
                class="folder-caret"
                :class="{ expandable: row.group.children?.length }"
                role="button"
                @click.stop="toggleHostGroupExpanded(row.group)"
              ><AppIcon v-if="row.group.children?.length" :name="isHostGroupExpanded(row.group) ? 'chevronDown' : 'chevronRight'" :size="15" /></span>
              <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
              <strong>{{ row.group.label }}</strong>
              <em>{{ row.group.count }}</em>
            </button>
          </template>
          <div
            v-else
            class="host-group-row editing"
            :class="{ draft: row.editor.mode !== 'rename-root' }"
            :style="{ paddingLeft: `${10 + row.editor.level * 26}px` }"
            @click.stop
          >
            <span class="folder-caret"></span>
            <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
            <input
              v-model="row.editor.name"
              class="host-group-inline-input"
              autofocus
              placeholder="输入分组名称"
              @blur="saveHostGroupInlineEdit"
              @keydown.enter.prevent="saveHostGroupInlineEdit"
              @keydown.esc.prevent="cancelHostGroupInlineEdit"
            />
            <em>{{ row.editor.mode === 'rename-root' ? hostGroupRoot.count : 0 }}</em>
          </div>
        </template>
        <div v-if="!hostGroups.length && !hostGroupInlineEdit" class="empty-state host-empty">暂无分组。</div>
      </div>

      <div
        v-if="hostGroupMenu"
        class="host-group-menu"
        :style="{ left: `${hostGroupMenu.x}px`, top: `${hostGroupMenu.y}px` }"
        @click.stop
      >
        <button type="button" @click="openAddRootHostGroup(hostGroupMenu.group)"><span><AppIcon name="folderPlus" :size="15" /></span>新建分组</button>
        <button type="button" @click="openAddHostGroup(hostGroupMenu.group.key)"><span><AppIcon name="circlePlus" :size="15" /></span>新建子分组</button>
        <button type="button" @click="openRenameHostGroup(hostGroupMenu.group)"><span><AppIcon name="edit" :size="15" /></span>重命名</button>
        <hr />
        <button type="button" @click="addManagedHost(hostGroupMenu.group.key)"><span><AppIcon name="server" :size="15" /></span>添加主机</button>
        <button type="button" @click="openMoveHostDialog(hostGroupMenu.group)"><span><AppIcon name="upload" :size="15" /></span>移动主机</button>
        <button class="danger" type="button" @click="deleteManagedHostsInGroup(hostGroupMenu.group)"><span><AppIcon name="trash" :size="15" /></span>删除主机</button>
        <hr />
        <button class="danger" type="button" @click="deleteHostGroup(hostGroupMenu.group)"><span><AppIcon name="trash" :size="15" /></span>删除此分组</button>
      </div>
    </article>

    <article class="panel host-table-panel">
      <div class="host-toolbar">
        <input v-model="hostSearch" placeholder="输入别名/IP检索" />
        <div class="host-toolbar-actions">
          <button class="primary" type="button" @click="addManagedHost()"><AppIcon name="plus" :size="16" />新建</button>
          <button class="primary secondary-blue" type="button" @click="verifyVisibleManagedHosts">验证</button>
          <div class="status-tabs">
            <button :class="{ active: hostStatusFilter === 'all' }" type="button" @click="hostStatusFilter = 'all'">全部</button>
            <button :class="{ active: hostStatusFilter === 'unverified' }" type="button" @click="hostStatusFilter = 'unverified'">未验证</button>
          </div>
          <button class="icon-only" type="button" title="刷新" aria-label="刷新" @click="loadHostManagement"><AppIcon name="refresh" :size="16" /></button>
          <div class="host-column-settings" @click.stop>
            <button
              class="icon-only"
              type="button"
              title="列设置"
              aria-label="列设置"
              :aria-expanded="hostColumnSettingsOpen"
              @click="toggleHostColumnSettings"
            >
              <AppIcon name="settings" :size="16" />
            </button>
            <div v-if="hostColumnSettingsOpen" class="host-column-menu">
              <div class="host-column-menu-head">
                <label class="host-column-all">
                  <input
                    type="checkbox"
                    :checked="allHostColumnsVisible"
                    :indeterminate.prop="someHostColumnsVisible && !allHostColumnsVisible"
                    @change="toggleAllHostColumns"
                  />
                  <span>列显示</span>
                </label>
                <button type="button" class="host-column-reset" @click="resetHostColumns">重置</button>
              </div>
              <div class="host-column-options">
                <label v-for="column in hostColumnOptions" :key="column.key" class="host-column-option">
                  <input
                    type="checkbox"
                    :checked="hostColumnVisibility[column.key]"
                    :disabled="isOnlyVisibleHostColumn(column.key)"
                    @change="updateHostColumnVisibility(column.key, $event)"
                  />
                  <span>{{ column.label }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="host-stats-line">
        <span>共 {{ managedHostStats.total }} 台主机</span>
        <span>已验证 {{ managedHostStats.verified }}</span>
        <span>未验证 {{ managedHostStats.unverified }}</span>
        <span v-if="isLoadingHosts">加载中</span>
      </div>
      <div class="host-table-scroll">
        <div class="host-table" :style="hostTableStyle">
          <div class="host-table-row head">
            <label class="host-select-cell" aria-label="选择所有可见主机">
              <input
                type="checkbox"
                :checked="allVisibleHostsSelected"
                :disabled="!visibleHostIds.length"
                :indeterminate.prop="someVisibleHostsSelected && !allVisibleHostsSelected"
                @change="toggleAllVisibleHosts"
              />
            </label>
          <span v-if="isHostColumnVisible('group')">主机分组</span>
          <button v-if="isHostColumnVisible('name')" class="host-sort-button" :class="{ active: hostSortKey === 'name', desc: hostSortKey === 'name' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('name')">
            节点 <em>{{ hostSortMark('name') }}</em>
          </button>
          <button v-if="isHostColumnVisible('ip')" class="host-sort-button" :class="{ active: hostSortKey === 'ip', desc: hostSortKey === 'ip' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('ip')">
            IP地址 <em>{{ hostSortMark('ip') }}</em>
          </button>
          <span v-if="isHostColumnVisible('config')">配置信息</span>
          <span v-if="isHostColumnVisible('machine')">机器名称</span>
          <button v-if="isHostColumnVisible('platformType')" class="host-sort-button" :class="{ active: hostSortKey === 'platformType', desc: hostSortKey === 'platformType' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('platformType')">
            平台类型 <em>{{ hostSortMark('platformType') }}</em>
          </button>
          <span v-if="isHostColumnVisible('user')">用户</span>
          <span v-if="isHostColumnVisible('port')">端口</span>
          <button v-if="isHostColumnVisible('createdAt')" class="host-sort-button" :class="{ active: hostSortKey === 'createdAt', desc: hostSortKey === 'createdAt' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('createdAt')">
            创建时间 <em>{{ hostSortMark('createdAt') }}</em>
          </button>
          <button v-if="isHostColumnVisible('updatedAt')" class="host-sort-button" :class="{ active: hostSortKey === 'updatedAt', desc: hostSortKey === 'updatedAt' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('updatedAt')">
            更新时间 <em>{{ hostSortMark('updatedAt') }}</em>
          </button>
          <button v-if="isHostColumnVisible('creator')" class="host-sort-button" :class="{ active: hostSortKey === 'creator', desc: hostSortKey === 'creator' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('creator')">
            创建者 <em>{{ hostSortMark('creator') }}</em>
          </button>
          <span v-if="isHostColumnVisible('remark')">备注</span>
          <span v-if="isHostColumnVisible('status')" class="host-sticky-cell host-status-cell">状态</span>
          <span v-if="isHostColumnVisible('actions')" class="host-sticky-cell host-actions-cell">操作</span>
        </div>
        <div v-for="host in visibleManagedHosts" :key="host.id" class="host-table-row">
          <label class="host-select-cell" :aria-label="`选择主机 ${host.name}`">
            <input
              type="checkbox"
              :checked="selectedHostIds.has(host.id)"
              @change="toggleHostSelected(host.id, $event)"
            />
          </label>
          <span v-if="isHostColumnVisible('group')" class="host-group-cell">{{ hostGroupName(host.group) }}</span>
          <button v-if="isHostColumnVisible('name')" class="host-name-link" type="button" @click="openWebTerminal(host)">{{ host.name }}</button>
          <div v-if="isHostColumnVisible('ip')" class="host-ip-stack">
            <span v-if="host.publicIp"><i class="ip-tag public">公</i>{{ host.publicIp }}</span>
            <span>{{ host.privateIp }}</span>
          </div>
          <div v-if="isHostColumnVisible('config')" class="host-config">
            <template v-if="host.verified && host.cpu > 0 && host.memory > 0">
              <span class="os-badge" :class="host.os"></span>
              <strong>{{ host.cpu }}核 {{ host.memory }}GB</strong>
            </template>
            <span v-else class="host-config-empty" aria-label="配置信息为空"></span>
          </div>
          <span v-if="isHostColumnVisible('machine')" class="host-machine-cell" :title="host.machineName">{{ host.verified ? host.machineName : '' }}</span>
          <span v-if="isHostColumnVisible('platformType')" class="host-platform-type" :class="hostPlatformType(host.platformType)">
            {{ hostPlatformType(host.platformType) }}
          </span>
          <span v-if="isHostColumnVisible('user')" class="host-user-cell">{{ host.loginUser || '-' }}</span>
          <span v-if="isHostColumnVisible('port')" class="host-port-cell">{{ host.port || 22 }}</span>
          <span v-if="isHostColumnVisible('createdAt')" class="host-date-cell">{{ formatHostDate(host.createdAt) }}</span>
          <span v-if="isHostColumnVisible('updatedAt')" class="host-date-cell">{{ formatHostDate(host.updatedAt) }}</span>
          <span v-if="isHostColumnVisible('creator')" class="host-creator-cell">{{ host.creator || '-' }}</span>
          <span v-if="isHostColumnVisible('remark')" class="host-remark-cell" :title="host.remark">{{ host.remark || '-' }}</span>
          <div v-if="isHostColumnVisible('status')" class="host-sticky-cell host-status-cell">
            <span class="verify-badge" :class="{ verified: host.verified, failed: host.verifyStatus === 'failed' }">
              {{ host.verified ? '已验证' : host.verifyStatus === 'failed' ? '验证失败' : '未验证' }}
            </span>
          </div>
          <div v-if="isHostColumnVisible('actions')" class="host-actions host-sticky-cell host-actions-cell">
            <button type="button" @click="editManagedHost(host)">编辑</button>
            <button type="button" :disabled="verifyingHostIds.has(host.id)" @click="verifyManagedHost(host)">
              {{ verifyingHostIds.has(host.id) ? '验证中' : '验证' }}
            </button>
            <button class="danger" type="button" @click="deleteManagedHost(host)">删除</button>
          </div>
        </div>
          <div v-if="!visibleManagedHosts.length" class="empty-state host-empty">没有匹配的主机。</div>
        </div>
      </div>
    </article>

    <div v-if="hostDialog" class="modal-backdrop" @click.self="hostDialog = null">
      <form class="host-form-modal host-edit-modal host-horizontal-modal" @submit.prevent="saveManagedHost">
        <button class="modal-close" type="button" @click="hostDialog = null"><AppIcon name="x" :size="16" /></button>
        <h2>{{ hostDialog.mode === 'edit' ? '编辑主机' : '新增主机' }}</h2>
        <label class="host-horizontal-field required">
          <span>主机分组：</span>
          <select v-model.number="hostForm.group">
            <option disabled :value="null">{{ hostGroupRoot.label }}</option>
            <option v-for="group in flatHostGroups" :key="group.key" :value="group.key">{{ `${'　'.repeat(group.level)}${group.label}` }}</option>
          </select>
        </label>
        <label class="host-horizontal-field required">
          <span>节点：</span>
          <input v-model="hostForm.name" autofocus />
        </label>
        <label class="host-horizontal-field required">
          <span>主机 IP：</span>
          <input v-model="hostForm.privateIp" />
          <small v-if="hostPrivateIpExists" class="host-field-error">IP 已存在，请重新输入。</small>
        </label>
        <label class="host-horizontal-field required">
          <span>平台类型：</span>
          <select v-model="hostForm.os">
            <option value="centos">linux</option>
            <option value="windows">windows</option>
          </select>
        </label>
        <label class="host-horizontal-field">
          <span>端口：</span>
          <input v-model.number="hostForm.port" min="1" max="65535" type="number" />
        </label>
        <label class="host-horizontal-field">
          <span>账号：</span>
          <select v-model.number="hostForm.credential" @change="applyCredentialToHostForm">
            <option :value="null">手动输入</option>
            <option v-for="credential in hostCredentials" :key="credential.id" :value="credential.id">
              {{ credential.name }}（{{ credential.username }}）
            </option>
          </select>
        </label>
        <label class="host-horizontal-field">
          <span>用户：</span>
          <input v-model="hostForm.loginUser" />
        </label>
        <label class="host-horizontal-field">
          <span>密码：</span>
          <input v-model="hostForm.loginPassword" type="password" autocomplete="new-password" />
        </label>
        <div class="host-horizontal-field">
          <span>独立密钥：</span>
          <div class="host-key-upload">
            <label class="host-key-button">
              <input type="file" @change="uploadHostPrivateKey" />
              点击上传
            </label>
            <em>{{ hostForm.privateKeyName || '默认使用全局密钥，如果上传了独立密钥（私钥）则优先使用该密钥。' }}</em>
          </div>
        </div>
        <label class="host-horizontal-field">
          <span>备注信息：</span>
          <textarea v-model="hostForm.remark" rows="3"></textarea>
        </label>
        <div class="host-form-actions">
          <button type="button" @click="hostDialog = null">取消</button>
          <button class="primary" type="submit">保存</button>
        </div>
      </form>
    </div>

    <div v-if="hostMoveDialogOpen" class="modal-backdrop" @click.self="hostMoveDialogOpen = false">
      <form class="host-form-modal" @submit.prevent="saveMoveManagedHost">
        <button class="modal-close" type="button" @click="hostMoveDialogOpen = false"><AppIcon name="x" :size="16" /></button>
        <h2>移动主机</h2>
        <label>
          <span>选择主机</span>
          <select v-model.number="hostMoveForm.hostId">
            <option v-for="host in groupMoveHosts" :key="host.id" :value="host.id">{{ host.name }} · {{ host.privateIp }}</option>
          </select>
        </label>
        <label>
          <span>目标分组</span>
          <select v-model.number="hostMoveForm.targetGroup">
            <option disabled :value="null">{{ hostGroupRoot.label }}</option>
            <option v-for="group in flatHostGroups" :key="group.key" :value="group.key">{{ `${'　'.repeat(group.level)}${group.label}` }}</option>
          </select>
        </label>
        <div class="host-form-actions">
          <button type="button" @click="hostMoveDialogOpen = false">取消</button>
          <button class="primary" type="submit">移动</button>
        </div>
      </form>
    </div>
  </section>
</template>
