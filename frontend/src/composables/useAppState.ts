import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { apiGet } from '../api';
import { setupClickWords, setupPointerTrail } from '../utils/effects';
import { useAuthSession } from './app/useAuthSession';
import { useFeedback } from './app/useFeedback';
import { useShellState } from './app/useShellState';
import { useAuthenticator } from './features/useAuthenticator';
import { useHostManager, type HostTransferFormat } from './features/useHostManager';
import { useIpScanner } from './features/useIpScanner';
import { useMachineProbe } from './features/useMachineProbe';
import { usePasswordManager } from './features/usePasswordManager';
import { useSubnetCalculator } from './features/useSubnetCalculator';
import { useWatermarkSettings, watermarkAppliesToPage } from './features/useWatermarkSettings';
export function useAppState() {
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

const feedback = useFeedback(activeTool);
const {
  toast,
  confirmDialog,
  scopedToastVisible,
  toastTone,
  showToast,
  copyText,
  requestConfirm,
  runConfirmAction,
  clearFeedback,
  cleanupFeedback,
} = feedback;

const localIp = ref('198.18.0.1');
const selectedHost = ref('192.168.1.1');

const authImportFile = ref<HTMLInputElement | null>(null);
const passwordImportFile = ref<HTMLInputElement | null>(null);
const hostImportFile = ref<HTMLInputElement | null>(null);
const hostTransferDialog = ref<'import' | 'export' | null>(null);
const hostTransferFormat = ref<HostTransferFormat>('json');
const imageInput = ref<HTMLInputElement | null>(null);
const currentHostCreatorUsername = ref<string | null>(null);
const currentWatermarkText = ref('CAPTAIN');
const hostManager = useHostManager({ showToast, requestConfirm, currentUsername: () => currentHostCreatorUsername.value });
const {
  hostSearch,
  selectedHostGroup,
  hostStatusFilter,
  hostSortKey,
  hostSortDirection,
  hostGroups,
  hostCredentials,
  hostGroupRoot,
  flatHostGroups,
  visibleHostGroups,
  hostGroupRows,
  hostGroupRootExpanded,
  visibleManagedHosts,
  groupMoveHosts,
  managedHostStats,
  isLoadingHosts,
  hostGroupInlineEdit,
  rootHostGroupDialogOpen,
  rootHostGroupName,
  rootHostGroupSortAfter,
  hostGroupMenu,
  hostDialog,
  hostForm,
  hostMoveDialogOpen,
  hostMoveMode,
  hostMoveForm,
  draggedHostGroupId,
  hostGroupDropTarget,
  verifyingHostIds,
  selectedManagedHostIds,
  loadHostManagement,
  backupHostManagement,
  exportHostManagement,
  importHostManagement,
  selectManagedGroup,
  setHostSort,
  hostSortMark,
  hostGroupName,
  isHostGroupExpanded,
  toggleHostGroupExpanded,
  toggleHostGroupRootExpanded,
  startHostGroupDrag,
  updateHostGroupDropTarget,
  clearHostGroupDropTarget,
  dropHostGroup,
  finishHostGroupDrag,
  openHostGroupMenu,
  closeHostGroupMenu,
  openAddRootHostGroup,
  openAddHostGroup,
  openRenameHostGroup,
  saveHostGroupInlineEdit,
  saveRootHostGroup,
  cancelHostGroupInlineEdit,
  verifyManagedHost,
  verifyVisibleManagedHosts,
  verifySelectedManagedHosts,
  openWebTerminal,
  addManagedHost,
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
} = hostManager;

const machineProbe = useMachineProbe({ showToast, selectedHost });
const {
  portHost,
  portsInput,
  portTimeout,
  portConcurrency,
  portResult,
  portProgress,
  portScanMessage,
  isScanningPorts,
  pingHost,
  pingCount,
  pingTimeout,
  pingInterval,
  pingContinuous,
  pingDetails,
  isPinging,
  pingMetrics,
  pingChart,
  applyPortPreset,
  scanPorts,
  stopPortScan,
  setPingPreset,
  useSelectedIpForPing,
  runPing,
  stopPing,
  clearPingResults,
  exportPingResults,
} = machineProbe;

const ipScanner = useIpScanner({ showToast, selectHost });
const {
  networkSegment,
  hosts,
  ipProgress,
  isScanningIp,
  ipScanMessage,
  onlineHosts,
  offlineHosts,
  scanIp,
} = ipScanner;

const subnetCalculator = useSubnetCalculator({ showToast });
const {
  subnetInput,
  subnetPrefix,
  subnetTargetPrefix,
  subnetSplitMode,
  subnetResult,
  subnetPresets,
  prefixOptions,
  subnetSplitChoices,
  subnetSplitSummary,
  canSplitSubnet,
  subnetTypeText,
  subnetClassText,
  subnetBinaryParts,
  calculateSubnet,
  handlePrefixChange,
  setSubnetPreset,
  clearSubnet,
} = subnetCalculator;

const passwordManager = usePasswordManager({ showToast, copyText, requestConfirm, passwordImportFile });
const {
  passwordProject,
  passwordLength,
  passwordOptions,
  passwordResult,
  passwordHistory,
  generatePassword,
  loadPasswords,
  deletePassword,
  togglePasswordOption,
  passwordOptionText,
  formatRecordTime,
  clearPasswordRecords,
  exportPasswordRecords,
  importPasswordRecords,
  triggerPasswordImportFile,
} = passwordManager;

const authenticator = useAuthenticator({ showToast, copyText, requestConfirm, authImportFile, imageInput });
const {
  authEntries,
  authForm,
  authImport,
  editingAuthId,
  qrPreview,
  loadAuthEntries,
  saveAuthEntry,
  saveAuthEntries,
  importAuthEntries,
  editAuth,
  deleteAuth,
  clearAuthEntries,
  copyAuthCode,
  showQr,
  resetAuthForm,
  parseAuthImport,
  scanScreenQr,
  triggerImageImport,
  triggerAuthImportFile,
  handleImageImport,
} = authenticator;

const watermarkSettings = useWatermarkSettings({ showToast, getWatermarkText: () => currentWatermarkText.value });
const {
  watermarkConfig,
  watermarkDraft,
  watermarkText,
  watermarkLoading,
  watermarkSaving,
  watermarkMessage,
  loadWatermarkSetting,
  saveWatermarkSetting,
  resetWatermarkDraft,
} = watermarkSettings;

async function loadLocalIp() {
  try {
    const data = await apiGet<{ ip: string }>('/api/local-ip/');
    localIp.value = data.ip;
  } catch {
    localIp.value = '198.18.0.1';
  }
}

async function loadWorkspaceData() {
  currentWatermarkText.value = currentUser.value?.username ?? 'CAPTAIN';
  await Promise.allSettled([loadLocalIp(), loadAuthEntries(), loadPasswords(), loadWatermarkSetting(), loadHostManagement(), calculateSubnet(false)]);
}

const { currentUser, isAuthReady, isAuthenticated, loadCurrentUser, login, verifyTwoFactorLogin, verifyTwoFactorSetupLogin, updateCurrentUser, refreshCurrentUser, logout } = useAuthSession({
  loadWorkspaceData,
  clearSessionUi: () => {
    clearFeedback();
    qrPreview.value = null;
  },
});

watch(
  currentUser,
  (user) => {
    currentHostCreatorUsername.value = user?.username ?? null;
    currentWatermarkText.value = user?.username ?? 'CAPTAIN';
  },
  { immediate: true },
);

const permittedNavGroups = computed(() => {
  const user = currentUser.value;
  if (!user || user.is_superuser || user.is_staff) return navGroups;
  const permissionCodes = new Set(user.featurePermissionCodes ?? []);
  return navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => permissionCodes.has(`access_${item.key}`)),
    }))
    .filter((group) => group.items.length);
});

