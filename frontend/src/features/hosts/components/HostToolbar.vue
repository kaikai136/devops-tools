<script setup lang="ts">
import { computed } from 'vue';

import AppIcon from '@shared/components/AppIcon.vue';
import type { HostStatusFilter } from '@features/hosts/composables/useHostList';

export type HostColumnKey =
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
  | 'status'
  | 'actions';

export interface HostColumnOption {
  key: HostColumnKey;
  label: string;
  width: string;
  minWidth: number;
}

const props = defineProps<{
  search: string;
  statusFilter: HostStatusFilter;
  selectedCount: number;
  selectedVerifyingCount: number;
  moreActionsOpen: boolean;
  columnSettingsOpen: boolean;
  fullscreen: boolean;
  columns: readonly HostColumnOption[];
  columnVisibility: Record<HostColumnKey, boolean>;
  allColumnsVisible: boolean;
  someColumnsVisible: boolean;
  isOnlyVisibleColumn: (key: HostColumnKey) => boolean;
  canCreate: boolean;
  canManageQuickCommands: boolean;
  canUseMoreActions: boolean;
  canVerify: boolean;
  canFilter: boolean;
  canMove: boolean;
  canDelete: boolean;
  canBulkExecute: boolean;
  showMoreActionsDivider: boolean;
  canImport: boolean;
  canExport: boolean;
}>();

const emit = defineEmits<{
  'update:search': [value: string];
  create: [];
  'open-quick-commands': [];
  'toggle-more-actions': [];
  'status-filter': [filter: 'all' | 'unverified'];
  'verify-selected': [];
  'bulk-execute-selected': [];
  'move-selected': [];
  'delete-selected': [];
  import: [];
  export: [];
  refresh: [];
  'toggle-column-settings': [];
  'toggle-all-columns': [event: Event];
  'reset-columns': [];
  'update-column': [key: HostColumnKey, event: Event];
  'toggle-fullscreen': [];
}>();

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value),
});
</script>

<template>
  <div class="host-toolbar">
    <input v-model="searchModel" placeholder="输入别名/IP检索" />
    <div class="host-toolbar-actions">
      <button v-if="props.canCreate" class="primary" type="button" @click="emit('create')"><AppIcon name="plus" :size="16" />新建</button>
      <button v-if="props.canManageQuickCommands" class="host-quick-command-trigger" type="button" @click="emit('open-quick-commands')">
        <AppIcon name="zap" :size="16" />
        快捷命令
      </button>
      <div v-if="props.canUseMoreActions" class="host-more-actions" @click.stop>
        <button
          class="more-action-trigger"
          type="button"
          :aria-expanded="props.moreActionsOpen"
          @click="emit('toggle-more-actions')"
        >
          更多操作
          <AppIcon name="chevronDown" :size="14" />
        </button>
        <div v-if="props.moreActionsOpen" class="host-more-menu">
          <button v-if="props.canVerify" type="button" :disabled="!props.selectedCount || props.selectedVerifyingCount > 0" @click="emit('verify-selected')">
            <AppIcon name="shield" :size="15" />
            <span>{{ props.selectedVerifyingCount > 0 ? '验证中' : '验证所选' }}</span>
          </button>
          <button v-if="props.canBulkExecute" type="button" :disabled="!props.selectedCount" @click="emit('bulk-execute-selected')">
            <AppIcon name="terminal" :size="15" />
            <span>批量执行</span>
          </button>
          <button v-if="props.canFilter" type="button" :class="{ active: props.statusFilter === 'all' }" @click="emit('status-filter', 'all')">
            <AppIcon name="search" :size="15" />
            <span>查询全部</span>
          </button>
          <button v-if="props.canFilter" type="button" :class="{ active: props.statusFilter === 'unverified' }" @click="emit('status-filter', 'unverified')">
            <AppIcon name="circleHelp" :size="15" />
            <span>查未验证</span>
          </button>
          <hr v-if="props.showMoreActionsDivider" />
          <button v-if="props.canMove" type="button" :disabled="!props.selectedCount" @click="emit('move-selected')">
            <AppIcon name="upload" :size="15" />
            <span>更新所选</span>
          </button>
          <button v-if="props.canDelete" class="danger" type="button" :disabled="!props.selectedCount" @click="emit('delete-selected')">
            <AppIcon name="trash" :size="15" />
            <span>删除所选</span>
          </button>
        </div>
      </div>
      <button v-if="props.canImport" class="icon-only" type="button" title="导入" aria-label="导入" @click="emit('import')"><AppIcon name="upload" :size="16" /></button>
      <button v-if="props.canExport" class="icon-only" type="button" title="导出" aria-label="导出" @click="emit('export')"><AppIcon name="download" :size="16" /></button>
      <button class="icon-only" type="button" title="刷新" aria-label="刷新" @click="emit('refresh')"><AppIcon name="refresh" :size="16" /></button>
      <div class="host-column-settings" @click.stop>
        <button
          class="icon-only"
          type="button"
          title="列设置"
          aria-label="列设置"
          :aria-expanded="props.columnSettingsOpen"
          @click="emit('toggle-column-settings')"
        >
          <AppIcon name="settings" :size="16" />
        </button>
        <div v-if="props.columnSettingsOpen" class="host-column-menu">
          <div class="host-column-menu-head">
            <label class="host-column-all">
              <input
                type="checkbox"
                :checked="props.allColumnsVisible"
                :indeterminate.prop="props.someColumnsVisible && !props.allColumnsVisible"
                @change="emit('toggle-all-columns', $event)"
              />
              <span>列显示</span>
            </label>
            <button type="button" class="host-column-reset" @click="emit('reset-columns')">重置</button>
          </div>
          <div class="host-column-options">
            <label v-for="column in props.columns" :key="column.key" class="host-column-option">
              <input
                type="checkbox"
                :checked="props.columnVisibility[column.key]"
                :disabled="props.isOnlyVisibleColumn(column.key)"
                @change="emit('update-column', column.key, $event)"
              />
              <span>{{ column.label }}</span>
            </label>
          </div>
        </div>
      </div>
      <button class="icon-only" type="button" :title="props.fullscreen ? '退出全屏' : '全屏'" :aria-label="props.fullscreen ? '退出全屏' : '全屏'" @click.stop="emit('toggle-fullscreen')">
        <AppIcon :name="props.fullscreen ? 'minimize' : 'maximize'" :size="18" />
      </button>
    </div>
  </div>
</template>
