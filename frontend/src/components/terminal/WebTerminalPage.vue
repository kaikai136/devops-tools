<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, watch, type ComponentPublicInstance } from 'vue';
import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import type { IDisposable } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

import { apiGet, apiPost } from '../../api';
import AppIcon from '../common/AppIcon.vue';
import type { IconName } from '../common/AppIcon.vue';

interface TerminalHost {
  id: number;
  name: string;
  group: number;
  privateIp: string;
  publicIp: string;
  port: number;
  loginUser: string;
  remark: string;
  verified: boolean;
  verifyStatus?: 'unverified' | 'verified' | 'failed';
}

interface TerminalGroup {
  id: number;
  name: string;
  hosts: TerminalHost[];
  children: TerminalGroup[];
}

type TerminalStatus = 'connecting' | 'connected' | 'closed' | 'error';
type TerminalSidebarMode = 'hosts' | 'files' | 'monitor';
type TerminalTransferKind = 'upload' | 'download';
type TerminalTransferStatus = 'queued' | 'running' | 'success' | 'error' | 'canceled';
type TerminalDownloadProtocol = 'auto' | 'scp' | 'sftp';

interface TerminalTab {
  id: string;
  host: TerminalHost;
  status: TerminalStatus;
  terminal: Terminal;
  fitAddon: FitAddon;
  socket: WebSocket | null;
  sessionId: string | null;
  mounted: boolean;
  disposables: IDisposable[];
  resizeObserver: ResizeObserver | null;
  highlightState: TerminalHighlightState;
  suppressInterruptUntil: number;
  hasUnreadOutput: boolean;
  currentCwd: string;
  reconnectHintShown: boolean;
}

type TreeRow =
  | { kind: 'root'; group: TerminalRoot; level: number }
  | { kind: 'group'; group: TerminalGroup; level: number }
  | { kind: 'host'; host: TerminalHost; level: number };

interface TerminalRoot {
  id: null;
  name: string;
  count: number;
}

interface TerminalMessage {
  type: 'ready' | 'output' | 'cwd' | 'error' | 'closed';
  sessionId?: string;
  data?: string;
  path?: string;
  message?: string;
  reason?: string;
}

interface TerminalHighlightRule {
  name: string;
  pattern: RegExp;
  open: string;
  close: string;
}

interface TerminalHighlightState {
  sgrActive: boolean;
  pendingControl: string;
}

interface PersistedTerminalTab {
  id: string;
  hostId: number;
}

interface PersistedTerminalWorkspace {
  tabs: PersistedTerminalTab[];
  activeTabId: string | null;
}

interface TerminalFileEntry {
  name: string;
  type: 'directory' | 'file';
  modifiedAt: string;
  path: string;
  size?: number | string;
  permissions?: string;
  owner?: string;
  group?: string;
}

interface TerminalFileListResponse {
  path: string;
  protocol: string;
  entries: TerminalFileEntry[];
}

interface TerminalLocalWritableFile {
  write(data: Blob | Uint8Array): Promise<void>;
  close(): Promise<void>;
  abort?: () => Promise<void>;
}

interface TerminalLocalFileHandle {
  createWritable(): Promise<TerminalLocalWritableFile>;
}

interface TerminalLocalDirectoryHandle {
  getFileHandle(name: string, options?: { create?: boolean }): Promise<TerminalLocalFileHandle>;
  getDirectoryHandle(name: string, options?: { create?: boolean }): Promise<TerminalLocalDirectoryHandle>;
}

interface TerminalDirectoryPickerWindow extends Window {
  showDirectoryPicker?: (options?: { id?: string; mode?: 'read' | 'readwrite' }) => Promise<TerminalLocalDirectoryHandle>;
}

interface TerminalFileUploadItem {
  file: File;
  relativePath?: string;
}

interface TerminalFileSystemEntry {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file?: (success: (file: File) => void, error?: (error: DOMException) => void) => void;
  createReader?: () => {
    readEntries(success: (entries: TerminalFileSystemEntry[]) => void, error?: (error: DOMException) => void): void;
  };
}

interface TerminalTransferRecord {
  id: string;
  kind: TerminalTransferKind;
  status: TerminalTransferStatus;
  name: string;
  path: string;
  currentFile: string;
  currentBytes: number;
  currentTotalBytes: number;
  completedFiles: number;
  totalFiles: number;
  progress: number;
  error: string;
  canceled: boolean;
  abortController: AbortController;
  createdAt: number;
  updatedAt: number;
}

interface TerminalMonitorResponse {
  system: {
    hostname: string;
    arch: string;
    os: string;
    kernel: string;
    uptimeSeconds: number;
  };
  cpu: {
    usagePercent: number;
    load1: number;
    load5: number;
    load15: number;
    cores: number;
  };
  memory: {
    totalBytes: number;
    usedBytes: number;
    availableBytes: number;
    cacheBytes: number;
    usagePercent: number;
  };
  network: Array<{
    name: string;
    rxBytesPerSecond: number;
    txBytesPerSecond: number;
  }>;
  disks: Array<{
    filesystem: string;
    type: string;
    mountpoint: string;
    totalBytes: number;
    usedBytes: number;
    availableBytes: number;
    usagePercent: number;
  }>;
}

interface TerminalFileProperties {
  name: string;
  path: string;
  directory: string;
  type: 'directory' | 'file';
  size: number;
  modifiedAt: string;
  accessedAt: string;
  owner: string;
  group: string;
  uid: number;
  gid: number;
  permissions: string;
  mode: number;
  octalMode: string;
  special: {
    setuid: boolean;
    setgid: boolean;
    sticky: boolean;
  };
}

interface TerminalFilePropertiesDraft {
  owner: string;
  group: string;
  octalMode: string;
}

interface TerminalFilePropertiesDialogState {
  visible: boolean;
  loading: boolean;
  saving: boolean;
  error: string;
  entry: TerminalFileEntry | null;
  properties: TerminalFileProperties | null;
  draft: TerminalFilePropertiesDraft;
  recursive: boolean;
}

interface TerminalFileContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  entry: TerminalFileEntry | null;
}

interface TerminalFileContextMenuItem {
  id: string;
  label: string;
  icon: IconName;
  enabled: boolean;
  danger?: boolean;
  separatorBefore?: boolean;
  children?: TerminalFileContextMenuItem[];
  action: () => void | Promise<void>;
}

interface TerminalFileRenameState {
  path: string;
  originalName: string;
  draftName: string;
  saving: boolean;
  error: string;
}

interface TerminalFileDeleteDialogState {
  visible: boolean;
  entry: TerminalFileEntry | null;
  entries: TerminalFileEntry[];
  deleting: boolean;
  error: string;
}

interface TerminalFileMarqueeState {
  active: boolean;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  additive: boolean;
  basePaths: string[];
}

type TerminalFileCreateMode = 'file' | 'directory' | 'symlink';

interface TerminalFileCreateDialogState {
  visible: boolean;
  mode: TerminalFileCreateMode;
  name: string;
  targetPath: string;
  octalMode: string;
  openAfterCreate: boolean;
  saving: boolean;
  error: string;
}