const currentPermissionCodes = computed(() => new Set(currentUser.value?.featurePermissionCodes ?? []));
const permittedDashboardItem = computed(() => {
  const user = currentUser.value;
  if (!user || user.is_superuser || user.is_staff) return dashboardNavItem;
  return currentPermissionCodes.value.has('access_dashboard') ? dashboardNavItem : null;
});
const permittedToolKeys = computed(() => {
  const keys = permittedNavGroups.value.flatMap((group) => group.items.map((item) => item.key));
  if (permittedDashboardItem.value) keys.unshift(permittedDashboardItem.value.key);
  return new Set(keys);
});
const permittedActiveNavGroup = computed(() => {
  if (activeTool.value === 'dashboard' && permittedDashboardItem.value) {
    return { key: 'dashboard', label: '仪表盘', items: [permittedDashboardItem.value] };
  }
  return permittedNavGroups.value.find((group) => group.items.some((item) => item.key === activeTool.value)) ?? permittedNavGroups.value[0] ?? activeNavGroup.value;
});
const permittedActiveNavItem = computed(
  () => {
    if (activeTool.value === 'dashboard' && permittedDashboardItem.value) return permittedDashboardItem.value;
    return permittedActiveNavGroup.value.items.find((item) => item.key === activeTool.value) ?? permittedActiveNavGroup.value.items[0] ?? activeNavItem.value;
  },
);
const shouldShowWatermark = computed(() => watermarkAppliesToPage(watermarkConfig.value, activeTool.value));

