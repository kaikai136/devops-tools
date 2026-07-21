<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';
import type { ManagedHost } from '@features/hosts/types';
import type { HostSortKey, SortDirection } from '@features/hosts/utils/groups';
import type { HostColumnKey } from './HostToolbar.vue';

const props = defineProps<{
  hosts: ManagedHost[];
  visibleHostCount: number;
  selectedIds: Set<number>;
  visibleIds: number[];
  allVisibleSelected: boolean;
  someVisibleSelected: boolean;
  tableStyle: Record<string, string>;
  sortKey: HostSortKey;
  sortDirection: SortDirection;
  page: number;
  pageSize: number;
  totalPages: number;
  pageNumbers: number[];
  pageStart: number;
  pageEnd: number;
  selectedCount: number;
  selectedVerifyingCount: number;
  stats: { total: number; verified: number; unverified: number };
  loading: boolean;
  verifyingIds: Set<number>;
  canOpenTerminal: boolean;
  canEdit: boolean;
  canVerify: boolean;
  canMove: boolean;
  canDelete: boolean;
  canUseRowActions: boolean;
  isColumnVisible: (key: HostColumnKey) => boolean;
  groupName: (groupId: number) => string;
  sortMark: (key: HostSortKey) => string;
  formatDate: (value: string | null | undefined) => string;
  platformType: (value: string | null | undefined) => string;
}>();

const emit = defineEmits<{
  'toggle-all-visible': [event: Event];
  'toggle-host': [hostId: number, event: Event];
  sort: [key: HostSortKey];
  'open-terminal': [host: ManagedHost];
  edit: [host: ManagedHost];
  verify: [host: ManagedHost];
  delete: [host: ManagedHost];
  'page-change': [page: number];
  'page-size-change': [pageSize: number];
  'clear-selection': [];
  'verify-selected': [];
  'move-selected': [];
  'delete-selected': [];
}>();

function updatePageSize(event: Event) {
  emit('page-size-change', Number((event.target as HTMLSelectElement).value));
}
</script>