const ANSI_CONTROL_PATTERN = /\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]/g;
const ANSI_CONTROL_PREFIX_PATTERN = /^\x1b(?:\[[0-?]*[ -/]*)?$/;
const CONTROL_C = '\x03';
const MOUSE_SELECTION_INTERRUPT_SUPPRESSION_MS = 250;
const MOUSE_DOUBLE_CLICK_INTERRUPT_SUPPRESSION_MS = 1200;
const MAX_CONNECTING_TERMINALS = 2;
const TERMINAL_WORKSPACE_STORAGE_KEY = 'ops-tool.web-terminal.workspace';
const TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY = 'ops-tool.web-terminal.sidebar-width';
const TERMINAL_SIDEBAR_COLLAPSED_STORAGE_KEY = 'ops-tool.web-terminal.sidebar-collapsed';
const TERMINAL_SIDEBAR_DEFAULT_WIDTH = 284;
const TERMINAL_SIDEBAR_MIN_WIDTH = 200;
const TERMINAL_WORKSPACE_MIN_WIDTH = 360;
const TERMINAL_FILE_CONTEXT_MENU_WIDTH = 220;
const TERMINAL_FILE_CONTEXT_MENU_HEIGHT = 540;
const TERMINAL_DIRECTORY_CONTEXT_MENU_HEIGHT = 300;
const TERMINAL_MONITOR_REFRESH_MS = 5000;
const TERMINAL_TRANSFER_PANEL_DEFAULT_HEIGHT = 170;
const TERMINAL_TRANSFER_PANEL_MIN_HEIGHT = 96;
const TERMINAL_TRANSFER_PANEL_MAX_HEIGHT = 360;
const TERMINAL_DOWNLOAD_FILE_CONCURRENCY = 1;
const TERMINAL_DOWNLOAD_DIRECTORY_PICKER_ID = 'terminal-download-directory';
const TERMINAL_LOCAL_FILENAME_RESERVED_CHARS = /[<>:"/\\|?*\x00-\x1f]/g;
const TERMINAL_LOCAL_FILENAME_RESERVED_NAMES = new Set([
  'CON',
  'PRN',
  'AUX',
  'NUL',
  'COM1',
  'COM2',
  'COM3',
  'COM4',
  'COM5',
  'COM6',
  'COM7',
  'COM8',
  'COM9',
  'LPT1',
  'LPT2',
  'LPT3',
  'LPT4',
  'LPT5',
  'LPT6',
  'LPT7',
  'LPT8',
  'LPT9',
]);
const terminalHighlightRules: TerminalHighlightRule[] = [
  {
    name: 'danger',
    pattern: /\b(error|failed|failure|exception|traceback|denied|refused|fatal|critical)\b/gi,
    open: '\x1b[48;5;52m',
    close: '\x1b[49m',
  },
  {
    name: 'warning',
    pattern: /\b(warn|warning|timeout|retry|deprecated|unreachable)\b/gi,
    open: '\x1b[48;5;58m',
    close: '\x1b[49m',
  },
  {
    name: 'success',
    pattern: /\b(success|succeeded|ok|done|completed|running|started|active)\b/gi,
    open: '\x1b[48;5;22m',
    close: '\x1b[49m',
  },
  {
    name: 'ip',
    pattern: /\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b/g,
    open: '\x1b[48;5;24m',
    close: '\x1b[49m',
  },
];
const initialTerminalFileEntries: TerminalFileEntry[] = [
  { name: '..', type: 'directory', modifiedAt: '', path: '..', permissions: '', owner: '', group: '' },
  { name: '.ansible', type: 'directory', modifiedAt: '2025/03/11 13:20', path: '~/.ansible', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.cache', type: 'directory', modifiedAt: '2025/05/07 17:53', path: '~/.cache', permissions: 'drwxr-xr-x', owner: 'root', group: 'root' },
  { name: '.config', type: 'directory', modifiedAt: '2025/05/07 16:47', path: '~/.config', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.ctcss', type: 'directory', modifiedAt: '2025/08/01 11:23', path: '~/.ctcss', permissions: 'd---------', owner: 'root', group: 'root' },
  { name: '.docker', type: 'directory', modifiedAt: '2026/01/20 20:58', path: '~/.docker', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.ssh', type: 'directory', modifiedAt: '2025/03/11 20:58', path: '~/.ssh', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.vim', type: 'directory', modifiedAt: '2026/04/10 17:15', path: '~/.vim', permissions: 'drwxr-xr-x', owner: 'root', group: 'root' },
  { name: 'download_test', type: 'directory', modifiedAt: '2026/01/14 19:03', path: '~/download_test', permissions: 'drwxr-xr-x', owner: 'root', group: 'root' },
  { name: '.bash_history', type: 'file', modifiedAt: '2026/05/25 11:07', path: '~/.bash_history', size: 39200, permissions: '-rw-------', owner: 'root', group: 'root' },
  { name: '.bashrc', type: 'file', modifiedAt: '2019/12/05 13:37', path: '~/.bashrc', size: 241, permissions: '-rw-r--r--', owner: 'root', group: 'root' },
  { name: '.lesshst', type: 'file', modifiedAt: '2025/10/15 16:48', path: '~/.lesshst', size: 1200, permissions: '-rw-------', owner: 'root', group: 'root' },
];

const initialSelectedTerminalFile = initialTerminalFileEntries.find((entry) => entry.type === 'file') ?? null;
const terminalFileEntries = ref<TerminalFileEntry[]>(initialTerminalFileEntries);
const selectedTerminalFile = ref<TerminalFileEntry | null>(initialSelectedTerminalFile);
const selectedTerminalFilePaths = ref<Set<string>>(new Set(initialSelectedTerminalFile ? [initialSelectedTerminalFile.path] : []));
const terminalFileSelectionAnchorPath = ref(initialSelectedTerminalFile?.path ?? '');
const terminalFilePath = ref('.');
const terminalFileListProtocol = ref('');
const terminalFileListError = ref('');
const isTerminalFileFollowingCwd = ref(false);
const isTerminalFileListLoading = ref(false);
const terminalFileListRef = ref<HTMLElement | null>(null);
const terminalFileUploadInput = ref<HTMLInputElement | null>(null);
const terminalFolderUploadInput = ref<HTMLInputElement | null>(null);
const terminalFileRenameInput = ref<HTMLInputElement | null>(null);
const terminalFileBrowserRef = ref<HTMLElement | null>(null);
const terminalFileContextMenu = ref<TerminalFileContextMenuState>({
  visible: false,
  x: 0,
  y: 0,
  entry: null,
});
const terminalDirectoryContextMenu = ref<Omit<TerminalFileContextMenuState, 'entry'>>({
  visible: false,
  x: 0,
  y: 0,
});
const terminalFileRename = ref<TerminalFileRenameState | null>(null);
const terminalFileDeleteDialog = ref<TerminalFileDeleteDialogState>({
  visible: false,
  entry: null,
  entries: [],
  deleting: false,
  error: '',
});
const isTerminalFileDragOver = ref(false);
const terminalFileMarquee = ref<TerminalFileMarqueeState>({
  active: false,
  startX: 0,
  startY: 0,
  currentX: 0,
  currentY: 0,
  additive: false,
  basePaths: [],
});
let shouldSuppressTerminalFileClick = false;
const terminalTransferRecords = ref<TerminalTransferRecord[]>([]);
const terminalDownloadProtocol = ref<TerminalDownloadProtocol>('auto');
const terminalTransferPanelHeight = ref(TERMINAL_TRANSFER_PANEL_DEFAULT_HEIGHT);
const isTerminalTransferPanelResizing = ref(false);
let terminalTransferResizeStartY = 0;
let terminalTransferResizeStartHeight = TERMINAL_TRANSFER_PANEL_DEFAULT_HEIGHT;
const terminalFileCreateDialog = ref<TerminalFileCreateDialogState>({
  visible: false,
  mode: 'file',
  name: '',
  targetPath: '',
  octalMode: '0644',
  openAfterCreate: false,
  saving: false,
  error: '',
});
const terminalFilePropertiesDialog = ref<TerminalFilePropertiesDialogState>({
  visible: false,
  loading: false,
  saving: false,
  error: '',
  entry: null,
  properties: null,
  draft: { owner: '', group: '', octalMode: '0000' },
  recursive: false,
});
let terminalFileListRequestId = 0;
const terminalMonitorData = ref<TerminalMonitorResponse | null>(null);
const isTerminalMonitorLoading = ref(false);
const terminalMonitorError = ref('');
let terminalMonitorRequestId = 0;
let terminalMonitorTimer: ReturnType<typeof window.setInterval> | null = null;

const groups = ref<TerminalGroup[]>([]);
const collapsed = ref<Set<number>>(new Set());
const rootExpanded = ref(true);
const rootLabel = ref(readTerminalRootLabel());
const search = ref('');
const tabs = ref<TerminalTab[]>([]);
const activeTabId = ref<string | null>(null);
const isTerminalTabMenuOpen = ref(false);
const terminalTabsRef = ref<HTMLElement | null>(null);
const canScrollTerminalTabsLeft = ref(false);
const canScrollTerminalTabsRight = ref(false);
const isLoadingTree = ref(false);
const treeError = ref('');
const highlightEnabled = ref(true);
const terminalSidebarMode = ref<TerminalSidebarMode>('hosts');
const sidebarWidth = ref(readTerminalSidebarWidth());
const isTerminalSidebarCollapsed = ref(readTerminalSidebarCollapsed());
const isResizingSidebar = ref(false);
let sidebarResizeStartX = 0;
let sidebarResizeStartWidth = TERMINAL_SIDEBAR_DEFAULT_WIDTH;
const terminalContainers = new Map<string, HTMLElement>();
const pendingConnectTabIds: string[] = [];
const connectingTabIds = new Set<string>();

const rows = computed(() => {
  const query = search.value.trim().toLowerCase();
  const root: TreeRow = { kind: 'root', group: terminalRoot.value, level: 0 };
  const treeRows = rootExpanded.value ? [root, ...flattenTerminalRows(groups.value, collapsed.value, 1)] : [root];
  return treeRows.filter((row) => {
    if (!query) return true;
    if (row.kind === 'root') return row.group.name.toLowerCase().includes(query);
    if (row.kind === 'group') return row.group.name.toLowerCase().includes(query);
    return [row.host.name, row.host.privateIp, row.host.publicIp, row.host.loginUser]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});

const activeTab = computed(() => tabs.value.find((tab) => tab.id === activeTabId.value) ?? null);
const activeTerminalNodeName = computed(() => activeTab.value?.host.name ?? '未选择主机');
const terminalSidebarToggleLabel = computed(() => (isTerminalSidebarCollapsed.value ? '展开侧栏' : '收起侧栏'));
const selectedTerminalFiles = computed(() =>
  terminalFileEntries.value.filter((entry) => selectedTerminalFilePaths.value.has(entry.path) && !isParentDirectoryEntry(entry)),
);
const selectedTerminalDownloadableEntries = computed(() => selectedTerminalFiles.value);
const selectedTerminalFileCount = computed(() => selectedTerminalFiles.value.length);
const canDownloadSelectedTerminalFiles = computed(() => selectedTerminalDownloadableEntries.value.length > 0);
const terminalFileSelectionStatusText = computed(() => {
  const total = terminalFileEntries.value.length;
  return selectedTerminalFileCount.value > 1 ? `已选 ${selectedTerminalFileCount.value} 项 / 共 ${total} 项` : `共 ${total} 项`;
});
const terminalFileMarqueeStyle = computed<Record<string, string>>(() => {
  const state = terminalFileMarquee.value;
  if (!state.active) return {} as Record<string, string>;
  const left = Math.min(state.startX, state.currentX);
  const top = Math.min(state.startY, state.currentY);
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.abs(state.currentX - state.startX)}px`,
    height: `${Math.abs(state.currentY - state.startY)}px`,
  };
});
const terminalTransferPanelStyle = computed<Record<string, string>>(() => ({
  '--terminal-transfer-height': `${terminalTransferPanelHeight.value}px`,
}));
const hasRunningTerminalTransfers = computed(() => terminalTransferRecords.value.some((record) => isTerminalTransferActive(record)));
const hasClearableTerminalTransfers = computed(() => terminalTransferRecords.value.some((record) => !isTerminalTransferActive(record)));
const terminalFileProtocolLabel = computed(() => formatTerminalFileProtocol(terminalFileListProtocol.value));
const terminalFileStatus = computed<'idle' | 'loading' | 'success' | 'error'>(() => {
  if (isTerminalFileListLoading.value) return 'loading';
  if (terminalFileListError.value) return 'error';
  if (terminalFileListProtocol.value) return 'success';
  return 'idle';
});
const terminalFileStatusText = computed(() => {
  if (terminalFileStatus.value === 'loading') return '读取中';
  if (terminalFileStatus.value === 'error') return '读取失败';
  if (terminalFileStatus.value === 'success') return terminalFileProtocolLabel.value;
  return '待加载';
});
const terminalFileFollowCwdLabel = computed(() => (isTerminalFileFollowingCwd.value ? '停止跟踪终端目录' : '跟踪终端目录'));
const terminalMonitorNodeName = computed(() => activeTab.value?.host.name ?? '请选择服务器');
const terminalFileContextMenuItems = computed<TerminalFileContextMenuItem[]>(() => {
  const entry = terminalFileContextMenu.value.entry;
  const targetEntries = getTerminalFileActionEntries(entry);
  const isMultiple = targetEntries.length > 1;
  const isSingle = targetEntries.length === 1;
  const hasEntry = Boolean(entry);
  const isParent = isParentDirectoryEntry(entry);
  const isDirectory = entry?.type === 'directory';
  const path = entry ? getTerminalFileResolvedPath(entry) : '';
  const name = entry?.name ?? '';
  const directoryPath = entry ? getTerminalFileDirectoryPath(entry) : '';
  const targetPathsText = targetEntries.map((item) => getTerminalFileResolvedPath(item)).join('\n');
  const targetNamesText = targetEntries.map((item) => item.name).join('\n');
  const canDownload = targetEntries.length > 0;

  const items: TerminalFileContextMenuItem[] = [
    { id: 'open', label: '打开', icon: 'folder', enabled: Boolean(isDirectory) && (isSingle || isParent), action: () => { if (entry) openTerminalDirectory(entry); } },
    { id: 'refresh', label: '刷新', icon: 'refresh', enabled: true, action: () => loadTerminalDirectory() },
    { id: 'upload', label: '上传到当前文件夹...', icon: 'upload', enabled: hasEntry && !isParent, action: () => openTerminalUpload() },
    { id: 'download', label: isMultiple ? '下载所选到目录...' : '下载到目录...', icon: 'download', enabled: canDownload, action: () => downloadTerminalFiles(targetEntries) },
    { id: 'rename', label: '重命名...', icon: 'edit', enabled: false, separatorBefore: true, action: () => undefined },
    { id: 'move', label: '移动到...', icon: 'moveRight', enabled: false, action: () => undefined },
    { id: 'delete', label: isMultiple ? '删除所选' : '删除', icon: 'trash', enabled: false, danger: true, action: () => undefined },
    { id: 'favorite', label: '添加到收藏夹', icon: 'bookmark', enabled: false, separatorBefore: true, action: () => undefined },
    { id: 'copy-path', label: isMultiple ? '复制所选路径' : '复制路径', icon: 'copy', enabled: targetEntries.length > 0 || hasEntry, separatorBefore: true, action: () => copyTerminalFileText(targetEntries.length > 0 ? targetPathsText : path) },
    { id: 'copy-name', label: isMultiple ? '复制所选名称' : '复制名称', icon: 'copy', enabled: targetEntries.length > 0, action: () => copyTerminalFileText(isMultiple ? targetNamesText : name) },
    { id: 'copy-directory', label: '复制目录路径', icon: 'folder', enabled: hasEntry && !isParent, action: () => copyTerminalFileText(directoryPath) },
    { id: 'send-path', label: isMultiple ? '将所选路径发送到终端' : '将路径发送到终端', icon: 'cornerDownLeft', enabled: targetEntries.length > 0 || hasEntry, separatorBefore: true, action: () => sendTerminalFileTextToActiveTerminal(targetEntries.length > 0 ? targetPathsText : path) },
    { id: 'send-name', label: isMultiple ? '将所选名称发送到终端' : '将名称发送到终端', icon: 'chevronRight', enabled: targetEntries.length > 0, action: () => sendTerminalFileTextToActiveTerminal(isMultiple ? targetNamesText : name) },
    { id: 'send-directory', label: '将目录路径发送到终端', icon: 'chevronsRight', enabled: hasEntry && !isParent, action: () => sendTerminalFileTextToActiveTerminal(directoryPath) },
    { id: 'properties', label: '属性...', icon: 'info', enabled: hasEntry && !isParent && isSingle, separatorBefore: true, action: async () => { if (entry) await openTerminalFileProperties(entry); } },
  ];
  return items.map((item) => {
    if (item.id === 'rename') {
      return { ...item, enabled: hasEntry && !isParent && isSingle, action: () => { if (entry) startTerminalFileRename(entry); } };
    }
    if (item.id === 'delete') {
      return { ...item, enabled: targetEntries.length > 0, action: () => openTerminalFileDeleteDialog(targetEntries) };
    }
    return item;
  });
});
const terminalDirectoryContextMenuItems = computed<TerminalFileContextMenuItem[]>(() => [
  { id: 'refresh', label: '刷新', icon: 'refresh', enabled: Boolean(activeTab.value), action: () => loadTerminalDirectory() },
  {
    id: 'upload',
    label: '上传到当前文件夹...',
    icon: 'upload',
    enabled: Boolean(activeTab.value),
    action: () => undefined,
    children: [
      { id: 'upload-file', label: '上传文件', icon: 'file', enabled: Boolean(activeTab.value), action: () => openTerminalUpload() },
      { id: 'upload-folder', label: '上传文件夹', icon: 'folder', enabled: Boolean(activeTab.value), action: () => openTerminalFolderUpload() },
    ],
  },
  { id: 'create-file', label: '新建文件', icon: 'file', enabled: Boolean(activeTab.value), separatorBefore: true, action: () => openTerminalFileCreateDialog('file') },
  { id: 'create-directory', label: '新建文件夹', icon: 'folderPlus', enabled: Boolean(activeTab.value), action: () => openTerminalFileCreateDialog('directory') },
  { id: 'create-symlink', label: '新建符号链接', icon: 'link', enabled: Boolean(activeTab.value), action: () => openTerminalFileCreateDialog('symlink') },
  { id: 'copy-directory', label: '复制目录路径', icon: 'copy', enabled: Boolean(activeTab.value), separatorBefore: true, action: () => copyTerminalFileText(terminalFilePath.value) },
  { id: 'send-directory', label: '将目录路径发送到终端', icon: 'cornerDownLeft', enabled: Boolean(activeTab.value), action: () => sendTerminalFileTextToActiveTerminal(terminalFilePath.value) },
  { id: 'properties', label: '属性', icon: 'info', enabled: Boolean(activeTab.value), separatorBefore: true, action: () => openTerminalCurrentDirectoryProperties() },
]);
const terminalRoot = computed<TerminalRoot>(() => ({
  id: null,
  name: rootLabel.value,
  count: countTerminalHosts(groups.value),
}));

const workspaceTitle = computed(() => {
  if (!activeTab.value) return '选择左侧主机开始连接';
  const host = activeTab.value.host;
  return `${host.name} / ${host.publicIp || host.privateIp}:${host.port}`;
});

function selectTerminalFile(entry: TerminalFileEntry, event?: MouseEvent | KeyboardEvent) {
  if (!activeTab.value) return;
  if (shouldSuppressTerminalFileClick) {
    shouldSuppressTerminalFileClick = false;
    return;
  }
  if (event?.shiftKey && terminalFileSelectionAnchorPath.value) {
    selectTerminalFileRange(terminalFileSelectionAnchorPath.value, entry);
    return;
  }
  setTerminalFileSelection([entry], isParentDirectoryEntry(entry) ? '' : entry.path);
}

function setTerminalFileSelection(entries: TerminalFileEntry[], anchorPath = entries[0]?.path ?? '') {
  const selectableEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  selectedTerminalFilePaths.value = new Set(selectableEntries.map((entry) => entry.path));
  selectedTerminalFile.value = selectableEntries[selectableEntries.length - 1] ?? entries[entries.length - 1] ?? null;
  terminalFileSelectionAnchorPath.value = anchorPath && !isParentDirectoryEntry(entries.find((entry) => entry.path === anchorPath)) ? anchorPath : selectableEntries[0]?.path ?? '';
}

function selectTerminalFileRange(anchorPath: string, entry: TerminalFileEntry) {
  const anchorIndex = terminalFileEntries.value.findIndex((item) => item.path === anchorPath);
  const targetIndex = terminalFileEntries.value.findIndex((item) => item.path === entry.path);
  if (anchorIndex === -1 || targetIndex === -1) {
    setTerminalFileSelection([entry], isParentDirectoryEntry(entry) ? '' : entry.path);
    return;
  }
  const start = Math.min(anchorIndex, targetIndex);
  const end = Math.max(anchorIndex, targetIndex);
  const range = terminalFileEntries.value.slice(start, end + 1).filter((item) => !isParentDirectoryEntry(item));
  setTerminalFileSelection(range, anchorPath);
  selectedTerminalFile.value = isParentDirectoryEntry(entry) ? range[range.length - 1] ?? null : entry;
}

function startTerminalFileMarquee(event: MouseEvent) {
  if (!activeTab.value || event.button !== 0 || !terminalFileListRef.value) return;
  const target = event.target as Element | null;
  const currentTarget = event.currentTarget as Element | null;
  const isListBlank = target === currentTarget && currentTarget?.classList.contains('terminal-file-list');
  const isFileRow = currentTarget?.classList.contains('terminal-file-item') && !target?.closest('input');
  if (!isListBlank && !isFileRow) return;
  event.preventDefault();
  closeTerminalContextMenus();
  const point = getTerminalFileListPoint(event);
  terminalFileMarquee.value = {
    active: true,
    startX: point.x,
    startY: point.y,
    currentX: point.x,
    currentY: point.y,
    additive: event.shiftKey || event.ctrlKey || event.metaKey,
    basePaths: Array.from(selectedTerminalFilePaths.value),
  };
  updateTerminalFileMarqueeSelection();
  window.addEventListener('mousemove', moveTerminalFileMarquee);
  window.addEventListener('mouseup', stopTerminalFileMarquee);
}

function moveTerminalFileMarquee(event: MouseEvent) {
  if (!terminalFileMarquee.value.active) return;
  const point = getTerminalFileListPoint(event);
  terminalFileMarquee.value = { ...terminalFileMarquee.value, currentX: point.x, currentY: point.y };
  updateTerminalFileMarqueeSelection();
}

function stopTerminalFileMarquee() {
  if (!terminalFileMarquee.value.active) return;
  const state = terminalFileMarquee.value;
  shouldSuppressTerminalFileClick = Math.abs(state.currentX - state.startX) > 4 || Math.abs(state.currentY - state.startY) > 4;
  updateTerminalFileMarqueeSelection();
  terminalFileMarquee.value = { ...terminalFileMarquee.value, active: false };
  window.removeEventListener('mousemove', moveTerminalFileMarquee);
  window.removeEventListener('mouseup', stopTerminalFileMarquee);
  window.setTimeout(() => {
    shouldSuppressTerminalFileClick = false;
  }, 0);
}

function getTerminalFileListPoint(event: MouseEvent) {
  const list = terminalFileListRef.value;
  if (!list) return { x: 0, y: 0 };
  const rect = list.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top + list.scrollTop,
  };
}

function updateTerminalFileMarqueeSelection() {
  const list = terminalFileListRef.value;
  if (!list) return;
  const state = terminalFileMarquee.value;
  const marquee = {
    left: Math.min(state.startX, state.currentX),
    right: Math.max(state.startX, state.currentX),
    top: Math.min(state.startY, state.currentY),
    bottom: Math.max(state.startY, state.currentY),
  };
  const listRect = list.getBoundingClientRect();
  const selectedEntries = terminalFileEntries.value.filter((entry) => {
    if (isParentDirectoryEntry(entry)) return false;
    const row = list.querySelector<HTMLElement>(`[data-terminal-file-path="${cssEscape(entry.path)}"]`);
    if (!row) return false;
    const rowRect = row.getBoundingClientRect();
    const rowBox = {
      left: rowRect.left - listRect.left,
      right: rowRect.right - listRect.left,
      top: rowRect.top - listRect.top + list.scrollTop,
      bottom: rowRect.bottom - listRect.top + list.scrollTop,
    };
    return boxesIntersect(marquee, rowBox);
  });
  const nextPaths = new Set(state.additive ? state.basePaths : []);
  for (const entry of selectedEntries) nextPaths.add(entry.path);
  const nextEntries = terminalFileEntries.value.filter((entry) => nextPaths.has(entry.path) && !isParentDirectoryEntry(entry));
  setTerminalFileSelection(nextEntries, nextEntries[0]?.path ?? '');
}

function boxesIntersect(
  first: { left: number; right: number; top: number; bottom: number },
  second: { left: number; right: number; top: number; bottom: number },
) {
  return first.left <= second.right && first.right >= second.left && first.top <= second.bottom && first.bottom >= second.top;
}

function cssEscape(value: string) {
  const escape = window.CSS?.escape;
  return escape ? escape(value) : value.replace(/["\\]/g, '\\$&');
}

function syncTerminalFileSelectionAfterEntriesChange(preferredEntry?: TerminalFileEntry | null) {
  const availablePaths = new Set(terminalFileEntries.value.map((entry) => entry.path));
  const nextPaths = new Set(Array.from(selectedTerminalFilePaths.value).filter((path) => availablePaths.has(path)));
  if (preferredEntry && !isParentDirectoryEntry(preferredEntry) && availablePaths.has(preferredEntry.path)) {
    nextPaths.add(preferredEntry.path);
  }
  selectedTerminalFilePaths.value = nextPaths;
  selectedTerminalFile.value =
    (preferredEntry && availablePaths.has(preferredEntry.path) ? preferredEntry : null) ??
    terminalFileEntries.value.find((entry) => nextPaths.has(entry.path)) ??
    getDefaultSelectedTerminalFile(terminalFileEntries.value);
  if (selectedTerminalFile.value && !isParentDirectoryEntry(selectedTerminalFile.value)) {
    terminalFileSelectionAnchorPath.value = selectedTerminalFile.value.path;
    if (!selectedTerminalFilePaths.value.has(selectedTerminalFile.value.path)) {
      selectedTerminalFilePaths.value = new Set([selectedTerminalFile.value.path]);
    }
  } else {
    terminalFileSelectionAnchorPath.value = '';
  }
}

function isTerminalFileSelected(entry: TerminalFileEntry) {
  return selectedTerminalFilePaths.value.has(entry.path);
}

function getTerminalFileActionEntries(entry: TerminalFileEntry | null | undefined = selectedTerminalFile.value) {
  if (entry && !isParentDirectoryEntry(entry) && selectedTerminalFilePaths.value.has(entry.path)) {
    return selectedTerminalFiles.value;
  }
  if (entry && !isParentDirectoryEntry(entry)) return [entry];
  return selectedTerminalFiles.value;
}

function openTerminalFileContextMenu(entry: TerminalFileEntry, event: MouseEvent) {
  if (!activeTab.value) return;
  event.preventDefault();
  event.stopPropagation();
  if (!isTerminalFileSelected(entry)) {
    setTerminalFileSelection([entry], isParentDirectoryEntry(entry) ? '' : entry.path);
  } else {
    selectedTerminalFile.value = entry;
  }
  closeTerminalDirectoryContextMenu();
  terminalFileContextMenu.value = {
    visible: true,
    ...getTerminalFileContextMenuPosition(event),
    entry,
  };
}

function openTerminalDirectoryContextMenu(event: MouseEvent) {
  if (!activeTab.value) return;
  const target = event.target as Element | null;
  if (target?.closest('.terminal-file-item') || target?.closest('.terminal-file-context-menu')) return;
  event.preventDefault();
  event.stopPropagation();
  setTerminalFileSelection([], '');
  closeTerminalFileContextMenu();
  terminalDirectoryContextMenu.value = {
    visible: true,
    ...getTerminalFileContextMenuPosition(event, TERMINAL_DIRECTORY_CONTEXT_MENU_HEIGHT),
  };
}

function getTerminalFileContextMenuPosition(event: MouseEvent, menuHeight = TERMINAL_FILE_CONTEXT_MENU_HEIGHT) {
  const padding = 8;
  return {
    x: Math.max(padding, Math.min(event.clientX, window.innerWidth - TERMINAL_FILE_CONTEXT_MENU_WIDTH - padding)),
    y: Math.max(padding, Math.min(event.clientY, window.innerHeight - menuHeight - padding)),
  };
}

function isTerminalContextSubmenuLeft(x: number) {
  return x + TERMINAL_FILE_CONTEXT_MENU_WIDTH * 2 + 16 > window.innerWidth;
}

function closeTerminalFileContextMenu() {
  if (!terminalFileContextMenu.value.visible) return;
  terminalFileContextMenu.value = { visible: false, x: 0, y: 0, entry: null };
}

function closeTerminalDirectoryContextMenu() {
  if (!terminalDirectoryContextMenu.value.visible) return;
  terminalDirectoryContextMenu.value = { visible: false, x: 0, y: 0 };
}

function toggleTerminalTabMenu() {
  isTerminalTabMenuOpen.value = !isTerminalTabMenuOpen.value;
}

function closeTerminalTabMenu() {
  isTerminalTabMenuOpen.value = false;
}

function syncTerminalTabsScrollState() {
  const tabsElement = terminalTabsRef.value;
  if (!tabsElement) {
    canScrollTerminalTabsLeft.value = false;
    canScrollTerminalTabsRight.value = false;
    return;
  }

  const maxScrollLeft = Math.max(0, tabsElement.scrollWidth - tabsElement.clientWidth);
  canScrollTerminalTabsLeft.value = tabsElement.scrollLeft > 1;
  canScrollTerminalTabsRight.value = tabsElement.scrollLeft < maxScrollLeft - 1;
}

function syncTerminalTabsScrollStateSoon() {
  window.requestAnimationFrame(syncTerminalTabsScrollState);
}

function scrollTerminalTabs(direction: 'left' | 'right') {
  const tabsElement = terminalTabsRef.value;
  if (!tabsElement) return;
  const distance = Math.max(120, tabsElement.clientWidth * 0.7);
  tabsElement.scrollBy({
    left: direction === 'left' ? -distance : distance,
    behavior: 'smooth',
  });
  window.setTimeout(syncTerminalTabsScrollState, 220);
}

function scrollActiveTerminalTabIntoView() {
  const tabsElement = terminalTabsRef.value;
  if (!tabsElement || !activeTabId.value) {
    syncTerminalTabsScrollStateSoon();
    return;
  }
  const activeButton = tabsElement.querySelector<HTMLElement>(`[data-terminal-tab-id="${cssEscape(activeTabId.value)}"]`);
  activeButton?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  window.setTimeout(syncTerminalTabsScrollState, 220);
}

function closeTerminalContextMenus() {
  closeTerminalFileContextMenu();
  closeTerminalDirectoryContextMenu();
  closeTerminalTabMenu();
}

async function selectTerminalTabFromMenu(tab: TerminalTab) {
  closeTerminalTabMenu();
  await activateTab(tab.id);
}

async function runTerminalFileContextMenuItem(item: TerminalFileContextMenuItem) {
  if (!item.enabled) return;
  if (item.children?.length) return;
  closeTerminalContextMenus();
  await item.action();
}

function startTerminalFileRename(entry: TerminalFileEntry) {
  if (!activeTab.value || isParentDirectoryEntry(entry)) return;
  setTerminalFileSelection([entry], entry.path);
  terminalFileRename.value = {
    path: entry.path,
    originalName: entry.name,
    draftName: entry.name,
    saving: false,
    error: '',
  };
  void nextTick(() => {
    terminalFileRenameInput.value?.focus();
    terminalFileRenameInput.value?.select();
  });
}

function setTerminalFileRenameInput(element: Element | ComponentPublicInstance | null) {
  terminalFileRenameInput.value = element instanceof HTMLInputElement ? element : null;
}

function cancelTerminalFileRename() {
  terminalFileRename.value = null;
}

async function saveTerminalFileRename() {
  const state = terminalFileRename.value;
  if (!activeTab.value || !state || state.saving) return;
  const newName = state.draftName.trim();
  if (!newName) {
    terminalFileRename.value = { ...state, error: '请输入新名称' };
    return;
  }
  if (newName === state.originalName) {
    cancelTerminalFileRename();
    return;
  }
  terminalFileRename.value = { ...state, saving: true, error: '' };
  try {
    await apiPost<TerminalFileProperties>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/rename/`,
      { path: state.path, newName },
    );
    terminalFileRename.value = null;
    await loadTerminalDirectory(terminalFilePath.value);
  } catch (error) {
    terminalFileRename.value = {
      ...state,
      saving: false,
      error: error instanceof Error ? error.message : '重命名失败',
    };
    void nextTick(() => terminalFileRenameInput.value?.focus());
  }
}

function isTerminalFileRenaming(entry: TerminalFileEntry) {
  return terminalFileRename.value?.path === entry.path;
}

function openTerminalFileDeleteDialog(target: TerminalFileEntry | TerminalFileEntry[] | null = getTerminalFileActionEntries()) {
  if (!activeTab.value) return;
  const entries = Array.isArray(target) ? target : target ? [target] : [];
  const deletableEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  if (!deletableEntries.length) return;
  setTerminalFileSelection(deletableEntries, deletableEntries[0].path);
  terminalFileDeleteDialog.value = {
    visible: true,
    entry: deletableEntries[0],
    entries: deletableEntries,
    deleting: false,
    error: '',
  };
}

function closeTerminalFileDeleteDialog() {
  if (terminalFileDeleteDialog.value.deleting) return;
  terminalFileDeleteDialog.value = {
    visible: false,
    entry: null,
    entries: [],
    deleting: false,
    error: '',
  };
}

async function confirmTerminalFileDelete() {
  const dialog = terminalFileDeleteDialog.value;
  const entries = dialog.entries.length ? dialog.entries : dialog.entry ? [dialog.entry] : [];
  if (!activeTab.value || !entries.length || dialog.deleting) return;
  terminalFileDeleteDialog.value = { ...dialog, deleting: true, error: '' };
  try {
    for (const entry of entries) {
      await apiPost<{ deleted: boolean }>(
        `/api/web-terminal/hosts/${activeTab.value.host.id}/files/delete/`,
        { path: entry.path },
      );
    }
    terminalFileDeleteDialog.value = { visible: false, entry: null, entries: [], deleting: false, error: '' };
    setTerminalFileSelection([], '');
    await loadTerminalDirectory(terminalFilePath.value);
  } catch (error) {
    terminalFileDeleteDialog.value = {
      ...dialog,
      deleting: false,
      error: error instanceof Error ? error.message : '删除失败',
    };
  }
}

function openTerminalFileCreateDialog(mode: TerminalFileCreateMode) {
  if (!activeTab.value) return;
  const isDirectory = mode === 'directory';
  terminalFileCreateDialog.value = {
    visible: true,
    mode,
    name: mode === 'file' ? 'new-file' : isDirectory ? 'new-folder' : 'new-link',
    targetPath: '',
    octalMode: isDirectory ? '0755' : '0644',
    openAfterCreate: isDirectory,
    saving: false,
    error: '',
  };
}

function closeTerminalFileCreateDialog() {
  if (terminalFileCreateDialog.value.saving) return;
  terminalFileCreateDialog.value = {
    visible: false,
    mode: 'file',
    name: '',
    targetPath: '',
    octalMode: '0644',
    openAfterCreate: false,
    saving: false,
    error: '',
  };
}

async function saveTerminalFileCreateDialog() {
  const dialog = terminalFileCreateDialog.value;
  if (!activeTab.value || !dialog.visible || dialog.saving) return;
  const name = dialog.name.trim();
  if (!name) {
    terminalFileCreateDialog.value = { ...dialog, error: '请输入名称' };
    return;
  }
  if (dialog.mode === 'symlink' && !dialog.targetPath.trim()) {
    terminalFileCreateDialog.value = { ...dialog, error: '请输入目标路径' };
    return;
  }
  terminalFileCreateDialog.value = { ...dialog, saving: true, error: '' };
  try {
    const endpoint =
      dialog.mode === 'file'
        ? 'create-file'
        : dialog.mode === 'directory'
          ? 'create-directory'
          : 'create-symlink';
    const payload =
      dialog.mode === 'file'
        ? { directory: terminalFilePath.value, filename: name, octalMode: normalizeTerminalFileOctalMode(dialog.octalMode) }
        : dialog.mode === 'directory'
          ? { directory: terminalFilePath.value, dirname: name, octalMode: normalizeTerminalFileOctalMode(dialog.octalMode) }
          : { directory: terminalFilePath.value, linkName: name, targetPath: dialog.targetPath.trim() };
    const created = await apiPost<TerminalFileProperties>(`/api/web-terminal/hosts/${activeTab.value.host.id}/files/${endpoint}/`, payload);
    terminalFileCreateDialog.value = {
      visible: false,
      mode: 'file',
      name: '',
      targetPath: '',
      octalMode: '0644',
      openAfterCreate: false,
      saving: false,
      error: '',
    };
    if (dialog.mode === 'directory' && dialog.openAfterCreate) {
      await loadTerminalDirectory(created.path);
      return;
    }
    await loadTerminalDirectory(terminalFilePath.value);
    const createdEntry = terminalFileEntries.value.find((entry) => entry.path === created.path || entry.name === created.name) ?? null;
    setTerminalFileSelection(createdEntry ? [createdEntry] : [], createdEntry?.path ?? '');
  } catch (error) {
    terminalFileCreateDialog.value = {
      ...dialog,
      saving: false,
      error: error instanceof Error ? error.message : '创建失败',
    };
  }
}

function terminalFileCreateTitle() {
  if (terminalFileCreateDialog.value.mode === 'file') return '新建文件';
  if (terminalFileCreateDialog.value.mode === 'directory') return '新建文件夹';
  return '新建符号链接';
}

function terminalFileCreateNameLabel() {
  if (terminalFileCreateDialog.value.mode === 'directory') return '目录：';
  if (terminalFileCreateDialog.value.mode === 'file') return '文件：';
  return '名称：';
}

function terminalFileCreateOpenLabel() {
  return terminalFileCreateDialog.value.mode === 'directory' ? '创建后打开目录' : '创建后打开文件';
}

function isTerminalFileCreatePermissionChecked(mask: number) {
  const mode = Number.parseInt(terminalFileCreateDialog.value.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}

function setTerminalFileCreatePermission(mask: number, checked: boolean) {
  const current = Number.parseInt(terminalFileCreateDialog.value.octalMode || '0', 8) || 0;
  const next = checked ? current | mask : current & ~mask;
  terminalFileCreateDialog.value.octalMode = (next & 0o7777).toString(8).padStart(4, '0');
}

function setTerminalFileCreatePermissionFromEvent(mask: number, event: Event) {
  setTerminalFileCreatePermission(mask, (event.target as HTMLInputElement).checked);
}

function getTerminalFileCreateSpecialOctalDigit() {
  return normalizeTerminalFileOctalMode(terminalFileCreateDialog.value.octalMode).charAt(0);
}

function getTerminalFileCreateStandardOctalMode() {
  return normalizeTerminalFileOctalMode(terminalFileCreateDialog.value.octalMode).slice(1);
}

function updateTerminalFileCreateOctalMode(event: Event) {
  const input = event.target as HTMLInputElement;
  const standardMode = String(input.value || '').replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  terminalFileCreateDialog.value.octalMode = `${getTerminalFileCreateSpecialOctalDigit()}${standardMode}`;
}

function openTerminalCurrentDirectoryProperties() {
  if (!activeTab.value) return;
  void openTerminalFileProperties({
    name: currentTerminalDirectoryName(),
    type: 'directory',
    modifiedAt: '',
    path: terminalFilePath.value,
  });
}

function currentTerminalDirectoryName() {
  const value = String(terminalFilePath.value || '.').replace(/\/+$/, '');
  if (!value || value === '.') return '.';
  if (value === '/') return '/';
  return value.split('/').filter(Boolean).pop() || value;
}

async function openTerminalFileProperties(entry: TerminalFileEntry) {
  if (!activeTab.value || isParentDirectoryEntry(entry)) return;
  setTerminalFileSelection([entry], entry.path);
  terminalFilePropertiesDialog.value = {
    visible: true,
    loading: true,
    saving: false,
    error: '',
    entry,
    properties: null,
    draft: { owner: '', group: '', octalMode: '0000' },
    recursive: false,
  };
  try {
    const properties = mergeTerminalFilePropertiesEntryIdentity(
      await apiPost<TerminalFileProperties>(
        `/api/web-terminal/hosts/${activeTab.value.host.id}/files/properties/`,
        { path: entry.path },
      ),
      entry,
    );
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      loading: false,
      properties,
      draft: {
        owner: getTerminalFileOwnerLabel(properties),
        group: getTerminalFileGroupLabel(properties),
        octalMode: normalizeTerminalFileOctalMode(properties.octalMode),
      },
    };
  } catch (error) {
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      loading: false,
      error: error instanceof Error ? error.message : '属性读取失败',
    };
  }
}

function closeTerminalFilePropertiesDialog() {
  if (terminalFilePropertiesDialog.value.saving) return;
  terminalFilePropertiesDialog.value = {
    visible: false,
    loading: false,
    saving: false,
    error: '',
    entry: null,
    properties: null,
    draft: { owner: '', group: '', octalMode: '0000' },
    recursive: false,
  };
}

async function saveTerminalFileProperties() {
  const dialog = terminalFilePropertiesDialog.value;
  if (!activeTab.value || !dialog.properties || dialog.loading || dialog.saving) return;
  const recursive = dialog.properties.type === 'directory' && dialog.recursive;
  if (recursive && !window.confirm('确认要将所有权和权限递归应用到此目录及所有子目录/文件吗？')) return;
  terminalFilePropertiesDialog.value = { ...dialog, saving: true, error: '' };
  try {
    const properties = await apiPost<TerminalFileProperties>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/properties/update/`,
      {
        path: dialog.properties.path,
        owner: dialog.draft.owner,
        group: dialog.draft.group,
        octalMode: normalizeTerminalFileOctalMode(dialog.draft.octalMode),
        recursive,
      },
    );
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      saving: false,
      properties,
      draft: {
        owner: getTerminalFileOwnerLabel(properties),
        group: getTerminalFileGroupLabel(properties),
        octalMode: normalizeTerminalFileOctalMode(properties.octalMode),
      },
      recursive: false,
    };
    closeTerminalFilePropertiesDialog();
    await loadTerminalDirectory(terminalFilePath.value);
  } catch (error) {
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      saving: false,
      error: error instanceof Error ? error.message : '属性保存失败',
    };
  }
}

async function loadTerminalDirectory(path = terminalFilePath.value) {
  if (!activeTab.value) return;
  closeTerminalContextMenus();
  const targetPath = resolveTerminalDirectoryPath(path);
  const requestId = ++terminalFileListRequestId;
  isTerminalFileListLoading.value = true;
  terminalFileListError.value = '';

  try {
    const response = await apiPost<TerminalFileListResponse>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/list/`,
      { path: targetPath },
    );
    if (requestId !== terminalFileListRequestId) return;
    terminalFilePath.value = response.path;
    terminalFileEntries.value = sortTerminalFileEntries(response.entries);
    terminalFileListProtocol.value = response.protocol;
    syncTerminalFileSelectionAfterEntriesChange();
  } catch (error) {
    if (requestId !== terminalFileListRequestId) return;
    terminalFileListError.value = error instanceof Error ? error.message : '目录加载失败';
  } finally {
    if (requestId === terminalFileListRequestId) {
      isTerminalFileListLoading.value = false;
    }
  }
}

function openTerminalDirectory(entry: TerminalFileEntry) {
  if (!activeTab.value || entry.type !== 'directory') return;
  void loadTerminalDirectory(entry.path);
}

function openTerminalParentDirectory() {
  void loadTerminalDirectory(parentTerminalDirectoryPath(terminalFilePath.value));
}

function toggleTerminalFileCwdFollow() {
  isTerminalFileFollowingCwd.value = !isTerminalFileFollowingCwd.value;
  if (isTerminalFileFollowingCwd.value && activeTab.value?.currentCwd) {
    void loadTerminalDirectory(activeTab.value.currentCwd);
  }
}

function getTerminalFileDeleteDialogEntries() {
  const dialog = terminalFileDeleteDialog.value;
  return dialog.entries.length ? dialog.entries : dialog.entry ? [dialog.entry] : [];
}

function getTerminalFileDeleteDialogVisualType() {
  const entries = getTerminalFileDeleteDialogEntries();
  if (entries.length === 1) return entries[0].type;
  return entries.length > 0 && entries.every((entry) => entry.type === 'directory') ? 'directory' : 'file';
}

function getTerminalFileDeleteDialogTitle() {
  const entries = getTerminalFileDeleteDialogEntries();
  if (entries.length > 1) return `确定要删除所选 ${entries.length} 项吗？`;
  return `确定要删除“${entries[0]?.name ?? ''}”吗？`;
}

function getTerminalFileDeleteDialogDescription() {
  const entries = getTerminalFileDeleteDialogEntries();
  if (entries.length <= 1) {
    return `此操作会从远端主机删除该${entries[0]?.type === 'directory' ? '目录及其内容' : '文件'}。`;
  }
  const directoryCount = entries.filter((entry) => entry.type === 'directory').length;
  const fileCount = entries.length - directoryCount;
  if (directoryCount && fileCount) return `此操作会从远端主机删除 ${fileCount} 个文件和 ${directoryCount} 个目录及其内容。`;
  if (directoryCount) return `此操作会从远端主机删除 ${directoryCount} 个目录及其内容。`;
  return `此操作会从远端主机删除 ${fileCount} 个文件。`;
}

function resolveTerminalDirectoryPath(path: string) {
  const value = String(path || '.').trim();
  if (value === '..') return parentTerminalDirectoryPath(terminalFilePath.value);
  if (value.startsWith('/') || value.startsWith('~') || value === '.') return value;
  if (terminalFilePath.value === '/' || terminalFilePath.value === '') return `/${value}`;
  if (terminalFilePath.value === '.') return value;
  return `${terminalFilePath.value.replace(/\/+$/, '')}/${value}`;
}

function parentTerminalDirectoryPath(path: string) {
  const value = String(path || '.').replace(/\/+$/, '');
  if (!value || value === '.' || value === '~') return '/';
  if (value === '/') return '/';
  if (value.startsWith('~/')) {
    const parent = value.slice(0, value.lastIndexOf('/'));
    return parent || '/';
  }
  if (!value.startsWith('/')) return '/';
  const parent = value.slice(0, value.lastIndexOf('/'));
  return parent || '/';
}

function isParentDirectoryEntry(entry: TerminalFileEntry | null | undefined) {
  return entry?.type === 'directory' && entry.name === '..';
}

function sortTerminalFileEntries(entries: TerminalFileEntry[]) {
  const parentEntries = entries.filter(isParentDirectoryEntry);
  const normalEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  normalEntries.sort(compareTerminalFileEntries);
  return [...parentEntries.slice(0, 1), ...normalEntries];
}

function compareTerminalFileEntries(left: TerminalFileEntry, right: TerminalFileEntry) {
  const leftRank = getTerminalFileSortRank(left);
  const rightRank = getTerminalFileSortRank(right);
  if (leftRank !== rightRank) return leftRank - rightRank;
  return left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: 'base' });
}