function canUsePageAction(pageKey: string, actionKey: string) {
  const user = currentUser.value;
  if (!user) return false;
  if (user.is_superuser || user.is_staff) return true;
  return currentPermissionCodes.value.has(`action_${pageKey}_${actionKey}`);
}

function canAccessPage(pageKey: string) {
  const user = currentUser.value;
  if (!user) return false;
  if (user.is_superuser || user.is_staff) return true;
  return currentPermissionCodes.value.has(`access_${pageKey}`);
}

function selectHost(ip: string) {
  selectedHost.value = ip;
  machineProbe.setProbeHost(ip);
}

const hostImportAccept = computed(() => 'application/json,.json,.enc.json');

function openHostTransferDialog(mode: 'import' | 'export') {
  hostTransferDialog.value = mode;
  hostTransferFormat.value = mode === 'export' ? 'excel' : 'json';
}

function closeHostTransferDialog() {
  hostTransferDialog.value = null;
}

async function confirmHostTransfer() {
  if (hostTransferDialog.value === 'export') {
    await exportHostManagement(hostTransferFormat.value);
    closeHostTransferDialog();
    return;
  }
  if (hostTransferDialog.value === 'import') {
    hostImportFile.value?.click();
    closeHostTransferDialog();
  }
}

function triggerHostImportFile() {
  hostImportFile.value?.click();
}

function triggerHostRestoreFile() {
  hostTransferFormat.value = 'json';
  hostImportFile.value?.click();
}

async function importSelectedHostManagement(event: Event) {
  await importHostManagement(event, hostTransferFormat.value);
}

async function openPingFromHost(ip: string) {
  selectHost(ip);
  activeTool.value = 'ports';
  await runPing();
}

let cleanupClickWords: (() => void) | undefined;
let cleanupPointerTrail: (() => void) | undefined;
let authTimer: number | undefined;

