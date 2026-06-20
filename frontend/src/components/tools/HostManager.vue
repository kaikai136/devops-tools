<script setup lang="ts">
import { useAppContext } from '../../appContext';
import AppIcon from '../common/AppIcon.vue';

const {
  activeTool,
  hostGroups,
  flatHostGroups,
  hostGroupRows,
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
</script>

<template>
  <section v-if="activeTool === 'hosts'" class="host-manager-page" @click="closeHostGroupMenu">
    <article class="panel host-groups-panel">
      <div class="host-group-head">
        <h2>分组列表</h2>
        <button class="group-add-button" type="button" title="添加分组" aria-label="添加分组" @click.stop="openAddRootHostGroup()"><AppIcon name="plus" :size="16" /></button>
      </div>
      <div class="host-group-list">
        <template v-for="row in hostGroupRows" :key="row.kind === 'group' ? `group-${row.group.key}` : `editor-${row.editor.mode}-${row.editor.after ?? 'end'}`">
          <template v-if="row.kind === 'group'">
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
            class="host-group-row editing draft"
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
            <em>0</em>
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
        <button type="button" @click="openAddRootHostGroup(hostGroupMenu.group)"><span><AppIcon name="folderPlus" :size="15" /></span>新建根分组</button>
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
        <input v-model="hostSearch" placeholder="输入名称/IP检索" />
        <div class="host-toolbar-actions">
          <button class="primary" type="button" @click="addManagedHost()"><AppIcon name="plus" :size="16" />新建</button>
          <button class="primary secondary-blue" type="button" @click="verifyVisibleManagedHosts">验证</button>
          <div class="status-tabs">
            <button :class="{ active: hostStatusFilter === 'all' }" type="button" @click="hostStatusFilter = 'all'">全部</button>
            <button :class="{ active: hostStatusFilter === 'unverified' }" type="button" @click="hostStatusFilter = 'unverified'">未验证</button>
          </div>
          <button class="icon-only" type="button" title="刷新" aria-label="刷新" @click="loadHostManagement"><AppIcon name="refresh" :size="16" /></button>
        </div>
      </div>
      <div class="host-stats-line">
        <span>共 {{ managedHostStats.total }} 台主机</span>
        <span>已验证 {{ managedHostStats.verified }}</span>
        <span>未验证 {{ managedHostStats.unverified }}</span>
        <span v-if="isLoadingHosts">加载中</span>
      </div>
      <div class="host-table">
        <div class="host-table-row head">
          <span>主机分组</span>
          <button class="host-sort-button" :class="{ active: hostSortKey === 'name', desc: hostSortKey === 'name' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('name')">
            主机名称 <em>{{ hostSortMark('name') }}</em>
          </button>
          <button class="host-sort-button" :class="{ active: hostSortKey === 'ip', desc: hostSortKey === 'ip' && hostSortDirection === 'desc' }" type="button" @click="setHostSort('ip')">
            IP地址 <em>{{ hostSortMark('ip') }}</em>
          </button>
          <span>机器名称</span>
          <span>用户</span>
          <span>端口</span>
          <span>配置信息</span>
          <span>备注</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        <div v-for="host in visibleManagedHosts" :key="host.id" class="host-table-row">
          <span class="host-group-cell">{{ hostGroupName(host.group) }}</span>
          <button class="host-name-link" type="button" @click="openWebTerminal(host)">{{ host.name }}</button>
          <div class="host-ip-stack">
            <span v-if="host.publicIp"><i class="ip-tag public">公</i>{{ host.publicIp }}</span>
            <span><i class="ip-tag private">内</i>{{ host.privateIp }}</span>
          </div>
          <span class="host-machine-cell" :title="host.machineName">{{ host.verified ? host.machineName : '' }}</span>
          <span class="host-user-cell">{{ host.loginUser || '-' }}</span>
          <span class="host-port-cell">{{ host.port || 22 }}</span>
          <div class="host-config">
            <template v-if="host.verified && host.cpu > 0 && host.memory > 0">
              <span class="os-badge" :class="host.os"></span>
              <strong>{{ host.cpu }}核 {{ host.memory }}GB</strong>
            </template>
            <span v-else class="host-config-empty" aria-label="配置信息为空"></span>
          </div>
          <span class="host-remark-cell" :title="host.remark">{{ host.remark || '-' }}</span>
          <span class="verify-badge" :class="{ verified: host.verified, failed: host.verifyStatus === 'failed' }">
            {{ host.verified ? '已验证' : host.verifyStatus === 'failed' ? '验证失败' : '未验证' }}
          </span>
          <div class="host-actions">
            <button type="button" @click="editManagedHost(host)">编辑</button>
            <button type="button" :disabled="verifyingHostIds.has(host.id)" @click="verifyManagedHost(host)">
              {{ verifyingHostIds.has(host.id) ? '验证中' : '验证' }}
            </button>
            <button class="danger" type="button" @click="deleteManagedHost(host)">删除</button>
          </div>
        </div>
        <div v-if="!visibleManagedHosts.length" class="empty-state host-empty">没有匹配的主机。</div>
      </div>
    </article>

    <div v-if="rootHostGroupDialogOpen" class="modal-backdrop" @click.self="rootHostGroupDialogOpen = false">
      <form class="host-form-modal" @submit.prevent="saveRootHostGroup">
        <button class="modal-close" type="button" @click="rootHostGroupDialogOpen = false"><AppIcon name="x" :size="16" /></button>
        <h2>新建根分组</h2>
        <label>
          <span>分组名称</span>
          <input v-model="rootHostGroupName" autofocus placeholder="输入根分组名称" />
        </label>
        <label>
          <span>插入位置</span>
          <select v-model.number="rootHostGroupSortAfter">
            <option :value="null">列表末尾</option>
            <option v-for="group in flatHostGroups.filter((item) => item.level === 0)" :key="group.key" :value="group.key">
              在 {{ group.label }} 后
            </option>
          </select>
        </label>
        <div class="host-form-actions">
          <button type="button" @click="rootHostGroupDialogOpen = false">取消</button>
          <button class="primary" type="submit">保存</button>
        </div>
      </form>
    </div>

    <div v-if="hostDialog" class="modal-backdrop" @click.self="hostDialog = null">
      <form class="host-form-modal host-edit-modal host-horizontal-modal" @submit.prevent="saveManagedHost">
        <button class="modal-close" type="button" @click="hostDialog = null"><AppIcon name="x" :size="16" /></button>
        <h2>{{ hostDialog.mode === 'edit' ? '编辑主机' : '新增主机' }}</h2>
        <label class="host-horizontal-field required">
          <span>主机分组：</span>
          <select v-model.number="hostForm.group">
            <option v-for="group in flatHostGroups" :key="group.key" :value="group.key">{{ `${'　'.repeat(group.level)}${group.label}` }}</option>
          </select>
        </label>
        <label class="host-horizontal-field required">
          <span>主机名称：</span>
          <input v-model="hostForm.name" autofocus />
        </label>
        <label class="host-horizontal-field required">
          <span>主机 IP：</span>
          <input v-model="hostForm.privateIp" />
          <small v-if="hostPrivateIpExists" class="host-field-error">IP 已存在，请重新输入。</small>
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