function getTerminalFileSortRank(entry: TerminalFileEntry) {
  if (entry.name.startsWith('.')) return 0;
  if (entry.type === 'directory') return 1;
  return 2;
}

function getDefaultSelectedTerminalFile(entries: TerminalFileEntry[]) {
  return entries.find((entry) => entry.type === 'file') ?? entries.find((entry) => entry.type === 'directory' && !isParentDirectoryEntry(entry)) ?? null;
}

function formatTerminalFileProtocol(protocol: string) {
  const value = protocol.trim().toLowerCase();
  if (!value) return '';
  if (value.includes('sftp')) return 'SFTP';
  if (value.includes('enhanced')) return 'SCP enhanced';
  if (value.includes('scp')) return 'SCP normal';
  return protocol;
}

function formatTerminalFileSize(entry: TerminalFileEntry) {
  if (entry.type === 'directory') return '-';
  if (entry.size === undefined || entry.size === null || entry.size === '') return '-';
  return formatTerminalFileSizeValue(entry.size);
}

function formatTerminalFilePropertiesSize(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return formatTerminalFileSizeValue(properties.size);
}

function formatTerminalFileSizeValue(size: number | string) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  if (typeof size === 'string') return size;
  let valueSize = size;
  let unitIndex = 0;
  while (valueSize >= 1024 && unitIndex < units.length - 1) {
    valueSize /= 1024;
    unitIndex += 1;
  }
  const value = unitIndex === 0 ? String(valueSize) : valueSize.toFixed(valueSize >= 10 ? 1 : 2).replace(/\.0+$/, '');
  return `${value} ${units[unitIndex]}`;
}

