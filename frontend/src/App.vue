<script setup lang="ts">
import { computed, defineAsyncComponent, provide, ref, watch } from 'vue';

import { appContextKey } from './appContext';
import AppIcon from './components/common/AppIcon.vue';
import WatermarkOverlay from './components/common/WatermarkOverlay.vue';
import LockScreenOverlay from './components/common/LockScreenOverlay.vue';
import { hostExportColumnOptions, type HostExportColumnKey, type HostExportScope } from './composables/features/useHostManager';
import { useAppState } from './composables/useAppState';
import { errorMessage } from './utils/errors';

type DashboardPageExpose = {
  refresh?: () => Promise<void> | void;
};

const AccountManager = defineAsyncComponent(() => import('./components/tools/AccountManager.vue'));
const AuthenticatorPanel = defineAsyncComponent(() => import('./components/tools/AuthenticatorPanel.vue'));
const DashboardPage = defineAsyncComponent(() => import('./components/tools/DashboardPage.vue'));
const HostManager = defineAsyncComponent(() => import('./components/tools/HostManager.vue'));
const IpScanner = defineAsyncComponent(() => import('./components/tools/IpScanner.vue'));
const SessionAuditManager = defineAsyncComponent(() => import('./components/tools/SessionAuditManager.vue'));
const LoginLogManager = defineAsyncComponent(() => import('./components/tools/LoginLogManager.vue'));
const LoginPage = defineAsyncComponent(() => import('./components/auth/LoginPage.vue'));
const MachineProbe = defineAsyncComponent(() => import('./components/tools/MachineProbe.vue'));
const OperationLogManager = defineAsyncComponent(() => import('./components/tools/OperationLogManager.vue'));
const PasswordGenerator = defineAsyncComponent(() => import('./components/tools/PasswordGenerator.vue'));
const ProfileCenter = defineAsyncComponent(() => import('./components/tools/ProfileCenter.vue'));
const RoleManager = defineAsyncComponent(() => import('./components/tools/RoleManager.vue'));
const SubnetCalculator = defineAsyncComponent(() => import('./components/tools/SubnetCalculator.vue'));
const SystemSettingsPanel = defineAsyncComponent(() => import('./components/tools/SystemSettingsPanel.vue'));
const UserManager = defineAsyncComponent(() => import('./components/tools/UserManager.vue'));

const appState = useAppState();
provide(appContextKey, appState);

const hostExportScope = ref<HostExportScope>('all');
const selectedHostExportColumns = ref<Set<HostExportColumnKey>>(new Set(hostExportColumnOptions.map((column) => column.field)));
const selectedHostExportColumnList = computed(() => [...selectedHostExportColumns.value]);
const allHostExportColumnsSelected = computed(() => selectedHostExportColumns.value.size === hostExportColumnOptions.length);
const dashboardPageRef = ref<DashboardPageExpose | null>(null);
const isDashboardRefreshing = ref(false);

const {
  activeTool,
  groupsOpen,
  sidebarCollapsed,
  hoveredNavGroup,
  isWorkspaceDark,
  toast,
  localIp,
  selectedHost,
  ipScanMessage,
  dashboardNavItem,
  navGroups,
  activeNavGroup,
  activeNavItem,
  currentUser,
  isLocked,
  hasWorkspaceDataLoaded,
  canAccessPage,
  canUsePageAction,
  isAuthReady,
  isAuthenticated,
  login,
  verifyTwoFactorLogin,
  verifyTwoFactorSetupLogin,
  logout,
  lockSession,
  unlockSession,
  scopedToastVisible,
  toastTone,
  showToast,
  shouldShowWatermark,
  siteIdentity,
  layoutFooter,
  renderSystemTemplate,
  watermarkText,
  setActiveTool,
  selectNavItem,
  toggleSidebar,
  toggleWorkspaceTheme,
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
  hostImportFile,
  hostImportAccept,
  hostTransferDialog,
  hostTransferFormat,
  openHostTransferDialog,
  closeHostTransferDialog,
  confirmHostTransfer,
  backupHostManagement,
  exportHostManagement,
  importHostManagement,
  triggerHostRestoreFile,
  selectedManagedHostIds,
  visibleManagedHosts,
  openWebTerminal,
  useSelectedIpForPing,
  qrPreview,
  copyText,
  confirmDialog,
  runConfirmAction,
} = appState;