const appState = {
  groupsOpen,
  sidebarCollapsed,
  hoveredNavGroup,
  workspaceTheme,
  isWorkspaceDark,
  toast,
  localIp,
  dashboardNavItem: permittedDashboardItem,
  navGroups: permittedNavGroups,
  activeNavGroup: permittedActiveNavGroup,
  activeNavItem: permittedActiveNavItem,
  scopedToastVisible,
  toastTone,
  showToast,
  shouldShowWatermark,
  watermarkConfig,
  watermarkDraft,
  watermarkText,
  watermarkLoading,
  watermarkSaving,
  watermarkMessage,
  loadWatermarkSetting,
  saveWatermarkSetting,
  resetWatermarkDraft,
  currentUser,
  canAccessPage,
  canUsePageAction,
  isAuthReady,
  isAuthenticated,
  loadCurrentUser,
  login,
  verifyTwoFactorLogin,
  verifyTwoFactorSetupLogin,
  updateCurrentUser,
  refreshCurrentUser,
  logout,
  setActiveTool,
  selectNavItem,
  toggleSidebar,
  toggleWorkspaceTheme,
  openNavFlyout,
  closeNavFlyout,
  navItemIcon,
  navGroupIcon,
  authImportFile,
  passwordImportFile,
  hostImportFile,
  hostImportAccept,
  hostTransferDialog,
  hostTransferFormat,
  triggerAuthImportFile,
  triggerPasswordImportFile,
  triggerHostImportFile,
  triggerHostRestoreFile,
  openHostTransferDialog,
  closeHostTransferDialog,
  confirmHostTransfer,
  importAuthEntries,
  exportPasswordRecords,
  importPasswordRecords,
  qrPreview,
  confirmDialog,
  runConfirmAction,
  activeTool,
  networkSegment,
  scanIp,
  isScanningIp,
  ipProgress,
  ipScanMessage,
  onlineHosts,
  offlineHosts,
  hosts,
  selectedHost,
  selectHost,
  openPingFromHost,
  copyText,
  hostGroups,
  hostCredentials,
  hostGroupRoot,
  flatHostGroups,
  visibleHostGroups,
  hostGroupRows,
  hostGroupRootExpanded,
  selectedHostGroup,
  selectManagedGroup,
  setHostSort,
  hostSortMark,
  hostGroupName,
  isHostGroupExpanded,
  toggleHostGroupExpanded,
  toggleHostGroupRootExpanded,
  openHostGroupMenu,
  closeHostGroupMenu,
  hostSearch,
  hostStatusFilter,
  hostSortKey,
  hostSortDirection,
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
  hostMoveDialogOpen,
  hostMoveMode,
  hostMoveForm,
  draggedHostGroupId,
  hostGroupDropTarget,
  verifyingHostIds,
  selectedManagedHostIds,
  loadHostManagement,
  backupHostManagement,
  exportHostManagement,
  importHostManagement: importSelectedHostManagement,
  startHostGroupDrag,
  updateHostGroupDropTarget,
  clearHostGroupDropTarget,
  dropHostGroup,
  finishHostGroupDrag,
  openAddRootHostGroup,
  openAddHostGroup,
  openRenameHostGroup,
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
  portHost,
  portsInput,
  portTimeout,
  portConcurrency,
  applyPortPreset,
  scanPorts,
  isScanningPorts,
  stopPortScan,
  portProgress,
  portScanMessage,
  setPingPreset,
  pingHost,
  useSelectedIpForPing,
  runPing,
  isPinging,
  stopPing,
  pingCount,
  pingTimeout,
  pingInterval,
  pingContinuous,
  clearPingResults,
  exportPingResults,
  pingMetrics,
  pingChart,
  pingDetails,
  portResult,
  subnetPresets,
  setSubnetPreset,
  subnetInput,
  subnetPrefix,
  prefixOptions,
  handlePrefixChange,
  calculateSubnet,
  clearSubnet,
  subnetResult,
  subnetBinaryParts,
  subnetClassText,
  subnetTypeText,
  subnetSplitMode,
  subnetSplitChoices,
  subnetTargetPrefix,
  canSplitSubnet,
  subnetSplitSummary,
  authImport,
  scanScreenQr,
  triggerImageImport,
  imageInput,
  handleImageImport,
  parseAuthImport,
  resetAuthForm,
  authForm,
  saveAuthEntry,
  editingAuthId,
  authEntries,
  saveAuthEntries,
  clearAuthEntries,
  editAuth,
  deleteAuth,
  copyAuthCode,
  showQr,
  passwordLength,
  passwordOptions,
  togglePasswordOption,
  passwordOptionText,
  passwordProject,
  passwordResult,
  generatePassword,
  clearPasswordRecords,
  passwordHistory,
  formatRecordTime,
  deletePassword,
};

onMounted(async () => {
  document.title = '运维船长';
  cleanupClickWords = setupClickWords();
  cleanupPointerTrail = setupPointerTrail();
  await loadCurrentUser();
  authTimer = window.setInterval(() => {
    if (isAuthenticated.value && activeTool.value === 'auth') loadAuthEntries();
  }, 1000);
});

watch([isAuthenticated, permittedToolKeys], ([authenticated, toolKeys]) => {
  if (!authenticated || toolKeys.has(activeTool.value)) return;
  const firstTool = permittedDashboardItem.value?.key ?? permittedNavGroups.value[0]?.items[0]?.key;
  if (firstTool) activeTool.value = firstTool;
});

onUnmounted(() => {
  cleanupClickWords?.();
  cleanupPointerTrail?.();
  window.clearInterval(authTimer);
  cleanupShellState();
  cleanupFeedback();
});

return appState;
}

export type AppState = ReturnType<typeof useAppState>;