function terminalFileText(value?: string | number) {
  if (value === undefined || value === null || value === '') return '-';
  return String(value);
}

function getTerminalFileDirectoryPath(entry: TerminalFileEntry) {
  if (isParentDirectoryEntry(entry)) return parentTerminalDirectoryPath(terminalFilePath.value);
  if (entry.type === 'directory') return entry.path;
  return parentTerminalDirectoryPath(entry.path);
}

function getTerminalFileResolvedPath(entry: TerminalFileEntry) {
  if (isParentDirectoryEntry(entry)) return parentTerminalDirectoryPath(terminalFilePath.value);
  return entry.path;
}

async function copyTerminalFileText(value: string) {
  if (!value) return;
  await navigator.clipboard?.writeText(value);
}

function sendTerminalFileTextToActiveTerminal(value: string) {
  if (!value || !activeTab.value) return;
  activeTab.value.terminal.write(value);
  activeTab.value.terminal.focus();
}

function getTerminalFilePropertiesTypeLabel(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return properties.type === 'directory' ? '文件夹' : '文件';
}

function getTerminalFileOwnerLabel(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return properties.owner || String(properties.uid);
}

function mergeTerminalFilePropertiesEntryIdentity(properties: TerminalFileProperties, entry: TerminalFileEntry): TerminalFileProperties {
  const owner = shouldUseTerminalFileEntryIdentity(properties.owner, properties.uid, entry.owner) ? String(entry.owner) : properties.owner;
  const group = shouldUseTerminalFileEntryIdentity(properties.group, properties.gid, entry.group) ? String(entry.group) : properties.group;
  if (owner === properties.owner && group === properties.group) return properties;
  return { ...properties, owner, group };
}

function shouldUseTerminalFileEntryIdentity(current: string, numericId: number, entryValue?: string) {
  const value = String(entryValue || '').trim();
  return Boolean(value && value !== '-' && value !== String(numericId) && String(current || '').trim() === String(numericId));
}

function getTerminalFileGroupLabel(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return properties.group || String(properties.gid);
}

function normalizeTerminalFileOctalMode(value: string) {
  const normalized = String(value || '').replace(/[^0-7]/g, '').slice(-4);
  return normalized.padStart(4, '0');
}

function updateTerminalFileOctalMode(event: Event) {
  const input = event.target as HTMLInputElement;
  const standardMode = String(input.value || '').replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  terminalFilePropertiesDialog.value.draft.octalMode = `${getTerminalFileSpecialOctalDigit()}${standardMode}`;
}

function isTerminalFilePermissionChecked(mask: number) {
  const mode = Number.parseInt(terminalFilePropertiesDialog.value.draft.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}

function setTerminalFilePermission(mask: number, checked: boolean) {
  const current = Number.parseInt(terminalFilePropertiesDialog.value.draft.octalMode || '0', 8) || 0;
  const next = checked ? current | mask : current & ~mask;
  terminalFilePropertiesDialog.value.draft.octalMode = (next & 0o7777).toString(8).padStart(4, '0');
}

function setTerminalFilePermissionFromEvent(mask: number, event: Event) {
  setTerminalFilePermission(mask, (event.target as HTMLInputElement).checked);
}

function getTerminalFileSpecialOctalDigit() {
  return normalizeTerminalFileOctalMode(terminalFilePropertiesDialog.value.draft.octalMode).charAt(0);
}

function getTerminalFileStandardOctalMode() {
  return normalizeTerminalFileOctalMode(terminalFilePropertiesDialog.value.draft.octalMode).slice(1);
}

async function downloadTerminalFile(entry = selectedTerminalFile.value) {
  if (!activeTab.value || !entry || isParentDirectoryEntry(entry)) return;
  await downloadTerminalFiles([entry]);
}

async function downloadTerminalFiles(entries = getTerminalFileActionEntries()) {
  const tab = activeTab.value;
  const downloadableEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  if (!tab || !downloadableEntries.length) return;
  try {
    terminalFileListError.value = '';
    const directoryHandle = await pickTerminalDownloadDirectory();
    if (!directoryHandle) return;
    const hostId = tab.host.id;
    const usedNames = new Set<string>();
    for (const entry of downloadableEntries) {
      const record = createTerminalTransferRecord('download', entry.name, entry.path, entry.type === 'file' ? 1 : 0);
      if (entry.type === 'directory') {
        await runTerminalTransfer(record, async () => {
          await downloadTerminalDirectory(entry, directoryHandle, usedNames, hostId, record);
        });
        continue;
      }
      await runTerminalTransfer(record, async () => {
        await downloadTerminalFileToDirectory(entry, directoryHandle, usedNames, hostId, record);
      });
    }
  } catch (error) {
    if (isTerminalDownloadAbortError(error)) return;
    terminalFileListError.value = error instanceof Error ? error.message : '下载失败';
  }
}

function getTerminalFileDownloadUrl(entry: TerminalFileEntry) {
  if (!activeTab.value) return '';
  return getTerminalFileDownloadRawUrl(activeTab.value.host.id, entry.path, terminalDownloadProtocol.value);
}

function getTerminalFileDownloadRawUrl(hostId: number, path: string, protocol: TerminalDownloadProtocol) {
  const params = new URLSearchParams({ path, protocol });
  return `/api/web-terminal/hosts/${hostId}/files/download/raw/?${params.toString()}`;
}

async function downloadTerminalDirectory(
  entry: TerminalFileEntry,
  directoryHandle: TerminalLocalDirectoryHandle,
  usedNames: Set<string>,
  hostId: number,
  record?: TerminalTransferRecord,
) {
  throwIfTerminalTransferCanceled(record);
  const directoryName = getUniqueTerminalDownloadFilename(sanitizeTerminalLocalFilename(entry.name || 'download'), usedNames);
  const childDirectoryHandle = await directoryHandle.getDirectoryHandle(directoryName, { create: true });
  await downloadTerminalDirectoryContents(entry.path, childDirectoryHandle, hostId, record);
}

async function downloadTerminalDirectoryContents(
  path: string,
  directoryHandle: TerminalLocalDirectoryHandle,
  hostId: number,
  record?: TerminalTransferRecord,
) {
  throwIfTerminalTransferCanceled(record);
  const response = await apiPost<TerminalFileListResponse>(
    `/api/web-terminal/hosts/${hostId}/files/list-download/`,
    { path },
    getTerminalTransferRequestOptions(record),
  );
  const usedNames = new Set<string>();
  const files = response.entries.filter((child) => child.type === 'file' && !isParentDirectoryEntry(child));
  const directories = response.entries.filter((child) => child.type === 'directory' && !isParentDirectoryEntry(child));
  if (record && files.length) incrementTerminalTransferTotal(record, files.length);
  for (const child of directories) {
    throwIfTerminalTransferCanceled(record);
    await downloadTerminalDirectory(child, directoryHandle, usedNames, hostId, record);
  }
  await runTerminalTransferPool(files, TERMINAL_DOWNLOAD_FILE_CONCURRENCY, async (child) => {
    throwIfTerminalTransferCanceled(record);
    await downloadTerminalFileToDirectory(child, directoryHandle, usedNames, hostId, record);
  });
}

async function downloadTerminalFileToDirectory(
  entry: TerminalFileEntry,
  directoryHandle: TerminalLocalDirectoryHandle,
  usedNames: Set<string>,
  hostId: number,
  record?: TerminalTransferRecord,
) {
  throwIfTerminalTransferCanceled(record);
  setTerminalTransferCurrentFile(record, entry.name);
  const response = await fetch(getTerminalFileDownloadRawUrl(hostId, entry.path, terminalDownloadProtocol.value), {
    credentials: 'include',
    ...getTerminalTransferRequestOptions(record),
  });
  if (!response.ok) throw new Error(await readTerminalDownloadError(response));
  throwIfTerminalTransferCanceled(record);
  const filename = getTerminalDownloadFilename(entry, getTerminalDownloadResponseFilename(response), usedNames);
  await writeTerminalResponseToDirectory(directoryHandle, filename, response, record);
  completeTerminalTransferFile(record);
}

async function runTerminalTransferPool<T>(items: T[], concurrency: number, worker: (item: T) => Promise<void>) {
  let cursor = 0;
  const workerCount = Math.min(Math.max(1, concurrency), items.length);
  await Promise.all(
    Array.from({ length: workerCount }, async () => {
      while (cursor < items.length) {
        const item = items[cursor];
        cursor += 1;
        await worker(item);
      }
    }),
  );
}

async function pickTerminalDownloadDirectory() {
  const picker = (window as TerminalDirectoryPickerWindow).showDirectoryPicker;
  if (!picker) {
    throw new Error('当前浏览器不支持选择下载目录，请使用新版 Chrome 或 Edge，并通过 HTTPS 或 localhost 打开。');
  }
  return picker({ id: TERMINAL_DOWNLOAD_DIRECTORY_PICKER_ID, mode: 'readwrite' });
}

async function writeTerminalBlobToDirectory(directoryHandle: TerminalLocalDirectoryHandle, filename: string, blob: Blob) {
  const fileHandle = await directoryHandle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  try {
    await writable.write(blob);
    await writable.close();
  } catch (error) {
    await writable.abort?.();
    throw error;
  }
}

async function writeTerminalResponseToDirectory(
  directoryHandle: TerminalLocalDirectoryHandle,
  filename: string,
  response: Response,
  record?: TerminalTransferRecord,
) {
  const fileHandle = await directoryHandle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  const totalBytes = Number(response.headers.get('Content-Length') || 0);
  updateTerminalTransferBytes(record, {
    currentBytes: 0,
    currentTotalBytes: Number.isFinite(totalBytes) && totalBytes > 0 ? totalBytes : 0,
  });
  try {
    if (!response.body) {
      const blob = await response.blob();
      throwIfTerminalTransferCanceled(record);
      await writable.write(blob);
      updateTerminalTransferBytes(record, { currentBytes: blob.size });
      await writable.close();
      return;
    }
    const reader = response.body.getReader();
    let writtenBytes = 0;
    while (true) {
      throwIfTerminalTransferCanceled(record);
      const { done, value } = await reader.read();
      if (done) break;
      if (!value) continue;
      await writable.write(value);
      writtenBytes += value.byteLength;
      updateTerminalTransferBytes(record, { currentBytes: writtenBytes });
    }
    throwIfTerminalTransferCanceled(record);
    await writable.close();
  } catch (error) {
    await writable.abort?.();
    throw error;
  }
}

function updateTerminalTransferBytes(record: TerminalTransferRecord | undefined, patch: Pick<Partial<TerminalTransferRecord>, 'currentBytes' | 'currentTotalBytes'>) {
  if (!record) return;
  updateTerminalTransferRecord(record, patch);
}

async function readTerminalDownloadError(response: Response) {
  const text = await response.text();
  if (!text) return '下载失败';
  try {
    const payload = JSON.parse(text) as { error?: unknown };
    return typeof payload.error === 'string' && payload.error ? payload.error : '下载失败';
  } catch {
    return text;
  }
}

function getTerminalDownloadResponseFilename(response: Response) {
  const disposition = response.headers.get('Content-Disposition') || '';
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      return encoded;
    }
  }
  const quoted = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  return quoted || '';
}

function getTerminalDownloadFilename(entry: TerminalFileEntry, responseFilename: string, usedNames: Set<string>) {
  return getUniqueTerminalDownloadFilename(
    sanitizeTerminalLocalFilename(responseFilename || entry.name || 'download'),
    usedNames,
  );
}

function sanitizeTerminalLocalFilename(filename: string) {
  const replaced = String(filename || 'download')
    .replace(TERMINAL_LOCAL_FILENAME_RESERVED_CHARS, '_')
    .replace(/[. ]+$/g, '')
    .trim();
  const safeName = replaced || 'download';
  return TERMINAL_LOCAL_FILENAME_RESERVED_NAMES.has(safeName.toUpperCase()) ? `${safeName}_` : safeName;
}

function getUniqueTerminalDownloadFilename(filename: string, usedNames: Set<string>) {
  if (!usedNames.has(filename.toLowerCase())) {
    usedNames.add(filename.toLowerCase());
    return filename;
  }
  const extensionIndex = filename.lastIndexOf('.');
  const hasExtension = extensionIndex > 0;
  const baseName = hasExtension ? filename.slice(0, extensionIndex) : filename;
  const extension = hasExtension ? filename.slice(extensionIndex) : '';
  let index = 2;
  let nextName = `${baseName} (${index})${extension}`;
  while (usedNames.has(nextName.toLowerCase())) {
    index += 1;
    nextName = `${baseName} (${index})${extension}`;
  }
  usedNames.add(nextName.toLowerCase());
  return nextName;
}

function isTerminalDownloadAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function startTerminalFileDragDownload(entry: TerminalFileEntry, event: DragEvent) {
  if (!activeTab.value || entry.type !== 'file' || isParentDirectoryEntry(entry) || !event.dataTransfer) return;
  if (!isTerminalFileSelected(entry)) setTerminalFileSelection([entry], entry.path);
  selectedTerminalFile.value = entry;
  const downloadableEntries = getTerminalFileDragDownloadEntries(entry);
  if (!downloadableEntries.length) return;
  const downloadItems = downloadableEntries.map((item) => ({
    mimeType: 'application/octet-stream',
    filename: item.name,
    url: new URL(getTerminalFileDownloadUrl(item), window.location.origin).toString(),
  }));
  event.dataTransfer.effectAllowed = 'copy';
  const firstItem = downloadItems[0];
  event.dataTransfer.setData('DownloadURL', `${firstItem.mimeType}:${firstItem.filename}:${firstItem.url}`);
  if (downloadItems.length === 1) {
    event.dataTransfer.setData('text/uri-list', firstItem.url);
    event.dataTransfer.setData('text/plain', firstItem.filename);
    return;
  }
  event.dataTransfer.setData('DownloadURL-list', JSON.stringify(downloadItems));
  event.dataTransfer.setData('text/uri-list', downloadItems.map((item) => item.url).join('\n'));
  event.dataTransfer.setData('text/plain', downloadItems.map((item) => item.filename).join('\n'));
}

function getTerminalFileDragDownloadEntries(entry: TerminalFileEntry) {
  const selectedEntries = selectedTerminalFiles.value.filter((item) => item.type === 'file' && !isParentDirectoryEntry(item));
  if (isTerminalFileSelected(entry) && selectedEntries.length) return selectedEntries;
  return entry.type === 'file' && !isParentDirectoryEntry(entry) ? [entry] : [];
}

function openTerminalUpload() {
  if (!activeTab.value || isParentDirectoryEntry(selectedTerminalFile.value)) return;
  closeTerminalContextMenus();
  terminalFileUploadInput.value?.click();
}

function openTerminalFolderUpload() {
  if (!activeTab.value) return;
  closeTerminalContextMenus();
  terminalFolderUploadInput.value?.click();
}

async function uploadTerminalFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!activeTab.value || !file) return;
  await uploadTerminalFiles([{ file }]);
}

async function uploadTerminalFolder(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = '';
  if (!activeTab.value || !files.length) return;
  await uploadTerminalFiles(
    files.map((file) => ({
      file,
      relativePath: (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
    })),
  );
}

async function uploadTerminalFiles(items: TerminalFileUploadItem[]) {
  const tab = activeTab.value;
  if (!tab || !items.length) return;
  const targetDirectory = terminalFilePath.value;
  try {
    terminalFileListError.value = '';
    const groups = groupTerminalUploadItems(items);
    for (const group of groups) {
      const record = createTerminalTransferRecord('upload', group.name, targetDirectory, group.items.length);
      await runTerminalTransfer(record, async () => {
        for (const item of group.items) {
          throwIfTerminalTransferCanceled(record);
          const file = item.file;
          setTerminalTransferCurrentFile(record, item.relativePath || file.name);
          const contentBase64 = await fileToBase64(file);
          throwIfTerminalTransferCanceled(record);
          await apiPost<{ protocol: string }>(
            `/api/web-terminal/hosts/${tab.host.id}/files/upload/`,
            { directory: targetDirectory, filename: file.name, relativePath: item.relativePath || '', contentBase64 },
            getTerminalTransferRequestOptions(record),
          );
          completeTerminalTransferFile(record);
        }
      });
    }
    if (activeTab.value?.id === tab.id && terminalFilePath.value === targetDirectory) {
      await loadTerminalDirectory(targetDirectory);
    }
  } catch (error) {
    if (isTerminalTransferCancelError(error)) return;
    terminalFileListError.value = error instanceof Error ? error.message : '文件上传失败';
  } finally {
    isTerminalFileDragOver.value = false;
  }
}

function onTerminalFileDragEnter(event: DragEvent) {
  if (!activeTab.value || !hasLocalDragFiles(event)) return;
  event.preventDefault();
  isTerminalFileDragOver.value = true;
}

function onTerminalFileDragOver(event: DragEvent) {
  if (!activeTab.value || !hasLocalDragFiles(event)) return;
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
  isTerminalFileDragOver.value = true;
}

function onTerminalFileDragLeave(event: DragEvent) {
  if (!(event.currentTarget instanceof HTMLElement)) return;
  const nextTarget = event.relatedTarget;
  if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) return;
  isTerminalFileDragOver.value = false;
}

async function onTerminalFileDrop(event: DragEvent) {
  if (!activeTab.value || !hasLocalDragFiles(event)) return;
  event.preventDefault();
  isTerminalFileDragOver.value = false;
  const items = await getDroppedUploadItems(event);
  if (!items.length) return;
  await uploadTerminalFiles(items);
}

function hasLocalDragFiles(event: DragEvent) {
  return Array.from(event.dataTransfer?.types || []).includes('Files');
}

async function getDroppedUploadItems(event: DragEvent): Promise<TerminalFileUploadItem[]> {
  const entries = Array.from(event.dataTransfer?.items || [])
    .map((item) => getTerminalDroppedFileSystemEntry(item))
    .filter((entry): entry is TerminalFileSystemEntry => Boolean(entry));
  if (entries.length) {
    return (await Promise.all(entries.map((entry) => readTerminalDroppedEntry(entry)))).flat();
  }
  return Array.from(event.dataTransfer?.files || []).map((file) => ({ file, relativePath: getDroppedFileRelativePath(file) }));
}

