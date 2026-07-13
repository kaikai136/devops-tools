<script setup lang="ts">
import { computed } from 'vue';

import AppIcon from '@shared/components/AppIcon.vue';
import type { HostGroup } from '@features/hosts/types';
import type {
  HostGroupDropPosition,
  HostGroupInlineEdit,
  HostGroupMenuGroup,
  HostGroupRoot,
  HostGroupRow,
} from '@features/hosts/composables/useHostGroups';
import type { FlatHostGroup } from '@features/hosts/utils/groups';

const props = defineProps<{
  groups: HostGroup[];
  root: HostGroupRoot;
  rows: HostGroupRow[];
  rootExpanded: boolean;
  selectedGroup: number | null;
  inlineEdit: HostGroupInlineEdit | null;
  menu: { group: HostGroupMenuGroup; x: number; y: number } | null;
  draggedGroupId: number | null;
  dropTarget: { key: number; position: HostGroupDropPosition } | null;
  canManageGroups: boolean;
  canCreateHosts: boolean;
  canMoveHosts: boolean;
  canDeleteHosts: boolean;
  showGroupActionDivider: boolean;
  isGroupExpanded: (group: FlatHostGroup) => boolean;
}>();

const emit = defineEmits<{
  'add-root': [group?: HostGroupMenuGroup];
  'select-group': [groupId: number | null];
  'toggle-root': [];
  'toggle-group': [group: FlatHostGroup];
  'open-menu': [group: HostGroupMenuGroup, event: MouseEvent];
  'update-inline-name': [value: string];
  'save-inline-edit': [];
  'cancel-inline-edit': [];
  'drag-start': [group: FlatHostGroup, event: DragEvent];
  'drag-over': [group: FlatHostGroup, event: DragEvent];
  'drag-leave': [];
  drop: [group: FlatHostGroup, event: DragEvent];
  'drag-end': [];
  'add-child': [groupId: number];
  rename: [group: HostGroupMenuGroup];
  'add-host': [groupId?: number | null];
  'move-host': [group: HostGroupMenuGroup];
  'delete-hosts': [group: HostGroupMenuGroup];
  'delete-group': [group: HostGroupMenuGroup];
}>();

const inlineName = computed({
  get: () => props.inlineEdit?.name ?? '',
  set: (value: string) => emit('update-inline-name', value),
});
</script>

