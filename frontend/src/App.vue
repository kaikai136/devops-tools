<script setup lang="ts">
import { provide } from 'vue';

import { appContextKey } from './appContext';
import AccountManager from './components/tools/AccountManager.vue';
import AppIcon from './components/common/AppIcon.vue';
import AuthenticatorPanel from './components/tools/AuthenticatorPanel.vue';
import HostManager from './components/tools/HostManager.vue';
import IpScanner from './components/tools/IpScanner.vue';
import MachineProbe from './components/tools/MachineProbe.vue';
import PasswordGenerator from './components/tools/PasswordGenerator.vue';
import SubnetCalculator from './components/tools/SubnetCalculator.vue';
import UserManager from './components/tools/UserManager.vue';
import { useAppState } from './composables/useAppState';

const appState = useAppState();
provide(appContextKey, appState);

const {
  activeTool,
  groupsOpen,
  sidebarCollapsed,
  hoveredNavGroup,
  toast,
  localIp,
  selectedHost,
  ipScanMessage,
  navGroups,
  activeNavItem,
  scopedToastVisible,
  toastTone,
  setActiveTool,
  selectNavItem,
  toggleSidebar,
  openNavFlyout,
  closeNavFlyout,
  navItemIcon,
  navGroupIcon,
  saveAuthEntries,
  triggerAuthImportFile,
  authImportFile,
  importAuthEntries,
  exportPasswordRecords,
  triggerPasswordImportFile,
  passwordImportFile,
  importPasswordRecords,
  openWebTerminal,
  useSelectedIpForPing,
  qrPreview,
  copyText,
  confirmDialog,
  runConfirmAction,
} = appState;
</script>
<template>
  <main class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-brand">
        <img src="/captain-banner.png" alt="运维船长" />
        <button
          class="sidebar-toggle"
          type="button"
          :title="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
          @click="toggleSidebar"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
      </div>

      <nav class="sidebar-nav">
        <section v-for="group in navGroups" :key="group.key" class="nav-group">
          <button
            class="nav-group-button"
            :class="{ expanded: groupsOpen[group.key], active: group.items.some((item) => item.key === activeTool) }"
            type="button"
            @click="groupsOpen[group.key] = !groupsOpen[group.key]"
          >
            <span class="nav-icon"><AppIcon :name="navGroupIcon(group.key)" :size="18" /></span>
            <span>{{ group.label }}</span>
            <span class="nav-caret"><AppIcon name="chevronDown" :size="14" /></span>
          </button>
          <Transition name="nav-collapse">
            <div v-if="groupsOpen[group.key] && !sidebarCollapsed" class="nav-items">
              <button
                v-for="item in group.items"
                :key="item.key"
                class="nav-item"
                :class="{ active: activeTool === item.key }"
                type="button"
                @click="setActiveTool(item.key)"
              >
                <span class="nav-dot"><AppIcon :name="navItemIcon(item.key)" :size="17" /></span>
                <span>{{ item.label }}</span>
              </button>
            </div>
          </Transition>
          <div
            v-if="sidebarCollapsed"
            class="nav-flyout-wrap"
            :class="{ open: hoveredNavGroup === group.key }"
            @mouseenter="openNavFlyout(group.key)"
            @mouseleave="() => closeNavFlyout()"
            @focusin="openNavFlyout(group.key)"
            @focusout="() => closeNavFlyout()"
          >
            <button
              class="nav-group-compact"
              :class="{ active: group.items.some((item) => item.key === activeTool) }"
              type="button"
              :title="group.label"
              :aria-label="group.label"
              @click="groupsOpen[group.key] = true"
            >
              <span class="nav-icon"><AppIcon :name="navGroupIcon(group.key)" :size="18" /></span>
            </button>
            <div class="nav-flyout" role="menu">
              <strong>{{ group.label }}</strong>
              <button
                v-for="item in group.items"
                :key="item.key"
                class="nav-flyout-item"
                :class="{ active: activeTool === item.key }"
                type="button"
                role="menuitem"
                @click="selectNavItem(item.key)"
              >
                <span class="nav-dot"><AppIcon :name="navItemIcon(item.key)" :size="17" /></span>
                <span>{{ item.label }}</span>
              </button>
            </div>
          </div>
        </section>
      </nav>
    </aside>

    <section class="workspace">
      <div v-if="scopedToastVisible" class="top-toast" :class="[toastTone, { leaving: toast?.leaving }]">
        <span class="toast-icon" aria-hidden="true">
          <AppIcon :name="toastTone === 'success' ? 'circleCheck' : toastTone === 'info' ? 'circleHelp' : 'alert'" :size="18" />
        </span>
        <div class="toast-content">
          <strong>{{ toast?.title }}</strong>
          <p>{{ toast?.message }}</p>
        </div>
        <button type="button" aria-label="关闭提示" @click="toast = null"><AppIcon name="x" :size="16" /></button>
      </div>

      <header v-if="activeTool !== 'users'" class="page-header">
        <div class="page-title-block">
          <h1>{{ activeNavItem.label }}</h1>
          <p>
            {{ activeNavItem.desc }}
            <span v-if="activeTool === 'ip' && ipScanMessage" class="inline-status">{{ ipScanMessage }}</span>
          </p>
        </div>
        <div class="header-stats">
          <template v-if="activeTool === 'auth'">
            <button class="header-action" type="button" @click="saveAuthEntries">导出</button>
            <button class="header-action" type="button" @click="triggerAuthImportFile">导入</button>
            <input ref="authImportFile" hidden type="file" accept="application/json,.json" @change="importAuthEntries" />
          </template>
          <template v-else-if="activeTool === 'password'">
            <button class="header-action" type="button" @click="exportPasswordRecords">导出</button>
            <button class="header-action" type="button" @click="triggerPasswordImportFile">导入</button>
            <input ref="passwordImportFile" hidden type="file" accept="text/plain,application/json,.txt,.json" @change="importPasswordRecords" />
          </template>
          <template v-else-if="activeTool === 'hosts'">
            <button class="header-action terminal-action" type="button" @click="openWebTerminal()"><AppIcon name="terminal" :size="16" />Web 终端</button>
          </template>
          <template v-else-if="activeTool === 'accounts' || activeTool === 'users' || activeTool === 'loginLogs' || activeTool === 'roles' || activeTool === 'systemSettings'"></template>
          <template v-else>
            <article><span>本机 IP</span><strong>{{ localIp }}</strong></article>
            <article
              class="selected-host-card"
              title="双击使用选中 IP"
              @dblclick="useSelectedIpForPing"
            ><span>选中 IP</span><strong>{{ selectedHost }}</strong></article>
          </template>
        </div>
      </header>

      <IpScanner v-if="activeTool === 'ip'" />
      <HostManager v-if="activeTool === 'hosts'" />
      <AccountManager v-if="activeTool === 'accounts'" />
      <MachineProbe v-if="activeTool === 'ports'" />
      <SubnetCalculator v-if="activeTool === 'subnet'" />
      <AuthenticatorPanel v-if="activeTool === 'auth'" />
      <PasswordGenerator v-if="activeTool === 'password'" />
      <UserManager v-if="activeTool === 'users'" />
    </section>

    <div v-if="qrPreview" class="modal-backdrop" @click.self="qrPreview = null">
      <article class="qr-modal share-modal">
        <button class="modal-close" type="button" @click="qrPreview = null"><AppIcon name="x" :size="16" /></button>
        <h2>分享二维码</h2>
        <p>扫码后可直接导入 {{ qrPreview.issuer }} 的双因子配置。</p>
        <div class="qr-frame">
          <img :src="qrPreview.dataUrl" alt="TOTP 二维码" />
        </div>
        <div class="qr-meta">
          <strong>{{ qrPreview.issuer }}</strong>
          <span>{{ qrPreview.account }}</span>
        </div>
        <div class="qr-actions">
          <button type="button" @click="copyText(qrPreview.uri, '已复制分享链接。')">复制分享链接</button>
          <button class="primary" type="button" @click="qrPreview = null">完成</button>
        </div>
      </article>
    </div>
    <div v-if="confirmDialog" class="confirm-panel">
      <article>
        <button class="modal-close" type="button" @click="confirmDialog = null"><AppIcon name="x" :size="16" /></button>
        <h3>{{ confirmDialog.title }}</h3>
        <p>{{ confirmDialog.message }}</p>
        <div>
          <button type="button" @click="confirmDialog = null">取消</button>
          <button class="danger" type="button" @click="runConfirmAction">{{ confirmDialog.actionText }}</button>
        </div>
      </article>
    </div>
  </main>
</template>