function getTerminalDroppedFileSystemEntry(item: DataTransferItem): TerminalFileSystemEntry | null {
  const maybeEntryItem = item as DataTransferItem & { webkitGetAsEntry?: () => TerminalFileSystemEntry | null };
  return maybeEntryItem.webkitGetAsEntry?.() ?? null;
}

async function readTerminalDroppedEntry(entry: TerminalFileSystemEntry, parentPath = ''): Promise<TerminalFileUploadItem[]> {
  const relativePath = parentPath ? `${parentPath}/${entry.name}` : entry.name;
  if (entry.isFile && entry.file) {
    const file = await readTerminalDroppedFile(entry);
    return [{ file, relativePath }];
  }
  if (!entry.isDirectory || !entry.createReader) return [];
  const children = await readTerminalDroppedDirectoryEntries(entry);
  return (await Promise.all(children.map((child) => readTerminalDroppedEntry(child, relativePath)))).flat();
}

function readTerminalDroppedFile(entry: TerminalFileSystemEntry): Promise<File> {
  return new Promise((resolve, reject) => {
    entry.file?.(resolve, reject);
  });
}

function readTerminalDroppedDirectoryEntries(entry: TerminalFileSystemEntry): Promise<TerminalFileSystemEntry[]> {
  const reader = entry.createReader?.();
  if (!reader) return Promise.resolve([]);
  const entries: TerminalFileSystemEntry[] = [];
  return new Promise((resolve, reject) => {
    const readBatch = () => {
      reader.readEntries((batch) => {
        if (!batch.length) {
          resolve(entries);
          return;
        }
        entries.push(...batch);
        readBatch();
      }, reject);
    };
    readBatch();
  });
}

function getDroppedFileRelativePath(file: File) {
  return (file as File & { webkitRelativePath?: string }).webkitRelativePath || '';
}

function groupTerminalUploadItems(items: TerminalFileUploadItem[]) {
  const groups = new Map<string, TerminalFileUploadItem[]>();
  for (const item of items) {
    const key = item.relativePath ? item.relativePath.replace(/\\/g, '/').split('/')[0] || item.file.name : item.file.name;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return Array.from(groups, ([name, groupItems]) => ({ name, items: groupItems }));
}

function createTerminalTransferRecord(kind: TerminalTransferKind, name: string, path: string, totalFiles = 0) {
  const now = Date.now();
  const record: TerminalTransferRecord = {
    id: `transfer-${now}-${Math.random().toString(36).slice(2, 8)}`,
    kind,
    status: 'queued',
    name,
    path,
    currentFile: '',
    currentBytes: 0,
    currentTotalBytes: 0,
    completedFiles: 0,
    totalFiles,
    progress: totalFiles > 0 ? 0 : 0,
    error: '',
    canceled: false,
    abortController: new AbortController(),
    createdAt: now,
    updatedAt: now,
  };
  terminalTransferRecords.value = [record, ...terminalTransferRecords.value];
  return record;
}

async function runTerminalTransfer(record: TerminalTransferRecord, work: () => Promise<void>) {
  updateTerminalTransferRecord(record, { status: 'running', error: '' });
  try {
    await work();
    if (record.canceled) {
      updateTerminalTransferRecord(record, { status: 'canceled', progress: record.progress });
      return;
    }
    updateTerminalTransferRecord(record, { status: 'success', progress: 100, currentFile: '' });
  } catch (error) {
    if (isTerminalTransferCancelError(error) || record.canceled) {
      updateTerminalTransferRecord(record, { status: 'canceled' });
      return;
    }
    updateTerminalTransferRecord(record, {
      status: 'error',
      error: error instanceof Error ? error.message : '传输失败',
    });
    throw error;
  }
}

function updateTerminalTransferRecord(record: TerminalTransferRecord, patch: Partial<TerminalTransferRecord>) {
  Object.assign(record, patch, { updatedAt: Date.now() });
  terminalTransferRecords.value = [...terminalTransferRecords.value];
}

function incrementTerminalTransferTotal(record: TerminalTransferRecord | undefined, count: number) {
  if (!record || count <= 0) return;
  updateTerminalTransferRecord(record, {
    totalFiles: record.totalFiles + count,
    progress: calculateTerminalTransferProgress(record.completedFiles, record.totalFiles + count),
  });
}

function setTerminalTransferCurrentFile(record: TerminalTransferRecord | undefined, currentFile: string) {
  if (!record) return;
  updateTerminalTransferRecord(record, { currentFile, currentBytes: 0, currentTotalBytes: 0 });
}

function completeTerminalTransferFile(record: TerminalTransferRecord | undefined) {
  if (!record) return;
  const completedFiles = record.completedFiles + 1;
  const totalFiles = Math.max(record.totalFiles, completedFiles);
  updateTerminalTransferRecord(record, {
    completedFiles,
    totalFiles,
    progress: calculateTerminalTransferProgress(completedFiles, totalFiles),
  });
}

function calculateTerminalTransferProgress(completedFiles: number, totalFiles: number) {
  if (totalFiles <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((completedFiles / totalFiles) * 100)));
}

function cancelTerminalTransfer(record: TerminalTransferRecord) {
  if (!isTerminalTransferActive(record)) return;
  updateTerminalTransferRecord(record, { canceled: true, status: 'canceled' });
  record.abortController.abort();
}

function cancelAllTerminalTransfers() {
  for (const record of terminalTransferRecords.value) {
    if (isTerminalTransferActive(record)) cancelTerminalTransfer(record);
  }
}

function clearTerminalTransferRecords() {
  terminalTransferRecords.value = terminalTransferRecords.value.filter(isTerminalTransferActive);
}

function isTerminalTransferActive(record: TerminalTransferRecord) {
  return record.status === 'queued' || record.status === 'running';
}

function throwIfTerminalTransferCanceled(record?: TerminalTransferRecord) {
  if (record?.canceled || record?.abortController.signal.aborted) throw new DOMException('传输已取消', 'AbortError');
}

function isTerminalTransferCancelError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function getTerminalTransferRequestOptions(record?: TerminalTransferRecord): RequestInit {
  return record ? { signal: record.abortController.signal } : {};
}

function getTerminalDownloadProtocolLabel(protocol = terminalDownloadProtocol.value) {
  if (protocol === 'sftp') return 'SFTP';
  if (protocol === 'scp') return 'SCP';
  return '自动';
}

function getTerminalTransferStatusText(record: TerminalTransferRecord) {
  if (record.status === 'queued') return '等待中';
  if (record.status === 'running') {
    if (!record.currentFile) return '传输中';
    const bytesText =
      record.currentTotalBytes > 0
        ? `（${formatTerminalFileSizeValue(record.currentBytes)} / ${formatTerminalFileSizeValue(record.currentTotalBytes)}）`
        : record.currentBytes > 0
          ? `（${formatTerminalFileSizeValue(record.currentBytes)}）`
          : '';
    return `传输中：${record.currentFile}${bytesText}`;
  }
  if (record.status === 'success') return '已完成';
  if (record.status === 'canceled') return '已取消';
  return record.error || '传输失败';
}

function getTerminalTransferCountText(record: TerminalTransferRecord) {
  if (!record.totalFiles) return record.status === 'running' ? '扫描中' : '0 / 0';
  return `${record.completedFiles} / ${record.totalFiles}`;
}

function getTerminalTransferProgressStyle(record: TerminalTransferRecord): Record<string, string> {
  return { width: `${Math.max(0, Math.min(100, record.progress))}%` };
}

function startTerminalTransferPanelResize(event: MouseEvent) {
  if (event.button !== 0) return;
  event.preventDefault();
  isTerminalTransferPanelResizing.value = true;
  terminalTransferResizeStartY = event.clientY;
  terminalTransferResizeStartHeight = terminalTransferPanelHeight.value;
  window.addEventListener('mousemove', resizeTerminalTransferPanel);
  window.addEventListener('mouseup', stopTerminalTransferPanelResize);
}

function resizeTerminalTransferPanel(event: MouseEvent) {
  if (!isTerminalTransferPanelResizing.value) return;
  const delta = terminalTransferResizeStartY - event.clientY;
  terminalTransferPanelHeight.value = clampTerminalTransferPanelHeight(terminalTransferResizeStartHeight + delta);
}

function stopTerminalTransferPanelResize() {
  if (!isTerminalTransferPanelResizing.value) return;
  isTerminalTransferPanelResizing.value = false;
  window.removeEventListener('mousemove', resizeTerminalTransferPanel);
  window.removeEventListener('mouseup', stopTerminalTransferPanelResize);
}

function syncTerminalTransferPanelHeight() {
  const nextHeight = clampTerminalTransferPanelHeight(terminalTransferPanelHeight.value);
  if (nextHeight !== terminalTransferPanelHeight.value) terminalTransferPanelHeight.value = nextHeight;
}

function clampTerminalTransferPanelHeight(height: number) {
  const browserHeight = terminalFileBrowserRef.value?.getBoundingClientRect().height ?? 0;
  const maxByBrowser = browserHeight ? Math.floor(browserHeight * 0.45) : TERMINAL_TRANSFER_PANEL_MAX_HEIGHT;
  const maxHeight = Math.max(TERMINAL_TRANSFER_PANEL_MIN_HEIGHT, Math.min(TERMINAL_TRANSFER_PANEL_MAX_HEIGHT, maxByBrowser));
  return Math.min(Math.max(height, TERMINAL_TRANSFER_PANEL_MIN_HEIGHT), maxHeight);
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',')[1] : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error('文件读取失败'));
    reader.readAsDataURL(file);
  });
}

async function loadTerminalMonitor() {
  if (!isTerminalMonitorVisible()) {
    terminalMonitorRequestId += 1;
    isTerminalMonitorLoading.value = false;
    if (!activeTab.value) {
      terminalMonitorData.value = null;
      terminalMonitorError.value = '';
    }
    return;
  }

  const tab = activeTab.value;
  if (!tab) return;

  const requestId = ++terminalMonitorRequestId;
  isTerminalMonitorLoading.value = true;
  try {
    const response = await apiPost<TerminalMonitorResponse>(`/api/web-terminal/hosts/${tab.host.id}/monitor/`, {});
    if (requestId !== terminalMonitorRequestId) return;
    terminalMonitorData.value = response;
    terminalMonitorError.value = '';
  } catch (error) {
    if (requestId !== terminalMonitorRequestId) return;
    terminalMonitorError.value = error instanceof Error ? error.message : '资源监控读取失败';
  } finally {
    if (requestId === terminalMonitorRequestId) {
      isTerminalMonitorLoading.value = false;
    }
  }
}

function isTerminalMonitorVisible() {
  return (
    terminalSidebarMode.value === 'monitor' &&
    !isTerminalSidebarCollapsed.value &&
    document.visibilityState === 'visible' &&
    Boolean(activeTab.value)
  );
}

function syncTerminalMonitorPolling() {
  if (!isTerminalMonitorVisible()) {
    stopTerminalMonitorPolling();
    terminalMonitorRequestId += 1;
    isTerminalMonitorLoading.value = false;
    if (!activeTab.value) {
      terminalMonitorData.value = null;
      terminalMonitorError.value = '';
    }
    return;
  }

  void loadTerminalMonitor();
  startTerminalMonitorPolling();
}

function startTerminalMonitorPolling() {
  if (terminalMonitorTimer) return;
  terminalMonitorTimer = window.setInterval(() => {
    if (isTerminalMonitorVisible()) {
      void loadTerminalMonitor();
    } else {
      syncTerminalMonitorPolling();
    }
  }, TERMINAL_MONITOR_REFRESH_MS);
}

function stopTerminalMonitorPolling() {
  if (!terminalMonitorTimer) return;
  window.clearInterval(terminalMonitorTimer);
  terminalMonitorTimer = null;
}

function formatMonitorPercent(value: number) {
  return `${formatMonitorNumber(value, 1)}%`;
}

function formatMonitorNumber(value: number, digits = 1) {
  if (!Number.isFinite(value)) return '0';
  return Number(value).toFixed(digits).replace(/\.0$/, '');
}

function formatMonitorBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${formatMonitorNumber(value, unitIndex >= 3 ? 2 : 1)} ${units[unitIndex]}`;
}

function formatMonitorRate(bytesPerSecond: number) {
  return `${formatMonitorBytes(bytesPerSecond)}/s`;
}

function formatMonitorUptime(seconds: number) {
  const totalDays = Math.floor(Math.max(0, seconds) / 86400);
  if (totalDays >= 1) return `${totalDays}天`;
  const hours = Math.floor(Math.max(0, seconds) / 3600);
  if (hours >= 1) return `${hours}小时`;
  const minutes = Math.floor(Math.max(0, seconds) / 60);
  return `${minutes}分钟`;
}

function monitorProgressStyle(value: number): Record<string, string> {
  const percent = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  return {
    '--value': String(percent),
    width: `${percent}%`,
  };
}

watch([activeTabId, terminalSidebarMode], () => {
  closeTerminalContextMenus();
  if (activeTab.value && terminalSidebarMode.value === 'files') {
    terminalFilePath.value = '.';
    void loadTerminalDirectory('.');
    void nextTick(syncTerminalTransferPanelHeight);
  }
  syncTerminalMonitorPolling();
});

watch(isTerminalSidebarCollapsed, () => {
  syncTerminalMonitorPolling();
});

const workspaceStatus = computed(() => {
  if (!activeTab.value) return '';
  if (activeTab.value.status === 'connecting') return '连接中...';
  if (activeTab.value.status === 'connected') return '已连接';
  if (activeTab.value.status === 'error') return '连接失败';
  return '已关闭';
});
const terminalShellStyle = computed<Record<string, string>>(() => ({
  '--terminal-sidebar-width': `${isTerminalSidebarCollapsed.value ? 42 : sidebarWidth.value}px`,
}));
onMounted(async () => {
  window.addEventListener('click', closeTerminalContextMenus);
  window.addEventListener('keydown', closeTerminalFileContextMenuOnEscape);
  window.addEventListener('resize', syncTerminalSidebarWidth);
  window.addEventListener('resize', syncTerminalTabsScrollStateSoon);
  document.addEventListener('visibilitychange', syncTerminalMonitorPolling);
  await loadTree();
  await restoreTerminalWorkspace();
  const params = new URLSearchParams(window.location.search);
  const hostId = Number(params.get('host'));
  if (hostId) {
    const restoredTab = tabs.value.find((tab) => tab.host.id === hostId);
    if (restoredTab) {
      await activateTab(restoredTab.id);
    } else {
      const host = findHostById(groups.value, hostId);
      if (host) await openHostTab(host);
    }
  }
});

onBeforeUnmount(() => {
  stopSidebarResize();
  stopTerminalTransferPanelResize();
  stopTerminalMonitorPolling();
  window.removeEventListener('click', closeTerminalContextMenus);
  window.removeEventListener('keydown', closeTerminalFileContextMenuOnEscape);
  window.removeEventListener('resize', syncTerminalSidebarWidth);
  window.removeEventListener('resize', syncTerminalTabsScrollStateSoon);
  document.removeEventListener('visibilitychange', syncTerminalMonitorPolling);
  for (const tab of tabs.value) disposeTab(tab);
});

function closeTerminalFileContextMenuOnEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;
  closeTerminalContextMenus();
  closeTerminalFileDeleteDialog();
  closeTerminalFileCreateDialog();
  cancelTerminalFileRename();
  closeTerminalFilePropertiesDialog();
}

async function loadTree() {
  isLoadingTree.value = true;
  treeError.value = '';
  try {
    groups.value = await apiGet<TerminalGroup[]>('/api/web-terminal/tree/');
  } catch (error) {
    treeError.value = (error as Error).message;
  } finally {
    isLoadingTree.value = false;
  }
}

function toggleGroup(group: TerminalGroup) {
  const next = new Set(collapsed.value);
  if (next.has(group.id)) {
    next.delete(group.id);
  } else {
    next.add(group.id);
  }
  collapsed.value = next;
}

async function openHostTab(host: TerminalHost) {
  const createdTab = createTerminalTab(host);
  tabs.value = [...tabs.value, createdTab];
  activeTabId.value = createdTab.id;
  saveTerminalWorkspace();
  await nextTick();
  scrollActiveTerminalTabIntoView();
  const tab = getTabById(createdTab.id) ?? createdTab;
  mountTerminal(tab);
  enqueueConnectTab(tab);
}

function toggleRoot() {
  rootExpanded.value = !rootExpanded.value;
}

async function activateTab(tabId: string) {
  activeTabId.value = tabId;
  saveTerminalWorkspace();
  await nextTick();
  scrollActiveTerminalTabIntoView();
  const tab = tabs.value.find((item) => item.id === tabId);
  if (tab) {
    tab.hasUnreadOutput = false;
    mountTerminal(tab);
    fitTerminal(tab);
    tab.terminal.focus();
    if (isTerminalFileFollowingCwd.value && tab.currentCwd) {
      void loadTerminalDirectory(tab.currentCwd);
    }
  }
}

function createTerminalTab(host: TerminalHost, tabId = createTerminalTabId(host.id)): TerminalTab {
  const terminal = markRaw(
    new Terminal({
      cursorBlink: true,
      convertEol: false,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: 14,
      lineHeight: 1.25,
      scrollback: 5000,
      theme: {
        background: '#000000',
        foreground: '#f5f7fb',
        cursor: '#f5f7fb',
        selectionBackground: '#31588f',
      },
    }),
  );
  const fitAddon = markRaw(new FitAddon());
  terminal.loadAddon(fitAddon);
  terminal.attachCustomKeyEventHandler((event) => handleTerminalKey(event, terminal));
  terminal.writeln('CAPTAIN WEB TERMINAL');
  terminal.writeln(`正在连接 ${host.name} (${host.publicIp || host.privateIp}:${host.port})...`);

  return {
    id: tabId,
    host,
    status: 'connecting',
    terminal,
    fitAddon,
    socket: null,
    sessionId: null,
    mounted: false,
    disposables: [],
    resizeObserver: null,
    highlightState: {
      sgrActive: false,
      pendingControl: '',
    },
    suppressInterruptUntil: 0,
    hasUnreadOutput: false,
    currentCwd: '',
    reconnectHintShown: false,
  };
}

function createTerminalTabId(hostId: number) {
  return `${hostId}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function handleTerminalKey(event: KeyboardEvent, terminal: Terminal) {
  const isCopyShortcut = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'c';
  if (!isCopyShortcut || !terminal.hasSelection()) return true;

  const selection = terminal.getSelection();
  if (selection) {
    navigator.clipboard?.writeText(selection).catch(() => undefined);
  }
  return false;
}