<template>
  <article class="panel host-groups-panel">
    <div class="host-group-head">
      <h2>分组列表</h2>
      <button v-if="props.canManageGroups" class="group-add-button" type="button" title="添加分组" aria-label="添加分组" @click.stop="emit('add-root')"><AppIcon name="plus" :size="16" /></button>
    </div>
    <div class="host-group-list">
      <template v-for="row in props.rows" :key="row.kind === 'root' ? 'group-root' : row.kind === 'group' ? `group-${row.group.key}` : `editor-${row.editor.mode}-${row.editor.after ?? 'end'}`">
        <button
          v-if="row.kind === 'root'"
          class="host-group-row host-group-root"
          :class="{ active: props.selectedGroup === null }"
          type="button"
          @click.stop="emit('select-group', null)"
          @dblclick.stop="emit('toggle-root')"
          @contextmenu="emit('open-menu', row.group, $event)"
        >
          <span class="folder-caret expandable" role="button" @click.stop="emit('toggle-root')">
            <AppIcon :name="props.rootExpanded ? 'chevronDown' : 'chevronRight'" :size="15" />
          </span>
          <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
          <strong>{{ row.group.label }}</strong>
          <em>{{ row.group.count }}</em>
        </button>
        <template v-else-if="row.kind === 'group'">
          <div
            v-if="props.inlineEdit?.mode === 'rename' && props.inlineEdit.groupId === row.group.key"
            class="host-group-row editing"
            :style="{ paddingLeft: `${10 + row.group.level * 26}px` }"
            @click.stop
          >
            <span
              class="folder-caret"
              :class="{ expandable: row.group.children?.length }"
              role="button"
              @click.stop="emit('toggle-group', row.group)"
            ><AppIcon v-if="row.group.children?.length" :name="props.isGroupExpanded(row.group) ? 'chevronDown' : 'chevronRight'" :size="15" /></span>
            <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
            <input
              v-model="inlineName"
              class="host-group-inline-input"
              autofocus
              @blur="emit('save-inline-edit')"
              @keydown.enter.prevent="emit('save-inline-edit')"
              @keydown.esc.prevent="emit('cancel-inline-edit')"
            />
            <em>{{ row.group.count }}</em>
          </div>
          <button
            v-else
            class="host-group-row"
            :class="{
              active: props.selectedGroup === row.group.key,
              dragging: props.draggedGroupId === row.group.key,
              'drop-before': props.dropTarget?.key === row.group.key && props.dropTarget.position === 'before',
              'drop-inside': props.dropTarget?.key === row.group.key && props.dropTarget.position === 'inside',
              'drop-after': props.dropTarget?.key === row.group.key && props.dropTarget.position === 'after',
            }"
            :style="{ paddingLeft: `${10 + row.group.level * 26}px` }"
            type="button"
            draggable="true"
            @click.stop="emit('select-group', row.group.key)"
            @dblclick.stop="emit('toggle-group', row.group)"
            @contextmenu="emit('open-menu', row.group, $event)"
            @dragstart="emit('drag-start', row.group, $event)"
            @dragover="emit('drag-over', row.group, $event)"
            @dragleave="emit('drag-leave')"
            @drop="emit('drop', row.group, $event)"
            @dragend="emit('drag-end')"
          >
            <span
              class="folder-caret"
              :class="{ expandable: row.group.children?.length }"
              role="button"
              @click.stop="emit('toggle-group', row.group)"
            ><AppIcon v-if="row.group.children?.length" :name="props.isGroupExpanded(row.group) ? 'chevronDown' : 'chevronRight'" :size="15" /></span>
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
            v-model="inlineName"
            class="host-group-inline-input"
            autofocus
            placeholder="输入分组名称"
            @blur="emit('save-inline-edit')"
            @keydown.enter.prevent="emit('save-inline-edit')"
            @keydown.esc.prevent="emit('cancel-inline-edit')"
          />
          <em>{{ row.editor.mode === 'rename-root' ? props.root.count : 0 }}</em>
        </div>
      </template>
      <div v-if="!props.groups.length && !props.inlineEdit" class="empty-state host-empty">暂无分组。</div>
    </div>

    <div
      v-if="props.menu"
      class="host-group-menu"
      :style="{ left: `${props.menu.x}px`, top: `${props.menu.y}px` }"
      @click.stop
    >
      <button v-if="props.canManageGroups" type="button" @click="emit('add-root', props.menu.group)"><span><AppIcon name="folderPlus" :size="15" /></span>新建分组</button>
      <button v-if="props.canManageGroups" type="button" @click="emit('add-child', props.menu.group.key as number)"><span><AppIcon name="circlePlus" :size="15" /></span>新建子分组</button>
      <button v-if="props.canManageGroups" type="button" @click="emit('rename', props.menu.group)"><span><AppIcon name="edit" :size="15" /></span>重命名</button>
      <hr v-if="props.canManageGroups && props.showGroupActionDivider" />
      <button v-if="props.canCreateHosts" type="button" @click="emit('add-host', props.menu.group.key ?? undefined)"><span><AppIcon name="server" :size="15" /></span>添加主机</button>
      <button v-if="props.canMoveHosts" type="button" @click="emit('move-host', props.menu.group)"><span><AppIcon name="upload" :size="15" /></span>移动主机</button>
      <button v-if="props.canDeleteHosts" class="danger" type="button" @click="emit('delete-hosts', props.menu.group)"><span><AppIcon name="trash" :size="15" /></span>删除主机</button>
      <hr v-if="props.canManageGroups" />
      <button v-if="props.canManageGroups" class="danger" type="button" @click="emit('delete-group', props.menu.group)"><span><AppIcon name="trash" :size="15" /></span>删除此分组</button>
    </div>
  </article>
</template>