const selectedManagedHostCount = computed(() => visibleManagedHosts.value.filter((host) => selectedManagedHostIds.value.has(host.id)).length);
const currentUserDisplayName = computed(() => currentUser.value?.displayName || currentUser.value?.first_name || currentUser.value?.username || '未命名用户');
const currentUserAccount = computed(() => currentUser.value?.username || currentUser.value?.email || '当前账户');
const currentUserAvatar = computed(() => currentUser.value?.avatarUrl || siteIdentity.value.iconUrl);
const sidebarLogoUrl = computed(() => siteIdentity.value.logoImageUrl || siteIdentity.value.iconUrl);
const footerText = computed(() => renderSystemTemplate(layoutFooter.value.textTemplate));
const footerLinkText = computed(() => renderSystemTemplate(layoutFooter.value.linkText));
const footerStyle = computed(() => ({ fontSize: `${layoutFooter.value.fontSize}px`, color: layoutFooter.value.color }));
const isExternalFooterLink = computed(() => /^https?:\/\//i.test(layoutFooter.value.linkUrl));

watch(hostTransferDialog, (mode) => {
  if (mode !== 'export') return;
  hostExportScope.value = 'all';
  selectedHostExportColumns.value = new Set(hostExportColumnOptions.map((column) => column.field));
});

function toggleHostExportColumn(column: HostExportColumnKey, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const next = new Set(selectedHostExportColumns.value);
  if (checked) {
    next.add(column);
  } else {
    next.delete(column);
  }
  selectedHostExportColumns.value = next;
}

function toggleAllHostExportColumns(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  selectedHostExportColumns.value = checked ? new Set(hostExportColumnOptions.map((column) => column.field)) : new Set();
}

async function confirmHostExport() {
  const exported = await exportHostManagement(hostTransferFormat.value, {
    scope: hostExportScope.value,
    selectedIds: [...selectedManagedHostIds.value],
    columns: selectedHostExportColumnList.value,
  });
  if (exported) closeHostTransferDialog();
}

async function refreshDashboard() {
  if (isDashboardRefreshing.value) return;
  isDashboardRefreshing.value = true;
  try {
    await dashboardPageRef.value?.refresh();
    showToast('刷新完成', '仪表盘数据已更新。');
  } finally {
    isDashboardRefreshing.value = false;
  }
}

async function lockCurrentSession() {
  try {
    await lockSession();
  } catch (error) {
    showToast('锁屏失败', errorMessage(error));
  }
}
</script>
<template>
  <main v-if="!isAuthReady" class="auth-loading">
    <div>
      <span></span>
      <strong>正在检查登录状态</strong>
    </div>
  </main>
  <LoginPage
    v-else-if="!isAuthenticated"
    :login="login"
    :verify-two-factor-login="verifyTwoFactorLogin"
    :verify-two-factor-setup-login="verifyTwoFactorSetupLogin"
  />
  <main v-else class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'workspace-dark': isWorkspaceDark }">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-brand">
        <img :src="sidebarLogoUrl" :alt="siteIdentity.appName" />
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
        <button
          v-if="dashboardNavItem && !sidebarCollapsed"
          class="nav-dashboard-button"
          :class="{ active: activeTool === 'dashboard' }"
          type="button"
          @click="setActiveTool('dashboard')"
        >
          <span class="nav-icon"><AppIcon name="dashboard" :size="18" /></span>
          <span>{{ dashboardNavItem.label }}</span>
        </button>
        <button
          v-if="dashboardNavItem && sidebarCollapsed"
          class="nav-dashboard-compact"
          :class="{ active: activeTool === 'dashboard' }"
          type="button"
          :title="dashboardNavItem.label"
          :aria-label="dashboardNavItem.label"
          @click="setActiveTool('dashboard')"
        >
          <span class="nav-icon"><AppIcon name="dashboard" :size="18" /></span>
        </button>
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

    <section class="workspace" :class="{ 'has-workspace-footer': layoutFooter.enabled }">
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

      <header class="workspace-topbar">
        <div class="workspace-topbar-main">
          <button
            class="workspace-menu-button"
            type="button"
            :title="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
            :aria-label="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
            @click="toggleSidebar"
          >
            <AppIcon name="menu" :size="18" />
          </button>
          <div class="page-breadcrumb">
            <span>首页</span>
            <template v-if="activeTool === 'dashboard'">
              <em>/</em>
              <strong>仪表盘</strong>
            </template>
            <template v-else>
              <em>/</em>
              <span>{{ activeNavGroup.label }}</span>
              <em>/</em>
              <strong>{{ activeNavItem.label }}</strong>
            </template>
          </div>
        </div>
        <div class="workspace-actions">
          <div class="header-stats">
            <template v-if="activeTool === 'auth'">
              <button v-if="canUsePageAction('auth', 'export')" class="header-action" type="button" @click="saveAuthEntries">导出</button>
              <button v-if="canUsePageAction('auth', 'import')" class="header-action" type="button" @click="triggerAuthImportFile">导入</button>
              <input ref="authImportFile" hidden type="file" accept="application/json,.json" @change="importAuthEntries" />
            </template>
            <template v-else-if="activeTool === 'password'">
              <button v-if="canUsePageAction('password', 'export')" class="header-action" type="button" @click="exportPasswordRecords">导出</button>
              <button v-if="canUsePageAction('password', 'import')" class="header-action" type="button" @click="triggerPasswordImportFile">导入</button>
              <input ref="passwordImportFile" hidden type="file" accept="text/plain,application/json,.txt,.json" @change="importPasswordRecords" />
            </template>
            <template v-else-if="activeTool === 'hosts'">
              <button v-if="canUsePageAction('hosts', 'export')" class="header-action" type="button" @click="backupHostManagement"><AppIcon name="download" :size="16" />备份</button>
              <button v-if="canUsePageAction('hosts', 'import')" class="header-action" type="button" @click="triggerHostRestoreFile"><AppIcon name="upload" :size="16" />恢复</button>
              <input ref="hostImportFile" hidden type="file" :accept="hostImportAccept" @change="importHostManagement" />
              <button
                v-if="canUsePageAction('hosts', 'terminal')"
                class="header-action terminal-action terminal-icon-action"
                type="button"
                title="Web 终端"
                aria-label="Web 终端"
                @click="openWebTerminal()"
              >
                <AppIcon name="terminal" :size="16" />
              </button>
            </template>
            <template v-else-if="activeTool === 'dashboard' || activeTool === 'sessionAudits' || activeTool === 'accounts' || activeTool === 'users' || activeTool === 'loginLogs' || activeTool === 'operationLogs' || activeTool === 'roles' || activeTool === 'profile' || activeTool === 'systemSettings'"></template>
            <template v-else-if="activeTool === 'ip' && ipScanMessage">
              <span class="inline-status">{{ ipScanMessage }}</span>
            </template>
            <template v-else>
              <article><span>本机 IP</span><strong>{{ localIp }}</strong></article>
              <article
                class="selected-host-card"
                title="双击使用选中 IP"
                @dblclick="useSelectedIpForPing"
              ><span>选中 IP</span><strong>{{ selectedHost }}</strong></article>
            </template>
          </div>
          <button
            class="workspace-icon-button workspace-theme-toggle"
            type="button"
            :title="isWorkspaceDark ? '切换明亮模式' : '切换暗黑模式'"
            :aria-label="isWorkspaceDark ? '切换明亮模式' : '切换暗黑模式'"
            :aria-pressed="isWorkspaceDark"
            @click="toggleWorkspaceTheme"
          >
            <AppIcon :name="isWorkspaceDark ? 'sun' : 'moon'" :size="18" />
          </button>
          <button
            v-if="activeTool === 'dashboard'"
            class="workspace-icon-button workspace-dashboard-refresh"
            type="button"
            :disabled="isDashboardRefreshing"
            :title="isDashboardRefreshing ? '刷新中' : '刷新仪表盘'"
            :aria-label="isDashboardRefreshing ? '刷新中' : '刷新仪表盘'"
            @click="refreshDashboard"
          >
            <AppIcon name="refresh" :size="18" />
          </button>
          <div class="workspace-user-menu">
            <button class="workspace-avatar-button" type="button" aria-haspopup="menu" aria-label="账户菜单">
              <img :src="currentUserAvatar" alt="" />
            </button>
            <div class="workspace-user-dropdown" role="menu">
              <div class="workspace-user-card">
                <img :src="currentUserAvatar" alt="" />
                <div>
                  <strong>{{ currentUserDisplayName }}</strong>
                  <span>{{ currentUserAccount }}</span>
                </div>
              </div>
              <span class="workspace-menu-divider"></span>
              <button class="workspace-menu-action" type="button" role="menuitem" :disabled="!canAccessPage('profile')" @click="setActiveTool('profile')">
                <AppIcon name="user" :size="16" />
                <span>个人中心</span>
              </button>
              <button class="workspace-menu-action" type="button" role="menuitem" @click="lockCurrentSession">
                <AppIcon name="lock" :size="16" />
                <span>锁定屏幕</span>
              </button>
              <span class="workspace-menu-divider"></span>
              <button class="workspace-menu-action workspace-menu-logout" type="button" role="menuitem" @click="logout">
                <AppIcon name="logout" :size="16" />
                <span>退出登录</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <section class="workspace-body">
        <template v-if="!isLocked || hasWorkspaceDataLoaded">
          <DashboardPage v-if="activeTool === 'dashboard'" ref="dashboardPageRef" />
          <IpScanner v-if="activeTool === 'ip'" />
          <HostManager v-if="activeTool === 'hosts'" />
          <SessionAuditManager v-if="activeTool === 'sessionAudits'" />
          <AccountManager v-if="activeTool === 'accounts'" />
          <MachineProbe v-if="activeTool === 'ports'" />
          <SubnetCalculator v-if="activeTool === 'subnet'" />
          <AuthenticatorPanel v-if="activeTool === 'auth'" />
          <PasswordGenerator v-if="activeTool === 'password'" />
          <LoginLogManager v-if="activeTool === 'loginLogs'" />
          <OperationLogManager v-if="activeTool === 'operationLogs'" />
          <UserManager v-if="activeTool === 'users'" />
          <RoleManager v-if="activeTool === 'roles'" />
          <ProfileCenter v-if="activeTool === 'profile'" />
          <SystemSettingsPanel v-if="activeTool === 'systemSettings'" />
        </template>
      </section>
      <footer v-if="layoutFooter.enabled" class="workspace-footer" :style="footerStyle">
        <span>{{ footerText }}</span>
        <a
          v-if="layoutFooter.linkText && layoutFooter.linkUrl"
          :href="layoutFooter.linkUrl"
          :target="isExternalFooterLink ? '_blank' : undefined"
          :rel="isExternalFooterLink ? 'noreferrer' : undefined"
        >
          {{ footerLinkText }}
        </a>
      </footer>
    </section>

    <WatermarkOverlay v-if="shouldShowWatermark" :text="watermarkText" />
    <LockScreenOverlay
      v-if="currentUser"
      :locked="isLocked"
      :avatar-url="currentUserAvatar"
      :display-name="currentUserDisplayName"
      :account="currentUserAccount"
      :unlock-session="unlockSession"
      :logout="logout"
    />

    <div v-if="hostTransferDialog" class="modal-backdrop" @click.self="closeHostTransferDialog">
      <article class="host-transfer-modal" :class="{ 'host-export-modal': hostTransferDialog === 'export' }">
        <button class="modal-close" type="button" @click="closeHostTransferDialog"><AppIcon name="x" :size="16" /></button>
        <template v-if="hostTransferDialog === 'export'">
          <h2>导出实例数据</h2>
          <div class="host-export-body">
            <section class="export-section">
              <span class="export-section-title">需要导出的实例</span>
              <div class="export-scope-grid">
                <label class="export-scope-card" :class="{ active: hostExportScope === 'all' }">
                  <input v-model="hostExportScope" type="radio" value="all" />
                  <span>
                    <strong>所有实例</strong>
                    <em>导出当前主机列表下的所有实例</em>
                  </span>
                </label>
                <label class="export-scope-card" :class="{ active: hostExportScope === 'selected' }">
                  <input v-model="hostExportScope" type="radio" value="selected" />
                  <span>
                    <strong>已选中的实例 {{ selectedManagedHostCount }}</strong>
                    <em>导出当前列表中所选中的实例</em>
                  </span>
                </label>
              </div>
            </section>

            <section class="export-section">
              <span class="export-section-title">需要导出的数据列</span>
              <div class="export-check-all">
                <input type="checkbox" :checked="allHostExportColumnsSelected" @change="toggleAllHostExportColumns" />
                <span>全选</span>
              </div>
              <div class="export-column-grid">
                <label v-for="column in hostExportColumnOptions" :key="column.field" class="export-column-option">
                  <input type="checkbox" :checked="selectedHostExportColumns.has(column.field)" @change="toggleHostExportColumn(column.field, $event)" />
                  <span>{{ column.label }}</span>
                </label>
              </div>
            </section>

            <section class="export-section">
              <span class="export-section-title">导出文件格式</span>
              <div class="export-format-row">
                <label class="transfer-radio">
                  <input v-model="hostTransferFormat" type="radio" value="excel" />
                  <span>Excel</span>
                </label>
                <label class="transfer-radio">
                  <input v-model="hostTransferFormat" type="radio" value="json" />
                  <span>JSON</span>
                </label>
              </div>
            </section>
          </div>
        </template>
        <template v-else>
          <h2>导入</h2>
          <div class="host-transfer-body">
            <div class="transfer-row">
              <span class="transfer-label">文件类型</span>
              <label class="transfer-radio">
                <input v-model="hostTransferFormat" type="radio" value="json" />
                <span>JSON</span>
              </label>
              <label class="transfer-radio">
                <input v-model="hostTransferFormat" type="radio" value="excel" />
                <span>Excel</span>
              </label>
            </div>
          </div>
        </template>
        <div class="modal-actions">
          <button type="button" @click="closeHostTransferDialog">取消</button>
          <button class="primary" type="button" @click="hostTransferDialog === 'export' ? confirmHostExport() : confirmHostTransfer()">确定</button>
        </div>
      </article>
    </div>

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