function suppressMouseInterrupt(tab: TerminalTab, duration: number) {
  tab.suppressInterruptUntil = Math.max(tab.suppressInterruptUntil, Date.now() + duration);
}

function markTerminalDoubleClick(tab: TerminalTab) {
  suppressMouseInterrupt(tab, MOUSE_DOUBLE_CLICK_INTERRUPT_SUPPRESSION_MS);
}

function getSendableTerminalData(tab: TerminalTab, data: string) {
  if (!data.includes(CONTROL_C) || Date.now() > tab.suppressInterruptUntil) return data;
  return data.split(CONTROL_C).join('');
}

function mountTerminal(tab: TerminalTab) {
  if (tab.mounted) return;
  const container = terminalContainers.get(tab.id);
  if (!container) return;

  tab.terminal.open(container);
  tab.mounted = true;
  tab.disposables.push(
    tab.terminal.onData((data) => {
      if (tab.status === 'closed' || tab.status === 'error') {
        if (data.includes('\r')) reconnectTerminalTab(tab);
        return;
      }
      if (tab.status === 'connecting') return;

      const sendableData = getSendableTerminalData(tab, data);
      if (!sendableData) return;

      if (tab.socket?.readyState === WebSocket.OPEN) {
        tab.socket.send(JSON.stringify({ type: 'input', data: sendableData }));
      }
    }),
  );
  const handleMouseDown = (event: MouseEvent) => {
    if (event.button !== 0) return;
    suppressMouseInterrupt(tab, MOUSE_SELECTION_INTERRUPT_SUPPRESSION_MS);
    if (event.detail >= 2) markTerminalDoubleClick(tab);
  };
  const handleDoubleClick = () => markTerminalDoubleClick(tab);
  container.addEventListener('mousedown', handleMouseDown, true);
  container.addEventListener('dblclick', handleDoubleClick, true);
  tab.disposables.push({
    dispose: () => {
      container.removeEventListener('mousedown', handleMouseDown, true);
      container.removeEventListener('dblclick', handleDoubleClick, true);
    },
  });
  tab.resizeObserver = new ResizeObserver(() => fitTerminal(tab));
  tab.resizeObserver.observe(container);
  fitTerminal(tab);
  tab.terminal.focus();
}

function enqueueConnectTab(tab: TerminalTab) {
  if (tab.status !== 'connecting' || pendingConnectTabIds.includes(tab.id) || connectingTabIds.has(tab.id)) return;
  pendingConnectTabIds.push(tab.id);
  drainConnectQueue();
}

function drainConnectQueue() {
  while (connectingTabIds.size < MAX_CONNECTING_TERMINALS && pendingConnectTabIds.length) {
    const tabId = pendingConnectTabIds.shift();
    if (!tabId) continue;

    const tab = getTabById(tabId);
    if (!tab || tab.status !== 'connecting') continue;

    connectingTabIds.add(tab.id);
    connectTab(tab);
  }
}

function finishConnectingTab(tab: TerminalTab) {
  if (!connectingTabIds.delete(tab.id)) return;
  drainConnectQueue();
}

function resetTerminalHighlightState(tab: TerminalTab) {
  tab.highlightState = {
    sgrActive: false,
    pendingControl: '',
  };
}

function showTerminalReconnectHint(tab: TerminalTab, reason = '') {
  if (tab.reconnectHintShown) return;
  if (reason) {
    tab.terminal.writeln(`\r\n\x1b[33m${reason}\x1b[0m`);
  }
  tab.terminal.writeln('\x1b[32m[会话已断开]\x1b[0m');
  tab.terminal.writeln('\x1b[32m[按回车键重新连接]\x1b[0m');
  tab.reconnectHintShown = true;
}

function reconnectTerminalTab(tab: TerminalTab) {
  if (tab.status !== 'closed' && tab.status !== 'error') return;
  tab.status = 'connecting';
  tab.sessionId = null;
  tab.currentCwd = '';
  tab.socket = null;
  tab.reconnectHintShown = false;
  resetTerminalHighlightState(tab);
  removePendingConnectTab(tab.id);
  finishConnectingTab(tab);
  tab.terminal.writeln('\r\n\x1b[32m[正在重新连接...]\x1b[0m');
  enqueueConnectTab(tab);
}

function connectTab(tab: TerminalTab) {
  tab.reconnectHintShown = false;
  const socket = new WebSocket(buildWebSocketUrl(tab.host.id));
  tab.socket = socket;

  socket.addEventListener('open', () => fitTerminal(tab));
  socket.addEventListener('message', (event) => handleSocketMessage(tab, event));
  socket.addEventListener('error', () => {
    if (tab.status !== 'closed') {
      tab.status = 'error';
      showTerminalReconnectHint(tab, 'WebSocket 连接失败。');
    }
    finishConnectingTab(tab);
  });
  socket.addEventListener('close', () => {
    tab.socket = null;
    finishConnectingTab(tab);
    if (tab.status === 'connected' || tab.status === 'connecting') {
      tab.status = 'closed';
      showTerminalReconnectHint(tab, '连接已关闭。');
    }
  });
}

function handleSocketMessage(tab: TerminalTab, event: MessageEvent<string>) {
  let message: TerminalMessage;
  try {
    message = JSON.parse(event.data) as TerminalMessage;
  } catch {
    tab.terminal.writeln('\r\n\x1b[31m终端消息解析失败。\x1b[0m');
    return;
  }

  if (message.type === 'ready') {
    tab.status = 'connected';
    tab.sessionId = message.sessionId ?? null;
    tab.reconnectHintShown = false;
    finishConnectingTab(tab);
    fitTerminal(tab);
    return;
  }

  if (message.type === 'output') {
    tab.terminal.write(highlightTerminalOutput(message.data ?? '', tab.highlightState));
    if (tab.id !== activeTabId.value) {
      markTabUnread(tab.id);
    }
    return;
  }

  if (message.type === 'cwd') {
    const path = String(message.path || '').trim();
    if (!path) return;
    tab.currentCwd = path;
    if (isTerminalFileFollowingCwd.value && tab.id === activeTabId.value) {
      void loadTerminalDirectory(path);
    }
    return;
  }

  if (message.type === 'error') {
    tab.status = 'error';
    finishConnectingTab(tab);
    showTerminalReconnectHint(tab, message.message ?? '终端连接失败');
    return;
  }

  if (message.type === 'closed') {
    tab.status = 'closed';
    finishConnectingTab(tab);
    showTerminalReconnectHint(tab, message.reason ?? '连接已关闭');
  }
}

function getTabById(tabId: string) {
  return tabs.value.find((item) => item.id === tabId) ?? null;
}

function markTabUnread(tabId: string) {
  const tab = getTabById(tabId);
  if (tab && tab.id !== activeTabId.value) {
    tab.hasUnreadOutput = true;
  }
}

function fitTerminal(tab: TerminalTab) {
  if (!tab.mounted || activeTabId.value !== tab.id) return;
  try {
    tab.fitAddon.fit();
    if (tab.socket?.readyState === WebSocket.OPEN) {
      tab.socket.send(JSON.stringify({ type: 'resize', cols: tab.terminal.cols, rows: tab.terminal.rows }));
    }
  } catch {
    // xterm cannot fit until the container has a measurable size.
  }
}

function startSidebarResize(event: MouseEvent, options: { alignToPointer?: boolean } = {}) {
  event.preventDefault();
  if (isTerminalSidebarCollapsed.value) setTerminalSidebarCollapsed(false);
  sidebarResizeStartX = event.clientX;
  sidebarResizeStartWidth = sidebarWidth.value;
  isResizingSidebar.value = true;
  if (options.alignToPointer) {
    sidebarWidth.value = clampTerminalSidebarWidth(event.clientX);
    sidebarResizeStartWidth = sidebarWidth.value;
  }
  window.addEventListener('mousemove', resizeSidebar);
  window.addEventListener('mouseup', stopSidebarResize);
  document.body.classList.add('terminal-resizing');
}

function resizeSidebar(event: MouseEvent) {
  if (!isResizingSidebar.value) return;
  const nextWidth = clampTerminalSidebarWidth(sidebarResizeStartWidth + event.clientX - sidebarResizeStartX);
  sidebarWidth.value = nextWidth;
  window.localStorage.setItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY, String(nextWidth));
  fitActiveTerminalSoon();
}

function clampTerminalSidebarWidth(width: number) {
  const viewportWidth = typeof window === 'undefined' ? 0 : window.innerWidth;
  const maxWidth = Math.max(
    TERMINAL_SIDEBAR_MIN_WIDTH,
    viewportWidth - TERMINAL_WORKSPACE_MIN_WIDTH,
  );
  return Math.min(Math.max(width, TERMINAL_SIDEBAR_MIN_WIDTH), maxWidth);
}

function syncTerminalSidebarWidth() {
  if (isTerminalSidebarCollapsed.value) {
    fitActiveTerminalSoon();
    syncTerminalTransferPanelHeight();
    return;
  }
  const nextWidth = clampTerminalSidebarWidth(sidebarWidth.value);
  if (nextWidth !== sidebarWidth.value) {
    sidebarWidth.value = nextWidth;
    window.localStorage.setItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY, String(nextWidth));
  }
  syncTerminalTransferPanelHeight();
  fitActiveTerminalSoon();
}

function stopSidebarResize() {
  if (!isResizingSidebar.value) return;
  isResizingSidebar.value = false;
  window.removeEventListener('mousemove', resizeSidebar);
  window.removeEventListener('mouseup', stopSidebarResize);
  document.body.classList.remove('terminal-resizing');
  fitActiveTerminalSoon();
}

function selectTerminalSidebarMode(mode: TerminalSidebarMode) {
  terminalSidebarMode.value = mode;
  if (isTerminalSidebarCollapsed.value) setTerminalSidebarCollapsed(false);
}

function toggleTerminalSidebar() {
  setTerminalSidebarCollapsed(!isTerminalSidebarCollapsed.value);
}

function setTerminalSidebarCollapsed(collapsed: boolean) {
  isTerminalSidebarCollapsed.value = collapsed;
  window.localStorage.setItem(TERMINAL_SIDEBAR_COLLAPSED_STORAGE_KEY, collapsed ? '1' : '0');
  if (collapsed) stopSidebarResize();
  closeTerminalContextMenus();
  fitActiveTerminalSoon();
}

function fitActiveTerminalSoon() {
  window.requestAnimationFrame(() => {
    const tab = activeTab.value;
    if (tab) fitTerminal(tab);
  });
}

async function closeTab(tab: TerminalTab) {
  closeTerminalTabMenu();
  const index = tabs.value.findIndex((item) => item.id === tab.id);
  disposeTab(tab);
  tabs.value = tabs.value.filter((item) => item.id !== tab.id);
  terminalContainers.delete(tab.id);
  await nextTick();

  if (activeTabId.value === tab.id) {
    const nextTab = tabs.value[Math.min(index, tabs.value.length - 1)] ?? null;
    activeTabId.value = nextTab?.id ?? null;
    if (nextTab) await activateTab(nextTab.id);
  }
  saveTerminalWorkspace();
  syncTerminalTabsScrollStateSoon();
}

async function restoreTerminalWorkspace() {
  const workspace = loadTerminalWorkspace();
  if (!workspace?.tabs.length || treeError.value) return;

  const restoredTabs = workspace.tabs
    .map((item) => {
      const host = findHostById(groups.value, item.hostId);
      return host ? createTerminalTab(host, item.id) : null;
    })
    .filter((tab): tab is TerminalTab => Boolean(tab));

  if (!restoredTabs.length) {
    saveTerminalWorkspace();
    return;
  }

  tabs.value = restoredTabs;
  activeTabId.value = restoredTabs.some((tab) => tab.id === workspace.activeTabId) ? workspace.activeTabId : restoredTabs[0].id;
  saveTerminalWorkspace();

  await nextTick();
  scrollActiveTerminalTabIntoView();
  for (const tab of restoredTabs) {
    mountTerminal(tab);
    enqueueConnectTab(tab);
  }
}

function loadTerminalWorkspace(): PersistedTerminalWorkspace | null {
  if (typeof window === 'undefined') return null;

  const raw = window.sessionStorage.getItem(TERMINAL_WORKSPACE_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<PersistedTerminalWorkspace>;
    if (!Array.isArray(parsed.tabs)) return null;

    const seenIds = new Set<string>();
    const persistedTabs = parsed.tabs.flatMap((item) => {
      if (!item || typeof item !== 'object') return [];
      const id = typeof item.id === 'string' && item.id ? item.id : '';
      const hostId = Number(item.hostId);
      if (!id || !Number.isFinite(hostId) || seenIds.has(id)) return [];
      seenIds.add(id);
      return [{ id, hostId }];
    });

    return {
      tabs: persistedTabs,
      activeTabId: typeof parsed.activeTabId === 'string' ? parsed.activeTabId : null,
    };
  } catch {
    return null;
  }
}

function saveTerminalWorkspace() {
  if (typeof window === 'undefined') return;

  const workspace: PersistedTerminalWorkspace = {
    tabs: tabs.value.map((tab) => ({ id: tab.id, hostId: tab.host.id })),
    activeTabId: activeTabId.value,
  };

  if (!workspace.tabs.length) {
    window.sessionStorage.removeItem(TERMINAL_WORKSPACE_STORAGE_KEY);
    return;
  }

  window.sessionStorage.setItem(TERMINAL_WORKSPACE_STORAGE_KEY, JSON.stringify(workspace));
}

function disposeTab(tab: TerminalTab) {
  tab.status = 'closed';
  removePendingConnectTab(tab.id);
  finishConnectingTab(tab);
  if (tab.socket && tab.socket.readyState !== WebSocket.CLOSED) {
    tab.socket.close();
  }
  tab.socket = null;
  tab.resizeObserver?.disconnect();
  tab.resizeObserver = null;
  for (const disposable of tab.disposables) disposable.dispose();
  tab.disposables = [];
  tab.terminal.dispose();
}

function removePendingConnectTab(tabId: string) {
  const index = pendingConnectTabIds.indexOf(tabId);
  if (index !== -1) {
    pendingConnectTabIds.splice(index, 1);
  }
}

function setTerminalContainer(tabId: string, element: unknown) {
  if (element instanceof HTMLElement) {
    terminalContainers.set(tabId, element);
    const tab = tabs.value.find((item) => item.id === tabId);
    if (tab) mountTerminal(tab);
  } else {
    terminalContainers.delete(tabId);
  }
}

