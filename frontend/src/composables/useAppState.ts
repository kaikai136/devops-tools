import { onMounted, onUnmounted, ref } from 'vue';

import { apiGet } from '../api';
import { setupClickWords, setupPointerTrail } from '../utils/effects';
import { useAuthSession } from './app/useAuthSession';
import { useFeedback } from './app/useFeedback';
import { useShellState } from './app/useShellState';
import { useAuthenticator } from './features/useAuthenticator';
import { useHostManager } from './features/useHostManager';
import { useIpScanner } from './features/useIpScanner';
import { useMachineProbe } from './features/useMachineProbe';
import { usePasswordManager } from './features/usePasswordManager';
import { useSubnetCalculator } from './features/useSubnetCalculator';
export function useAppState() {
const shellState = useShellState();
const {
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
const imageInput = ref<HTMLInputElement | null>(null);
const hostManager = useHostManager({ showToast, requestConfirm });
const {
  hostSearch,
  selectedHostGroup,
  hostStatusFilter,
  hostSortKey,
  hostSortDirection,
  hostGroups,
  hostCredentials,
  flatHostGroups,
  visibleHostGroups,
  hostGroupRows,
  visibleManagedHosts,
  groupMoveHosts,
  managedHostStats,
  hostPrivateIpExists,
  isLoadingHosts,
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
  selectManagedGroup,
  setHostSort,
  hostSortMark,
  hostGroupName,
  isHostGroupExpanded,
  toggleHostGroupExpanded,
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
  openWebTerminal,
  addManagedHost,
  editManagedHost,
  saveManagedHost,
  applyCredentialToHostForm,
  uploadHostPrivateKey,
  openMoveHostDialog,
  saveMoveManagedHost,
  deleteManagedHost,
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

async function loadLocalIp() {
  try {
    const data = await apiGet<{ ip: string }>('/api/local-ip/');
    localIp.value = data.ip;
  } catch {
    localIp.value = '198.18.0.1';
  }
}

async function loadWorkspaceData() {
  await Promise.allSettled([loadLocalIp(), loadAuthEntries(), loadPasswords(), loadHostManagement(), calculateSubnet(false)]);
}

const { currentUser, isAuthReady, isAuthenticated, loadCurrentUser, login, logout } = useAuthSession({
  loadWorkspaceData,
  clearSessionUi: () => {
    clearFeedback();
    qrPreview.value = null;
  },
});

function selectHost(ip: string) {
  selectedHost.value = ip;
  machineProbe.setProbeHost(ip);
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
  toast,
  localIp,
  navGroups,
  activeNavGroup,
  activeNavItem,
  scopedToastVisible,
  toastTone,
  currentUser,
  isAuthReady,
  isAuthenticated,
  loadCurrentUser,
  login,
  logout,
  setActiveTool,
  selectNavItem,
  toggleSidebar,
  openNavFlyout,
  closeNavFlyout,
  navItemIcon,
  navGroupIcon,
  authImportFile,
  passwordImportFile,
  triggerAuthImportFile,
  triggerPasswordImportFile,
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
  flatHostGroups,
  visibleHostGroups,
  hostGroupRows,
  selectedHostGroup,
  selectManagedGroup,
  setHostSort,
  hostSortMark,
  hostGroupName,
  isHostGroupExpanded,
  toggleHostGroupExpanded,
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
  editManagedHost,
  saveManagedHost,
  applyCredentialToHostForm,
  uploadHostPrivateKey,
  openMoveHostDialog,
  saveMoveManagedHost,
  deleteManagedHost,
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