<template>
  <div class="host-table-scroll">
    <div class="host-table" :style="props.tableStyle">
      <div class="host-table-row head">
        <label class="host-select-cell" aria-label="选择所有可见主机">
          <input
            type="checkbox"
            :checked="props.allVisibleSelected"
            :disabled="!props.visibleIds.length"
            :indeterminate.prop="props.someVisibleSelected && !props.allVisibleSelected"
            @change="emit('toggle-all-visible', $event)"
          />
        </label>
        <span v-if="props.isColumnVisible('group')">主机分组</span>
        <button v-if="props.isColumnVisible('name')" class="host-sort-button" :class="{ active: props.sortKey === 'name', desc: props.sortKey === 'name' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'name')">
          节点 <em>{{ props.sortMark('name') }}</em>
        </button>
        <button v-if="props.isColumnVisible('ip')" class="host-sort-button" :class="{ active: props.sortKey === 'ip', desc: props.sortKey === 'ip' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'ip')">
          IP地址 <em>{{ props.sortMark('ip') }}</em>
        </button>
        <span v-if="props.isColumnVisible('machine')">机器名称</span>
        <button v-if="props.isColumnVisible('systemArch')" class="host-sort-button" :class="{ active: props.sortKey === 'systemArch', desc: props.sortKey === 'systemArch' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'systemArch')">
          系统架构 <em>{{ props.sortMark('systemArch') }}</em>
        </button>
        <button v-if="props.isColumnVisible('systemType')" class="host-sort-button" :class="{ active: props.sortKey === 'systemType', desc: props.sortKey === 'systemType' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'systemType')">
          系统类型 <em>{{ props.sortMark('systemType') }}</em>
        </button>
        <span v-if="props.isColumnVisible('config')">配置信息</span>
        <button v-if="props.isColumnVisible('platformType')" class="host-sort-button" :class="{ active: props.sortKey === 'platformType', desc: props.sortKey === 'platformType' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'platformType')">
          平台类型 <em>{{ props.sortMark('platformType') }}</em>
        </button>
        <span v-if="props.isColumnVisible('user')">用户</span>
        <span v-if="props.isColumnVisible('port')">端口</span>
        <button v-if="props.isColumnVisible('createdAt')" class="host-sort-button" :class="{ active: props.sortKey === 'createdAt', desc: props.sortKey === 'createdAt' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'createdAt')">
          创建时间 <em>{{ props.sortMark('createdAt') }}</em>
        </button>
        <button v-if="props.isColumnVisible('updatedAt')" class="host-sort-button" :class="{ active: props.sortKey === 'updatedAt', desc: props.sortKey === 'updatedAt' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'updatedAt')">
          更新时间 <em>{{ props.sortMark('updatedAt') }}</em>
        </button>
        <button v-if="props.isColumnVisible('creator')" class="host-sort-button" :class="{ active: props.sortKey === 'creator', desc: props.sortKey === 'creator' && props.sortDirection === 'desc' }" type="button" @click="emit('sort', 'creator')">
          创建者 <em>{{ props.sortMark('creator') }}</em>
        </button>
        <span v-if="props.isColumnVisible('remark')">备注</span>
        <span v-if="props.isColumnVisible('status')" class="host-sticky-cell host-status-cell">状态</span>
        <span v-if="props.isColumnVisible('actions')" class="host-sticky-cell host-actions-cell">操作</span>
      </div>
      <div v-for="host in props.hosts" :key="host.id" class="host-table-row">
        <label class="host-select-cell" :aria-label="`选择主机 ${host.name}`">
          <input
            type="checkbox"
            :checked="props.selectedIds.has(host.id)"
            @change="emit('toggle-host', host.id, $event)"
          />
        </label>
        <span v-if="props.isColumnVisible('group')" class="host-group-cell">{{ props.groupName(host.group) }}</span>
        <button v-if="props.isColumnVisible('name') && props.canOpenTerminal" class="host-name-link" type="button" @click="emit('open-terminal', host)">{{ host.name }}</button>
        <span v-else-if="props.isColumnVisible('name')" class="host-name-text">{{ host.name }}</span>
        <div v-if="props.isColumnVisible('ip')" class="host-ip-stack">
          <span v-if="host.publicIp"><i class="ip-tag public">公</i>{{ host.publicIp }}</span>
          <span>{{ host.privateIp }}</span>
        </div>
        <span v-if="props.isColumnVisible('machine')" class="host-machine-cell" :title="host.machineName">{{ host.verified ? host.machineName : '' }}</span>
        <span v-if="props.isColumnVisible('systemArch')" class="host-system-cell">{{ host.systemArch || '-' }}</span>
        <span v-if="props.isColumnVisible('systemType')" class="host-system-cell">{{ host.systemType || '-' }}</span>
        <div v-if="props.isColumnVisible('config')" class="host-config">
          <template v-if="host.verified && host.cpu > 0 && host.memory > 0">
            <span class="os-badge" :class="host.os"></span>
            <strong>{{ host.cpu }}核 {{ host.memory }}GB</strong>
          </template>
          <span v-else class="host-config-empty" aria-label="配置信息为空"></span>
        </div>
        <span v-if="props.isColumnVisible('platformType')" class="host-platform-type" :class="props.platformType(host.platformType)">
          {{ props.platformType(host.platformType) }}
        </span>
        <span v-if="props.isColumnVisible('user')" class="host-user-cell">{{ host.loginUser || '-' }}</span>
        <span v-if="props.isColumnVisible('port')" class="host-port-cell">{{ host.port || 22 }}</span>
        <span v-if="props.isColumnVisible('createdAt')" class="host-date-cell">{{ props.formatDate(host.createdAt) }}</span>
        <span v-if="props.isColumnVisible('updatedAt')" class="host-date-cell">{{ props.formatDate(host.updatedAt) }}</span>
        <span v-if="props.isColumnVisible('creator')" class="host-creator-cell">{{ host.creator || '-' }}</span>
        <span v-if="props.isColumnVisible('remark')" class="host-remark-cell" :title="host.remark">{{ host.remark || '-' }}</span>
        <div v-if="props.isColumnVisible('status')" class="host-sticky-cell host-status-cell">
          <span class="verify-badge" :class="{ verified: host.verified, failed: host.verifyStatus === 'failed' }">
            {{ host.verified ? '已验证' : host.verifyStatus === 'failed' ? '验证失败' : '未验证' }}
          </span>
        </div>
        <div v-if="props.isColumnVisible('actions')" class="host-actions host-sticky-cell host-actions-cell">
          <button v-if="props.canEdit" type="button" @click="emit('edit', host)">编辑</button>
          <button v-if="props.canVerify" type="button" :disabled="props.verifyingIds.has(host.id)" @click="emit('verify', host)">
            {{ props.verifyingIds.has(host.id) ? '验证中' : '验证' }}
          </button>
          <button v-if="props.canDelete" class="danger" type="button" @click="emit('delete', host)">删除</button>
          <span v-if="!props.canUseRowActions" class="host-action-placeholder">-</span>
        </div>
      </div>
      <div v-if="!props.visibleHostCount" class="empty-state host-empty">没有匹配的主机。</div>
    </div>
  </div>
  <div class="host-pagination" aria-label="主机列表分页">
    <div class="host-pagination-summary">
      <span>共 {{ props.visibleHostCount }} 条</span>
      <span>{{ props.pageStart }}-{{ props.pageEnd }}</span>
    </div>
    <div class="host-pagination-controls">
      <button class="prev" type="button" :disabled="props.page <= 1" aria-label="上一页" @click="emit('page-change', props.page - 1)">
        <AppIcon name="chevronRight" :size="14" />
      </button>
      <button
        v-for="pageNumber in props.pageNumbers"
        :key="pageNumber"
        type="button"
        :class="{ active: pageNumber === props.page }"
        @click="emit('page-change', pageNumber)"
      >
        {{ pageNumber }}
      </button>
      <button type="button" :disabled="props.page >= props.totalPages" aria-label="下一页" @click="emit('page-change', props.page + 1)">
        <AppIcon name="chevronRight" :size="14" />
      </button>
      <select :value="props.pageSize" aria-label="每页条数" @change="updatePageSize">
        <option :value="10">10 条/页</option>
        <option :value="20">20 条/页</option>
        <option :value="50">50 条/页</option>
      </select>
    </div>
    <div class="host-stats-line">
      <span>共 {{ props.stats.total }} 台主机</span>
      <span>已验证 {{ props.stats.verified }}</span>
      <span>未验证 {{ props.stats.unverified }}</span>
      <span v-if="props.loading">加载中</span>
    </div>
  </div>

  <div v-if="props.selectedCount" class="host-bulk-action-bar" @click.stop>
    <div class="host-bulk-action-info">
      <span class="host-bulk-action-icon"><AppIcon name="info" :size="16" /></span>
      <div class="host-bulk-action-copy">
        <strong>批量操作</strong>
        <span class="host-bulk-action-count">已选择 {{ props.selectedCount }} 个主机</span>
      </div>
    </div>
    <div class="host-bulk-action-buttons">
      <button class="host-bulk-button host-bulk-button-cancel" type="button" @click="emit('clear-selection')">取消选中</button>
      <button
        v-if="props.canVerify"
        class="host-bulk-button host-bulk-button-verify"
        type="button"
        :disabled="props.selectedVerifyingCount > 0"
        @click="emit('verify-selected')"
      >
        {{ props.selectedVerifyingCount > 0 ? '验证中' : '验证所选' }}
      </button>
      <button v-if="props.canMove" class="host-bulk-button host-bulk-button-update" type="button" @click="emit('move-selected')">更新所选</button>
      <button v-if="props.canDelete" class="host-bulk-button host-bulk-button-delete" type="button" @click="emit('delete-selected')">删除所选</button>
    </div>
  </div>
</template>