function buildWebSocketUrl(hostId: number) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/web-terminal/${hostId}/`;
}

function highlightTerminalOutput(output: string, state: TerminalHighlightState) {
  if (!output && !state.pendingControl) return '';

  const source = state.pendingControl + output;
  state.pendingControl = getTrailingAnsiPrefix(source);
  const parseableOutput = state.pendingControl ? source.slice(0, -state.pendingControl.length) : source;
  const shouldHighlight = highlightEnabled.value;

  let result = '';
  let lastIndex = 0;
  ANSI_CONTROL_PATTERN.lastIndex = 0;

  for (let match = ANSI_CONTROL_PATTERN.exec(parseableOutput); match; match = ANSI_CONTROL_PATTERN.exec(parseableOutput)) {
    if (match.index > lastIndex) {
      const plainText = parseableOutput.slice(lastIndex, match.index);
      result += shouldHighlight && !state.sgrActive ? highlightPlainText(plainText) : plainText;
    }

    const controlSequence = match[0];
    result += controlSequence;
    state.sgrActive = getNextSgrState(controlSequence, state.sgrActive);
    lastIndex = match.index + controlSequence.length;
  }

  if (lastIndex < parseableOutput.length) {
    const plainText = parseableOutput.slice(lastIndex);
    result += shouldHighlight && !state.sgrActive ? highlightPlainText(plainText) : plainText;
  }

  return result;
}

function getTrailingAnsiPrefix(output: string) {
  const escapeIndex = output.lastIndexOf('\x1b');
  if (escapeIndex === -1) return '';

  const suffix = output.slice(escapeIndex);
  if (suffix.startsWith('\x1b]')) {
    const bellIndex = suffix.indexOf('\x07', 2);
    const stringTerminatorIndex = suffix.indexOf('\x1b\\', 2);
    return bellIndex === -1 && stringTerminatorIndex === -1 ? suffix : '';
  }

  return ANSI_CONTROL_PREFIX_PATTERN.test(suffix) ? suffix : '';
}

function highlightPlainText(text: string) {
  const matches: Array<{ start: number; end: number; rule: TerminalHighlightRule; priority: number }> = [];

  terminalHighlightRules.forEach((rule, priority) => {
    rule.pattern.lastIndex = 0;
    for (let match = rule.pattern.exec(text); match; match = rule.pattern.exec(text)) {
      if (!match[0]) {
        rule.pattern.lastIndex += 1;
        continue;
      }
      matches.push({ start: match.index, end: match.index + match[0].length, rule, priority });
    }
  });

  if (!matches.length) return text;

  matches.sort((left, right) => left.start - right.start || left.priority - right.priority || right.end - left.end);

  let result = '';
  let cursor = 0;
  for (const match of matches) {
    if (match.start < cursor) continue;
    result += text.slice(cursor, match.start);
    result += `${match.rule.open}${text.slice(match.start, match.end)}${match.rule.close}`;
    cursor = match.end;
  }
  result += text.slice(cursor);

  return result;
}

function getNextSgrState(sequence: string, current: boolean) {
  if (!sequence.endsWith('m')) return current;

  const rawParams = sequence.slice(2, -1);
  const params = rawParams ? rawParams.split(';') : ['0'];
  if (params.some((param) => param === '' || param === '0')) return false;

  return true;
}

function flattenTerminalRows(source: TerminalGroup[], hidden: Set<number>, level = 0): TreeRow[] {
  return source.flatMap((group) => {
    const current: TreeRow[] = [{ kind: 'group', group, level }];
    if (!hidden.has(group.id)) {
      current.push(...flattenTerminalRows(group.children, hidden, level + 1));
      current.push(...group.hosts.map((host) => ({ kind: 'host' as const, host, level: level + 1 })));
    }
    return current;
  });
}

function countTerminalHosts(source: TerminalGroup[]): number {
  return source.reduce((total, group) => total + group.hosts.length + countTerminalHosts(group.children), 0);
}

function findHostById(source: TerminalGroup[], hostId: number): TerminalHost | null {
  for (const group of source) {
    const host = group.hosts.find((item) => item.id === hostId);
    if (host) return host;
    const childHost = findHostById(group.children, hostId);
    if (childHost) return childHost;
  }
  return null;
}

function readTerminalRootLabel() {
  if (typeof window === 'undefined') return 'DEFAULT';
  return window.localStorage.getItem('ops-tool.host-manager.root-label') || 'DEFAULT';
}

function readTerminalSidebarWidth() {
  if (typeof window === 'undefined') return TERMINAL_SIDEBAR_DEFAULT_WIDTH;
  const saved = Number(window.localStorage.getItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY));
  if (!Number.isFinite(saved)) return TERMINAL_SIDEBAR_DEFAULT_WIDTH;
  return clampTerminalSidebarWidth(saved);
}

function readTerminalSidebarCollapsed() {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(TERMINAL_SIDEBAR_COLLAPSED_STORAGE_KEY) === '1';
}
</script>

<template>
  <main class="terminal-shell" :class="{ resizing: isResizingSidebar, 'sidebar-collapsed': isTerminalSidebarCollapsed }" :style="terminalShellStyle">
    <aside class="terminal-sidebar">
      <nav class="terminal-side-switch" aria-label="终端侧栏切换" @mousedown.self="startSidebarResize" @dblclick.stop="toggleTerminalSidebar">
        <button
          type="button"
          title="服务器列表"
          aria-label="服务器列表"
          :class="{ active: terminalSidebarMode === 'hosts' }"
          @click="selectTerminalSidebarMode('hosts')"
        >
          <AppIcon name="server" :size="18" />
        </button>
        <button
          type="button"
          title="FTP 文件夹"
          aria-label="FTP 文件夹"
          :class="{ active: terminalSidebarMode === 'files' }"
          @click="selectTerminalSidebarMode('files')"
        >
          <AppIcon name="folder" :size="19" />
        </button>
        <button
          type="button"
          title="资源监控"
          aria-label="资源监控"
          :class="{ active: terminalSidebarMode === 'monitor' }"
          @click="selectTerminalSidebarMode('monitor')"
        >
          <AppIcon name="monitor" :size="18" />
        </button>
        <button
          class="terminal-sidebar-collapse-button"
          type="button"
          :title="terminalSidebarToggleLabel"
          :aria-label="terminalSidebarToggleLabel"
          :aria-pressed="isTerminalSidebarCollapsed"
          @click="toggleTerminalSidebar"
        >
          <AppIcon name="chevronsRight" :size="17" />
        </button>
      </nav>
      <div class="terminal-sidebar-panel">
        <template v-if="terminalSidebarMode === 'hosts'">
          <div class="terminal-search">
            <input v-model="search" placeholder="输入主机名/IP检索" />
            <button type="button" title="刷新" aria-label="刷新" @click="loadTree"><AppIcon name="refresh" :size="16" /></button>
          </div>
          <div class="terminal-tree">
            <button
              v-for="row in rows"
              :key="row.kind === 'root' ? 'group-root' : row.kind === 'group' ? `group-${row.group.id}` : `host-${row.host.id}`"
              class="terminal-tree-row"
              :class="{ root: row.kind === 'root', host: row.kind === 'host', active: row.kind === 'host' && activeTab?.host.id === row.host.id }"
              :style="{ paddingLeft: `${12 + row.level * 24}px` }"
              type="button"
              @click="row.kind === 'root' ? toggleRoot() : row.kind === 'group' && toggleGroup(row.group)"
              @dblclick="row.kind === 'host' && openHostTab(row.host)"
            >
              <template v-if="row.kind === 'root'">
                <span><AppIcon :name="rootExpanded ? 'chevronDown' : 'chevronRight'" :size="15" /></span>
                <strong><AppIcon name="folder" :size="16" />{{ row.group.name }}</strong>
                <em>{{ row.group.count }}</em>
              </template>
              <template v-else-if="row.kind === 'group'">
                <span><AppIcon :name="collapsed.has(row.group.id) ? 'chevronRight' : 'chevronDown'" :size="15" /></span>
                <strong><AppIcon name="folder" :size="16" />{{ row.group.name }}</strong>
              </template>
              <template v-else>
                <span><AppIcon name="server" :size="15" /></span>
                <strong>{{ row.host.name }}</strong>
                <i
                  v-if="row.host.verified || row.host.verifyStatus === 'failed'"
                  class="terminal-host-verify-dot"
                  :class="{ failed: row.host.verifyStatus === 'failed' }"
                  :title="row.host.verifyStatus === 'failed' ? '验证失败' : '已验证'"
                  :aria-label="row.host.verifyStatus === 'failed' ? '验证失败' : '已验证'"
                ></i>
              </template>
            </button>
            <p v-if="isLoadingTree" class="terminal-tree-empty">加载中...</p>
            <p v-else-if="treeError" class="terminal-tree-empty">{{ treeError }}</p>
            <p v-else-if="!rows.length" class="terminal-tree-empty">没有匹配的主机。</p>
          </div>
        </template>
        <template v-else-if="terminalSidebarMode === 'files'">
          <div ref="terminalFileBrowserRef" class="terminal-file-browser" :style="terminalTransferPanelStyle">
            <header class="terminal-file-title">
              <strong>文件浏览器</strong>
              <span class="terminal-file-node">{{ activeTerminalNodeName }}</span>
            </header>
            <div class="terminal-file-toolbar">
              <button type="button" title="新建文件" aria-label="新建文件" @click="openTerminalFileCreateDialog('file')"><AppIcon name="plus" :size="15" /></button>
              <button type="button" title="新建文件夹" aria-label="新建文件夹" @click="openTerminalFileCreateDialog('directory')"><AppIcon name="folderPlus" :size="15" /></button>
              <span></span>
              <button type="button" title="上传" aria-label="上传" @click="openTerminalUpload"><AppIcon name="upload" :size="15" /></button>
              <button type="button" title="下载" aria-label="下载" :disabled="!canDownloadSelectedTerminalFiles" @click="downloadTerminalFiles()"><AppIcon name="download" :size="15" /></button>
              <button
                type="button"
                title="删除"
                aria-label="删除"
                :disabled="!selectedTerminalFileCount"
                @click="openTerminalFileDeleteDialog()"
              >
                <AppIcon name="trash" :size="15" />
              </button>
              <span></span>
              <button type="button" title="返回上级" aria-label="返回上级" @click="openTerminalParentDirectory"><AppIcon name="chevronRight" :size="15" /></button>
              <button type="button" title="刷新" aria-label="刷新" @click="loadTerminalDirectory()"><AppIcon name="refresh" :size="15" /></button>
              <span></span>
              <button type="button" title="搜索" aria-label="搜索"><AppIcon name="search" :size="15" /></button>
            </div>
            <div class="terminal-file-path">
              <span>{{ terminalFilePath }}</span>
              <button type="button" title="收藏路径" aria-label="收藏路径"><AppIcon name="folder" :size="14" /></button>
            </div>
            <div class="terminal-file-table">
              <div class="terminal-file-table-head">
                <button type="button">名称 <em>▲</em></button>
                <span>修改时间</span>
                <span>大小</span>
                <span>权限</span>
                <span>所有者</span>
                <span>组</span>
              </div>
              <div
                ref="terminalFileListRef"
                class="terminal-file-list"
                :class="{ 'drag-over': isTerminalFileDragOver, selecting: terminalFileMarquee.active }"
                @contextmenu="openTerminalDirectoryContextMenu"
                @mousedown="startTerminalFileMarquee"
                @dragenter="onTerminalFileDragEnter"
                @dragover="onTerminalFileDragOver"
                @dragleave="onTerminalFileDragLeave"
                @drop="onTerminalFileDrop"
              >
                <div
                  v-for="entry in terminalFileEntries"
                  :key="entry.name"
                  class="terminal-file-item"
                  :class="{ selected: isTerminalFileSelected(entry), parent: isParentDirectoryEntry(entry) }"
                  :data-terminal-file-path="entry.path"
                  :draggable="Boolean(activeTab) && entry.type === 'file' && isTerminalFileSelected(entry)"
                  role="button"
                  :tabindex="activeTab ? 0 : -1"
                  :aria-disabled="!activeTab"
                  @click="selectTerminalFile(entry, $event)"
                  @contextmenu="openTerminalFileContextMenu(entry, $event)"
                  @mousedown="!isTerminalFileSelected(entry) && startTerminalFileMarquee($event)"
                  @dragstart="startTerminalFileDragDownload(entry, $event)"
                  @dblclick="!isTerminalFileRenaming(entry) && entry.type === 'directory' && openTerminalDirectory(entry)"
                  @keydown.enter.prevent="!isTerminalFileRenaming(entry) && entry.type === 'directory' && openTerminalDirectory(entry)"
                >
                  <span class="terminal-file-name">
                    <AppIcon :name="entry.type === 'directory' ? 'folder' : 'settings'" :size="15" />
                    <input
                      v-if="isTerminalFileRenaming(entry)"
                      :ref="setTerminalFileRenameInput"
                      v-model="terminalFileRename!.draftName"
                      class="terminal-file-rename-input"
                      type="text"
                      :disabled="terminalFileRename?.saving"
                      @click.stop
                      @dblclick.stop
                      @keydown.enter.prevent.stop="saveTerminalFileRename"
                      @keydown.esc.prevent.stop="cancelTerminalFileRename"
                      @blur="saveTerminalFileRename"
                    />
                    <strong v-else>{{ entry.name }}</strong>
                  </span>
                  <time>{{ entry.modifiedAt }}</time>
                  <span class="terminal-file-size">{{ formatTerminalFileSize(entry) }}</span>
                  <span class="terminal-file-permissions">{{ terminalFileText(entry.permissions) }}</span>
                  <span>{{ terminalFileText(entry.owner) }}</span>
                  <span>{{ terminalFileText(entry.group) }}</span>
                </div>
                <p v-if="!activeTab" class="terminal-tree-empty">请选择服务器</p>
                <p v-else-if="isTerminalFileListLoading" class="terminal-tree-empty">目录加载中...</p>
                <p v-else-if="terminalFileListError" class="terminal-tree-empty">{{ terminalFileListError }}</p>
                <div v-if="isTerminalFileDragOver" class="terminal-file-drop-hint">
                  <AppIcon name="upload" :size="22" />
                  <strong>释放后上传到当前目录</strong>
                </div>
                <div v-if="terminalFileMarquee.active" class="terminal-file-marquee" :style="terminalFileMarqueeStyle"></div>
              </div>
            </div>
            <footer class="terminal-file-status">
              <span>{{ terminalFileSelectionStatusText }}</span>
              <span class="terminal-file-protocol" :class="terminalFileStatus">{{ terminalFileStatusText }}</span>
              <label class="terminal-file-download-protocol" :title="`下载方式：${getTerminalDownloadProtocolLabel()}`">
                <span>下载</span>
                <select v-model="terminalDownloadProtocol" aria-label="下载方式">
                  <option value="auto">自动</option>
                  <option value="sftp">SFTP</option>
                  <option value="scp">SCP</option>
                </select>
              </label>
              <div>
                <button
                  type="button"
                  :title="terminalFileFollowCwdLabel"
                  :aria-label="terminalFileFollowCwdLabel"
                  :aria-pressed="isTerminalFileFollowingCwd"
                  :class="{ active: isTerminalFileFollowingCwd }"
                  @click="toggleTerminalFileCwdFollow"
                >
                  <AppIcon name="refresh" :size="15" />
                </button>
              </div>
            </footer>
            <section class="terminal-transfer-panel" :class="{ resizing: isTerminalTransferPanelResizing }">
              <button
                class="terminal-transfer-resizer"
                type="button"
                title="调整文件传输栏高度"
                aria-label="调整文件传输栏高度"
                @mousedown="startTerminalTransferPanelResize"
              ></button>
              <header class="terminal-transfer-header">
                <strong>文件传输</strong>
                <div>
                  <button type="button" title="取消全部" aria-label="取消全部" :disabled="!hasRunningTerminalTransfers" @click="cancelAllTerminalTransfers">
                    <AppIcon name="x" :size="14" />
                  </button>
                  <button type="button" title="清空记录" aria-label="清空记录" :disabled="!hasClearableTerminalTransfers" @click="clearTerminalTransferRecords">
                    <AppIcon name="trash" :size="14" />
                  </button>
                </div>
              </header>
              <div class="terminal-transfer-list">
                <p v-if="!terminalTransferRecords.length" class="terminal-transfer-empty">无传输记录</p>
                <article
                  v-for="record in terminalTransferRecords"
                  :key="record.id"
                  class="terminal-transfer-item"
                  :class="[record.kind, record.status]"
                >
                  <AppIcon :name="record.kind === 'upload' ? 'upload' : 'download'" :size="15" />
                  <div class="terminal-transfer-main">
                    <div class="terminal-transfer-line">
                      <strong>{{ record.name }}</strong>
                      <span>{{ getTerminalTransferCountText(record) }}</span>
                    </div>
                    <div class="terminal-transfer-progress" aria-hidden="true">
                      <i :style="getTerminalTransferProgressStyle(record)"></i>
                    </div>
                    <p>{{ getTerminalTransferStatusText(record) }}</p>
                  </div>
                  <button
                    type="button"
                    title="取消"
                    aria-label="取消"
                    :disabled="!isTerminalTransferActive(record)"
                    @click="cancelTerminalTransfer(record)"
                  >
                    <AppIcon name="x" :size="13" />
                  </button>
                </article>
              </div>
            </section>
            <input ref="terminalFileUploadInput" hidden type="file" @change="uploadTerminalFile" />
            <input ref="terminalFolderUploadInput" hidden type="file" multiple webkitdirectory @change="uploadTerminalFolder" />
            <div
              v-if="terminalFileContextMenu.visible"
              class="terminal-file-context-menu"
              :class="{ 'submenu-left': isTerminalContextSubmenuLeft(terminalFileContextMenu.x) }"
              :style="{ left: `${terminalFileContextMenu.x}px`, top: `${terminalFileContextMenu.y}px` }"
              role="menu"
              @click.stop
              @contextmenu.prevent.stop
            >
              <div
                v-for="item in terminalFileContextMenuItems"
                :key="item.id"
                class="terminal-file-context-menu-row"
                :class="{ separator: item.separatorBefore }"
              >
                <button
                  type="button"
                  role="menuitem"
                  class="terminal-file-context-menu-item"
                  :class="{ danger: item.danger }"
                  :disabled="!item.enabled"
                  @click="runTerminalFileContextMenuItem(item)"
                >
                  <AppIcon :name="item.icon" :size="15" />
                  <span>{{ item.label }}</span>
                  <AppIcon v-if="item.children?.length" name="chevronRight" :size="14" />
                </button>
                <div v-if="item.children?.length" class="terminal-file-context-submenu" role="menu">
                  <button
                    v-for="child in item.children"
                    :key="child.id"
                    type="button"
                    role="menuitem"
                    class="terminal-file-context-menu-item"
                    :disabled="!child.enabled"
                    @click="runTerminalFileContextMenuItem(child)"
                  >
                    <AppIcon :name="child.icon" :size="15" />
                    <span>{{ child.label }}</span>
                  </button>
                </div>
              </div>
            </div>
            <div
              v-if="terminalDirectoryContextMenu.visible"
              class="terminal-file-context-menu terminal-file-directory-context-menu"
              :class="{ 'submenu-left': isTerminalContextSubmenuLeft(terminalDirectoryContextMenu.x) }"
              :style="{ left: `${terminalDirectoryContextMenu.x}px`, top: `${terminalDirectoryContextMenu.y}px` }"
              role="menu"
              @click.stop
              @contextmenu.prevent.stop
            >
              <div
                v-for="item in terminalDirectoryContextMenuItems"
                :key="item.id"
                class="terminal-file-context-menu-row"
                :class="{ separator: item.separatorBefore }"
              >
                <button
                  type="button"
                  role="menuitem"
                  class="terminal-file-context-menu-item"
                  :disabled="!item.enabled"
                  @click="runTerminalFileContextMenuItem(item)"
                >
                  <AppIcon :name="item.icon" :size="15" />
                  <span>{{ item.label }}</span>
                  <AppIcon v-if="item.children?.length" name="chevronRight" :size="14" />
                </button>
                <div v-if="item.children?.length" class="terminal-file-context-submenu" role="menu">
                  <button
                    v-for="child in item.children"
                    :key="child.id"
                    type="button"
                    role="menuitem"
                    class="terminal-file-context-menu-item"
                    :disabled="!child.enabled"
                    @click="runTerminalFileContextMenuItem(child)"
                  >
                    <AppIcon :name="child.icon" :size="15" />
                    <span>{{ child.label }}</span>
                  </button>
                </div>
              </div>
            </div>
            <Teleport to="body">
              <div
                v-if="terminalFileCreateDialog.visible"
                class="modal-backdrop terminal-file-create-backdrop"
                @click.self="closeTerminalFileCreateDialog"
              >
                <section class="terminal-file-create-modal" role="dialog" aria-modal="true">
                  <header>
                    <h2>{{ terminalFileCreateTitle() }}</h2>
                    <button type="button" aria-label="关闭" :disabled="terminalFileCreateDialog.saving" @click="closeTerminalFileCreateDialog">
                      <AppIcon name="x" :size="16" />
                    </button>
                  </header>
                  <div class="terminal-file-create-body">
                    <label class="terminal-file-create-name-row">
                      <span>{{ terminalFileCreateNameLabel() }}</span>
                      <input v-model="terminalFileCreateDialog.name" type="text" :disabled="terminalFileCreateDialog.saving" autofocus @keydown.enter.prevent="saveTerminalFileCreateDialog" />
                    </label>
                    <label v-if="terminalFileCreateDialog.mode === 'symlink'" class="terminal-file-create-name-row">
                      <span>目标路径：</span>
                      <input v-model="terminalFileCreateDialog.targetPath" type="text" :disabled="terminalFileCreateDialog.saving" @keydown.enter.prevent="saveTerminalFileCreateDialog" />
                    </label>
                    <div v-if="terminalFileCreateDialog.mode !== 'symlink'" class="terminal-file-create-permissions">
                      <span class="terminal-file-create-label">权限：</span>
                      <div class="terminal-file-create-permission-grid" role="group" aria-label="权限">
                        <span></span>
                        <span>用户</span>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o400)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o400, $event)" /> R</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o200)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o200, $event)" /> W</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o100)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o100, $event)" /> X</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o4000)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o4000, $event)" /> UID</label>
                        <span></span>
                        <span>组</span>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o040)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o040, $event)" /> R</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o020)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o020, $event)" /> W</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o010)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o010, $event)" /> X</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o2000)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o2000, $event)" /> GID</label>
                        <span></span>
                        <span>其他</span>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o004)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o004, $event)" /> R</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o002)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o002, $event)" /> W</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o001)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o001, $event)" /> X</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o1000)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o1000, $event)" /> 粘性</label>
                      </div>
                    </div>
                    <label v-if="terminalFileCreateDialog.mode !== 'symlink'" class="terminal-file-create-octal-row">
                      <span>八进制</span>
                      <em>{{ getTerminalFileCreateSpecialOctalDigit() }}</em>
                      <input
                        :value="getTerminalFileCreateStandardOctalMode()"
                        type="text"
                        inputmode="numeric"
                        maxlength="3"
                        :disabled="terminalFileCreateDialog.saving"
                        @input="updateTerminalFileCreateOctalMode"
                        @keydown.enter.prevent="saveTerminalFileCreateDialog"
                      />
                    </label>
                    <p v-if="terminalFileCreateDialog.error" class="terminal-file-create-error">{{ terminalFileCreateDialog.error }}</p>
                  </div>
                  <footer>
                    <label v-if="terminalFileCreateDialog.mode !== 'symlink'" class="terminal-file-create-open-after">
                      <input v-model="terminalFileCreateDialog.openAfterCreate" type="checkbox" :disabled="terminalFileCreateDialog.saving" />
                      <span>{{ terminalFileCreateOpenLabel() }}</span>
                    </label>
                    <div>
                      <button type="button" :disabled="terminalFileCreateDialog.saving" @click="closeTerminalFileCreateDialog">取消</button>
                      <button class="primary" type="button" :disabled="terminalFileCreateDialog.saving" @click="saveTerminalFileCreateDialog">
                        {{ terminalFileCreateDialog.saving ? '创建中...' : '确定' }}
                      </button>
                    </div>
                  </footer>
                </section>
              </div>
            </Teleport>
            <Teleport to="body">
              <div
                v-if="terminalFileDeleteDialog.visible"
                class="modal-backdrop terminal-file-delete-backdrop"
                @click.self="closeTerminalFileDeleteDialog"
              >
                <section class="terminal-file-delete-modal" role="dialog" aria-modal="true">
                  <div class="terminal-file-delete-visual" :class="getTerminalFileDeleteDialogVisualType()">
                    <span class="terminal-file-delete-visual-card">
                      <AppIcon :name="getTerminalFileDeleteDialogVisualType() === 'directory' ? 'folder' : 'file'" :size="34" />
                    </span>
                    <span class="terminal-file-delete-alert"><AppIcon name="alert" :size="18" /></span>
                  </div>
                  <h2>{{ getTerminalFileDeleteDialogTitle() }}</h2>
                  <p>{{ getTerminalFileDeleteDialogDescription() }}</p>
                  <p v-if="terminalFileDeleteDialog.error" class="terminal-file-delete-error">{{ terminalFileDeleteDialog.error }}</p>
                  <div class="terminal-file-delete-actions">
                    <button type="button" :disabled="terminalFileDeleteDialog.deleting" @click="closeTerminalFileDeleteDialog">取消</button>
                    <button class="danger" type="button" :disabled="terminalFileDeleteDialog.deleting" @click="confirmTerminalFileDelete">
                      {{ terminalFileDeleteDialog.deleting ? '删除中...' : '删除' }}
                    </button>
                  </div>
                </section>
              </div>
            </Teleport>
            <Teleport to="body">
              <div
                v-if="terminalFilePropertiesDialog.visible"
                class="modal-backdrop terminal-file-properties-backdrop"
                @click.self="closeTerminalFilePropertiesDialog"
              >
                <section class="terminal-file-properties-modal" role="dialog" aria-modal="true">
                  <header class="terminal-file-properties-head">
                    <span class="terminal-file-properties-icon" :class="terminalFilePropertiesDialog.properties?.type || terminalFilePropertiesDialog.entry?.type">
                      <AppIcon :name="(terminalFilePropertiesDialog.properties?.type || terminalFilePropertiesDialog.entry?.type) === 'directory' ? 'folder' : 'file'" :size="18" />
                    </span>
                    <h2>{{ terminalFilePropertiesDialog.entry?.name || terminalFilePropertiesDialog.properties?.name || '文件' }} 的属性</h2>
                    <button
                      class="terminal-file-properties-close"
                      type="button"
                      aria-label="关闭"
                      :disabled="terminalFilePropertiesDialog.saving"
                      @click="closeTerminalFilePropertiesDialog"
                    >
                      <AppIcon name="x" :size="16" />
                    </button>
                  </header>

                <div v-if="terminalFilePropertiesDialog.loading" class="terminal-file-properties-empty">属性读取中...</div>
                <div v-else-if="terminalFilePropertiesDialog.properties" class="terminal-file-properties-body">
                  <p v-if="terminalFilePropertiesDialog.error" class="terminal-file-properties-error">{{ terminalFilePropertiesDialog.error }}</p>

                  <section class="terminal-file-properties-section">
                    <h3>常规</h3>
                    <dl class="terminal-file-properties-details">
                      <dt>类型：</dt>
                      <dd>{{ getTerminalFilePropertiesTypeLabel(terminalFilePropertiesDialog.properties) }}</dd>
                      <dt>位置：</dt>
                      <dd>{{ terminalFilePropertiesDialog.properties.directory }}</dd>
                      <dt>大小：</dt>
                      <dd>{{ formatTerminalFilePropertiesSize(terminalFilePropertiesDialog.properties) }}</dd>
                      <dt>修改时间：</dt>
                      <dd>{{ terminalFilePropertiesDialog.properties.modifiedAt }}</dd>
                      <dt>访问时间：</dt>
                      <dd>{{ terminalFilePropertiesDialog.properties.accessedAt }}</dd>
                      <dt>所有者：</dt>
                      <dd>{{ getTerminalFileOwnerLabel(terminalFilePropertiesDialog.properties) }} [{{ terminalFilePropertiesDialog.properties.uid }}]</dd>
                      <dt>组：</dt>
                      <dd>{{ getTerminalFileGroupLabel(terminalFilePropertiesDialog.properties) }} [{{ terminalFilePropertiesDialog.properties.gid }}]</dd>
                    </dl>
                  </section>

                  <section class="terminal-file-properties-section">
                    <h3>所有权</h3>
                    <label class="terminal-file-properties-field">
                      <span>所有者：</span>
                      <input v-model="terminalFilePropertiesDialog.draft.owner" type="text" :disabled="terminalFilePropertiesDialog.saving" />
                    </label>
                    <label class="terminal-file-properties-field">
                      <span>组：</span>
                      <input v-model="terminalFilePropertiesDialog.draft.group" type="text" :disabled="terminalFilePropertiesDialog.saving" />
                    </label>
                  </section>

                  <section class="terminal-file-properties-section">
                    <h3>权限</h3>
                    <table class="terminal-file-permission-table">
                      <thead>
                        <tr>
                          <th></th>
                          <th>R</th>
                          <th>W</th>
                          <th>X</th>
                          <th>特殊</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <th>用户</th>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o400)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o400, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o200)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o200, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o100)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o100, $event)" /></td>
                          <td><label><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o4000)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o4000, $event)" /> UID</label></td>
                        </tr>
                        <tr>
                          <th>组</th>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o040)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o040, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o020)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o020, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o010)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o010, $event)" /></td>
                          <td><label><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o2000)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o2000, $event)" /> GID</label></td>
                        </tr>
                        <tr>
                          <th>其他</th>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o004)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o004, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o002)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o002, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o001)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o001, $event)" /></td>
                          <td><label><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o1000)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o1000, $event)" /> 粘性</label></td>
                        </tr>
                      </tbody>
                    </table>
                    <label class="terminal-file-octal-field">
                      <span>八进制：</span>
                      <em>{{ getTerminalFileSpecialOctalDigit() }}</em>
                      <input
                        :value="getTerminalFileStandardOctalMode()"
                        type="text"
                        inputmode="numeric"
                        maxlength="3"
                        :disabled="terminalFilePropertiesDialog.saving"
                        @input="updateTerminalFileOctalMode"
                      />
                    </label>
                    <label v-if="terminalFilePropertiesDialog.properties.type === 'directory'" class="terminal-file-recursive-field">
                      <input v-model="terminalFilePropertiesDialog.recursive" type="checkbox" :disabled="terminalFilePropertiesDialog.saving" />
                      <span>应用到此目录及所有子目录/文件</span>
                    </label>
                  </section>
                </div>
                <div v-else class="terminal-file-properties-empty error">{{ terminalFilePropertiesDialog.error || '属性读取失败' }}</div>

                <footer class="terminal-file-properties-actions">
                  <button type="button" :disabled="terminalFilePropertiesDialog.saving" @click="closeTerminalFilePropertiesDialog">取消</button>
                  <button
                    class="primary"
                    type="button"
                    :disabled="terminalFilePropertiesDialog.loading || terminalFilePropertiesDialog.saving || !terminalFilePropertiesDialog.properties"
                    @click="saveTerminalFileProperties"
                  >
                    {{ terminalFilePropertiesDialog.saving ? '保存中...' : '保存' }}
                  </button>
                </footer>
                </section>
              </div>
            </Teleport>
          </div>
        </template>
        <template v-else>
          <div class="terminal-monitor-panel">
            <header class="terminal-monitor-title">
              <strong>资源监控</strong>
              <span>{{ terminalMonitorNodeName }}</span>
              <button
                class="terminal-monitor-refresh"
                type="button"
                title="刷新"
                aria-label="刷新"
                :disabled="!activeTab || isTerminalMonitorLoading"
                @click="loadTerminalMonitor"
              >
                <AppIcon name="refresh" :size="15" />
              </button>
            </header>

            <div v-if="!activeTab" class="terminal-monitor-empty">请选择服务器</div>
            <div v-else class="terminal-monitor-body">
              <p v-if="terminalMonitorError" class="terminal-monitor-error">{{ terminalMonitorError }}</p>

              <template v-if="terminalMonitorData">
                <section class="terminal-monitor-card terminal-monitor-system">
                  <h3><AppIcon name="monitor" :size="15" />系统</h3>
                  <dl>
                    <div>
                      <dt>主机名称</dt>
                      <dd>{{ terminalMonitorData.system.hostname }}</dd>
                    </div>
                    <div>
                      <dt>系统架构</dt>
                      <dd>{{ terminalMonitorData.system.arch }}</dd>
                    </div>
                    <div>
                      <dt>操作系统</dt>
                      <dd>{{ terminalMonitorData.system.os }}</dd>
                    </div>
                    <div>
                      <dt>运行时长</dt>
                      <dd>{{ formatMonitorUptime(terminalMonitorData.system.uptimeSeconds) }}</dd>
                    </div>
                  </dl>
                </section>

                <section class="terminal-monitor-card">
                  <h3><AppIcon name="cpu" :size="15" />CPU</h3>
                  <div class="terminal-monitor-usage">
                    <div class="terminal-monitor-ring" :style="monitorProgressStyle(terminalMonitorData.cpu.usagePercent)">
                      <span>{{ formatMonitorNumber(terminalMonitorData.cpu.usagePercent, 0) }}%</span>
                    </div>
                    <div class="terminal-monitor-usage-main">
                      <div>
                        <span>平均使用率</span>
                        <strong>{{ formatMonitorPercent(terminalMonitorData.cpu.usagePercent) }}</strong>
                      </div>
                      <i><b :style="monitorProgressStyle(terminalMonitorData.cpu.usagePercent)"></b></i>
                      <em>{{ terminalMonitorData.cpu.cores }} CPU</em>
                    </div>
                  </div>
                  <div class="terminal-monitor-loads">
                    <span><strong>{{ formatMonitorNumber(terminalMonitorData.cpu.load1, 2) }}</strong><em>1分钟</em></span>
                    <span><strong>{{ formatMonitorNumber(terminalMonitorData.cpu.load5, 2) }}</strong><em>5分钟</em></span>
                    <span><strong>{{ formatMonitorNumber(terminalMonitorData.cpu.load15, 2) }}</strong><em>15分钟</em></span>
                  </div>
                </section>

                <section class="terminal-monitor-card">
                  <h3><AppIcon name="gauge" :size="15" />内存</h3>
                  <div class="terminal-monitor-usage">
                    <div class="terminal-monitor-ring" :style="monitorProgressStyle(terminalMonitorData.memory.usagePercent)">
                      <span>{{ formatMonitorNumber(terminalMonitorData.memory.usagePercent, 0) }}%</span>
                    </div>
                    <div class="terminal-monitor-usage-main">
                      <div>
                        <span>RAM</span>
                        <strong>{{ formatMonitorPercent(terminalMonitorData.memory.usagePercent) }}</strong>
                      </div>
                      <i><b :style="monitorProgressStyle(terminalMonitorData.memory.usagePercent)"></b></i>
                      <em>{{ formatMonitorBytes(terminalMonitorData.memory.usedBytes) }} / {{ formatMonitorBytes(terminalMonitorData.memory.totalBytes) }}</em>
                    </div>
                  </div>
                  <div class="terminal-monitor-memory-extra">
                    <span>剩余 {{ formatMonitorBytes(terminalMonitorData.memory.availableBytes) }}</span>
                    <span>缓存 {{ formatMonitorBytes(terminalMonitorData.memory.cacheBytes) }}</span>
                  </div>
                </section>

                <section class="terminal-monitor-card">
                  <h3><AppIcon name="network" :size="15" />网络</h3>
                  <div v-if="terminalMonitorData.network.length" class="terminal-monitor-network-list">
                    <div v-for="item in terminalMonitorData.network" :key="item.name" class="terminal-monitor-network-item">
                      <strong>{{ item.name }}</strong>
                      <span><em>↑{{ formatMonitorRate(item.txBytesPerSecond) }}</em><em>↓{{ formatMonitorRate(item.rxBytesPerSecond) }}</em></span>
                      <i><b :style="monitorProgressStyle(Math.min(100, (item.rxBytesPerSecond + item.txBytesPerSecond) / 1024))"></b></i>
                    </div>
                  </div>
                  <p v-else class="terminal-monitor-muted">暂无网卡数据</p>
                </section>

                <section class="terminal-monitor-card">
                  <h3><AppIcon name="hardDrive" :size="15" />磁盘</h3>
                  <div v-if="terminalMonitorData.disks.length" class="terminal-monitor-disk-list">
                    <div v-for="disk in terminalMonitorData.disks" :key="`${disk.filesystem}-${disk.mountpoint}`" class="terminal-monitor-disk-item">
                      <div>
                        <strong>{{ disk.mountpoint }}</strong>
                        <em>{{ disk.filesystem }} · {{ disk.type }}</em>
                      </div>
                      <span>{{ formatMonitorPercent(disk.usagePercent) }}</span>
                      <i><b :style="monitorProgressStyle(disk.usagePercent)"></b></i>
                      <p>{{ formatMonitorBytes(disk.usedBytes) }} / {{ formatMonitorBytes(disk.totalBytes) }}，可用 {{ formatMonitorBytes(disk.availableBytes) }}</p>
                    </div>
                  </div>
                  <p v-else class="terminal-monitor-muted">暂无磁盘数据</p>
                </section>
              </template>
            </div>
          </div>
        </template>
      </div>
    </aside>
    <div
      class="terminal-sidebar-resizer"
      role="separator"
      aria-label="调整主机列表宽度"
      aria-orientation="vertical"
      @mousedown="startSidebarResize($event, { alignToPointer: true })"
    ></div>

    <section class="terminal-workspace">
      <div class="terminal-hint">
        <span>{{ workspaceTitle }}</span>
        <div class="terminal-hint-actions">
          <strong v-if="workspaceStatus">{{ workspaceStatus }}</strong>
          <label class="terminal-highlight-toggle" title="关键词高亮">
            <input v-model="highlightEnabled" type="checkbox" />
            <span></span>
            <em>高亮</em>
          </label>
        </div>
      </div>
      <div class="terminal-tabbar">
        <div ref="terminalTabsRef" class="terminal-tabs" @scroll="syncTerminalTabsScrollState">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            type="button"
            class="terminal-tab"
            :data-terminal-tab-id="tab.id"
            :class="{ active: tab.id === activeTabId, closed: tab.status === 'closed', error: tab.status === 'error' }"
            @click="activateTab(tab.id)"
          >
            <span class="terminal-tab-label">{{ tab.host.name }}</span>
            <span class="terminal-tab-status" :class="[tab.status, { unread: tab.hasUnreadOutput && tab.id !== activeTabId }]"></span>
            <span class="terminal-tab-close" title="关闭" @click.stop="closeTab(tab)"><AppIcon name="x" :size="13" /></span>
          </button>
        </div>
        <div v-if="tabs.length" class="terminal-tab-overview" @click.stop>
          <button
            type="button"
            class="terminal-tab-scroll-button previous"
            title="向左移动标签"
            aria-label="向左移动标签"
            :disabled="!canScrollTerminalTabsLeft"
            @click="scrollTerminalTabs('left')"
          >
            <AppIcon name="chevronRight" :size="15" />
          </button>
          <button
            type="button"
            class="terminal-tab-scroll-button next"
            title="向右移动标签"
            aria-label="向右移动标签"
            :disabled="!canScrollTerminalTabsRight"
            @click="scrollTerminalTabs('right')"
          >
            <AppIcon name="chevronRight" :size="15" />
          </button>
          <button
            type="button"
            class="terminal-tab-menu-trigger"
            :class="{ active: isTerminalTabMenuOpen }"
            title="打开的标签"
            aria-label="打开的标签"
            :aria-expanded="isTerminalTabMenuOpen"
            @click="toggleTerminalTabMenu"
          >
            <AppIcon name="link" :size="16" />
          </button>
          <div v-if="isTerminalTabMenuOpen" class="terminal-tab-menu" role="menu" aria-label="打开的标签">
            <header>打开的标签</header>
            <button
              v-for="(tab, index) in tabs"
              :key="`menu-${tab.id}`"
              type="button"
              class="terminal-tab-menu-item"
              :class="{ active: tab.id === activeTabId, closed: tab.status === 'closed', error: tab.status === 'error' }"
              role="menuitem"
              @click="selectTerminalTabFromMenu(tab)"
            >
              <span class="terminal-tab-menu-check">
                <AppIcon v-if="tab.id === activeTabId" name="check" :size="15" />
              </span>
              <AppIcon name="server" :size="15" />
              <span class="terminal-tab-menu-label">{{ index + 1 }} {{ tab.host.name }}</span>
              <span class="terminal-tab-status" :class="[tab.status, { unread: tab.hasUnreadOutput && tab.id !== activeTabId }]"></span>
            </button>
          </div>
        </div>
      </div>
      <div class="terminal-screen">
        <div v-if="!tabs.length" class="terminal-empty">双击左侧主机名连接 SSH 终端。</div>
        <div
          v-for="tab in tabs"
          :key="tab.id"
          :ref="(element) => setTerminalContainer(tab.id, element)"
          class="terminal-panel"
          :class="{ active: tab.id === activeTabId }"
          :aria-hidden="tab.id !== activeTabId"
        ></div>
      </div>
    </section>
  </main>
</template>
