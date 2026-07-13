import { computed, watch } from 'vue';

import { useShellState } from '../../composables/app/useShellState';
import type { useSessionState } from './useSessionState';

type SessionState = ReturnType<typeof useSessionState>;

type UsePageStateOptions = {
  selectHost: (ip: string) => void;
  runPing: () => Promise<void>;
};

export function usePageState(session: SessionState, { selectHost, runPing }: UsePageStateOptions) {
  const shellState = useShellState();
  const {
    activeTool,
    groupsOpen,
    sidebarCollapsed,
    hoveredNavGroup,
    workspaceTheme,
    isWorkspaceDark,
    navGroups,
    dashboardNavItem,
    activeNavGroup,
    activeNavItem,
    setActiveTool,
    selectNavItem,
    toggleSidebar,
    toggleWorkspaceTheme,
    openNavFlyout,
    closeNavFlyout,
    navItemIcon,
    navGroupIcon,
    cleanupShellState,
  } = shellState;
  const { currentUser, isAuthenticated } = session.state;

  const permittedNavGroups = computed(() => {
    const user = currentUser.value;
    if (!user || user.is_superuser || user.is_staff) return navGroups;
    const permissionCodes = new Set(user.featurePermissionCodes ?? []);
    return navGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => session.canAccessNavItem(item.key, permissionCodes)),
      }))
      .filter((group) => group.items.length);
  });

  const permittedDashboardItem = computed(() => {
    const user = currentUser.value;
    if (!user || user.is_superuser || user.is_staff) return dashboardNavItem;
    return session.currentPermissionCodes.value.has('access_dashboard') ? dashboardNavItem : null;
  });

  const permittedToolKeys = computed(() => {
    const keys = permittedNavGroups.value.flatMap((group) => group.items.map((item) => item.key));
    if (permittedDashboardItem.value) keys.unshift(permittedDashboardItem.value.key);
    return new Set(keys);
  });

  const permittedActiveNavGroup = computed(() => {
    if (activeTool.value === 'dashboard' && permittedDashboardItem.value) {
      return { key: 'dashboard', label: dashboardNavItem.label, items: [permittedDashboardItem.value] };
    }
    return permittedNavGroups.value.find((group) => group.items.some((item) => item.key === activeTool.value)) ?? permittedNavGroups.value[0] ?? activeNavGroup.value;
  });

  const permittedActiveNavItem = computed(() => {
    if (activeTool.value === 'dashboard' && permittedDashboardItem.value) return permittedDashboardItem.value;
    return permittedActiveNavGroup.value.items.find((item) => item.key === activeTool.value) ?? permittedActiveNavGroup.value.items[0] ?? activeNavItem.value;
  });

  function defaultLoginTool() {
    return permittedDashboardItem.value?.key ?? permittedNavGroups.value[0]?.items[0]?.key ?? 'dashboard';
  }

  function selectDefaultTool() {
    setActiveTool(defaultLoginTool());
  }

  async function openPingFromHost(ip: string) {
    selectHost(ip);
    activeTool.value = 'ports';
    await runPing();
  }

  watch([isAuthenticated, permittedToolKeys], ([authenticated, toolKeys]) => {
    if (!authenticated || toolKeys.has(activeTool.value)) return;
    const firstTool = permittedDashboardItem.value?.key ?? permittedNavGroups.value[0]?.items[0]?.key;
    if (firstTool) activeTool.value = firstTool;
  });

  const state = {
    groupsOpen,
    sidebarCollapsed,
    hoveredNavGroup,
    workspaceTheme,
    isWorkspaceDark,
    dashboardNavItem: permittedDashboardItem,
    navGroups: permittedNavGroups,
    activeNavGroup: permittedActiveNavGroup,
    activeNavItem: permittedActiveNavItem,
    setActiveTool,
    selectNavItem,
    toggleSidebar,
    toggleWorkspaceTheme,
    openNavFlyout,
    closeNavFlyout,
    navItemIcon,
    navGroupIcon,
    activeTool,
    openPingFromHost,
  };

  return {
    state,
    activeTool,
    selectDefaultTool,
    cleanup: cleanupShellState,
  };
}
