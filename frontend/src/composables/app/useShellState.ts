import { computed, ref } from 'vue';

import type { IconName } from '../../components/common/AppIcon.vue';
import { navGroups } from '../../navigation';
import type { ToolKey } from '../../types';

export function useShellState() {
  const activeTool = ref<ToolKey>('ip');
  const groupsOpen = ref({ network: true, host: true, security: true, system: true });
  const sidebarCollapsed = ref(false);
  const hoveredNavGroup = ref<string | null>(null);
  let navFlyoutTimer: number | undefined;

  const activeNavGroup = computed(() => navGroups.find((group) => group.items.some((item) => item.key === activeTool.value)) ?? navGroups[0]);
  const activeNavItem = computed(() => activeNavGroup.value.items.find((item) => item.key === activeTool.value) ?? activeNavGroup.value.items[0]);

  function setActiveTool(key: ToolKey) {
    activeTool.value = key;
    if (key === 'hosts') {
      sidebarCollapsed.value = true;
    }
  }

  function selectNavItem(key: ToolKey) {
    setActiveTool(key);
    closeNavFlyout(80);
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  function openNavFlyout(key: string) {
    window.clearTimeout(navFlyoutTimer);
    hoveredNavGroup.value = key;
  }

  function closeNavFlyout(delay = 220) {
    window.clearTimeout(navFlyoutTimer);
    navFlyoutTimer = window.setTimeout(() => {
      hoveredNavGroup.value = null;
    }, delay);
  }

  function cleanupShellState() {
    window.clearTimeout(navFlyoutTimer);
  }

  return {
    activeTool,
    groupsOpen,
    sidebarCollapsed,
    hoveredNavGroup,
    navGroups,
    activeNavGroup,
    activeNavItem,
    setActiveTool,
    selectNavItem,
    toggleSidebar,
    openNavFlyout,
    closeNavFlyout,
    navItemIcon,
    navGroupIcon,
    cleanupShellState,
  };
}

function navItemIcon(key: ToolKey): IconName {
  const icons: Record<ToolKey, IconName> = {
    ip: 'network',
    hosts: 'server',
    accounts: 'users',
    ports: 'gauge',
    subnet: 'globe',
    auth: 'shield',
    password: 'key',
    loginLogs: 'bell',
    users: 'user',
    roles: 'shield',
    systemSettings: 'settings',
  };
  return icons[key];
}

function navGroupIcon(key: string): IconName {
  const icons: Record<string, IconName> = { network: 'monitor', host: 'server', security: 'settings', system: 'dashboard' };
  return icons[key] ?? 'dashboard';
}
